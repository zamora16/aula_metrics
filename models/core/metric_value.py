# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MetricValue(models.Model):
    """
    Almacena valores de métricas individuales por estudiante/evaluación.
    Permite comparaciones temporales y almacenamiento flexible de cualquier métrica.
    """
    _name = 'aula_metrics.metric_value'
    _description = 'Valor de Métrica Individual'
    _order = 'timestamp desc, id desc'

    # Relaciones
    survey_id = fields.Many2one(
        'survey.survey',
        string='Encuesta',
        required=True,
        ondelete='cascade',
        index=True
    )
    student_id = fields.Many2one(
        'res.partner',
        string='Estudiante',
        required=True,
        ondelete='cascade',
        index=True
    )
    evaluation_id = fields.Many2one(
        'aula_metrics.evaluation',
        string='Evaluación',
        required=True,
        ondelete='cascade',
        index=True
    )
    question_id = fields.Many2one(
        'survey.question',
        string='Pregunta',
        ondelete='set null',
        help='Pregunta específica si aplica'
    )
    user_input_id = fields.Many2one(
        'survey.user_input',
        string='Respuesta de Encuesta',
        ondelete='cascade',
        help='Referencia a la respuesta completa de la encuesta'
    )

    # Datos de la métrica
    metric_name = fields.Char(
        string='Nombre de Métrica',
        required=True,
        index=True,
        help='Identificador de la métrica (ej: who5_score, bullying_victimization, custom_metric_1)'
    )
    metric_label = fields.Char(
        string='Etiqueta de Métrica',
        help='Nombre legible de la métrica'
    )

    # Valores (almacenamiento flexible según tipo)
    value_float = fields.Float(
        string='Valor Numérico',
        help='Para métricas numéricas (scores, escalas Likert, etc.)'
    )
    value_text = fields.Text(
        string='Valor Texto',
        help='Para respuestas abiertas, selección múltiple (JSON), etc.'
    )
    value_json = fields.Json(
        string='Valor JSON',
        help='Para datos estructurados complejos'
    )

    # Metadatos
    timestamp = fields.Datetime(
        string='Fecha y Hora',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    academic_group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo Académico',
        store=True,
        readonly=True,
        index=True,
        ondelete='set null',
        help='Grupo del alumno en el momento de registrar esta métrica (dato histórico, no cambia al cambiar de curso).'
    )

    academic_year_id = fields.Many2one(
        'aula_metrics.academic_year',
        string='Curso Académico',
        store=True,
        readonly=True,
        index=True,
        ondelete='set null',
        help='Curso académico de la evaluación en el momento de registrar esta métrica (dato histórico).'
    )

    # Campos auxiliares
    notes = fields.Text(
        string='Notas',
        help='Información adicional sobre esta métrica'
    )

    _sql_constraints = [
        (
            'unique_metric_per_response',
            'UNIQUE(survey_id, student_id, evaluation_id, metric_name, question_id)',
            'Ya existe un valor para esta métrica en esta combinación de encuesta/estudiante/evaluación/pregunta'
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Congela el grupo académico y el curso del alumno en el momento de crear la métrica.
        Así los datos históricos no se alteran cuando el alumno cambia de grupo al año siguiente.
        """
        for vals in vals_list:
            if 'academic_group_id' not in vals and vals.get('student_id'):
                student = self.env['res.partner'].browse(vals['student_id'])
                vals['academic_group_id'] = student.academic_group_id.id or False
            if 'academic_year_id' not in vals and vals.get('evaluation_id'):
                evaluation = self.env['aula_metrics.evaluation'].browse(vals['evaluation_id'])
                vals['academic_year_id'] = evaluation.academic_year_id.id or False
        return super().create(vals_list)

    def name_get(self):
        """Representación legible del registro"""
        result = []
        for record in self:
            name = f"{record.metric_label or record.metric_name} - {record.student_id.name} ({record.evaluation_id.name})"
            result.append((record.id, name))
        return result

    @api.model
    def get_metric_history(self, student_id, metric_name, limit=None):
        """
        Obtiene el historial de una métrica específica para un estudiante.
        Útil para gráficos de evolución temporal.
        """
        domain = [
            ('student_id', '=', student_id),
            ('metric_name', '=', metric_name)
        ]
        return self.search(domain, order='timestamp asc', limit=limit)

    @api.model
    def get_metric_summary(self, evaluation_id, metric_name):
        """
        Obtiene estadísticas resumidas de una métrica para una evaluación.
        Retorna dict con count, avg, min, max.
        """
        records = self.search([
            ('evaluation_id', '=', evaluation_id),
            ('metric_name', '=', metric_name),
            ('value_float', '!=', None)
        ])
        
        if not records:
            return {'count': 0, 'avg': 0, 'min': 0, 'max': 0}
        
        values = records.mapped('value_float')
        return {
            'count': len(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values)
        }
    
    @api.model
    def clean_duplicate_metrics(self):
        """
        Limpia métricas duplicadas usando SQL directo en lugar de cargar todos los
        registros en memoria. Mantiene el registro con datos más completos por grupo
        (prioridad: tiene valor > timestamp más reciente > id más alto).

        La agrupación es la misma que define el constraint único del modelo:
        (survey_id, student_id, evaluation_id, metric_name, question_id).
        """
        # Una sola query con ROW_NUMBER() identifica qué registros son duplicados.
        # rn = 1 → el registro a conservar; rn > 1 → duplicados a eliminar.
        self.env.cr.execute("""
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            survey_id,
                            student_id,
                            evaluation_id,
                            metric_name,
                            COALESCE(question_id, 0)
                        ORDER BY
                            -- Primero los registros que tienen algún valor
                            CASE
                                WHEN value_float IS NOT NULL
                                  OR value_text  IS NOT NULL
                                  OR value_json  IS NOT NULL
                                THEN 0 ELSE 1
                            END ASC,
                            -- Luego el más reciente
                            timestamp DESC,
                            -- Desempate por id más alto
                            id DESC
                    ) AS rn
                FROM aula_metrics_metric_value
            )
            SELECT id FROM ranked WHERE rn > 1
        """)
        ids_to_delete = [row[0] for row in self.env.cr.fetchall()]

        if not ids_to_delete:
            return 0

        # unlink() a través del ORM para que Odoo invalide su caché
        duplicates = self.browse(ids_to_delete)
        count = len(duplicates)
        duplicates.unlink()
        return count
