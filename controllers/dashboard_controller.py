# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from markupsafe import Markup
# Importar utilidades compartidas
from odoo.addons.aula_metrics.utils import role_service
from odoo.addons.aula_metrics.utils.constants import ROLE_MANAGEMENT

_HTML_HEADERS = [('Content-Type', 'text/html; charset=utf-8')]

# Keys whose values are pre-rendered HTML and must not be re-escaped by t-out.
_HTML_VALUE_KEYS = frozenset({
    'css_styles', 'head_extra',
    'content_html', 'scripts_html',       # used by student profile pages
    'topbar_subtitle', 'topbar_extra_actions',  # may contain HTML fragments
})


def _render(template, values):
    """Render a QWeb template to a standalone HTML response.

    All values listed in _HTML_VALUE_KEYS are wrapped in markupsafe.Markup
    so that QWeb's t-out emits them as raw HTML instead of escaping them.
    """
    safe = {
        k: (Markup(v) if k in _HTML_VALUE_KEYS and isinstance(v, str) else v)
        for k, v in values.items()
    }
    html = request.env['ir.ui.view']._render_template(template, safe)
    return request.make_response(html, headers=_HTML_HEADERS)


class DashboardChartsController(http.Controller):
    """Controlador para dashboard interactivo con filtros de rol."""

    def _detect_user_role(self):
        """
        Detecta el rol del usuario actual con sus grupos académicos permitidos.
        Jerarquía: admin > counselor > management > tutor
        """
        return role_service.get_role_info(request.env, request.env.user)

    @http.route('/aulametrics/dashboard', type='http', auth='user')
    def dashboard_view(self, **kwargs):
        """
        Dashboard principal con filtros dinámicos.
        
        Parámetros GET:
        - evaluation_ids: lista CSV de IDs de evaluaciones
        """
        role_info = self._detect_user_role()

        # Parsear parámetros de filtro
        filters = self._parse_hub_filters(kwargs)
        
        # Aplicar restricciones de rol a los filtros
        filters = self._apply_role_restrictions(filters, role_info)

        values = request.env['aula_metrics.dashboard.charts'].generate_dashboard(
            filters=filters,
            role_info=role_info
        )
        return _render('aula_metrics.dashboard_main', values)

    @http.route('/aulametrics/students', type='http', auth='user')
    def students_list_view(self, **kwargs):
        """
        Lista de estudiantes en formato HTML estilo dashboard.
        
        Acceso según rol:
        - Counselor/Admin: todos los alumnos
        - Tutor: solo alumnos de sus grupos
        - Management: bloqueado
        """
        role_info = self._detect_user_role()
        
        # Management no tiene acceso a perfiles individuales
        if role_info.get('role') == ROLE_MANAGEMENT:
            return _render('aula_metrics.dashboard_access_denied', {
                'message': 'El equipo directivo no tiene acceso a perfiles individuales de alumnos.',
            })

        values = request.env['aula_metrics.dashboard.student_profile'].generate_students_list(
            role_info=role_info
        )
        return _render('aula_metrics.dashboard_page_base', values)

    @http.route('/aulametrics/student/<int:student_id>', type='http', auth='user')
    def student_profile_view(self, student_id, **kwargs):
        """
        Dashboard individual de alumno con visión longitudinal.
        
        Acceso según rol:
        - Counselor/Admin: todos los alumnos
        - Tutor: solo alumnos de sus grupos
        - Management: bloqueado
        
        Args:
            student_id: ID del res.partner con student=True
        """
        role_info = self._detect_user_role()
        
        # Verificar que el ID corresponde a un estudiante
        student = request.env['res.partner'].sudo().search([
            ('id', '=', student_id),
            ('is_student', '=', True)
        ], limit=1)
        
        if not student:
            return request.not_found(description="El estudiante solicitado no existe.")
        
        # Delegar validación de acceso y generación al modelo
        try:
            values = request.env['aula_metrics.dashboard.student_profile'].generate_student_profile(
                student_id=student_id,
                role_info=role_info
            )
            return _render('aula_metrics.dashboard_page_base', values)
        except Exception as e:
            error_msg = str(e)
            if 'permiso' in error_msg.lower() or 'access' in error_msg.lower():
                return _render('aula_metrics.dashboard_access_denied', {'message': error_msg})
            return _render('aula_metrics.dashboard_error_page', {
                'error_title': 'Error al generar el perfil',
                'error_message': error_msg,
            })

    @http.route('/aulametrics/student/<int:student_id>/informe_compuesto',
                type='http', auth='user', methods=['GET'])
    def student_composite_report(self, student_id, **kwargs):
        """
        Genera un informe PDF compuesto con resultados de cuestionarios oficiales
        filtrado por evaluaciones y cuestionarios seleccionados.

        Parámetros GET (repetibles):
            evaluation_ids: IDs de evaluaciones a incluir
            survey_ids:     IDs de cuestionarios a incluir
        """
        from datetime import date as _date

        role_info = self._detect_user_role()

        # Modo directo: IDs de resultado ya seleccionados (nuevo flujo desde la barra flotante)
        result_ids = [
            int(x) for x in request.httprequest.args.getlist('result_ids')
            if x.strip().lstrip('-').isdigit()
        ]

        # Modo legado: filtro por evaluación + cuestionario
        evaluation_ids = [
            int(x) for x in request.httprequest.args.getlist('evaluation_ids')
            if x.strip().lstrip('-').isdigit()
        ]
        survey_ids = [
            int(x) for x in request.httprequest.args.getlist('survey_ids')
            if x.strip().lstrip('-').isdigit()
        ]

        if not result_ids and (not evaluation_ids or not survey_ids):
            return _render('aula_metrics.dashboard_error_page', {
                'error_title':   'Parámetros inválidos',
                'error_message': 'Seleccione al menos un resultado para generar el informe.',
            })

        student = request.env['res.partner'].sudo().browse(student_id)
        if not student.exists() or not getattr(student, 'is_student', False):
            return request.not_found()

        if not role_service.can_access_student(role_info, student):
            return _render('aula_metrics.dashboard_access_denied', {
                'message': 'No tiene permisos para ver este perfil.',
            })

        try:
            env = request.env

            if result_ids:
                results_ordered = env['aula_metrics.survey_result'].search([
                    ('id',             'in', result_ids),
                    ('student_id',     '=', student_id),
                    ('is_aulametrics', '=', True),
                ], order='evaluation_id, survey_id, completed_at asc')
            else:
                results_ordered = env['aula_metrics.survey_result'].search([
                    ('student_id',     '=', student_id),
                    ('is_aulametrics', '=', True),
                    ('evaluation_id',  'in', evaluation_ids),
                    ('survey_id',      'in', survey_ids),
                ], order='evaluation_id, survey_id, completed_at asc')

            pages              = []
            eval_names_seen    = []
            survey_titles_seen = []

            for r in results_ordered:
                ev_name    = r.evaluation_id.name if r.evaluation_id else 'Sin evaluación'
                survey_ttl = r.survey_id.title or ''
                if ev_name not in eval_names_seen:
                    eval_names_seen.append(ev_name)
                if survey_ttl not in survey_titles_seen:
                    survey_titles_seen.append(survey_ttl)
                page_data = r.get_report_data()
                page_data['evaluation_name'] = ev_name
                pages.append(page_data)

            report_data = {
                'student_name':    student.name or '',
                'student_group':   student.academic_group_id.name if student.academic_group_id else '',
                'generated_date':  _date.today().strftime('%d/%m/%Y'),
                'evaluation_names': eval_names_seen,
                'survey_titles':   survey_titles_seen,
                'pages':           pages,
            }

            pdf_bytes, _ = env['ir.actions.report'].sudo()._render_qweb_pdf(
                'aula_metrics.report_student_composite',
                [student_id],
                data=report_data,
            )

            import unicodedata, re
            def _slug(s):
                s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
                return re.sub(r'[^\w]+', '_', s).strip('_')
            _alumno = _slug(student.name or 'alumno')
            _grupo  = _slug(student.academic_group_id.name if student.academic_group_id else '')
            _fecha  = _date.today().strftime('%Y%m%d')
            filename = f'{_alumno}_{_grupo}_{_fecha}.pdf' if _grupo else f'{_alumno}_{_fecha}.pdf'
            return request.make_response(
                pdf_bytes,
                headers=[
                    ('Content-Type',        'application/pdf'),
                    ('Content-Disposition', f'inline; filename="{filename}"'),
                ],
            )

        except Exception as e:
            return _render('aula_metrics.dashboard_error_page', {
                'error_title':   'Error al generar el informe compuesto',
                'error_message': str(e),
            })

    def _parse_hub_filters(self, kwargs):
        """Parsea los parámetros GET a un dict de filtros (SIMPLIFICADO: solo evaluaciones)."""
        filters = {
            'evaluation_ids': [],
        }

        # Solo evaluaciones (filtro maestro del que se derivan métricas y grupos)
        if kwargs.get('evaluation_ids'):
            try:
                filters['evaluation_ids'] = [int(e) for e in kwargs['evaluation_ids'].split(',') if e.strip().isdigit()]
            except (ValueError, AttributeError):
                pass

        return filters

    def _apply_role_restrictions(self, filters, role_info):
        """
        Aplica restricciones de rol a los filtros.
        Con el sistema simplificado (solo filtro de evaluaciones), 
        ya no es necesario filtrar por grupos aquí.
        Las restricciones de rol se aplican a nivel de modelo.
        """
        # El método ahora es pass-through
        # Las restricciones de datos por rol se manejan en el modelo generate_dashboard()
        return filters

