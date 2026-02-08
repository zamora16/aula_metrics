# -*- coding: utf-8 -*-

from odoo import api, fields, models
import re
import json

class QualitativeResponse(models.Model):
    _name = 'aulametrics.qualitative_response'
    _description = 'Respuesta Cualitativa (Texto Abierto)'
    _order = 'response_date desc'
    
    # Relaciones
    student_id = fields.Many2one('res.partner', string='Estudiante', required=True, ondelete='cascade', index=True)
    academic_group_id = fields.Many2one('aulametrics.academic_group', string='Grupo Académico', required=True, index=True)
    evaluation_id = fields.Many2one('aulametrics.evaluation', string='Evaluación', required=True, index=True)
    survey_id = fields.Many2one('survey.survey', string='Cuestionario', required=True)
    question_id = fields.Many2one('survey.question', string='Pregunta', required=True)
    user_input_id = fields.Many2one('survey.user_input', string='Respuesta de Usuario', ondelete='cascade')
    
    # Contenido
    response_text = fields.Text('Respuesta', required=True)
    response_date = fields.Datetime('Fecha de Respuesta', default=fields.Datetime.now, index=True)
    
    # Análisis automático
    word_count = fields.Integer('Número de Palabras', compute='_compute_word_count', store=True)
    detected_keywords = fields.Char('Palabras Clave Detectadas')  # JSON: ["suicidio", "depresión"]
    has_alert_keywords = fields.Boolean('Contiene Palabras de Alerta', compute='_compute_alert_keywords', store=True, index=True)
    
    # Campos computados para anonimización
    display_name = fields.Char('Nombre Mostrado', compute='_compute_display_name')
    course_level = fields.Char('Nivel de Curso', compute='_compute_course_level', store=True)
    
    @api.depends('response_text')
    def _compute_word_count(self):
        """Calcula número de palabras en la respuesta."""
        for record in self:
            record.word_count = len(record.response_text.split()) if record.response_text else 0
    
    @api.depends('response_text')
    def _compute_alert_keywords(self):
        """Detecta palabras clave críticas configuradas por el centro."""
        for record in self:
            if not record.response_text:
                record.has_alert_keywords = False
                record.detected_keywords = False
                continue
            
            # Obtener palabras clave activas del sistema
            alert_keywords = self.env['aulametrics.alert_keyword'].search([
                ('active', '=', True)
            ])
            
            if not alert_keywords:
                record.has_alert_keywords = False
                record.detected_keywords = False
                continue
            
            # Buscar coincidencias
            text_lower = record.response_text.lower()
            found = []
            
            for keyword_record in alert_keywords:
                keyword = keyword_record.keyword.lower()
                if keyword in text_lower:
                    found.append(keyword_record.keyword)
            
            record.has_alert_keywords = bool(found)
            record.detected_keywords = json.dumps(found, ensure_ascii=False) if found else False
    
    @api.depends('student_id')
    def _compute_display_name(self):
        """Nombre mostrado según rol del usuario."""
        user = self.env.user
        is_counselor = user.has_group('aula_metrics.group_counselor')
        
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
    _name = 'aulametrics.alert_keyword'
    _description = 'Palabra Clave para Alertas Automáticas'
    _order = 'sequence, keyword'
    
    keyword = fields.Char('Palabra Clave', required=True, help='Palabra que activará alerta automática')
    description = fields.Text('Descripción', help='Contexto o razón de esta palabra clave')
    severity = fields.Selection([
        ('low', 'Baja'),
        ('moderate', 'Moderada'),
        ('high', 'Alta'),
        ('critical', 'Crítica')
    ], string='Gravedad', default='moderate', required=True)
    
    is_system_default = fields.Boolean('Palabra del Sistema', default=False, readonly=True, 
                                       help='Palabras configuradas por defecto (no se pueden eliminar)')
    is_variant = fields.Boolean('Es Variante', default=False, readonly=True,
                                help='Variante automática generada de otra palabra')
    parent_keyword_id = fields.Many2one('aulametrics.alert_keyword', string='Palabra Principal',
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
                    self.env['aulametrics.alert_keyword'].search([
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
            existing = self.env['aulametrics.alert_keyword'].search([
                ('keyword', '=', variant)
            ], limit=1)
            
            if not existing:
                try:
                    self.env['aulametrics.alert_keyword'].create({
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
        Genera variantes gramaticales comunes en español.
        Solo para casos más comunes y relevantes.
        """
        variants = set()
        
        # Diccionario de raíces comunes y sus variantes
        common_variants = {
            # Suicidio
            'suicidio': ['suicida', 'suicidas', 'suicidarse', 'suicidar', 'suicidó', 'suicidándose'],
            'suicida': ['suicidio', 'suicidas', 'suicidarse'],
            
            # Depresión
            'depresion': ['depresivo', 'depresiva', 'deprimido', 'deprimida', 'deprimir'],
            'depresión': ['depresivo', 'depresiva', 'deprimido', 'deprimida', 'deprimir'],
            'depresivo': ['depresion', 'depresión', 'deprimido'],
            'deprimido': ['depresion', 'depresión', 'deprimir'],
            
            # Ansiedad
            'ansiedad': ['ansioso', 'ansiosa', 'ansiedades'],
            'ansioso': ['ansiedad'],
            
            # Acoso
            'acoso': ['acosar', 'acosado', 'acosada', 'acosador', 'acosadora', 'acosos'],
            'acosar': ['acoso', 'acosado', 'acosador'],
            'acosado': ['acoso', 'acosar'],
            
            # Bullying
            'bullying': ['bully', 'bullyng'],  # error ortográfico común
            
            # Maltrato
            'maltrato': ['maltratar', 'maltratado', 'maltratada', 'maltratador'],
            'maltratar': ['maltrato', 'maltratado'],
            
            # Abuso
            'abuso': ['abusar', 'abusado', 'abusada', 'abusador', 'abusiva', 'abusivo'],
            'abusar': ['abuso', 'abusado', 'abusador'],
            
            # Violencia
            'violencia': ['violento', 'violenta', 'violentar'],
            'violento': ['violencia'],
            
            # Muerte
            'muerte': ['morir', 'muerto', 'muerta', 'muriendo', 'morirse'],
            'morir': ['muerte', 'muerto', 'muriendo'],
            'muerto': ['muerte', 'morir'],
            
            # Matar
            'matar': ['mata', 'mato', 'matado', 'matando', 'matarme', 'matarse'],
            'matarme': ['matar', 'matarse'],
            
            # Cortar (autolesión)
            'cortar': ['corto', 'cortado', 'cortando', 'cortarme'],
            'cortarme': ['cortar', 'cortarse'],
            
            # Miedo
            'miedo': ['miedos', 'miedoso', 'temer', 'temor'],
            'temer': ['miedo', 'temor'],
            
            # Tristeza
            'tristeza': ['triste', 'tristes', 'entristecer'],
            'triste': ['tristeza', 'tristes'],
            
            # Soledad
            'soledad': ['solo', 'sola', 'solos', 'solas'],
            'solo': ['soledad', 'sola'],
            
            # Llorar
            'llorar': ['lloro', 'llora', 'llorando', 'lloré'],
            'lloro': ['llorar', 'llorando'],
            
            # Pegar
            'pegar': ['pego', 'pega', 'pegado', 'pegando', 'pegaron'],
            
            # Golpear
            'golpear': ['golpe', 'golpes', 'golpeado', 'golpeando'],
            'golpe': ['golpear', 'golpes', 'golpeado'],
            
            # Amenaza
            'amenaza': ['amenazar', 'amenazado', 'amenazas', 'amenazador'],
            'amenazar': ['amenaza', 'amenazado'],
            
            # Odio
            'odio': ['odiar', 'odiado', 'odia'],
            'odiar': ['odio', 'odiado'],
            
            # Pánico
            'panico': ['panicos'],
            'pánico': ['pánicos'],
        }
        
        # Buscar en el diccionario
        if word in common_variants:
            variants.update(common_variants[word])
        
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
