# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api


class Case(models.Model):
    _name = 'aula_metrics.case'
    _description = 'Caso de Orientación Escolar'
    _order = 'open_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ── Identificación ──────────────────────────────────────────────────────
    name = fields.Char(
        string='Título del Caso',
        required=True,
        tracking=True,
    )

    # ── Relaciones principales ───────────────────────────────────────────────
    student_id = fields.Many2one(
        'res.partner',
        string='Alumno',
        required=True,
        index=True,
        tracking=True,
    )
    alert_id = fields.Many2one(
        'aula_metrics.alert',
        string='Alerta Asociada',
        ondelete='set null',
        help='Alerta que originó este caso (opcional)',
    )
    stage_id = fields.Many2one(
        'aula_metrics.case.stage',
        string='Fase',
        index=True,
        tracking=True,
        group_expand='_read_group_stage_ids',
        default=lambda self: self._default_stage(),
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
    )
    academic_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo Académico',
        store=True,
        readonly=True,
        ondelete='set null',
        help='Grupo del alumno cuando se abrió el caso (dato histórico, no cambia al cambiar de curso).'
    )
    academic_year_id = fields.Many2one(
        'aula_metrics.academic_year',
        string='Curso Académico',
        store=True,
        readonly=True,
        index=True,
        ondelete='set null',
        help='Curso académico cuando se abrió el caso (dato histórico).'
    )

    # ── Fechas ───────────────────────────────────────────────────────────────
    open_date = fields.Date(
        string='Fecha de Apertura',
        default=fields.Date.today,
        required=True,
    )
    close_date = fields.Date(
        string='Fecha de Cierre',
        tracking=True,
    )

    # ── Contenido ────────────────────────────────────────────────────────────
    description = fields.Html(
        string='Motivo de Apertura',
        help='Contexto inicial del caso y motivo de apertura',
        sanitize=True,
    )
    intervention_plan = fields.Html(
        string='Plan de Intervención',
        help='Pasos planificados de intervención por el orientador',
        sanitize=True,
    )

    # ── Estado calculado ─────────────────────────────────────────────────────
    is_closed = fields.Boolean(
        string='Cerrado',
        compute='_compute_is_closed',
        store=True,
    )
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgente')],
        string='Prioridad',
        default='0',
    )
    color = fields.Integer(string='Color', related='stage_id.color', store=False)
    kanban_state = fields.Selection(
        [
            ('normal', 'En Curso'),
            ('done', 'Listo para Avanzar'),
            ('blocked', 'Bloqueado'),
        ],
        string='Estado Kanban',
        default='normal',
        tracking=True,
    )

    # ── Computed helpers ─────────────────────────────────────────────────────
    @api.depends('stage_id.is_final')
    def _compute_is_closed(self):
        for case in self:
            case.is_closed = bool(case.stage_id and case.stage_id.is_final)

    @api.model
    def _default_stage(self):
        """Devuelve la primera fase disponible (menor secuencia)."""
        return self.env['aula_metrics.case.stage'].search(
            [], order='sequence, id', limit=1
        )

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Hace que todas las fases aparezcan en el Kanban aunque estén vacías."""
        return stages.search([], order=order)

    # ── ORM overrides ─────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        # Congelar el grupo académico y el curso del alumno en el momento de abrir el caso.
        # Si el alumno cambia de grupo al año siguiente, el caso sigue mostrado
        # en el grupo y curso en que ocurrió, preservando el historial correcto.
        for vals in vals_list:
            if 'academic_group_id' not in vals and vals.get('student_id'):
                student = self.env['res.partner'].browse(vals['student_id'])
                vals['academic_group_id'] = student.academic_group_id.id or False
            if 'academic_year_id' not in vals:
                group_id = vals.get('academic_group_id')
                if not group_id and vals.get('student_id'):
                    student = self.env['res.partner'].browse(vals['student_id'])
                    group_id = student.academic_group_id.id or False
                if group_id:
                    group = self.env['aula_metrics.academic_group'].browse(group_id)
                    vals['academic_year_id'] = group.academic_year_id.id or False
        records = super().create(vals_list)
        for record in records:
            # Registrar en chatter el motivo de apertura con un mensaje interno
            if record.description:
                record.message_post(
                    body=Markup('<b>Caso abierto.</b><br/>') + Markup(record.description),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
        return records

    def write(self, vals):
        # Registrar automáticamente la fecha de cierre al moverse a fase final
        if 'stage_id' in vals:
            stage = self.env['aula_metrics.case.stage'].browse(vals['stage_id'])
            if stage.is_final:
                vals.setdefault('close_date', fields.Date.today())
            else:
                # Si se saca de fase final, limpiar fecha de cierre
                vals['close_date'] = False
        result = super().write(vals)
        # Sincronizar estado de la alerta vinculada cuando cambia la fase del caso:
        #   · Screening (primera fase) → alerta 'active'   (pendiente de atender)
        #   · Seguimiento / Intervención → alerta 'en_gestion' (siendo atendida)
        #   · Cerrado (fase final) → alerta 'resolved'     (caso cerrado)
        if 'stage_id' in vals:
            stage = self.env['aula_metrics.case.stage'].browse(vals['stage_id'])
            first_stage = self.env['aula_metrics.case.stage'].search(
                [('is_final', '=', False)], order='sequence, id', limit=1
            )
            for case in self:
                if not case.alert_id:
                    continue
                if stage.is_final:
                    new_status = 'resolved'
                elif stage.id == first_stage.id:
                    new_status = 'active'
                else:
                    new_status = 'en_gestion'
                if case.alert_id.status != new_status:
                    update = {'status': new_status}
                    if new_status == 'resolved':
                        update['resolution_date'] = fields.Datetime.now()
                        update['resolution_action'] = (
                            f'Caso cerrado el {fields.Date.today()}.'
                        )
                    elif new_status == 'active':
                        # Al volver a screening limpiar la resolución anterior
                        update['resolution_date'] = False
                        update['resolution_action'] = False
                    case.alert_id.sudo().write(update)
        return result

    # ── Acciones de botón ─────────────────────────────────────────────────────
    def action_close_case(self):
        """Mueve el caso a la fase final marcada como cierre.
        Al cerrar el caso, resuelve automáticamente la alerta vinculada.
        """
        final_stage = self.env['aula_metrics.case.stage'].search(
            [('is_final', '=', True)], order='sequence, id', limit=1
        )
        if not final_stage:
            final_stage = self.env['aula_metrics.case.stage'].create({
                'name': 'Cerrado',
                'sequence': 99,
                'is_final': True,
                'fold': True,
                'color': 2,
            })
        self.write({'stage_id': final_stage.id})

    def action_reopen_case(self):
        """Mueve el caso de vuelta a la primera fase no final.
        Al reabrir el caso, reactiva la alerta vinculada a 'en gestión'.
        """
        first_stage = self.env['aula_metrics.case.stage'].search(
            [('is_final', '=', False)], order='sequence, id', limit=1
        )
        if first_stage:
            self.write({'stage_id': first_stage.id})

    def action_view_alert(self):
        """Abre la alerta vinculada."""
        self.ensure_one()
        if not self.alert_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'aula_metrics.alert',
            'res_id': self.alert_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Método de fábrica ─────────────────────────────────────────────────────
    @api.model
    def create_from_alert(self, alert):
        """Crea un caso de orientación a partir de una alerta.
        
        Se llama automáticamente cuando se genera una alerta relevante.
        Evita duplicados para la misma alerta.
        
        :param alert: registro de aula_metrics.alert
        :return: caso creado o existente
        """
        # Evitar duplicados
        existing = self.search([('alert_id', '=', alert.id)], limit=1)
        if existing:
            return existing

        # Obtener fase inicial (primera fase en secuencia)
        initial_stage = self.env['aula_metrics.case.stage'].search(
            [('is_final', '=', False)], order='sequence, id', limit=1
        )

        student = alert.student_id
        name_parts = []
        if student:
            name_parts.append(student.name)
        if alert.is_manual:
            name_parts.append('Notificación del Tutor')
        elif alert.threshold_id:
            name_parts.append(alert.threshold_id.name)
        elif alert.qualitative_response_id:
            name_parts.append('Alerta Cualitativa')
        case_name = ' - '.join(name_parts) if name_parts else 'Nuevo Caso'

        # Crear el caso en el contexto del usuario sistema para que todos los
        # mensajes del chatter (tracking "creado" + nota de apertura) aparezcan
        # con el nombre "AulaMetrics" en lugar del usuario que disparó el flujo.
        system_user = self.env.ref('aula_metrics.user_aulametrics_system', raise_if_not_found=False)
        create_self = self.with_user(system_user).sudo() if system_user else self

        return create_self.create({
            'name': case_name,
            'student_id': student.id if student else False,
            'alert_id': alert.id,
            'stage_id': initial_stage.id if initial_stage else False,
            'description': alert.message or '',
        })
