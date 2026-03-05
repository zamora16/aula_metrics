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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

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
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--am-bg);
            color: var(--am-text);
            line-height: 1.6;
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
            background: linear-gradient(180deg, var(--am-sidebar-start) 0%, var(--am-sidebar-end) 100%);
            color: white;
            display: flex;
            flex-direction: column;
            position: fixed;
            height: 100vh;
            left: 0;
            top: 0;
            z-index: 1000;
            box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
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
            color: #cbd5e1;
            text-decoration: none;
            border-radius: 8px;
            margin-bottom: 4px;
            transition: all 0.2s ease;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
        }
        
        .sidebar-item:hover {
            background: rgba(255, 255, 255, 0.1);
            color: white;
        }
        
        .sidebar-item.active {
            background: rgba(var(--am-primary-rgb), 0.18);
            color: white;
            box-shadow: 0 0 0 1px rgba(var(--am-primary-rgb), 0.3);
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
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .topbar h3 {
            font-size: 24px;
            font-weight: 700;
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
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            margin-bottom: 24px;
            overflow: hidden;
        }
        
        .card-header {
            padding: 20px 24px;
            border-bottom: 1px solid #e2e8f0;
            background: white;
        }
        
        .card-title {
            font-size: 18px;
            font-weight: 600;
            color: #0f172a;
            margin: 0;
        }
        
        .card-subtitle {
            font-size: 13px;
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
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--am-border);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }
        
        .kpi-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            transform: translateY(-2px);
        }
        
        .kpi-label {
            font-size: 13px;
            font-weight: 500;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .kpi-value {
            font-size: 36px;
            font-weight: 700;
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
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            white-space: nowrap;
        }
        
        .badge.bg-primary {
            background: #3b82f6;
            color: white;
        }
        
        .badge.bg-success {
            background: #10b981;
            color: white;
        }
        
        .badge.bg-warning {
            background: #f59e0b;
            color: #0f172a;
        }
        
        .badge.bg-danger {
            background: #ef4444;
            color: white;
        }
        
        .badge.bg-light {
            background: #f1f5f9;
            color: #475569;
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
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(var(--am-primary-rgb), 0.1);
        }
        
        .filter-pill.active {
            background: linear-gradient(135deg, var(--am-primary) 0%, var(--am-primary-600) 100%);
            color: var(--am-surface);
            border-color: var(--am-primary-600);
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
            background: linear-gradient(135deg, var(--am-primary) 0%, var(--am-primary-600) 100%);
            color: var(--am-surface);
            border-color: var(--am-primary-600);
            box-shadow: 0 2px 4px rgba(var(--am-primary-rgb), 0.2);
        }
        
        .btn-filter-primary:hover {
            background: linear-gradient(135deg, var(--am-primary-600) 0%, var(--am-primary-darker) 100%);
            box-shadow: 0 4px 8px rgba(var(--am-primary-rgb), 0.3);
            transform: translateY(-1px);
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
            font-size: 20px;
            font-weight: 600;
            margin: 16px 0 8px;
        }
        
        .empty-state p {
            color: var(--am-muted);
            font-size: 14px;
        }
        
        /* ==================== HOME SECTION ==================== */
        .home-section {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .welcome-banner {
            background: linear-gradient(135deg, var(--am-primary) 0%, var(--am-primary-600) 100%);
            color: var(--am-surface);
            padding: 48px 40px;
            border-radius: 16px;
            margin-bottom: 32px;
            box-shadow: 0 10px 40px rgba(var(--am-primary-rgb), 0.2);
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
            transform: translateY(-2px);
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
            background: linear-gradient(135deg, var(--am-primary) 0%, var(--am-primary-600) 100%);
            color: var(--am-surface);
        }
        
        .stat-icon.green {
            background: linear-gradient(135deg, var(--am-success) 0%, var(--am-success-dark) 100%);
            color: var(--am-surface);
        }
        
        .stat-icon.red {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }
        
        .stat-icon.purple {
            background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
            color: white;
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
            transform: translateY(-4px);
        }
        
        .evaluation-card-header {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
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
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            height: fit-content;
        }
        
        .card-header {
            padding: 16px 20px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: #1e293b;
            margin: 0 0 4px 0;
        }
        
        .card-subtitle {
            font-size: 13px;
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
