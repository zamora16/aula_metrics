# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime

class AcademicGroup(models.Model):
    _name = 'aulametrics.academic_group'
    _description = 'Grupo Académico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Nombre del Grupo',
        required=True,
        tracking=True,
        help='Ejemplo: 1º ESO A, 2º Bachillerato B'
    )
    
    course_level = fields.Selection([
        ('eso1', '1º ESO'),
        ('eso2', '2º ESO'),
        ('eso3', '3º ESO'),
        ('eso4', '4º ESO'),
        ('bach1', '1º Bachillerato'),
        ('bach2', '2º Bachillerato'),
    ], string='Nivel Educativo', required=True, tracking=True)
    
    academic_year = fields.Char(
        string='Curso Académico',
        required=True,
        default=lambda self: self._default_academic_year(),
        tracking=True,
        help='Ejemplo: 2024-2025'
    )
    
    tutor_id = fields.Many2one(
        'res.users',
        string='Tutor/a',
        tracking=True,
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
    
    def _default_academic_year(self):
        """Genera el curso académico actual según el mes (sept-agosto)"""
        today = datetime.date.today()
        if today.month >= 9:
            return f"{today.year}-{today.year + 1}"
        else:
            return f"{today.year - 1}-{today.year}"
    
    _sql_constraints = [
        ('name_academic_year_unique', 
         'UNIQUE(name, academic_year)', 
         'Ya existe un grupo con ese nombre en este curso académico.')
    ]