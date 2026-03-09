# -*- coding: utf-8 -*-
"""
Estilos CSS compartidos para todos los dashboards de AulaMetrics
"""
from . import palette


def get_common_styles():
    """
    Retorna los estilos CSS compartidos por todos los dashboards.
    Incluye layout principal, sidebar, topbar, cards, badges, etc.
    """
    root_vars = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

        :root {{
            --am-bg: {palette.UI_BG};
            --am-surface: {palette.UI_SURFACE};
            --am-text: {palette.UI_TEXT};
            --am-primary: {palette.UI_PRIMARY};
            --am-primary-600: {palette.UI_PRIMARY_DARK};
            --am-primary-darker: {palette.UI_PRIMARY_DARKER};
            --am-primary-rgb: {palette.UI_PRIMARY_RGB};
            --am-primary-100: {palette.UI_PRIMARY_LIGHT};
            --am-primary-200: {palette.UI_PRIMARY_200};
            --am-success: {palette.UI_SUCCESS};
            --am-success-dark: {palette.UI_SUCCESS_DARK};
            --am-muted: {palette.UI_MUTED};
            --am-border: {palette.UI_BORDER};
            --am-light: {palette.UI_LIGHT};
            --am-warning: {palette.UI_WARNING};
            --am-danger: {palette.UI_DANGER};
            --am-sidebar-start: {palette.UI_SIDEBAR_START};
            --am-sidebar-end: {palette.UI_SIDEBAR_END};
        }}
    """

    rest_css = """
        /* Reset y base */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--am-bg);
            color: var(--am-text);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        
        /* ==================== LAYOUT PRINCIPAL ==================== */
        .dashboard-layout {
            display: flex;
            min-height: 100vh;
        }
        
        /* ==================== SIDEBAR ==================== */
        .sidebar {
            width: 260px;
            background: var(--am-sidebar-start);
            color: white;
            display: flex;
            flex-direction: column;
            position: fixed;
            height: 100vh;
            left: 0;
            top: 0;
            z-index: 1000;
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }
        
        .sidebar-header {
            padding: 24px 20px;
            font-size: 20px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .sidebar-nav {
            flex: 1;
            padding: 16px 12px;
            overflow-y: auto;
        }
        
        .sidebar-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            color: rgba(255, 255, 255, 0.45);
            text-decoration: none;
            border-radius: 8px;
            margin-bottom: 4px;
            transition: all 0.2s ease;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
        }
        
        .sidebar-item:hover {
            background: rgba(255, 255, 255, 0.06);
            color: rgba(255, 255, 255, 0.8);
        }
        
        .sidebar-item.active {
            background: rgba(255, 255, 255, 0.09);
            color: white;
            border-left: 3px solid var(--am-warning);
        }
        
        .sidebar-item i {
            width: 20px;
            text-align: center;
            font-size: 16px;
        }
        
        .sidebar-footer {
            padding: 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* ==================== MAIN CONTENT ==================== */
        .main-content {
            flex: 1;
            margin-left: 260px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        
        .topbar {
            background: white;
            border-bottom: 1px solid var(--am-border);
            padding: 20px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .topbar h3 {
            font-size: 22px;
            font-weight: 800;
            margin: 0;
            color: var(--am-text);
        }
        
        .breadcrumbs {
            font-size: 13px;
            color: var(--am-muted);
            display: block;
            margin-top: 4px;
        }
        
        .topbar-actions {
            display: flex;
            gap: 12px;
            align-items: center;
        }
        
        .topbar-date {
            color: #64748b;
            font-size: 14px;
        }
        
        .content-wrapper {
            flex: 1;
            padding: 32px;
            overflow-y: auto;
        }
        
        .content-section {
            display: none;
        }
        
        .content-section.active {
            display: block;
        }
        
        /* ==================== CARDS ==================== */
        .card {
            background: white;
            border-radius: 12px;
            border: 1px solid var(--am-border);
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
            margin-bottom: 24px;
            overflow: hidden;
        }
        
        .card-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--am-border);
            background: #f8fafc;
        }
        
        .card-title {
            font-size: 14px;
            font-weight: 700;
            color: var(--am-text);
            margin: 0;
        }
        
        .card-subtitle {
            font-size: 12px;
            color: #64748b;
            margin: 4px 0 0 0;
        }
        
        .card-body {
            padding: 24px;
        }
        
        /* ==================== KPI CARDS ==================== */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .kpi-card {
            background: white;
            padding: 20px 24px;
            border-radius: 12px;
            border: 1px solid var(--am-border);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }
        
        .kpi-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
        
        .kpi-label {
            font-size: 11px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 8px;
        }
        
        .kpi-value {
            font-size: 30px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #0f172a;
            margin: 8px 0;
        }
        
        .kpi-description {
            font-size: 14px;
            color: var(--am-muted);
        }
        
        /* ==================== BADGES ==================== */
        .badge {
            display: inline-block;
            padding: 2px 9px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            white-space: nowrap;
            border: 1px solid transparent;
        }
        
        .badge.bg-primary {
            background: #eff6ff !important;
            color: #1d4ed8 !important;
            border-color: #bfdbfe;
        }
        
        .badge.bg-success {
            background: #f0fdf4 !important;
            color: var(--am-success-dark) !important;
            border-color: #a7f3d0;
        }
        
        .badge.bg-warning {
            background: #fffbeb !important;
            color: #d97706 !important;
            border-color: #fde68a;
        }
        
        .badge.bg-danger {
            background: #fef2f2 !important;
            color: #dc2626 !important;
            border-color: #fecaca;
        }
        
        .badge.bg-light {
            background: #f8fafc !important;
            color: #475569 !important;
            border-color: #e2e8f0;
        }
        
        .badge.bg-secondary {
            background: #f8fafc !important;
            color: #475569 !important;
            border-color: #cbd5e1;
        }
        
        /* ==================== FILTROS MODERNOS ==================== */
        .filter-panel-compact {
            background: linear-gradient(to bottom, var(--am-surface), var(--am-bg));
            border: 1px solid var(--am-border);
            border-radius: 16px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
            padding: 24px 28px;
            margin-bottom: 24px;
        }
        
        .filter-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 18px;
            padding-bottom: 14px;
            border-bottom: 2px solid var(--am-border);
        }
        
        .filter-header i {
            color: #3b82f6;
            font-size: 18px;
            flex-shrink: 0;
        }
        
        .filter-header span {
            font-weight: 600;
            color: #0f172a;
            font-size: 15px;
            letter-spacing: -0.01em;
            flex-shrink: 0;
        }
        
        .filter-pills-container {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 16px;
            min-height: 38px;
        }
        
        .filter-pill {
            display: inline-flex;
            align-items: center;
            padding: 8px 16px;
            background: var(--am-bg);
            color: var(--am-muted);
            border-radius: 24px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 14px;
            font-weight: 500;
            border: 2px solid var(--am-border);
            user-select: none;
        }
        
        .filter-pill:hover {
            background: var(--am-primary-100);
            border-color: var(--am-primary-200);
            color: var(--am-primary-600);
            box-shadow: 0 4px 6px rgba(var(--am-primary-rgb), 0.1);
        }
        
        .filter-pill.active {
            background: var(--am-primary);
            color: white;
            border-color: var(--am-primary);
            box-shadow: 0 4px 8px rgba(var(--am-primary-rgb), 0.25);
        }
        
        .filter-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            padding-top: 12px;
            border-top: 1px solid #f1f5f9;
        }
        
        .btn-filter-action {
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 500;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            background: white;
            color: #64748b;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .btn-filter-action:hover {
            background: #f8fafc;
            border-color: #cbd5e1;
            color: #475569;
        }
        
        .btn-filter-primary {
            background: var(--am-primary);
            color: var(--am-surface);
            border-color: var(--am-primary);
            box-shadow: 0 2px 4px rgba(var(--am-primary-rgb), 0.2);
        }
        
        .btn-filter-primary:hover {
            background: var(--am-primary-600);
            box-shadow: 0 4px 8px rgba(var(--am-primary-rgb), 0.3);
        }
        
        .btn-filter-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        /* ==================== ESTADO VACÍO ==================== */
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: var(--am-muted);
        }
        
        .empty-state i {
            color: var(--am-light);
            margin-bottom: 16px;
        }
        
        .empty-state h3 {
            color: var(--am-muted);
            font-size: 16px;
            font-weight: 700;
            margin: 16px 0 8px;
        }
        
        .empty-state p {
            color: var(--am-muted);
            font-size: 13px;
        }
        
        /* ==================== HOME SECTION ==================== */
        .home-section {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .welcome-banner {
            background: var(--am-primary);
            color: var(--am-surface);
            padding: 48px 40px;
            border-radius: 16px;
            margin-bottom: 32px;
        }
        
        .welcome-banner h2 {
            font-size: 32px;
            font-weight: 700;
            margin: 0 0 12px 0;
            display: flex;
            align-items: center;
        }
        
        .welcome-banner p {
            font-size: 16px;
            opacity: 0.95;
            margin: 0;
        }
        
        /* ==================== ESTADÍSTICAS RÁPIDAS ==================== */
        .quick-stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .stat-card {
            background: white;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            padding: 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            transition: all 0.2s ease;
        }
        
        .stat-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
        
        .stat-icon {
            width: 56px;
            height: 56px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            flex-shrink: 0;
        }
        
        .stat-icon.blue {
            background: #eff6ff;
            color: #2563eb;
        }
        
        .stat-icon.green {
            background: #f0fdf4;
            color: #059669;
        }
        
        .stat-icon.red {
            background: #fef2f2;
            color: #dc2626;
        }
        
        .stat-icon.purple {
            background: #f5f3ff;
            color: #7c3aed;
        }
        
        .stat-content {
            flex: 1;
        }
        
        .stat-label {
            font-size: 13px;
            font-weight: 500;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #0f172a;
            line-height: 1;
        }
        
        /* ==================== EVALUACIONES ACTIVAS ==================== */
        .evaluations-section {
            margin-top: 32px;
        }
        
        .section-title {
            font-size: 20px;
            font-weight: 600;
            color: #0f172a;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .section-title i {
            color: #3b82f6;
        }
        
        .evaluations-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }
        
        .evaluation-card {
            background: white;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            overflow: hidden;
            transition: all 0.2s ease;
        }
        
        .evaluation-card:hover {
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
        }
        
        .evaluation-card-header {
            background: #f8fafc;
            padding: 16px 20px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .evaluation-card-title {
            font-size: 16px;
            font-weight: 600;
            color: #0f172a;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .evaluation-card-body {
            padding: 20px;
        }
        
        .evaluation-info-item {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
            font-size: 14px;
            color: #475569;
        }
        
        .evaluation-info-item:last-child {
            margin-bottom: 0;
        }
        
        .evaluation-info-item i {
            width: 20px;
            text-align: center;
            color: #64748b;
            font-size: 16px;
        }
        
        .evaluation-info-label {
            font-weight: 500;
            color: #64748b;
            min-width: 100px;
        }
        
        .evaluation-info-value {
            font-weight: 600;
            color: #0f172a;
        }
        
        .participation-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
        }
        
        .participation-badge.high {
            background: #d1fae5;
            color: #065f46;
        }
        
        .participation-badge.medium {
            background: #fef3c7;
            color: #92400e;
        }
        
        .participation-badge.low {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .alerts-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            background: #fee2e2;
            color: #991b1b;
        }
        
        .alerts-badge.zero {
            background: #d1fae5;
            color: #065f46;
        }
        
        .empty-evaluations {
            text-align: center;
            padding: 60px 20px;
            color: #94a3b8;
        }
        
        .empty-evaluations i {
            font-size: 48px;
            color: #cbd5e1;
            margin-bottom: 16px;
        }
        
        .empty-evaluations h3 {
            color: #64748b;
            font-size: 18px;
            font-weight: 600;
            margin: 16px 0 8px;
        }
        
        .empty-evaluations p {
            color: #94a3b8;
            font-size: 14px;
        }
        
        /* ==================== CHARTS ==================== */
        .charts-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
            gap: 24px;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
            overflow: hidden;
            height: fit-content;
        }
        
        .card-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--am-border);
            background: #f8fafc;
        }
        
        .card-title {
            font-size: 14px;
            font-weight: 700;
            color: var(--am-text);
            margin: 0 0 4px 0;
        }
        
        .card-subtitle {
            font-size: 12px;
            color: #64748b;
            margin: 0;
        }
        
        .card-body {
            padding: 20px;
            max-height: 400px;
            overflow: auto;
        }
        
        .card-body canvas {
            max-height: 360px;
        }
        
        /* ==================== RESPONSIVE ==================== */
        @media (max-width: 1024px) {
            .sidebar {
                width: 220px;
            }
            
            .main-content {
                margin-left: 220px;
            }
            
            .content-wrapper {
                padding: 24px;
            }
        }
        
        @media (max-width: 768px) {
            .sidebar {
                width: 100%;
                height: auto;
                position: relative;
                flex-direction: row;
            }
            
            .main-content {
                margin-left: 0;
            }
            
            .sidebar-header {
                padding: 16px;
                font-size: 18px;
            }
            
            .sidebar-nav {
                display: flex;
                flex-direction: row;
                padding: 8px;
                overflow-x: auto;
            }
            
            .sidebar-item {
                white-space: nowrap;
            }
            
            .sidebar-item span {
                display: none;
            }
            
            .sidebar-footer {
                display: none;
            }
            
            .content-wrapper {
                padding: 16px;
            }
            
            .topbar {
                padding: 16px;
            }
            
            .topbar h3 {
                font-size: 20px;
            }
            
            .kpi-container {
                grid-template-columns: 1fr;
            }
            
            .evaluations-grid {
                grid-template-columns: 1fr;
            }
            
            .quick-stats-container {
                grid-template-columns: 1fr;
            }
            
            .welcome-banner {
                padding: 32px 24px;
            }
            
            .welcome-banner h2 {
                font-size: 24px;
            }
        }
        
        /* ==================== UTILIDADES ==================== */
        .text-center {
            text-align: center;
        }
        
        .text-muted {
            color: #94a3b8;
        }
        
        .mb-4 {
            margin-bottom: 1.5rem;
        }
        
        .me-2 {
            margin-right: 0.5rem;
        }
        
        .me-3 {
            margin-right: 0.75rem;
        }
    </style>
    """
    return root_vars + rest_css


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
                width: 40px; height: 40px; border-radius: 50%;
                background: var(--am-bg); border: 2px solid var(--am-border);
                display: flex; align-items: center; justify-content: center;
                flex-shrink: 0; color: var(--am-primary); font-size: 18px;
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
                border: 1px solid var(--am-border);
                border-radius: 12px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                padding: 10px 20px;
                flex: 1;
                display: flex; flex-direction: column; justify-content: center;
                align-items: center; text-align: center; gap: 2px;
                transition: box-shadow 0.15s, transform 0.15s;
            }
            .kpi-card:hover {
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                transform: translateY(-1px);
            }
            .kpi-label {
                font-size: 11px; font-weight: 600; color: var(--am-muted);
                text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;
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
                background: var(--am-surface); border: 1px solid var(--am-border);
                border-radius: 10px; margin-bottom: 24px; overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            }
            .am-section-card__header {
                padding: 16px 20px; border-bottom: 1px solid var(--am-border);
                display: flex; flex-direction: column; gap: 2px;
            }
            .am-section-card__title { font-size: 15px; font-weight: 600; color: var(--am-text); }
            .am-section-card__sub   { font-size: 12px; color: var(--am-muted); }
            .am-section-card__body  { padding: 20px; }

            /* ── Compatibility: card classes still used elsewhere ────────── */
            .card {
                background: var(--am-surface); border: 1px solid var(--am-border);
                border-radius: 10px; margin-bottom: 24px; overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
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
                background: var(--am-surface); border: 1px solid var(--am-border);
                border-radius: 10px; margin-bottom: 16px; overflow: hidden;
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
            tbody tr:hover   { background: #fbfcfe; }

            /* ── Barra flotante de informe ───────────────────────────────── */
            .am-float-bar {
                position: fixed; bottom: 0; left: 260px; right: 0; z-index: 1050;
                background: #1e293b; color: #fff;
                display: flex; align-items: center; gap: 12px; padding: 12px 32px;
                box-shadow: 0 -4px 16px rgba(0,0,0,0.2);
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
                letter-spacing: 0.08em; color: #d97706; margin-bottom: 6px; display: block;
            }
            .am-drawer-interp__text { font-size: 12px; line-height: 1.65; color: #78350f; margin: 0; }
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
                display: flex; align-items: center; gap: 12px; margin-bottom: 10px;
            }
            .am-bar-row--total {
                border-top: 1px solid var(--am-border); padding-top: 10px; margin-top: 6px;
            }
            .am-bar-row__label {
                min-width: 160px; font-size: 12px; font-weight: 600;
                color: var(--am-text); flex-shrink: 0;
            }
            .am-bar-row__track {
                flex: 1; position: relative; height: 10px; border-radius: 5px;
                background: #e2e8f0; box-shadow: inset 0 1px 2px rgba(0,0,0,0.06);
                overflow: visible;
            }
            .am-bar-row__score {
                font-family: 'JetBrains Mono', monospace; font-size: 13px;
                font-weight: 700; min-width: 40px; text-align: right; flex-shrink: 0;
            }
            .am-bar-row__score-denom { font-weight: 400; color: var(--am-muted); font-size: 10px; }
        </style>"""


