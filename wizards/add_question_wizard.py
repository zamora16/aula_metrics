# -*- coding: utf-8 -*-

from odoo import api, fields, models

class AddQuestionWizard(models.TransientModel):
    _name = 'aula_metrics.add_question_wizard'
    _description = 'Asistente para Añadir Pregunta'
    
    survey_id = fields.Many2one('survey.survey', string='Encuesta', required=True, readonly=True)
    title = fields.Char(string='Pregunta', required=True)
    question_type = fields.Selection([
        ('simple_choice', 'Opción Única'),
        ('multiple_choice', 'Opción Múltiple'),
        ('char_box', 'Texto Corto'),
        ('text_box', 'Texto Largo'),
        ('matrix', 'Matriz'),
    ], string='Tipo de Pregunta', required=True, default='simple_choice')
    sequence = fields.Integer(string='Secuencia', default=10)
    
    # Opciones de respuesta (solo para choice/matrix)
    answer_line_ids = fields.One2many('aula_metrics.add_question_wizard.answer', 'wizard_id', string='Opciones')
    
    def action_add_question(self):
        """Crear la pregunta en la encuesta"""
        self.ensure_one()
        
        # Crear la pregunta
        question_vals = {
            'survey_id': self.survey_id.id,
            'title': self.title,
            'question_type': self.question_type,
            'sequence': self.sequence,
        }
        
        question = self.env['survey.question'].create(question_vals)
        
        # Crear las opciones de respuesta si hay
        if self.answer_line_ids and self.question_type in ['simple_choice', 'multiple_choice', 'matrix']:
            for line in self.answer_line_ids:
                self.env['survey.question.answer'].create({
                    'question_id': question.id,
                    'value': line.value,
                    'sequence': line.sequence,
                })
        
        return {'type': 'ir.actions.act_window_close'}


class AddQuestionWizardAnswer(models.TransientModel):
    _name = 'aula_metrics.add_question_wizard.answer'
    _description = 'Línea de Respuesta del Wizard'
    _order = 'sequence, id'
    
    wizard_id = fields.Many2one('aula_metrics.add_question_wizard', string='Wizard', required=True, ondelete='cascade')
    value = fields.Char(string='Texto de la Opción', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
