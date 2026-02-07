# -*- coding: utf-8 -*-
from odoo import models, fields, api

class Threshold(models.Model):
    _name = 'aulametrics.threshold'
    _description = 'Umbral para Alertas'

    name = fields.Char(string='Nombre', required=True, help='Ej: Alto Estrés ASQ-14')
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
        """Genera opciones dinámicamente desde TODOS los cuestionarios AulaMetrics (oficiales y del centro)"""
        options = []
        # Obtener todos los cuestionarios de AulaMetrics (oficiales y ad hoc)
        surveys = self.env['survey.survey'].search([
            ('is_aulametrics', '=', True)
        ], order='is_adhoc, title')
        
        for survey in surveys:
            # Para oficiales: usar survey_code
            if survey.survey_code:
                metric_name = survey.survey_code
            # Para ad hoc: usar survey_{id}
            else:
                metric_name = f"survey_{survey.id}"
            
            # Añadir indicador de tipo para claridad
            label = survey.title
            if survey.is_adhoc:
                label = f"{survey.title} - Cuestionario del centro"
            
            options.append((metric_name, label))
        
        return options
    severity = fields.Selection([
        ('low', 'Leve'),
        ('moderate', 'Moderada'),
        ('high', 'Severa'),
    ], string='Severidad', required=True, default='moderate', help='Nivel de severidad de la alerta')
    group_threshold_percentage = fields.Float(string='Umbral Grupal (%)', default=25.0, help='Porcentaje de alumnos con alerta para generar alerta grupal')