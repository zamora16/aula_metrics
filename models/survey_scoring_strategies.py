# -*- coding: utf-8 -*-
"""
Estrategias de cálculo de scoring para surveys AulaMetrics
"""
from .survey_config import SURVEY_SCORING_CONFIGS

class BaseSurveyScoring:
    def __init__(self, survey, config):
        self.survey = survey
        self.config = config

    def calculate(self, user_input):
        raise NotImplementedError("Debe implementar el método calculate en la subclase.")

class Who5Scoring(BaseSurveyScoring):
    def calculate(self, user_input):
        # Lógica igual a la genérica, pero se puede personalizar aquí
        return self._calculate_normalized_scores(user_input)

    def _calculate_normalized_scores(self, user_input):
        config = self.config
        scores = {}
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
                scores[subscale_name] = subscale_score
        return scores

class BullyingVAScoring(BaseSurveyScoring):
    def calculate(self, user_input):
        config = self.config
        scores = {}
        matrix_questions = self.survey.question_ids.filtered(
            lambda q: q.question_type == 'matrix'
        ).sorted(key=lambda q: q.sequence)
        subscale_items = list(config['subscales'].items())
        subscale_items.sort(key=lambda x: 1 if 'combine' in x[1] else 0)
        for subscale_name, subscale_config in subscale_items:
            if 'combine' in subscale_config:
                combined_scores = [scores[sub_name] for sub_name in subscale_config['combine'] if sub_name in scores]
                if combined_scores:
                    scores[subscale_name] = sum(combined_scores) / len(combined_scores)
                continue
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
        return scores

class Asq14Scoring(Who5Scoring):
    # Hereda la lógica de Who5Scoring (todas matrix)
    pass

SCORING_STRATEGIES = {
    'WHO5': Who5Scoring,
    'BULLYING_VA': BullyingVAScoring,
    'ASQ14': Asq14Scoring,
}
