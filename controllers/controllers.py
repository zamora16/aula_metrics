# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class EvaluationPortalController(http.Controller):
    """Controlador para el portal público de evaluaciones de estudiantes."""

    @http.route(['/evaluation/<string:token>', '/evaluation/<string:token>/'], type='http', auth='public', csrf=False)
    def evaluation_portal(self, token):
        """
        Portal público donde el estudiante ve las encuestas de su evaluación.
        Accesible mediante token único sin necesidad de login.
        """
        # Buscar participación por token (sudo porque auth=public no tiene permisos)
        Participation = request.env['aulametrics.participation'].sudo()
        participation = Participation.search([('evaluation_token', '=', token)], limit=1)
        
        if not participation:
            return request.render('aula_metrics.evaluation_not_found')
        
        # Preparar datos de cada encuesta
        survey_data = []
        for survey in participation.evaluation_id.survey_ids:
            # Buscar respuesta existente de este alumno en esta evaluación
            user_input = request.env['survey.user_input'].sudo().search([
                ('partner_id', '=', participation.student_id.id),
                ('survey_id', '=', survey.id),
                ('create_date', '>=', participation.evaluation_id.date_start)
            ], limit=1)
            
            # Crear respuesta si no existe
            if not user_input:
                user_input = request.env['survey.user_input'].sudo().create({
                    'survey_id': survey.id,
                    'partner_id': participation.student_id.id,
                })
            
            survey_data.append({
                'survey': survey,
                'url': f"/survey/start/{survey.access_token}?answer_token={user_input.access_token}",
                'completed': user_input.state == 'done'
            })
        
        response = request.render('aula_metrics.evaluation_portal', {
            'participation': participation,
            'evaluation': participation.evaluation_id,
            'student': participation.student_id,
            'survey_data': survey_data
        })
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        return response

