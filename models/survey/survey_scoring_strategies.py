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
                min_val, max_val = self._get_score_range(question)
                if max_val is None or max_val == min_val:
                    continue
                # Determinar si las opciones tienen scores explícitos configurados (no-cero).
                # Si ninguna opción tiene score >0, se usa sequence como valor numérico.
                has_configured_scores = any(
                    a.score not in (None, 0.0, False)
                    for a in question.suggested_answer_ids
                )
                # Normalizar todas las filas de esta matriz usando min-max:
                # opción mínima → 0, opción máxima → 100
                for line in lines:
                    ans = line.suggested_answer_id
                    if ans is not None:
                        if has_configured_scores:
                            value = ans.score  # puede ser 0 legítimamente (ej. "Nunca")
                        else:
                            value = ans.sequence  # fallback cuando no hay scores configurados
                        if value is not None:
                            score = (value - min_val) / (max_val - min_val) * 100
                            all_scores.append(score)
            except Exception:
                continue

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

    def _get_score_range(self, question):
        """
        Devuelve (min_val, max_val) para normalizar opciones de una pregunta matriz.
        - Si hay scores explícitos configurados (alguno > 0): min=0, max=max_score.
          Así "Nunca=0" siempre vale 0 y la opción máxima vale 100.
        - Si no hay scores configurados: usa sequences con min-max real,
          de modo que la primera opción siempre vale 0 y la última 100,
          independientemente de que Odoo haya asignado sequences 10, 20, 30...
        """
        try:
            answers = question.suggested_answer_ids
            if answers:
                configured = [a.score for a in answers
                              if hasattr(a, 'score') and a.score not in (None, 0.0, False)]
                if configured:
                    # Scores explícitos: mínimo semántico es 0 (ej. "Nunca")
                    return (0.0, max(configured))
                # Sin scores: usar sequences con normalización min-max
                sequences = [a.sequence for a in answers
                             if hasattr(a, 'sequence') and a.sequence is not None]
                if sequences:
                    return (min(sequences), max(sequences))
        except Exception:
            pass
        return (None, None)

    def _get_max_score(self, question):
        """Compatibilidad: delega a _get_score_range y devuelve solo el máximo."""
        _, max_val = self._get_score_range(question)
        return max_val
    
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

            # simple_choice / multiple_choice are handled exclusively by
            # survey_user_input._save_multiplechoice_responses() to avoid
            # creating duplicate metric_value records.

        except Exception:
            pass

        return metrics


# ============================================================
# Estrategia SDQ — Cuestionario de Capacidades y Dificultades
# Versión autoinforme (11-17 años)
# ============================================================

