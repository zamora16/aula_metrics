# -*- coding: utf-8 -*-
"""
Estilos CSS exclusivos del perfil individual de alumno.

Separado de dashboard_styles.py para mantener cada archivo en un tamaño
manejable.  Se consume únicamente desde DashboardStudentProfile a través de
get_profile_styles().
"""


def get_profile_styles():
    """Estilos CSS exclusivos del perfil individual de alumno.

    Layout de 3 capas sticky (cabecera, KPI strip, pestañas) + drawer lateral.
    Se concatena a get_common_styles() en las vistas de perfil.
    """
    return """
        <style>
            /* ── Reset wrapper y ocultación de topbar estándar ─────────────── */
            .content-wrapper { padding: 0 !important; }
            /* El perfil tiene su propio encabezado sticky; la topbar estándar sobra */
            .main-content > .topbar { display: none !important; }

            /* ── Variables de altura de capas sticky ───────────────────── */
            :root {
                --am-l1: 64px;
                --am-l2: 108px;
                --am-l3: 45px;
            }

            /* ── Capas sticky ───────────────────────────────────────────── */
            .am-sticky-l1 {
                position: sticky; top: 0; z-index: 60;
                background: var(--am-surface);
                border-bottom: 1px solid var(--am-border);
                box-shadow: 0 2px 6px rgba(0,0,0,0.06);
                padding: 16px 40px;
                min-height: var(--am-l1);
                display: flex; align-items: center;
            }
            .am-sticky-l1 > .d-flex { width: 100%; }
            .am-sticky-l2 {
                position: sticky; top: var(--am-l1); z-index: 59;
                background: var(--am-bg);
                border-bottom: 1px solid var(--am-border);
                padding: 12px 40px;
                height: var(--am-l2);
                display: flex; align-items: center;
            }
            .am-sticky-l3 {
                position: sticky;
                top: calc(var(--am-l1) + var(--am-l2));
                z-index: 58;
                background: var(--am-surface);
                border-bottom: 2px solid var(--am-border);
                padding: 0 32px;
            }

            /* ── Cabecera del alumno (capa 1) ───────────────────────────── */
            .am-avatar-circle {
                width: 44px; height: 44px; border-radius: 50%;
                background: linear-gradient(135deg, var(--am-primary) 0%, var(--am-accent) 100%);
                border: 2px solid rgba(255,255,255,0.8);
                display: flex; align-items: center; justify-content: center;
                flex-shrink: 0; color: white; font-size: 18px;
                box-shadow: 0 2px 8px rgba(15,76,129,0.3);
            }
            .am-student-name {
                font-size: 18px; font-weight: 800; color: var(--am-text);
                line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            }
            .am-student-meta {
                font-size: 12px; color: var(--am-muted);
            }
            .am-meta-sep { margin: 0 6px; }
            .am-sticky-l1 a.btn {
                padding: 5px 12px; font-size: 12px; border: 1px solid var(--am-border);
                background: transparent; color: var(--am-muted); border-radius: 7px;
            }
            .am-sticky-l1 a.btn:hover { background: var(--am-bg); color: var(--am-text); }

            /* ── KPI strip (capa 2) ─────────────────────────────────────── */
            .am-kpi-strip {
                display: flex; gap: 16px; align-items: stretch;
                width: 100%;
            }
            .kpi-card {
                background: white;
                border-left: 3px solid var(--am-border);
                border-radius: 12px;
                box-shadow: 0 1px 4px rgba(15, 30, 54, 0.06);
                padding: 10px 20px;
                flex: 1;
                display: flex; flex-direction: column; justify-content: center;
                align-items: center; text-align: center; gap: 2px;
                transition: box-shadow 0.15s, transform 0.15s;
            }
            .kpi-card:hover {
                box-shadow: 0 4px 16px rgba(15, 30, 54, 0.10);
                transform: translateY(-1px);
            }
            .kpi-label {
                font-size: 11px; font-weight: 700; color: var(--am-muted);
                text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 4px;
            }
            .kpi-value {
                font-family: 'JetBrains Mono', monospace;
                font-size: 28px; font-weight: 700;
                letter-spacing: -0.02em; line-height: 1;
                color: var(--am-text); margin: 2px 0;
            }
            .kpi-value--group {
                font-size: 20px; font-weight: 700;
                letter-spacing: 0; line-height: 1.25;
                font-family: inherit;
            }
            .kpi-value--danger { color: var(--am-danger); }
            .kpi-description {
                font-size: 12px; color: var(--am-muted); font-weight: 400;
            }
            /* ── Pestañas principales (capa 3) ──────────────────────────── */
            .am-main-tab-bar {
                display: flex; gap: 0; align-items: flex-end; height: var(--am-l3);
            }
            .am-main-tab {
                background: none; border: none;
                border-bottom: 3px solid transparent;
                padding: 10px 20px; margin-right: 4px;
                font-size: 13px; font-weight: 500; color: var(--am-muted);
                cursor: pointer; transition: all 0.15s; white-space: nowrap;
                border-radius: 0; line-height: 1;
            }
            .am-main-tab:hover  { color: var(--am-primary); }
            .am-main-tab.active {
                color: var(--am-primary); font-weight: 600;
                border-bottom-color: var(--am-primary);
            }

            /* ── Cuerpo de pestañas ─────────────────────────────────────── */
            .am-tabs-body { padding-bottom: 80px; }
            .am-tab-pane  { display: none; padding: 24px 32px; }
            .am-tab-pane.am-show { display: block; }

            /* ── Sub-pestañas ───────────────────────────────────────────── */
            .am-subtab-bar {
                display: flex; gap: 0; border-bottom: 1px solid var(--am-border);
                margin-bottom: 24px;
            }
            .am-subtab {
                background: none; border: none;
                border-bottom: 2px solid transparent; margin-bottom: -1px;
                padding: 8px 16px; font-size: 13px; font-weight: 500;
                color: var(--am-muted); cursor: pointer; transition: all 0.15s;
            }
            .am-subtab:hover  { color: var(--am-primary); }
            .am-subtab.active {
                color: var(--am-primary); font-weight: 600;
                border-bottom-color: var(--am-primary);
            }
            .am-subpane { display: none; }
            .am-subpane.am-show { display: block; }

            /* ── Tarjeta de sección (reemplaza .card) ───────────────────── */
            .am-section-card {
                background: var(--am-surface);
                border-radius: 14px; margin-bottom: 24px; overflow: hidden;
                box-shadow: 0 1px 4px rgba(15, 30, 54, 0.06);
            }
            .am-section-card__header {
                padding: 16px 20px; border-bottom: 1px solid var(--am-border);
                display: flex; flex-direction: column; gap: 2px;
            }
            .am-section-card__title { font-size: 15px; font-weight: 700; color: var(--am-text); }
            .am-section-card__sub   { font-size: 12px; color: var(--am-muted); }
            .am-section-card__body  { padding: 20px; }

            /* ── Compatibility: card classes still used elsewhere ────────── */
            .card {
                background: var(--am-surface);
                border-radius: 14px; margin-bottom: 24px; overflow: hidden;
                box-shadow: 0 1px 4px rgba(15, 30, 54, 0.06);
            }
            .card-header {
                padding: 16px 20px; border-bottom: 1px solid var(--am-border);
                background: var(--am-surface);
            }
            .card-title        { font-size: 15px; font-weight: 600; color: var(--am-text); margin: 0; }
            .card-title-sm     { font-size: 14px; font-weight: 600; color: var(--am-text); margin: 0; }
            .card-subtitle     { font-size: 12px; color: var(--am-muted); margin: 3px 0 0; font-weight: 400; }
            .card-body         { padding: 20px; }

            /* ── Tarjeta de evaluación ───────────────────────────────────── */
            .am-eval-card {
                background: var(--am-surface);
                border-radius: 12px; margin-bottom: 16px; overflow: hidden;
                box-shadow: 0 1px 3px rgba(15, 30, 54, 0.05);
            }
            .am-eval-card__header {
                display: flex; align-items: center; gap: 8px;
                padding: 8px 18px; background: var(--am-light);
                border-bottom: 1px solid var(--am-border);
            }
            .am-eval-card__header label > span {
                font-size: 11px !important; font-weight: 700 !important;
                color: var(--am-muted) !important; text-transform: uppercase !important;
                letter-spacing: 0.08em !important;
            }
            .am-eval-check { flex-shrink: 0; cursor: pointer; }

            /* ── Filas de cuestionario ───────────────────────────────────── */
            .am-survey-row {
                display: flex; align-items: center; gap: 10px;
                padding: 13px 18px; border-bottom: 1px solid var(--am-border);
                transition: background 0.12s;
            }
            .am-survey-row:last-child { border-bottom: none; }
            .am-survey-row:hover { background: var(--am-bg); }
            .am-row-dot {
                width: 9px; height: 9px; min-width: 9px;
                border-radius: 50%; display: inline-block; flex-shrink: 0;
            }
            .am-row-title {
                flex: 1; font-size: 13px; font-weight: 700; color: var(--am-text);
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;
            }
            .am-row-score { font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; flex-shrink: 0; }
            .am-row-max   { font-size: 10px; font-weight: 400; color: var(--am-muted); }
            .am-row-badge { font-size: 10px; padding: 3px 8px; border-radius: 4px;
                            white-space: nowrap; flex-shrink: 0; }
            .am-ver-detalle {
                background: white; border: 1px solid var(--am-border); border-radius: 6px;
                padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;
                color: var(--am-muted); white-space: nowrap; flex-shrink: 0;
                transition: all 0.15s;
            }
            .am-ver-detalle:hover {
                border-color: var(--am-primary); color: var(--am-primary);
                background: var(--am-primary-100);
            }
            .am-row-check { flex-shrink: 0; cursor: pointer; }

            /* ── Tablas ─────────────────────────────────────────────────── */
            table        { width: 100%; border-collapse: collapse; font-size: 14px; }
            thead        { background: var(--am-light); border-bottom: 1px solid var(--am-border); }
            th           { padding: 9px 14px; text-align: left; font-weight: 800;
                           color: var(--am-muted); font-size: 10px; text-transform: uppercase;
                           letter-spacing: 0.08em; }
            td           { padding: 10px 14px; border-bottom: 1px solid var(--am-border); color: var(--am-text); font-size: 12px; }
            td:first-child { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--am-muted); }
            tr:last-child td { border-bottom: none; }
            tbody tr:hover   { background: var(--am-row-hover); }

            /* ── Barra flotante de informe ───────────────────────────────── */
            .am-float-bar {
                position: fixed; bottom: 0; left: 260px; right: 0; z-index: 1050;
                background: var(--am-surface-inverse); color: #fff;
                display: flex; align-items: center; gap: 12px; padding: 12px 32px;
                box-shadow: 0 -4px 20px rgba(0,0,0,0.22);
                transform: translateY(100%); transition: transform 0.22s ease;
            }
            .am-float-bar.am-float-bar--on { transform: translateY(0); }
            .am-float-count {
                font-weight: 700; font-size: 12px; white-space: nowrap;
                background: var(--am-primary); color: #fff;
                padding: 2px 10px; border-radius: 12px;
            }
            .am-float-tags {
                display: flex; gap: 6px; flex-wrap: wrap; flex: 1; min-width: 0;
            }
            .am-float-tag {
                display: inline-flex; align-items: center; gap: 2px;
                background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.9);
                padding: 2px 8px; border-radius: 4px; font-size: 11px;
            }
            .am-float-actions { display: flex; gap: 8px; flex-shrink: 0; }
            .am-btn-ghost {
                background: none; border: 1px solid rgba(255,255,255,0.3);
                color: rgba(255,255,255,0.8); padding: 5px 14px; border-radius: 6px;
                font-size: 12px; cursor: pointer; transition: all 0.15s;
            }
            .am-btn-ghost:hover { border-color: rgba(255,255,255,.7); color: #fff; }
            .am-btn-primary-inv {
                background: var(--am-primary); border: none; color: #fff;
                padding: 5px 14px; border-radius: 6px; font-size: 12px;
                font-weight: 600; cursor: pointer; transition: opacity 0.15s;
            }
            .am-btn-primary-inv:hover { opacity: 0.88; }

            /* ── Drawer lateral ─────────────────────────────────────────── */
            .am-drawer {
                position: fixed; inset: 0; z-index: 1100;
                pointer-events: none;
            }
            .am-drawer--open { pointer-events: all; }
            .am-drawer__overlay {
                position: absolute; inset: 0;
                background: rgba(0,0,0,0); transition: background 0.22s;
            }
            .am-drawer--open .am-drawer__overlay { background: rgba(0,0,0,0.35); }
            .am-drawer__panel {
                position: absolute; top: 0; right: 0;
                width: 560px; max-width: 96vw; height: 100%;
                background: var(--am-surface);
                box-shadow: -6px 0 24px rgba(0,0,0,0.12);
                display: flex; flex-direction: column;
                transform: translateX(100%); transition: transform 0.22s ease;
            }
            .am-drawer--open .am-drawer__panel { transform: translateX(0); }
            .am-drawer__header {
                padding: 16px 20px; border-bottom: 1px solid var(--am-border);
                display: flex; align-items: flex-start; gap: 10px; flex-shrink: 0;
                background: var(--am-surface);
            }
            .am-drawer__title {
                flex: 1; font-size: 18px; font-weight: 800; color: var(--am-text);
                margin: 0; line-height: 1.2;
            }
            .am-drawer__close {
                width: 30px; height: 30px; border-radius: 7px;
                border: 1px solid var(--am-border); background: transparent;
                color: var(--am-muted); cursor: pointer; font-size: 14px;
                display: flex; align-items: center; justify-content: center;
                flex-shrink: 0; transition: all 0.12s;
            }
            .am-drawer__close:hover { background: #fef2f2; color: var(--am-danger); border-color: #fecaca; }
            .am-drawer__body {
                flex: 1; overflow-y: auto; padding: 24px;
                background: var(--am-bg);
            }
            .am-drawer__footer {
                padding: 12px 20px; border-top: 1px solid var(--am-border);
                display: flex; justify-content: flex-end; flex-shrink: 0;
                background: var(--am-surface);
            }
            .am-drawer__footer a.btn-primary, .am-drawer__footer .btn-primary {
                background: var(--am-primary); color: white; border: none;
                border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 700;
                text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
                transition: background 0.15s;
            }
            .am-drawer__footer a.btn-primary:hover, .am-drawer__footer .btn-primary:hover {
                background: var(--am-primary-600);
            }
            /* ── Contenido del drawer ─────────────────────────────────── */
            .am-drawer__date {
                font-size: 11px; font-family: 'JetBrains Mono', monospace;
                color: var(--am-muted); border-bottom: 1px solid var(--am-border);
                padding-bottom: 16px; margin-bottom: 20px;
            }
            .am-drawer-interp {
                background: #fffbeb; border: 1px solid #fde68a;
                border-left: 4px solid var(--am-warning); border-radius: 9px;
                padding: 12px 16px; margin-bottom: 16px;
            }
            .am-drawer-interp__label {
                font-size: 10px; font-weight: 800; text-transform: uppercase;
                letter-spacing: 0.08em; color: var(--am-warning-dark); margin-bottom: 6px; display: block;
            }
            .am-drawer-interp__text { font-size: 12px; line-height: 1.65; color: var(--am-warning-text); margin: 0; }
            .am-drawer-legend {
                display: flex; gap: 16px; align-items: center;
                padding: 8px 12px; background: var(--am-light); border-radius: 8px;
                border: 1px solid var(--am-border); margin-bottom: 16px;
            }
            .am-drawer-legend__item {
                display: flex; align-items: center;
                font-size: 11px; font-weight: 600; color: var(--am-muted);
            }
            .am-drawer-legend__line {
                display: inline-block; width: 2px; height: 14px;
                border-radius: 1px; vertical-align: middle; margin-right: 5px; flex-shrink: 0;
            }
            .am-drawer-section-label {
                font-size: 10px; font-weight: 800; text-transform: uppercase;
                letter-spacing: 0.1em; color: var(--am-muted); margin-bottom: 12px; display: block;
            }
            .am-bar-row {
                display: flex; align-items: center; gap: 12px;
                margin-bottom: 8px;
            }
            .am-bar-row--total {
                border-top: 2px solid var(--am-border); padding-top: 8px; margin-top: 10px;
            }
            .am-bar-row__label {
                min-width: 150px; font-size: 12px; font-weight: 600;
                color: var(--am-text); flex-shrink: 0;
            }
            .am-bar-row--total .am-bar-row__label { font-size: 13px; font-weight: 800; }
            /* am-bar-row__track, am-bar-fill, am-bar-row__score: eliminados.
               El drawer usa ahora Chart.js (horizontal bar + scatter). */
        </style>"""
