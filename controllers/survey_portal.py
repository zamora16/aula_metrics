# -*- coding: utf-8 -*-
"""
Portal público de encuestas para alumnos usando tokens de participación.
"""
import logging
from odoo import http, fields
from odoo.http import request
from ..utils.lang_service import get_request_lang, set_lang_cookie, SUPPORTED_LANGS, DEFAULT_LANG
from ..utils.constants import centro_surveys_enabled

_logger = logging.getLogger(__name__)


class AulaMetricsSurveyPortal(http.Controller):
    """Portal público de encuestas sin autenticación."""

    @http.route('/am/lang', type='http', auth='public', csrf=False, methods=['POST'])
    def set_lang(self, lang='es_ES', redirect='/', **kw):
        """Fija el idioma del portal mediante cookie y redirige a la página actual."""
        if lang not in SUPPORTED_LANGS:
            lang = DEFAULT_LANG
        # Evitar open redirects: solo rutas relativas internas
        if not redirect.startswith('/') or '://' in redirect:
            redirect = '/'
        response = request.redirect(redirect)
        return set_lang_cookie(response, lang)

    @http.route('/survey/preview/<int:survey_id>', type='http', auth='user')
    def survey_preview(self, survey_id, **kw):
        """Vista previa de survey usando template personalizado."""
        lang = get_request_lang(request)

        user = request.env.user
        has_role = (
            user.has_group('aula_metrics.group_aulametrics_admin')
            or user.has_group('aula_metrics.group_aulametrics_counselor')
            or user.has_group('aula_metrics.group_aulametrics_management')
            or user.has_group('aula_metrics.group_aulametrics_tutor')
        )
        if not has_role:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Acceso denegado',
                'error_message': 'No tienes permisos para previsualizar encuestas de AulaMetrics.',
            })

        survey = request.env['survey.survey'].sudo().browse(survey_id)
        if not survey.exists() or not (survey.is_aulametrics or survey.is_adhoc):
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Encuesta no encontrada',
                'error_message': 'La encuesta no existe o no es de AulaMetrics.'
            })

        # Denegar acceso a encuestas adhoc si el feature flag está desactivado
        if survey.is_adhoc and not centro_surveys_enabled(request.env):
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Encuesta no disponible',
                'error_message': 'Los cuestionarios del centro no están activados en esta instancia.',
            })

        questions = survey.with_context(lang=lang).get_questions_data(user_input=None)

        response = request.render('aula_metrics.portal_survey_form', {
            'survey': survey.with_context(lang=lang),
            'questions': questions,
            'preview': True,
            'token': 'preview',
            'active_lang': lang,
            'supported_langs': SUPPORTED_LANGS,
        })
        return set_lang_cookie(response, lang)

    @http.route('/evaluacion/<string:token>', type='http', auth='public', csrf=False)
    def portal_evaluacion(self, token, **kw):
        """Portal principal con lista de encuestas de la evaluación."""
        lang = get_request_lang(request)

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

        survey_status = participation.with_context(lang=lang).get_surveys_status()
        completed_count = len([s for s in survey_status if s['completed']])
        total_count = len(survey_status)
        progress = int((completed_count / total_count * 100) if total_count > 0 else 0)

        response = request.render('aula_metrics.portal_evaluacion', {
            'participation': participation.sudo().with_context(lang=lang),
            'evaluation': evaluation.with_context(lang=lang),
            'student': participation.student_id.sudo().with_context(lang=lang),
            'surveys': survey_status,
            'progress': progress,
            'completed_count': completed_count,
            'total_count': total_count,
            'token': token,
            'active_lang': lang,
            'supported_langs': SUPPORTED_LANGS,
        })
        return set_lang_cookie(response, lang)

    @http.route('/evaluacion/<string:token>/encuesta/<int:survey_id>', type='http', auth='public', csrf=False)
    def render_survey(self, token, survey_id, **kw):
        """Renderiza el formulario de una encuesta específica."""
        lang = get_request_lang(request)

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

        # Redirigir si el alumno ya completó esta encuesta en esta evaluación
        already_done = request.env['survey.user_input'].sudo().search_count([
            ('partner_id', '=', participation.student_id.id),
            ('survey_id', '=', survey.id),
            ('state', '=', 'done'),
            ('aulametrics_evaluation_id', '=', participation.evaluation_id.id),
        ])
        if already_done:
            return request.redirect(f'/evaluacion/{token}?msg=completada')

        user_input = request.env['survey.user_input'].get_or_create_for_participation(
            participation, survey
        )

        questions_data = survey.with_context(lang=lang).get_questions_data(user_input)

        response = request.render('aula_metrics.portal_survey_form', {
            'participation': participation.sudo().with_context(lang=lang),
            'evaluation': participation.evaluation_id.sudo().with_context(lang=lang),
            'student': participation.student_id.sudo().with_context(lang=lang),
            'survey': survey.with_context(lang=lang),
            'user_input': user_input,
            'questions': questions_data,
            'token': token,
            'active_lang': lang,
            'supported_langs': SUPPORTED_LANGS,
        })
        return set_lang_cookie(response, lang)

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
