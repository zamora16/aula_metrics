# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AlertsDashboard(models.Model):
    _name = 'alerts.dashboard'
    _description = 'Dashboard de Alertas'

    name = fields.Char(string='Dashboard', default='Sistema de Alertas', readonly=True)
    
    active_alerts = fields.Many2many('aulametrics.alert', string='Alertas Activas', compute='_compute_active_alerts')
    all_alerts = fields.Many2many('aulametrics.alert', string='Todas las Alertas', compute='_compute_all_alerts')
    thresholds = fields.Many2many('aulametrics.threshold', string='Umbrales', compute='_compute_thresholds')

    @api.depends()
    def _compute_active_alerts(self):
        for record in self:
            record.active_alerts = self.env['aulametrics.alert'].search([('status', '=', 'active')])

    @api.depends()
    def _compute_all_alerts(self):
        for record in self:
            record.all_alerts = self.env['aulametrics.alert'].search([])

    @api.depends()
    def _compute_thresholds(self):
        for record in self:
            record.thresholds = self.env['aulametrics.threshold'].search([])