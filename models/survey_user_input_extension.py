# -*- coding: utf-8 -*-
from odoo import models, api

class SurveyUserInputExtension(models.Model):
    """Extensión de survey.user_input para actualizar participaciones"""
    _inherit = 'survey.user_input'
    
    def write(self, vals):
        """Override write para detectar cuando se completa una encuesta"""
        res = super().write(vals)
        
        # Si se marca como completada (state='done')
        if vals.get('state') == 'done':
            for user_input in self:
                # Buscar si hay una participación asociada
                if user_input.partner_id:
                    # Obtener todas las participaciones pendientes de este estudiante
                    participations = self.env['aulametrics.participation'].search([
                        ('student_id', '=', user_input.partner_id.id),
                        ('state', '=', 'pending')
                    ])
                    
                    for participation in participations:
                        # Verificar si todas las encuestas de la evaluación están completadas
                        evaluation = participation.evaluation_id
                        all_surveys = evaluation.survey_ids
                        
                        # Contar cuántas encuestas ha completado el estudiante
                        completed_surveys = self.search_count([
                            ('partner_id', '=', user_input.partner_id.id),
                            ('survey_id', 'in', all_surveys.ids),
                            ('state', '=', 'done')
                        ])
                        
                        # Si completó todas las encuestas, marcar participación como completada
                        if completed_surveys >= len(all_surveys):
                            participation.action_complete()
        
        return res
