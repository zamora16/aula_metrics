# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields
from .survey_scoring_strategies import SCORING_STRATEGIES

_logger = logging.getLogger(__name__)


class SurveyUserInput(models.Model):
    """Hook para capturar cuando un alumno completa una encuesta de AulaMetrics"""
    _inherit = 'survey.user_input'

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
                except Exception:
                    pass

                try:
                    user_input._save_multiplechoice_responses()
                except Exception:
                    pass

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
                    except Exception:
                        pass

                    # Verificar si completó todos los cuestionarios
                    try:
                        all_surveys = evaluation.survey_ids
                        domain = [
                            ('partner_id', '=', user_input.partner_id.id),
                            ('survey_id', 'in', all_surveys.ids),
                            ('state', '=', 'done'),
                        ]
                        if evaluation and evaluation.state == 'active':
                            if evaluation.date_end:
                                domain.append(('create_date', '<=', evaluation.date_end))
                        else:
                            if evaluation and evaluation.date_start:
                                domain.append(('create_date', '>=', evaluation.date_start))

                        completed_surveys = self.env['survey.user_input'].search_count(domain)

                        if completed_surveys == len(all_surveys):
                            participation.action_complete()
                    except Exception:
                        pass

            except Exception:
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

        # Determinar evaluación activa (si hay)
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
            ('state', 'in', ['scheduled', 'active']),
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