class SdqScoring:
    """
    Estrategia de puntuación para el SDQ (Strengths and Difficulties Questionnaire).
    Versión autoinforme para 11-17 años.

    25 ítems distribuidos en 5 sub-escalas de 5 ítems cada una (rango 0-10 c/u).
    El Total de Dificultades es la suma de las 4 primeras sub-escalas (rango 0-40).
    La sub-escala Prosocial NO se incluye en el Total de Dificultades.

    Los ítems inversos (7, 11, 14, 21, 25) se puntúan al revés:
      No es cierto → 2, Un tanto cierto → 1, Absolutamente cierto → 0.

    Opciones de respuesta estándar (por sequence):
      sequence 0 → No es cierto     → valor 0 (o 2 si es inverso)
      sequence 1 → Un tanto cierto  → valor 1
      sequence 2 → Absolutamente cierto → valor 2 (o 0 si es inverso)

    En el XML del cuestionario los ítems inversos deben llevar
    is_inverse=True en el campo correspondiente de la pregunta,
    o bien el campo de la respuesta `score` ya debe estar precalculado de forma inversa.

    Esta estrategia devuelve métricas con el siguiente formato:
      [
        {'metric_name': 'SDQ_emotional',    'metric_label': 'Síntomas emocionales',    'value_float': 3.0, ...},
        {'metric_name': 'SDQ_conduct',      'metric_label': 'Problemas de conducta',   'value_float': 2.0, ...},
        {'metric_name': 'SDQ_hyperactivity','metric_label': 'Hiperactividad/inatención','value_float': 5.0, ...},
        {'metric_name': 'SDQ_peer',         'metric_label': 'Problemas con compañeros', 'value_float': 1.0, ...},
        {'metric_name': 'SDQ_prosocial',    'metric_label': 'Conducta prosocial',       'value_float': 8.0, ...},
        {'metric_name': 'SDQ_total',        'metric_label': 'Total dificultades',       'value_float': 11.0, ...},
      ]
    """

    # Mapeo de número de ítem a sub-escala
    SCALE_ITEMS = {
        'emotional':     [3, 8, 13, 16, 24],
        'conduct':       [5, 7, 12, 18, 22],
        'hyperactivity': [2, 10, 15, 21, 25],
        'peer':          [6, 11, 14, 19, 23],
        'prosocial':     [1, 4, 9, 17, 20],
    }

    SCALE_LABELS = {
        'emotional':     'Síntomas emocionales',
        'conduct':       'Problemas de conducta',
        'hyperactivity': 'Hiperactividad/inatención',
        'peer':          'Problemas con compañeros',
        'prosocial':     'Conducta prosocial',
        'total':         'Total dificultades',
    }

    # Ítems con puntuación inversa
    INVERSE_ITEMS = {7, 11, 14, 21, 25}

    # Escalas que componen el Total de Dificultades
    DIFFICULTY_SCALES = ['emotional', 'conduct', 'hyperactivity', 'peer']

    def __init__(self, survey):
        self.survey = survey

    def calculate(self, user_input):
        """
        Calcula las 6 puntuaciones SDQ (5 sub-escalas + Total Dificultades).

        Returns:
            list[dict]: Lista de métricas con las puntuaciones calculadas.
        """
        if not user_input or not user_input.user_input_line_ids:
            return []

        # Construir mapa: número de ítem → puntuación obtenida
        item_scores = self._extract_item_scores(user_input)

        if not item_scores:
            return []

        # Calcular sub-escalas
        scale_results = {}
        metrics = []

        for scale_name, item_numbers in self.SCALE_ITEMS.items():
            scale_score = 0
            items_found = 0
            for item_num in item_numbers:
                score = item_scores.get(item_num)
                if score is not None:
                    scale_score += score
                    items_found += 1

            # Solo registrar si hay al menos 1 ítem respondido
            if items_found > 0:
                scale_results[scale_name] = scale_score
                metrics.append({
                    'metric_name': f'SDQ_{scale_name}',
                    'metric_label': self.SCALE_LABELS[scale_name],
                    'value_float': float(scale_score),
                    'value_text': None,
                    'value_json': None,
                    'question_id': None,
                })

        # Total dificultades
        total = sum(
            scale_results[s] for s in self.DIFFICULTY_SCALES if s in scale_results
        )
        metrics.append({
            'metric_name': 'SDQ_total',
            'metric_label': self.SCALE_LABELS['total'],
            'value_float': float(total),
            'value_text': None,
            'value_json': None,
            'question_id': None,
        })

        return metrics

    def calculate_scale_scores(self, user_input):
        """
        Devuelve un dict con los scores por sub-escala y el total,
        para persistir en SurveyResult.scale_scores_json.

        Returns:
            dict: {
                'emotional': score,
                'conduct': score,
                'hyperactivity': score,
                'peer': score,
                'prosocial': score,
                'total': score,
            }
        """
        if not user_input or not user_input.user_input_line_ids:
            return {}

        item_scores = self._extract_item_scores(user_input)
        if not item_scores:
            return {}

        result = {}
        for scale_name, item_numbers in self.SCALE_ITEMS.items():
            scale_score = sum(
                item_scores[n] for n in item_numbers if n in item_scores
            )
            result[scale_name] = scale_score

        result['total'] = sum(
            result.get(s, 0) for s in self.DIFFICULTY_SCALES
        )
        return result

    def _extract_item_scores(self, user_input):
        """
        Extrae la puntuación de cada ítem numerado del SDQ.

        El número de ítem se mapea a través del campo `sequence` de la pregunta
        (la pregunta con sequence=1 es el ítem 1, etc.) o del campo `sdq_item_number`
        si se definió explícitamente en el XML.

        Para ítems inversos, aplica la inversión: valor_final = 2 - valor_original.

        Returns:
            dict: {item_number: score_value}
        """
        item_scores = {}

        for line in user_input.user_input_line_ids:
            question = line.question_id
            if not question or question.is_page:
                continue

            # Obtener el número de ítem SDQ
            # Preferir campo explícito 'sdq_item_number'; fallback a sequence
            item_num = getattr(question, 'sdq_item_number', None)
            if not item_num:
                item_num = getattr(question, 'sequence', None)
            if not item_num:
                continue

            try:
                item_num = int(item_num)
            except (TypeError, ValueError):
                continue

            if item_num < 1 or item_num > 25:
                continue

            # Obtener la puntuación de la respuesta seleccionada
            answer = line.suggested_answer_id
            if not answer:
                continue

            # Usar el campo `score` si está definido; si no, usar sequence como fallback
            raw_value = None
            if hasattr(answer, 'score') and answer.score is not None and answer.score != 0.0:
                raw_value = float(answer.score)
            elif hasattr(answer, 'sequence') and answer.sequence is not None:
                raw_value = float(answer.sequence)

            if raw_value is None:
                continue

            # Aplicar inversión para ítems inversos
            if item_num in self.INVERSE_ITEMS:
                raw_value = 2.0 - raw_value

            item_scores[item_num] = raw_value

        return item_scores


# ============================================================
# Estrategia SWLS — Escala de Satisfacción con la Vida
# Diener et al. (1985) | 5 ítems Likert 1-7 | Suma → 5-35
# ============================================================

class SwlsScoring:
    """
    Estrategia de puntuación para el SWLS (Satisfaction With Life Scale).
    Suma los scores de los 5 ítems (1-7 cada uno) → puntuación total 5-35.
    Devuelve 1 única escala: 'total' (Satisfacción con la vida).
    """

    def __init__(self, survey):
        self.survey = survey

    def _sum_scores(self, user_input):
        """Suma los scores de todos los ítems respondidos del SWLS."""
        total = 0.0
        for line in (user_input.user_input_line_ids or []):
            ans = line.suggested_answer_id
            if ans and hasattr(ans, 'score') and ans.score not in (None, False):
                total += float(ans.score)
        return total

    def calculate_scale_scores(self, user_input):
        """Devuelve {'total': puntuación_raw} para que el pipeline lo enriquezca con baremos."""
        if not user_input or not user_input.user_input_line_ids:
            return {}
        return {'total': self._sum_scores(user_input)}

    def calculate(self, user_input):
        """Fallback: devuelve la métrica total SWLS (valor bruto 5-35)."""
        if not user_input or not user_input.user_input_line_ids:
            return []
        return [{
            'metric_name': 'SWLS',
            'metric_label': 'Satisfacción con la vida',
            'value_float': self._sum_scores(user_input),
            'value_text': None,
            'value_json': None,
            'question_id': None,
        }]


# Todas las encuestas usan la estrategia universal
SCORING_STRATEGIES = {
    'SDQ': SdqScoring,
    'SWLS': SwlsScoring,
    'ADHOC': UniversalMatrixScoring,
}
