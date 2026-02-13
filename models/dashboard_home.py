# -*- coding: utf-8 -*-
from odoo import models, fields, api


class DashboardHome(models.Model):
    """
    Modelo dummy para el dashboard de inicio.
    Contiene tarjetas de navegación estáticas.
    Las tarjetas se definen en data/dashboard_home_data.xml
    """
    _name = 'aulametrics.dashboard.home'
    _description = 'Dashboard de Inicio AulaMetrics'
    _order = 'sequence, id'
    
    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    description = fields.Text(string='Descripción')
    icon = fields.Char(string='Icono FontAwesome', default='fa-cubes')
    color = fields.Char(string='Color', default='#667eea')
    action_id = fields.Many2one('ir.actions.actions', string='Acción')
    
    def action_open_menu(self):
        """Acción que se ejecuta al hacer clic en una tarjeta"""
        self.ensure_one()
        
        if not self.action_id:
            return {'type': 'ir.actions.act_window_close'}
            
        # Obtener el tipo de acción correcto (ir.actions.act_window, ir.actions.act_url, etc.)
        action_type = self.action_id.type
        
        try:
            # Browsing del modelo específico para asegurar que leemos todos los campos (res_model, view_mode, etc.)
            real_action = self.env[action_type].browse(self.action_id.id)
            action_dict = real_action.read()[0]
            
            # Limpieza básica
            action_dict.pop('id', None)
            action_dict.pop('xml_id', None)
            
            return action_dict
            
        except Exception as e:
            return {'type': 'ir.actions.act_window_close'}

