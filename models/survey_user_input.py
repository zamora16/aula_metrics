# -*- coding: utf-8 -*-
from odoo import models, fields

class SurveyUserInput(models.Model):
    """Hook para capturar cuando un alumno completa una encuesta de AulaMetrics"""
    _inherit = 'survey.user_input'
    
    def _mark_done(self):
        """
        Override del método que marca una encuesta como completada.
        Calcula scores, verifica alertas y marca participación como completada si corresponde.
        También captura respuestas cualitativas (texto abierto).
        """
        res = super(SurveyUserInput, self)._mark_done()
        
        for user_input in self:
            try:
                if not user_input.survey_id or not user_input.survey_id.is_aulametrics:
                    continue
                
                if not user_input.partner_id:
                    continue
                
                # Capturar respuestas cualitativas (texto)
                try:
                    user_input._save_qualitative_responses()
                except Exception:
                    pass
                
                evaluations = self.env['aulametrics.evaluation'].search([
                    ('state', 'in', ['scheduled', 'active']),
                    ('survey_ids', 'in', user_input.survey_id.id)
                ])
                
                if not evaluations:
                    continue
                
                for evaluation in evaluations:
                    participation = self.env['aulametrics.participation'].search([
                        ('evaluation_id', '=', evaluation.id),
                        ('student_id', '=', user_input.partner_id.id),
                        ('state', '=', 'pending')
                    ], limit=1)
                    
                    if not participation:
                        continue
                    
                    # Calcular puntuaciones y verificar alertas
                    try:
                        participation._calculate_scores()
                        participation.check_alerts()
                    except Exception:
                        pass
                    
                    # Verificar si completó todos los cuestionarios
                    try:
                        all_surveys = evaluation.survey_ids
                        completed_surveys = self.env['survey.user_input'].search_count([
                            ('partner_id', '=', user_input.partner_id.id),
                            ('survey_id', 'in', all_surveys.ids),
                            ('state', '=', 'done'),
                            ('create_date', '>=', evaluation.date_start)
                        ])
                        
                        if completed_surveys == len(all_surveys):
                            participation.action_complete()
                    except Exception:
                        pass
            
            except Exception:
                continue
        
        return res
    
    def _save_qualitative_responses(self):
        """Extrae y guarda respuestas de preguntas de texto abierto."""
        self.ensure_one()
        
        # Obtener preguntas de texto del survey
        text_questions = self.survey_id.question_ids.filtered(
            lambda q: q.question_type in ['text_box', 'char_box']
        )
        
        if not text_questions:
            return
        
        # Obtener participación asociada (última evaluación activa con este survey)
        evaluation = self.env['aulametrics.evaluation'].search([
            ('state', 'in', ['scheduled', 'active']),
            ('survey_ids', 'in', self.survey_id.id)
        ], order='date_start desc', limit=1)
        
        if not evaluation:
            return
        
        participation = self.env['aulametrics.participation'].search([
            ('evaluation_id', '=', evaluation.id),
            ('student_id', '=', self.partner_id.id)
        ], limit=1)
        
        if not participation or not participation.student_id.academic_group_id:
            return
        
        academic_group = participation.student_id.academic_group_id
        
        QualitativeResponse = self.env['aulametrics.qualitative_response']
        
        for question in text_questions:
            # Buscar respuesta del usuario
            line = self.user_input_line_ids.filtered(
                lambda l: l.question_id == question and (l.value_text_box or l.value_char_box)
            )
            
            if not line:
                continue
            
            # Obtener el texto según el tipo de pregunta
            response_text = (line[0].value_text_box or line[0].value_char_box or '').strip()
            
            # Validar límite de palabras (300 máximo)
            word_count = len(response_text.split())
            if word_count > 300:
                # Truncar a 300 palabras
                words = response_text.split()[:300]
                response_text = ' '.join(words) + '...'
            
            if not response_text:
                continue
            
            # Verificar si ya existe (evitar duplicados)
            existing = QualitativeResponse.search([
                ('user_input_id', '=', self.id),
                ('question_id', '=', question.id)
            ], limit=1)
            
            if existing:
                continue
            
            # Crear registro cualitativo
            QualitativeResponse.create({
                'student_id': self.partner_id.id,
                'academic_group_id': academic_group.id,
                'evaluation_id': evaluation.id,
                'survey_id': self.survey_id.id,
                'question_id': question.id,
                'user_input_id': self.id,
                'response_text': response_text,
                'response_date': self.create_date or fields.Datetime.now()
            })
