# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResolveAlertWizard(models.TransientModel):
    _name = 'aulametrics.resolve_alert_wizard'
    _description = 'Wizard para Resolver Alerta'
    
    alert_id = fields.Many2one('aulametrics.alert', string='Alerta', required=True, ondelete='cascade')
    resolution_action = fields.Text(
        string='Acción Tomada',
        required=True,
        help='Describe brevemente la intervención o acción realizada para resolver esta alerta'
    )
    resolution_date = fields.Datetime(
        string='Fecha de Resolución',
        default=fields.Datetime.now,
        readonly=True
    )
    
    @api.constrains('resolution_action')
    def _check_resolution_action(self):
        """Validar que se haya escrito algo significativo"""
        for wizard in self:
            if not wizard.resolution_action or len(wizard.resolution_action.strip()) < 10:
                raise ValidationError(
                    'Debes proporcionar una descripción de al menos 10 caracteres '
                    'sobre la acción tomada para resolver la alerta.'
                )
    
    def action_confirm_resolve(self):
        """Confirmar la resolución de la alerta"""
        self.ensure_one()
        
        # Actualizar la alerta
        self.alert_id.write({
            'status': 'resolved',
            'resolution_action': self.resolution_action,
            'resolution_date': self.resolution_date,
        })
        
        return {'type': 'ir.actions.act_window_close'}
