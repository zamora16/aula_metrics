# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
import re
from datetime import datetime, date as _date

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_GENDER_MAP = {
    'm': 'male', 'masculino': 'male', 'hombre': 'male', 'h': 'male', 'male': 'male',
    'f': 'female', 'femenino': 'female', 'mujer': 'female', 'female': 'female',
    'otro': 'other', 'other': 'other', 'o': 'other',
    'prefer_not_say': 'prefer_not_say', 'ns/nc': 'prefer_not_say',
}

_HEADER_MAP = {
    'nombre': 'nombre', 'name': 'nombre', 'first_name': 'nombre',
    'apellidos': 'apellidos', 'apellido': 'apellidos',
    'surname': 'apellidos', 'last_name': 'apellidos', 'apellidos/nombre2': 'apellidos',
    'grupo': 'grupo', 'group': 'grupo', 'clase': 'grupo', 'class': 'grupo',
    'email': 'email', 'correo': 'email', 'e-mail': 'email', 'correo electrónico': 'email',
    'género': 'genero', 'genero': 'genero', 'gender': 'genero', 'sexo': 'genero',
    'fecha_nacimiento': 'fecha_nacimiento', 'fecha nacimiento': 'fecha_nacimiento',
    'fechanacimiento': 'fecha_nacimiento', 'birth_date': 'fecha_nacimiento',
    'birthdate': 'fecha_nacimiento', 'nacimiento': 'fecha_nacimiento',
    'f. nacimiento': 'fecha_nacimiento', 'fnacimiento': 'fecha_nacimiento',
}


class StudentImportLine(models.TransientModel):
    _name = 'aula_metrics.student_import_line'
    _description = 'Línea de previsualización de importación de alumnos'
    _order = 'row_num'

    wizard_id = fields.Many2one(
        'aula_metrics.student_import_wizard',
        ondelete='cascade',
        required=True,
    )
    row_num = fields.Integer(string='Fila', readonly=True)
    first_name = fields.Char(string='Nombre', readonly=True)
    last_name = fields.Char(string='Apellidos', readonly=True)
    group_name = fields.Char(string='Grupo (CSV)', readonly=True)
    group_id = fields.Many2one(
        'aula_metrics.academic_group',
        string='Grupo resuelto',
        readonly=True,
    )
    email = fields.Char(string='Email', readonly=True)
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro'),
        ('prefer_not_say', 'Prefiero no decir'),
    ], string='Género', readonly=True)
    birthdate = fields.Date(string='Nacimiento', readonly=True)
    status = fields.Selection([
        ('ok', 'OK'),
        ('warn', 'Aviso'),
        ('error', 'Error'),
    ], string='Estado', default='ok', readonly=True)
    message = fields.Char(string='Incidencia', readonly=True)
    will_import = fields.Boolean(
        string='Importar',
        default=True,
        help='Desmarca para excluir manualmente esta fila de la importación.',
    )


