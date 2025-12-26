# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    """Extensión del modelo de contactos para alumnos"""
    _inherit = 'res.partner'
    
    academic_group_id = fields.Many2one(
        'aulametrics.academic_group',
        string='Grupo Académico',
        help='Grupo al que pertenece el estudiante',
        ondelete='set null'
    )
