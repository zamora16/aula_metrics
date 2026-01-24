# -*- coding: utf-8 -*-
from odoo import models, fields, api

class Alert(models.Model):
    _name = 'aulametrics.alert'
    _description = 'Alerta de AulaMetrics'
    _order = 'alert_date desc'
    
    name = fields.Char(string='Título', compute='_compute_name')
    threshold_id = fields.Many2one('aulametrics.threshold', string='Umbral', required=True, ondelete='cascade')
    participation_id = fields.Many2one('aulametrics.participation', string='Participación', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Alumno')
    academic_group_id = fields.Many2one('aulametrics.academic_group', string='Grupo Académico')
    score_value = fields.Float(string='Valor de Puntuación', required=True)
    alert_date = fields.Datetime(string='Fecha de Alerta', default=fields.Datetime.now)
    status = fields.Selection([
        ('active', 'Activa'),
        ('resolved', 'Resuelta'),
        ('dismissed', 'Descartada'),
    ], string='Estado', default='active', required=True)
    message = fields.Text(string='Mensaje', related='threshold_id.alert_message', readonly=True)
    alert_level = fields.Selection([
        ('individual', 'Individual'),
        ('group', 'Grupal'),
    ], string='Nivel de Alerta', default='individual', required=True)
    severity = fields.Selection(related='threshold_id.severity', string='Severidad', readonly=True, store=True)
    
    # Campos de resolución
    resolution_action = fields.Text(
        string='Acción de Resolución',
        help='Descripción de la intervención o acción tomada para resolver la alerta'
    )
    resolution_date = fields.Datetime(
        string='Fecha de Resolución',
        readonly=True,
        help='Fecha y hora en que se resolvió la alerta'
    )
    
    def _compute_name(self):
        for alert in self:
            can_see_student = self.env.user.has_group('aulametrics.group_aulametrics_admin') or self.env.user.has_group('aulametrics.group_aulametrics_counselor')
            if alert.alert_level == 'group':
                alert.name = f"{alert.threshold_id.name} - Grupo {alert.academic_group_id.name}"
            else:
                if can_see_student and alert.student_id:
                    alert.name = f"{alert.threshold_id.name} - {alert.student_id.name}"
                else:
                    alert.name = f"{alert.threshold_id.name} - Alerta Individual"
    
    @api.model
    def check_alerts_for_participation(self, participation):
        """
        Verifica si las puntuaciones de una participación superan algún umbral activo.
        Se llama en tiempo real cada vez que se completa un cuestionario.
        """
        # Buscar umbrales activos relevantes para los cuestionarios de esta evaluación
        thresholds = self.env['aulametrics.threshold'].search([
            ('active', '=', True),
            ('survey_id', 'in', participation.evaluation_id.survey_ids.ids)
        ])
        
        for threshold in thresholds:
            # Obtener el valor de la puntuación usando el nombre del campo definido en el umbral
            score_value = getattr(participation, threshold.score_field, 0)
            if not score_value:
                continue
            
            # Comprobar condición individual
            is_alert = False
            if threshold.operator == '>' and score_value > threshold.threshold_value:
                is_alert = True
            elif threshold.operator == '<' and score_value < threshold.threshold_value:
                is_alert = True
                
            if is_alert:
                # Crear alerta individual
                self._create_alert(participation, threshold, score_value, 'individual')
        
        # Verificar alertas grupales después de procesar todas las individuales
        self._check_all_group_alerts(participation)
    
    def _check_group_alert(self, threshold, group):
        """Verifica y genera alerta grupal si corresponde"""
        if not threshold.group_threshold_percentage:
            return
            
        # Contar alertas activas individuales en este grupo para este umbral
        active_alerts = self.search_count([
            ('threshold_id', '=', threshold.id),
            ('academic_group_id', '=', group.id),
            ('status', '=', 'active'),
            ('alert_level', '=', 'individual')
        ])
        
        total_students = group.student_count or len(group.student_ids)
        if total_students == 0:
            return
        
        percentage = (active_alerts / total_students) * 100
        
        if percentage >= threshold.group_threshold_percentage:
            # Crear alerta grupal si no existe
            existing_group_alert = self.search([
                ('threshold_id', '=', threshold.id),
                ('academic_group_id', '=', group.id),
                ('alert_level', '=', 'group'),
                ('status', '=', 'active')
            ], limit=1)
            
            if not existing_group_alert:
                self.create({
                    'threshold_id': threshold.id,
                    'academic_group_id': group.id,
                    'score_value': percentage,
                    'alert_level': 'group',
                })
    
    def _check_all_group_alerts(self, participation):
        """Verifica y genera alertas grupales para todos los umbrales relevantes en una sola operación"""
        group = participation.student_id.academic_group_id
        thresholds = self.env['aulametrics.threshold'].search([
            ('active', '=', True),
            ('survey_id', 'in', participation.evaluation_id.survey_ids.ids),
            ('group_threshold_percentage', '>', 0)
        ])
        if not thresholds:
            return
        
        # Obtener conteos de alertas activas individuales por threshold en este grupo
        domain = [
            ('threshold_id', 'in', thresholds.ids),
            ('academic_group_id', '=', group.id),
            ('status', '=', 'active'),
            ('alert_level', '=', 'individual')
        ]
        grouped = self.read_group(domain, ['threshold_id'], ['threshold_id'])
        counts = {g['threshold_id'][0]: g['threshold_id_count'] for g in grouped}
        
        total_students = group.student_count or len(group.student_ids)
        if total_students == 0:
            return
        
        for threshold in thresholds:
            active_alerts = counts.get(threshold.id, 0)
            percentage = (active_alerts / total_students) * 100
            if percentage >= threshold.group_threshold_percentage:
                # Verificar si ya existe alerta grupal
                existing = self.search([
                    ('threshold_id', '=', threshold.id),
                    ('academic_group_id', '=', group.id),
                    ('alert_level', '=', 'group'),
                    ('status', '=', 'active')
                ], limit=1)
                if not existing:
                    self.create({
                        'threshold_id': threshold.id,
                        'academic_group_id': group.id,
                        'score_value': percentage,
                        'alert_level': 'group',
                    })
    
    def _create_alert(self, participation, threshold, score_value, alert_level='individual'):
        """Crea alerta si no existe ya"""
        domain = [('threshold_id', '=', threshold.id), ('alert_level', '=', alert_level)]
        if alert_level == 'individual':
            domain.append(('participation_id', '=', participation.id))
        else:
            domain.append(('academic_group_id', '=', participation.student_id.academic_group_id.id))
        
        existing = self.search(domain)
        if not existing:
            vals = {
                'threshold_id': threshold.id,
                'score_value': score_value,
                'alert_level': alert_level,
            }
            if alert_level == 'individual':
                vals['participation_id'] = participation.id
                vals['student_id'] = participation.student_id.id
                vals['academic_group_id'] = participation.student_id.academic_group_id.id
            else:
                vals['academic_group_id'] = participation.student_id.academic_group_id.id
            
            self.create(vals)

    def action_resolve(self):
        """Abrir wizard para registrar la acción tomada y resolver la alerta"""
        self.ensure_one()
        
        return {
            'name': 'Resolver Alerta',
            'type': 'ir.actions.act_window',
            'res_model': 'aulametrics.resolve_alert_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_alert_id': self.id,
            }
        }

    def action_dismiss(self):
        """Descartar alerta"""
        for alert in self:
            alert.status = 'dismissed'