# -*- coding: utf-8 -*-
import logging
from markupsafe import escape
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)

class Evaluation(models.Model):
    """Evaluación Programada - Asignación de cuestionarios a grupos académicos"""
    _name = 'aula_metrics.evaluation'
    _table = 'aulametrics_evaluation'
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
    
    # Curso académico al que pertenece esta evaluación
    academic_year_id = fields.Many2one(
        'aula_metrics.academic_year',
        string='Curso Académico',
        index=True,
        ondelete='restrict',
        default=lambda self: self.env['aula_metrics.academic_year']._get_default_year(),
        help='Curso académico de referencia para esta evaluación'
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
        'aula_metrics.academic_group',
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
        """Crear evaluación"""
        evaluations = super().create(vals_list)
        return evaluations
    
    def copy(self, default=None):
        """Al duplicar, agregar sufijo al nombre para evitar conflictos"""
        self.ensure_one()
        if default is None:
            default = {}
        
        if 'name' not in default:
            # Buscar un nombre único agregando sufijo
            base_name = self.name
            counter = 1
            new_name = f"{base_name} (Copia)"
            
            # Si ya existe, incrementar contador
            while self.search([('name', '=', new_name)], limit=1):
                counter += 1
                new_name = f"{base_name} (Copia {counter})"
            
            default['name'] = new_name
        
        # Resetear estado a borrador al duplicar
        if 'state' not in default:
            default['state'] = 'draft'
        
        return super().copy(default)
    
    participation_rate = fields.Float(
        string='Tasa de Participación (%)',
        compute='_compute_participation_metrics',
        store=True,
        help='Porcentaje de alumnos que han completado'
    )
    
    # Relación con participaciones
    participation_ids = fields.One2many(
        'aula_metrics.participation',
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
        """Activar evaluación (scheduled -> active) y enviar emails de notificación"""
        self.ensure_one()
        now = fields.Datetime.now()
        # Si se activa antes de la fecha de inicio programada, adelantar date_start
        # a ahora para que los filtros temporales sean siempre consistentes.
        vals = {'state': 'active'}
        if self.date_start > now:
            vals['date_start'] = now
        self.write(vals)
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
        tutors = evaluation.academic_group_ids.mapped('tutor_id').filtered(lambda t: t and t.email)
        
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
        student_name = escape(participation.student_id.name or '')
        eval_name = escape(evaluation.name or '')
        date_start = escape(str(evaluation.date_start or ''))
        date_end = escape(str(evaluation.date_end or ''))
        surveys = escape(', '.join(evaluation.survey_ids.mapped('title')))

        return f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">¡Evaluación Activada!</h2>
    <p>Hola <strong>{student_name}</strong>,</p>
    <p>Se ha activado la evaluación <strong>"{eval_name}"</strong> en el sistema AulaMetrics.</p>
    <p><strong>Detalles de la evaluación:</strong></p>
    <ul>
        <li><strong>Nombre:</strong> {eval_name}</li>
        <li><strong>Fecha de inicio:</strong> {date_start}</li>
        <li><strong>Fecha de expiración:</strong> {date_end}</li>
        <li><strong>Cuestionarios incluidos:</strong> {surveys}</li>
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
        tutor_name = escape(tutor.name or '')
        eval_name = escape(evaluation.name or '')
        group_names = escape(', '.join(tutor_groups.mapped('name')))
        date_start = escape(str(evaluation.date_start or ''))
        date_end = escape(str(evaluation.date_end or ''))
        surveys = escape(', '.join(evaluation.survey_ids.mapped('title')))

        return f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">Evaluación Activada</h2>
    <p>Hola <strong>{tutor_name}</strong>,</p>
    <p>Se ha activado la evaluación <strong>"{eval_name}"</strong> para los siguientes grupos a su cargo:</p>
    <p><strong>Grupos afectados:</strong> {group_names}</p>
    <p><strong>Detalles de la evaluación:</strong></p>
    <ul>
        <li><strong>Fecha de inicio:</strong> {date_start}</li>
        <li><strong>Fecha de expiración:</strong> {date_end}</li>
        <li><strong>Cuestionarios incluidos:</strong> {surveys}</li>
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
        """Obtiene el email remitente: del usuario responsable o del parámetro de sistema.
        Configurable en Ajustes técnicos → Parámetros → aula_metrics.default_from_email
        """
        return (
            evaluation.user_id.email
            or self.env['ir.config_parameter'].sudo().get_param(
                'aula_metrics.default_from_email',
                'noreply@example.com',
            )
        )
    
    def _send_mail(self, mail_values, recipient_email):
        """Envía un email y maneja errores silenciosamente"""
        try:
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
        except Exception as e:
            _logger.error('Error enviando email a %s: %s', recipient_email, e, exc_info=True)
    
    def action_close(self):
        """Cerrar evaluación (active -> closed)"""
        self.write({'state': 'closed'})
        for evaluation in self:
            evaluation.participation_ids.filtered(lambda p: p.state == 'pending').action_expire()
            try:
                evaluation._send_closure_emails()
            except Exception as e:
                _logger.error('Error enviando emails de cierre para evaluación %s: %s',
                              evaluation.id, e, exc_info=True)

    # ──────────────────────────────────────────────────────────────────────
    # Emails de cierre de evaluación
    # ──────────────────────────────────────────────────────────────────────

    def _send_closure_emails(self):
        """
        Envía informes PDF por email al cerrarse la evaluación, adaptados por rol:
          - Dirección     → datos solo por nivel educativo y centro
          - Orientadores  → datos completos (todos los grupos)
          - Tutores       → solo los grupos que tienen asignados

        Cada destinatario recibe un PDF generado con su capa de visibilidad propia.
        Los errores de PDF o de envío se capturan individualmente para no bloquear
        el cierre de la evaluación.
        """
        from ...utils.constants import ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR

        self.ensure_one()
        EvalReport = self.env['aula_metrics.dashboard.evaluation_report']
        eval_id    = self.id

        def _make_role_info(role, is_admin=False, is_counselor=False,
                            is_management=False, allowed_group_ids=None):
            return {
                'role':             role,
                'is_admin':         is_admin,
                'is_counselor':     is_counselor,
                'is_management':    is_management,
                'is_tutor':         True,
                'allowed_group_ids': allowed_group_ids or [],
                'anonymize_students': role == ROLE_MANAGEMENT,
            }

        def _generate_pdf(role_info):
            pdf_data = EvalReport.get_pdf_report_data(eval_id, role_info)
            if pdf_data is None:
                return None
            pdf_bytes, _ = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'aula_metrics.report_evaluation_pdf',
                [eval_id],
                data=pdf_data,
            )
            return pdf_bytes

        def _attach_pdf(pdf_bytes, filename):
            return self.env['ir.attachment'].create({
                'name':         filename,
                'type':         'binary',
                'datas':        __import__('base64').b64encode(pdf_bytes).decode(),
                'mimetype':     'application/pdf',
                'res_model':    'aula_metrics.evaluation',
                'res_id':       self.id,
            })

        def _send(subject, body_html, recipient_email, attachment_ids=None):
            vals = {
                'subject':          subject,
                'body_html':        body_html,
                'email_to':         recipient_email,
                'email_from':       self._get_email_from(self),
                'attachment_ids':   [(4, att.id) for att in (attachment_ids or [])],
            }
            self._send_mail(vals, recipient_email)

        eval_name    = escape(self.name or '')
        date_closed  = escape(fields.Date.today().strftime('%d/%m/%Y'))
        base_url     = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'http://localhost:8069'
        )
        informe_url  = f'{base_url}/aulametrics/evaluacion/{self.id}/informe'

        # ── 1. Dirección ─────────────────────────────────────────────────
        mgmt_group = self.env.ref('aula_metrics.group_aulametrics_management',
                                  raise_if_not_found=False)
        if mgmt_group:
            mgmt_role_info = _make_role_info(ROLE_MANAGEMENT, is_management=True)
            mgmt_pdf = None
            try:
                mgmt_pdf = _generate_pdf(mgmt_role_info)
            except Exception as e:
                _logger.error('PDF dirección eval %s: %s', self.id, e, exc_info=True)

            for user in mgmt_group.users.filtered(lambda u: u.email):
                try:
                    atts = []
                    if mgmt_pdf:
                        att = _attach_pdf(mgmt_pdf,
                                          f'informe_evaluacion_{self.id}_direccion.pdf')
                        atts.append(att)
                    _send(
                        subject=f'Evaluación cerrada: {self.name}',
                        body_html=self._get_closure_email_body(
                            user, eval_name, date_closed, informe_url,
                            'Dirección', nivel='nivel',
                        ),
                        recipient_email=user.email,
                        attachment_ids=atts,
                    )
                except Exception as e:
                    _logger.error('Email cierre dirección %s eval %s: %s',
                                  user.email, self.id, e, exc_info=True)

        # ── 2. Orientadores / Admin ───────────────────────────────────────
        counselor_group = self.env.ref('aula_metrics.group_aulametrics_counselor',
                                       raise_if_not_found=False)
        admin_group     = self.env.ref('aula_metrics.group_aulametrics_admin',
                                       raise_if_not_found=False)
        counselor_users = self.env['res.users'].browse()
        if counselor_group:
            counselor_users |= counselor_group.users
        if admin_group:
            counselor_users |= admin_group.users
        counselor_users = counselor_users.filtered(lambda u: u.email)

        if counselor_users:
            counselor_role_info = _make_role_info(
                ROLE_COUNSELOR, is_counselor=True,
            )
            counselor_pdf = None
            try:
                counselor_pdf = _generate_pdf(counselor_role_info)
            except Exception as e:
                _logger.error('PDF orientadores eval %s: %s', self.id, e, exc_info=True)

            for user in counselor_users:
                try:
                    atts = []
                    if counselor_pdf:
                        att = _attach_pdf(counselor_pdf,
                                          f'informe_evaluacion_{self.id}_orientador.pdf')
                        atts.append(att)
                    _send(
                        subject=f'Evaluación cerrada: {self.name}',
                        body_html=self._get_closure_email_body(
                            user, eval_name, date_closed, informe_url,
                            'Orientador',
                        ),
                        recipient_email=user.email,
                        attachment_ids=atts,
                    )
                except Exception as e:
                    _logger.error('Email cierre orientador %s eval %s: %s',
                                  user.email, self.id, e, exc_info=True)

        # ── 3. Tutores ────────────────────────────────────────────────────
        eval_group_ids = self.academic_group_ids.ids
        if not eval_group_ids:
            return

        tutors = self.academic_group_ids.mapped('tutor_id').filtered(
            lambda t: t and t.email
        )
        for tutor_user in tutors:
            tutor_groups = self.academic_group_ids.filtered(
                lambda g: g.tutor_id == tutor_user
            )
            tutor_role_info = _make_role_info(
                ROLE_TUTOR,
                allowed_group_ids=tutor_groups.ids,
            )
            try:
                tutor_pdf   = _generate_pdf(tutor_role_info)
                atts = []
                if tutor_pdf:
                    att = _attach_pdf(tutor_pdf,
                                      f'informe_evaluacion_{self.id}_tutor.pdf')
                    atts.append(att)
                group_names = escape(', '.join(tutor_groups.mapped('name')))
                _send(
                    subject=f'Evaluación cerrada: {self.name}',
                    body_html=self._get_closure_email_body(
                        tutor_user, eval_name, date_closed, informe_url,
                        'Tutor', group_names=group_names,
                    ),
                    recipient_email=tutor_user.email,
                    attachment_ids=atts,
                )
            except Exception as e:
                _logger.error('Email cierre tutor %s eval %s: %s',
                              tutor_user.email, self.id, e, exc_info=True)

    def _get_closure_email_body(self, user, eval_name, date_closed,
                                 informe_url, role_label,
                                 nivel='grupo', group_names=None):
        """Genera el HTML del email de cierre adaptado a cada tipo de destinatario."""
        user_name    = escape(user.name or '')
        surveys_list = escape(', '.join(self.survey_ids.mapped('title')))

        if group_names:
            group_line = f'<li><strong>Grupos:</strong> {group_names}</li>'
        else:
            group_line = ''

        return f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #1A5C52;">Evaluaci&#243;n Finalizada</h2>
    <p>Hola <strong>{user_name}</strong> ({role_label}),</p>
    <p>La evaluaci&#243;n <strong>&#8220;{eval_name}&#8221;</strong> ha finalizado el <strong>{date_closed}</strong>.</p>
    <p>Adjunto encontrar&#225;s el informe PDF con los resultados filtrados para tu perfil.</p>
    <ul>
        <li><strong>Cuestionarios:</strong> {surveys_list}</li>
        {group_line}
    </ul>
    <p style="text-align:center;margin:24px 0;">
        <a href="{informe_url}"
           style="background:#1A5C52;color:white;padding:10px 22px;text-decoration:none;border-radius:5px;display:inline-block;">
            Ver informe en l&#237;nea
        </a>
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
    <p style="font-size:12px;color:#666;">Mensaje autom&#225;tico del sistema AulaMetrics.</p>
