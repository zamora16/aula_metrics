# -*- coding: utf-8 -*-
from odoo import models, fields

CENTER_TYPES = [
    ('ies', 'IES — Educación Secundaria'),
    ('ceip', 'CEIP — Infantil y Primaria'),
    ('cifp', 'CIFP — Formación Profesional Integrada'),
    ('concertado', 'Concertado'),
    ('privado', 'Privado'),
    ('otro', 'Otro'),
]


class ResCompanyAulaMetrics(models.Model):
    _inherit = 'res.company'

    am_center_code = fields.Char(
        string='Código de centro',
        help='Código oficial asignado por la administración educativa (ej. 46012345).',
    )
    am_center_type = fields.Selection(
        CENTER_TYPES,
        string='Tipo de centro',
    )
