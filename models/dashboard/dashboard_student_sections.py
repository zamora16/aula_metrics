# -*- coding: utf-8 -*-
"""
Secciones HTML del perfil de alumno: alertas, participaciones, respuestas
cualitativas y lista de alumnos.
"""
from odoo import models, api, fields
from markupsafe import Markup
from ...utils import dashboard_styles, dashboard_helpers, palette
from ...utils.constants import ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR

# Colores de severidad de alertas — solo usados en este módulo
_ALERT_SEV = {
    'low':      {'color': '#0ea5e9', 'bg': '#f0f9ff', 'border': '#bae6fd', 'label': 'Baja'},
    'moderate': {'color': '#f59e0b', 'bg': '#fffbeb', 'border': '#fde68a', 'label': 'Moderada'},
    'high':     {'color': palette.UI_DANGER, 'bg': '#fef2f2', 'border': '#fecaca', 'label': 'Alta'},
}
_ALERT_ST = {
    'resolved':  {'color': palette.UI_SUCCESS, 'label': 'Resuelta'},
    'dismissed': {'color': palette.UI_MUTED,   'label': 'Descartada'},
}


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
            return (
                '<div style="display:flex;align-items:center;gap:10px;padding:14px 16px;'
                'background:var(--am-light);border:1px solid var(--am-border);'
                'border-radius:8px;font-size:13px;color:var(--am-muted);">'
                f'<i class="fa-solid fa-check-circle" style="color:{palette.UI_SUCCESS};font-size:16px;"></i>'
                'No hay alertas activas para este estudiante</div>'
            )

        html = '<div style="display:flex;flex-direction:column;gap:8px;">'
        for alert in alerts:
            sc = _ALERT_SEV.get(alert.severity,
                {'color': palette.UI_MUTED, 'bg': 'var(--am-light)', 'border': 'var(--am-border)', 'label': alert.severity})
            html += f"""
            <div style="border:1px solid {sc['border']};border-left:4px solid {sc['color']};
                        border-radius:8px;background:{sc['bg']};padding:14px 16px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:14px;font-weight:600;color:var(--am-text);margin-bottom:4px;">
                            {alert.name}
                        </div>
                        <div style="font-size:13px;color:var(--am-text);opacity:0.85;margin-bottom:6px;">
                            {alert.message or ''}
                        </div>
                        <div style="font-size:11px;color:var(--am-muted);">
                            <i class="fa-regular fa-clock me-1"></i>
                            Creada: {alert.alert_date.strftime('%d/%m/%Y %H:%M')}
                        </div>
                    </div>
                    <span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;
                                 border:1px solid {sc['border']};background:white;
                                 color:{sc['color']};white-space:nowrap;flex-shrink:0;">
                        {sc['label']}
                    </span>
                </div>
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
            return (
                '<div style="padding:14px 16px;background:var(--am-light);'
                'border:1px solid var(--am-border);border-radius:8px;'
                'font-size:13px;color:var(--am-muted);">'
                'No hay historial de alertas</div>'
            )

        html = '<div style="display:flex;flex-direction:column;gap:6px;">'
        for alert in alerts:
            sc = _ALERT_SEV.get(alert.severity,
                {'color': palette.UI_MUTED, 'label': alert.severity})
            st = _ALERT_ST.get(alert.status,
                {'color': palette.UI_MUTED, 'label': alert.status})

            resolution_info = ''
            if alert.resolution_date:
                resolution_info += (
                    f'<div style="font-size:11px;color:var(--am-muted);margin-top:4px;">'
                    f'<i class="fa-solid fa-square-check me-1"></i>'
                    f'Resuelta: {alert.resolution_date.strftime("%d/%m/%Y %H:%M")}</div>'
                )
            if alert.resolution_action:
                resolution_info += (
                    f'<div style="font-size:11px;color:var(--am-muted);margin-top:2px;">'
                    f'<i class="fa-solid fa-bolt me-1"></i>'
                    f'<strong>Acción:</strong> {alert.resolution_action}</div>'
                )

            html += f"""
            <div style="border:1px solid var(--am-border);border-left:3px solid {sc['color']};
                        border-radius:8px;background:var(--am-surface);
                        padding:12px 16px;opacity:0.85;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:600;color:var(--am-text);margin-bottom:3px;">
                            {alert.name}
                        </div>
                        <div style="font-size:12px;color:var(--am-muted);margin-bottom:4px;">
                            {alert.message or ''}
                        </div>
                        <div style="font-size:11px;color:var(--am-muted);">
                            <i class="fa-regular fa-clock me-1"></i>
                            Creada: {alert.alert_date.strftime('%d/%m/%Y %H:%M')}
                        </div>
                        {resolution_info}
                    </div>
                    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0;">
                        <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;
                                     border:1px solid {sc['color']}44;color:{sc['color']};
                                     background:{sc['color']}14;white-space:nowrap;">
                            {sc['label']}
                        </span>
                        <span style="font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;
                                     border:1px solid {st['color']}44;color:{st['color']};
                                     background:{st['color']}14;white-space:nowrap;">
                            {st['label']}
                        </span>
                    </div>
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
            return (
                '<div style="padding:14px 16px;background:var(--am-light);'
                'border:1px solid var(--am-border);border-radius:8px;'
                'font-size:13px;color:var(--am-muted);">'
                'No hay respuestas cualitativas registradas</div>'
            )

        html = '<div style="display:flex;flex-direction:column;gap:10px;">'
        for resp in responses:
            has_alert       = resp.has_alert_keywords
            accent_color    = palette.UI_DANGER if has_alert else palette.UI_SUCCESS
            question_title  = resp.question_id.title if resp.question_id else 'Pregunta sin título'
            evaluation_name = resp.evaluation_id.name if resp.evaluation_id else 'Sin evaluación'
            date_str        = resp.response_date.strftime('%d/%m/%Y') if resp.response_date else 'Sin fecha'

            alert_badge = (
                f'<span style="font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;'
                f'background:#fef2f2;border:1px solid #fecaca;color:{palette.UI_DANGER};white-space:nowrap;">'
                f'<i class="fa-solid fa-triangle-exclamation me-1"></i>Alerta</span>'
                if has_alert else
                f'<span style="font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;'
                f'background:#f0fdf4;border:1px solid #bbf7d0;color:{palette.UI_SUCCESS};white-space:nowrap;">'
                f'<i class="fa-solid fa-check me-1"></i>OK</span>'
            )

            keywords_html = ''
            if has_alert and resp.detected_keyword_ids:
                pills = ''.join(
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
                    f'background:#fef2f2;border:1px solid #fecaca;color:{palette.UI_DANGER};'
                    f'font-size:11px;font-weight:600;margin:2px 3px 2px 0;">{kw.keyword}</span>'
                    for kw in resp.detected_keyword_ids
                )
                keywords_html = (
                    f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--am-border);">'
                    f'<span style="font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.07em;color:{palette.UI_DANGER};margin-right:6px;">Palabras detectadas</span>'
                    f'{pills}</div>'
                )

            html += f"""
            <div style="border:1px solid var(--am-border);border-left:4px solid {accent_color};
                        border-radius:8px;background:var(--am-surface);overflow:hidden;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;
                            gap:12px;padding:12px 16px 10px;border-bottom:1px solid var(--am-border);">
                    <div style="min-width:0;flex:1;">
                        <div style="font-size:13px;font-weight:600;color:var(--am-text);">
                            {question_title}
                        </div>
                        <div style="font-size:11px;color:var(--am-muted);margin-top:3px;">
                            <i class="fa-solid fa-graduation-cap me-1"></i>{evaluation_name}
                            <span style="margin:0 5px;">·</span>
                            <i class="fa-regular fa-calendar me-1"></i>{date_str}
                            <span style="margin:0 5px;">·</span>
                            {resp.word_count} palabras
                        </div>
                    </div>
                    {alert_badge}
                </div>
                <div style="padding:12px 16px;font-size:13px;color:var(--am-text);line-height:1.6;">
                    {resp.response_text}
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

        list_styles = dashboard_styles.get_common_styles()

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
            'head_extra':           Markup(''),
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
