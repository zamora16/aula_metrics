# -*- coding: utf-8 -*-
import datetime
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .year_wizard_group_line import _COURSE_LEVELS

_logger = logging.getLogger(__name__)

# Grupos típicos que se pre-rellenan en el paso 2 (el usuario puede editarlos)
_DEFAULT_GROUPS = [
    ('1º ESO A', 'eso1'),
    ('1º ESO B', 'eso1'),
    ('2º ESO A', 'eso2'),
    ('2º ESO B', 'eso2'),
    ('3º ESO A', 'eso3'),
    ('3º ESO B', 'eso3'),
    ('4º ESO A', 'eso4'),
    ('4º ESO B', 'eso4'),
    ('1º Bachillerato A', 'bach1'),
    ('1º Bachillerato B', 'bach1'),
    ('2º Bachillerato A', 'bach2'),
    ('2º Bachillerato B', 'bach2'),
]


class FirstYearGroupLine(models.TransientModel):
    """Línea de grupo en el paso 2 del wizard de configuración inicial."""
    _name = 'aula_metrics.first_year_group_line'
    _description = 'Línea de grupo para configuración inicial'
    _order = 'course_level, name'

    wizard_id = fields.Many2one(
        'aula_metrics.first_year_wizard',
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


class FirstYearWizard(models.TransientModel):
    """
    Wizard de configuración inicial — 2 pasos:

    Paso 1: Nombre y fechas del primer curso académico.
    Paso 2: Tabla editable de grupos (pre-rellenada con una estructura típica).

    Al confirmar:
      - Se crea el AcademicYear y sus grupos.
      - El curso se activa automáticamente.
      - Se abre el wizard de importación de alumnos (CSV) listo para usarse.
    """
    _name = 'aula_metrics.first_year_wizard'
    _description = 'Asistente de Configuración Inicial'

    step = fields.Selection([
        ('1', 'Datos del curso'),
        ('2', 'Grupos y tutores'),
    ], string='Paso actual', default='1', required=True)

    # ── Paso 1 ────────────────────────────────────────────────────────────────
    year_name = fields.Char(
        string='Nombre del curso',
        required=True,
        default=lambda self: self._default_year_name(),
        help='Ejemplo: 2025-2026',
    )
    date_start = fields.Date(string='Fecha de inicio')
    date_end = fields.Date(string='Fecha de fin')

    # ── Paso 2 ────────────────────────────────────────────────────────────────
    group_line_ids = fields.One2many(
        'aula_metrics.first_year_group_line',
        'wizard_id',
        string='Grupos',
    )

    # ── Defaults ──────────────────────────────────────────────────────────────

    @staticmethod
    def _default_year_name():
        today = datetime.date.today()
        start = today.year if today.month >= 9 else today.year - 1
        return '%d-%d' % (start, start + 1)

    # ── Navegación ────────────────────────────────────────────────────────────

    def action_step1_to_2(self):
        self.ensure_one()
        self._validate_step1()
        if not self.group_line_ids:
            self._prefill_groups()
        self.step = '2'
        return self._reload_action()

    def action_step2_to_1(self):
        self.ensure_one()
        self.step = '1'
        return self._reload_action()

    # ── Confirmación ──────────────────────────────────────────────────────────

    def action_confirm(self):
        self.ensure_one()
        self._validate_step1()
        if not self.group_line_ids:
            raise UserError(_('Debes definir al menos un grupo antes de confirmar.'))

        # 1. Crear el AcademicYear
        year_vals = {'name': self.year_name.strip(), 'state': 'draft'}
        if self.date_start:
            year_vals['date_start'] = self.date_start
        if self.date_end:
            year_vals['date_end'] = self.date_end
        new_year = self.env['aula_metrics.academic_year'].create(year_vals)
        _logger.info('Primer curso creado: %s (id=%s)', new_year.name, new_year.id)

        # 2. Crear grupos
        for line in self.group_line_ids:
            self.env['aula_metrics.academic_group'].create({
                'name': line.name,
                'course_level': line.course_level,
                'academic_year_id': new_year.id,
                'tutor_id': line.tutor_id.id if line.tutor_id else False,
            })

        # 3. Activar el curso
        new_year.action_activate()
        _logger.info('Primer curso %s activado con %d grupos', new_year.name, len(self.group_line_ids))

        # 4. Abrir directamente el importador de alumnos CSV
        return self.env['ir.actions.act_window']._for_xml_id(
            'aula_metrics.action_student_import_wizard'
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _prefill_groups(self):
        """Rellena la tabla con una estructura de grupos típica."""
        self.env['aula_metrics.first_year_group_line'].create([
            {'wizard_id': self.id, 'name': name, 'course_level': level}
            for name, level in _DEFAULT_GROUPS
        ])

    def _validate_step1(self):
        if not self.year_name or not self.year_name.strip():
            raise UserError(_('Introduce el nombre del curso académico.'))
        existing = self.env['aula_metrics.academic_year'].search(
            [('name', '=', self.year_name.strip())], limit=1
        )
        if existing:
            raise UserError(_(
                'Ya existe un curso académico con el nombre "%s". '
                'Elige un nombre diferente.'
            ) % self.year_name.strip())
        active = self.env['aula_metrics.academic_year'].search(
            [('state', '=', 'active')], limit=1
        )
        if active:
            raise UserError(_(
                'Ya existe un curso activo (%s). '
                'Usa "Pasar de Curso" para crear el siguiente.'
            ) % active.name)

    def _reload_action(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
