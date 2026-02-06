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

    # Campos related para facilitar agrupación y filtros
    academic_group_id = fields.Many2one(
        related='student_id.academic_group_id',
        string='Grupo Académico',
        store=True,
        readonly=True
    )
    
    student_gender = fields.Selection(
        related='student_id.gender',
        string='Género',
        store=True,
        readonly=True
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
    
    # Relación a valores de métricas (nuevo sistema flexible)
    metric_value_ids = fields.One2many(
        'aulametrics.metric_value',
        compute='_compute_metric_value_ids',
        string='Valores de Métricas',
        help='Valores de todas las métricas calculadas para este estudiante en esta evaluación'
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
    
    @api.depends('student_id', 'evaluation_id')
    def _compute_metric_value_ids(self):
        """Obtiene las métricas de este estudiante en esta evaluación"""
        for participation in self:
            if participation.student_id and participation.evaluation_id:
                participation.metric_value_ids = self.env['aulametrics.metric_value'].search([
                    ('student_id', '=', participation.student_id.id),
                    ('evaluation_id', '=', participation.evaluation_id.id)
                ])
            else:
                participation.metric_value_ids = False
    
    def get_metric_value(self, metric_name):
        """
        Obtiene el valor de una métrica específica para esta participación.
        Retorna el valor float o None si no existe.
        """
        self.ensure_one()
        metric = self.env['aulametrics.metric_value'].search([
            ('student_id', '=', self.student_id.id),
            ('evaluation_id', '=', self.evaluation_id.id),
            ('metric_name', '=', metric_name)
        ], limit=1)
        return metric.value_float if metric else None
    
    def get_all_metrics(self):
        """
        Retorna dict con todas las métricas de esta participación.
        Formato: {metric_name: value_float}
        """
        self.ensure_one()
        metrics = self.env['aulametrics.metric_value'].search([
            ('student_id', '=', self.student_id.id),
            ('evaluation_id', '=', self.evaluation_id.id)
        ])
        return {m.metric_name: m.value_float for m in metrics if m.value_float}
    
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
        Almacena los valores en el modelo metric_value para comparaciones temporales.
        """
        self.ensure_one()
        
        surveys = self.evaluation_id.survey_ids
        MetricValue = self.env['aulametrics.metric_value']
        
        for survey in surveys:
            # Buscar la respuesta del alumno a este survey DURANTE esta evaluación
            user_input = self.env['survey.user_input'].search([
                ('partner_id', '=', self.student_id.id),
                ('survey_id', '=', survey.id),
                ('state', '=', 'done'),
                ('create_date', '>=', self.evaluation_id.date_start)
            ], limit=1)
            
            if not user_input:
                continue
            
            # Delegar el cálculo al propio survey (ahora retorna lista de métricas)
            metrics = survey.calculate_scores(user_input)
            
            # Crear registros de metric_value para cada métrica
            if metrics:
                for metric in metrics:
                    MetricValue.create({
                        'survey_id': survey.id,
                        'student_id': self.student_id.id,
                        'evaluation_id': self.evaluation_id.id,
                        'user_input_id': user_input.id,
                        'question_id': metric.get('question_id'),  # Puede ser None para métricas agregadas
                        'metric_name': metric.get('metric_name'),
                        'metric_label': metric.get('metric_label'),
                        'value_float': metric.get('value_float'),
                        'value_text': metric.get('value_text'),
                        'value_json': metric.get('value_json'),
                        'timestamp': fields.Datetime.now(),
                    })
    
    def check_alerts(self):
        """Verifica si las puntuaciones actuales generan alertas"""
        self.ensure_one()
        self.env['aulametrics.alert'].check_alerts_for_participation(self)

    def action_expire(self):
        """Marca participaciones pendientes como expiradas"""
        for participation in self:
            if participation.state == 'pending':
                participation.write({'state': 'expired'})