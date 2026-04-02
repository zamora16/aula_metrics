# -*- coding: utf-8 -*-
import json
import re
from odoo import models, fields, api
from ...utils.constants import GROUP_ADMIN, GROUP_COUNSELOR, GROUP_MANAGEMENT

class Alert(models.Model):
    _name = 'aula_metrics.alert'
    _table = 'aulametrics_alert'
    _description = 'Alerta de AulaMetrics'
    _order = 'alert_date desc'
    
    name = fields.Char(string='Título', compute='_compute_name')
    threshold_id = fields.Many2one('aula_metrics.threshold', string='Umbral', ondelete='cascade')
    participation_id = fields.Many2one('aula_metrics.participation', string='Participación', ondelete='cascade')
    qualitative_response_id = fields.Many2one('aula_metrics.qualitative_response', string='Respuesta Cualitativa', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Alumno')
    academic_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo Académico',
        readonly=True,
        help='Grupo del alumno en el momento de generar la alerta (dato histórico).'
    )
    academic_year_id = fields.Many2one(
        'aula_metrics.academic_year',
        string='Curso Académico',
        compute='_compute_academic_year_id',
        store=True,
        readonly=True,
        index=True,
        help='Curso académico de la alerta, derivado del grupo académico.'
    )
    score_value = fields.Float(string='Valor de Puntuación', default=0.0)
    alert_date = fields.Datetime(string='Fecha de Alerta', default=fields.Datetime.now)
    status = fields.Selection([
        ('active', 'Activa'),
        ('en_gestion', 'En Gestión'),
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
        ('qualitative', 'Cualitativa'),
        ('manual', 'Manual (Tutor)'),
    ], string='Tipo de Alerta', compute='_compute_alert_type', store=True)
    severity = fields.Selection([
        ('low', 'Baja'),
        ('moderate', 'Moderada'),
        ('high', 'Alta')
    ], string='Severidad', compute='_compute_severity', store=True, readonly=False)
    
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

    # Alerta creada manualmente por un tutor
    is_manual = fields.Boolean(
        string='Alerta Manual',
        default=False,
        help='Indica que esta alerta fue creada manualmente por un tutor, no por el sistema automático'
    )
    manual_description = fields.Text(
        string='Descripción del Tutor',
        help='Descripción de la situación observada por el tutor'
    )
    
    # Caso de orientación vinculado (calculado desde el lado inverso)
    case_id = fields.Many2one(
        'aula_metrics.case',
        string='Caso de Orientación',
        compute='_compute_case_id',
        store=False,
    )

    # Campo computado para mostrar curso general (sin especificar A/B/C)
    course_level_general = fields.Char(
        string='Curso General',
        compute='_compute_course_level_general',
        store=False
    )
    
    def _compute_case_id(self):
        """Busca el caso de orientación vinculado a esta alerta (si existe)."""
        for alert in self:
            case = self.env['aula_metrics.case'].search(
                [('alert_id', '=', alert.id)], limit=1
            )
            alert.case_id = case

    @api.depends('academic_group_id.academic_year_id')
    def _compute_academic_year_id(self):
        """Deriva el curso académico desde el grupo académico de la alerta."""
        for alert in self:
            alert.academic_year_id = alert.academic_group_id.academic_year_id

    @api.depends('academic_group_id.course_level')
    def _compute_course_level_general(self):
        """Extrae solo el nivel de curso (Primero, Segundo...) sin la letra del grupo."""
        for alert in self:
            if alert.academic_group_id and alert.academic_group_id.course_level:
                course = alert.academic_group_id.course_level
                match = re.match(r'^(.*?)\s*[A-Z]?$', course)
                alert.course_level_general = match.group(1).strip() if match else course
            else:
                alert.course_level_general = 'Sin curso'
    
    @api.depends('qualitative_response_id', 'threshold_id', 'is_manual')
    def _compute_alert_type(self):
        """Determina si la alerta es cuantitativa, cualitativa o manual."""
        for alert in self:
            if alert.is_manual:
                alert.alert_type = 'manual'
            elif alert.qualitative_response_id:
                alert.alert_type = 'qualitative'
            else:
                alert.alert_type = 'quantitative'
    
    @api.depends('threshold_id', 'qualitative_response_id', 'is_manual')
    def _compute_severity(self):
        """Calcula severidad: desde threshold para cuantitativas, desde keywords para cualitativas.
        Para alertas manuales, la severidad es fijada directamente por el tutor (no se sobreescribe).
        """
        for alert in self:
            if alert.is_manual:
                # La severidad se establece en el wizard; no tocar el valor ya almacenado.
                # Solo asignar default si está vacía (primera vez).
                if not alert.severity:
                    alert.severity = 'moderate'
                continue
            if alert.qualitative_response_id and alert.qualitative_response_id.detected_keyword_ids:
                # Alerta cualitativa: usar severidad más alta de keywords detectadas
                try:
                    keywords = alert.qualitative_response_id.detected_keyword_ids.filtered('active')
                    if keywords:
                        severity_order = {'high': 3, 'moderate': 2, 'low': 1}
                        max_severity = max(keywords.mapped('severity'),
                                         key=lambda s: severity_order.get(s, 0))
                        alert.severity = max_severity
                    else:
                        alert.severity = 'moderate'
                except Exception:
                    alert.severity = 'moderate'
            elif alert.threshold_id:
                # Alerta cuantitativa: usar severidad del threshold
                alert.severity = alert.threshold_id.severity
            else:
                alert.severity = False
    
    @api.depends('threshold_id', 'qualitative_response_id', 'is_manual', 'manual_description')
    def _compute_message(self):
        """Computa el mensaje de alerta según el tipo."""
        for alert in self:
            if alert.is_manual:
                # Alerta manual: usar la descripción introducida por el tutor
                alert.message = alert.manual_description or 'Alerta reportada manualmente por el tutor'
            elif alert.qualitative_response_id:
                # Alerta cualitativa: mensaje personalizado con keywords
                try:
                    keywords_str = ', '.join(
                        alert.qualitative_response_id.detected_keyword_ids.mapped('keyword')
                    )
                    alert.message = f"Se detectaron palabras de alerta en una respuesta cualitativa: {keywords_str}"
                except Exception:
                    alert.message = "Se detectaron palabras de alerta en una respuesta cualitativa"
            elif alert.threshold_id:
                # Alerta cuantitativa: mensaje del threshold
                alert.message = alert.threshold_id.alert_message
            else:
                alert.message = False
    
    @api.depends('alert_type', 'alert_level', 'threshold_id.name', 'academic_group_id.name', 'student_id.name', 'course_level_general')
    def _compute_name(self):
        """Computa el nombre de la alerta según permisos del usuario."""
        for alert in self:
            user = self.env.user
            is_counselor_or_admin = user.has_group(GROUP_ADMIN) or user.has_group(GROUP_COUNSELOR)
            is_management = user.has_group(GROUP_MANAGEMENT)
            
            # Nombre base según tipo de alerta
            if alert.alert_type == 'qualitative':
                base_name = 'Alerta Cualitativa'
            elif alert.alert_type == 'manual':
                base_name = 'Alerta Manual'
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
        score_value = float(len(qualitative_response.detected_keyword_ids)) or 1.0
        
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

        # Crear caso de orientación automáticamente para alertas cualitativas individuales
        if alert.student_id:
            self.env['aula_metrics.case'].sudo().create_from_alert(alert)

        return alert
    
    @api.model
    def check_alerts_for_participation(self, participation):
        """
        Verifica si las puntuaciones de una participación superan algún umbral activo.
        Se llama en tiempo real cada vez que se completa un cuestionario.
        """
        # Buscar umbrales activos relevantes para los cuestionarios de esta evaluación
        thresholds = self.env['aula_metrics.threshold'].search([
            ('active', '=', True)
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
    
    def _check_all_group_alerts(self, participation):
        """Verifica y genera alertas grupales para todos los umbrales relevantes en una sola operación"""
        group = participation.student_id.academic_group_id
        thresholds = self.env['aula_metrics.threshold'].search([
            ('active', '=', True),
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

            new_alert = self.create(vals)

            # Crear caso de orientación automáticamente para alertas individuales
            if alert_level == 'individual' and new_alert.student_id:
                self.env['aula_metrics.case'].sudo().create_from_alert(new_alert)

    def action_resolve(self):
        """Abrir wizard para registrar la acción tomada y resolver la alerta.
        Solo se usa para alertas grupales o individuales sin caso asociado.
        """
        self.ensure_one()
        return {
            'name': 'Resolver Alerta',
            'type': 'ir.actions.act_window',
            'res_model': 'aula_metrics.resolve_alert_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_alert_id': self.id,
            }
        }

    def action_open_case(self):
        """Navega al caso de orientación vinculado a esta alerta.
        Solo accesible para orientadores y administradores.
        """
        self.ensure_one()
        if not self.case_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'aula_metrics.case',
            'res_id': self.case_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_dismiss(self):
        """Descartar alerta. Funciona tanto en estado 'active' como 'en_gestion'."""
        for alert in self:
            if alert.status in ('active', 'en_gestion'):
                alert.status = 'dismissed'