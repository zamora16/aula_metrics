# -*- coding: utf-8 -*-
import json
import logging
from collections import Counter

from odoo import models, api

from ...utils import role_service, palette
from ...utils.constants import EVAL_STATES_ACTIVE, ROLE_ADMIN, ROLE_COUNSELOR, ROLE_TUTOR

_logger = logging.getLogger(__name__)

_BAR_COLORS = palette.METRICS_PALETTE


class DashboardSegmentation(models.TransientModel):
    _name = 'aula_metrics.dashboard.segmentation'
    _description = 'Generador de datos para el dashboard de distribución del alumnado'

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @api.model
    def get_available_evaluations(self, role_info):
        """Evaluaciones con al menos un valor de segmentación disponible para el rol actual."""
        domain = role_service.apply_group_filter(
            [('state', 'in', EVAL_STATES_ACTIVE)],
            role_info,
            field='academic_group_ids',
        )
        if domain is None:
            return []

        seg_question_ids = self.env['survey.question'].search(
            [('is_segmentation', '=', True)]
        ).ids
        if not seg_question_ids:
            return []

        all_evals = self.env['aula_metrics.evaluation'].search(
            domain, order='date_start desc'
        )

        result = []
        for ev in all_evals:
            has_seg = self.env['aula_metrics.metric_value'].search_count([
                ('evaluation_id', '=', ev.id),
                ('question_id', 'in', seg_question_ids),
                ('value_json', '!=', False),
            ]) > 0
            if has_seg:
                result.append({'id': ev.id, 'name': ev.name})
        return result

    @api.model
    def get_segmentation_variables(self, role_info, evaluation_ids=None):
        """Variables de segmentación con distribución de respuestas, filtradas por rol y evaluación."""
        base_domain = []
        if evaluation_ids:
            base_domain.append(('evaluation_id', 'in', [int(e) for e in evaluation_ids]))

        filtered_domain = role_service.apply_group_filter(
            base_domain, role_info, field='academic_group_id'
        )
        if filtered_domain is None:
            return []

        seg_questions = self.env['survey.question'].search(
            [('is_segmentation', '=', True)]
        )
        if not seg_questions:
            return []

        role = role_info['role']
        variables = []

        for question in seg_questions:
            q_domain = filtered_domain + [
                ('question_id', '=', question.id),
                ('value_json', '!=', False),
            ]
            all_records = self.env['aula_metrics.metric_value'].search(q_domain)
            if not all_records:
                continue

            # Una respuesta por alumno; prioriza la clave canónica de _save_multiplechoice_responses().
            metric_values = self._deduplicate_by_student(question, all_records)

            if role in [ROLE_ADMIN, ROLE_COUNSELOR]:
                var_data = self._build_full_variable(question, metric_values, include_groups=True)
            elif role == ROLE_TUTOR:
                var_data = self._build_full_variable(question, metric_values, include_groups=False)
            else:  # management
                var_data = self._build_management_variable(question, metric_values)

            if var_data:
                variables.append(var_data)

        return variables

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate_by_student(question, all_records):
        """Una respuesta por alumno; prioriza la clave canónica 'question_<id>_choices'."""
        preferred = f'question_{question.id}_choices'
        seen = {}
        for mv in all_records:
            sid = mv.student_id.id
            if sid not in seen or mv.metric_name == preferred:
                seen[sid] = mv
        return list(seen.values())

    @staticmethod
    def _extract_options(value_json):
        """Normaliza value_json (lista, JSON-string o string plano) a list[str]."""
        if isinstance(value_json, list):
            return [str(v) for v in value_json if v is not None]
        if isinstance(value_json, str):
            try:
                parsed = json.loads(value_json)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed if v is not None]
                return [str(parsed)]
            except (ValueError, TypeError):
                return [value_json]
        return []

    @classmethod
    def _build_distribution(cls, options_counter, total):
        """Lista de opciones ordenada por frecuencia, con porcentaje y color de paleta."""
        return [
            {
                'label': opt,
                'count': cnt,
                'pct': round(cnt * 100 / total, 1) if total else 0,
                'color': _BAR_COLORS[i % len(_BAR_COLORS)],
            }
            for i, (opt, cnt) in enumerate(
                sorted(options_counter.items(), key=lambda x: (-x[1], x[0]))
            )
        ]

    @classmethod
    def _build_full_variable(cls, question, metric_values, include_groups=True):
        """Distribución global más desglose por grupo (counselor/admin) o sin desglose (tutor)."""
        all_options = []
        group_data = {}

        for mv in metric_values:
            opts = cls._extract_options(mv.value_json)
            all_options.extend(opts)
            if include_groups:
                grp = mv.academic_group_id.name if mv.academic_group_id else 'Sin grupo'
                group_data.setdefault(grp, []).extend(opts)

        total = len(metric_values)
        distribution = cls._build_distribution(Counter(all_options), total)

        by_group = []
        if include_groups:
            for grp_name in sorted(group_data):
                opts = group_data[grp_name]
                grp_total = len(opts)
                by_group.append({
                    'name': grp_name,
                    'total': grp_total,
                    'distribution': cls._build_distribution(Counter(opts), grp_total),
                })

        return {
            'question_id': question.id,
            'variable_name': question.metric_label or question.title,
            'total': total,
            'distribution': distribution,
            'by_group': by_group,
            'by_level': [],
            'view_type': 'counselor' if include_groups else 'tutor',
        }

    @classmethod
    def _build_management_variable(cls, question, metric_values):
        """Distribución agregada más desglose por nivel educativo para dirección."""
        all_options = []
        level_data = {}

        for mv in metric_values:
            opts = cls._extract_options(mv.value_json)
            all_options.extend(opts)
            level = (
                mv.academic_group_id.course_level
                if mv.academic_group_id and mv.academic_group_id.course_level
                else 'Sin especificar'
            )
            level_data.setdefault(level, []).extend(opts)

        total = len(metric_values)
        distribution = cls._build_distribution(Counter(all_options), total)

        by_level = []
        for level_name in sorted(level_data):
            opts = level_data[level_name]
            lvl_total = len(opts)
            by_level.append({
                'name': level_name,
                'total': lvl_total,
                'distribution': cls._build_distribution(Counter(opts), lvl_total),
            })

        return {
            'question_id': question.id,
            'variable_name': question.metric_label or question.title,
            'total': total,
            'distribution': distribution,
            'by_group': [],
            'by_level': by_level,
            'view_type': 'management',
        }
