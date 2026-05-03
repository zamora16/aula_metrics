# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class AcademicGroup(models.Model):
    _name = 'aula_metrics.academic_group'
    _table = 'aulametrics_academic_group'
    _description = 'Grupo Académico'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Grupo',
        required=True,
        help='Ejemplo: 1º ESO A, 2º Bachillerato B'
    )
    
    course_level = fields.Selection([
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
    ], string='Nivel Educativo', required=True)
    
    academic_year_id = fields.Many2one(
        'aula_metrics.academic_year',
        string='Curso Académico',
        required=True,
        ondelete='restrict',
        index=True,
        default=lambda self: self.env['aula_metrics.academic_year']._get_default_year(),
        help='Curso académico al que pertenece este grupo'
    )

    # Campo de conveniencia: nombre del curso para mostrar en filtros y búsquedas.
    academic_year = fields.Char(
        related='academic_year_id.name',
        string='Curso',
        store=True,
        readonly=True,
    )
    
    tutor_id = fields.Many2one(
        'res.users',
        string='Tutor/a',
        domain=[('share', '=', False)],
        help='Usuario asignado como tutor de este grupo'
    )
    
    student_ids = fields.One2many(
        'res.partner',
        'academic_group_id',
        string='Alumnado',
        help='Estudiantes que pertenecen a este grupo'
    )
    
    student_count = fields.Integer(
        string='Nº Alumnos',
        compute='_compute_student_count',
        store=True
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Desmarcar para archivar grupos de cursos pasados'
    )
    
    notes = fields.Text(string='Notas')

    @api.depends('student_ids')
    def _compute_student_count(self):
        """Calcula automáticamente el número de alumnos"""
        for group in self:
            group.student_count = len(group.student_ids)

    def action_view_students_list(self):
        """Abre la lista de alumnos de este grupo con vista completa."""
        self.ensure_one()
        view_tree = self.env.ref('aula_metrics.view_student_tree').id
        view_form = self.env.ref('aula_metrics.view_student_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alumnos — %s') % self.name,
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'views': [(view_tree, 'tree'), (view_form, 'form')],
            'domain': [('academic_group_id', '=', self.id)],
            'context': {'default_academic_group_id': self.id},
        }

    _sql_constraints = [
        ('name_academic_year_unique',
         'UNIQUE(name, academic_year_id)',
         'Ya existe un grupo con ese nombre en este curso académico.')
    ]