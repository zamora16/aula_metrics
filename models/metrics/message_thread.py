# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from ...utils.constants import GROUP_ADMIN, GROUP_COUNSELOR, GROUP_MANAGEMENT, GROUP_TUTOR


class MessageThread(models.Model):
    _name = 'aula_metrics.message_thread'
    _description = 'Hilo de Comunicación Interna'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'write_date desc'

    # ── Campos principales ──────────────────────────────────────────────────

    name = fields.Char(
        string='Asunto',
        required=True,
        tracking=True,
    )
    description = fields.Html(
        string='Mensaje inicial',
        help='Contexto o mensaje inicial del hilo visible para todos los participantes',
    )
    participant_ids = fields.Many2many(
        'res.users',
        'aula_metrics_thread_participant_rel',
        'thread_id',
        'user_id',
        string='Participantes',
    )
    state = fields.Selection(
        [('open', 'Activo'), ('closed', 'Cerrado')],
        string='Estado',
        default='open',
        required=True,
        tracking=True,
    )
    creator_id = fields.Many2one(
        'res.users',
        string='Creado por',
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )

    # ── Campos calculados ───────────────────────────────────────────────────

    participant_count = fields.Integer(
        string='Nº participantes',
        compute='_compute_participant_count',
    )

    @api.depends('participant_ids')
    def _compute_participant_count(self):
        for rec in self:
            rec.participant_count = len(rec.participant_ids)

    # ── ORM overrides ───────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        # Auto-añadir al creador como participante si no está en la lista
        for vals in vals_list:
            creator_id = vals.get('creator_id') or self.env.user.id
            participant_ids = vals.get('participant_ids', [])
            # participant_ids es una lista de comandos (6, 0, [ids])
            if participant_ids and participant_ids[0][0] == 6:
                existing_ids = set(participant_ids[0][2])
            else:
                existing_ids = set()
            
            if creator_id not in existing_ids:
                existing_ids.add(creator_id)
                vals['participant_ids'] = [(6, 0, list(existing_ids))]
        
        threads = super().create(vals_list)
        for thread in threads:
            # Suscribir a todos los participantes como seguidores
            # → Odoo les enviará notificaciones automáticamente al haber nuevos mensajes
            partner_ids = thread.participant_ids.mapped('partner_id').ids
            thread.message_subscribe(partner_ids=partner_ids)
        return threads

    def write(self, vals):
        res = super().write(vals)
        # Sincronizar seguidores si cambian los participantes
        if 'participant_ids' in vals:
            for thread in self:
                partner_ids = thread.participant_ids.mapped('partner_id').ids
                thread.message_subscribe(partner_ids=partner_ids)
        return res

    # ── Acciones de botón ───────────────────────────────────────────────────

    def action_close(self):
        for thread in self:
            thread.message_post(
                body=Markup('<p>Hilo cerrado por <b>{}</b>.</p>').format(self.env.user.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'open'})

    # ── Constraints ─────────────────────────────────────────────────────────

    @api.constrains('participant_ids')
    def _check_participants(self):
        valid_groups = [
            GROUP_TUTOR,
            GROUP_COUNSELOR,
            GROUP_MANAGEMENT,
            GROUP_ADMIN,
        ]
        for thread in self:
            if len(thread.participant_ids) < 1:
                raise ValidationError(
                    'Un hilo de comunicación debe tener al menos 1 participante.'
                )
            for user in thread.participant_ids:
                if not any(user.has_group(g) for g in valid_groups):
                    raise ValidationError(
                        f'{user.name} no pertenece a ningún grupo de AulaMetrics '
                        f'y no puede participar en comunicaciones internas.'
                    )
