# -*- coding: utf-8 -*-
"""
Estrategia UNIVERSAL de cálculo de scoring para surveys (v1.9.0)
1 Cuestionario = 1 Métrica: todas las matrices se promedian juntas.
"""


class UniversalMatrixScoring:
    """
    Estrategia universal simplificada: 1 CUESTIONARIO = 1 MÉTRICA.
    - Todas las matrices del cuestionario se promedian juntas
    - El título del cuestionario = nombre de la métrica
    - Normaliza cada fila a 0-100 y promedia TODO
    """
    
    def __init__(self, survey):
        self.survey = survey
    
    def calculate(self, user_input):
        """Calcula 1 única métrica agregando TODAS las matrices del cuestionario"""
        metrics = []
        
        if not user_input or not user_input.user_input_line_ids:
            return metrics
        
        # Obtener todas las preguntas matriz del survey
        matrix_questions = self.survey.question_ids.filtered(
            lambda q: q.question_type == 'matrix'
        )
        
        if not matrix_questions:
            # Si no hay matrices, procesar preguntas no-matriz
            return self._process_non_matrix_questions(user_input)
        
        # Recopilar TODAS las líneas de TODAS las matrices
        all_scores = []
        
        for question in matrix_questions:
            try:
                # Obtener respuestas de esta matriz
                lines = user_input.user_input_line_ids.filtered(
                    lambda l: l.question_id.id == question.id
                )
                
                if not lines:
                    continue
                
                # Detectar max_sequence automáticamente para esta matriz
                max_seq = self._get_max_sequence(question)
                if not max_seq or max_seq <= 0:
                    continue
                
                # Normalizar todas las filas de esta matriz
                for line in lines:
                    if line.suggested_answer_id and hasattr(line.suggested_answer_id, 'sequence'):
                        if line.suggested_answer_id.sequence is not None:
                            score = (line.suggested_answer_id.sequence / max_seq) * 100
                            all_scores.append(score)
            
            except Exception:
                continue
        
        # Si tenemos scores, crear la métrica única
        if all_scores:
            avg_score = sum(all_scores) / len(all_scores)
            
            # Usar título del cuestionario como nombre de la métrica
            metric_label = self.survey.title if self.survey.title else "Encuesta"
            metric_name = self.survey.survey_code if hasattr(self.survey, 'survey_code') and self.survey.survey_code else f"survey_{self.survey.id}"
            
            metrics.append({
                'metric_name': metric_name,
                'metric_label': metric_label,
                'value_float': avg_score,
                'value_text': None,
                'value_json': None,
                'question_id': None  # No es de una pregunta específica, es del cuestionario completo
            })
        
        # Procesar preguntas no-matriz (texto, opciones) - estas van aparte
        metrics.extend(self._process_non_matrix_questions(user_input))
        
        return metrics
    
    def _get_max_sequence(self, question):
        """Detecta automáticamente el max_sequence de una matriz"""
        try:
            answers = question.suggested_answer_ids
            if answers:
                sequences = [ans.sequence for ans in answers 
                           if hasattr(ans, 'sequence') and ans.sequence is not None]
                if sequences:
                    return max(sequences)
        except Exception:
            pass
        return None
    
    def _process_non_matrix_questions(self, user_input):
        """Procesa preguntas no-matriz (texto, opciones simples) - van como métricas separadas"""
        metrics = []
        
        for line in user_input.user_input_line_ids:
            if not line.question_id:
                continue
            
            question = line.question_id
            
            # Skip matrices (ya procesadas)
            if question.question_type == 'matrix':
                continue
            
            metric_name = f"adhoc_q{question.id}"
            metric_label = question.title[:100] if question.title else f"Pregunta {question.sequence}"
            
            try:
                # Opciones simples/múltiples
                if question.question_type in ['simple_choice', 'multiple_choice']:
                    if line.suggested_answer_id and line.suggested_answer_id.value:
                        metrics.append({
                            'metric_name': metric_name,
                            'metric_label': metric_label,
                            'value_float': None,
                            'value_text': line.suggested_answer_id.value,
                            'value_json': None,
                            'question_id': question.id
                        })
                
                # Texto libre
                elif question.question_type in ['char_box', 'text_box']:
                    text_value = None
                    if hasattr(line, 'value_char_box') and line.value_char_box:
                        text_value = line.value_char_box
                    elif hasattr(line, 'value_text_box') and line.value_text_box:
                        text_value = line.value_text_box
                    
                    if text_value:
                        metrics.append({
                            'metric_name': metric_name,
                            'metric_label': metric_label,
                            'value_float': None,
                            'value_text': text_value,
                            'value_json': None,
                            'question_id': question.id
                        })
            
            except Exception:
                continue
        
        return metrics

# Todas las encuestas usan la estrategia universal
SCORING_STRATEGIES = {
    'WHO5': UniversalMatrixScoring,
    'BULLYING_VA': UniversalMatrixScoring,
    'ASQ14': UniversalMatrixScoring,
    'ADHOC': UniversalMatrixScoring,
}
