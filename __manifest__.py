# -*- coding: utf-8 -*-
{
    'name': "AulaMetrics",
    'version': '1.0.1',
    'summary': "Sistema de evaluación psicosocial para centros educativos",

    'author': "Angel Zamora",
    'category': 'Education',
    'depends': ['base', 'mail', 'survey'],
    'data': [
        # 1. Seguridad
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/users_groups.xml',
        # 2. Datos
        'data/alert_keywords.xml',
        'data/surveys/survey_sdq.xml',
        'data/surveys/survey_swls.xml',
        'data/cron/cron_jobs.xml',
        'data/dashboard_data.xml',
        'data/case_stages.xml',
        # 3. Vistas
        'views/dashboard_home_views.xml',
        'views/dashboard.xml',
        'views/dashboard_hub.xml',
        'views/academic_group_views.xml',
        'views/survey_extension_views.xml',
        'views/evaluation_views.xml',
        'views/participations_views.xml',
        'views/threshold_views.xml',
        'views/alert_views.xml',
        'views/alert_keyword_views.xml',
        'views/alerts_dashboard.xml',
        'views/case_views.xml',
        'views/message_thread_views.xml',
        'views/survey_portal_templates.xml',
        'views/qualitative_dashboard_templates.xml',
        'views/dashboard_page_templates.xml',
        'views/dashboard_main_templates.xml',
        'views/reports/survey_result_report_sdq.xml',
        # 4. Datos de Dashboard
        'data/dashboard_home_data.xml',
        # 5. Wizards (antes del menú para que las acciones existan al resolverlas)
        'wizards/resolve_alert_wizard_views.xml',
        'wizards/manual_alert_wizard_views.xml',
        'views/menu.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'aula_metrics/static/src/scss/dashboard_home.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

