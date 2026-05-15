# -*- coding: utf-8 -*-
"""
Informe de Evaluación — Capa de datos.

Agrega resultados de una evaluación concreta a tres niveles de granularidad:
  - Por grupo académico  (admin / counselor / tutor)
  - Por nivel educativo  (management)
  - Centro completo      (todos los roles, en el resumen global)

Diseño data-driven:
  - Las escalas, rangos, etiquetas de severidad y colores se leen íntegramente
    de survey.baremo_ids.  No existe ninguna constante hardcodeada relativa
    a cuestionarios concretos.  Añadir un nuevo cuestionario oficial solo
    requiere definir su estrategia de puntuación y sus baremo_ids.
  - La sección de HTML se delega a dashboard_evaluation_report_sections.py
    (mismo modelo, _inherit).

Jerarquía de acceso:
  Admin / Counselor → todos los grupos, datos identificados
  Tutor             → solo sus grupos (validado en _check_eval_access)
  Management        → solo niveles educativos y centro (sin grupos ni alumnos)
"""
import logging
import re as _re
import unicodedata as _ud
from collections import defaultdict, Counter

from odoo import models, api
from markupsafe import Markup
from ...utils import dashboard_styles
from ...utils.constants import centro_surveys_enabled
from ...utils.constants import ROLE_TUTOR, ROLE_MANAGEMENT, ROLE_ADMIN, ROLE_COUNSELOR

_logger = logging.getLogger(__name__)

# Cuántos survey_result como máximo por cuestionario × evaluación.
# 5 000 cubre centros de hasta ~50 grupos con cuestionarios por grupo.
_RESULT_LIMIT = 5_000

# ── Procesamiento de texto abierto ───────────────────────────────────────
_STOPWORDS_ES = frozenset({
    'de','la','que','el','en','y','a','los','del','se','las','un','por',
    'con','una','su','para','es','al','lo','como','pero','sus','le','ya',
    'o','este','esta','entre','cuando','muy','sin','sobre','ser','tienen',
    'tambien','me','hasta','hay','donde','han','son','desde','todo','nos',
    'uno','ni','ese','eso','esto','mi','antes','unos','yo','otro','fue',
    'era','si','ha','bien','mismo','menos','asi','haber','mucho','cada',
    'muchos','otros','vez','poco','siempre','nunca','tan','hacer','muchas',
    'tener','pueden','puede','hemos','tengo','tu','tiene','mas','les',
    'ellos','ellas','nos','usted','ustedes','nuestro','nuestra','vuestro',
    'ello','cual','cuales','quien','quienes','algo','alguien','ninguno',
})


def _word_freq(texts):
    """Devuelve un Counter de palabras relevantes a partir de una lista de textos."""
    counter = Counter()
    for text in (texts or []):
        t = _ud.normalize('NFD', (text or '').lower())
        t = ''.join(c for c in t if _ud.category(c) != 'Mn')
        counter.update(w for w in _re.findall(r'\b[a-z]{3,}\b', t)
                       if w not in _STOPWORDS_ES)
    return counter


