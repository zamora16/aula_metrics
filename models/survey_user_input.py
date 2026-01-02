# -*- coding: utf-8 -*-
from odoo import models

class SurveyUserInput(models.Model):
    """Hook para capturar cuando un alumno completa una encuesta de AulaMetrics"""
    _inherit = 'survey.user_input'
    
    def _mark_done(self):
        """
        Override del método que marca una encuesta como completada.
        Si la encuesta es de AulaMetrics y el alumno ha completado todos los 
        cuestionarios de la evaluación, marca la participación como completada.
        """
        res = super(SurveyUserInput, self)._mark_done()
        
        for user_input in self:
            # Solo procesar si es un cuestionario de AulaMetrics
            if not user_input.survey_id.is_aulametrics:
                continue
            
            # Buscar la participación correspondiente
            # El partner_id del user_input corresponde al alumno
            if not user_input.partner_id:
                continue
            
            # Buscar evaluaciones activas que usen esta encuesta
            evaluations = self.env['aulametrics.evaluation'].search([
                ('state', 'in', ['scheduled', 'active']),
                ('survey_ids', 'in', user_input.survey_id.id)
            ])
            
            # Buscar la participación pendiente del alumno
            for evaluation in evaluations:
                participation = self.env['aulametrics.participation'].search([
                    ('evaluation_id', '=', evaluation.id),
                    ('student_id', '=', user_input.partner_id.id),
                    ('state', '=', 'pending')
                ], limit=1)
                
                if not participation:
                    continue
                
                # Verificar si ha completado TODOS los cuestionarios de ESTA evaluación
                # Solo contar user_inputs creados DESPUÉS del inicio de la evaluación
                all_surveys = evaluation.survey_ids
                completed_surveys = self.env['survey.user_input'].search_count([
                    ('partner_id', '=', user_input.partner_id.id),
                    ('survey_id', 'in', all_surveys.ids),
                    ('state', '=', 'done'),
                    ('create_date', '>=', evaluation.date_start)
                ])
                
                # Si completó todos los cuestionarios, marcar participación como completada
                if completed_surveys == len(all_surveys):
                    participation.action_complete()
        
        return res
