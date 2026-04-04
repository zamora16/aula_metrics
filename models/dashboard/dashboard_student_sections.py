# -*- coding: utf-8 -*-
"""
Secciones del perfil de alumno: alertas, participaciones, respuestas cualitativas
y lista de alumnos.

Cada método prepara un dict de datos y delega la presentación a una plantilla QWeb.
"""
from odoo import models, fields
from markupsafe import Markup
from ...utils import dashboard_styles, role_service, palette

_ALERT_SEV = {
    'low':      {'color': palette.ALERT_LOW_COLOR,  'bg': palette.ALERT_LOW_BG,  'border': palette.ALERT_LOW_BORDER,  'label': 'Baja'},
    'moderate': {'color': palette.ALERT_MOD_COLOR,  'bg': palette.ALERT_MOD_BG,  'border': palette.ALERT_MOD_BORDER,  'label': 'Moderada'},
    'high':     {'color': palette.ALERT_HIGH_COLOR, 'bg': palette.ALERT_HIGH_BG, 'border': palette.ALERT_HIGH_BORDER, 'label': 'Alta'},
}
_ALERT_ST = {
    'resolved':  {'color': palette.UI_SUCCESS, 'label': 'Resuelta'},
    'dismissed': {'color': palette.UI_MUTED,   'label': 'Descartada'},
}
_SEV_DEFAULT = {'color': palette.UI_MUTED, 'bg': 'var(--am-light)', 'border': 'var(--am-border)', 'label': '—'}
_ST_DEFAULT  = {'color': palette.UI_MUTED, 'label': '—'}


def _qweb(env, template_id, values):
    """Render a QWeb template and return Markup (handles bytes or str return)."""
    result = env['ir.qweb']._render(template_id, values)
    if isinstance(result, bytes):
        return Markup(result.decode('utf-8'))
    return Markup(result)


