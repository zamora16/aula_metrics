# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

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
    
    # Duración media estimada (10 segundos por ítem, mostrado en minutos)
    average_duration = fields.Integer(
        string='Duración Media (min)',
        compute='_compute_average_duration',
        help='Duración estimada en minutos (10 seg por ítem del cuestionario, redondeado)'
    )
    
    @api.model
    def create(self, vals):
        """Prevenir la creación de nuevos cuestionarios"""
        raise UserError("No se pueden crear nuevos cuestionarios. Los cuestionarios son proporcionados por el sistema de AulaMetrics.")
    
    @api.depends('evaluation_ids')
    def _compute_evaluation_count(self):
        """Cuenta cuántas evaluaciones usan este cuestionario"""
        for survey in self:
            survey.evaluation_count = len(survey.evaluation_ids)
    
    @api.depends('question_ids')
    def _compute_average_duration(self):
        """Calcula la duración media estimada: 10 segundos por ítem del cuestionario, en minutos redondeados"""
        for survey in self:
            item_count = 0
            matrix_questions = survey.question_ids.filtered(lambda q: q.question_type == 'matrix')
            if matrix_questions:
                # Para preguntas matrix, contar las filas (answers con matrix_question_id)
                matrix_answers = self.env['survey.question.answer'].search([
                    ('matrix_question_id', 'in', matrix_questions.ids)
                ])
                item_count += len(matrix_answers)
            
            # Para preguntas no matrix, contar como 1 ítem cada una
            non_matrix_questions = survey.question_ids.filtered(lambda q: q.question_type != 'matrix' and not q.is_page)
            item_count += len(non_matrix_questions)
            
            # Calcular en segundos y convertir a minutos redondeados
            total_seconds = item_count * 10
            survey.average_duration = round(total_seconds / 60)

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
        
        Retorna un diccionario con los campos de puntuación a actualizar.
        
        Args:
            user_input: Registro de survey.user_input con las respuestas del alumno
            
        Returns:
            dict: Diccionario con campos de puntuación {campo: valor}
        """
        self.ensure_one()
        
        # Configuración por survey_code
        survey_configs = {
            'WHO5': {
                'max_sequence': 5,
                'subscales': {
                    'who5_score': {'questions': 'all_matrix', 'items': 5}
                }
            },
            'BULLYING_VA': {
                'max_sequence': 4,
                'subscales': {
                    'bullying_score': {'questions': 'all', 'items': 14},  # Global: suma de ambas matrices
                    'victimization_score': {'questions': 0, 'items': 7},
                    'aggression_score': {'questions': 1, 'items': 7}
                }
            }
        }
        
        config = survey_configs.get(self.survey_code)
        if not config:
            return {}
        
        return self._calculate_normalized_scores(user_input, config)
    
    def _calculate_normalized_scores(self, user_input, config):
        """
        Calcula puntuaciones normalizadas (0-100) basadas en configuración.
        
        Args:
            user_input: survey.user_input
            config: dict con max_sequence y subscales
            
        Returns:
            dict: {'field_name': float, ...}
        """
        scores = {}
        
        matrix_questions = self.question_ids.filtered(
            lambda q: q.question_type == 'matrix'
        ).sorted(key=lambda q: q.sequence)
        
        subscale_scores = []
        
        for subscale_name, subscale_config in config['subscales'].items():
            if subscale_config['questions'] == 'all_matrix':
                # Todas las preguntas matrix
                questions = matrix_questions
            elif subscale_config['questions'] == 'all':
                # Todas las preguntas matrix (alias)
                questions = matrix_questions
            else:
                # Índice específico
                questions = matrix_questions[subscale_config['questions']] if subscale_config['questions'] < len(matrix_questions) else None
                if not questions:
                    continue
                questions = [questions]
            
            total_score = 0
            item_count = 0
            
            for question in questions:
                lines = user_input.user_input_line_ids.filtered(
                    lambda l: l.question_id.id == question.id
                )
                for line in lines:
                    if line.suggested_answer_id:
                        # Normalizar: sequence 0-max -> 0-100
                        value = (line.suggested_answer_id.sequence / config['max_sequence']) * 100
                        total_score += value
                        item_count += 1
            
            # Solo calcular si se completaron todos los ítems esperados
            if item_count == subscale_config['items']:
                subscale_score = total_score / item_count
                scores[subscale_name] = subscale_score
                subscale_scores.append(subscale_score)
        
        return scores
