# -*- coding: utf-8 -*-
from odoo import models, fields, api

class Alert(models.Model):
    _name = 'aulametrics.alert'
    _description = 'Alerta de AulaMetrics'
    _order = 'alert_date desc'
    
    name = fields.Char(string='Título', compute='_compute_name', store=True)
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
    notes = fields.Text(string='Notas del Orientador', help='Notas privadas del orientador sobre esta alerta')
    def _compute_name(self):
        for alert in self:
            if alert.alert_level == 'group':
                alert.name = f"{alert.threshold_id.name} - Grupo {alert.academic_group_id.name}"
            else:
                alert.name = f"{alert.threshold_id.name} - {alert.student_id.name}"
    
    @api.model
    def generate_alerts(self):
        """Genera alertas para participaciones que superan umbrales activos"""
        from datetime import timedelta
        
        # Buscar umbrales activos
        thresholds = self.env['aulametrics.threshold'].search([('active', '=', True)])
        
        for threshold in thresholds:
            # Buscar participaciones completadas recientes (últimas 24h) que usen este survey
            recent_participations = self.env['aulametrics.participation'].search([
                ('evaluation_id.survey_ids', 'in', [threshold.survey_id.id]),
                ('state', '=', 'completed'),
                ('completed_at', '>=', fields.Datetime.now() - timedelta(hours=24))
            ])
            
            # Generar alertas individuales
            for participation in recent_participations:
                score_value = getattr(participation, threshold.score_field, 0)
                if not score_value:
                    continue
                
                if threshold.operator == '>' and score_value > threshold.threshold_value:
                    self._create_alert(participation, threshold, score_value, 'individual')
                elif threshold.operator == '<' and score_value < threshold.threshold_value:
                    self._create_alert(participation, threshold, score_value, 'individual')
            
            # Generar alertas grupales
            self._generate_group_alerts(threshold, recent_participations)
    
    def _generate_group_alerts(self, threshold, participations):
        """Genera alertas grupales si supera el porcentaje"""
        if not threshold.group_threshold_percentage:
            return
        
        # Agrupar participaciones por grupo
        groups = {}
        for part in participations:
            group_id = part.student_id.academic_group_id.id
            if group_id not in groups:
                groups[group_id] = {'group': part.student_id.academic_group_id, 'participations': []}
            groups[group_id]['participations'].append(part)
        
        for group_data in groups.values():
            group = group_data['group']
            parts = group_data['participations']
            
            # Contar alertas activas individuales en este grupo para este umbral
            active_alerts = self.search([
                ('threshold_id', '=', threshold.id),
                ('academic_group_id', '=', group.id),
                ('status', '=', 'active'),
                ('alert_level', '=', 'individual')
            ])
            
            total_students = group.student_count or len(group.student_ids)
            if total_students == 0:
                continue
            
            percentage = (len(active_alerts) / total_students) * 100
            
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
        """Marcar alerta como resuelta"""
        for alert in self:
            alert.status = 'resolved'

    def action_dismiss(self):
        """Descartar alerta"""
        for alert in self:
            alert.status = 'dismissed'

    def action_reactivate(self):
        """Reactivar alerta"""
        for alert in self:
            alert.status = 'active'