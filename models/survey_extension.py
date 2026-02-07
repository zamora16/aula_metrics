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
    
    # Feedback de calidad para encuestas ad hoc
    quality_feedback = fields.Html(
        string='Análisis de Calidad',
        compute='_compute_quality_feedback',
        help='Análisis automático de usabilidad (solo para encuestas del centro)'
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
    
    @api.depends('title', 'description', 'question_ids', 'question_ids.title', 'is_adhoc')
    def _compute_quality_feedback(self):
        """Calcula feedback de usabilidad para encuestas ad hoc"""
        for survey in self:
            if not survey.is_adhoc:
                survey.quality_feedback = False
                continue
            
            feedback_items = []
            warnings = []
            successes = []
            
            # 1. Validar cantidad de preguntas (rango recomendado: 5-20)
            questions = survey.question_ids.filtered(lambda q: not q.is_page)
            num_questions = len(questions)
            
            if num_questions == 0:
                warnings.append("No has añadido ninguna pregunta todavía.")
            elif num_questions < 5:
                warnings.append(f"Solo tienes {num_questions} pregunta(s). Recomendamos al menos 5.")
            elif num_questions > 20:
                warnings.append(f"Tienes {num_questions} preguntas. Considera reducir para evitar fatiga.")
            else:
                successes.append(f"Buena cantidad de preguntas ({num_questions}). ✓")
            
            # 2. Validar longitud de preguntas
            long_questions = []
            for i, question in enumerate(questions, 1):
                if question.title and len(question.title) > 150:
                    long_questions.append(f"#{i} ({len(question.title)} caracteres)")
            
            if long_questions:
                warnings.append(f"Preguntas largas: {', '.join(long_questions[:3])}{'...' if len(long_questions) > 3 else ''}")
            elif num_questions > 0:
                successes.append("Longitud de preguntas apropiada. ✓")
            
            # 3. Validar variedad de tipos
            question_types = questions.mapped('question_type')
            unique_types = set(question_types)
            if len(unique_types) >= 2:
                successes.append(f"Variedad de tipos de preguntas ({len(unique_types)} diferentes). ✓")
            elif len(unique_types) == 1 and num_questions > 3:
                warnings.append("Todas las preguntas son del mismo tipo. Considera variar.")
            
            # 4. Validar opciones en preguntas cerradas
            questions_without_options = 0
            matrix_questions = []
            for question in questions:
                if question.question_type in ['simple_choice', 'multiple_choice', 'matrix']:
                    if len(question.suggested_answer_ids) < 2:
                        questions_without_options += 1
                    elif question.question_type == 'matrix':
                        # Detectar max_sequence de cada matriz
                        sequences = [ans.sequence for ans in question.suggested_answer_ids if hasattr(ans, 'sequence') and ans.sequence]
                        if sequences:
                            max_seq = max(sequences)
                            matrix_questions.append((question.title[:50], max_seq))
            
            if questions_without_options > 0:
                warnings.append(f"{questions_without_options} pregunta(s) sin suficientes opciones (mínimo 2).")
            
            # 5. Información sobre normalización automática de matrices
            if matrix_questions:
                successes.append(f"Preguntas matriz: {len(matrix_questions)}. Se normalizarán automáticamente a 0-100. ✓")
            
            # Construir HTML
            html = "<div style='padding: 10px;'>"
            
            if successes:
                html += "<div style='background-color: #d4edda; border-left: 4px solid #28a745; padding: 10px; margin-bottom: 10px;'>"
                html += "<strong style='color: #155724;'>✓ Aspectos positivos:</strong><ul style='margin: 5px 0;'>"
                for success in successes:
                    html += f"<li style='color: #155724;'>{success}</li>"
                html += "</ul></div>"
            
            if warnings:
                html += "<div style='background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px;'>"
                html += "<strong style='color: #856404;'>⚠ Sugerencias:</strong><ul style='margin: 5px 0;'>"
                for warning in warnings:
                    html += f"<li style='color: #856404;'>{warning}</li>"
                html += "</ul></div>"
            
            if not warnings and not successes:
                html += "<p style='color: #6c757d;'>Añade preguntas para ver el análisis de calidad.</p>"
            
            # Información sobre el sistema de scoring
            if matrix_questions:
                html += "<div style='background-color: #e7f3ff; border-left: 4px solid #2196F3; padding: 10px; margin-top: 10px;'>"
                html += "<strong style='color: #0d47a1;'>ℹ️ Sistema de Scoring Automático</strong>"
                html += "<ul style='margin: 5px 0; color: #0d47a1;'>"
                html += "<li>Todas las preguntas matriz se normalizan automáticamente a escala 0-100</li>"
                html += "<li>Cada pregunta genera una métrica individual que puede usarse en dashboards y alertas</li>"
                html += "</ul>"
                html += "<details style='margin-top: 5px;'><summary style='cursor: pointer; color: #1976d2;'>Ver escalas detectadas por pregunta ▼</summary>"
                html += "<ul style='margin: 5px 0; font-size: 0.9em;'>"
                for q_title, max_seq in matrix_questions[:10]:
                    html += f"<li>'{q_title}...': Escala 1-{max_seq} → normalizada a 0-100</li>"
                if len(matrix_questions) > 10:
                    html += f"<li><em>... y {len(matrix_questions) - 10} más</em></li>"
                html += "</ul></details>"
                html += "</div>"
            
            html += "</div>"
            survey.quality_feedback = html

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
