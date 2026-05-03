# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NewAcademicYearWizard(models.TransientModel):
    """
    Wizard de paso de curso académico — 3 pasos:

    Paso 1: Nombre y fechas del nuevo curso (+ preview de grupos base)
    Paso 2: Tabla editable de grupos del nuevo año: tutores, añadir/eliminar filas
    Paso 3: Mapeo manual grupo origen → grupo destino del nuevo año

    Al confirmar:
      - Se crea el nuevo AcademicYear y sus grupos
      - Los alumnos con destino asignado se mueven al grupo nuevo
      - Los alumnos sin destino quedan en su grupo (ahora archivado);
        el orientador los reasigna manualmente después
      - Los grupos del año origen se archivan y el año se cierra
    """
    _name = 'aula_metrics.new_academic_year_wizard'
    _description = 'Asistente de Nuevo Curso Académico'

    step = fields.Selection([
        ('1', 'Nuevo año'),
        ('2', 'Grupos y tutores'),
        ('3', 'Promoción de alumnos'),
    ], string='Paso actual', default='1', required=True)

    # ── Paso 1 ────────────────────────────────────────────────────────────────
    source_year_id = fields.Many2one(
        'aula_metrics.academic_year',
        string='Curso a cerrar',
        required=True,
        default=lambda self: self.env['aula_metrics.academic_year'].get_current_year(),
    )
    new_year_name = fields.Char(
        string='Nombre del nuevo curso',
        required=True,
        default=lambda self: self._default_new_year_name(),
        help='Ejemplo: 2026-2027',
    )
    new_year_date_start = fields.Date(string='Fecha de inicio')
    new_year_date_end = fields.Date(string='Fecha de fin')

    preview_group_count = fields.Integer(
        string='Grupos base a crear',
        compute='_compute_preview',
    )
    source_group_ids = fields.Many2many(
        'aula_metrics.academic_group',
        string='Grupos del curso origen',
        compute='_compute_preview',
    )

    # ── Paso 2 ────────────────────────────────────────────────────────────────
    group_line_ids = fields.One2many(
        'aula_metrics.year_wizard_group_line',
        'wizard_id',
        string='Grupos del nuevo año',
    )

    # ── Paso 3 ────────────────────────────────────────────────────────────────
    promotion_line_ids = fields.One2many(
        'aula_metrics.year_wizard_promo_line',
        'wizard_id',
        string='Mapeo de promoción',
    )

    # ── Computed helpers ──────────────────────────────────────────────────────

    @api.depends('source_year_id')
    def _compute_preview(self):
        for wiz in self:
            if wiz.source_year_id:
                groups = wiz.source_year_id.academic_group_ids
                wiz.source_group_ids = groups
                wiz.preview_group_count = len(groups)
            else:
                wiz.source_group_ids = False
                wiz.preview_group_count = 0

    def _default_new_year_name(self):
        current = self.env['aula_metrics.academic_year'].get_current_year()
        if not current:
            import datetime
            today = datetime.date.today()
            yr = today.year if today.month >= 9 else today.year - 1
            return '%d-%d' % (yr + 1, yr + 2)
        try:
            parts = current.name.split('-')
            if len(parts) == 2:
                start = int(parts[0]) + 1
                end = int(parts[1]) + 1
                return '%d-%d' % (start, end)
        except (ValueError, IndexError):
            pass
        return ''

    # ── Navegación ────────────────────────────────────────────────────────────

    def action_step1_to_2(self):
        self.ensure_one()
        self._validate_step1()

        self.group_line_ids.unlink()
        self.env['aula_metrics.year_wizard_group_line'].create([
            {
                'wizard_id': self.id,
                'name': g.name,
                'course_level': g.course_level,
                'tutor_id': g.tutor_id.id if g.tutor_id else False,
                'source_group_id': g.id,
                'is_new': False,
            }
            for g in self.source_year_id.academic_group_ids.sorted('name')
        ])
        self.step = '2'
        return self._reload_action()

    def action_step2_to_1(self):
        self.ensure_one()
        self.step = '1'
        return self._reload_action()

    def action_step2_to_3(self):
        self.ensure_one()
        if not self.group_line_ids:
            raise UserError(_('Debes definir al menos un grupo para el nuevo año.'))

        self.promotion_line_ids.unlink()
        self.env['aula_metrics.year_wizard_promo_line'].create([
            {
                'wizard_id': self.id,
                'source_group_id': g.id,
                'student_count': g.student_count,
                'dest_group_line_id': False,
            }
            for g in self.source_year_id.academic_group_ids.sorted('name')
        ])
        self.step = '3'
        return self._reload_action()

    def action_step3_to_2(self):
        self.ensure_one()
        self.step = '2'
        return self._reload_action()

    # ── Confirmación ──────────────────────────────────────────────────────────

    def action_confirm(self):
        self.ensure_one()
        self._validate_step1()
        if not self.group_line_ids:
            raise UserError(_('No hay grupos definidos para el nuevo año.'))

        # 1. Crear el nuevo AcademicYear
        new_year_vals = {'name': self.new_year_name, 'state': 'draft'}
        if self.new_year_date_start:
            new_year_vals['date_start'] = self.new_year_date_start
        if self.new_year_date_end:
            new_year_vals['date_end'] = self.new_year_date_end
        new_year = self.env['aula_metrics.academic_year'].create(new_year_vals)
        _logger.info('Nuevo curso creado: %s (id=%s)', new_year.name, new_year.id)

        # 2. Crear grupos del nuevo año → mapa {line.id: new_group}
        line_to_group = {}
        for line in self.group_line_ids:
            try:
                new_group = self.env['aula_metrics.academic_group'].create({
                    'name': line.name,
                    'course_level': line.course_level,
                    'academic_year_id': new_year.id,
                    'tutor_id': line.tutor_id.id if line.tutor_id else False,
                })
                line_to_group[line.id] = new_group
                _logger.info('Grupo creado: %s en %s', new_group.name, new_year.name)
            except Exception as e:
                _logger.error('Error creando grupo "%s": %s', line.name, e, exc_info=True)
                raise UserError(_('Error al crear el grupo "%s": %s') % (line.name, e))

        # 3. Mover alumnos según el mapeo; los sin destino se quedan donde están
        moved = 0
        stranded = 0
        graduated = 0
        stranded_group_ids = []
        for promo in self.promotion_line_ids:
            students = promo.source_group_id.student_ids
            if not students:
                continue
            if promo.dest_group_line_id:
                dest_group = line_to_group.get(promo.dest_group_line_id.id)
                if dest_group:
                    students.write({'academic_group_id': dest_group.id})
                    moved += len(students)
                    _logger.info('%d alumnos: %s → %s', len(students), promo.source_group_id.name, dest_group.name)
            elif promo.is_terminal_level:
                # Nivel terminal (2º Bach, CFGM2, etc.): archivar alumnos
                students.write({'active': False})
                graduated += len(students)
                _logger.info(
                    '%d alumnos graduados archivados desde "%s"',
                    len(students), promo.source_group_id.name,
                )
            else:
                stranded += len(students)
                stranded_group_ids.append(promo.source_group_id.id)
                _logger.info(
                    '%d alumnos sin destino en "%s" — quedan en grupo archivado para gestión manual',
                    len(students), promo.source_group_id.name,
                )

        # 4. Archivar grupos del año origen y cerrar el año
        source_groups = self.source_year_id.academic_group_ids
        source_groups.write({'active': False})
        self.source_year_id.write({'state': 'closed'})
        _logger.info('%d grupos archivados, curso %s cerrado', len(source_groups), self.source_year_id.name)

        # 5. Activar el nuevo curso
        new_year.action_activate()
        _logger.info('Nuevo curso %s activado', new_year.name)

        # Si hay alumnos sin destino, abrir su listado para gestión inmediata
        if stranded:
            tree_view = self.env.ref('aula_metrics.view_student_no_group_tree', raise_if_not_found=False)
            form_view = self.env.ref('aula_metrics.view_student_form', raise_if_not_found=False)
            views = []
            if tree_view:
                views.append((tree_view.id, 'list'))
            if form_view:
                views.append((form_view.id, 'form'))
            parts = [_('%d alumnos promocionados') % moved]
            if graduated:
                parts.append(_('%d graduados archivados') % graduated)
            parts.append(_('%d pendientes de reasignar grupo') % stranded)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Alumnos sin grupo activo'),
                'res_model': 'res.partner',
                'view_mode': 'list,form',
                'views': views if views else [(False, 'list'), (False, 'form')],
                'domain': [('academic_group_id', 'in', stranded_group_ids)],
                'context': {'active_test': False},
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo Curso Académico'),
            'res_model': 'aula_metrics.academic_year',
            'res_id': new_year.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Validación ────────────────────────────────────────────────────────────

    def _validate_step1(self):
        if not self.new_year_name or not self.new_year_name.strip():
            raise UserError(_('Introduce el nombre del nuevo curso.'))
        existing = self.env['aula_metrics.academic_year'].search(
            [('name', '=', self.new_year_name.strip())], limit=1
        )
        if existing:
            raise UserError(_(
                'Ya existe un curso académico con el nombre "%s". '
                'Elige un nombre diferente.'
            ) % self.new_year_name)

    def _reload_action(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
