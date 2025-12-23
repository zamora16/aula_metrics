# -*- coding: utf-8 -*-
from odoo import models, api

class SurveyUserInput(models.Model):
    """Hook para capturar cuando un alumno completa una encuesta de AulaMetrics"""
    _inherit = 'survey.user_input'
    
    def _mark_done(self):
        """
        Override del método que marca una encuesta como completada.
        Si la encuesta es de AulaMetrics y hay una participación pendiente,
        la marca como completada automáticamente.
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
            
            # Obtener el usuario (alumno) desde el partner
            student = self.env['res.users'].search([
                ('partner_id', '=', user_input.partner_id.id)
            ], limit=1)
            
            if not student:
                continue
            
            # Buscar evaluaciones activas que usen esta encuesta
            evaluations = self.env['aulametrics.evaluation'].search([
                ('state', 'in', ['scheduled', 'active']),
                ('survey_ids', 'in', user_input.survey_id.id)
            ])
            
            # Buscar y completar la participación pendiente del alumno
            for evaluation in evaluations:
                participation = self.env['aulametrics.participation'].search([
                    ('evaluation_id', '=', evaluation.id),
                    ('student_id', '=', student.id),
                    ('state', '=', 'pending')
                ], limit=1)
                
                if participation:
                    participation.action_complete()
        
        return res
