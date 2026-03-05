# -*- coding: utf-8 -*-
"""
Secciones HTML del perfil de alumno: alertas, participaciones, respuestas
cualitativas y lista de alumnos.
"""
from odoo import models, api, fields
from markupsafe import Markup
from ...utils import dashboard_styles, dashboard_helpers
from ...utils.constants import ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR


class DashboardStudentSections(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.student_profile'

    def _get_student_alerts_html(self, student_id):
        """Obtiene HTML con las alertas activas del estudiante."""
        Alert = self.env['aula_metrics.alert']
        alerts = Alert.search([
            ('student_id', '=', student_id),
            ('status', '=', 'active')
        ], order='severity desc, alert_date desc')

        if not alerts:
            return '<div class="alert alert-success"><i class="fa-solid fa-check-circle me-2"></i>No hay alertas activas para este estudiante</div>'

        severity_classes = {'low': 'info', 'moderate': 'warning', 'high': 'danger'}
        severity_labels  = {'low': 'Baja', 'moderate': 'Moderada', 'high': 'Alta'}

        html = '<div class="alerts-container">'
        for alert in alerts:
            badge_class    = severity_classes.get(alert.severity, 'secondary')
            severity_label = severity_labels.get(alert.severity, alert.severity)
            html += f"""
            <div class="alert alert-{badge_class} d-flex justify-content-between align-items-start">
                <div>
                    <h6>{alert.name}</h6>
                    <p class="mb-1">{alert.message or ''}</p>
                    <small class="text-muted">Creada: {alert.alert_date.strftime('%d/%m/%Y %H:%M')}</small>
                </div>
                <span class="badge bg-{badge_class}">{severity_label}</span>
            </div>"""
        html += '</div>'
        return html

    def _get_student_alerts_history_html(self, student_id):
        """Obtiene HTML con el historial de alertas resueltas/descartadas."""
        Alert = self.env['aula_metrics.alert']
        alerts = Alert.search([
            ('student_id', '=', student_id),
            ('status', 'in', ['resolved', 'dismissed'])
        ], order='resolution_date desc, alert_date desc', limit=20)

        if not alerts:
            return '<div class="alert alert-light">No hay historial de alertas</div>'

        severity_classes = {'low': 'info', 'moderate': 'warning', 'high': 'danger'}
        severity_labels  = {'low': 'Baja', 'moderate': 'Moderada', 'high': 'Alta'}
        status_labels    = {'resolved': 'Resuelta', 'dismissed': 'Descartada'}
        status_colors    = {'resolved': 'success', 'dismissed': 'secondary'}

        html = '<div class="alerts-history-container">'
        for alert in alerts:
            badge_class    = severity_classes.get(alert.severity, 'secondary')
            severity_label = severity_labels.get(alert.severity, alert.severity)
            status_label   = status_labels.get(alert.status, alert.status)
            status_color   = status_colors.get(alert.status, 'secondary')

            resolution_info = ''
            if alert.resolution_date:
                resolution_info = f'<small class="text-muted d-block">Resuelta: {alert.resolution_date.strftime("%d/%m/%Y %H:%M")}</small>'
            if alert.resolution_action:
                resolution_info += f'<small class="text-muted d-block mt-1"><strong>Acción:</strong> {alert.resolution_action}</small>'

            html += f"""
            <div class="alert alert-light border-start border-{badge_class} border-3 mb-2">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">{alert.name} <span class="badge bg-{status_color} ms-2">{status_label}</span></h6>
                        <p class="mb-1 text-muted small">{alert.message or ''}</p>
                        <small class="text-muted">Creada: {alert.alert_date.strftime('%d/%m/%Y %H:%M')}</small>
                        {resolution_info}
                    </div>
                    <span class="badge bg-{badge_class} ms-2">{severity_label}</span>
                </div>
            </div>"""
        html += '</div>'
        return html

    def _get_participations_html(self, student_id):
        """Obtiene HTML con el histórico de participaciones."""
        Participation = self.env['aula_metrics.participation']
        participations = Participation.search([
            ('student_id', '=', student_id)
        ], order='completed_at desc', limit=20)

        if not participations:
            return '<p class="text-muted">No hay participaciones registradas</p>'

        state_badges = {
            'pending':   '<span class="badge bg-warning">Pendiente</span>',
            'completed': '<span class="badge bg-success">Completada</span>',
            'expired':   '<span class="badge bg-secondary">Expirada</span>',
        }

        rows = ''
        for p in participations:
            state_html    = state_badges.get(p.state, p.state)
            completed_date = p.completed_at.strftime('%d/%m/%Y') if p.completed_at else 'N/A'
            surveys_names = ', '.join(p.evaluation_id.survey_ids.mapped('title')) if p.evaluation_id.survey_ids else 'N/A'
            rows += f"""
                <tr>
                    <td>{completed_date}</td>
                    <td>{p.evaluation_id.name}</td>
                    <td>{surveys_names}</td>
                    <td>{state_html}</td>
                </tr>"""

        return f"""
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead>
                    <tr><th>Fecha</th><th>Evaluación</th><th>Encuesta</th><th>Estado</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    def _get_qualitative_responses_html(self, student_id):
        """Obtiene HTML con las respuestas cualitativas del estudiante."""
        QualitativeResponse = self.env['aula_metrics.qualitative_response']
        responses = QualitativeResponse.search([
            ('student_id', '=', student_id)
        ], order='response_date desc', limit=20)

        if not responses:
            return '<p class="text-muted">No hay respuestas cualitativas registradas</p>'

        html = '<div class="qualitative-responses">'
        for resp in responses:
            alert_class   = 'alert-warning' if resp.has_alert_keywords else ''
            alert_badge   = ('<span class="badge bg-danger">Alerta</span>'
                             if resp.has_alert_keywords
                             else '<span class="badge bg-success"><i class="fa-solid fa-check"></i></span>')
            question_title  = resp.question_id.title if resp.question_id else 'Pregunta sin título'
            evaluation_name = resp.evaluation_id.name if resp.evaluation_id else 'Sin evaluación'
            date_str        = resp.response_date.strftime('%d/%m/%Y') if resp.response_date else 'Sin fecha'

            keywords_html = ''
            if resp.has_alert_keywords and resp.detected_keyword_ids:
                keywords_list = ', '.join(
                    f'<strong>{kw.keyword}</strong>' for kw in resp.detected_keyword_ids
                )
                if keywords_list:
                    keywords_html = f'<div class="mt-2"><small class="text-danger">Palabras detectadas: {keywords_list}</small></div>'

            html += f"""
            <div class="card mb-3 {alert_class}">
                <div class="card-header d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">{question_title}</h6>
                        <small class="text-muted">{evaluation_name} · {date_str} · {resp.word_count} palabras</small>
                    </div>
                    {alert_badge}
                </div>
                <div class="card-body">
                    <p class="mb-0">{resp.response_text}</p>
                    {keywords_html}
                </div>
            </div>"""
        html += '</div>'
        return html

    def _build_students_list_html(self, students, role_info):
        """Construye los datos de la lista de estudiantes para el template QWeb."""
        groups = {}
        for student in students:
            if student.academic_group_id:
                groups[student.academic_group_id.id] = student.academic_group_id.name

        group_options = '<option value="">Todos los grupos</option>'
        for group_id, group_name in sorted(groups.items(), key=lambda x: x[1]):
            group_options += f'<option value="{group_id}">{group_name}</option>'

        if not students:
            students_rows = '''
            <tr>
                <td colspan="5" class="text-center text-muted py-5">
                    <i class="fa-solid fa-user-slash fa-3x mb-3 d-block"></i>
                    No hay estudiantes disponibles
                </td>
            </tr>'''
        else:
            students_rows = ''
            for student in students:
                group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
                group_id   = student.academic_group_id.id   if student.academic_group_id else 0
                email      = student.email or 'N/A'

                metrics_count = self.env['aula_metrics.metric_value'].search_count([
                    ('student_id', '=', student.id)
                ])
                alerts_count = self.env['aula_metrics.alert'].search_count([
                    ('student_id', '=', student.id),
                    ('status', '=', 'active'),
                ])

                alerts_badge = (
                    f'<span class="badge bg-danger">{alerts_count} alerta(s)</span>'
                    if alerts_count > 0
                    else '<span class="badge bg-success"><i class="fa-solid fa-check"></i></span>'
                )
                students_rows += f'''
                <tr data-group-id="{group_id}">
                    <td>
                        <div class="d-flex align-items-center">
                            <div class="student-avatar me-3">
                                <i class="fa-solid fa-user-circle fa-2x text-primary"></i>
                            </div>
                            <div>
                                <div class="fw-bold">{student.name}</div>
                                <small class="text-muted">{email}</small>
                            </div>
                        </div>
                    </td>
                    <td>{group_name}</td>
                    <td class="text-center">{metrics_count}</td>
                    <td>{alerts_badge}</td>
                    <td class="text-end">
                        <a href="/aulametrics/student/{student.id}" class="btn btn-sm btn-outline-primary">
                            <i class="fa-solid fa-chart-line me-1"></i> Ver Perfil
                        </a>
                    </td>
                </tr>'''

        list_styles = dashboard_styles.get_common_styles() + """
        <style>
            .card { border-radius: 12px; border: 1px solid var(--am-border); box-shadow: 0 1px 3px rgba(0,0,0,0.05); background: var(--am-surface); }
            .card-header { background: var(--am-surface); border-bottom: 1px solid var(--am-border); font-weight: 600; padding: 1.25rem 1.5rem; }
            .table { margin-bottom: 0; }
            .table thead th { background: var(--am-bg); font-weight: 600; border-bottom: 2px solid var(--am-border); padding: 1rem; }
            .table tbody td { padding: 1rem; vertical-align: middle; }
            .table tbody tr:hover { background: var(--am-bg); }
            .search-box { margin-bottom: 1.5rem; }
            .search-box input { border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid var(--am-border); }
            .search-box input:focus { border-color: var(--am-primary); box-shadow: 0 0 0 3px rgba(var(--am-primary-rgb), 0.1); }
            .filters-bar { margin-bottom: 1.5rem; display: flex; gap: 1rem; align-items: center; }
            .filters-bar select { border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid var(--am-border); }
            .filters-bar select:focus { border-color: var(--am-primary); box-shadow: 0 0 0 3px rgba(var(--am-primary-rgb), 0.1); }
        </style>"""

        scripts_html = """
            <script>
                function applyFilters() {
                    const searchTerm   = document.getElementById('searchInput').value.toLowerCase();
                    const selectedGroup = document.getElementById('groupFilter').value;
                    const rows = document.querySelectorAll('#studentsTable tbody tr');
                    let visibleCount = 0;
                    rows.forEach(row => {
                        const text    = row.textContent.toLowerCase();
                        const groupId = row.getAttribute('data-group-id');
                        const ok = (!searchTerm || text.includes(searchTerm))
                                && (!selectedGroup || groupId === selectedGroup);
                        row.style.display = ok ? '' : 'none';
                        if (ok) visibleCount++;
                    });
                    const header = document.querySelector('.card-header span');
                    if (header) {
                        const total = rows.length;
                        header.innerHTML = visibleCount === total
                            ? '<i class="fa-solid fa-list me-2"></i>Estudiantes (' + total + ')'
                            : '<i class="fa-solid fa-list me-2"></i>Estudiantes (' + visibleCount + ' de ' + total + ')';
                    }
                }
                document.getElementById('searchInput').addEventListener('keyup', applyFilters);
                document.getElementById('groupFilter').addEventListener('change', applyFilters);
            </script>"""

        content_html = f"""
        <div class="container-fluid">
            <div class="filters-bar">
                <div class="flex-grow-1">
                    <input type="text" id="searchInput" class="form-control" placeholder="Buscar por nombre...">
                </div>
                <div style="min-width: 250px;">
                    <select id="groupFilter" class="form-select">{group_options}</select>
                </div>
            </div>
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span><i class="fa-solid fa-list me-2"></i>Estudiantes ({len(students)})</span>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover" id="studentsTable">
                            <thead>
                                <tr>
                                    <th>Estudiante</th><th>Grupo</th>
                                    <th class="text-center">Métricas</th>
                                    <th>Estado</th><th class="text-end">Acciones</th>
                                </tr>
                            </thead>
                            <tbody>{students_rows}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>"""

        return {
            'page_title':           'Perfiles de Alumnos',
            'css_styles':           Markup(list_styles),
            'head_extra':           Markup('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet"/>'),
            'role_info':            role_info,
            'active_section':       'profiles',
            'topbar_title':         'Perfiles de Alumnos',
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-users me-2"></i>Listado de estudiantes · {fields.Date.today().strftime("%d/%m/%Y")}'
            ),
            'topbar_extra_actions': Markup(''),
            'content_html':         Markup(content_html),
            'scripts_html':         Markup(scripts_html),
        }
