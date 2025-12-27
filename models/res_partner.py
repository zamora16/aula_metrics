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

