# -*- coding: utf-8 -*-
"""
SurveyResult — Resultado persistido de un cuestionario AulaMetrics completado.

Cada vez que un alumno completa un cuestionario oficial (is_aulametrics=True),
se crea un registro SurveyResult con:
  - La puntuación bruta total (raw_score)
  - El baremo aplicado en el momento (snapshot)
  - Las puntuaciones desglosadas por sub-escala en value_json
  - Metadatos: alumno, cuestionario, fecha, edad al completarlo

El modelo es la fuente primaria de datos para el dashboard de perfil de alumno
cuando se muestran resultados de cuestionarios AulaMetrics oficiales.
"""
from odoo import models, fields, api
import json
from datetime import date


class SurveyResult(models.Model):
    _name = 'aula_metrics.survey_result'
    _description = 'Resultado de cuestionario AulaMetrics'
    _order = 'completed_at desc'
    _rec_name = 'display_name'

    # ──────────────────────────────────────────────
    # Relaciones principales
    # ──────────────────────────────────────────────
    student_id = fields.Many2one(
        'res.partner',
        string='Alumno',
        required=True,
        ondelete='cascade',
        index=True,
    )
    survey_id = fields.Many2one(
        'survey.survey',
        string='Cuestionario',
        required=True,
        ondelete='restrict',
        index=True,
    )
    user_input_id = fields.Many2one(
        'survey.user_input',
        string='Respuesta original',
        ondelete='set null',
        help='Referencia al survey.user_input de Odoo que generó este resultado.',
    )
    evaluation_id = fields.Many2one(
        'aula_metrics.evaluation',
        string='Evaluación',
        ondelete='set null',
        help='Evaluación en la que se enmarcó este cuestionario (si aplica).',
    )

    # ──────────────────────────────────────────────
    # Metadatos
    # ──────────────────────────────────────────────
    completed_at = fields.Datetime(
        string='Completado el',
        required=True,
        default=fields.Datetime.now,
    )
    is_aulametrics = fields.Boolean(
        string='Es oficial AulaMetrics',
        default=True,
        help='Redundante para filtrado rápido sin join.',
    )

    # ──────────────────────────────────────────────
    # Puntuaciones
    # ──────────────────────────────────────────────
    raw_score = fields.Float(
        string='Puntuación bruta',
        default=0.0,
        help='Puntuación bruta total del cuestionario.',
    )
    scale_scores_json = fields.Text(
        string='Puntuaciones por escala (JSON)',
        default='{}',
        help='Dict serializado con la puntuación de cada sub-escala.',
    )

    # ──────────────────────────────────────────────
    # Baremo aplicado (snapshot)
    # ──────────────────────────────────────────────
    baremo_label = fields.Char(
        string='Nivel de severidad',
        help='Etiqueta del baremo aplicado en el momento de completar.',
    )
    baremo_description = fields.Text(
        string='Descripción del baremo',
    )
    baremo_severity = fields.Integer(
        string='Severidad (0-2)',
        default=0,
        help='0 = bajo, 1 = medio, 2 = alto.',
    )
    notes = fields.Text(
        string='Observaciones del orientador',
        help='Notas o comentarios añadidos por el orientador sobre este resultado.',
    )

    # ──────────────────────────────────────────────
    # Snapshot histórico
    # ──────────────────────────────────────────────
    academic_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo Académico',
        store=True,
        readonly=True,
        ondelete='set null',
        help='Grupo del alumno en el momento de completar el cuestionario (dato histórico, '
             'no cambia al cambiar de curso o grupo).'
    )

    # ──────────────────────────────────────────────
    # Computed
    # ──────────────────────────────────────────────
    age_at_completion = fields.Integer(
        string='Edad al completar',
        compute='_compute_age_at_completion',
        store=False,
    )

    @api.depends('completed_at', 'student_id')
    def _compute_age_at_completion(self):
        for rec in self:
            partner = rec.student_id
            birth = getattr(partner, 'birthdate_date', None) or getattr(partner, 'birth_date', None)
            if birth and rec.completed_at:
                ref = rec.completed_at.date() if hasattr(rec.completed_at, 'date') else rec.completed_at
                rec.age_at_completion = (
                    ref.year - birth.year
                    - ((ref.month, ref.day) < (birth.month, birth.day))
                )
            else:
                rec.age_at_completion = 0

    def get_scale_scores(self):
        """
        Devuelve el dict de puntuaciones por escala almacenado en scale_scores_json.

        Returns:
            dict: {'escala': {'score': float, 'label': str, 'severity': int, ...}}
        """
        self.ensure_one()
        raw = self.scale_scores_json or '{}'
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}

    def get_report_data(self):
        """
        Prepara datos estructurados para el informe PDF de resultados.

        Returns:
            dict con todas las claves necesarias para el template QWeb:
            student_name, survey_title, completed_at, raw_score,
            global_label, global_severity, global_description, scales (list).
        """
        self.ensure_one()
        BaremoRange = self.env['aula_metrics.survey_baremo_range']

        # Obtener mapeo dinámico de severidad
        severity_mapping = BaremoRange.get_severity_mapping(self.survey_id.id)

        # Metadatos de escala: etiqueta legible y orden
        baremos_all = BaremoRange.search([('survey_id', '=', self.survey_id.id)])
        scale_meta  = {}
        scale_maxes = {}
        for br in baremos_all:
            sn = br.scale_name or '__global__'
            if sn not in scale_meta:
                scale_meta[sn] = {
                    'label': br.scale_label or sn.replace('_', ' ').capitalize(),
                    'order': br.display_order if br.display_order is not None else 99,
                }
            if br.score_max > scale_maxes.get(sn, 0):
                scale_maxes[sn] = br.score_max

        # Ordenar escalas igual que en el dashboard
        scale_scores_raw = self.get_scale_scores()
        has_total = 'total' in scale_scores_raw
        non_total = [s for s in scale_scores_raw if s != 'total']
        non_total.sort(key=lambda s: scale_meta.get(s, {}).get('order', 99))
        ordered_scales = non_total + (['total'] if has_total else [])

        scales = []
        for sn in ordered_scales:
            data  = scale_scores_raw[sn]
            score = data.get('score', 0) if isinstance(data, dict) else float(data or 0)
            sev   = min(data.get('severity', 0) if isinstance(data, dict) else 0, 2)
            label = data.get('label', '') if isinstance(data, dict) else ''

            # Descripción interpretativa actualizada del baremo
            br_match = BaremoRange.search([
                ('survey_id', '=', self.survey_id.id),
                ('scale_name', '=', sn),
                ('score_min', '<=', score),
                ('score_max', '>=', score),
            ], limit=1)
            description = br_match.description if br_match else ''

            scale_max = max(scale_maxes.get(sn, 10), 1)
            pct = min(score / scale_max * 100, 100)

            # Usar mapeo dinámico para colores y labels
            sev_info = severity_mapping.get(sev, {})
            sev_label = label or sev_info.get('label', '—')
            sev_color = sev_info.get('color', '#ccc')
            sev_bg = sev_info.get('bg_color', '#fff')

            scales.append({
                'name':        sn,
                'label':       scale_meta.get(sn, {}).get('label') or sn.replace('_', ' ').capitalize(),
                'score':       score,
                'score_str':   '%.0f' % score,
                'max':         scale_max,
                'max_str':     '%.0f' % scale_max,
                'pct':         pct,
                'pct_str':     '%.1f' % pct,
                'severity':    sev,
                'sev_label':   sev_label,
                'sev_color':   sev_color,
                'sev_bg':      sev_bg,
                'description': description,
                'is_total':    sn == 'total',
            })

        global_sev = min(self.baremo_severity, 2)
        raw_score_max = scale_maxes.get('total') if 'total' in scale_scores_raw else None

        # Usar mapeo para global
        global_sev_info = severity_mapping.get(global_sev, {})
        global_label = self.baremo_label or global_sev_info.get('label', f'Severity {global_sev}')
        global_sev_color = global_sev_info.get('color', '#ccc')
        global_sev_bg = global_sev_info.get('bg_color', '#fff')

        return {
            'student_name':        self.student_id.name or '',
            'student_age':         self.age_at_completion,
            'survey_title':        self.survey_id.title or '',
            'completed_at':        self.completed_at,
            'raw_score':           self.raw_score,
            'raw_score_max':       raw_score_max,
            'global_label':        global_label,
            'global_severity':     global_sev,
            'global_sev_color':    global_sev_color,
            'global_sev_bg':       global_sev_bg,
            'global_description':  self.baremo_description or '',
            'scales':              scales,
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Congela el grupo académico del alumno en el momento de crear el resultado.
        Así las comparativas históricas de peer comparison usan el grupo correcto
        aunque el alumno cambie de grupo al año siguiente.
        """
        for vals in vals_list:
            if 'academic_group_id' not in vals and vals.get('student_id'):
                student = self.env['res.partner'].browse(vals['student_id'])
                vals['academic_group_id'] = student.academic_group_id.id or False
        return super().create(vals_list)

    @api.model
    def create_from_scoring(self, student_id, survey_id, user_input_id, evaluation_id,
                             raw_score, scale_scores, baremo_env):
        """
        Método de factoría: crea un SurveyResult a partir de los datos de scoring.

        Args:
            student_id (int): ID del alumno (res.partner).
            survey_id (int): ID del cuestionario (survey.survey).
            user_input_id (int|None): ID del survey.user_input.
            evaluation_id (int|None): ID de la evaluación.
            raw_score (float): Puntuación bruta total.
            scale_scores (dict): {'escala': {'score': float, 'label': str, 'severity': int, 'description': str}}.
            baremo_env: recordset de aula_metrics.survey_baremo_range para buscar baremo global.

        Returns:
            SurveyResult: nuevo registro creado.
        """
        # Buscar baremo global: usar 'total' si existe, sino None
        scale_name_global = 'total' if 'total' in scale_scores else None
        global_baremo = baremo_env.find_baremo(survey_id, raw_score, scale_name=scale_name_global)
        baremo_label = global_baremo.label if global_baremo else ''
        baremo_description = global_baremo.description if global_baremo else ''
        baremo_severity = global_baremo.severity if global_baremo else 0

        vals = {
            'student_id': student_id,
            'survey_id': survey_id,
            'user_input_id': user_input_id,
            'evaluation_id': evaluation_id,
            'completed_at': fields.Datetime.now(),
            'is_aulametrics': True,
            'raw_score': raw_score,
            'baremo_label': baremo_label,
            'baremo_description': baremo_description,
            'baremo_severity': baremo_severity,
            'scale_scores_json': json.dumps(scale_scores) if scale_scores else '{}',
        }
        return self.create(vals)
