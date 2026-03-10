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
        related='student_id.academic_group_id',
        store=True,
        index=True
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
        Limpia métricas duplicadas, manteniendo solo el registro con datos.
        Útil para limpiar duplicados creados por errores de guardado múltiple.
        """
        # Buscar todos los registros
        all_records = self.search([], order='id')
        
        # Agrupar por la clave única
        groups = {}
        for record in all_records:
            key = (
                record.survey_id.id,
                record.student_id.id,
                record.evaluation_id.id,
                record.metric_name,
                record.question_id.id if record.question_id else False
            )
            
            if key not in groups:
                groups[key] = []
            groups[key].append(record)
        
        # Eliminar duplicados de cada grupo
        deleted_count = 0
        for key, records in groups.items():
            if len(records) > 1:
                # Ordenar por prioridad: primero los que tienen datos
                records_sorted = sorted(records, key=lambda r: (
                    bool(r.value_float or r.value_json or r.value_text),
                    r.timestamp,
                    r.id
                ), reverse=True)
                
                # Mantener el primero (el que tiene datos más recientes)
                keep = records_sorted[0]
                to_delete = records_sorted[1:]
                
                # Eliminar los demás
                for record in to_delete:
                    try:
                        record.unlink()
                        deleted_count += 1
                    except Exception:
                        pass
        
        return deleted_count
