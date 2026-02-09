# -*- coding: utf-8 -*-
from odoo import models, fields, api
import re

class Alert(models.Model):
    _name = 'aulametrics.alert'
    _description = 'Alerta de AulaMetrics'
    _order = 'alert_date desc'
    
    name = fields.Char(string='Título', compute='_compute_name')
    threshold_id = fields.Many2one('aulametrics.threshold', string='Umbral', ondelete='cascade')
    participation_id = fields.Many2one('aulametrics.participation', string='Participación', ondelete='cascade')
    qualitative_response_id = fields.Many2one('aulametrics.qualitative_response', string='Respuesta Cualitativa', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Alumno')
    academic_group_id = fields.Many2one('aulametrics.academic_group', string='Grupo Académico')
    score_value = fields.Float(string='Valor de Puntuación', required=True)
    alert_date = fields.Datetime(string='Fecha de Alerta', default=fields.Datetime.now)
    status = fields.Selection([
        ('active', 'Activa'),
        ('resolved', 'Resuelta'),
        ('dismissed', 'Descartada'),
    ], string='Estado', default='active', required=True)
    message = fields.Text(string='Mensaje', compute='_compute_message', store=True)
    alert_level = fields.Selection([
        ('individual', 'Individual'),
        ('group', 'Grupal'),
    ], string='Nivel de Alerta', default='individual', required=True)
    alert_type = fields.Selection([
        ('quantitative', 'Cuantitativa'),
        ('qualitative', 'Cualitativa')
    ], string='Tipo de Alerta', compute='_compute_alert_type', store=True)
    severity = fields.Selection([
        ('low', 'Baja'),
        ('moderate', 'Moderada'),
        ('high', 'Alta')
    ], string='Severidad', compute='_compute_severity', store=True)
    
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
    
    # Campo computado para mostrar curso general (sin especificar A/B/C)
    course_level_general = fields.Char(
        string='Curso General',
        compute='_compute_course_level_general',
        store=False
    )
    
    def _compute_course_level_general(self):
        """Extrae solo el nivel de curso (Primero, Segundo...) sin la letra del grupo."""
        for alert in self:
            if alert.academic_group_id and alert.academic_group_id.course_level:
                course = alert.academic_group_id.course_level
                match = re.match(r'^(.*?)\s*[A-Z]?$', course)
                alert.course_level_general = match.group(1).strip() if match else course
            else:
                alert.course_level_general = 'Sin curso'
    
    @api.depends('qualitative_response_id', 'threshold_id')
    def _compute_alert_type(self):
        """Determina si la alerta es cuantitativa o cualitativa."""
        for alert in self:
            alert.alert_type = 'qualitative' if alert.qualitative_response_id else 'quantitative'
    
    @api.depends('threshold_id', 'qualitative_response_id')
    def _compute_severity(self):
        """Calcula severidad: desde threshold para cuantitativas, desde keywords para cualitativas."""
        for alert in self:
            if alert.qualitative_response_id and alert.qualitative_response_id.detected_keywords:
                # Alerta cualitativa: usar severidad más alta de keywords detectadas
                try:
                    import json
                    keywords_list = json.loads(alert.qualitative_response_id.detected_keywords or '[]')
                    
                    # Buscar keywords en BD para obtener sus severidades
                    keywords = self.env['aulametrics.alert_keyword'].search([
                        ('keyword', 'in', keywords_list),
                        ('active', '=', True)
                    ])
                    
                    if keywords:
                        # Ordenar por severidad (high > moderate > low)
                        severity_order = {'high': 3, 'moderate': 2, 'low': 1}
                        max_severity = max(keywords.mapped('severity'), 
                                         key=lambda s: severity_order.get(s, 0))
                        alert.severity = max_severity
                    else:
                        alert.severity = 'moderate'  # Default si no se encuentran keywords
                except:
                    alert.severity = 'moderate'
            elif alert.threshold_id:
                # Alerta cuantitativa: usar severidad del threshold
                alert.severity = alert.threshold_id.severity
            else:
                alert.severity = False
    
    @api.depends('threshold_id', 'qualitative_response_id')
    def _compute_message(self):
        """Computa el mensaje de alerta según el tipo."""
        for alert in self:
            if alert.qualitative_response_id:
                # Alerta cualitativa: mensaje personalizado con keywords
                try:
                    import json
                    keywords = json.loads(alert.qualitative_response_id.detected_keywords or '[]')
                    keywords_str = ', '.join(keywords)
                    alert.message = f"Se detectaron palabras de alerta en una respuesta cualitativa: {keywords_str}"
                except:
                    alert.message = "Se detectaron palabras de alerta en una respuesta cualitativa"
            elif alert.threshold_id:
                # Alerta cuantitativa: mensaje del threshold
                alert.message = alert.threshold_id.alert_message
            else:
                alert.message = False
    
    def _compute_name(self):
        """Computa el nombre de la alerta según permisos del usuario."""
        for alert in self:
            user = self.env.user
            is_counselor_or_admin = user.has_group('aulametrics.group_aulametrics_admin') or user.has_group('aulametrics.group_aulametrics_counselor')
            is_management = user.has_group('aulametrics.group_aulametrics_management')
            
            # Nombre base según tipo de alerta
            if alert.alert_type == 'qualitative':
                base_name = 'Alerta Cualitativa'
            else:
                base_name = alert.threshold_id.name if alert.threshold_id else 'Alerta'
            
            if alert.alert_level == 'group':
                # Alertas grupales
                if is_counselor_or_admin:
                    # Counselor/Admin: ven grupo específico (2A, 2B)
                    alert.name = f"{base_name} - Grupo {alert.academic_group_id.name}"
                elif is_management:
                    # Management: solo curso general sin letra del grupo
                    alert.name = f"{base_name} - Alerta Grupal ({alert.course_level_general})"
                else:
                    # Tutor: ve su grupo específico
                    alert.name = f"{base_name} - Grupo {alert.academic_group_id.name}"
            else:
                # Alertas individuales
                if is_counselor_or_admin and alert.student_id:
                    # Counselor/Admin: ven nombre del estudiante
                    alert.name = f"{base_name} - {alert.student_id.name}"
                elif is_management:
                    # Management: solo ven curso general sin grupo específico
                    alert.name = f"{base_name} - {alert.course_level_general}"
                else:
                    # Tutor: nombre genérico sin identificar
                    alert.name = f"{base_name} - Alerta Individual"
    
    @api.model
    def create_qualitative_alert(self, qualitative_response):
        """Crea alerta formal desde respuesta cualitativa con keywords."""
        if not qualitative_response.has_alert_keywords:
            return
        
        # Verificar si ya existe alerta para esta respuesta
        existing = self.search([
            ('qualitative_response_id', '=', qualitative_response.id),
            ('status', '=', 'active')
        ], limit=1)
        
        if existing:
            return existing
        
        # Contar keywords como score_value
        try:
            import json
            keywords = json.loads(qualitative_response.detected_keywords or '[]')
            score_value = float(len(keywords))
        except:
            score_value = 1.0
        
        # Crear alerta SIN threshold (severity se calculará desde keywords)
        alert = self.create({
            'qualitative_response_id': qualitative_response.id,
            'student_id': qualitative_response.student_id.id,
            'academic_group_id': qualitative_response.academic_group_id.id,
            'threshold_id': False,  # No usar threshold
            'score_value': score_value,
            'alert_level': 'individual',
            'status': 'active',
        })
        
        return alert
    
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
            # Obtener el valor de la métrica desde metric_value
            score_value = participation.get_metric_value(threshold.score_field)
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