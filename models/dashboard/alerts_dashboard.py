# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AlertsDashboard(models.Model):
    _name = 'aula_metrics.alerts_dashboard'
    _table = 'alerts_dashboard'
    _description = 'Dashboard de Alertas'

    name = fields.Char(string='Dashboard', default='Sistema de Alertas', readonly=True)
    
    active_alerts = fields.Many2many('aula_metrics.alert', string='Alertas Activas', compute='_compute_active_alerts')
    all_alerts = fields.Many2many('aula_metrics.alert', string='Todas las Alertas', compute='_compute_all_alerts')
    thresholds = fields.Many2many('aula_metrics.threshold', string='Umbrales', compute='_compute_thresholds')

    @api.depends()
    def _compute_active_alerts(self):
        for record in self:
            # Incluye alertas activas (sin caso) y en gestión (con caso abierto)
            record.active_alerts = self.env['aula_metrics.alert'].search([
                ('status', 'in', ['active', 'en_gestion'])
            ])

    @api.depends()
    def _compute_all_alerts(self):
        for record in self:
            record.all_alerts = self.env['aula_metrics.alert'].search([])

    @api.depends()
    def _compute_thresholds(self):
        for record in self:
            record.thresholds = self.env['aula_metrics.threshold'].search([])