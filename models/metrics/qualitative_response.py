# -*- coding: utf-8 -*-

from odoo import api, fields, models
import re
import unicodedata
from ...utils.constants import GROUP_COUNSELOR

class QualitativeResponse(models.Model):
    _name = 'aula_metrics.qualitative_response'
    _description = 'Respuesta Cualitativa (Texto Abierto)'
    _order = 'response_date desc'

    def _normalize_text(self, text):
        """Removes accents and lowercases text for keyword matching."""
        return ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        ).lower()
    
    # Relaciones
    student_id = fields.Many2one('res.partner', string='Estudiante', required=True, ondelete='cascade', index=True)
    academic_group_id = fields.Many2one('aula_metrics.academic_group', string='Grupo Académico', required=True, index=True)
    evaluation_id = fields.Many2one('aula_metrics.evaluation', string='Evaluación', required=True, ondelete='cascade', index=True)
    survey_id = fields.Many2one('survey.survey', string='Cuestionario', required=True, ondelete='restrict')
    question_id = fields.Many2one('survey.question', string='Pregunta', required=True, ondelete='restrict')
    user_input_id = fields.Many2one('survey.user_input', string='Respuesta de Usuario', ondelete='cascade')
    
    # Contenido
    response_text = fields.Text('Respuesta', required=True)
    response_date = fields.Datetime('Fecha de Respuesta', default=fields.Datetime.now, index=True)
    
    # Análisis automático
    word_count = fields.Integer('Número de Palabras', compute='_compute_word_count', store=True)
    detected_keyword_ids = fields.Many2many(
        'aula_metrics.alert_keyword',
        'qualitative_response_keyword_rel',
        'response_id',
        'keyword_id',
        string='Palabras Clave Detectadas',
        help='Palabras clave detectadas en la respuesta',
        index=True
    )
    has_alert_keywords = fields.Boolean('Contiene Palabras de Alerta', compute='_compute_alert_keywords', store=True, index=True)
    
    # Campos computados para anonimización
    display_name = fields.Char('Nombre Mostrado', compute='_compute_display_name')
    course_level = fields.Char('Nivel de Curso', compute='_compute_course_level', store=True)
    
    @api.depends('response_text')
    def _compute_alert_keywords(self):
        for record in self:
            if not record.response_text:
                record.has_alert_keywords = False
                record.detected_keyword_ids = [(5, 0, 0)]
                continue
            alert_keywords = self.env['aula_metrics.alert_keyword'].search([('active', '=', True)])
            if not alert_keywords:
                record.has_alert_keywords = False
                record.detected_keyword_ids = [(5, 0, 0)]
                continue
            text_normalized = self._normalize_text(record.response_text)
            found = alert_keywords.filtered(
                lambda k: bool(re.search(
                    r'\b' + re.escape(self._normalize_text(k.keyword)) + r'\b',
                    text_normalized
                ))
            )
            record.has_alert_keywords = bool(found)
            record.detected_keyword_ids = [(6, 0, found.ids)] if found else [(5, 0, 0)]
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Trigger alert creation AFTER the record and its computed fields are persisted.
        # Done here (not inside _compute_alert_keywords) to avoid calling create()
        # inside a stored compute, which causes ORM flush recursion errors.
        for record in records:
            if record.has_alert_keywords:
                self.env['aula_metrics.alert'].sudo().create_qualitative_alert(record)
        return records

    @api.depends('student_id')
    def _compute_display_name(self):
        """Nombre mostrado según rol del usuario."""
        user = self.env.user
        is_counselor = user.has_group(GROUP_COUNSELOR)
        
        for record in self:
            if is_counselor:
                record.display_name = record.student_id.name
            else:
                record.display_name = "Estudiante Anónimo"
    
    @api.depends('academic_group_id')
    def _compute_course_level(self):
        """Extrae nivel de curso sin identificar grupo específico."""
        for record in self:
            if record.academic_group_id:
                # "2º A" → "2º ESO"
                name = record.academic_group_id.name
                match = re.match(r'(\d+)º', name)
                record.course_level = f"{match.group(1)}º ESO" if match else "Curso no especificado"
            else:
                record.course_level = False


