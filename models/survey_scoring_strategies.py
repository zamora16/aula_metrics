# -*- coding: utf-8 -*-
"""
Estrategias de cálculo de scoring para surveys AulaMetrics.
Ahora retornan listas de métricas para almacenamiento flexible en metric_value.
"""
from .survey_config import SURVEY_SCORING_CONFIGS

class BaseSurveyScoring:
    """Clase base para estrategias de scoring"""
    
    def __init__(self, survey, config):
        self.survey = survey
        self.config = config

    def calculate(self, user_input):
        """
        Calcula las métricas para un user_input.
        Debe retornar una lista de dicts con formato:
        [
            {
                'metric_name': 'who5_score',
                'metric_label': 'Bienestar (WHO-5)',
                'value_float': 75.5,
                'value_text': None,
                'value_json': None
            },
            ...
        ]
        """
        raise NotImplementedError("Debe implementar el método calculate en la subclase.")

class Who5Scoring(BaseSurveyScoring):
    """Estrategia de scoring para WHO-5 (Bienestar)"""
    
    def calculate(self, user_input):
        return self._calculate_normalized_scores(user_input)

    def _calculate_normalized_scores(self, user_input):
        """Calcula scores normalizados para todas las subescalas"""
        config = self.config
        metrics = []
        
        matrix_questions = self.survey.question_ids.filtered(
            lambda q: q.question_type == 'matrix'
        ).sorted(key=lambda q: q.sequence)
        
        for subscale_name, subscale_config in config['subscales'].items():
            if subscale_config['questions'] == 'all_matrix':
                questions = matrix_questions
            else:
                questions = []
            
            total_score = 0
            item_count = 0
            
            for question in questions:
                lines = user_input.user_input_line_ids.filtered(
                    lambda l: l.question_id.id == question.id
                )
                for line in lines:
                    if line.suggested_answer_id:
                        value = (line.suggested_answer_id.sequence / config['max_sequence']) * 100
                        total_score += value
                        item_count += 1
            
            if item_count == subscale_config['items']:
                subscale_score = total_score / item_count
                metrics.append({
                    'metric_name': subscale_name,
                    'metric_label': subscale_config.get('label', subscale_name),
                    'value_float': subscale_score,
                    'value_text': None,
                    'value_json': None
                })
        
        return metrics

class BullyingVAScoring(BaseSurveyScoring):
    """Estrategia de scoring para Bullying VA (Victimización y Agresión)"""
    
    def calculate(self, user_input):
        config = self.config
        scores = {}  # Temp dict para cálculos combinados
        metrics = []  # Lista final de métricas
        
        matrix_questions = self.survey.question_ids.filtered(
            lambda q: q.question_type == 'matrix'
        ).sorted(key=lambda q: q.sequence)
        
        # Ordenar para calcular primero las subescalas base, luego las combinadas
        subscale_items = list(config['subscales'].items())
        subscale_items.sort(key=lambda x: 1 if 'combine' in x[1] else 0)
        
        for subscale_name, subscale_config in subscale_items:
            # Manejar subescalas combinadas
            if 'combine' in subscale_config:
                combined_scores = [scores[sub_name] for sub_name in subscale_config['combine'] if sub_name in scores]
                if combined_scores:
                    combined_value = sum(combined_scores) / len(combined_scores)
                    scores[subscale_name] = combined_value
                    metrics.append({
                        'metric_name': subscale_name,
                        'metric_label': subscale_config.get('label', subscale_name),
                        'value_float': combined_value,
                        'value_text': None,
                        'value_json': None
                    })
                continue
            
            # Calcular subescalas base
            idx = subscale_config['questions']
            questions = matrix_questions[idx:idx+1] if idx < len(matrix_questions) else []
            
            total_score = 0
            item_count = 0
            
            for question in questions:
                lines = user_input.user_input_line_ids.filtered(
                    lambda l: l.question_id.id == question.id
                )
                for line in lines:
                    if line.suggested_answer_id:
                        value = (line.suggested_answer_id.sequence / config['max_sequence']) * 100
                        total_score += value
                        item_count += 1
            
            if item_count == subscale_config['items']:
                subscale_score = total_score / item_count
                scores[subscale_name] = subscale_score
                metrics.append({
                    'metric_name': subscale_name,
                    'metric_label': subscale_config.get('label', subscale_name),
                    'value_float': subscale_score,
                    'value_text': None,
                    'value_json': None
                })
        
        return metrics

class Asq14Scoring(Who5Scoring):
    """Estrategia de scoring para ASQ-14 (Estrés). Hereda la lógica de Who5Scoring."""
    pass


class GenericAdHocScoring(BaseSurveyScoring):
    """
    Estrategia genérica para encuestas ad hoc.
    Almacena respuestas individuales sin scoring complejo.
    """
    
    def calculate(self, user_input):
        """Almacena cada respuesta como una métrica individual"""
        metrics = []
        
        for line in user_input.user_input_line_ids:
            question = line.question_id
            metric_name = f"adhoc_q{question.id}"
            metric_label = question.title[:100] if question.title else f"Pregunta {question.sequence}"
            
            # Diferentes tipos de valores según tipo de pregunta
            if question.question_type in ['simple_choice', 'multiple_choice']:
                # Para opciones, guardar la respuesta seleccionada
                if line.suggested_answer_id:
                    metrics.append({
                        'metric_name': metric_name,
                        'metric_label': metric_label,
                        'value_float': None,
                        'value_text': line.suggested_answer_id.value,
                        'value_json': None,
                        'question_id': question.id
                    })
            
            elif question.question_type == 'matrix':
                # Para matriz, normalizar score
                if line.suggested_answer_id and self.config.get('max_sequence'):
                    score = (line.suggested_answer_id.sequence / self.config['max_sequence']) * 100
                    metrics.append({
                        'metric_name': metric_name,
                        'metric_label': metric_label,
                        'value_float': score,
                        'value_text': line.suggested_answer_id.value,
                        'value_json': None,
                        'question_id': question.id
                    })
            
            elif question.question_type in ['char_box', 'text_box']:
                # Para texto, guardar raw
                if line.value_char_box or line.value_text_box:
                    metrics.append({
                        'metric_name': metric_name,
                        'metric_label': metric_label,
                        'value_float': None,
                        'value_text': line.value_char_box or line.value_text_box,
                        'value_json': None,
                        'question_id': question.id
                    })
        
        return metrics


SCORING_STRATEGIES = {
    'WHO5': Who5Scoring,
    'BULLYING_VA': BullyingVAScoring,
    'ASQ14': Asq14Scoring,
    'ADHOC': GenericAdHocScoring,  # Estrategia genérica para ad hoc
}
