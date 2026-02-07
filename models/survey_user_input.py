# -*- coding: utf-8 -*-
from odoo import models

class SurveyUserInput(models.Model):
    """Hook para capturar cuando un alumno completa una encuesta de AulaMetrics"""
    _inherit = 'survey.user_input'
    
    def _mark_done(self):
        """
        Override del método que marca una encuesta como completada.
        Calcula scores, verifica alertas y marca participación como completada si corresponde.
        """
        res = super(SurveyUserInput, self)._mark_done()
        
        for user_input in self:
            try:
                if not user_input.survey_id or not user_input.survey_id.is_aulametrics:
                    continue
                
                if not user_input.partner_id:
                    continue
                
                evaluations = self.env['aulametrics.evaluation'].search([
                    ('state', 'in', ['scheduled', 'active']),
                    ('survey_ids', 'in', user_input.survey_id.id)
                ])
                
                if not evaluations:
                    continue
                
                for evaluation in evaluations:
                    participation = self.env['aulametrics.participation'].search([
                        ('evaluation_id', '=', evaluation.id),
                        ('student_id', '=', user_input.partner_id.id),
                        ('state', '=', 'pending')
                    ], limit=1)
                    
                    if not participation:
                        continue
                    
                    # Calcular puntuaciones y verificar alertas
                    try:
                        participation._calculate_scores()
                        participation.check_alerts()
                    except Exception:
                        pass
                    
                    # Verificar si completó todos los cuestionarios
                    try:
                        all_surveys = evaluation.survey_ids
                        completed_surveys = self.env['survey.user_input'].search_count([
                            ('partner_id', '=', user_input.partner_id.id),
                            ('survey_id', 'in', all_surveys.ids),
                            ('state', '=', 'done'),
                            ('create_date', '>=', evaluation.date_start)
                        ])
                        
                        if completed_surveys == len(all_surveys):
                            participation.action_complete()
                    except Exception:
                        pass
            
            except Exception:
                continue
        
        return res
