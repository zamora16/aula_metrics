# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date

class ResPartner(models.Model):
    """Extensión del modelo de contactos para alumnos"""
    _inherit = 'res.partner'
    
    academic_group_id = fields.Many2one(
        'aulametrics.academic_group',
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

