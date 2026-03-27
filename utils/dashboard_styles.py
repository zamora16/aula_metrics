# -*- coding: utf-8 -*-
"""
Estilos CSS compartidos para todos los dashboards de AulaMetrics
"""
from . import palette

# Module-level cache: CSS is fully deterministic (palette constants only),
# so we generate it once and reuse across all requests.
_common_styles_cache = None


def get_common_styles():
    """
    Retorna los estilos CSS compartidos por todos los dashboards.
    Incluye layout principal, sidebar, topbar, cards, badges, etc.
    """
    global _common_styles_cache
    if _common_styles_cache is not None:
        return _common_styles_cache
    root_vars = f"""
    <style>
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
            --am-accent: {palette.UI_ACCENT};
            --am-accent-dark: {palette.UI_ACCENT_DARK};
            --am-success: {palette.UI_SUCCESS};
            --am-success-dark: {palette.UI_SUCCESS_DARK};
            --am-muted: {palette.UI_MUTED};
            --am-text-secondary: {palette.UI_TEXT_SECONDARY};
            --am-subtle: {palette.UI_SUBTLE};
            --am-subtle-border: {palette.UI_SUBTLE_BORDER};
            --am-border: {palette.UI_BORDER};
            --am-light: {palette.UI_LIGHT};
            --am-warning: {palette.UI_WARNING};
            --am-warning-dark: {palette.UI_WARNING_DARK};
            --am-warning-text: {palette.UI_WARNING_TEXT};
            --am-danger: {palette.UI_DANGER};
            --am-danger-dark: {palette.UI_DANGER_DARK};
            --am-danger-darker: {palette.UI_DANGER_DARKER};
            --am-sidebar-start: {palette.UI_SIDEBAR_START};
            --am-sidebar-end: {palette.UI_SIDEBAR_END};
            --am-surface-inverse: {palette.UI_SURFACE_INVERSE};
            --am-role-admin: {palette.UI_ROLE_ADMIN};
            --am-role-counselor: {palette.UI_ROLE_COUNSELOR};
            --am-role-management: {palette.UI_ROLE_MANAGEMENT};
            --am-role-tutor: {palette.UI_ROLE_TUTOR};
            --am-row-hover: {palette.UI_ROW_HOVER};
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
            background: linear-gradient(180deg, var(--am-sidebar-start) 0%, var(--am-sidebar-end) 100%);
            color: white;
            display: flex;
            flex-direction: column;
            position: fixed;
            height: 100vh;
            left: 0;
            top: 0;
            z-index: 1000;
            border-right: 1px solid rgba(255, 255, 255, 0.05);
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
            background: rgba(14, 165, 233, 0.14);
            color: white;
            border-left: 3px solid var(--am-accent);
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
            color: var(--am-muted);
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
        /* Nivel 1: card base — elevación limpia sin border redundante */
        .card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 1px 4px rgba(15, 30, 54, 0.06);
            margin-bottom: 24px;
            overflow: hidden;
        }
        
        .card-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--am-border);
            background: var(--am-light);
        }
        
        .card-title {
            font-size: 15px;
            font-weight: 700;
            color: var(--am-text);
            margin: 0;
        }
        
        .card-subtitle {
            font-size: 12px;
            color: var(--am-muted);
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
            border-radius: 16px;
            border-left: 3px solid var(--am-border);
            box-shadow: 0 1px 4px rgba(15, 30, 54, 0.06);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        
        .kpi-card:hover {
            box-shadow: 0 4px 16px rgba(15, 30, 54, 0.10);
            transform: translateY(-2px);
        }
        
        .kpi-label {
            font-size: 11px;
            font-weight: 700;
            color: var(--am-muted);
            text-transform: uppercase;
            letter-spacing: 0.09em;
            margin-bottom: 8px;
        }
        
        .kpi-value {
            font-size: 28px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: var(--am-text);
            letter-spacing: -0.02em;
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
            background: var(--am-primary-100) !important;
            color: var(--am-primary) !important;
            border-color: var(--am-primary-200);
        }
        
        .badge.bg-success {
            background: #f0fdf4 !important;
            color: var(--am-success-dark) !important;
            border-color: #a7f3d0;
        }
        
        .badge.bg-warning {
            background: #fffbeb !important;
            color: var(--am-warning-dark) !important;
            border-color: #fde68a;
        }
        
        .badge.bg-danger {
            background: #fef2f2 !important;
            color: var(--am-danger-dark) !important;
            border-color: #fecaca;
        }
        
        .badge.bg-light {
            background: var(--am-light) !important;
            color: var(--am-text-secondary) !important;
            border-color: var(--am-border);
        }
        
        .badge.bg-secondary {
            background: var(--am-light) !important;
            color: var(--am-text-secondary) !important;
            border-color: var(--am-subtle-border);
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
            color: var(--am-primary);
            font-size: 18px;
            flex-shrink: 0;
        }
        
        .filter-header span {
            font-weight: 600;
            color: var(--am-text);
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
            font-family: inherit;
            border: 2px solid var(--am-border);
            user-select: none;
            /* reset <button> defaults */
            appearance: none;
            -webkit-appearance: none;
            line-height: inherit;
            text-align: left;
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
            border: 1px solid var(--am-border);
            background: white;
            color: var(--am-muted);
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .btn-filter-action:hover {
            background: var(--am-light);
            border-color: var(--am-subtle-border);
            color: var(--am-text-secondary);
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
            background:
                linear-gradient(135deg, var(--am-primary) 0%, #1a5fa0 55%, #0d3a6e 100%),
                radial-gradient(circle, rgba(255,255,255,0.07) 1px, transparent 1px);
            background-size: cover, 22px 22px;
            color: var(--am-surface);
            padding: 48px 40px;
            border-radius: 20px;
            margin-bottom: 32px;
            box-shadow: 0 4px 24px rgba(15, 30, 54, 0.18);
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
            border-radius: 16px;
            box-shadow: 0 1px 4px rgba(15, 30, 54, 0.06);
            padding: 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        
        .stat-card:hover {
            box-shadow: 0 4px 16px rgba(15, 30, 54, 0.10);
            transform: translateY(-1px);
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
            background: var(--am-primary-100);
            color: var(--am-primary);
        }
        
        .stat-icon.green {
            background: #f0fdf4;
            color: #059669;
        }
        
        .stat-icon.red {
            background: #fef2f2;
            color: var(--am-danger-dark);
        }
        
        .stat-icon.purple {
            background: #f5f3ff;
            color: #7c3aed;
        }
        
        .stat-content {
            flex: 1;
        }
        
        .stat-label {
            font-size: 11px;
            font-weight: 700;
            color: var(--am-muted);
            text-transform: uppercase;
            letter-spacing: 0.09em;
            margin-bottom: 4px;
        }
        
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: var(--am-text);
            letter-spacing: -0.02em;
            line-height: 1;
        }
        
        /* ==================== EVALUACIONES ACTIVAS ==================== */
        .evaluations-section {
            margin-top: 32px;
        }
        
        .section-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--am-text);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .section-title i {
            color: var(--am-primary);
        }
        
        .evaluations-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }
        
        .evaluation-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 1px 4px rgba(15, 30, 54, 0.06);
            overflow: hidden;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        
        .evaluation-card:hover {
            box-shadow: 0 8px 24px rgba(15, 30, 54, 0.12);
            transform: translateY(-2px);
        }
        
        .evaluation-card-header {
            background: var(--am-light);
            padding: 16px 20px;
            border-bottom: 1px solid var(--am-border);
        }
        
        .evaluation-card-title {
            font-size: 15px;
            font-weight: 700;
            color: var(--am-text);
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
            font-size: 13px;
            color: var(--am-text-secondary);
        }
        
        .evaluation-info-item:last-child {
            margin-bottom: 0;
        }
        
        .evaluation-info-item i {
            width: 20px;
            text-align: center;
            color: var(--am-muted);
            font-size: 16px;
        }
        
        .evaluation-info-label {
            font-weight: 500;
            color: var(--am-muted);
            min-width: 100px;
        }
        
        .evaluation-info-value {
            font-weight: 600;
            color: var(--am-text);
        }
        
        .participation-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.03em;
        }
        
        .participation-badge.high {
            background: #dcfce7;
            color: var(--am-success-dark);
        }
        
        .participation-badge.medium {
            background: #fef9c3;
            color: #854d0e;
        }
        
        .participation-badge.low {
            background: #fee2e2;
            color: var(--am-danger-darker);
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
            color: var(--am-danger-darker);
        }
        
        .alerts-badge.zero {
            background: #d1fae5;
            color: var(--am-success-dark);
        }
        
        .empty-evaluations {
            text-align: center;
            padding: 60px 20px;
            color: var(--am-subtle);
        }
        
        .empty-evaluations i {
            font-size: 48px;
            color: var(--am-subtle-border);
            margin-bottom: 16px;
        }
        
        .empty-evaluations h3 {
            color: var(--am-muted);
            font-size: 18px;
            font-weight: 600;
            margin: 16px 0 8px;
        }
        
        .empty-evaluations p {
            color: var(--am-subtle);
            font-size: 14px;
        }
        
        /* ==================== CHARTS ==================== */
        .charts-container {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }

        /* Cards con muchos grupos (>12 filas) pueden ocupar columna completa */
        .charts-container .card--wide {
            grid-column: 1 / -1;
        }

        @media (max-width: 1280px) {
            .charts-container {
                grid-template-columns: 1fr;
            }
        }
        
        .charts-container .card {
            height: fit-content;
        }
        
        .charts-container .card-header {
            padding: 16px 20px;
        }
        
        .charts-container .card-title {
            margin: 0 0 4px 0;
        }
        
        .charts-container .card-subtitle {
            margin: 0;
        }
        
        .charts-container .card-body {
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
            color: var(--am-subtle);
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

        /* ==================== SEGMENTATION DASHBOARD ==================== */
        .seg-filter-card {
            border-radius: 10px;
            border: 1px solid var(--am-border);
            background: var(--am-surface);
        }

        .seg-filter-body {
            padding: 16px 20px;
        }

        .btn-seg-filter {
            background: var(--am-primary);
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 7px 16px;
        }

        .btn-seg-filter:hover {
            background: var(--am-primary-600);
            color: #fff;
        }

        .seg-card-header {
            background: linear-gradient(135deg, var(--am-primary-100) 0%, transparent 100%);
            border-bottom: 1px solid var(--am-border);
            padding: 14px 20px;
        }

        .seg-var-title {
            font-size: 15px;
            font-weight: 600;
            color: var(--am-text);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .seg-total-badge {
            background: var(--am-primary);
            color: #fff;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 11px;
            border-radius: 20px;
        }

        .seg-dist-row {
            margin-bottom: 13px;
        }

        .seg-dist-label-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            margin-bottom: 5px;
        }

        .seg-bar-label {
            font-weight: 500;
            color: var(--am-text);
        }

        .seg-bar-value {
            color: var(--am-muted);
        }

        .seg-bar-track {
            background: var(--am-border);
            border-radius: 6px;
            height: 10px;
            overflow: hidden;
        }

        .seg-bar-fill {
            height: 100%;
            border-radius: 6px;
            transition: width 0.5s ease;
        }

        .seg-breakdown-section {
            margin-top: 18px;
            border-top: 1px solid var(--am-border);
            padding-top: 14px;
        }

        .seg-breakdown-summary {
            cursor: pointer;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--am-muted);
            list-style: none;
            display: flex;
            align-items: center;
            gap: 6px;
            user-select: none;
            outline: none;
        }

        .seg-breakdown-body {
            margin-top: 12px;
        }

        .seg-group-card {
            background: rgba(0, 0, 0, 0.025);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
        }

        .seg-group-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .seg-group-name {
            font-size: 12px;
            color: var(--am-text);
        }

        .seg-group-total {
            font-size: 11px;
            color: var(--am-muted);
        }

        .seg-dist-row-sm {
            margin-bottom: 7px;
        }

        .seg-dist-label-row-sm {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            margin-bottom: 3px;
        }

        .seg-bar-track-sm {
            background: var(--am-border);
            border-radius: 4px;
            height: 6px;
            overflow: hidden;
        }

        .seg-bar-fill-sm {
            height: 100%;
            border-radius: 4px;
        }

        .seg-level-title {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--am-muted);
            margin-bottom: 12px;
        }

        .seg-empty-state {
            text-align: center;
            padding: 60px 20px;
        }

        .seg-empty-title {
            margin-top: 20px;
            color: var(--am-text);
        }

        .seg-empty-body {
            color: var(--am-muted);
            margin-top: 10px;
            max-width: 480px;
            margin-left: auto;
            margin-right: auto;
        }

        /* ==================== TABLA DE ALUMNOS / RESULTADOS ==================== */
        .table { margin-bottom: 0; }
        .table thead th {
            background: var(--am-bg);
            font-size: 10px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--am-muted);
            border-bottom: 2px solid var(--am-border);
            padding: 9px 14px;
        }
        .table tbody td { padding: 10px 14px; vertical-align: middle; font-size: 13px; }
        .table tbody tr:hover { background: var(--am-row-hover); }

        /* ==================== BUSCADOR / FILTROS DE LISTA ==================== */
        .search-box { margin-bottom: 1.5rem; }
        .search-box input,
        .filters-bar select {
            border-radius: 8px;
            padding: 0.75rem 1rem;
            border: 1px solid var(--am-border);
        }
        .search-box input:focus,
        .filters-bar select:focus {
            border-color: var(--am-primary);
            box-shadow: 0 0 0 3px rgba(var(--am-primary-rgb), 0.1);
            outline: none;
        }
        .filters-bar {
            margin-bottom: 1.5rem;
            display: flex;
            gap: 1rem;
            align-items: center;
        }

        /* ==================== SURVEY UNIFIED CARD (tabs multi-escala) ==================== */
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
        .survey-unified-card .am-tab-pane > .am-tab-comparativa > .card,
        .survey-unified-card .am-tab-pane > .am-tab-evo > .card {
            border: none;
            box-shadow: none;
            border-radius: 0;
            margin: 0;
        }
        .survey-unified-card .am-tab-pane > .am-tab-comparativa > .card > .card-header,
        .survey-unified-card .am-tab-pane > .am-tab-evo > .card > .card-header {
            background: var(--am-bg);
            border-bottom: 1px solid var(--am-border);
            border-radius: 0;
        }
        .survey-unified-card .am-tab-pane .card .card {
            border: none;
            box-shadow: none;
            margin: 0;
            border-radius: 0;
        }
        /* ── Survey summary table: clases de utilidad ──────────────────── */
        .am-td        {{ text-align:center; padding:8px 10px; }}
        .am-td-label  {{ padding:8px 10px; font-size:12px; color:var(--am-text); white-space:nowrap; }}
        .am-th-cell   {{ text-align:center; padding:8px 10px; font-size:10px; font-weight:800;
                        text-transform:uppercase; letter-spacing:0.07em;
                        color:var(--am-muted); white-space:nowrap; }}
        .am-th-label  {{ text-align:left; padding:8px 10px; font-size:10px; font-weight:800;
                        text-transform:uppercase; letter-spacing:0.07em; color:var(--am-muted); }}
        .am-mono      {{ font-family:'JetBrains Mono', monospace; }}
        .am-group-col {{ color:var(--am-muted); }}
        .am-center-col {{ color:{palette.UI_CHALKBOARD_GREEN}; }}

        /* ==================== TOUCH TARGETS & ACCESSIBILITY ==================== */
        .filter-pill,
        .btn-filter-action,
        .btn-seg-filter {
            min-height: 44px;
        }

        .filter-pill:focus-visible,
        .btn-filter-action:focus-visible,
        .btn-seg-filter:focus-visible {
            outline: 3px solid var(--am-primary);
            outline-offset: 3px;
        }

        *:focus-visible {
            outline: 2px solid var(--am-primary);
            outline-offset: 2px;
        }

        .sidebar-item:focus-visible {
            outline: 2px solid rgba(255, 255, 255, 0.8);
            outline-offset: 2px;
        }

        /* ==================== SORT BUTTON ==================== */
        .am-sort-btn {
            display: inline-flex;
            align-items: center;
            min-height: 44px;
            padding: 8px 16px;
            background: var(--am-bg);
            border: 1px solid var(--am-border);
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-weight: 500;
            color: var(--am-muted);
            transition: background 0.2s, border-color 0.2s, color 0.2s;
        }
        .am-sort-btn:hover,
        .am-sort-btn:focus-visible {
            background: var(--am-primary-light);
            border-color: var(--am-primary-200);
            color: var(--am-primary);
        }
        .am-sort-btn:focus-visible {
            outline: 2px solid var(--am-primary);
            outline-offset: 2px;
        }

        /* ==================== CHART CARD HEADER WITH CONTROLS ==================== */
        /* card-header con título a la izquierda y controles compactos a la derecha */
        .am-card-header--controls {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }
        .am-card-header__info { min-width: 0; flex: 1; }
        .am-card-header__controls {
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
        }

        /* Selector de segmentación compacto */
        .am-segment-select {
            padding: 4px 8px;
            background: var(--am-surface);
            border: 1px solid var(--am-border);
            border-radius: 6px;
            font-size: 12px;
            color: var(--am-muted);
            font-weight: 500;
            max-width: 140px;
            cursor: pointer;
        }
        .am-segment-select:focus {
            outline: 2px solid var(--am-primary);
            outline-offset: 1px;
        }

        /* Botón icono pequeño (sort) */
        .am-icon-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            padding: 0;
            background: var(--am-surface);
            border: 1px solid var(--am-border);
            border-radius: 6px;
            color: var(--am-muted);
            cursor: pointer;
            font-size: 13px;
            transition: background 0.15s, color 0.15s, border-color 0.15s;
        }
        .am-icon-btn:hover {
            background: var(--am-primary-light);
            border-color: var(--am-primary-200);
            color: var(--am-primary);
        }
        .am-icon-btn:focus-visible {
            outline: 2px solid var(--am-primary);
            outline-offset: 2px;
        }

        /* ==================== VIEW TOGGLE ==================== */
        /* Pill toggle para alternar entre Comparativa / Evolución */
        .am-view-toggle {
            display: inline-flex;
            border: 1px solid var(--am-border);
            border-radius: 8px;
            overflow: hidden;
            background: var(--am-bg);
            flex-shrink: 0;
        }
        .am-vtoggle-btn {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 5px 14px;
            font-size: 12px;
            font-weight: 500;
            color: var(--am-muted);
            background: transparent;
            border: none;
            cursor: pointer;
            transition: background 0.15s, color 0.15s;
            white-space: nowrap;
            min-height: 32px;
        }
        .am-vtoggle-btn + .am-vtoggle-btn {
            border-left: 1px solid var(--am-border);
        }
        .am-vtoggle-btn:hover:not(.am-vtoggle-btn--active) {
            background: var(--am-primary-light);
            color: var(--am-primary);
        }
        .am-vtoggle-btn--active {
            background: var(--am-primary);
            color: white;
        }
        .am-vtoggle-btn:focus-visible {
            outline: 2px solid var(--am-primary);
            outline-offset: 2px;
        }

        /* ==================== REDUCED MOTION ==================== */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                transition-duration: 0.01ms !important;
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                scroll-behavior: auto !important;
            }
        }
    </style>
    """
    _common_styles_cache = root_vars + rest_css
    return _common_styles_cache


# get_profile_styles() has been moved to utils/dashboard_profile_styles.py
def get_profile_styles():
    """Compatibilidad: delega en dashboard_profile_styles.get_profile_styles()."""
    from . import dashboard_profile_styles  # noqa: PLC0415
    return dashboard_profile_styles.get_profile_styles()


