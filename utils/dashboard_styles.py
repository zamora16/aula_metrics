# -*- coding: utf-8 -*-
"""
Estilos CSS compartidos para todos los dashboards de AulaMetrics
"""
from . import palette

# Module-level cache: CSS is fully deterministic (palette constants only),
# so we generate it once and reuse across all requests.
# NOTE: set to None to force regeneration after any style change.
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
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Source+Sans+3:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;700&display=swap');
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
            --font-display: 'Playfair Display', Georgia, 'Times New Roman', serif;
            --font-body: 'Source Sans 3', 'Source Sans Pro', system-ui, sans-serif;
            --font-mono: 'IBM Plex Mono', 'Courier New', monospace;
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
            font-family: var(--font-body);
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
            transition: background 0.18s ease, color 0.18s ease, transform 0.18s cubic-bezier(0.4, 0, 0.2, 1);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
        }
        
        .sidebar-item:hover {
            background: rgba(255, 255, 255, 0.08);
            color: rgba(255, 255, 255, 0.88);
            transform: translateX(3px);
        }
        
        .sidebar-item.active {
            background: rgba(212, 98, 26, 0.20);
            color: white;
            border-left: 3px solid var(--am-accent);
            font-weight: 600;
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

        /* ── Sidebar user card ─────────────────────────────────────── */
        .sidebar-user-card {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            margin-bottom: 10px;
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            transition: background 0.2s;
        }
        .sidebar-user-card:hover {
            background: rgba(255, 255, 255, 0.11);
        }
        .sidebar-user-avatar {
            flex-shrink: 0;
            width: 34px;
            height: 34px;
            border-radius: 8px;
            background: var(--am-accent);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0;
            font-family: var(--font-body);
        }
        .sidebar-user-info {
            min-width: 0;
            flex: 1;
        }
        .sidebar-user-name {
            font-size: 12px;
            font-weight: 600;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.3;
        }
        .sidebar-user-role {
            display: flex;
            align-items: center;
            gap: 5px;
            margin-top: 2px;
            font-size: 10px;
            color: rgba(255, 255, 255, 0.55);
            letter-spacing: 0.03em;
        }
        .sidebar-user-role i {
            font-size: 9px;
            opacity: 0.8;
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
            font-size: 21px;
            font-weight: 700;
            margin: 0;
            color: var(--am-text);
            font-family: var(--font-display);
            letter-spacing: -0.01em;
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
        
        .dashboard-header {
            background: white;
            border-bottom: 1px solid var(--am-border);
            padding: 20px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .dashboard-header h2 {
            font-size: 22px;
            font-weight: 800;
            margin: 0;
            color: var(--am-text);
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
        /* Nivel 1: card base */
        .card {
            background: var(--am-surface);
            border-radius: 14px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.06);
            border: 1px solid var(--am-border);
            margin-bottom: 24px;
            overflow: hidden;
            transition: box-shadow 0.2s ease;
        }
        
        .card-header {
            padding: 18px 24px;
            border-bottom: 1px solid var(--am-border);
            background: var(--am-surface);
        }
        
        /* card-title: short chapter-rule underline stroke, editorial style */
        .card-title {
            font-size: 15px;
            font-weight: 700;
            font-family: var(--font-display);
            color: var(--am-text);
            margin: 0;
            letter-spacing: -0.01em;
            display: inline-flex;
            flex-direction: column;
            gap: 0;
        }

        .card-title::after {
            content: '';
            display: block;
            width: 24px;
            height: 2px;
            background: var(--am-primary);
            margin-top: 5px;
            border-radius: 1px;
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
            background: var(--am-surface);
            padding: 20px 24px;
            border-radius: 14px;
            border: 1px solid var(--am-border);
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        
        .kpi-card:hover {
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.09);
            transform: translateY(-2px);
        }
        
        .kpi-label {
            font-size: 11px;
            font-weight: 700;
            color: var(--am-muted);
            text-transform: uppercase;
            letter-spacing: 0.09em;
            margin-bottom: 4px;
        }
        
        .kpi-value {
            font-size: 28px;
            font-weight: 600;
            font-family: var(--font-mono);
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
            background: var(--am-surface);
            border: 1px solid var(--am-border);
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
            padding: 20px 24px;
            margin-bottom: 28px;
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
            font-weight: 700;
            font-family: var(--font-display);
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
            display: flex;
            align-items: center;
            gap: 24px;
            padding: 28px 36px;
            border-radius: 14px;
            margin-bottom: 32px;
            background: var(--am-surface);
            border: 1px solid var(--am-border);
            box-shadow: 0 2px 12px rgba(26, 92, 82, 0.06);
            animation: fadeIn 0.55s ease both;
        }

        .welcome-banner-icon {
            width: 52px;
            height: 52px;
            border-radius: 12px;
            background: var(--am-primary-100);
            border: 1px solid var(--am-primary-200);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            color: var(--am-primary);
            flex-shrink: 0;
        }

        .welcome-banner-body h2 {
            font-size: 21px;
            font-weight: 700;
            font-family: var(--font-display);
            color: var(--am-text);
            margin: 0 0 2px 0;
            line-height: 1.25;
            letter-spacing: -0.01em;
        }

        .welcome-banner-body h2::after {
            content: '';
            display: block;
            width: 36px;
            height: 2px;
            background: var(--am-accent);
            margin-top: 6px;
            border-radius: 1px;
        }

        .welcome-banner-body p {
            font-size: 14px;
            color: var(--am-muted);
            margin: 0;
            font-weight: 400;
            padding-top: 2px;
        }

        /* ── Cabecera de sección con contador ── */
        .section-header {
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-bottom: 16px;
        }

        .section-title {
            font-size: 17px;
            font-weight: 700;
            font-family: var(--font-display);
            color: var(--am-text);
            margin: 0;
            letter-spacing: -0.01em;
        }

        .section-count {
            font-size: 12px;
            font-weight: 500;
            color: var(--am-muted);
        }
        
        /* ==================== ESTADÍSTICAS RÁPIDAS ==================== */
        .quick-stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .stat-card {
            background: var(--am-surface);
            border-radius: 14px;
            border: 1px solid var(--am-border);
            padding: 22px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            transition: box-shadow 0.25s ease, transform 0.25s ease;
            animation: slideUp 0.5s ease both;
        }

        .stat-card:nth-child(1) { animation-delay: 0.08s; }
        .stat-card:nth-child(2) { animation-delay: 0.16s; }
        .stat-card:nth-child(3) { animation-delay: 0.24s; }
        .stat-card:nth-child(4) { animation-delay: 0.32s; }

        .stat-card:hover {
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.09);
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
            background: var(--am-primary-100);
            color: var(--am-primary);
        }
        
        .stat-icon.green {
            background: #EFF6EE;
            color: var(--am-success);
        }
        
        .stat-icon.red {
            background: #FBF0F2;
            color: var(--am-danger-dark);
        }
        
        .stat-icon.purple {
            background: #F5F3F0;
            color: var(--am-accent);
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
            font-weight: 600;
            font-family: var(--font-mono);
            color: var(--am-text);
            letter-spacing: -0.02em;
            line-height: 1;
        }
        
        /* ==================== EVALUACIONES ==================== */
        .evaluations-section {
            margin-top: 28px;
        }

        .evaluations-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }
        
        .evaluation-card {
            background: var(--am-surface);
            border-radius: 14px;
            border: 1px solid var(--am-border);
            overflow: hidden;
            transition: box-shadow 0.25s ease, transform 0.25s ease;
            animation: slideUp 0.5s ease both;
        }

        .evaluation-card:hover {
            box-shadow: 0 8px 28px rgba(0, 0, 0, 0.10);
            transform: translateY(-2px);
        }
        
        .evaluation-card-title {
            font-size: 16px;
            font-weight: 700;
            font-family: var(--font-display);
            color: var(--am-text);
            margin: 0;
            line-height: 1.3;
            letter-spacing: -0.01em;
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

        /* ── Meta line bajo el valor del stat-card ── */
        .stat-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 6px;
        }

        .stat-meta-dot {
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 6px;
        }

        .stat-meta-dot.active {
            background: #dcfce7;
            color: #166534;
        }

        .stat-meta-dot.scheduled {
            background: #dbeafe;
            color: #1e40af;
        }

        .stat-meta-dot.closed {
            background: var(--am-light);
            color: var(--am-muted);
        }

        .stat-meta-empty {
            font-size: 11px;
            color: var(--am-muted);
        }

        /* ── Estado en cards de evaluación ── */
        .evaluation-card-header {
            background: var(--am-light);
            padding: 14px 16px 16px 20px;
            border-bottom: 1px solid var(--am-border);
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
        }

        .evaluation-card-header-left {
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-width: 0;
            flex: 1;
        }

        .eval-report-btn {
            flex-shrink: 0;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 5px 11px;
            border-radius: 8px;
            background: var(--am-primary);
            color: #fff;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.02em;
            text-decoration: none;
            white-space: nowrap;
            transition: background 0.15s, transform 0.15s;
            margin-top: 2px;
        }

        .eval-report-btn:hover {
            background: var(--am-primary-dark, #134940);
            color: #fff;
            transform: scale(1.07);
            text-decoration: none;
        }

        .eval-state-badge {
            display: inline-block;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: 3px 10px;
            border-radius: 6px;
            width: fit-content;
        }

        .eval-state-badge.state-active {
            background: #dcfce7;
            color: #166534;
        }

        .eval-state-badge.state-scheduled {
            background: #dbeafe;
            color: #1e40af;
        }

        .eval-state-badge.state-closed {
            background: var(--am-light);
            color: var(--am-muted);
        }

        .eval-state-badge.state-draft {
            background: #fef9c3;
            color: #854d0e;
        }

        .eval-state-badge.state-cancelled {
            background: #fee2e2;
            color: var(--am-danger-darker);
        }

        /* Borde lateral de color según estado */
        .evaluation-card.eval-state-active   { border-left: 3px solid #22c55e; }
        .evaluation-card.eval-state-scheduled { border-left: 3px solid #3b82f6; }
        .evaluation-card.eval-state-closed    { border-left: 3px solid var(--am-border); }
        .evaluation-card.eval-state-draft     { border-left: 3px solid #f59e0b; }

        /* ── Pie de card: barra de progreso ── */
        .evaluation-card-footer {
            padding: 14px 20px 18px;
            border-top: 1px solid var(--am-border);
        }

        .eval-progress-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 12px;
            color: var(--am-muted);
            font-weight: 500;
        }

        .eval-progress-track {
            height: 7px;
            background: var(--am-light);
            border-radius: 4px;
            overflow: hidden;
        }

        .eval-progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.4s ease;
        }

        .eval-progress-fill.high   { background: #22c55e; }
        .eval-progress-fill.medium { background: #f59e0b; }
        .eval-progress-fill.low    { background: #ef4444; }

        .eval-report-link {
            display: inline-flex;
            align-items: center;
            font-size: .78rem;
            font-weight: 600;
            color: var(--am-primary);
            text-decoration: none;
            gap: .25rem;
        }
        .eval-report-link:hover { text-decoration: underline; }

        /* ==================== CHARTS ==================== */
        .charts-container {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }

        /* Cards con muchos grupos (>12 filas) ocupan la fila completa */
        .charts-container .card--wide {
            grid-column: 1 / -1;
        }

        @media (max-width: 1100px) {
            .charts-container {
                grid-template-columns: 1fr;
            }
        }
        
        .charts-container .card {
            height: fit-content;
        }

        .charts-container .card:hover {
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08), 0 12px 28px rgba(0, 0, 0, 0.08);
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
                padding: 20px 20px;
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
        .seg-card-header {
            background: var(--am-light);
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
            background: var(--am-light);
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: var(--am-muted);
            border-bottom: 1px solid var(--am-border);
            padding: 10px 14px;
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
        /* Remove the scroll container from inner cards so Chart.js can measure width correctly */
        .survey-unified-card .am-tab-pane > .am-tab-comparativa > .card > .card-body,
        .survey-unified-card .am-tab-pane > .am-tab-evo > .card > .card-body {
            max-height: none !important;
            overflow: visible !important;
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
        .am-mono      {{ font-family: var(--font-mono); }}
        .am-group-col {{ color:var(--am-muted); }}
        .am-center-col {{ color:{palette.UI_CHALKBOARD_GREEN}; }}

        /* ==================== TOUCH TARGETS & ACCESSIBILITY ==================== */
        .filter-pill,
        .btn-filter-action {
            min-height: 44px;
        }

        .filter-pill:focus-visible,
        .btn-filter-action:focus-visible {
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
            font-family: var(--font-body);
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
            background: var(--am-primary-100);
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
            transition: background 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s ease;
            white-space: nowrap;
            min-height: 32px;
        }
        .am-vtoggle-btn + .am-vtoggle-btn {
            border-left: 1px solid var(--am-border);
        }
        .am-vtoggle-btn:hover:not(.am-vtoggle-btn--active) {
            background: var(--am-primary-100);
            color: var(--am-primary);
        }
        .am-vtoggle-btn--active {
            background: var(--am-primary);
            color: white;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.18);
        }
        .am-vtoggle-btn:focus-visible {
            outline: 2px solid var(--am-primary);
            outline-offset: 2px;
        }

        /* ==================== ANIMATIONS ==================== */
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(14px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to   { opacity: 1; }
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


