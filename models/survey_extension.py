# -*- coding: utf-8 -*-
from odoo import models, fields, api

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
    
    # Marca si es una encuesta ad hoc creada por un orientador
    is_adhoc = fields.Boolean(
        string='Encuesta Ad Hoc',
        default=False,
        help='Marca si este cuestionario fue creado por un orientador (no es oficial)'
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
        """Crear cuestionarios - ahora permitido para orientadores"""
        for vals in vals_list:
            # Si se crea desde menú de cuestionarios del centro, marcar como ad hoc
            if self.env.context.get('default_is_adhoc') or vals.get('is_adhoc'):
                vals['is_aulametrics'] = True
                vals['is_adhoc'] = True
                vals['access_mode'] = 'token'  # Solo por token
                vals['users_login_required'] = False
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
    
    def action_test_survey(self):
        """Override para vista previa: usa portal personalizado si es AulaMetrics."""
        self.ensure_one()
        if self.is_aulametrics:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/survey/preview/{self.id}',
                'target': 'new',
            }
        else:
            return super().action_test_survey()

    # ============================================================
    # MÉTODOS DE CÁLCULO DE PUNTUACIONES
    # ============================================================
    

    def calculate_scores(self, user_input):
        """
        Calcula las puntuaciones de este cuestionario para una respuesta dada.
        v1.9.0: Todas las encuestas usan la estrategia universal (1 cuestionario = 1 métrica)
        """
        self.ensure_one()
        
        if not user_input:
            return []
        
        try:
            # Determinar qué estrategia usar
            if self.is_adhoc:
                strategy_key = 'ADHOC'
            elif self.survey_code:
                strategy_key = self.survey_code
            else:
                return []
            
            # Obtener y ejecutar estrategia
            scoring_class = SCORING_STRATEGIES.get(strategy_key)
            if not scoring_class:
                return []
            
            return scoring_class(self).calculate(user_input)
        
        except Exception:
            return []


class SurveyQuestionExtension(models.Model):
    """Extensión del modelo de preguntas de encuesta para AulaMetrics"""
    _inherit = 'survey.question'
    
    metric_label = fields.Char(
        string='Métrica',
        required=True,
        help='Nombre corto que identifica esta métrica en dashboards, gráficos y reportes de análisis.'
    )
