# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date

class ResPartner(models.Model):
    """Extensión del modelo de contactos para alumnos"""
    _inherit = 'res.partner'

    student_code = fields.Char(
        string='Código de Alumno',
        readonly=True,
        copy=False,
        index=True,
        help='Identificador único permanente del alumno. Se asigna al crear el '
             'alumno y no cambia aunque pase de grupo o de curso académico.'
    )

    academic_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo Académico',
        help='Grupo al que pertenece el estudiante',
        ondelete='set null'
    )
    
    is_student = fields.Boolean(
        string='Es Estudiante',
        compute='_compute_is_student',
        search='_search_is_student',
        store=False,
        help='Indica si el contacto es un estudiante (tiene grupo académico asignado)'
    )
    
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro'),
        ('prefer_not_say', 'Prefiero no decir')
    ], string='Género')
    
    birthdate = fields.Date(string='Fecha de Nacimiento')
    
    age = fields.Integer(string='Edad', compute='_compute_age', store=False)
    
    @api.depends('birthdate')
    def _compute_age(self):
        today = date.today()
        for partner in self:
            if partner.birthdate:
                born = partner.birthdate
                partner.age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            else:
                partner.age = 0

    @api.depends('academic_group_id')
    def _compute_is_student(self):
        """Un contacto es estudiante si tiene grupo académico asignado"""
        for partner in self:
            partner.is_student = bool(partner.academic_group_id)
    
    def _search_is_student(self, operator, value):
        """Permite buscar contactos que sean estudiantes"""
        if (operator == '=' and value) or (operator == '!=' and not value):
            # Buscar contactos CON grupo académico
            return [('academic_group_id', '!=', False)]
        else:
            # Buscar contactos SIN grupo académico
            return [('academic_group_id', '=', False)]

    def _assign_student_code(self):
        """Asigna un código único permanente a los alumnos que aún no tienen."""
        for partner in self:
            if not partner.student_code and partner.academic_group_id:
                partner.student_code = self.env['ir.sequence'].next_by_code(
                    'aula_metrics.student_code'
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._assign_student_code()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'academic_group_id' in vals:
            self._assign_student_code()
        return result

