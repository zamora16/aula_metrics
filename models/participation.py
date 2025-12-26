# -*- coding: utf-8 -*-
from odoo import models, fields, api

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
    
    # Constraint: un alumno solo puede tener una participación por evaluación
    _sql_constraints = [
        ('unique_student_evaluation',
         'UNIQUE(evaluation_id, student_id)',
         'Un alumno solo puede participar una vez en cada evaluación.')
    ]
    
    def action_complete(self):
        """Marca la participación como completada"""
        self.ensure_one()
        if self.state == 'pending':
            self.write({
                'state': 'completed',
                'completed_at': fields.Datetime.now()
            })
    
    def action_expire(self):
        """Marca participaciones pendientes como expiradas"""
        for participation in self:
            if participation.state == 'pending':
                participation.write({'state': 'expired'})