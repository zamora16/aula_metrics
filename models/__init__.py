# -*- coding: utf-8 -*-
"""
Capa de modelos de AulaMetrics, organizada en submódulos temáticos:

  core/     — Entidades base: alumnos, grupos, evaluaciones, métricas
  survey/   — Cuestionarios: extensiones, baremos, resultados, puntuaciones
  dashboard/— Dashboards: gráficos, perfil de alumno, consultas agregadas
  metrics/  — Seguimiento: alertas, casos de orientación, respuestas cualitativas
"""

from . import core
from . import survey
from . import dashboard
from . import metrics
