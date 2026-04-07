# -*- coding: utf-8 -*-
"""
SurveyBaremoRange — Rangos de puntuación e interpretación para cuestionarios AulaMetrics.

Cada registro define un tramo de puntuación con una etiqueta y descripción interpretativa.
Opcionalmente puede estar vinculado a una sub-escala concreta (campo scale_name),
lo que permite cuestionarios con múltiples sub-escalas como el SDQ.

Ejemplo SDQ — Síntomas emocionales:
  score_min=0, score_max=3, label='Normal', severity=0
  score_min=4, score_max=4, label='Límite', severity=1
  score_min=5, score_max=10, label='Anormal', severity=2
"""
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SurveyBaremoRange(models.Model):
    _name = 'aula_metrics.survey_baremo_range'
    _description = 'Baremo de puntuación para cuestionario AulaMetrics'
    _order = 'survey_id, scale_name, score_min'

    survey_id = fields.Many2one(
        'survey.survey',
        string='Cuestionario',
        required=True,
        ondelete='cascade',
        index=True,
    )

    scale_name = fields.Char(
        string='Sub-escala',
        help='Nombre de la sub-escala a la que aplica este baremo (vacío = cuestionario completo). '
             'Ejemplos: "emotional", "conduct", "hyperactivity", "peer", "prosocial", "total"',
    )

    scale_label = fields.Char(
        string='Etiqueta de escala',
        help='Nombre legible de la sub-escala para visualización en el perfil de alumno. '
             'Si se deja vacío se usa scale_name capitalizado como fallback.',
    )

    display_order = fields.Integer(
        string='Orden de visualización',
        default=99,
        help='Posición de esta sub-escala en el desglose del perfil. '
             'Valores más bajos aparecen primero. "total" usa 99 por convención.',
    )

    score_min = fields.Float(
        string='Puntuación mínima',
        required=True,
        default=0.0,
    )
    score_max = fields.Float(
        string='Puntuación máxima',
        required=True,
        default=0.0,
        help='Inclusivo. Para el tramo final usa un valor muy alto (ej. 999).',
    )

    label = fields.Char(
        string='Etiqueta',
        required=True,
        help='Texto corto mostrado al orientador. Ej: "Normal", "Riesgo leve", "Anormal"',
    )

    description = fields.Text(
        string='Descripción',
        help='Texto explicativo sobre qué implica este rango de puntuación.',
    )

    severity = fields.Integer(
        string='Severidad',
        default=0,
        help='Nivel numérico de severidad (0=normal, 1=límite, 2=anormal/alto). '
             'Usado para colorear y priorizar en el dashboard.',
    )

    color = fields.Char(
        string='Color (CSS)',
        help='Color hex o nombre CSS para mostrar en dashboard. Ej: #28a745 (verde), #ffc107 (amarillo), #dc3545 (rojo).',
    )

    @api.constrains('score_min', 'score_max')
    def _check_score_range(self):
        for rec in self:
            if rec.score_max < rec.score_min:
                raise ValidationError(
                    f'El baremo "{rec.label}": score_max ({rec.score_max}) '
                    f'debe ser mayor o igual que score_min ({rec.score_min}).'
                )

    def get_label_for_score(self, score):
        """
        Devuelve el baremo que corresponde a una puntuación dada.
        Retorna el objeto SurveyBaremoRange o None.
        """
        for baremo in self:
            if baremo.score_min <= score <= baremo.score_max:
                return baremo
        return None

    @api.model
    def find_baremo(self, survey_id, score, scale_name=None):
        """
        Busca el baremo que corresponde a una puntuación para un cuestionario y sub-escala dados.

        Cuando la puntuación cae exactamente dentro de un rango, devuelve ese baremo.
        Cuando no cae exactamente en ningún rango (p.ej. medias decimales entre rangos enteros
        como 3.7 entre [0-3] y [4-4]), devuelve el baremo cuyo extremo más cercano minimice la
        distancia — esto garantiza que las medias grupales siempre tengan interpretación.

        Args:
            survey_id (int): ID del cuestionario.
            score (float): Puntuación a interpretar.
            scale_name (str|None): Sub-escala (None para cuestionario global).

        Returns:
            recordset: El baremo que aplique (exacto o más cercano), o vacío si no hay baremos.
        """
        base_domain = [('survey_id', '=', survey_id)]
        if scale_name:
            base_domain.append(('scale_name', '=', scale_name))
        else:
            base_domain.append(('scale_name', 'in', [False, '']))

        # Búsqueda exacta primero
        exact = self.search(base_domain + [
            ('score_min', '<=', score),
            ('score_max', '>=', score),
        ], limit=1)
        if exact:
            return exact

        # Fallback: baremo más cercano (distancia al extremo más próximo del rango)
        all_baremos = self.search(base_domain)
        if not all_baremos:
            return self.browse()

        def _distance(b):
            if score < b.score_min:
                return b.score_min - score
            if score > b.score_max:
                return score - b.score_max
            return 0.0

        return min(all_baremos, key=_distance)

    @api.model
    def get_severity_mapping(self, survey_id):
        """
        Devuelve un mapeo de severidad a etiquetas y colores para un cuestionario dado.
        Útil para evitar hardcodear constantes de UI.

        Args:
            survey_id (int): ID del cuestionario.

        Returns:
            dict: {severity: {'label': str, 'color': str, 'bg_color': str or None}}
        """
        baremos = self.search([('survey_id', '=', survey_id)])
        mapping = {}
        for b in baremos:
            sev = b.severity
            if sev not in mapping:
                mapping[sev] = {
                    'label': b.label,
                    'color': b.color,
                    'bg_color': getattr(b, 'bg_color', None),
                }
        return mapping
