# -*- coding: utf-8 -*-
"""
Portal público de encuestas para alumnos usando tokens de participación.
"""
from odoo import http, fields
from odoo.http import request


class AulaMetricsSurveyPortal(http.Controller):
    """Portal público de encuestas sin autenticación."""

    @http.route('/survey/preview/<int:survey_id>', type='http', auth='user', website=True)
    def survey_preview(self, survey_id, **kw):
        """Vista previa de survey usando template personalizado."""
        survey = request.env['survey.survey'].sudo().browse(survey_id)
        if not survey.exists() or not survey.is_aulametrics:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Encuesta no encontrada',
                'error_message': 'La encuesta no existe o no es de AulaMetrics.'
            })
        
        # Simular participación dummy para preview
        questions = self._prepare_questions_data(survey, user_input=None)
        
        return request.render('aula_metrics.portal_survey_form', {
            'survey': survey,
            'questions': questions,
            'preview': True,  # Flag para modo preview (sin submit)
            'token': 'preview',  # Token dummy
        })

    @http.route('/evaluacion/<string:token>', type='http', auth='public', csrf=False)
    def portal_evaluacion(self, token, **kw):
        """Portal principal con lista de encuestas de la evaluación."""
        participation = self._get_participation_by_token(token)
        
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
        
        survey_status = self._get_surveys_status(participation)
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
        participation = self._get_participation_by_token(token)
        
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
        
        user_input = self._get_or_create_user_input(participation, survey)
        
        if user_input.state == 'done':
            return request.redirect(f'/evaluacion/{token}?msg=completada')
        
        questions_data = self._prepare_questions_data(survey, user_input)
        
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
        participation = self._get_participation_by_token(token)
        
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
        
        user_input = self._get_or_create_user_input(participation, survey)
        
        if user_input.state == 'done':
            return request.redirect(f'/evaluacion/{token}?msg=ya_completada')
        
        try:
            self._process_answers(survey, user_input, post)
            user_input.sudo().write({'state': 'done'})
            user_input.sudo()._mark_done()
            
            return request.redirect(f'/evaluacion/{token}?msg=guardado')
            
        except Exception:
            return request.render('aula_metrics.portal_error', {
                'error_title': 'Error al guardar',
                'error_message': 'Hubo un problema al guardar tus respuestas. Por favor, inténtalo de nuevo.'
            })

    def _get_participation_by_token(self, token):
        """Busca participación por token."""
        return request.env['aulametrics.participation'].sudo().search([
            ('evaluation_token', '=', token),
            ('state', '!=', 'expired')
        ], limit=1)
    
    def _get_surveys_status(self, participation):
        """Retorna estado de todas las encuestas de una evaluación."""
        surveys = participation.evaluation_id.sudo().survey_ids
        result = []
        
        for survey in surveys:
            user_input = request.env['survey.user_input'].sudo().search([
                ('partner_id', '=', participation.student_id.id),
                ('survey_id', '=', survey.id),
                ('create_date', '>=', participation.evaluation_id.date_start)
            ], limit=1)
            
            is_completed = user_input.state == 'done' if user_input else False
            
            result.append({
                'survey': survey.sudo(),
                'completed': is_completed,
                'user_input': user_input,
                'url': f'/evaluacion/{participation.evaluation_token}/encuesta/{survey.id}'
            })
        
        return result
    
    def _get_or_create_user_input(self, participation, survey):
        """Obtiene o crea user_input para la participación."""
        SurveyUserInput = request.env['survey.user_input'].sudo()
        
        user_input = SurveyUserInput.search([
            ('partner_id', '=', participation.student_id.id),
            ('survey_id', '=', survey.id),
            ('create_date', '>=', participation.evaluation_id.date_start)
        ], limit=1)
        
        if not user_input:
            user_input = SurveyUserInput.create({
                'survey_id': survey.id,
                'partner_id': participation.student_id.id,
                'state': 'in_progress',
                'deadline': participation.evaluation_id.date_end,
            })
        elif user_input.state == 'new':
            user_input.write({'state': 'in_progress'})
        
        return user_input
    
    def _prepare_questions_data(self, survey, user_input):
        """Prepara datos de preguntas para el template."""
        questions = []
        
        # Obtener respuestas existentes (si hay user_input)
        existing_lines = {}
        if user_input:
            existing_lines = {
                line.question_id.id: line 
                for line in user_input.user_input_line_ids
            }
        
        for question in survey.question_ids:
            if question.is_page:
                questions.append({
                    'type': 'page',
                    'id': question.id,
                    'title': question.title,
                    'description': question.description,
                })
            else:
                q_data = {
                    'type': 'question',
                    'id': question.id,
                    'title': question.title,
                    'description': question.description,
                    'question_type': question.question_type,
                    'constr_mandatory': question.constr_mandatory,
                    'suggested_answer_ids': question.suggested_answer_ids,
                    'previous_answer': existing_lines.get(question.id),
                }
                
                # Para preguntas tipo matrix
                if question.question_type == 'matrix':
                    q_data['matrix_subtype'] = question.matrix_subtype
                    q_data['matrix_row_ids'] = question.matrix_row_ids
                
                questions.append(q_data)
        
        return questions
    
    def _process_answers(self, survey, user_input, post):
        """Procesa y guarda respuestas del formulario."""
        SurveyLine = request.env['survey.user_input.line'].sudo()
        
        # Eliminar respuestas anteriores (para permitir re-edición antes de completar)
        user_input.user_input_line_ids.unlink()
        
        for question in survey.question_ids:
            if question.is_page:
                continue
            
            # Procesar según tipo de pregunta
            if question.question_type == 'matrix':
                self._process_matrix_answer(question, user_input, post, SurveyLine)
            elif question.question_type in ('text_box', 'char_box'):
                self._process_text_answer(question, user_input, post, SurveyLine)
            elif question.question_type == 'simple_choice':
                self._process_simple_choice_answer(question, user_input, post, SurveyLine)
            elif question.question_type == 'multiple_choice':
                self._process_multiple_choice_answer(question, user_input, post, SurveyLine)
            elif question.question_type == 'numerical_box':
                self._process_numerical_answer(question, user_input, post, SurveyLine)
            elif question.question_type in ('date', 'datetime'):
                self._process_date_answer(question, user_input, post, SurveyLine)
    
    def _process_text_answer(self, question, user_input, post, SurveyLine):
        """Procesa respuestas de texto (text_box, char_box)."""
        answer_key = f'question_{question.id}'
        answer_value = post.get(answer_key, '').strip()
        
        if answer_value:
            data = {
                'user_input_id': user_input.id,
                'question_id': question.id,
                'answer_type': question.question_type,  # 'text_box' o 'char_box'
            }
            
            if question.question_type == 'text_box':
                data['value_text_box'] = answer_value
            else:
                data['value_char_box'] = answer_value
            
            SurveyLine.create(data)
    
    def _process_simple_choice_answer(self, question, user_input, post, SurveyLine):
        """Procesa respuestas de selección simple (radio)."""
        answer_key = f'question_{question.id}'
        answer_value = post.get(answer_key)
        
        if answer_value:
            try:
                answer_id = int(answer_value)
                SurveyLine.create({
                    'user_input_id': user_input.id,
                    'question_id': question.id,
                    'answer_type': 'suggestion',
                    'suggested_answer_id': answer_id,
                })
            except (ValueError, TypeError):
                pass
    
    def _process_multiple_choice_answer(self, question, user_input, post, SurveyLine):
        """Procesa respuestas de selección múltiple (checkbox)."""
        for key, value in post.items():
            if key.startswith(f'question_{question.id}_answer_'):
                try:
                    answer_id = int(value)
                    SurveyLine.create({
                        'user_input_id': user_input.id,
                        'question_id': question.id,
                        'answer_type': 'suggestion',
                        'suggested_answer_id': answer_id,
                    })
                except (ValueError, TypeError):
                    pass
    
    def _process_numerical_answer(self, question, user_input, post, SurveyLine):
        """Procesa respuestas numéricas."""
        answer_key = f'question_{question.id}'
        answer_value = post.get(answer_key)
        
        if answer_value:
            try:
                number = float(answer_value)
                SurveyLine.create({
                    'user_input_id': user_input.id,
                    'question_id': question.id,
                    'answer_type': 'numerical_box',
                    'value_numerical_box': number,
                })
            except (ValueError, TypeError):
                pass
    
    def _process_date_answer(self, question, user_input, post, SurveyLine):
        """Procesa respuestas de fecha/datetime."""
        answer_key = f'question_{question.id}'
        answer_value = post.get(answer_key)
        
        if answer_value:
            data = {
                'user_input_id': user_input.id,
                'question_id': question.id,
                'answer_type': question.question_type,
            }
            
            if question.question_type == 'date':
                data['value_date'] = answer_value
            else:
                data['value_datetime'] = answer_value
            
            SurveyLine.create(data)
    
    def _process_matrix_answer(self, question, user_input, post, SurveyLine):
        """Procesa respuestas de preguntas tipo matriz."""
        for row in question.matrix_row_ids:
            answer_key = f'question_{question.id}_row_{row.id}'
            answer_value = post.get(answer_key)
            
            if answer_value:
                # Respuesta única por fila (asumiendo matrix_subtype siempre 'simple')
                try:
                    answer_id = int(answer_value)
                    SurveyLine.create({
                        'user_input_id': user_input.id,
                        'question_id': question.id,
                        'answer_type': 'suggestion',
                        'matrix_row_id': row.id,
                        'suggested_answer_id': answer_id,
                    })
                except (ValueError, TypeError):
                    pass
