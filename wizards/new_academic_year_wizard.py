# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NewAcademicYearWizard(models.TransientModel):
    """
    Wizard para abrir un nuevo curso académico.

    Flujo:
    1. El usuario introduce el nombre del nuevo curso (ej: 2026-2027)
    2. Se crean los nuevos grupos vacíos copiando la estructura del curso origen.
    3. Los grupos del curso origen se archivan y el curso se cierra.
    4. Los alumnos permanecen vinculados a sus grupos históricos (archivados).
       El tutor/orientador los reasigna manualmente a los nuevos grupos.
    """
    _name = 'aula_metrics.new_academic_year_wizard'
    _description = 'Asistente de Nuevo Curso Académico'

    # ── Origen ────────────────────────────────────────────────────────────────
    source_year_id = fields.Many2one(
        'aula_metrics.academic_year',
        string='Curso a copiar',
        required=True,
        default=lambda self: self.env['aula_metrics.academic_year'].get_current_year(),
        help='Curso académico cuyos grupos se copiarán como base del nuevo curso.'
    )

    # ── Nuevo curso ───────────────────────────────────────────────────────────
    new_year_name = fields.Char(
        string='Nombre del nuevo curso',
        required=True,
        default=lambda self: self._default_new_year_name(),
        help='Ejemplo: 2026-2027'
    )

    new_year_date_start = fields.Date(string='Fecha de inicio del nuevo curso')
    new_year_date_end = fields.Date(string='Fecha de fin del nuevo curso')

    # ── Preview ───────────────────────────────────────────────────────────────
    preview_group_count = fields.Integer(
        string='Grupos a crear',
        compute='_compute_preview',
    )

    source_group_ids = fields.Many2many(
        'aula_metrics.academic_group',
        string='Grupos del curso origen',
        compute='_compute_preview',
        help='Grupos que se copiarán en el nuevo curso.'
    )

    @api.depends('source_year_id')
    def _compute_preview(self):
        for wizard in self:
            if wizard.source_year_id:
                groups = wizard.source_year_id.academic_group_ids
                wizard.source_group_ids = groups
                wizard.preview_group_count = len(groups)
            else:
                wizard.source_group_ids = False
                wizard.preview_group_count = 0

    # ── Defaults ──────────────────────────────────────────────────────────────
    def _default_new_year_name(self):
        """Sugiere el siguiente curso académico (año actual + 1)."""
        current = self.env['aula_metrics.academic_year'].get_current_year()
        if not current:
            import datetime
            today = datetime.date.today()
            yr = today.year if today.month >= 9 else today.year - 1
            return f"{yr + 1}-{yr + 2}"
        # Intentar parsear "AAAA-BBBB" y sumar 1
        try:
            parts = current.name.split('-')
            if len(parts) == 2:
                start = int(parts[0]) + 1
                end = int(parts[1]) + 1
                return f"{start}-{end}"
        except (ValueError, IndexError):
            pass
        return ''

    # ── Acción principal ──────────────────────────────────────────────────────
    def action_create_new_year(self):
        """Ejecuta el proceso de apertura del nuevo curso."""
        self.ensure_one()

        # Validar que el nombre no exista ya
        existing = self.env['aula_metrics.academic_year'].search(
            [('name', '=', self.new_year_name)], limit=1
        )
        if existing:
            raise UserError(
                _(f'Ya existe un curso académico con el nombre "{self.new_year_name}". '
                  f'Elige un nombre diferente.')
            )

        source_groups = self.source_year_id.academic_group_ids

        # 1. Crear el nuevo AcademicYear
        new_year_vals = {
            'name': self.new_year_name,
            'state': 'draft',
        }
        if self.new_year_date_start:
            new_year_vals['date_start'] = self.new_year_date_start
        if self.new_year_date_end:
            new_year_vals['date_end'] = self.new_year_date_end

        new_year = self.env['aula_metrics.academic_year'].create(new_year_vals)
        _logger.info('Nuevo curso académico creado: %s (id=%s)', new_year.name, new_year.id)

        # 2. Crear grupos vacíos en el nuevo curso (misma estructura, sin alumnos)
        created_groups = self.env['aula_metrics.academic_group']
        for group in source_groups:
            new_group_vals = {
                'name': group.name,
                'course_level': group.course_level,
                'academic_year_id': new_year.id,
                'tutor_id': group.tutor_id.id if group.tutor_id else False,
                'notes': group.notes or '',
                # student_ids vacío intencionalmente
            }
            try:
                new_group = self.env['aula_metrics.academic_group'].create(new_group_vals)
                created_groups |= new_group
                _logger.info('Grupo creado: %s en curso %s', new_group.name, new_year.name)
            except Exception as e:
                _logger.error('Error al crear grupo %s: %s', group.name, e, exc_info=True)

        # 3. Archivar grupos del curso origen (siempre)
        #    Los alumnos permanecen vinculados a sus grupos históricos.
        #    Así se preserva el histórico y los repetidores se pueden
        #    reasignar manualmente al nuevo grupo.
        source_groups.write({'active': False})
        _logger.info('Archivados %d grupos del curso %s', len(source_groups), self.source_year_id.name)

        # 4. Cerrar el curso origen (siempre)
        self.source_year_id.write({'state': 'closed'})
        _logger.info('Curso %s cerrado', self.source_year_id.name)

        # 5. Activar automáticamente el nuevo curso
        new_year.action_activate()
        _logger.info('Nuevo curso %s activado', new_year.name)

        # Notificación de éxito — abrir el nuevo curso
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo Curso Académico'),
            'res_model': 'aula_metrics.academic_year',
            'res_id': new_year.id,
            'view_mode': 'form',
            'target': 'current',
        }
