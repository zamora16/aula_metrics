# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, models, fields
from .survey_scoring_strategies import SCORING_STRATEGIES

_logger = logging.getLogger(__name__)


class SurveyUserInput(models.Model):
    """Hook para capturar cuando un alumno completa una encuesta de AulaMetrics"""
    _inherit = 'survey.user_input'

    aulametrics_evaluation_id = fields.Many2one(
        'aula_metrics.evaluation',
        string='Evaluación AulaMetrics',
        index=True,
        ondelete='set null',
        help='Evaluación AulaMetrics a la que pertenece esta respuesta',
    )

    def _mark_done(self):
        """
        Override del método que marca una encuesta como completada.
        Calcula scores, verifica alertas y marca participación.
        Para cuestionarios is_aulametrics crea además un SurveyResult persistido.
        """
        res = super(SurveyUserInput, self)._mark_done()

        for user_input in self:
            try:
                # Procesar tanto cuestionarios oficiales como ad-hoc del centro
                if not user_input.survey_id or not (user_input.survey_id.is_aulametrics or user_input.survey_id.is_adhoc):
                    continue

                if not user_input.partner_id:
                    continue

                # ── Persistir SurveyResult para cuestionarios oficiales ──
                if user_input.survey_id.is_aulametrics:
                    try:
                        user_input._create_survey_result()
                    except Exception as e:
                        _logger.warning('SurveyResult: no se pudo crear para user_input %s: %s', user_input.id, e)

                # Capturar respuestas cualitativas y de opciones múltiples
                try:
                    user_input._save_qualitative_responses()
                except Exception as e:
                    _logger.error('_mark_done: error guardando respuestas cualitativas para user_input %s: %s', user_input.id, e, exc_info=True)

                try:
                    user_input._save_multiplechoice_responses()
                except Exception as e:
                    _logger.error('_mark_done: error guardando respuestas múltiple opción para user_input %s: %s', user_input.id, e, exc_info=True)

                evaluations = self.env['aula_metrics.evaluation'].search([
                    ('state', 'in', ['scheduled', 'active']),
                    ('survey_ids', 'in', user_input.survey_id.id)
                ])

                if not evaluations:
                    continue

                for evaluation in evaluations:
                    participation = self.env['aula_metrics.participation'].search([
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
                    except Exception as e:
                        _logger.error('_mark_done: error en scores/alertas para participación %s: %s', participation.id, e, exc_info=True)

                    # Verificar si completó todos los cuestionarios
                    try:
                        all_surveys = evaluation.survey_ids
                        completed_surveys = self.env['survey.user_input'].search_count([
                            ('partner_id', '=', user_input.partner_id.id),
                            ('survey_id', 'in', all_surveys.ids),
                            ('state', '=', 'done'),
                            ('aulametrics_evaluation_id', '=', evaluation.id),
                        ])
                        if completed_surveys == len(all_surveys):
                            participation.action_complete()
                    except Exception as e:
                        _logger.error('_mark_done: error verificando completitud para participación %s: %s', participation.id, e, exc_info=True)

            except Exception as e:
                _logger.error('_mark_done: error procesando user_input %s: %s', user_input.id, e, exc_info=True)
                continue

        return res

    def _create_survey_result(self):
        """
        Crea un registro SurveyResult para este user_input (cuestionario oficial AulaMetrics).
        Usa la estrategia de scoring específica del cuestionario para calcular
        el raw_score, los scale_scores y el baremo aplicado.
        """
        self.ensure_one()
        survey = self.survey_id
        survey_code = survey.survey_code or ''

        # Evitar crear duplicados si ya existe un resultado para este user_input
        existing = self.env['aula_metrics.survey_result'].search([
            ('user_input_id', '=', self.id)
        ], limit=1)
        if existing:
            return existing

        # Obtener la estrategia de scoring
        strategy_class = SCORING_STRATEGIES.get(survey_code)
        if not strategy_class:
            _logger.info('SurveyResult: sin estrategia para survey_code="%s", omitiendo.', survey_code)
            return None

        strategy = strategy_class(survey)

        # Calcular puntuaciones por sub-escala (si la estrategia lo soporta)
        scale_scores = {}
        if hasattr(strategy, 'calculate_scale_scores'):
            try:
                scale_scores = strategy.calculate_scale_scores(self)
            except Exception as e:
                _logger.warning('SurveyResult: calculate_scale_scores error: %s', e)

        # El raw_score es el total (o la primera métrica si no hay sub-escalas)
        raw_score = 0.0
        if scale_scores:
            raw_score = float(scale_scores.get('total', 0.0))
        else:
            metrics = strategy.calculate(self)
            if metrics:
                raw_score = float(metrics[0].get('value_float') or 0.0)

        # Buscar baremo global: usar 'total' si existe, sino None
        BaremoRange = self.env['aula_metrics.survey_baremo_range']
        scale_name_global = 'total' if 'total' in scale_scores else None
        global_baremo = BaremoRange.find_baremo(survey.id, raw_score, scale_name=scale_name_global)
        baremo_label = global_baremo.label if global_baremo else ''
        baremo_description = global_baremo.description if global_baremo else ''
        baremo_severity = global_baremo.severity if global_baremo else 0

        # Enriquecer scale_scores con baremo por sub-escala
        enriched_scales = {}
        for scale_name, score in scale_scores.items():
            baremo = BaremoRange.find_baremo(survey.id, float(score), scale_name=scale_name)
            enriched_scales[scale_name] = {
                'score': score,
                'label': baremo.label if baremo else '',
                'severity': baremo.severity if baremo else 0,
                'description': baremo.description if baremo else '',
            }

        # Usar la evaluación ya vinculada al user_input cuando esté disponible.
        # Hacer búsqueda genérica solo como fallback: evita asignar el resultado
        # a la evaluación equivocada cuando hay varias activas con el mismo survey.
        if self.aulametrics_evaluation_id:
            evaluation_id = self.aulametrics_evaluation_id.id
        else:
            evaluation = self.env['aula_metrics.evaluation'].search([
                ('state', 'in', ['scheduled', 'active']),
                ('survey_ids', 'in', survey.id)
            ], order='date_start desc', limit=1)
            evaluation_id = evaluation.id if evaluation else False

        vals = {
            'student_id': self.partner_id.id,
            'survey_id': survey.id,
            'user_input_id': self.id,
            'evaluation_id': evaluation_id,
            'completed_at': fields.Datetime.now(),
            'is_aulametrics': True,
            'raw_score': raw_score,
            'baremo_label': baremo_label,
            'baremo_description': baremo_description,
            'baremo_severity': baremo_severity,
            'scale_scores_json': json.dumps(enriched_scales) if enriched_scales else '{}',
        }
        result = self.env['aula_metrics.survey_result'].create(vals)
        _logger.info('SurveyResult creado: id=%s alumno=%s survey=%s score=%.1f baremo=%s',
                     result.id, self.partner_id.name, survey.title, raw_score, baremo_label)
        return result
    
    def _get_evaluation_context(self):
        """Obtiene la evaluación y participación activa para este user_input."""
        self.ensure_one()
        
        evaluation = self.env['aula_metrics.evaluation'].search([
            ('state', 'in', ['scheduled', 'active', 'closed']),
            ('survey_ids', 'in', self.survey_id.id)
        ], order='date_start desc', limit=1)
        
        if not evaluation:
            return None, None
        
        participation = self.env['aula_metrics.participation'].search([
            ('evaluation_id', '=', evaluation.id),
            ('student_id', '=', self.partner_id.id)
        ], limit=1)
        
        if not participation or not participation.student_id.academic_group_id:
            return None, None
        
        return evaluation, participation
    
    def _save_qualitative_responses(self):
        """Extrae y guarda respuestas de preguntas de texto abierto."""
        self.ensure_one()
        
        text_questions = self.survey_id.question_ids.filtered(
            lambda q: q.question_type in ['text_box', 'char_box']
        )
        
        if not text_questions:
            return
        
        evaluation, participation = self._get_evaluation_context()
        if not evaluation or not participation:
            return
        
        QualitativeResponse = self.env['aula_metrics.qualitative_response']
        
        for question in text_questions:
            line = self.user_input_line_ids.filtered(
                lambda l: l.question_id == question and (l.value_text_box or l.value_char_box)
            )
            
            if not line:
                continue
            
            response_text = (line[0].value_text_box or line[0].value_char_box or '').strip()
            
            # Truncar a 300 palabras si excede
            word_count = len(response_text.split())
            if word_count > 300:
                words = response_text.split()[:300]
                response_text = ' '.join(words) + '...'
            
            if not response_text:
                continue
            
            # Evitar duplicados
            existing = QualitativeResponse.search([
                ('user_input_id', '=', self.id),
                ('question_id', '=', question.id)
            ], limit=1)
            
            if existing:
                continue
            
            QualitativeResponse.create({
                'student_id': self.partner_id.id,
                'academic_group_id': participation.student_id.academic_group_id.id,
                'evaluation_id': evaluation.id,
                'survey_id': self.survey_id.id,
                'question_id': question.id,
                'user_input_id': self.id,
                'response_text': response_text,
                'response_date': self.create_date or fields.Datetime.now()
            })
    
    @api.model
    def get_or_create_for_participation(self, participation, survey):
        """Obtiene o crea un user_input para la participación dada."""
        SurveyUserInput = self.sudo()
        eval_rec = participation.evaluation_id

        user_input = SurveyUserInput.search([
            ('partner_id', '=', participation.student_id.id),
            ('survey_id', '=', survey.id),
            ('aulametrics_evaluation_id', '=', eval_rec.id),
        ], order='create_date desc', limit=1)

        if not user_input:
            user_input = SurveyUserInput.create({
                'survey_id': survey.id,
                'partner_id': participation.student_id.id,
                'state': 'in_progress',
                'deadline': eval_rec.date_end,
                'aulametrics_evaluation_id': eval_rec.id,
            })
        elif user_input.state == 'new':
            user_input.write({'state': 'in_progress'})

        return user_input

    def save_answers_from_post(self, survey, post):
        """Procesa y guarda respuestas del formulario POST en este user_input."""
        self.ensure_one()
        SurveyLine = self.env['survey.user_input.line'].sudo()

        # Borrar respuestas previas (permite re-edición antes de completar)
        self.user_input_line_ids.unlink()

        for question in survey.question_ids:
            if question.is_page:
                continue
            if question.question_type == 'matrix':
                self._save_matrix_answer(question, SurveyLine, post)
            elif question.question_type in ('text_box', 'char_box'):
                self._save_text_answer(question, SurveyLine, post)
            elif question.question_type == 'simple_choice':
                self._save_simple_choice_answer(question, SurveyLine, post)
            elif question.question_type == 'multiple_choice':
                self._save_multiple_choice_answer(question, SurveyLine, post)
            elif question.question_type == 'numerical_box':
                self._save_numerical_answer(question, SurveyLine, post)
            elif question.question_type in ('date', 'datetime'):
                self._save_date_answer(question, SurveyLine, post)

    def _save_text_answer(self, question, SurveyLine, post):
        answer_value = post.get(f'question_{question.id}', '').strip()
        if answer_value:
            data = {
                'user_input_id': self.id,
                'question_id': question.id,
                'answer_type': question.question_type,
            }
            if question.question_type == 'text_box':
                data['value_text_box'] = answer_value
            else:
                data['value_char_box'] = answer_value
            SurveyLine.create(data)

    def _save_simple_choice_answer(self, question, SurveyLine, post):
        answer_value = post.get(f'question_{question.id}')
        if answer_value:
            try:
                SurveyLine.create({
                    'user_input_id': self.id,
                    'question_id': question.id,
                    'answer_type': 'suggestion',
                    'suggested_answer_id': int(answer_value),
                })
            except (ValueError, TypeError):
                pass

    def _save_multiple_choice_answer(self, question, SurveyLine, post):
        prefix = f'question_{question.id}_answer_'
        for key, value in post.items():
            if key.startswith(prefix):
                try:
                    SurveyLine.create({
                        'user_input_id': self.id,
                        'question_id': question.id,
                        'answer_type': 'suggestion',
                        'suggested_answer_id': int(value),
                    })
                except (ValueError, TypeError):
                    pass

    def _save_numerical_answer(self, question, SurveyLine, post):
        answer_value = post.get(f'question_{question.id}')
        if answer_value:
            try:
                SurveyLine.create({
                    'user_input_id': self.id,
                    'question_id': question.id,
                    'answer_type': 'numerical_box',
                    'value_numerical_box': float(answer_value),
                })
            except (ValueError, TypeError):
                pass

    def _save_date_answer(self, question, SurveyLine, post):
        answer_value = post.get(f'question_{question.id}')
        if answer_value:
            data = {
                'user_input_id': self.id,
                'question_id': question.id,
                'answer_type': question.question_type,
            }
            if question.question_type == 'date':
                data['value_date'] = answer_value
            else:
                data['value_datetime'] = answer_value
            SurveyLine.create(data)

    def _save_matrix_answer(self, question, SurveyLine, post):
        for row in question.matrix_row_ids:
            answer_value = post.get(f'question_{question.id}_row_{row.id}')
            if answer_value:
                try:
                    SurveyLine.create({
                        'user_input_id': self.id,
                        'question_id': question.id,
                        'answer_type': 'suggestion',
                        'matrix_row_id': row.id,
                        'suggested_answer_id': int(answer_value),
                    })
                except (ValueError, TypeError):
                    pass

    def _save_multiplechoice_responses(self):
        """Extrae y guarda respuestas de opción múltiple como métricas JSON."""
        self.ensure_one()
        
        choice_questions = self.survey_id.question_ids.filtered(
            lambda q: q.question_type in ['simple_choice', 'multiple_choice']
        )
        
        if not choice_questions:
            return
        
        evaluation, participation = self._get_evaluation_context()
        if not evaluation or not participation:
            return
        
        MetricValue = self.env['aula_metrics.metric_value']
        
        for question in choice_questions:
            lines = self.user_input_line_ids.filtered(
                lambda l: l.question_id == question and l.suggested_answer_id
            )
            
            if not lines:
                continue
            
            # Recopilar opciones seleccionadas
            selected_options = [
                line.suggested_answer_id.value 
                for line in lines 
                if line.suggested_answer_id and line.suggested_answer_id.value
            ]
            
            if not selected_options:
                continue
            
            metric_name = f'question_{question.id}_choices'
            metric_label = question.metric_label[:100]
            
            # Evitar duplicados
            existing = MetricValue.search([
                ('survey_id', '=', self.survey_id.id),
                ('student_id', '=', self.partner_id.id),
                ('evaluation_id', '=', evaluation.id),
                ('question_id', '=', question.id),
                ('metric_name', '=', metric_name)
            ], limit=1)
            
            if existing:
                existing.write({
                    'value_json': selected_options,
                    'timestamp': self.create_date or fields.Datetime.now()
                })
            else:
                MetricValue.create({
                    'survey_id': self.survey_id.id,
                    'student_id': self.partner_id.id,
                    'evaluation_id': evaluation.id,
                    'question_id': question.id,
                    'user_input_id': self.id,
                    'metric_name': metric_name,
                    'metric_label': metric_label,
                    'value_json': selected_options,
                    'timestamp': self.create_date or fields.Datetime.now()
                })
