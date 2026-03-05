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
        help='Identificador único del cuestionario (ej: WHO5, BULLYING_VA, SDQ)'
    )

    # Edad recomendada para el cuestionario
    recommended_age_min = fields.Integer(
        string='Edad mínima recomendada',
        default=0,
        help='Edad mínima recomendada para aplicar este cuestionario (0 = sin límite)'
    )
    recommended_age_max = fields.Integer(
        string='Edad máxima recomendada',
        default=0,
        help='Edad máxima recomendada para aplicar este cuestionario (0 = sin límite)'
    )

    # Baremos del cuestionario (sólo para is_aulametrics)
    baremo_ids = fields.One2many(
        'aula_metrics.survey_baremo_range',
        'survey_id',
        string='Baremos',
        help='Rangos de puntuación e interpretación para este cuestionario'
    )

    evaluation_ids = fields.Many2many(
        'aula_metrics.evaluation',
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
            # ADHOC -> pertenece al centro: no debería marcarse como biblioteca `is_aulametrics`.
            if self.env.context.get('default_is_adhoc') or vals.get('is_adhoc'):
                vals['is_adhoc'] = True
                vals['is_aulametrics'] = False
                vals['access_mode'] = 'token'  # Solo por token
                vals['users_login_required'] = False

            # Sólo administradores pueden definir `survey_code` (cuestionarios oficiales)
            if vals.get('survey_code') and not self.env.user.has_group('base.group_system'):
                raise UserError('Solo los administradores pueden definir `survey_code`.')

            # Sólo administradores pueden marcar como parte de la biblioteca AulaMetrics
            if vals.get('is_aulametrics') and not self.env.user.has_group('base.group_system'):
                raise UserError('Solo los administradores pueden marcar una encuesta como `is_aulametrics`.')

        return super().create(vals_list)

    def write(self, vals):
        """Evitar que usuarios no-admins asignen `survey_code` o marquen `is_aulametrics`."""
        if vals.get('survey_code') and not self.env.user.has_group('base.group_system'):
            raise UserError('Solo los administradores pueden modificar `survey_code`.')

        if 'is_aulametrics' in vals and vals.get('is_aulametrics') and not self.env.user.has_group('base.group_system'):
            raise UserError('Solo los administradores pueden cambiar `is_aulametrics`.')

        return super(SurveyExtension, self).write(vals)
    
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

    @api.constrains('question_and_page_ids', 'is_aulametrics')
    def _check_single_metric_question(self):
        """Asegura que los cuestionarios ad-hoc del centro tengan UNA sola pregunta.

        Los cuestionarios AulaMetrics oficiales (con survey_code) quedan exentos:
        pueden tener cualquier número de preguntas según su diseño.
        Solo los cuestionarios ad-hoc (is_adhoc=True, sin survey_code) están
        sujetos a esta restricción para mantener el modelo de 1 pregunta = 1 métrica.
        """
        metric_types = {
            'matrix', 'simple_choice', 'multiple_choice',
            'numerical_box', 'text_box', 'char_box'
        }
        for survey in self:
            # Solo aplicar a cuestionarios ad-hoc del centro (sin survey_code oficial)
            if not survey.is_adhoc:
                continue
            if survey.survey_code:
                # Tiene código oficial → forma parte de la librería AulaMetrics → exento
                continue

            metric_questions = survey.question_and_page_ids.filtered(
                lambda q: not getattr(q, 'is_page', False)
                and getattr(q, 'question_type', None) in metric_types
            )
            if not metric_questions:
                metric_questions = survey.question_ids.filtered(
                    lambda q: not q.is_page and q.question_type in metric_types
                )

            if len(metric_questions) > 1:
                raise UserError(
                    'Los cuestionarios ad-hoc del centro deben contener sólo UNA pregunta '
                    f'productora de métricas. Este cuestionario tiene {len(metric_questions)}.'
                )

    def action_view_evaluations(self):
        """Acción para ver evaluaciones que usan este cuestionario"""
        self.ensure_one()
        return {
            'name': 'Evaluaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'aula_metrics.evaluation',
            'view_mode': 'tree,form',
            'domain': [('survey_ids', 'in', self.id)],
            'context': {'default_survey_ids': [(6, 0, [self.id])]},
        }
    
    def action_test_survey(self):
        """Override para vista previa: usa portal personalizado si es AulaMetrics."""
        self.ensure_one()
        # Usar el portal de AulaMetrics tanto para encuestas oficiales como para ad-hoc
        if self.is_aulametrics or self.is_adhoc:
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

    is_segmentation = fields.Boolean(
        string='Variable de segmentación',
        default=False,
        help=(
            'Marca esta pregunta como variable de segmentación. '
            'Sólo las preguntas con esta opción activada aparecen en los filtros de segmentación '
            'del dashboard (p. ej. "¿Eres repetidor?", "Tipo de familia"). '
            'Los ítems de cuestionarios clínicos o escalas de puntuación NUNCA deben activar esta opción.'
        )
    )
