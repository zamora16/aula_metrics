# -*- coding: utf-8 -*-
"""
Portal público de encuestas para alumnos usando tokens de participación.
"""
import logging
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class AulaMetricsSurveyPortal(http.Controller):
    """Portal público de encuestas sin autenticación."""

    @http.route('/survey/preview/<int:survey_id>', type='http', auth='user', website=True)
    def survey_preview(self, survey_id, **kw):
        """Vista previa de survey usando template personalizado."""
        survey = request.env['survey.survey'].sudo().browse(survey_id)
        if not survey.exists() or not (survey.is_aulametrics or survey.is_adhoc):
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Encuesta no encontrada',
                'error_message': 'La encuesta no existe o no es de AulaMetrics.'
            })

        questions = survey.get_questions_data(user_input=None)

        return request.render('aula_metrics.portal_survey_form', {
            'survey': survey,
            'questions': questions,
            'preview': True,
            'token': 'preview',
        })

    @http.route('/evaluacion/<string:token>', type='http', auth='public', csrf=False)
    def portal_evaluacion(self, token, **kw):
        """Portal principal con lista de encuestas de la evaluación."""
        participation = request.env['aula_metrics.participation'].get_by_token(token)

        if not participation:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Enlace no válido',
                'error_message': 'El enlace de evaluación no existe o ha expirado.'
            })

        evaluation = participation.evaluation_id.sudo()
        now = fields.Datetime.now()

        if evaluation.state == 'closed' or (evaluation.date_end and evaluation.date_end < now):
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Evaluación cerrada',
                'error_message': 'El plazo para responder esta evaluación ha finalizado.'
            })

        if evaluation.state == 'draft':
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Evaluación no disponible',
                'error_message': 'Esta evaluación aún no está disponible.'
            })

        survey_status = participation.get_surveys_status()
        completed_count = len([s for s in survey_status if s['completed']])
        total_count = len(survey_status)
        progress = int((completed_count / total_count * 100) if total_count > 0 else 0)

        return request.render('aula_metrics.portal_evaluacion', {
            'participation': participation.sudo(),
            'evaluation': evaluation,
            'student': participation.student_id.sudo(),
            'surveys': survey_status,
            'progress': progress,
            'completed_count': completed_count,
            'total_count': total_count,
            'token': token,
        })

    @http.route('/evaluacion/<string:token>/encuesta/<int:survey_id>', type='http', auth='public', csrf=False)
    def render_survey(self, token, survey_id, **kw):
        """Renderiza el formulario de una encuesta específica."""
        participation = request.env['aula_metrics.participation'].get_by_token(token)

        if not participation:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Enlace no válido',
                'error_message': 'El enlace de evaluación no existe o ha expirado.'
            })

        survey = request.env['survey.survey'].sudo().browse(survey_id)
        if not survey.exists() or survey not in participation.evaluation_id.survey_ids:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Encuesta no encontrada',
                'error_message': 'La encuesta solicitada no está disponible.'
            })

        # Redirigir si ya existe una respuesta completada en la ventana de evaluación
        eval_rec = participation.evaluation_id
        done_domain = [
            ('partner_id', '=', participation.student_id.id),
            ('survey_id', '=', survey.id),
            ('state', '=', 'done'),
        ]
        if eval_rec and eval_rec.date_start:
            done_domain.append(('create_date', '>=', eval_rec.date_start))
        if eval_rec and eval_rec.date_end:
            done_domain.append(('create_date', '<=', eval_rec.date_end))

        if request.env['survey.user_input'].sudo().search_count(done_domain):
            return request.redirect(f'/evaluacion/{token}?msg=completada')

        user_input = request.env['survey.user_input'].get_or_create_for_participation(
            participation, survey
        )
        questions_data = survey.get_questions_data(user_input)

        return request.render('aula_metrics.portal_survey_form', {
            'participation': participation.sudo(),
            'evaluation': participation.evaluation_id.sudo(),
            'student': participation.student_id.sudo(),
            'survey': survey,
            'user_input': user_input,
            'questions': questions_data,
            'token': token,
        })

    @http.route('/evaluacion/<string:token>/encuesta/<int:survey_id>/submit',
                type='http', auth='public', csrf=False, methods=['POST'])
    def submit_survey(self, token, survey_id, **post):
        """Procesa las respuestas enviadas de una encuesta."""
        participation = request.env['aula_metrics.participation'].get_by_token(token)

        if not participation:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Error de acceso',
                'error_message': 'Sesión inválida. Por favor, usa tu enlace de evaluación original.'
            })

        survey = request.env['survey.survey'].sudo().browse(survey_id)
        if not survey.exists() or survey not in participation.evaluation_id.survey_ids:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Error',
                'error_message': 'Encuesta no válida.'
            })

        user_input = request.env['survey.user_input'].get_or_create_for_participation(
            participation, survey
        )

        if user_input.state == 'done':
            return request.redirect(f'/evaluacion/{token}?msg=ya_completada')

        try:
            user_input = user_input.sudo()
            user_input.save_answers_from_post(survey, post)
            user_input.write({'state': 'done'})
            user_input._mark_done()
            return request.redirect(f'/evaluacion/{token}?msg=guardado')

        except Exception:
            _logger.exception(
                'submit_survey: error guardando respuestas para token=%s survey_id=%s',
                token, survey_id,
            )
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Error al guardar',
                'error_message': 'Hubo un problema al guardar tus respuestas. Por favor, inténtalo de nuevo.'
            })
