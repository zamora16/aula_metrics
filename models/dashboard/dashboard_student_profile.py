# -*- coding: utf-8 -*-
"""
Dashboard Student Profile — Perfil individual longitudinal de alumno.

La clase base define la API pública y los métodos de datos/orquestación.
Los métodos de renderizado están divididos en:
  - dashboard_student_sections.py  (alertas, participaciones, cualitativos, lista)
  - dashboard_student_surveys.py   (cuestionarios oficiales AulaMetrics)
  - dashboard_student_charts.py    (gráficos de evolución y resumen)
"""
from odoo import models, api, fields
import pandas as pd

from markupsafe import Markup
from ...utils import dashboard_styles, dashboard_profile_styles, dashboard_helpers, palette, role_service


class DashboardStudentProfile(models.TransientModel):
    _name = 'aula_metrics.dashboard.student_profile'
    _description = 'Generador de Perfil Individual de Estudiante'

    # ──────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def generate_student_profile(self, student_id, role_info=None):
        """
        Genera el dashboard de perfil individual de un estudiante.

        Returns:
            dict: Valores para renderizado QWeb via 'aula_metrics.dashboard_page_base'
        """
        if role_info is None:
            role_info = {'role': 'admin', 'anonymize_students': False}

        student = self.env['res.partner'].browse(student_id)
        if not student.exists():
            return self._error_html("Estudiante no encontrado")

        if not self._can_access_student(student, role_info):
            return self._error_html("No tiene permisos para ver este perfil")

        metrics = self._get_student_metrics(student_id)
        if not metrics:
            return self._build_empty_profile(student, role_info)

        df = self._prepare_metrics_dataframe(metrics)

        # Métricas de cuestionarios del centro (excluye oficiales AulaMetrics)
        centro_metrics = self._get_centro_metrics(student_id)
        df_centro      = self._prepare_metrics_dataframe(centro_metrics) if centro_metrics else pd.DataFrame()

        evolution_charts      = self._generate_evolution_chartjs(df_centro, student)
        radar_chart           = self._generate_radar_chart(df_centro, student)
        kpis                  = self._generate_student_kpis(student, df)
        alerts_html           = self._get_student_alerts_html(student_id)
        alerts_history_html   = self._get_student_alerts_history_html(student_id)
        participations_html   = self._get_participations_html(student_id)
        qualitative_html      = self._get_qualitative_responses_html(student_id)
        official_surveys_data = self._get_official_surveys_html(student_id)

        return self._build_profile_html_chartjs(
            student, role_info, kpis,
            evolution_charts, radar_chart,
            alerts_html, alerts_history_html,
            participations_html, qualitative_html,
            official_surveys_data=official_surveys_data,
        )

    @api.model
    def generate_students_list(self, role_info=None):
        """
        Genera una lista HTML de estudiantes accesibles según el rol.

        Returns:
            dict: Valores para renderizado QWeb via 'aula_metrics.dashboard_page_base'
        """
        if role_info is None:
            role_info = {'role': 'admin'}

        Partner  = self.env['res.partner']
        domain   = [('is_student', '=', True)]
        filtered = role_service.apply_group_filter(domain, role_info, field='academic_group_id')
        if filtered is None:
            students = Partner.browse([])
        else:
            students = Partner.search(filtered, order='name')

        return self._build_students_list_html(students, role_info)

    # ──────────────────────────────────────────────────────────────────────
    # Data access
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _can_access_student(self, student, role_info):
        return role_service.can_access_student(role_info, student)

    def _get_student_metrics(self, student_id):
        """Obtiene todas las métricas del estudiante ordenadas por fecha."""
        return self.env['aula_metrics.metric_value'].search([
            ('student_id', '=', student_id)
        ], order='timestamp desc')

    def _get_centro_metrics(self, student_id):
        """Métricas de encuestas del centro (excluye oficiales AulaMetrics no-adhoc)."""
        return self.env['aula_metrics.metric_value'].search([
            ('student_id', '=', student_id),
            '|',
            ('survey_id.is_aulametrics', '=', False),
            ('survey_id.is_adhoc', '=', True),
        ], order='timestamp desc')

    def _prepare_metrics_dataframe(self, metrics):
        """Construye el DataFrame de métricas del alumno para análisis longitudinal."""
        if not metrics:
            return pd.DataFrame()
        return pd.DataFrame(dashboard_helpers.metric_values_to_records(metrics))

    # ──────────────────────────────────────────────────────────────────────
    # KPIs
    # ──────────────────────────────────────────────────────────────────────

    def _generate_student_kpis(self, student, df):
        """Genera las 4 tarjetas KPI del estudiante."""
        total_evals   = df['evaluation_id'].nunique() if not df.empty else 0
        group_name    = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        alerts_count  = self.env['aula_metrics.alert'].search_count([
            ('student_id', '=', student.id),
            ('status',     '=', 'active'),
        ])

        participations  = self.env['aula_metrics.participation'].search([
            ('student_id', '=', student.id),
        ])
        total_parts     = len(participations)
        completed_parts = len(participations.filtered(lambda p: p.state == 'completed'))
        participation_pct = f'{round(completed_parts / total_parts * 100)}%' if total_parts else '—'

        alert_cls = 'kpi-value kpi-value--danger' if alerts_count > 0 else 'kpi-value'
        kpis = [
            f'<div class="kpi-card"><div class="kpi-label">Evaluaciones</div><div class="kpi-value">{total_evals}</div><div class="kpi-description">Completadas</div></div>',
            f'<div class="kpi-card"><div class="kpi-label">Participación</div><div class="kpi-value">{participation_pct}</div><div class="kpi-description">Encuestas respondidas</div></div>',
            f'<div class="kpi-card"><div class="kpi-label">Grupo</div><div class="kpi-value kpi-value--group">{group_name}</div><div class="kpi-description">Académico</div></div>',
            f'<div class="kpi-card"><div class="kpi-label">Alertas</div><div class="{alert_cls}">{alerts_count}</div><div class="kpi-description">Activas</div></div>',
        ]
        return '\n'.join(kpis)

    # ──────────────────────────────────────────────────────────────────────
    # Page builders
    # ──────────────────────────────────────────────────────────────────────

    def _build_empty_profile(self, student, role_info):
        """Contexto para perfil sin métricas."""
        group_name        = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        alerts_html       = self._get_student_alerts_html(student.id)
        alerts_history    = self._get_student_alerts_history_html(student.id)

        content_html = f"""
        <div class="container-fluid">
            <div class="card" style="text-align:center;padding:60px 40px;">
                <i class="fa-solid fa-chart-line" style="font-size:80px;color:var(--am-light);margin-bottom:24px;"></i>
                <h3 style="color:var(--am-muted);margin-bottom:12px;">Sin datos de métricas disponibles</h3>
                <p style="color:var(--am-muted);font-size:15px;">Complete una evaluación para comenzar a ver datos.</p>
            </div>
            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header"><h5 class="card-title">Alertas Activas</h5></div>
                        <div class="card-body">
                            {alerts_html}
                            <div class="mt-3">
                                <button class="btn btn-outline-secondary btn-sm w-100" type="button"
                                        data-bs-toggle="collapse" data-bs-target="#alertsHistory">
                                    <i class="fa-solid fa-clock-rotate-left me-2"></i>Ver Historial de Alertas
                                </button>
                                <div class="collapse mt-3" id="alertsHistory">
                                    <hr>
                                    <h6 class="text-muted mb-3">Historial de Alertas Resueltas/Descartadas</h6>
                                    {alerts_history}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>"""

        return {
            'page_title':           f'Perfil de {student.name}',
            'css_styles':           Markup(dashboard_styles.get_common_styles() + self._profile_styles_chartjs()),
            'head_extra':           Markup(''),
            'role_info':            role_info,
            'active_section':       'profiles',
            'topbar_title':         student.name,
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-user me-2"></i>{group_name} · {fields.Date.today().strftime("%d/%m/%Y")}'
            ),
            'topbar_extra_actions': Markup(
                '<a href="/aulametrics/students" class="btn btn-outline-secondary btn-sm">'
                '<i class="fa-solid fa-users"></i> Lista</a>'
            ),
            'content_html':         Markup(content_html),
            'scripts_html':         Markup(''),
        }

    def _build_profile_html_chartjs(self, student, role_info, kpis, evolution, radar,
                                     alerts, alerts_history, participations,
                                     qualitative='', official_surveys_data=None):
        """
        Contexto completo para el perfil con layout rediseñado:
        3 capas sticky + 4 pestañas principales + barra flotante + drawer lateral.
        """
        if official_surveys_data is None:
            official_surveys_data = {
                'timeline_html': '', 'evolution_html': '',
                'has_surveys': False, 'student_id': student.id,
            }

        group_name     = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        sid            = student.id
        timeline_html  = official_surveys_data.get('timeline_html', '')
        evol_ofic_html = official_surveys_data.get('evolution_html', '')
        has_surveys    = official_surveys_data.get('has_surveys', False)

        chart_libs = (
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n'
            '<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>'
        )

        # ── Contenido de las sub-pestañas ──────────────────────────────
        ofic_empty = """
            <div class="text-center py-5">
                <i class="fa-solid fa-clipboard-list fa-3x mb-3" style="color:var(--am-border);"></i>
                <p class="text-muted mb-0">Este alumno aún no tiene resultados de cuestionarios oficiales.</p>
            </div>"""
        centro_quant_content = radar or """
            <div class="text-center py-5">
                <i class="fa-solid fa-chart-bar fa-3x mb-3" style="color:var(--am-border);"></i>
                <p class="text-muted mb-0">No hay métricas de cuestionarios del centro registradas.</p>
            </div>"""
        evol_ofic_content = evol_ofic_html or """
            <div class="text-center py-5">
                <i class="fa-solid fa-chart-line fa-3x mb-3" style="color:var(--am-border);"></i>
                <p class="text-muted mb-0">Se necesitan al menos dos evaluaciones para mostrar la evolución.</p>
            </div>"""
        evol_centro_content = evolution or """
            <div class="text-center py-5">
                <i class="fa-solid fa-chart-bar fa-3x mb-3" style="color:var(--am-border);"></i>
                <p class="text-muted mb-0">No hay datos de evolución de métricas del centro disponibles.</p>
            </div>"""
        cual_content = qualitative or """
            <div class="text-center py-5">
                <i class="fa-solid fa-message fa-3x mb-3" style="color:var(--am-border);"></i>
                <p class="text-muted mb-0">No hay respuestas cualitativas registradas.</p>
            </div>"""

        content_html = f"""

        <!-- ═══ CAPA 1: Encabezado del alumno ════════════════════════════ -->
        <div class="am-sticky-l1">
            <div class="d-flex align-items-center gap-3">
                <div class="am-avatar-circle">
                    <i class="fa-solid fa-user"></i>
                </div>
                <div style="min-width:0;flex:1;display:flex;align-items:center;gap:16px;">
                    <div class="am-student-name" style="flex-shrink:1;min-width:0;">{student.name}</div>
                    <div class="am-student-meta" style="flex-shrink:0;white-space:nowrap;">
                        <i class="fa-solid fa-users me-1"></i>{group_name}
                        <span class="am-meta-sep">·</span>
                        <i class="fa-solid fa-calendar me-1"></i>{fields.Date.today().strftime('%d/%m/%Y')}
                    </div>
                </div>
                <div class="flex-shrink-0">
                    <a href="/aulametrics/students" class="btn btn-outline-secondary btn-sm">
                        <i class="fa-solid fa-arrow-left me-1"></i>Lista
                    </a>
                </div>
            </div>
        </div>

        <!-- ═══ CAPA 2: Banda de KPIs ════════════════════════════════════ -->
        <div class="am-sticky-l2">
            <div class="am-kpi-strip">{kpis}</div>
        </div>

        <!-- ═══ CAPA 3: Barra de pestañas principales ════════════════════ -->
        <div class="am-sticky-l3">
            <div class="am-main-tab-bar">
                <button class="am-main-tab active" data-tab="cuant" onclick="amTab('cuant',this)">
                    <i class="fa-solid fa-chart-column me-1"></i>Datos cuantitativos
                </button>
                <button class="am-main-tab" data-tab="cual" onclick="amTab('cual',this)">
                    <i class="fa-solid fa-quote-left me-1"></i>Datos cualitativos
                </button>
                <button class="am-main-tab" data-tab="evol" onclick="amTab('evol',this)">
                    <i class="fa-solid fa-chart-line me-1"></i>Evolución global
                </button>
                <button class="am-main-tab" data-tab="alertas" onclick="amTab('alertas',this)">
                    <i class="fa-solid fa-bell me-1"></i>Alertas
                </button>
            </div>
        </div>

        <!-- ═══ CONTENIDO DE PESTAÑAS ════════════════════════════════════ -->
        <div class="am-tabs-body">

            <!-- ── Tab: Datos cuantitativos ──────────────────────────── -->
            <div id="am-pane-cuant" class="am-tab-pane am-show">
                <div class="am-subtab-bar">
                    <button class="am-subtab active" data-group="cuant" data-sub="ofic"
                            onclick="amSubtab('cuant','ofic',this)">
                        <i class="fa-solid fa-clipboard-check me-1"></i>Cuestionarios Oficiales
                    </button>
                    <button class="am-subtab" data-group="cuant" data-sub="centro"
                            onclick="amSubtab('cuant','centro',this)">
                        <i class="fa-solid fa-school me-1"></i>Cuestionarios del Centro
                    </button>
                </div>
                <div id="am-cuant-ofic" class="am-subpane am-show" data-group="cuant">
                    {timeline_html if has_surveys else ofic_empty}
                    <div class="mt-4">
                        <div class="am-section-card">
                            <div class="am-section-card__header">
                                <span class="am-section-card__title">Histórico de Participación</span>
                                <span class="am-section-card__sub">Encuestas completadas</span>
                            </div>
                            <div class="am-section-card__body">{participations}</div>
                        </div>
                    </div>
                </div>
                <div id="am-cuant-centro" class="am-subpane" data-group="cuant">
                    {centro_quant_content}
                </div>
            </div>

            <!-- ── Tab: Datos cualitativos ───────────────────────────── -->
            <div id="am-pane-cual" class="am-tab-pane">
                <div class="am-section-card">
                    <div class="am-section-card__header">
                        <span class="am-section-card__title">Respuestas Cualitativas</span>
                        <span class="am-section-card__sub">Textos y comentarios abiertos</span>
                    </div>
                    <div class="am-section-card__body">{cual_content}</div>
                </div>
            </div>

            <!-- ── Tab: Evolución global ─────────────────────────────── -->
            <div id="am-pane-evol" class="am-tab-pane">
                <div class="am-subtab-bar">
                    <button class="am-subtab active" data-group="evol" data-sub="ofic"
                            onclick="amSubtab('evol','ofic',this)">
                        <i class="fa-solid fa-clipboard-check me-1"></i>Cuestionarios Oficiales
                    </button>
                    <button class="am-subtab" data-group="evol" data-sub="centro"
                            onclick="amSubtab('evol','centro',this)">
                        <i class="fa-solid fa-school me-1"></i>Cuestionarios del Centro
                    </button>
                </div>
                <div id="am-evol-ofic" class="am-subpane am-show" data-group="evol">
                    {evol_ofic_content}
                </div>
                <div id="am-evol-centro" class="am-subpane" data-group="evol">
                    {evol_centro_content}
                </div>
            </div>

            <!-- ── Tab: Alertas ──────────────────────────────────────── -->
            <div id="am-pane-alertas" class="am-tab-pane">
                {alerts}
                <div class="mt-3">
                    <button class="btn btn-outline-secondary btn-sm w-100" type="button"
                            data-bs-toggle="collapse"
                            data-bs-target="#am-alerts-hist-{sid}">
                        <i class="fa-solid fa-clock-rotate-left me-2"></i>Ver Historial de Alertas
                    </button>
                    <div class="collapse mt-3" id="am-alerts-hist-{sid}">
                        <hr>
                        <h6 class="text-muted mb-3">Alertas Resueltas / Descartadas</h6>
                        {alerts_history}
                    </div>
                </div>
            </div>

        </div><!-- /.am-tabs-body -->

        <!-- ═══ BARRA FLOTANTE (solo Cuantitativo > Oficiales) ══════════ -->
        <div id="am-float-bar" class="am-float-bar">
            <span id="am-float-count" class="am-float-count"></span>
            <div id="am-float-tags" class="am-float-tags"></div>
            <div class="am-float-actions">
                <button type="button" class="am-btn-ghost" onclick="amClear()">
                    <i class="fa-solid fa-xmark me-1"></i>Limpiar
                </button>
                <button type="button" class="am-btn-primary-inv" onclick="amGenerarInforme({sid})">
                    <i class="fa-solid fa-file-pdf me-1"></i>Generar informe
                </button>
            </div>
        </div>

        <!-- ═══ DRAWER LATERAL ═══════════════════════════════════════════ -->
        <div id="am-drawer" class="am-drawer">
            <div class="am-drawer__overlay" onclick="amCloseDrawer()"></div>
            <div class="am-drawer__panel">
                <div class="am-drawer__header">
                    <h6 id="am-drawer-title" class="am-drawer__title">Detalle</h6>
                    <button type="button" class="am-drawer__close" onclick="amCloseDrawer()">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
                <div class="am-drawer__body" id="am-drawer-body"></div>
                <div class="am-drawer__footer" id="am-drawer-footer"></div>
            </div>
        </div>

        <script>
        // ── Pestañas principales ─────────────────────────────────────
        function amTab(tab, btn) {{
            document.querySelectorAll('.am-tab-pane').forEach(function(p) {{
                p.classList.remove('am-show');
            }});
            document.querySelectorAll('.am-main-tab').forEach(function(b) {{
                b.classList.remove('active');
            }});
            var pane = document.getElementById('am-pane-' + tab);
            if (pane) pane.classList.add('am-show');
            if (btn)  btn.classList.add('active');
            amRefreshFloatBar();
        }}

        // ── Sub-pestañas ─────────────────────────────────────────────
        function amSubtab(group, sub, btn) {{
            document.querySelectorAll('[data-group="' + group + '"].am-subpane').forEach(function(p) {{
                p.classList.remove('am-show');
            }});
            var bar = btn ? btn.closest('.am-subtab-bar') : null;
            if (bar) bar.querySelectorAll('.am-subtab').forEach(function(b) {{
                b.classList.remove('active');
            }});
            var el = document.getElementById('am-' + group + '-' + sub);
            if (el) el.classList.add('am-show');
            if (btn) btn.classList.add('active');
            amRefreshFloatBar();
        }}

        // ── Selección de filas ───────────────────────────────────────
        var _amSel = new Map();

        function amOnCheck(cb) {{
            var rid = cb.dataset.rid, title = cb.dataset.title;
            if (cb.checked) _amSel.set(rid, title);
            else            _amSel.delete(rid);
            _amSyncEvalCheckbox(cb);
            _amRenderTags();
            amRefreshFloatBar();
        }}

        // Nivel evaluación: marcar/desmarcar todas las filas del bloque
        function amOnEvalCheck(evalCb) {{
            var cardId = evalCb.dataset.evalCard;
            var card   = document.getElementById(cardId);
            if (!card) return;
            card.querySelectorAll('.am-row-check').forEach(function(cb) {{
                cb.checked = evalCb.checked;
                var rid = cb.dataset.rid, title = cb.dataset.title;
                if (evalCb.checked) _amSel.set(rid, title);
                else                _amSel.delete(rid);
            }});
            _amRenderTags();
            amRefreshFloatBar();
        }}

        // Sincronizar checkbox de evaluación según estado de sus filas
        function _amSyncEvalCheckbox(rowCb) {{
            var card = rowCb.closest('.am-eval-card');
            if (!card) return;
            var rows    = card.querySelectorAll('.am-row-check');
            var total   = rows.length;
            var checked = 0;
            rows.forEach(function(r) {{ if (r.checked) checked++; }});
            var evalCb = card.querySelector('.am-eval-check');
            if (!evalCb) return;
            if (checked === 0) {{
                evalCb.checked       = false;
                evalCb.indeterminate = false;
            }} else if (checked === total) {{
                evalCb.checked       = true;
                evalCb.indeterminate = false;
            }} else {{
                evalCb.checked       = false;
                evalCb.indeterminate = true;
            }}
        }}

        function amClear() {{
            document.querySelectorAll('.am-row-check:checked').forEach(function(cb) {{
                cb.checked = false;
            }});
            document.querySelectorAll('.am-eval-check').forEach(function(cb) {{
                cb.checked = false; cb.indeterminate = false;
            }});
            _amSel.clear();
            _amRenderTags();
            amRefreshFloatBar();
        }}

        function amRemove(rid) {{
            var cb = document.querySelector('.am-row-check[data-rid="' + rid + '"]');
            if (cb) {{ cb.checked = false; _amSyncEvalCheckbox(cb); }}
            _amSel.delete(String(rid));
            _amRenderTags();
            amRefreshFloatBar();
        }}

        function _amRenderTags() {{
            var n = _amSel.size;
            var countEl = document.getElementById('am-float-count');
            if (countEl) countEl.textContent = n + ' seleccionad' + (n === 1 ? 'o' : 'os');
            var tags = document.getElementById('am-float-tags');
            if (!tags) return;
            tags.innerHTML = '';
            _amSel.forEach(function(title, rid) {{
                var t = document.createElement('span');
                t.className = 'am-float-tag';
                t.innerHTML = '<span style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom;display:inline-block;">' + title + '</span>'
                            + '<button type="button" onclick="amRemove(' + rid + ')" style="background:none;border:none;color:rgba(255,255,255,.7);cursor:pointer;padding:0 0 0 4px;font-size:14px;line-height:1;">×</button>';
                tags.appendChild(t);
            }});
        }}

        function amRefreshFloatBar() {{
            var bar       = document.getElementById('am-float-bar');
            if (!bar) return;
            var cuant     = document.getElementById('am-pane-cuant');
            var subOfic   = document.getElementById('am-cuant-ofic');
            var tabActive = cuant   && cuant.classList.contains('am-show');
            var subActive = subOfic && subOfic.classList.contains('am-show');
            if (tabActive && subActive && _amSel.size > 0) {{
                bar.classList.add('am-float-bar--on');
            }} else {{
                bar.classList.remove('am-float-bar--on');
            }}
        }}

        // ── Drawer ───────────────────────────────────────────────────
        function amOpenDrawer(rid) {{
            var body   = document.getElementById('am-drawer-content-' + rid);
            var footer = document.getElementById('am-drawer-footer-'  + rid);
            if (!body) return;
            // Survey title is in the first child with class that has title text
            // We use the card title from the parent row
            var row = document.querySelector('.am-row-check[data-rid="' + rid + '"]');
            var title = row ? row.dataset.title : 'Detalle';
            document.getElementById('am-drawer-title').textContent = title;
            var drawerBody   = document.getElementById('am-drawer-body');
            var drawerFooter = document.getElementById('am-drawer-footer');
            drawerBody.innerHTML   = body.innerHTML;
            drawerFooter.innerHTML = footer ? footer.innerHTML : '';
            document.getElementById('am-drawer').classList.add('am-drawer--open');
            document.body.style.overflow = 'hidden';
            // Inicializar Chart.js desde la config JSON inerte del drawer
            // (evita duplicados de ID y ejecución sobre canvas oculto)
            requestAnimationFrame(function() {{
                var cfgEl  = drawerBody.querySelector('script.am-chart-cfg');
                var canvas = drawerBody.querySelector('canvas.am-chart-canvas');
                if (cfgEl && canvas && typeof Chart !== 'undefined') {{
                    try {{
                        var cfg = JSON.parse(cfgEl.textContent);
                        if (cfg.options && cfg.options.plugins && cfg.options.plugins.tooltip) {{
                            cfg.options.plugins.tooltip.callbacks = {{
                                label: function(ctx) {{
                                    var v = typeof ctx.raw === 'object' ? ctx.raw.x : ctx.raw;
                                    if (v === null || v === undefined) return null;
                                    return ' ' + ctx.dataset.label + ': ' + parseFloat(v).toFixed(1);
                                }}
                            }};
                        }}
                        new Chart(canvas.getContext('2d'), cfg);
                    }} catch(e) {{
                        console.warn('[amDrawer] chart init error:', e);
                    }}
                }}
            }});
        }}

        function amCloseDrawer() {{
            document.getElementById('am-drawer').classList.remove('am-drawer--open');
            document.body.style.overflow = '';
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') amCloseDrawer();
        }});

        // ── Generar informe directo (sin modal) ─────────────────────
        function amGenerarInforme(studentId) {{
            if (_amSel.size === 0) return;
            var url = '/aulametrics/student/' + studentId + '/informe_compuesto?';
            var params = [];
            _amSel.forEach(function(title, rid) {{
                params.push('result_ids=' + encodeURIComponent(rid));
            }});
            window.open(url + params.join('&'), '_blank');
        }}
        </script>"""

        return {
            'page_title':           f'Perfil de {student.name}',
            'css_styles':           Markup(dashboard_styles.get_common_styles() + self._profile_styles_chartjs()),
            'head_extra':           Markup(chart_libs),
            'role_info':            role_info,
            'active_section':       'profiles',
            'topbar_title':         student.name,
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-user me-2"></i>{group_name} · {fields.Date.today().strftime("%d/%m/%Y")}'
            ),
            'topbar_extra_actions': Markup(''),
            'content_html':         Markup(content_html),
            'scripts_html':         Markup(''),
        }

    def _profile_styles_chartjs(self):
        return dashboard_profile_styles.get_profile_styles()

    def _error_html(self, message):
        raise ValueError(message)