</div>
"""
    
    def action_cancel(self):
        """Cancelar evaluación"""
        self.write({'state': 'cancelled'})
    
    def action_reset_to_draft(self):
        """Volver a borrador"""
        self.write({'state': 'draft'})
    
    def _create_participations(self):
        """Crea registros de participación para cada alumno de los grupos asignados"""
        self.ensure_one()
        Participation = self.env['aula_metrics.participation']

        # Todos los alumnos de todos los grupos (sin duplicados) — 2 queries en total
        all_students = self.academic_group_ids.student_ids
        if not all_students:
            return

        existing_student_ids = set(Participation.search([
            ('evaluation_id', '=', self.id),
            ('student_id', 'in', all_students.ids),
        ]).mapped('student_id').ids)

        vals_list = [
            {'evaluation_id': self.id, 'student_id': student.id, 'state': 'pending'}
            for student in all_students
            if student.id not in existing_student_ids
        ]
        if vals_list:
            Participation.create(vals_list)
    
    def action_recalculate_metrics(self):
        """
        Recalcula métricas y respuestas cualitativas para todas las participaciones
        de esta evaluación a partir de los user_input ya completados.
        Útil para regenerar datos cuando se repararon bugs de scoring.
        """
        self.ensure_one()
        if not self.env.user.has_group('aula_metrics.group_aulametrics_admin'):
            raise AccessError(_("Solo los administradores pueden recalcular métricas."))
        SurveyUserInput = self.env['survey.user_input']

        for participation in self.participation_ids:
            # 1. Recalcular métricas cuantitativas (metric_value)
            try:
                participation._calculate_scores()
            except Exception as e:
                _logger.error('Error recalculando scores para participación %s: %s', participation.id, e, exc_info=True)

            # 2. Regenerar respuestas cualitativas y de opción múltiple
            for survey in self.survey_ids:
                user_input = SurveyUserInput.search([
                    ('partner_id', '=', participation.student_id.id),
                    ('survey_id', '=', survey.id),
                    ('state', '=', 'done'),
                ], limit=1)
                if not user_input:
                    continue
                try:
                    user_input._save_qualitative_responses()
                except Exception as e:
                    _logger.error('Error guardando respuestas cualitativas para user_input %s: %s', user_input.id, e, exc_info=True)
                try:
                    user_input._save_multiplechoice_responses()
                except Exception as e:
                    _logger.error('Error guardando respuestas múltiple opción para user_input %s: %s', user_input.id, e, exc_info=True)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Métricas recalculadas',
                'message': 'Se han regenerado las métricas de todos los cuestionarios completados en esta evaluación.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_participations(self):
        """Acción para ver participaciones desde el smart button"""
        self.ensure_one()
        return {
            'name': 'Participaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'aula_metrics.participation',
            'view_mode': 'tree,form',
            'domain': [('evaluation_id', '=', self.id)],
            'context': {'default_evaluation_id': self.id},
        }
    
    @api.model
    def get_with_qualitative_questions(self, role_info):
        """
        Evaluaciones accesibles por el rol que contienen al menos una pregunta
        de texto libre (text_box o char_box).

        Sustituye el bucle N×M del controlador por 2 queries:
          1. Evaluaciones filtradas por rol.
          2. Cuestionarios con preguntas de texto libre.

        Args:
            role_info (dict): resultado de role_service.get_role_info().

        Returns:
            recordset de aula_metrics.evaluation (vacío si sin acceso).
        """
        from odoo.addons.aula_metrics.utils import role_service
        from odoo.addons.aula_metrics.utils.constants import EVAL_STATES_ACTIVE

        domain = role_service.apply_group_filter(
            [('state', 'in', EVAL_STATES_ACTIVE)],
            role_info,
            field='academic_group_ids',
        )
        if domain is None:
            return self.browse()

        all_evals = self.search(domain, order='date_start desc')
        if not all_evals:
            return self.browse()

        # Cuestionarios de todas las evaluaciones con preguntas de texto libre (1 query)
        all_survey_ids = all_evals.survey_ids.ids
        if not all_survey_ids:
            return self.browse()

        surveys_with_text = set(
            self.env['survey.question'].sudo().search([
                ('survey_id', 'in', all_survey_ids),
                ('question_type', 'in', ['text_box', 'char_box']),
            ]).mapped('survey_id').ids
        )

        return all_evals.filtered(
            lambda ev: bool(set(ev.survey_ids.ids) & surveys_with_text)
        )

    # Método automático para actualizar estados basado en fechas
    @api.model
    def auto_update_evaluation_states(self):
        """Método que se ejecuta automáticamente para actualizar estados de evaluaciones
        basado en las fechas de inicio y fin"""
        now = fields.Datetime.now()

        # 1. Activar evaluaciones programadas cuya fecha de inicio ya llegó
        #    y cuya fecha de fin todavía no ha pasado.
        scheduled_evaluations = self.search([
            ('state', '=', 'scheduled'),
            ('date_start', '<=', now),
            ('date_end', '>', now),
        ])

        for evaluation in scheduled_evaluations:
            evaluation.write({'state': 'active'})
            evaluation._send_activation_emails()

        # 2. Cerrar evaluaciones activas que han expirado
        active_evaluations = self.search([
            ('state', '=', 'active'),
            ('date_end', '<=', now)
        ])

        for evaluation in active_evaluations:
            evaluation.action_close()