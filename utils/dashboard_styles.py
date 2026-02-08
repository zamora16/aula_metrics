# -*- coding: utf-8 -*-
"""
Estilos CSS compartidos para todos los dashboards de AulaMetrics
"""


def get_common_styles():
    """
    Retorna los estilos CSS compartidos por todos los dashboards.
    Incluye layout principal, sidebar, topbar, cards, badges, etc.
    """
    return """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* Reset y base */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8fafc;
            color: #0f172a;
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
            background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
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
            background: rgba(59, 130, 246, 0.2);
            color: white;
            box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.3);
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
            border-bottom: 1px solid #e2e8f0;
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
            color: #0f172a;
        }
        
        .breadcrumbs {
            font-size: 13px;
            color: #64748b;
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
            border: 1px solid #e2e8f0;
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
            border: 1px solid #e2e8f0;
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
            color: #94a3b8;
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
        
        /* ==================== FILTROS ==================== */
        .filter-panel {
            background: white;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .filter-header {
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }
        
        .filter-content {
            padding: 20px;
            border-top: 1px solid #e2e8f0;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        
        .filter-content.show {
            max-height: 2000px;
        }
        
        .filter-section {
            margin-bottom: 20px;
        }
        
        .filter-section label {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
            color: #0f172a;
            margin-bottom: 12px;
        }
        
        .checkbox-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 8px;
        }
        
        .checkbox-grid label {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            border-radius: 6px;
            transition: background 0.2s;
            cursor: pointer;
            font-weight: normal;
        }
        
        .checkbox-grid label:hover {
            background: #f8fafc;
        }
        
        /* ==================== ESTADO VACÍO ==================== */
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: #94a3b8;
        }
        
        .empty-state i {
            color: #cbd5e1;
            margin-bottom: 16px;
        }
        
        .empty-state h3 {
            color: #64748b;
            font-size: 20px;
            font-weight: 600;
            margin: 16px 0 8px;
        }
        
        .empty-state p {
            color: #94a3b8;
            font-size: 14px;
        }
        
        /* ==================== HOME SECTION ==================== */
        .home-section {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .welcome-banner {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 48px 40px;
            border-radius: 16px;
            margin-bottom: 32px;
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.2);
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
        
        /* ==================== CHARTS ==================== */
        .charts-container {
            display: grid;
            gap: 24px;
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
    </style>
    """
