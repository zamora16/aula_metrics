# -*- coding: utf-8 -*-
"""
Configuración centralizada para AulaMetrics
Contiene constantes y configuraciones compartidas entre módulos
"""

# =============================================================================
# CONFIGURACIÓN DE MÉTRICAS DE CUESTIONARIOS
# =============================================================================
SURVEY_METRICS = {
    'WHO5': {
        'fields': ['who5_score'],
        'labels': {'who5_score': 'Bienestar (WHO-5)'},
        'colors': {'who5_score': '#28a745'},
        'default_threshold': 50, 'default_op': '<'
    },
    'BULLYING_VA': {
        'fields': ['bullying_score', 'victimization_score', 'aggression_score'],
        'labels': {
            'bullying_score': 'Bullying - Global',
            'victimization_score': 'Bullying - Victimización',
            'aggression_score': 'Agresión',
        },
        'colors': {
            'bullying_score': '#dc3545',
            'victimization_score': '#e83e8c',
            'aggression_score': '#6f42c1',
        },
        'default_threshold': 40, 'default_op': '>'
    },
    'ASQ14': {
        'fields': ['stress_score'],
        'labels': {'stress_score': 'Estrés (ASQ-14)'},
        'colors': {'stress_score': '#fd7e14'},
        'default_threshold': 60, 'default_op': '>'
    },
}

# =============================================================================
# MAPEO DE CÓDIGOS DE CUESTIONARIOS A NOMBRES DE CAMPOS
# =============================================================================
SURVEY_CODE_TO_FIELD = {
    'WHO5': 'has_who5',
    'BULLYING_VA': 'has_bullying',
    'ASQ14': 'has_stress'
}

# =============================================================================
# CONFIGURACIÓN DE CÁLCULO DE PUNTUACIONES
# =============================================================================
SURVEY_SCORING_CONFIGS = {
    'WHO5': {
        'max_sequence': 5,
        'subscales': {
            'who5_score': {'questions': 'all_matrix', 'items': 5}
        }
    },
    'BULLYING_VA': {
        'max_sequence': 4,
        'subscales': {
            'victimization_score': {'questions': 0, 'items': 7},
            'aggression_score': {'questions': 1, 'items': 7},
            'bullying_score': {'combine': ['victimization_score', 'aggression_score']}
        }
    },
    'ASQ14': {
        'max_sequence': 4,
        'subscales': {
            'stress_score': {'questions': 'all_matrix', 'items': 14}
        }
    }
}