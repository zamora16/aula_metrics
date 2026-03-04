# -*- coding: utf-8 -*-
from odoo import models, fields


class CaseStage(models.Model):
    _name = 'aula_metrics.case.stage'
    _description = 'Fase de Caso de Orientación'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    fold = fields.Boolean(
        string='Plegada en Kanban',
        default=False,
        help='Si está marcada, esta fase se muestra plegada en la vista Kanban'
    )
    is_final = fields.Boolean(
        string='Fase Final (Cierre)',
        default=False,
        help='Indica que los casos en esta fase se consideran cerrados'
    )
    color = fields.Integer(string='Color', default=0)
    case_count = fields.Integer(
        string='Número de Casos',
        compute='_compute_case_count'
    )

    def _compute_case_count(self):
        case_model = self.env['aula_metrics.case']
        for stage in self:
            stage.case_count = case_model.search_count([('stage_id', '=', stage.id)])
