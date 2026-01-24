# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Importar configuración centralizada
from .survey_config import SURVEY_SCORING_CONFIGS
from .survey_scoring_strategies import SCORING_STRATEGIES
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
    
    @api.model_create_multi
    def create(self, vals_list):
        """Crear cuestionarios - solo permitido durante instalación de datos"""
        # Permitir creación durante carga de datos del módulo
        return super().create(vals_list)
    
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
        Calcula las puntuaciones de este cuestionario para una respuesta dada usando la estrategia adecuada.
        """
        self.ensure_one()
        config = SURVEY_SCORING_CONFIGS.get(self.survey_code)
        if not config:
            return {}
        scoring_class = SCORING_STRATEGIES.get(self.survey_code)
        if not scoring_class:
            return {}
        return scoring_class(self, config).calculate(user_input)