class DashboardStudentSections(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.student_profile'

    # ── Alerts ──────────────────────────────────────────────────────────

    def _get_student_alerts_html(self, student_id):
        """Renderiza las alertas activas del estudiante via QWeb."""
        alerts = self.env['aula_metrics.alert'].search([
            ('student_id', '=', student_id),
            ('status', '=', 'active'),
        ], order='severity desc, alert_date desc')

        alert_items = []
        for alert in alerts:
            sev = _ALERT_SEV.get(alert.severity, _SEV_DEFAULT)
            alert_items.append({
                'name':       alert.name,
                'message':    alert.message or '',
                'date_str':   alert.alert_date.strftime('%d/%m/%Y %H:%M'),
                'sev_label':  sev['label'],
                'card_style': (
                    f"border:1px solid {sev['border']};"
                    f"border-left:4px solid {sev['color']};"
                    f"border-radius:8px;background:{sev['bg']};padding:14px 16px;"
                ),
                'badge_style': (
                    f"font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;"
                    f"border:1px solid {sev['border']};background:white;"
                    f"color:{sev['color']};white-space:nowrap;flex-shrink:0;"
                ),
            })

        return _qweb(self.env, 'aula_metrics.student_alerts_active_section', {
            'alert_items': alert_items,
            'ui_success':  palette.UI_SUCCESS,
        })

    def _get_student_alerts_history_html(self, student_id):
        """Renderiza el historial de alertas resueltas/descartadas via QWeb."""
        alerts = self.env['aula_metrics.alert'].search([
            ('student_id', '=', student_id),
            ('status', 'in', ['resolved', 'dismissed']),
        ], order='resolution_date desc, alert_date desc', limit=20)

        alert_items = []
        for alert in alerts:
            sev = _ALERT_SEV.get(alert.severity, _SEV_DEFAULT)
            st  = _ALERT_ST.get(alert.status,    _ST_DEFAULT)
            alert_items.append({
                'name':         alert.name,
                'message':      alert.message or '',
                'created_str':  alert.alert_date.strftime('%d/%m/%Y %H:%M'),
                'resolved_str': alert.resolution_date.strftime('%d/%m/%Y %H:%M') if alert.resolution_date else '',
                'action_str':   alert.resolution_action or '',
                'sev_label':    sev['label'],
                'status_label': st['label'],
                'card_style': (
                    f"border:1px solid var(--am-border);"
                    f"border-left:3px solid {sev['color']};"
                    f"border-radius:8px;background:var(--am-surface);padding:12px 16px;opacity:0.85;"
                ),
                'sev_badge_style': (
                    f"font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;"
                    f"border:1px solid {sev['color']}44;color:{sev['color']};"
                    f"background:{sev['color']}14;white-space:nowrap;"
                ),
                'status_badge_style': (
                    f"font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;"
                    f"border:1px solid {st['color']}44;color:{st['color']};"
                    f"background:{st['color']}14;white-space:nowrap;"
                ),
            })

        return _qweb(self.env, 'aula_metrics.student_alerts_history_section', {
            'alert_items': alert_items,
        })

    # ── Participations ───────────────────────────────────────────────────

    def _get_participations_html(self, student_id):
        """Renderiza el historial de participaciones via QWeb."""
        participations = self.env['aula_metrics.participation'].search([
            ('student_id', '=', student_id),
        ], order='completed_at desc', limit=20)

        _badge = {
            'pending':   ('bg-warning', 'Pendiente'),
            'completed': ('bg-success', 'Completada'),
            'expired':   ('bg-secondary', 'Expirada'),
        }

        rows = []
        for p in participations:
            bc, bl = _badge.get(p.state, ('bg-secondary', p.state))
            rows.append({
                'date_str':     p.completed_at.strftime('%d/%m/%Y') if p.completed_at else 'N/A',
                'eval_name':    p.evaluation_id.name,
                'survey_names': ', '.join(p.evaluation_id.survey_ids.mapped('title')) if p.evaluation_id.survey_ids else 'N/A',
                'badge_class':  bc,
                'badge_label':  bl,
            })

        return _qweb(self.env, 'aula_metrics.student_participations_section', {'rows': rows})

    # ── Qualitative responses ────────────────────────────────────────────

    def _get_qualitative_responses_html(self, student_id):
        """Renderiza las respuestas cualitativas via QWeb."""
        responses = self.env['aula_metrics.qualitative_response'].search([
            ('student_id', '=', student_id),
        ], order='response_date desc', limit=20)

        response_items = []
        for resp in responses:
            has_alert      = resp.has_alert_keywords
            accent_color   = palette.UI_DANGER if has_alert else palette.UI_SUCCESS

            if has_alert:
                alert_badge_html = Markup(
                    f'<i class="fa-solid fa-triangle-exclamation me-1"></i>Alerta'
                )
                alert_badge_style = (
                    f"font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;"
                    f"background:{palette.ALERT_HIGH_BG};border:1px solid {palette.ALERT_HIGH_BORDER};"
                    f"color:{palette.ALERT_HIGH_COLOR};white-space:nowrap;"
                )
            else:
                alert_badge_html = Markup(
                    f'<i class="fa-solid fa-check me-1"></i>OK'
                )
                alert_badge_style = (
                    f"font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;"
                    f"background:{palette.BADGE_OK_BG};border:1px solid {palette.BADGE_OK_BORDER};"
                    f"color:{palette.UI_SUCCESS};white-space:nowrap;"
                )

            keywords_html = Markup('')
            if has_alert and resp.detected_keyword_ids:
                pills = Markup('').join(
                    Markup(
                        f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
                        f'background:{palette.ALERT_HIGH_BG};border:1px solid {palette.ALERT_HIGH_BORDER};'
                        f'color:{palette.ALERT_HIGH_COLOR};font-size:11px;font-weight:600;margin:2px 3px 2px 0;">'
                        f'{kw.keyword}</span>'
                    )
                    for kw in resp.detected_keyword_ids
                )
                keywords_html = Markup(
                    f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--am-border);">'
                    f'<span style="font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.07em;color:{palette.UI_DANGER};margin-right:6px;">Palabras detectadas</span>'
                    f'{pills}</div>'
                )

            response_items.append({
                'question_title':   resp.question_id.title if resp.question_id else 'Pregunta sin título',
                'evaluation_name':  resp.evaluation_id.name if resp.evaluation_id else 'Sin evaluación',
                'date_str':         resp.response_date.strftime('%d/%m/%Y') if resp.response_date else 'Sin fecha',
                'word_count':       resp.word_count,
                'response_text':    resp.response_text,
                'alert_badge_html':  alert_badge_html,
                'alert_badge_style': alert_badge_style,
                'keywords_html':    keywords_html,
                'card_style': (
                    f"border:1px solid var(--am-border);"
                    f"border-left:4px solid {accent_color};"
                    f"border-radius:8px;background:var(--am-surface);overflow:hidden;"
                ),
            })

        return _qweb(self.env, 'aula_metrics.student_qualitative_section', {
            'response_items': response_items,
        })

    # ── Students list ────────────────────────────────────────────────────

    def _build_students_list_html(self, students, role_info):
        """Construye la página de lista de estudiantes via QWeb (batch-queries)."""
        student_ids = students.ids

        # Batch: evaluaciones completadas por alumno
        part_groups = self.env['aula_metrics.participation'].read_group(
            [('student_id', 'in', student_ids), ('state', '=', 'completed')],
            ['student_id'], ['student_id'],
        )
        evals_done_map = {g['student_id'][0]: g['student_id_count'] for g in part_groups}

        # Batch: alertas activas por alumno
        alert_groups = self.env['aula_metrics.alert'].read_group(
            [('student_id', 'in', student_ids), ('status', '=', 'active')],
            ['student_id'], ['student_id'],
        )
        alerts_map = {g['student_id'][0]: g['student_id_count'] for g in alert_groups}

        groups = {}
        student_list = []
        for student in students:
            if student.academic_group_id:
                groups[student.academic_group_id.id] = student.academic_group_id.name

            alerts_count = alerts_map.get(student.id, 0)
            if alerts_count > 0:
                alerts_badge_style = (
                    f"font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;"
                    f"background:{palette.ALERT_HIGH_BG};border:1px solid {palette.ALERT_HIGH_BORDER};"
                    f"color:{palette.ALERT_HIGH_COLOR};white-space:nowrap;"
                )
                alerts_badge_text = f'{alerts_count} alerta{"s" if alerts_count > 1 else ""}'
            else:
                alerts_badge_style = (
                    f"font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;"
                    f"background:{palette.BADGE_OK_BG};border:1px solid {palette.BADGE_OK_BORDER};"
                    f"color:{palette.UI_SUCCESS};"
                )
                alerts_badge_text = 'Sin alertas'

            student_list.append({
                'id':                student.id,
                'name':              student.name,
                'email':             student.email or 'N/A',
                'group_name':        student.academic_group_id.name if student.academic_group_id else 'Sin grupo',
                'group_id':          student.academic_group_id.id   if student.academic_group_id else 0,
                'initials':          ''.join(w[0].upper() for w in student.name.split()[:2]) if student.name else '?',
                'evals_done':        evals_done_map.get(student.id, 0),
                'alerts_badge_style': alerts_badge_style,
                'alerts_badge_text':  alerts_badge_text,
            })

        sorted_groups = sorted(groups.items(), key=lambda x: x[1])

        content_html = _qweb(self.env, 'aula_metrics.students_list_content', {
            'student_list': student_list,
            'groups':       sorted_groups,
            'total_count':  len(students),
        })

        return {
            'page_title':           'Perfiles de Alumnos',
            'css_styles':           Markup(dashboard_styles.get_common_styles()),
            'head_extra':           Markup(''),
            'role_info':            role_info,
            'active_section':       'profiles',
            'topbar_title':         'Perfiles de Alumnos',
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-users me-2"></i>'
                f'Listado de estudiantes · {fields.Date.today().strftime("%d/%m/%Y")}'
            ),
            'topbar_extra_actions': Markup(''),
            'content_html':         content_html,
            'scripts_html':         Markup(''),
        }
