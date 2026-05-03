# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Niveles de último curso: al confirmar el paso de curso, sus alumnos se archivan
# automáticamente (no promocionan a ningún grupo nuevo).
TERMINAL_LEVELS = {'bach2', 'cfgm2', 'cfgs2', 'fpb2'}

_COURSE_LEVELS = [
    # ESO
    ('eso1', '1º ESO'),
    ('eso2', '2º ESO'),
    ('eso3', '3º ESO'),
    ('eso4', '4º ESO'),
    # Bachillerato
    ('bach1', '1º Bachillerato'),
    ('bach2', '2º Bachillerato'),
    # Formación Profesional Básica
    ('fpb1', 'FPB — 1er curso'),
    ('fpb2', 'FPB — 2º curso'),
    # Ciclos Formativos Grado Medio
    ('cfgm1', 'CFGM — 1er curso'),
    ('cfgm2', 'CFGM — 2º curso'),
    # Ciclos Formativos Grado Superior
    ('cfgs1', 'CFGS — 1er curso'),
    ('cfgs2', 'CFGS — 2º curso'),
    # Programas de atención a la diversidad
    ('pmar', 'PMAR'),
    ('pmar3', 'PMAR 3º ESO'),
    # Otros
    ('otro', 'Otro nivel'),
]


class YearWizardGroupLine(models.TransientModel):
    """Grupo del nuevo año, editable en el paso 2 del wizard de paso de curso."""
    _name = 'aula_metrics.year_wizard_group_line'
    _description = 'Línea de grupo para el wizard de nuevo curso'
    _order = 'course_level, name'

    wizard_id = fields.Many2one(
        'aula_metrics.new_academic_year_wizard',
        ondelete='cascade',
        required=True,
    )
    name = fields.Char(string='Nombre del grupo', required=True)
    course_level = fields.Selection(_COURSE_LEVELS, string='Nivel', required=True)
    tutor_id = fields.Many2one(
        'res.users',
        string='Tutor/a',
        domain=[('share', '=', False)],
    )
    source_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo origen',
        readonly=True,
        help='Grupo del año anterior del que procede esta línea.',
    )
    is_new = fields.Boolean(
        string='Grupo nuevo',
        default=False,
        readonly=True,
        help='Marcado cuando el orientador añade el grupo manualmente.',
    )

    @api.depends('name', 'course_level')
    def _compute_display_name(self):
        """Muestra 'Nombre (Nivel)' en los selectores del paso 3."""
        level_labels = dict(self._fields['course_level'].selection)
        for rec in self:
            level = level_labels.get(rec.course_level, rec.course_level or '')
            rec.display_name = '%s  (%s)' % (rec.name or '…', level)


class YearWizardPromoLine(models.TransientModel):
    """Mapeo origen→destino para la promoción masiva de alumnos (paso 3)."""
    _name = 'aula_metrics.year_wizard_promo_line'
    _description = 'Línea de promoción para el wizard de nuevo curso'
    _order = 'source_group_level, source_group_name'

    wizard_id = fields.Many2one(
        'aula_metrics.new_academic_year_wizard',
        ondelete='cascade',
        required=True,
    )
    source_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo origen',
        required=True,
        readonly=True,
    )
    source_group_name = fields.Char(
        related='source_group_id.name',
        string='Grupo',
        readonly=True,
        store=True,
    )
    source_group_level = fields.Selection(
        _COURSE_LEVELS,
        related='source_group_id.course_level',
        string='Nivel origen',
        readonly=True,
        store=True,
    )
    student_count = fields.Integer(
        string='Alumnos',
        readonly=True,
        help='Número de alumnos en el momento de iniciar el paso de curso.',
    )
    dest_group_line_id = fields.Many2one(
        'aula_metrics.year_wizard_group_line',
        string='Grupo destino (nuevo año)',
        help='Grupo del nuevo año al que se moverán los alumnos.',
    )
    is_terminal_level = fields.Boolean(
        compute='_compute_is_terminal',
        store=True,
        string='Nivel terminal',
        help='True para niveles de último curso (2º Bach, CFGM 2º, CFGS 2º, FPB 2º). '
             'Sus alumnos se archivarán automáticamente al confirmar.',
    )

    @api.depends('source_group_level')
    def _compute_is_terminal(self):
        for rec in self:
            rec.is_terminal_level = rec.source_group_level in TERMINAL_LEVELS