def get_chart_styles():
    """Estilos específicos para gráficos de Chart.js."""
    return """
    <style>
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .row {
            display: flex;
            flex-wrap: wrap;
            margin: 0 -12px 24px -12px;
        }
        
        .col-lg-6 {
            flex: 0 0 50%;
            max-width: 50%;
            padding: 0 12px;
        }
        
        .col-12 {
            flex: 0 0 100%;
            max-width: 100%;
            padding: 0 12px;
        }
        
        @media (max-width: 992px) {
            .col-lg-6 {
                flex: 0 0 100%;
                max-width: 100%;
            }
        }

        /* ====== SURVEY UNIFIED CARD (multi-escala en una sola card) ====== */
        .survey-unified-card {
            margin-bottom: 36px;
            overflow: visible;
        }
        .survey-unified-card > .card-header {
            padding-bottom: 0;
            border-bottom: none;
        }
        .survey-unified-card .survey-scale-tabs {
            display: flex;
            flex-wrap: wrap;
            gap: 2px;
            list-style: none;
            margin: 10px -24px -1px;
            padding: 0 24px;
            border-bottom: none;
        }
        .survey-unified-card .survey-scale-tabs .nav-link {
            font-size: 13px;
            font-weight: 500;
            padding: 7px 16px;
            border-radius: 8px 8px 0 0;
            border: 1px solid transparent;
            color: var(--am-muted);
            background: transparent;
            cursor: pointer;
            transition: all 0.15s;
        }
        .survey-unified-card .survey-scale-tabs .nav-link:hover {
            color: var(--am-text);
            background: var(--am-bg);
        }
        .survey-unified-card .survey-scale-tabs .nav-link.am-tab-active {
            color: var(--am-primary);
            background: var(--am-surface);
            border-color: var(--am-border) var(--am-border) var(--am-surface);
        }
        .survey-unified-card .am-tab-content {
            border-top: 1px solid var(--am-border);
        }
        /* Aplanar cards internas dentro de los panes */
        .survey-unified-card .am-tab-pane > .card {
            border: none;
            box-shadow: none;
            border-radius: 0;
            margin: 0;
        }
        .survey-unified-card .am-tab-pane > .card > .card-header {
            background: var(--am-bg);
            border-bottom: 1px solid var(--am-border);
            border-radius: 0;
        }
        /* Ocultar título interno (el pill tab ya nombra la escala) */
        .survey-unified-card .am-tab-pane > .card > .card-header .card-title,
        .survey-unified-card .am-tab-pane > .card > .card-header .card-subtitle {
            display: none;
        }
        /* Cards de segundo nivel (dentro de toggle wrapper) */
        .survey-unified-card .am-tab-pane .card .card {
            border: none;
            box-shadow: none;
            margin: 0;
            border-radius: 0;
        }

        /* ====== CUESTIONARIOS MULTI-ESCALA (legado, puede quitarse) ====== */
        .survey-group {
            margin-bottom: 36px;
        }
        .survey-group-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            padding: 0 2px;
        }
        .survey-group-title {
            font-size: 15px;
            font-weight: 700;
            color: var(--am-text);
        }
        .survey-group-subscales-toggle {
            margin-top: 10px;
            padding: 0 2px;
        }
        .subscales-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 20px;
            padding: 16px 0 4px;
        }
        .subscale-item .card {
            margin-bottom: 0;
        }
        .subscale-item .card-header {
            padding: 14px 20px;
        }
        .subscale-item .card-title {
            font-size: 14px;
        }
        .subscale-item .card-body {
            padding: 12px 16px;
        }
        @media (max-width: 768px) {
            .subscales-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """
