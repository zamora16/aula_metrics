# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class ManualAlertWizard(models.TransientModel):
    _name = 'aula_metrics.manual_alert_wizard'
    _description = 'Wizard: Notificar al Orientador'

    def _check_only_tutor_access(self):
        """Los orientadores y admins gestionan casos y alertas directamente.
        Este wizard es exclusivo para tutores que quieren derivar una situación al orientador.
        """
        user = self.env.user
        is_counselor = user.has_group('aula_metrics.group_aulametrics_counselor')
        is_admin = user.has_group('aula_metrics.group_aulametrics_admin')
        if is_counselor or is_admin:
            raise UserError(
                'Esta función está pensada para tutores.\n\n'
                'Como orientador o administrador puedes crear casos de orientación '
                'directamente desde el menú Orientación → Casos de Orientación.'
            )

    @api.model
    def default_get(self, fields_list):
        """Bloquear acceso a orientadores y admins en el momento de abrir el wizard."""
        self._check_only_tutor_access()
        return super().default_get(fields_list)

    student_id = fields.Many2one(
        'res.partner',
        string='Alumno',
        required=True,
        domain="[('is_student', '=', True)]",
        help='Selecciona el alumno sobre el que quieres notificar al orientador',
    )
    academic_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo',
        related='student_id.academic_group_id',
        readonly=True,
    )
    description = fields.Text(
        string='Descripción de la situación',
        required=True,
        help='Describe brevemente la situación observada que deseas comunicar al orientador',
    )
    severity = fields.Selection(
        [
            ('low', 'Baja — Merece atención pero no es urgente'),
            ('moderate', 'Moderada — Requiere seguimiento pronto'),
            ('high', 'Alta — Situación urgente'),
        ],
        string='Severidad',
        required=True,
        default='moderate',
    )

    @api.constrains('student_id')
    def _check_student_belongs_to_tutor(self):
        """Un tutor solo puede notificar sobre alumnos de sus grupos.
        Orientadores y admins pueden notificar sobre cualquier alumno.
        """
        tutor_group = self.env.ref('aula_metrics.group_aulametrics_tutor')
        counselor_group = self.env.ref('aula_metrics.group_aulametrics_counselor')
        admin_group = self.env.ref('aula_metrics.group_aulametrics_admin')
        user = self.env.user
        # Orientadores y admins no tienen restricción
        if user in counselor_group.users or user in admin_group.users:
            return
        # Tutores: verificar que el alumno pertenece a uno de sus grupos
        if user in tutor_group.users:
            for wiz in self:
                if wiz.student_id.academic_group_id.tutor_id != user:
                    raise ValidationError(
                        f'Solo puedes notificar sobre alumnos de tus grupos asignados. '
                        f'{wiz.student_id.name} no pertenece a ninguno de tus grupos.'
                    )

    @api.constrains('description')
    def _check_description(self):
        for wiz in self:
            if not wiz.description or len(wiz.description.strip()) < 10:
                raise ValidationError(
                    'Por favor, describe la situación con al menos 10 caracteres '
                    'para que el orientador tenga contexto suficiente.'
                )

    def action_confirm(self):
        """Crea la alerta manual y su caso de orientación asociado.
        Solo para uso de tutores; orientadores y admins crean casos directamente.
        """
        self.ensure_one()
        if (self.env.user.has_group('aula_metrics.group_aulametrics_counselor')
                or self.env.user.has_group('aula_metrics.group_aulametrics_admin')):
            raise UserError(
                'Esta función está pensada para tutores.\n\n'
                'Como orientador o administrador puedes crear casos de orientación '
                'directamente desde el menú Orientación → Casos de Orientación.'
            )

        # Crear la alerta con sudo para que el tutor no necesite permisos directos
        alert = self.env['aula_metrics.alert'].sudo().create({
            'is_manual': True,
            'student_id': self.student_id.id,
            'academic_group_id': self.student_id.academic_group_id.id,
            'manual_description': self.description,
            'alert_level': 'individual',
            'status': 'active',
            'score_value': 0.0,
        })

        # Asignar severidad directamente después de crear
        # (el compute no la sobreescribe porque is_manual=True)
        alert.write({'severity': self.severity})

        # Crear el caso de orientación y marcar la alerta como en_gestion
        self.env['aula_metrics.case'].sudo().create_from_alert(alert)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Notificación enviada',
                'message': (
                    f'La situación de {self.student_id.name} ha sido comunicada al orientador. '
                    'Se ha abierto un caso de seguimiento.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