class DashboardEvaluationReport(models.TransientModel):
    _name = 'aula_metrics.dashboard.evaluation_report'
    _inherit = 'aula_metrics.dashboard.data_queries'
    _description = 'Informe de resultados por evaluación'

    # ──────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def generate_evaluation_report(self, eval_id, role_info):
        """
        Punto de entrada principal.  Reúne datos y delega el renderizado HTML
        a _build_report_context() definido en dashboard_evaluation_report_sections.

        Returns:
            dict: Contexto completo para 'aula_metrics.dashboard_page_base'.
        """
        evaluation = self.env['aula_metrics.evaluation'].browse(eval_id)
        if not evaluation.exists():
            return self._error_context('Evaluación no encontrada.')

        error = self._check_eval_access(evaluation, role_info)
        if error:
            return self._error_context(error)

        participation_data = self._get_participation_summary(evaluation, role_info)
        surveys_data       = self._collect_surveys_data(evaluation, role_info)

        return self._build_report_context(
            evaluation, role_info,
            participation_data, surveys_data,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Control de acceso
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _check_eval_access(self, evaluation, role_info):
        """
        Retorna None si el acceso es válido, o un str de mensaje de error.

        Solo aplica a tutores puros (role == 'tutor').  Admin, counselor y
        management tienen acceso global: sus record rules ORM ya filtran datos.

        Nota: is_tutor=True está presente en todos los roles como flag acumulativo;
        para distinguir un tutor puro hay que comparar role, no is_tutor.
        """
        if role_info.get('role') != ROLE_TUTOR:
            return None
        tutor_groups = set(role_info.get('allowed_group_ids', []))
        eval_groups  = set(evaluation.academic_group_ids.ids)
        if not tutor_groups & eval_groups:
            return 'No tienes grupos asignados en esta evaluación.'
        return None

    # ──────────────────────────────────────────────────────────────────────
    # Participación
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _get_participation_summary(self, evaluation, role_info):
        """
        Agrega la participación de la evaluación con búsqueda individual y
        fallback de grupo desde el alumno cuando academic_group_id está vacío.

        Returns:
            dict:
              'by_group'  list[dict]  filas por grupo (admin/counselor/tutor)
              'by_level'  list[dict]  filas por nivel educativo (management)
              'totals'    dict        totales globales {total, completed, rate}
        """
        is_tutor   = role_info.get('role') == ROLE_TUTOR
        base_domain = [('evaluation_id', '=', evaluation.id)]

        if is_tutor:
            allowed = role_info.get('allowed_group_ids', [])
            if not allowed:
                return self._empty_participation()
            domain = base_domain + [
                '|',
                ('academic_group_id', 'in', allowed),
                '&',
                ('academic_group_id', '=', False),
                ('student_id.academic_group_id', 'in', allowed),
            ]
        else:
            domain = base_domain

        participations = self.env['aula_metrics.participation'].search(domain)
        if not participations:
            return self._empty_participation()

        # Pre-resolver alumno → grupo como fallback cuando academic_group_id es null
        partner_ids = list({p.student_id.id for p in participations if p.student_id})
        partners    = self.env['res.partner'].browse(partner_ids)
        student_grp = {p.id: p.academic_group_id for p in partners if p.academic_group_id}

        # Acumular por grupo resolviendo el fallback
        group_counts = defaultdict(lambda: {'total': 0, 'completed': 0})
        groups_map   = {}

        for p in participations:
            grp = p.academic_group_id or student_grp.get(p.student_id.id)
            gid = grp.id if grp else 0
            if gid and gid not in groups_map:
                groups_map[gid] = grp
            group_counts[gid]['total'] += 1
            if p.state == 'completed':
                group_counts[gid]['completed'] += 1

        by_group = []
        for gid, cnt in sorted(
            group_counts.items(),
            key=lambda x: (groups_map.get(x[0]) or _EmptyGroup()).name,
        ):
            grp   = groups_map.get(gid)
            total = cnt['total']
            done  = cnt['completed']
            by_group.append({
                'group_id':     gid,
                'group_name':   grp.name if grp else 'Sin grupo',
                'course_level': grp.course_level if grp else '',
                'total':        total,
                'completed':    done,
                'rate':         round(done / total * 100) if total else 0,
            })

        # Agregado por nivel educativo
        level_agg = defaultdict(lambda: {'total': 0, 'completed': 0})
        for row in by_group:
            lvl = row['course_level'] or 'sin_nivel'
            level_agg[lvl]['total']     += row['total']
            level_agg[lvl]['completed'] += row['completed']

        by_level = []
        for lvl, cnt in sorted(level_agg.items()):
            total = cnt['total']
            done  = cnt['completed']
            by_level.append({
                'level':     lvl,
                'label':     _fmt_course_level(lvl),
                'total':     total,
                'completed': done,
                'rate':      round(done / total * 100) if total else 0,
            })

        grand_total = sum(r['total'] for r in by_group)
        grand_done  = sum(r['completed'] for r in by_group)
        totals = {
            'total':     grand_total,
            'completed': grand_done,
            'rate':      round(grand_done / grand_total * 100) if grand_total else 0,
        }
        return {'by_group': by_group, 'by_level': by_level, 'totals': totals}

    @staticmethod
    def _empty_participation():
        return {'by_group': [], 'by_level': [], 'totals': {'total': 0, 'completed': 0, 'rate': 0}}

    # ──────────────────────────────────────────────────────────────────────
    # Cuestionarios — dispatcher
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _collect_surveys_data(self, evaluation, role_info):
        """
        Itera los cuestionarios de la evaluación y recoge datos de resultados.
        Cuestionarios oficiales (is_aulametrics=True) se procesan primero.

        Returns:
            list[dict]: uno por cuestionario con datos listos para renderizar.
        """
        surveys = evaluation.survey_ids.sorted(
            lambda s: (0 if s.is_aulametrics else 1, s.title or '')
        )
        _centro_active = centro_surveys_enabled(self.env)
        result = []
        for survey in surveys:
            if survey.is_aulametrics:
                data = self._get_official_survey_data(survey, evaluation, role_info)
            elif self._is_text_only_survey(survey):
                # Si el cuestionario sólo tiene preguntas de texto abierto, mostrar
                # tabla de frecuencia de palabras sin pasar por la lógica cuantitativa.
                data = self._get_text_survey_data(survey, evaluation, role_info)
            else:
                if not _centro_active:
                    continue
                data = self._get_adhoc_survey_data(survey, evaluation, role_info)
                if not data:
                    data = self._get_text_survey_data(survey, evaluation, role_info)
            if data:
                result.append(data)
        return result

    @api.model
    def _is_text_only_survey(self, survey):
        """True si todas las preguntas del cuestionario son de texto abierto."""
        try:
            questions = survey.question_ids
        except Exception:
            return False
        if not questions:
            return False
        non_text = questions.filtered(
            lambda q: q.question_type not in ('text_box', 'char_box')
                      and not getattr(q, 'is_page', False)
        )
        has_text = any(q.question_type in ('text_box', 'char_box') for q in questions)
        return has_text and not bool(non_text)

    # ──────────────────────────────────────────────────────────────────────
    # Cuestionarios oficiales (is_aulametrics=True)
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _get_official_survey_data(self, survey, evaluation, role_info):
        """
        Agrega survey_result por escala × grupo.

        Todo el esquema de escalas, rangos y niveles de severidad se extrae de
        survey.baremo_ids — sin hardcoding de nombres de escala, etiquetas de
        nivel ni rangos numéricos.

        Jerarquía de acceso:
          Admin/Counselor → todos los grupos
          Tutor           → solo sus grupos; center_mean y level_means se
                            computan de TODOS los resultados del centro para
                            que la comparativa sea real.
          Management      → todos los grupos (la capa de presentación solo
                            muestra niveles y centro, nunca grupos individuales)

        Returns:
            dict | None: None si no hay resultados para este rol.
              {
                'survey_id'      int,
                'survey_name'    str,
                'is_aulametrics' True,
                'scales'         list[scale_dict],
                'severity_meta'  dict[int→{label,color}],
                'n_results'      int,
              }

            scale_dict añade ahora 'tutor_level_ref' (solo para tutores):
              'tutor_level_ref'  dict[level→{mean_score,label,baremo_label,baremo_color}]|None
        """
        is_tutor   = role_info.get('role') == ROLE_TUTOR
        base_domain = [
            ('survey_id',     '=', survey.id),
            ('evaluation_id', '=', evaluation.id),
        ]

        if is_tutor:
            allowed = role_info.get('allowed_group_ids', [])
            if not allowed:
                return None
            # OR: grupo congelado en result  /  grupo actual del alumno (fallback)
            domain = base_domain + [
                '|',
                ('academic_group_id', 'in', allowed),
                '&',
                ('academic_group_id', '=', False),
                ('student_id.academic_group_id', 'in', allowed),
            ]
        else:
            domain = base_domain

        results = self.env['aula_metrics.survey_result'].search(domain, limit=_RESULT_LIMIT)
        if not results:
            return None

        # Para tutores: cargar TODOS los resultados para center_mean/level_means reales
        if is_tutor:
            center_results = self.env['aula_metrics.survey_result'].sudo().search(
                base_domain, limit=_RESULT_LIMIT
            )
        else:
            center_results = results

        BaremoRange = self.env['aula_metrics.survey_baremo_range']

        # ── Estructura de escalas desde baremo_ids (data-driven) ──────────
        baremos = survey.baremo_ids.sorted(
            lambda b: (b.display_order if b.display_order is not None else 99,
                       b.scale_name or '', b.score_min)
        )

        scale_meta = {}
        for b in baremos:
            sn = b.scale_name or '__global__'
            if sn not in scale_meta:
                scale_meta[sn] = {
                    'scale_label': b.scale_label or sn.replace('_', ' ').capitalize(),
                    'order':       b.display_order if b.display_order is not None else 99,
                    'score_min':   b.score_min,
                    'score_max':   b.score_max,
                }
            else:
                scale_meta[sn]['score_min'] = min(scale_meta[sn]['score_min'], b.score_min)
                scale_meta[sn]['score_max'] = max(scale_meta[sn]['score_max'], b.score_max)

        # baremos is already sorted by (display_order, scale_name, score_min).
        # Build per-scale baremo_meta ordered by score_min: {label: {color, severity}}.
        # This preserves all distinct baremo labels (not collapsed by severity).
        scale_baremo_meta = {}
        for b in baremos:
            sn = b.scale_name or '__global__'
            if sn not in scale_baremo_meta:
                scale_baremo_meta[sn] = {}
            if b.label not in scale_baremo_meta[sn]:
                scale_baremo_meta[sn][b.label] = {
                    'color':    b.color or '#6c757d',
                    'severity': b.severity,
                }

        severity_meta = BaremoRange.get_severity_mapping(survey.id)

        # ── Helper: mapa alumno_id → academic_group record ────────────────
        def _student_group_map(rset, use_sudo=False):
            pids     = list({r.student_id.id for r in rset if r.student_id})
            env      = self.env['res.partner'].sudo() if use_sudo else self.env['res.partner']
            partners = env.browse(pids)
            return {p.id: p.academic_group_id for p in partners if p.academic_group_id}

        student_grp_map        = _student_group_map(results)
        center_student_grp_map = _student_group_map(center_results, use_sudo=True) if is_tutor else student_grp_map

        # ── Helper: acumular puntuaciones por grupo × escala ──────────────
        def _accumulate(rset, smap):
            g_scores = defaultdict(lambda: defaultdict(list))
            g_sevs   = defaultdict(lambda: defaultdict(list))
            g_meta   = {}
            for r in rset:
                grp = r.academic_group_id or smap.get(r.student_id.id)
                gid = grp.id if grp else 0
                if gid not in g_meta:
                    g_meta[gid] = {
                        'name':         grp.name if grp else 'Sin grupo',
                        'course_level': grp.course_level if grp else '',
                    }
                for sn, sdata in r.get_scale_scores().items():
                    score = sdata.get('score')
                    # Use baremo label string as key so all distinct baremos are preserved.
                    # Falls back to "sev_N" when label is absent (old records without label).
                    sev_label = sdata.get('label', '') or f'sev_{sdata.get("severity", 0)}'
                    if score is not None:
                        g_scores[gid][sn].append(float(score))
                        g_sevs[gid][sn].append(sev_label)
            return g_scores, g_sevs, g_meta

        group_scores, group_sevs, group_meta = _accumulate(results, student_grp_map)

        if is_tutor:
            ctr_scores, ctr_sevs, ctr_meta = _accumulate(center_results, center_student_grp_map)
        else:
            ctr_scores, ctr_sevs, ctr_meta = group_scores, group_sevs, group_meta

        # ── Construir salida por escala ───────────────────────────────────
        scales_out = []
        for sn, smeta in sorted(scale_meta.items(), key=lambda x: x[1]['order']):
            # Grupos del rol actual
            groups_out = []
            for gid in sorted(group_scores, key=lambda g: group_meta.get(g, {}).get('name', '')):
                scores = group_scores[gid].get(sn, [])
                if not scores:
                    continue
                mean   = sum(scores) / len(scores)
                sevs   = group_sevs[gid].get(sn, [])
                baremo = BaremoRange.find_baremo(
                    survey.id, mean, sn if sn != '__global__' else None
                )
                sev_dist = defaultdict(int)
                for s in sevs:
                    sev_dist[s] += 1
                groups_out.append({
                    'group_id':     gid,
                    'group_name':   group_meta[gid]['name'],
                    'course_level': group_meta[gid]['course_level'],
                    'n':            len(scores),
                    'mean_score':   round(mean, 2),
                    'min':          round(min(scores), 2),
                    'max':          round(max(scores), 2),
                    'baremo_label': baremo.label if baremo else '',
                    'baremo_color': baremo.color if baremo else '#6c757d',
                    'baremo_sev':   baremo.severity if baremo else 0,
                    'sev_dist':     dict(sev_dist),
                })

            # Agregado de centro — siempre desde ctr_scores (real para todos los roles)
            all_scores = [sc for gsc in ctr_scores.values() for sc in gsc.get(sn, [])]
            all_sevs   = [sv for gsv in ctr_sevs.values()   for sv in gsv.get(sn, [])]
            center_mean   = round(sum(all_scores) / len(all_scores), 2) if all_scores else None
            center_baremo = (
                BaremoRange.find_baremo(survey.id, center_mean, sn if sn != '__global__' else None)
                if center_mean is not None else None
            )
            center_sev_dist = defaultdict(int)
            for s in all_sevs:
                center_sev_dist[s] += 1

            # Agregado por nivel educativo — desde ctr_meta/ctr_scores
            level_scores_sn = defaultdict(list)
            level_sevs_sn   = defaultdict(list)
            for gid, gmeta in ctr_meta.items():
                lvl = gmeta.get('course_level') or 'sin_nivel'
                level_scores_sn[lvl].extend(ctr_scores[gid].get(sn, []))
                level_sevs_sn[lvl].extend(ctr_sevs[gid].get(sn, []))

            by_level_out = []
            for lvl in sorted(level_scores_sn.keys()):
                lscores = level_scores_sn[lvl]
                if not lscores:
                    continue
                lmean   = round(sum(lscores) / len(lscores), 2)
                lsevs   = level_sevs_sn[lvl]
                lbaremo = BaremoRange.find_baremo(
                    survey.id, lmean, sn if sn != '__global__' else None
                )
                lsev_dist = defaultdict(int)
                for s in lsevs:
                    lsev_dist[s] += 1
                by_level_out.append({
                    'level':        lvl,
                    'label':        _fmt_course_level(lvl),
                    'n':            len(lscores),
                    'mean_score':   lmean,
                    'min':          round(min(lscores), 2),
                    'max':          round(max(lscores), 2),
                    'baremo_label': lbaremo.label if lbaremo else '',
                    'baremo_color': lbaremo.color if lbaremo else '#6c757d',
                    'baremo_sev':   lbaremo.severity if lbaremo else 0,
                    'sev_dist':     dict(lsev_dist),
                })

            # Para tutores: referencia de nivel educativo de sus grupos
            tutor_level_ref = None
            if is_tutor and groups_out:
                tutor_levels = {g['course_level'] for g in groups_out if g['course_level']}
                tutor_level_ref = {
                    lv['level']: {
                        'mean_score':   lv['mean_score'],
                        'label':        lv['label'],
                        'baremo_label': lv.get('baremo_label', ''),
                        'baremo_color': lv.get('baremo_color', '#6c757d'),
                        'n':            lv['n'],
                        'sev_dist':     lv.get('sev_dist', {}),
                    }
                    for lv in by_level_out if lv['level'] in tutor_levels
                }

            scales_out.append({
                'scale_name':      sn,
                'scale_label':     smeta['scale_label'],
                'score_min':       smeta['score_min'],
                'score_max':       smeta['score_max'],
                'groups':          groups_out,
                'by_level':        by_level_out,
                'center_mean':     center_mean,
                'center_n':        len(all_scores),
                'center_baremo':   (
                    {
                        'label': center_baremo.label,
                        'color': center_baremo.color or '#6c757d',
                        'sev':   center_baremo.severity,
                    }
                    if center_baremo else None
                ),
                'center_sev_dist': dict(center_sev_dist),
                'baremo_meta':     scale_baremo_meta.get(sn, {}),
                'tutor_level_ref': tutor_level_ref,
            })

        return {
            'survey_id':      survey.id,
            'survey_name':    survey.title or '',
            'is_aulametrics': True,
            'scales':         scales_out,
            'severity_meta':  severity_meta,
            'n_results':      len(results),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Cuestionarios ad-hoc / centro
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _get_adhoc_survey_data(self, survey, evaluation, role_info):
        """
        Agrega metric_value por métrica × grupo usando búsqueda individual con
        fallback de grupo desde el alumno cuando academic_group_id está vacío.

        Returns:
            dict | None: None si no hay datos para este rol.
              {
                'survey_id'      int,
                'survey_name'    str,
                'is_aulametrics' False,
                'metrics'        list[metric_dict],
              }

            metric_dict incluye ahora 'tutor_level_ref' para tutores.
        """
        is_tutor   = role_info.get('role') == ROLE_TUTOR
        base_domain = [
            ('survey_id',     '=', survey.id),
            ('evaluation_id', '=', evaluation.id),
            ('value_float',   '!=', False),
        ]

        if is_tutor:
            allowed = role_info.get('allowed_group_ids', [])
            if not allowed:
                return None
            domain = base_domain + [
                '|',
                ('academic_group_id', 'in', allowed),
                '&',
                ('academic_group_id', '=', False),
                ('student_id.academic_group_id', 'in', allowed),
            ]
        else:
            domain = base_domain

        records = self.env['aula_metrics.metric_value'].search(domain, limit=_RESULT_LIMIT)
        if not records:
            return None

        # Para tutores: también cargar todos los registros para center_avg/level_avg reales
        if is_tutor:
            center_records = self.env['aula_metrics.metric_value'].sudo().search(
                base_domain, limit=_RESULT_LIMIT
            )
        else:
            center_records = records

        # Pre-resolver alumno → grupo como fallback cuando academic_group_id es null
        def _build_smap(rset, use_sudo=False):
            pids     = list({r.student_id.id for r in rset if r.student_id})
            env      = self.env['res.partner'].sudo() if use_sudo else self.env['res.partner']
            partners = env.browse(pids)
            return {p.id: p.academic_group_id for p in partners if p.academic_group_id}

        student_grp_map    = _build_smap(records)
        center_student_map = _build_smap(center_records, use_sudo=True) if is_tutor else student_grp_map

        # Cache de course_level por group record
        _lvl_cache = {}

        def _get_level(grp):
            if not grp:
                return 'sin_nivel'
            if grp.id not in _lvl_cache:
                _lvl_cache[grp.id] = grp.course_level or 'sin_nivel'
            return _lvl_cache[grp.id]

        def _get_grp(r, smap):
            return r.academic_group_id or smap.get(r.student_id.id)

        # ── Acumular datos del tutor por métrica × grupo ──────────────────
        # metric_name → {label, grp_data: {gid → {name, level, values}}}
        metrics_map = defaultdict(lambda: {
            'label': '',
            'grp_data': defaultdict(lambda: {'name': '', 'level': '', 'values': []}),
        })
        for r in records:
            mn  = r.metric_name or ''
            grp = _get_grp(r, student_grp_map)
            gid = grp.id if grp else 0
            metrics_map[mn]['label'] = r.metric_label or mn.replace('_', ' ').capitalize()
            gd = metrics_map[mn]['grp_data'][gid]
            if not gd['name']:
                gd['name']  = grp.name if grp else 'Sin grupo'
                gd['level'] = _get_level(grp)
            if r.value_float is not None:
                gd['values'].append(float(r.value_float))

        # ── Acumular datos del centro por métrica × grupo ─────────────────
        center_map = defaultdict(lambda: defaultdict(lambda: {'level': '', 'values': []}))
        for r in center_records:
            mn  = r.metric_name or ''
            grp = _get_grp(r, center_student_map)
            gid = grp.id if grp else 0
            cd  = center_map[mn][gid]
            if not cd['level']:
                cd['level'] = _get_level(grp)
            if r.value_float is not None:
                cd['values'].append(float(r.value_float))

        # ── Construir salida ──────────────────────────────────────────────
        metrics_out = []
        for mn in sorted(metrics_map.keys()):
            md       = metrics_map[mn]
            grp_data = md['grp_data']

            groups_out = []
            for gid in sorted(grp_data.keys(), key=lambda g: grp_data[g]['name']):
                gd   = grp_data[gid]
                vals = gd['values']
                if not vals:
                    continue
                groups_out.append({
                    'group_id':   gid,
                    'group_name': gd['name'],
                    'n':          len(vals),
                    'avg':        round(sum(vals) / len(vals), 2),
                    'min':        round(min(vals), 2),
                    'max':        round(max(vals), 2),
                })

            # Nivel educativo desde datos del centro (= real para todos los roles)
            level_agg = defaultdict(lambda: {'n': 0, 'weighted_sum': 0.0, 'label': '', 'values': []})
            for gid, cd in center_map[mn].items():
                lvl = cd['level']
                if not level_agg[lvl]['label']:
                    level_agg[lvl]['label'] = _fmt_course_level(lvl)
                vals = cd['values']
                for v in vals:
                    level_agg[lvl]['n']            += 1
                    level_agg[lvl]['weighted_sum'] += v
                    level_agg[lvl]['values'].append(v)

            by_level = []
            for lvl in sorted(level_agg.keys()):
                agg = level_agg[lvl]
                if agg['n'] > 0:
                    by_level.append({
                        'level': lvl,
                        'label': agg['label'] or _fmt_course_level(lvl),
                        'n':     agg['n'],
                        'avg':   round(agg['weighted_sum'] / agg['n'], 2),
                        'min':   round(min(agg['values']), 2),
                        'max':   round(max(agg['values']), 2),
                    })

            all_center_vals = [v for cd in center_map[mn].values() for v in cd['values']]
            center_avg      = (
                round(sum(all_center_vals) / len(all_center_vals), 2)
                if all_center_vals else None
            )
            center_min = round(min(all_center_vals), 2) if all_center_vals else None
            center_max = round(max(all_center_vals), 2) if all_center_vals else None

            # Para tutores: referencia de nivel de sus grupos
            tutor_level_ref = None
            if is_tutor and groups_out:
                tutor_levels = {grp_data[g['group_id']]['level'] for g in groups_out}
                tutor_level_ref = {
                    lv['level']: {
                        'avg':   lv['avg'],
                        'label': lv['label'],
                        'n':     lv['n'],
                        'min':   lv.get('min'),
                        'max':   lv.get('max'),
                    }
                    for lv in by_level if lv['level'] in tutor_levels
                }

            metrics_out.append({
                'metric_name':     mn,
                'metric_label':    md['label'],
                'groups':          groups_out,
                'by_level':        by_level,
                'center_avg':      center_avg,
                'center_min':      center_min,
                'center_max':      center_max,
                'center_n':        len(all_center_vals),
                'tutor_level_ref': tutor_level_ref,
            })

        return {
            'survey_id':      survey.id,
            'survey_name':    survey.title or '',
            'is_aulametrics': False,
            'metrics':        metrics_out,
        }

    @api.model
    def _get_text_survey_data(self, survey, evaluation, role_info):
        """
        Para cuestionarios de texto abierto.
        Devuelve tabla de frecuencia de palabras agregada por centro, nivel
        educativo y grupo, con visibilidad según rol:
          Admin/Counselor → centro + niveles + todos los grupos
          Management      → centro + niveles (sin grupos)
          Tutor           → centro + niveles + solo sus grupos
        """
        role     = role_info.get('role')
        is_tutor = role == ROLE_TUTOR
        allowed  = role_info.get('allowed_group_ids', [])

        base_domain = [
            ('survey_id',     '=', survey.id),
            ('evaluation_id', '=', evaluation.id),
        ]
        if is_tutor:
            if not allowed:
                return None
            domain = base_domain + [('academic_group_id', 'in', allowed)]
        else:
            domain = base_domain

        responses = self.env['aula_metrics.qualitative_response'].search(
            domain, order='course_level, academic_group_id', limit=500
        )
        if not responses:
            return None

        # Para tutores: cargar todas las respuestas del centro para centro/nivel reales
        if is_tutor:
            center_responses = self.env['aula_metrics.qualitative_response'].sudo().search(
                base_domain, order='course_level, academic_group_id', limit=500
            )
        else:
            center_responses = responses

        show_groups = role in (ROLE_ADMIN, ROLE_COUNSELOR, ROLE_TUTOR)

        all_texts   = []
        level_texts = defaultdict(list)
        group_texts = defaultdict(list)
        group_order = []   # preserves first-seen insertion order
        seen_groups = set()

        # Niveles que corresponden a los grupos del tutor (para filtrar columnas de nivel)
        tutor_levels_set = set()
        if is_tutor:
            for r in responses:
                if r.course_level:
                    tutor_levels_set.add(r.course_level)

        for r in center_responses:
            txt = r.response_text or ''
            all_texts.append(txt)
            lvl = r.course_level or 'sin_nivel'
            # Para tutores: solo acumular el nivel propio, no todos los del centro
            if not is_tutor or lvl in tutor_levels_set:
                level_texts[lvl].append(txt)

        for r in responses:
            txt = r.response_text or ''
            if show_groups:
                gname = r.academic_group_id.name if r.academic_group_id else '—'
                if gname not in seen_groups:
                    seen_groups.add(gname)
                    group_order.append(gname)
                group_texts[gname].append(txt)

        center_ctr = _word_freq(all_texts)
        if not center_ctr:
            return None

        top_words   = [w for w, _ in center_ctr.most_common(10)]
        levels      = sorted(
            ((lvl, _fmt_course_level(lvl)) for lvl in level_texts),
            key=lambda x: x[0]
        )

        return {
            'survey_id':      survey.id,
            'survey_name':    survey.title or '',
            'is_aulametrics': False,
            'is_text_survey': True,
            'n_responses':    len(responses),
            'top_words':      top_words,
            'center_freq':    dict(center_ctr),
            'level_freq':     {lvl: dict(_word_freq(txts)) for lvl, txts in level_texts.items()},
            'group_freq':     (
                {gn: dict(_word_freq(txts)) for gn, txts in group_texts.items()}
                if show_groups else {}
            ),
            'levels':         levels,       # [(code, label), ...]
            'groups':         group_order,    # [group_name, ...]
            'show_groups':    show_groups,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Contexto de error (stub; el renderizado real está en _sections.py)
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _error_context(self, message):
        """Contexto mínimo para mostrar un mensaje de error en dashboard_page_base."""
        return {
            'page_title':           'Error - Informe de Evaluación',
            'css_styles':           Markup(dashboard_styles.get_common_styles()),
            'head_extra':           Markup(''),
            'role_info':            {},
            'active_section':       'evaluations',
            'topbar_title':         'Informe de Evaluación',
            'topbar_subtitle':      Markup(''),
            'topbar_extra_actions': Markup(''),
            'content_html':         Markup(
                f'<div class="alert alert-danger m-4">'
                f'<i class="fa fa-circle-exclamation me-2"></i>{message}'
                f'</div>'
            ),
            'scripts_html':         Markup(''),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de módulo (privados)
# ──────────────────────────────────────────────────────────────────────────────

class _EmptyGroup:
    """Sentinel usado en sorted() para grupos sin metadatos."""
    name = ''


def _fmt_course_level(code):
    """
    Formatea un código de nivel educativo a texto legible.
    Fallback genérico que funciona con cualquier código futuro.
    """
    _MAP = {
        'eso1': 'ESO 1º', 'eso2': 'ESO 2º', 'eso3': 'ESO 3º', 'eso4': 'ESO 4º',
        'bach1': 'Bachillerato 1º', 'bach2': 'Bachillerato 2º',
    }
    return _MAP.get(code, code.replace('_', ' ').capitalize() if code else 'Sin nivel')
