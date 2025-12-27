# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class Evaluation(models.Model):
    """Evaluación Programada - Asignación de cuestionarios a grupos académicos"""
    _name = 'aulametrics.evaluation'
    _description = 'Evaluación Programada'
    _order = 'date_start desc, name'
    
    # Información básica
    name = fields.Char(
        string='Nombre',
        required=True,
        help='Ejemplo: Evaluación Trimestral Bienestar - 1º Trimestre 2025'
    )
    
    description = fields.Text(
        string='Descripción',
        help='Descripción de los objetivos de esta evaluación'
    )
    
    # Usuario responsable
    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        required=True,
        help='Usuario responsable de esta evaluación'
    )
    
    # Cuestionarios incluidos (Many2many)
    survey_ids = fields.Many2many(
        'survey.survey',
        'evaluation_survey_rel',
        'evaluation_id',
        'survey_id',
        string='Cuestionarios',
        required=True,
        help='Cuestionarios que forman parte de esta evaluación'
    )
    
    survey_count = fields.Integer(
        string='Nº Cuestionarios',
        compute='_compute_survey_count',
        store=True
    )
    
    # Grupos destinatarios (Many2many)
    academic_group_ids = fields.Many2many(
        'aulametrics.academic_group',
        'evaluation_group_rel',
        'evaluation_id',
        'group_id',
        string='Grupos Académicos',
        required=True,
        help='Grupos a los que se asignará esta evaluación'
    )
    
    group_count = fields.Integer(
        string='Nº Grupos',
        compute='_compute_group_count',
        store=True
    )
    
    # Programación temporal
    date_start = fields.Datetime(
        string='Fecha Inicio',
        required=True,
        help='Fecha y hora en que el alumnado puede empezar a responder'
    )
    
    date_end = fields.Datetime(
        string='Fecha Fin',
        required=True,
        help='Fecha y hora límite para completar la evaluación'
    )
    
    # Estado de la evaluación
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('scheduled', 'Programada'),
        ('active', 'Activa'),
        ('closed', 'Cerrada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', required=True)
    
    # Métricas de participación
    total_students = fields.Integer(
        string='Total Alumnos',
        compute='_compute_participation_metrics',
        store=True,
        help='Número total de alumnos de los grupos asignados'
    )
    
    completed_students = fields.Integer(
        string='Alumnos Completados',
        compute='_compute_participation_metrics',
        store=True,
        help='Número de alumnos que han completado la evaluación'
    )
    
    participation_rate = fields.Float(
        string='Tasa de Participación (%)',
        compute='_compute_participation_metrics',
        store=True,
        help='Porcentaje de alumnos que han completado'
    )
    
    # Relación con participaciones
    participation_ids = fields.One2many(
        'aulametrics.participation',
        'evaluation_id',
        string='Participaciones',
        help='Seguimiento de participación de cada alumno'
    )
    
    active = fields.Boolean(default=True)
    
    # Computed fields
    @api.depends('survey_ids')
    def _compute_survey_count(self):
        for evaluation in self:
            evaluation.survey_count = len(evaluation.survey_ids)
    
    @api.depends('academic_group_ids')
    def _compute_group_count(self):
        for evaluation in self:
            evaluation.group_count = len(evaluation.academic_group_ids)
    
    @api.depends('participation_ids.state', 'academic_group_ids.student_ids')
    def _compute_participation_metrics(self):
        """Calcula métricas de participación"""
        for evaluation in self:
            total = sum(group.student_count for group in evaluation.academic_group_ids)
            completed = len(evaluation.participation_ids.filtered(
                lambda p: p.state == 'completed'
            ))
            
            evaluation.total_students = total
            evaluation.completed_students = completed
            evaluation.participation_rate = (
                (completed / total * 100) if total > 0 else 0.0
            )
    
    # Validaciones
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Valida que fecha fin sea posterior a fecha inicio"""
        for evaluation in self:
            if evaluation.date_end <= evaluation.date_start:
                raise ValidationError(
                    _('La fecha de fin debe ser posterior a la fecha de inicio.')
                )
    
    # Acciones de estado
    def action_schedule(self):
        """Programar evaluación (draft -> scheduled)"""
        self.ensure_one()
        if not self.survey_ids:
            raise ValidationError(_('Debe asignar al menos un cuestionario.'))
        if not self.academic_group_ids:
            raise ValidationError(_('Debe asignar al menos un grupo académico.'))
        
        self.state = 'scheduled'
        self._create_participations()
    
    def action_activate(self):
        """Activar evaluación (scheduled -> active) y crear accesos para alumnos"""
        self.write({'state': 'active'})
        self._create_survey_accesses()
    
    def _create_survey_accesses(self):
        """Crea accesos directos (user_input) para cada participación pendiente"""
        SurveyUserInput = self.env['survey.user_input']
        
        for evaluation in self:
            # Solo procesar participaciones pendientes
            pending_participations = evaluation.participation_ids.filtered(
                lambda p: p.state == 'pending'
            )
            
            for participation in pending_participations:
                # Crear un user_input por cada survey de la evaluación
                for survey in evaluation.survey_ids:
                    # Verificar si ya existe acceso para este alumno/survey
                    existing_input = SurveyUserInput.search([
                        ('survey_id', '=', survey.id),
                        ('partner_id', '=', participation.student_id.id),
                        ('state', '!=', 'done')
                    ], limit=1)
                    
                    if not existing_input:
                        # Crear acceso (automáticamente genera token)
                        SurveyUserInput.create({
                            'survey_id': survey.id,
                            'partner_id': participation.student_id.id,
                            'deadline': evaluation.date_end,
                        })
    
    def action_close(self):
        """Cerrar evaluación (active -> closed)"""
        self.write({'state': 'closed'})
    
    def action_cancel(self):
        """Cancelar evaluación"""
        self.write({'state': 'cancelled'})
    
    def action_reset_to_draft(self):
        """Volver a borrador"""
        self.write({'state': 'draft'})
    
    def _create_participations(self):
        """Crea registros de participación para cada alumno de los grupos asignados"""
        Participation = self.env['aulametrics.participation']
        
        for group in self.academic_group_ids:
            for student in group.student_ids:
                existing = Participation.search([
                    ('evaluation_id', '=', self.id),
                    ('student_id', '=', student.id)
                ])
                
                if not existing:
                    Participation.create({
                        'evaluation_id': self.id,
                        'student_id': student.id,
                        'state': 'pending',
                    })
    
    def action_view_participations(self):
        """Acción para ver participaciones desde el smart button"""
        self.ensure_one()
        return {
            'name': 'Participaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'aulametrics.participation',
            'view_mode': 'tree,form',
            'domain': [('evaluation_id', '=', self.id)],
            'context': {'default_evaluation_id': self.id},
        }