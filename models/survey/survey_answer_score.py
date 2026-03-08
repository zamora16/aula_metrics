# -*- coding: utf-8 -*-
# Extensión de survey.question.answer para añadir campo score explícito
from odoo import models, fields

class SurveyQuestionAnswerScore(models.Model):
    _inherit = 'survey.question.answer'

    score = fields.Float(
        string='Puntuación (score)',
        default=0.0,
        help='Valor numérico real de esta opción para el cálculo de métricas. Si es 0 o vacío, se usará sequence como fallback.'
    )
