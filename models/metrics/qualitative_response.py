# -*- coding: utf-8 -*-

from odoo import api, fields, models
import logging
import re
import unicodedata
from odoo.addons.aula_metrics.utils import role_service

_logger = logging.getLogger(__name__)
from odoo.addons.aula_metrics.utils.constants import (
    GROUP_COUNSELOR,
    COURSE_LEVEL_MAP as _COURSE_LEVEL_MAP,
    QUERY_LIMIT_QUALITATIVE,
)

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

    @api.depends('response_text')
    def _compute_word_count(self):
        for record in self:
            record.word_count = len(record.response_text.split()) if record.response_text else 0

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
        alert_keywords = self.env['aula_metrics.alert_keyword'].search([('active', '=', True)])
        # Compile all patterns once outside the record loop.
        # _normalize_text already handles accents on both sides, so keywords
        # stored with or without tildes all resolve to the same pattern.
        compiled = [
            (kw, re.compile(r'\b' + re.escape(self._normalize_text(kw.keyword)) + r'\b'))
            for kw in alert_keywords
        ]
        for record in self:
            if not record.response_text or not compiled:
                record.has_alert_keywords = False
                record.detected_keyword_ids = [(5, 0, 0)]
                continue
            text_normalized = self._normalize_text(record.response_text)
            matched_ids = [kw.id for kw, pattern in compiled if pattern.search(text_normalized)]
            record.has_alert_keywords = bool(matched_ids)
            record.detected_keyword_ids = [(6, 0, matched_ids)] if matched_ids else [(5, 0, 0)]
    
    @api.model
    def get_for_dashboard(self, role_info, eval_ids=None):
        """
        Respuestas cualitativas filtradas por rol y evaluaciones seleccionadas.

        Centraliza el filtrado de datos cualitativos para el dashboard,
        sacando esta lógica del controlador HTTP.

        Args:
            role_info (dict): resultado de role_service.get_role_info().
            eval_ids (list[int] | None): evaluaciones a filtrar; None = todas.

        Returns:
            recordset de aula_metrics.qualitative_response (vacío si sin acceso).
        """
        domain = []
        if eval_ids:
            domain.append(('evaluation_id', 'in', eval_ids))

        filtered_domain = role_service.apply_group_filter(
            domain, role_info, field='academic_group_id'
        )
        if filtered_domain is None:
            return self.browse()

        return self.search(
            filtered_domain,
            order='response_date desc',
            limit=QUERY_LIMIT_QUALITATIVE,
        )

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
    
    @api.depends('academic_group_id.course_level')
    def _compute_course_level(self):
        """Extrae nivel educativo legible desde el campo de selección del grupo."""
        for record in self:
            if record.academic_group_id and record.academic_group_id.course_level:
                record.course_level = _COURSE_LEVEL_MAP.get(
                    record.academic_group_id.course_level,
                    record.academic_group_id.course_level
                )
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
    
    child_keyword_ids = fields.One2many(
        'aula_metrics.alert_keyword',
        'parent_keyword_id',
        string='Variantes Generadas',
        readonly=True,
    )

    active = fields.Boolean('Activa', default=True)
    sequence = fields.Integer('Secuencia', default=10)
    
    _sql_constraints = [
        ('keyword_unique', 'unique(keyword)', 'Esta palabra clave ya existe en el sistema.')
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Al crear palabras clave, generar variantes automáticamente."""
        records = super().create(vals_list)
        for record in records:
            if not record.is_variant and not record.is_system_default:
                record._generate_variants()
        return records
    
    def write(self, vals):
        """Al actualizar keyword, regenerar variantes."""
        res = super().write(vals)
        if 'keyword' in vals:
            for record in self:
                if not record.is_variant and not record.is_system_default:
                    # Compute new variants BEFORE touching the DB so that if
                    # _collect_variant_words raises, old variants are still intact.
                    new_variants = record._collect_variant_words()
                    self.env['aula_metrics.alert_keyword'].search([
                        ('parent_keyword_id', '=', record.id)
                    ]).unlink()
                    record._persist_variants(new_variants)
        return res

    def _collect_variant_words(self):
        """Pure computation: returns the set of variant strings for this keyword.
        No DB writes — safe to call before unlinking old variants."""
        self.ensure_one()
        keyword_lower = self.keyword.lower()
        # Accent variants are intentionally NOT generated here.
        # _normalize_text strips diacritics on both the response text and the
        # keyword at match time, so accent-only variants add no detection value
        # while polluting the keyword table with orthographically invalid words.
        variants = set(self._generate_grammatical_variants(keyword_lower))
        variants.discard(keyword_lower)
        return {v for v in variants if v and len(v) > 2}

    def _persist_variants(self, variants):
        """Creates variant records for the given set of keyword strings."""
        self.ensure_one()
        for variant in variants:
            if self.env['aula_metrics.alert_keyword'].search(
                [('keyword', '=', variant)], limit=1
            ):
                continue
            try:
                self.env['aula_metrics.alert_keyword'].create({
                    'keyword': variant,
                    'description': f'Variante automática de "{self.keyword}"',
                    'severity': self.severity,
                    'is_variant': True,
                    'parent_keyword_id': self.id,
                    'active': self.active,
                    'sequence': self.sequence + 1,
                })
            except Exception as e:
                # Only expected cause: unique constraint race between processes.
                _logger.warning(
                    '_persist_variants: no se pudo crear variante "%s" para keyword %s: %s',
                    variant, self.id, e,
                )

    def _generate_variants(self):
        """Genera y persiste variantes automáticas de esta palabra clave."""
        self.ensure_one()
        self._persist_variants(self._collect_variant_words())

    def _generate_grammatical_variants(self, word):
        """Genera el plural simple de la palabra (añade 's' o 'es')."""
        variants = set()
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