class StudentImportWizard(models.TransientModel):
    _name = 'aula_metrics.student_import_wizard'
    _description = 'Importación masiva de alumnos por CSV'

    state = fields.Selection([
        ('upload', 'Cargar fichero'),
        ('preview', 'Vista previa'),
        ('done', 'Resultado'),
    ], default='upload', required=True, string='Estado')

    csv_file = fields.Binary(string='Fichero CSV', attachment=False)
    csv_filename = fields.Char(string='Nombre del fichero')

    preview_line_ids = fields.One2many(
        'aula_metrics.student_import_line',
        'wizard_id',
        string='Filas',
    )

    valid_count = fields.Integer(string='Filas OK', compute='_compute_counts')
    warn_count = fields.Integer(string='Avisos', compute='_compute_counts')
    error_count_preview = fields.Integer(string='Errores', compute='_compute_counts')

    result_imported = fields.Integer(string='Importados', readonly=True)
    result_skipped = fields.Integer(string='Saltados', readonly=True)
    result_errors = fields.Integer(string='Errores', readonly=True)
    result_details = fields.Text(string='Detalles', readonly=True)

    @api.depends('preview_line_ids.status')
    def _compute_counts(self):
        for wiz in self:
            lines = wiz.preview_line_ids
            wiz.valid_count = len(lines.filtered(lambda l: l.status == 'ok'))
            wiz.warn_count = len(lines.filtered(lambda l: l.status == 'warn'))
            wiz.error_count_preview = len(lines.filtered(lambda l: l.status == 'error'))

    # ── CSV parsing helpers ───────────────────────────────────────────────────

    def _decode_csv(self):
        raw = base64.b64decode(self.csv_file)
        for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        raise UserError(_('No se pudo decodificar el fichero. Usa codificación UTF-8 o latin-1.'))

    @staticmethod
    def _detect_delimiter(first_line):
        if first_line.count(';') >= first_line.count(','):
            return ';'
        return ','

    @staticmethod
    def _parse_date(val):
        if not val:
            return False
        # openpyxl may return date/datetime objects directly
        if isinstance(val, _date):
            return val if isinstance(val, _date) and not isinstance(val, datetime) else val.date()
        if isinstance(val, datetime):
            return val.date()
        val = str(val).strip()
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        return False

    @staticmethod
    def _normalize_gender(val):
        if not val:
            return False
        return _GENDER_MAP.get(val.strip().lower(), False)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _parse_upload_file(self):
        """Parsea el fichero subido (CSV o Excel) y devuelve una lista de dicts
        con claves: first_name, last_name, group_name, email, gender, birthdate."""
        filename = (self.csv_filename or '').lower()
        raw = base64.b64decode(self.csv_file)

        if filename.endswith(('.xlsx', '.xls')):
            return self._parse_xlsx(raw)
        else:
            return self._parse_csv_bytes(raw)

    def _parse_csv_bytes(self, raw):
        for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                text = raw.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            raise UserError(_('No se pudo decodificar el fichero. Usa UTF-8 o latin-1.'))

        lines_text = text.splitlines()
        if not lines_text:
            raise UserError(_('El fichero está vacío.'))

        delimiter = self._detect_delimiter(lines_text[0])
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        try:
            raw_fieldnames = reader.fieldnames or []
        except Exception:
            raise UserError(_('No se pudo leer la cabecera del CSV.'))
        if not raw_fieldnames:
            raise UserError(_('El fichero no tiene cabecera.'))

        norm_fieldnames = [f.strip().lower() for f in raw_fieldnames]
        mapped_headers = {_HEADER_MAP.get(f, f): f for f in norm_fieldnames}
        missing = {'nombre', 'apellidos', 'grupo'} - set(mapped_headers.keys())
        if missing:
            raise UserError(_(
                'Faltan columnas obligatorias: %s\nColumnas detectadas: %s'
            ) % (', '.join(sorted(missing)), ', '.join(norm_fieldnames)))

        rows = []
        for raw_row in reader:
            row = {}
            for raw_k, v in raw_row.items():
                if raw_k:
                    norm_k = _HEADER_MAP.get(raw_k.strip().lower(), raw_k.strip().lower())
                    row[norm_k] = (v or '').strip()
            rows.append({
                'first_name': row.get('nombre', ''),
                'last_name': row.get('apellidos', ''),
                'group_name': row.get('grupo', ''),
                'email': row.get('email', '') or False,
                'gender': self._normalize_gender(row.get('genero', '')),
                'birthdate': self._parse_date(row.get('fecha_nacimiento', '')),
            })
        return rows

    def _parse_xlsx(self, raw):
        """Lee un .xlsx generado por la plantilla: una hoja por grupo.
        Columnas esperadas: nombre, apellidos, email, genero, fecha_nacimiento.
        El nombre del grupo se toma del título de la hoja."""
        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception as e:
            raise UserError(_('No se pudo abrir el fichero Excel: %s') % str(e))

        rows = []
        for sheet in wb.worksheets:
            group_name = sheet.title.strip()
            header = None
            for i, xl_row in enumerate(sheet.iter_rows(values_only=True)):
                # Saltar filas vacías antes de la cabecera
                if all(c is None or str(c).strip() == '' for c in xl_row):
                    continue
                if header is None:
                    def _normalize_header(c):
                        if c is None:
                            return ''
                        # lowercase, strip asterisks, strip parenthetical annotations
                        h = str(c).strip().lower()
                        h = re.sub(r'\s*\(.*?\)', '', h).strip()
                        h = h.rstrip(' *').strip()
                        return _HEADER_MAP.get(h, h)
                    header = [_normalize_header(c) for c in xl_row]
                    # Validar columnas obligatorias de esta hoja
                    missing = {'nombre', 'apellidos'} - set(header)
                    if missing:
                        raise UserError(_(
                            'Hoja "%s": faltan columnas obligatorias: %s'
                        ) % (group_name, ', '.join(sorted(missing))))
                    continue
                # Build row dict — preserve raw cell values for date/datetime cells
                row = dict(zip(header, [c for c in xl_row]))
                # Saltar filas completamente vacías de datos
                nombre = str(row.get('nombre') or '').strip()
                apellidos = str(row.get('apellidos') or '').strip()
                if not nombre and not apellidos:
                    continue
                rows.append({
                    'first_name': nombre,
                    'last_name': apellidos,
                    'group_name': group_name,
                    'email': str(row.get('email') or '').strip() or False,
                    'gender': self._normalize_gender(str(row.get('genero') or '').strip()),
                    'birthdate': self._parse_date(row.get('fecha_nacimiento')),
                })
        return rows

    def action_preview(self):
        self.ensure_one()
        if not self.csv_file:
            raise UserError(_('Por favor, selecciona un fichero.'))

        current_year = self.env['aula_metrics.academic_year'].get_current_year()
        if not current_year:
            raise UserError(_('No hay ningún curso académico activo.'))

        active_groups = {
            g.name.strip().lower(): g
            for g in self.env['aula_metrics.academic_group'].search([
                ('academic_year_id', '=', current_year.id),
            ])
        }

        active_group_ids = [g.id for g in active_groups.values()]
        existing_students = set()
        for s in self.env['res.partner'].search([
            ('academic_group_id', 'in', active_group_ids),
        ]):
            key = ((s.name or '').strip().lower(), s.academic_group_id.id)
            existing_students.add(key)

        parsed_rows = self._parse_upload_file()
        if not parsed_rows:
            raise UserError(_('El fichero no contiene filas de datos.'))

        line_vals = []
        for i, row in enumerate(parsed_rows, start=2):
            first_name = row['first_name']
            last_name = row['last_name']
            group_name = row['group_name']
            email = row['email']
            gender = row['gender']
            birthdate = row['birthdate']

            full_name = f"{first_name} {last_name}".strip()
            status = 'ok'
            message = ''
            group_id = False

            if not first_name or not last_name:
                status = 'error'
                message = 'Nombre o apellidos vacíos'
            elif not group_name:
                status = 'error'
                message = 'Grupo vacío'
            else:
                group = active_groups.get(group_name.lower())
                if not group:
                    status = 'error'
                    message = 'Grupo "%s" no encontrado en el curso activo' % group_name
                else:
                    group_id = group.id
                    if (full_name.lower(), group.id) in existing_students:
                        status = 'warn'
                        message = 'Ya existe este alumno en este grupo (se saltará)'

            line_vals.append({
                'row_num': i,
                'first_name': first_name,
                'last_name': last_name,
                'group_name': group_name,
                'group_id': group_id,
                'email': email,
                'gender': gender,
                'birthdate': birthdate,
                'status': status,
                'message': message,
                'will_import': status == 'ok',
            })

        if not line_vals:
            raise UserError(_('El fichero no contiene filas de datos.'))

        self.preview_line_ids.unlink()
        self.env['aula_metrics.student_import_line'].create(
            [{**v, 'wizard_id': self.id} for v in line_vals]
        )
        self.state = 'preview'
        return self._reload_action()

    def action_import(self):
        self.ensure_one()
        imported = 0
        skipped = 0
        errors = 0
        details = []

        for line in self.preview_line_ids:
            if not line.will_import or line.status in ('warn', 'error'):
                skipped += 1
                if line.message:
                    details.append('Fila %d: saltado — %s' % (line.row_num, line.message))
                continue

            full_name = '%s %s' % (line.first_name, line.last_name)
            vals = {
                'name': full_name.strip(),
                'student_firstname': line.first_name,
                'student_lastname': line.last_name,
                'academic_group_id': line.group_id.id,
                'is_company': False,
            }
            if line.email:
                vals['email'] = line.email
            if line.gender:
                vals['gender'] = line.gender
            if line.birthdate:
                vals['birthdate'] = line.birthdate

            try:
                self.env['res.partner'].create(vals)
                imported += 1
            except Exception as e:
                errors += 1
                details.append('Fila %d (%s): error al crear — %s' % (line.row_num, full_name, e))
                _logger.error('Error importing row %s: %s', line.row_num, e, exc_info=True)

        self.result_imported = imported
        self.result_skipped = skipped
        self.result_errors = errors
        self.result_details = '\n'.join(details) if details else 'Sin incidencias.'
        self.state = 'done'
        return self._reload_action()

    def action_download_template(self):
        """Genera y descarga una plantilla Excel (.xlsx) con una hoja por grupo."""
        self.ensure_one()
        current_year = self.env['aula_metrics.academic_year'].get_current_year()

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # quitar hoja vacía por defecto

        # Estilos
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill('solid', fgColor='2E5FA3')
        header_align = Alignment(horizontal='center')
        example_fill = PatternFill('solid', fgColor='EAF0FB')

        HEADERS = ['nombre', 'apellidos', 'email', 'genero', 'fecha_nacimiento']
        HEADER_LABELS = ['Nombre *', 'Apellidos *', 'Email', 'Género (M/F/Otro)', 'F. Nacimiento (DD/MM/AAAA)']
        COL_WIDTHS = [20, 25, 28, 18, 24]

        def _make_sheet(name):
            ws = wb.create_sheet(title=name[:31])  # Excel limita títulos a 31 chars
            # Cabecera
            for col, (label, width) in enumerate(zip(HEADER_LABELS, COL_WIDTHS), start=1):
                cell = ws.cell(row=1, column=col, value=label)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
                ws.column_dimensions[get_column_letter(col)].width = width
            # Fila de ejemplo en gris claro
            example = ['Juan', 'García López', 'juan@ejemplo.com', 'M', '15/09/2010']
            for col, val in enumerate(example, start=1):
                cell = ws.cell(row=2, column=col, value=val)
                cell.fill = example_fill
                cell.font = Font(italic=True, color='888888')
            # Filas vacías para rellenar (10 filas)
            for row in range(3, 23):
                for col in range(1, len(HEADERS) + 1):
                    ws.cell(row=row, column=col, value='')
            ws.freeze_panes = 'A2'
            return ws

        if current_year:
            groups = self.env['aula_metrics.academic_group'].search([
                ('academic_year_id', '=', current_year.id),
            ], order='name')
            for group in groups:
                _make_sheet(group.name)
        else:
            _make_sheet('Ejemplo — 1º ESO A')

        buf = io.BytesIO()
        wb.save(buf)
        xlsx_b64 = base64.b64encode(buf.getvalue()).decode()
        filename = 'plantilla_alumnos.xlsx'

        self.write({'csv_file': xlsx_b64, 'csv_filename': filename})

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?model=%s&id=%s&field=csv_file&filename=%s&download=true' % (
                self._name, self.id, filename,
            ),
            'target': 'self',
        }

    def action_back_to_upload(self):
        self.ensure_one()
        self.state = 'upload'
        return self._reload_action()

    def _reload_action(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
