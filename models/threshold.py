# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Importar configuración centralizada
from .survey_config import SURVEY_METRICS

class Threshold(models.Model):
    _name = 'aulametrics.threshold'
    _description = 'Umbral para Alertas'

    name = fields.Char(string='Nombre', required=True, help='Ej: Alto Estrés ASQ-14')
    survey_id = fields.Many2one('survey.survey', string='Cuestionario', required=True, domain=[('is_aulametrics', '=', True)])
    score_field = fields.Selection(
        selection='_get_score_field_options',
        string='Campo de Puntuación',
        required=True
    )
    threshold_value = fields.Float(string='Valor Umbral', required=True, help='Ej: 70 para >70')
    operator = fields.Selection([('>', 'Mayor que'), ('<', 'Menor que')], string='Operador', required=True, default='>')
    active = fields.Boolean(default=True)
    alert_message = fields.Text(string='Mensaje de Alerta', help='Mensaje personalizado para la alerta')

    @api.model
    def _get_score_field_options(self):
        """Genera opciones dinámicamente desde SURVEY_METRICS"""
        options = []
        for survey_config in SURVEY_METRICS.values():
            for field_name, label in survey_config['labels'].items():
                options.append((field_name, label))
        return options
    severity = fields.Selection([
        ('low', 'Leve'),
        ('moderate', 'Moderada'),
        ('high', 'Severa'),
    ], string='Severidad', required=True, default='moderate', help='Nivel de severidad de la alerta')
    group_threshold_percentage = fields.Float(string='Umbral Grupal (%)', default=25.0, help='Porcentaje de alumnos con alerta para generar alerta grupal')