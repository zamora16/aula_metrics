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
            # Si no hay matrices, procesar preguntas no-matriz y devolver UNA métrica por survey
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
                # Calcular el máximo valor de score/sequence para normalizar (fuera del bucle)
                max_value = self._get_max_score(question)
                if not max_value:
                    continue
                # Normalizar todas las filas de esta matriz usando score (fallback a sequence)
                for line in lines:
                    ans = line.suggested_answer_id
                    if ans is not None:
                        # Usar score si está definido (None), si no fallback a sequence
                        value = ans.score if ans.score is not None else ans.sequence
                        if value is not None:
                            score = (value / max_value) * 100
                            all_scores.append(score)
            except Exception:
                continue

    def _get_max_score(self, question):
        """Detecta el máximo score definido en las opciones de la matriz, fallback a max_sequence si no hay scores."""
        try:
            answers = question.suggested_answer_ids
            if answers:
                scores = [ans.score for ans in answers if hasattr(ans, 'score') and ans.score not in (None, 0.0, False)]
                if scores:
                    return max(scores)
                # Fallback a sequence si no hay scores
                sequences = [ans.sequence for ans in answers if hasattr(ans, 'sequence') and ans.sequence is not None]
                if sequences:
                    return max(sequences)
        except Exception:
            pass
        return None
        
        # Si tenemos scores, crear la métrica única
        if all_scores:
            avg_score = sum(all_scores) / len(all_scores)
            
            # Usar título del cuestionario como nombre de la métrica
            # Preferir el metric_label definido en la primera matriz (si existe)
            first_matrix = matrix_questions[0] if matrix_questions else None
            metric_label = (first_matrix.metric_label[:100] if first_matrix and getattr(first_matrix, 'metric_label', False)
                            else (self.survey.title if self.survey.title else "Encuesta"))
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
        """Procesa preguntas tipo texto libre.
        
        Nota: Opciones múltiples se procesan en survey_user_input._save_multiplechoice_responses()
        """
        metrics = []

        # Agrupar por pregunta relevante (excluyendo páginas y matrices)
        relevant_lines = [l for l in user_input.user_input_line_ids if l.question_id and l.question_id.question_type != 'matrix' and not l.question_id.is_page]
        if not relevant_lines:
            return metrics

        # Dado que aplicamos la restricción de 1 pregunta productora por survey,
        # la pregunta relevante será la única. Tomamos la primera encontrada.
        main_question = list({l.question_id for l in relevant_lines})[0]

        metric_label = main_question.metric_label[:100] if hasattr(main_question, 'metric_label') else (main_question.title or 'Encuesta')
        metric_name = self.survey.survey_code if hasattr(self.survey, 'survey_code') and self.survey.survey_code else f"survey_{self.survey.id}"

        # Procesar según tipo
        try:
            if main_question.question_type in ['char_box', 'text_box']:
                # Guardar texto cualitativo (usar el primer valor no vacío)
                text_value = None
                for line in relevant_lines:
                    if line.question_id.id == main_question.id:
                        if hasattr(line, 'value_char_box') and line.value_char_box:
                            text_value = line.value_char_box
                            break
                        if hasattr(line, 'value_text_box') and line.value_text_box:
                            text_value = line.value_text_box
                            break

                if text_value:
                    metrics.append({
                        'metric_name': metric_name,
                        'metric_label': metric_label,
                        'value_float': None,
                        'value_text': text_value,
                        'value_json': None,
                        'question_id': main_question.id
                    })

            elif main_question.question_type == 'numerical_box':
                # Tomar el primer valor numérico encontrado
                num = None
                for line in relevant_lines:
                    if line.question_id.id == main_question.id and hasattr(line, 'value_numerical_box') and line.value_numerical_box is not None:
                        num = line.value_numerical_box
                        break

                if num is not None:
                    metrics.append({
                        'metric_name': metric_name,
                        'metric_label': metric_label,
                        'value_float': float(num),
                        'value_text': None,
                        'value_json': None,
                        'question_id': main_question.id
                    })

            elif main_question.question_type in ['simple_choice', 'multiple_choice']:
                # Tratar siempre las opciones como variables de segmentación categóricas.
                # Recopilar los valores/textos de las opciones seleccionadas y guardarlos en value_json.
                selected = []
                for line in relevant_lines:
                    if line.question_id.id == main_question.id and line.suggested_answer_id:
                        # Usar el valor (label) de la opción para segmentación
                        val = getattr(line.suggested_answer_id, 'value', None)
                        if val is None:
                            # Fallback a la etiqueta si no hay 'value'
                            val = getattr(line.suggested_answer_id, 'name', None)
                        if val is not None:
                            selected.append(val)

                if selected:
                    metrics.append({
                        'metric_name': metric_name,
                        'metric_label': metric_label,
                        'value_float': None,
                        'value_text': None,
                        'value_json': selected,
                        'question_id': main_question.id
                    })

        except Exception:
            pass

        return metrics

# Todas las encuestas usan la estrategia universal
SCORING_STRATEGIES = {
    'WHO5': UniversalMatrixScoring,
    'BULLYING_VA': UniversalMatrixScoring,
    'ASQ14': UniversalMatrixScoring,
    'ADHOC': UniversalMatrixScoring,
}
