# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class EvaluationPortalController(http.Controller):

    @http.route('/evaluation/<string:token>', type='http', auth='public', website=True)
    def evaluation_portal(self, token, **kw):
        """Portal público donde el estudiante ve todas las encuestas de su evaluación."""
        # Buscar la participación por token
        participation = request.env['aulametrics.participation'].sudo().search([
            ('evaluation_token', '=', token)
        ], limit=1)
        
        if not participation:
            return request.render('aula_metrics.evaluation_not_found')
        
        # Obtener las encuestas asignadas a la evaluación
        surveys = participation.evaluation_id.survey_ids
        
        # Construir datos para cada encuesta
        survey_data = []
        for survey in surveys:
            # Buscar el user_input correspondiente
            user_input = request.env['survey.user_input'].sudo().search([
                ('partner_id', '=', participation.student_id.id),
                ('survey_id', '=', survey.id)
            ], limit=1)
            
            survey_url = None
            is_completed = False
            
            if user_input:
                # Construir URL completa con ambos tokens
                survey_url = f"/survey/start/{survey.access_token}?answer_token={user_input.access_token}"
                is_completed = user_input.state == 'done'
            
            survey_data.append({
                'survey': survey,
                'url': survey_url,
                'completed': is_completed
            })
        
        return request.render('aula_metrics.evaluation_portal', {
            'participation': participation,
            'evaluation': participation.evaluation_id,
            'student': participation.student_id,
            'survey_data': survey_data
        })

