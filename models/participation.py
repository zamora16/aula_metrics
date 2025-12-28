# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid

class Participation(models.Model):
    """Seguimiento de participación de alumnos en evaluaciones"""
    _name = 'aulametrics.participation'
    _description = 'Participación en Evaluación'
    _order = 'evaluation_id desc, student_id'
    
    # Relaciones
    evaluation_id = fields.Many2one(
        'aulametrics.evaluation',
        string='Evaluación',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    student_id = fields.Many2one(
        'res.partner',
        string='Alumno',
        required=True,
        ondelete='cascade',
        index=True,
        domain=[('academic_group_id', '!=', False)]
    )
    
    # Token único para acceso web
    evaluation_token = fields.Char(
        string='Token de Acceso',
        readonly=True,
        copy=False,
        index=True,
        help='Token único para acceder al portal de evaluación'
    )
    
    # Estado de participación
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('completed', 'Completada'),
        ('expired', 'Expirada'),
    ], string='Estado', default='pending', required=True, index=True)
    
    # Timestamp de completado
    completed_at = fields.Datetime(
        string='Completada',
        readonly=True,
        help='Fecha y hora en que el alumno finalizó el cuestionario'
    )
    
    # Puntuaciones calculadas - WHO-5 (Bienestar)
    who5_raw_score = fields.Integer(
        string='WHO-5 Puntuación Bruta',
        readonly=True,
        help='Suma de los 5 ítems (0-25)'
    )
    
    who5_percentage = fields.Float(
        string='WHO-5 Porcentaje',
        readonly=True,
        help='Puntuación convertida a escala 0-100. <50 sugiere baja calidad de vida'
    )
    
    # Puntuaciones calculadas - Victimización y Agresión
    victimization_score = fields.Float(
        string='Puntuación Victimización',
        readonly=True,
        help='Suma de 7 ítems de victimización (0-28). Mayor puntuación = mayor victimización'
    )
    
    aggression_score = fields.Float(
        string='Puntuación Agresión',
        readonly=True,
        help='Suma de 7 ítems de agresión (0-28). Mayor puntuación = mayor agresión'
    )
    
    # Constraint: un alumno solo puede tener una participación por evaluación
    _sql_constraints = [
        ('unique_student_evaluation',
         'UNIQUE(evaluation_id, student_id)',
         'Un alumno solo puede participar una vez en cada evaluación.')
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Genera token único al crear participación"""
        for vals in vals_list:
            if not vals.get('evaluation_token'):
                vals['evaluation_token'] = str(uuid.uuid4())
        return super().create(vals_list)
    
    def action_complete(self):
        """Marca la participación como completada y calcula puntuaciones"""
        self.ensure_one()
        if self.state == 'pending':
            # Calcular puntuaciones antes de marcar como completada
            self._calculate_scores()
            
            self.write({
                'state': 'completed',
                'completed_at': fields.Datetime.now()
            })
    
    def _calculate_scores(self):
        """
        Calcula las puntuaciones de todos los cuestionarios de la evaluación.
        """
        self.ensure_one()
        
        surveys = self.evaluation_id.survey_ids
        
        for survey in surveys:
            # Buscar la respuesta del alumno a este survey
            user_input = self.env['survey.user_input'].search([
                ('partner_id', '=', self.student_id.id),
                ('survey_id', '=', survey.id),
                ('state', '=', 'done')
            ], limit=1)
            
            if not user_input:
                continue
            
            # Delegar el cálculo al propio survey
            scores = survey.calculate_scores(user_input)
            
            # Actualizar las puntuaciones calculadas
            if scores:
                self.write(scores)
    
    def action_expire(self):
        """Marca participaciones pendientes como expiradas"""
        for participation in self:
            if participation.state == 'pending':
                participation.write({'state': 'expired'})