class AlertKeyword(models.Model):
    _name = 'aula_metrics.alert_keyword'
    _description = 'Palabra Clave para Alertas Automáticas'
    _order = 'sequence, keyword'
    
    keyword = fields.Char('Palabra Clave', required=True, help='Palabra que activará alerta automática')
    description = fields.Text('Descripción', help='Contexto o razón de esta palabra clave')
    severity = fields.Selection([
        ('low', 'Baja'),
        ('moderate', 'Moderada'),
        ('high', 'Alta')
    ], string='Gravedad', default='moderate', required=True)
    
    is_system_default = fields.Boolean('Palabra del Sistema', default=False, readonly=True, 
                                       help='Palabras configuradas por defecto (no se pueden eliminar)')
    is_variant = fields.Boolean('Es Variante', default=False, readonly=True,
                                help='Variante automática generada de otra palabra')
    parent_keyword_id = fields.Many2one('aula_metrics.alert_keyword', string='Palabra Principal',
                                       ondelete='cascade', readonly=True,
                                       help='Palabra clave de la que se generó esta variante')
    
    active = fields.Boolean('Activa', default=True)
    sequence = fields.Integer('Secuencia', default=10)
    
    _sql_constraints = [
        ('keyword_unique', 'unique(keyword)', 'Esta palabra clave ya existe en el sistema.')
    ]
    
    @api.model
    def create(self, vals):
        """Al crear una palabra, generar variantes automáticamente."""
        record = super().create(vals)
        
        # Solo generar variantes si no es una variante en sí misma
        if not record.is_variant and not record.is_system_default:
            record._generate_variants()
        
        return record
    
    def write(self, vals):
        """Al actualizar keyword, regenerar variantes."""
        res = super().write(vals)
        
        if 'keyword' in vals:
            for record in self:
                if not record.is_variant and not record.is_system_default:
                    # Eliminar variantes antiguas
                    self.env['aula_metrics.alert_keyword'].search([
                        ('parent_keyword_id', '=', record.id)
                    ]).unlink()
                    # Generar nuevas variantes
                    record._generate_variants()
        
        return res
    
    def _generate_variants(self):
        """
        Genera variantes automáticas de la palabra clave:
        1. Variantes ortográficas (con/sin tildes)
        2. Variantes gramaticales comunes (verbos, sustantivos)
        """
        self.ensure_one()
        
        variants = set()
        keyword_lower = self.keyword.lower()
        
        # 1. Variantes ortográficas (tildes)
        variants.update(self._generate_accent_variants(keyword_lower))
        
        # 2. Variantes gramaticales (formas verbales, plural, etc)
        variants.update(self._generate_grammatical_variants(keyword_lower))
        
        # Eliminar la palabra original y variantes vacías
        variants.discard(keyword_lower)
        variants = {v for v in variants if v and len(v) > 2}
        
        # Crear registros de variantes
        for variant in variants:
            # Verificar si ya existe (para evitar duplicados)
            existing = self.env['aula_metrics.alert_keyword'].search([
                ('keyword', '=', variant)
            ], limit=1)
            
            if not existing:
                try:
                    self.env['aula_metrics.alert_keyword'].create({
                        'keyword': variant,
                        'description': f'Variante automática de "{self.keyword}"',
                        'severity': self.severity,
                        'is_variant': True,
                        'parent_keyword_id': self.id,
                        'active': self.active,
                        'sequence': self.sequence + 1
                    })
                except Exception:
                    # Si falla (ej: duplicado por constraint), continuar
                    pass
    
    def _generate_accent_variants(self, word):
        """Genera variantes con/sin tildes."""
        variants = set()
        
        # Mapa de caracteres con tilde → sin tilde
        accent_map = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ü': 'u', 'ñ': 'n'
        }
        
        # Versión sin tildes
        no_accent = word
        for accented, plain in accent_map.items():
            no_accent = no_accent.replace(accented, plain)
        
        if no_accent != word:
            variants.add(no_accent)
        
        # Versión con tildes comunes (solo si no tiene)
        if 'a' in word or 'e' in word or 'i' in word or 'o' in word or 'u' in word:
            # Para palabras cortas, generar variantes con tildes comunes
            for vowel, accented in [('a', 'á'), ('e', 'é'), ('i', 'í'), ('o', 'ó'), ('u', 'ú')]:
                if vowel in word:
                    variants.add(word.replace(vowel, accented, 1))
        
        return variants
    
    def _generate_grammatical_variants(self, word):
        """
        Genera variantes gramaticales simples (plurales).
        """
        variants = set()
        # Plurales simples (agregar 's' o 'es')
        if not word.endswith('s'):
            if word.endswith(('a', 'e', 'i', 'o', 'u')):
                variants.add(word + 's')
            else:
                variants.add(word + 'es')
        return variants
    
    def unlink(self):
        """Prevenir eliminación de palabras del sistema."""
        for record in self:
            if record.is_system_default:
                raise models.ValidationError(
                    f'No se puede eliminar la palabra clave "{record.keyword}" porque es una palabra del sistema. '
                    'Puedes desactivarla en su lugar.'
                )
        return super().unlink()
