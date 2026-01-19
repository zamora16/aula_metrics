# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# Importar configuración centralizada
from .survey_config import SURVEY_METRICS, SURVEY_CODE_TO_FIELD

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

    # Indicadores de surveys incluidos
    has_who5 = fields.Boolean(
        string='Incluye WHO-5',
        compute='_compute_has_surveys',
        store=True
    )
    has_bullying = fields.Boolean(
        string='Incluye Bullying',
        compute='_compute_has_surveys',
        store=True
    )
    has_stress = fields.Boolean(
        string='Incluye Estrés',
        compute='_compute_has_surveys',
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

    @api.model_create_multi
    def create(self, vals_list):
        """Crear evaluación y su reporte asociado"""
        evaluations = super().create(vals_list)
        for evaluation in evaluations:
            self.env['aulametrics.report'].create({
                'evaluation_id': evaluation.id
            })
        return evaluations
    
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

    @api.depends('survey_ids.survey_code')
    def _compute_has_surveys(self):
        """Determina qué surveys están incluidos en la evaluación."""
        for evaluation in self:
            survey_codes = evaluation.survey_ids.mapped('survey_code')
            
            # Reset all flags
            for field_name in SURVEY_CODE_TO_FIELD.values():
                setattr(evaluation, field_name, False)
            
            # Set flags based on included surveys
            for survey_code in SURVEY_METRICS.keys():
                if survey_code in survey_codes:
                    field_name = SURVEY_CODE_TO_FIELD.get(survey_code)
                    if field_name:
                        setattr(evaluation, field_name, True)

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
        """Activar evaluación (scheduled -> active) y enviar emails de notificación"""
        self.write({'state': 'active'})
        self._send_activation_emails()
    
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
    
    def _send_activation_emails(self):
        """Envía emails de notificación a alumnos y tutores cuando se activa la evaluación"""
        for evaluation in self:
            pending_participations = evaluation.participation_ids.filtered(
                lambda p: p.state == 'pending'
            )
            
            # Enviar a alumnos
            self._send_student_emails(pending_participations)
            
            # Enviar a tutores
            self._send_tutor_emails(evaluation)
    
    def _send_tutor_emails(self, evaluation):
        """Envía emails a los tutores de los grupos asignados"""
        # Obtener todos los tutores (con y sin email para debugging)
        all_tutors = evaluation.academic_group_ids.mapped('tutor_id')
        tutors_with_email = all_tutors.filtered(lambda t: t and t.email)
        
        # Filtrar solo tutores con email
        tutors = tutors_with_email
        
        for tutor in tutors:
            tutor_groups = evaluation.academic_group_ids.filtered(lambda g: g.tutor_id == tutor)
            
            mail_values = {
                'subject': f'Evaluación activada para sus grupos: {evaluation.name}',
                'body_html': self._get_tutor_email_body(evaluation, tutor, tutor_groups),
                'email_to': tutor.email,
                'email_from': self._get_email_from(evaluation),
            }
            self._send_mail(mail_values, tutor.email)
    
    def _send_student_emails(self, participations):
        """Envía emails a los alumnos con su enlace de acceso personalizado"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
        
        valid_participations = participations.filtered(lambda p: p.student_id.email)
        
        for participation in valid_participations:
            evaluation = participation.evaluation_id
            
            mail_values = {
                'subject': f'Tienes una nueva evaluación: {evaluation.name}',
                'body_html': self._get_student_email_body(participation, base_url),
                'email_to': participation.student_id.email,
                'email_from': self._get_email_from(evaluation),
            }
            self._send_mail(mail_values, participation.student_id.email)
    
    def _get_student_email_body(self, participation, base_url):
        """Genera el HTML del email para el alumno"""
        evaluation = participation.evaluation_id
        evaluation_url = f"{base_url}/evaluacion/{participation.evaluation_token}"
        
        return f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">¡Evaluación Activada!</h2>
    <p>Hola <strong>{participation.student_id.name}</strong>,</p>
    <p>Se ha activado la evaluación <strong>"{evaluation.name}"</strong> en el sistema AulaMetrics.</p>
    <p><strong>Detalles de la evaluación:</strong></p>
    <ul>
        <li><strong>Nombre:</strong> {evaluation.name}</li>
        <li><strong>Fecha de inicio:</strong> {evaluation.date_start}</li>
        <li><strong>Fecha de expiración:</strong> {evaluation.date_end}</li>
        <li><strong>Cuestionarios incluidos:</strong> {', '.join(evaluation.survey_ids.mapped('title'))}</li>
    </ul>
    <p>Para participar en la evaluación, haz clic en el siguiente enlace:</p>
    <p style="text-align: center; margin: 30px 0;">
        <a href="{evaluation_url}"
           style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
            Acceder a la Evaluación
        </a>
    </p>
    <p><em>Este enlace es personal e intransferible. La evaluación estará disponible hasta la fecha de expiración.</em></p>
    <p>Si tienes alguna duda, contacta con tu profesor o coordinador.</p>
    <p>¡Gracias por tu participación!</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="font-size: 12px; color: #666;">
        Este es un mensaje automático del sistema AulaMetrics.
    </p>
</div>
"""
    
    def _get_tutor_email_body(self, evaluation, tutor, tutor_groups):
        """Genera el HTML del email para el tutor"""
        group_names = ', '.join(tutor_groups.mapped('name'))
        
        return f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">Evaluación Activada</h2>
    <p>Hola <strong>{tutor.name}</strong>,</p>
    <p>Se ha activado la evaluación <strong>"{evaluation.name}"</strong> para los siguientes grupos a su cargo:</p>
    <p><strong>Grupos afectados:</strong> {group_names}</p>
    <p><strong>Detalles de la evaluación:</strong></p>
    <ul>
        <li><strong>Fecha de inicio:</strong> {evaluation.date_start}</li>
        <li><strong>Fecha de expiración:</strong> {evaluation.date_end}</li>
        <li><strong>Cuestionarios incluidos:</strong> {', '.join(evaluation.survey_ids.mapped('title'))}</li>
        <li><strong>Número de alumnos:</strong> {evaluation.total_students}</li>
    </ul>
    <p>Le recomendamos informar a sus alumnos sobre esta evaluación y recordarles que participen antes de la fecha límite.</p>
    <p>Puede seguir el progreso de la evaluación desde el sistema AulaMetrics.</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="font-size: 12px; color: #666;">
        Este es un mensaje automático del sistema AulaMetrics.
    </p>
</div>
"""
    
    def _get_email_from(self, evaluation):
        """Obtiene el email remitente (del usuario o por defecto)"""
        return evaluation.user_id.email or 'noreply@aulametrics.com'
    
    def _send_mail(self, mail_values, recipient_email):
        """Envía un email y maneja errores silenciosamente"""
        try:
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
        except Exception as e:
            pass
    
    def action_close(self):
        """Cerrar evaluación (active -> closed)"""
        self.write({'state': 'closed'})
        # Marcar participaciones pendientes como expiradas
        for evaluation in self:
            evaluation.participation_ids.filtered(lambda p: p.state == 'pending').action_expire()
    
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
    
    # Método automático para actualizar estados basado en fechas
    @api.model
    def auto_update_evaluation_states(self):
        """Método que se ejecuta automáticamente para actualizar estados de evaluaciones
        basado en las fechas de inicio y fin"""
        now = fields.Datetime.now()
        
        # 1. Activar evaluaciones programadas que han llegado a su fecha de inicio
        scheduled_evaluations = self.search([
            ('state', '=', 'scheduled'),
            ('date_start', '<=', now)
        ])
        
        for evaluation in scheduled_evaluations:
            evaluation.action_activate()
        
        # 2. Cerrar evaluaciones activas que han expirado
        active_evaluations = self.search([
            ('state', '=', 'active'),
            ('date_end', '<=', now)
        ])
        
        for evaluation in active_evaluations:
            evaluation.action_close()