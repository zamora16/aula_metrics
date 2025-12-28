# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SurveyExtension(models.Model):
    """Extensión del modelo survey de Odoo para AulaMetrics"""
    _inherit = 'survey.survey'
    
    # Campo para identificar cuestionarios de AulaMetrics
    is_aulametrics = fields.Boolean(
        string='Es AulaMetrics',
        default=False,
        help='Marca si este cuestionario pertenece a la biblioteca de AulaMetrics'
    )
    
    # Código identificador del cuestionario
    survey_code = fields.Char(
        string='Código del Cuestionario',
        help='Identificador único del cuestionario (ej: WHO5, BULLYING_VA)'
    )
    
    # Relación con evaluaciones
    evaluation_ids = fields.Many2many(
        'aulametrics.evaluation',
        'evaluation_survey_rel',
        'survey_id',
        'evaluation_id',
        string='Evaluaciones',
        help='Evaluaciones que usan este cuestionario'
    )
    
    # Contador de usos en evaluaciones
    evaluation_count = fields.Integer(
        string='Nº Evaluaciones',
        compute='_compute_evaluation_count',
        store=True
    )
    
    @api.depends('evaluation_ids')
    def _compute_evaluation_count(self):
        """Cuenta cuántas evaluaciones usan este cuestionario"""
        for survey in self:
            survey.evaluation_count = len(survey.evaluation_ids)

    def action_view_evaluations(self):
        """Acción para ver evaluaciones que usan este cuestionario"""
        self.ensure_one()
        return {
            'name': 'Evaluaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'aulametrics.evaluation',
            'view_mode': 'tree,form',
            'domain': [('survey_ids', 'in', self.id)],
            'context': {'default_survey_ids': [(6, 0, [self.id])]},
        }
    
    # ============================================================
    # MÉTODOS DE CÁLCULO DE PUNTUACIONES
    # ============================================================
    
    def calculate_scores(self, user_input):
        """
        Calcula las puntuaciones de este cuestionario para una respuesta dada.
        
        Cada cuestionario sabe cómo calcularse a sí mismo según su survey_code.
        Retorna un diccionario con los campos de puntuación a actualizar.
        
        Args:
            user_input: Registro de survey.user_input con las respuestas del alumno
            
        Returns:
            dict: Diccionario con campos de puntuación {campo: valor}
        """
        self.ensure_one()
        
        if self.survey_code == 'WHO5':
            return self._calculate_who5(user_input)
        elif self.survey_code == 'BULLYING_VA':
            return self._calculate_victimization_aggression(user_input)
        
        return {}
    
    def _calculate_who5(self, user_input):
        """
        Calcula la puntuación WHO-5 (Índice de Bienestar de la OMS)
        
        Fórmula:
        - Suma de 5 ítems, cada uno valorado de 0 a 5
        - Puntuación bruta: 0-25
        - Puntuación porcentual: (bruta × 4) = 0-100
        - Interpretación: <50 sugiere baja calidad de vida
        
        Returns:
            dict: {'who5_raw_score': int, 'who5_percentage': float}
        """
        self.ensure_one()
        
        answer_lines = user_input.user_input_line_ids.filtered(
            lambda l: l.question_id.question_type == 'matrix'
        )
        
        raw_score = 0
        item_count = 0
        
        for line in answer_lines:
            if line.suggested_answer_id:
                try:
                    value = int(line.suggested_answer_id.value or 0)
                    raw_score += value
                    item_count += 1
                except (ValueError, AttributeError):
                    continue
        
        # Solo retornar si se completaron los 5 ítems
        if item_count == 5:
            return {
                'who5_raw_score': raw_score,
                'who5_percentage': raw_score * 4
            }
        
        return {}
    
    def _calculate_victimization_aggression(self, user_input):
        """
        Calcula las puntuaciones de Victimización y Agresión
        
        El cuestionario tiene 2 preguntas matrix:
        - Primera matrix: 7 ítems de VICTIMIZACIÓN (sufrir acoso)
        - Segunda matrix: 7 ítems de AGRESIÓN (ejercer acoso)
        
        Cada ítem: 0=Nunca, 1=Pocas veces, 2=Algunas veces, 3=Muchas veces, 4=Siempre
        Puntuación por escala: 0-28 (7 ítems × 4 puntos máximo)
        
        Returns:
            dict: {'victimization_score': float, 'aggression_score': float}
        """
        self.ensure_one()
        
        matrix_questions = self.question_ids.filtered(
            lambda q: q.question_type == 'matrix'
        ).sorted(key=lambda q: q.sequence)
        
        if len(matrix_questions) < 2:
            return {}
        
        victimization_question = matrix_questions[0]
        aggression_question = matrix_questions[1]
        
        # Calcular Victimización
        victimization_lines = user_input.user_input_line_ids.filtered(
            lambda l: l.question_id.id == victimization_question.id
        )
        
        victimization_score = 0
        victimization_count = 0
        
        for line in victimization_lines:
            if line.suggested_answer_id:
                try:
                    value = int(line.suggested_answer_id.value or 0)
                    victimization_score += value
                    victimization_count += 1
                except (ValueError, AttributeError):
                    continue
        
        # Calcular Agresión
        aggression_lines = user_input.user_input_line_ids.filtered(
            lambda l: l.question_id.id == aggression_question.id
        )
        
        aggression_score = 0
        aggression_count = 0
        
        for line in aggression_lines:
            if line.suggested_answer_id:
                try:
                    value = int(line.suggested_answer_id.value or 0)
                    aggression_score += value
                    aggression_count += 1
                except (ValueError, AttributeError):
                    continue
        
        # Solo retornar si ambas escalas están completas
        if victimization_count == 7 and aggression_count == 7:
            return {
                'victimization_score': victimization_score,
                'aggression_score': aggression_score
            }
        
        return {}
