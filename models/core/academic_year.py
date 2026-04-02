# -*- coding: utf-8 -*-
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AcademicYear(models.Model):
    _name = 'aula_metrics.academic_year'
    _description = 'Curso Académico'
    _order = 'name desc'

    name = fields.Char(
        string='Curso Académico',
        required=True,
        help='Ejemplo: 2025-2026'
    )
    date_start = fields.Date(string='Fecha de Inicio')
    date_end = fields.Date(string='Fecha de Fin')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('closed', 'Cerrado'),
    ], string='Estado', default='draft', required=True)

    is_current = fields.Boolean(
        string='Curso Actual',
        compute='_compute_is_current',
        store=True,
        help='Verdadero cuando el estado es "Activo". Solo un curso puede estar activo a la vez.'
    )

    academic_group_ids = fields.One2many(
        'aula_metrics.academic_group',
        'academic_year_id',
        string='Grupos Académicos'
    )

    group_count = fields.Integer(
        string='Nº Grupos',
        compute='_compute_group_count',
        store=True
    )

    total_student_count = fields.Integer(
        string='Total Alumnos',
        compute='_compute_total_student_count',
        store=True,
        help='Total de alumnos activos en todos los grupos de este curso.'
    )

    @api.depends('state')
    def _compute_is_current(self):
        for year in self:
            year.is_current = year.state == 'active'

    @api.depends('academic_group_ids')
    def _compute_group_count(self):
        for year in self:
            year.group_count = len(year.academic_group_ids)

    @api.depends('academic_group_ids.student_count')
    def _compute_total_student_count(self):
        for year in self:
            year.total_student_count = sum(year.academic_group_ids.mapped('student_count'))

    def action_activate(self):
        """Activa este curso académico. Cierra cualquier otro que esté activo."""
        self.env['aula_metrics.academic_year'].search([
            ('state', '=', 'active'),
            ('id', 'not in', self.ids),
        ]).write({'state': 'closed'})
        self.write({'state': 'active'})

    def action_close(self):
        """Cierra este curso académico."""
        self.write({'state': 'closed'})

    def action_reset_draft(self):
        """Vuelve el curso a borrador."""
        self.write({'state': 'draft'})

    def action_view_groups(self):
        """Abre la lista de grupos filtrada por este curso académico."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grupos — %s') % self.name,
            'res_model': 'aula_metrics.academic_group',
            'view_mode': 'tree,form',
            'domain': [('academic_year_id', '=', self.id)],
            'context': {
                'default_academic_year_id': self.id,
                'search_default_academic_year_id': self.id,
            },
        }

    def action_view_students(self):
        """Abre la lista de alumnos de todos los grupos de este curso."""
        self.ensure_one()
        group_ids = self.academic_group_ids.ids
        view_tree = self.env.ref('aula_metrics.view_student_tree').id
        view_form = self.env.ref('aula_metrics.view_student_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alumnos — %s') % self.name,
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'views': [(view_tree, 'tree'), (view_form, 'form')],
            'domain': [('academic_group_id', 'in', group_ids)],
        }

    @api.model
    def get_current_year(self):
        """Devuelve el curso activo o el más reciente si no hay ninguno activo."""
        current = self.search([('state', '=', 'active')], limit=1)
        if not current:
            current = self.search([], order='name desc', limit=1)
        return current

    @api.model
    def _get_default_year(self):
        """Usado como default en otros modelos."""
        return self.get_current_year()

    @api.model
    def action_open_new_year_wizard(self):
        """Abre el wizard de 'Pasar de Curso' desde la lista de cursos."""
        return self.env['ir.actions.act_window']._for_xml_id(
            'aula_metrics.action_new_academic_year_wizard'
        )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Ya existe un curso académico con ese nombre.'),
    ]
