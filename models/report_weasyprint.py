# -*- coding: utf-8 -*-
import io
import re
import logging

import lxml.html

from odoo import models
from odoo.tools.pdf import PdfFileWriter, PdfFileReader
from odoo.http import request as http_request

# Silenciar warnings de CSS moderno (calc vw, range media queries) que
# Bootstrap genera y WeasyPrint no soporta. No afectan al resultado porque
# las plantillas tienen todos los estilos inline.
logging.getLogger('weasyprint').setLevel(logging.CRITICAL)
logging.getLogger('weasyprint').propagate = False
logging.getLogger('fontTools').setLevel(logging.CRITICAL)


def _make_url_fetcher(base_url, session_id=None):
    try:
        from weasyprint.urls import URLFetcher, URLFetcherResponse
    except ImportError:
        return None

    from urllib.parse import urlparse, urljoin
    import urllib.request as urllib_req
    from email.message import EmailMessage

    parsed_base = urlparse(base_url)

    class OdooURLFetcher(URLFetcher):
        def fetch(self, url, headers=None):
            parsed = urlparse(url)
            is_same_origin = (
                parsed.netloc == parsed_base.netloc
                or not parsed.netloc
                or parsed.netloc in ('localhost', '127.0.0.1')
            )
            if is_same_origin and session_id:
                try:
                    full_url = urljoin(base_url, url) if not parsed.netloc else url
                    req = urllib_req.Request(full_url)
                    req.add_header('Cookie', f'session_id={session_id}')
                    resp = urllib_req.urlopen(req, timeout=10)
                    hdrs = EmailMessage()
                    for k, v in resp.headers.items():
                        try:
                            hdrs[k] = v
                        except Exception:
                            pass
                    return URLFetcherResponse(resp.url, resp.read(), hdrs, resp.status)
                except Exception:
                    return URLFetcherResponse(url, b'', EmailMessage(), 200)
            try:
                return super().fetch(url, headers=headers)
            except Exception:
                return URLFetcherResponse(url, b'', EmailMessage(), 200)

    return OdooURLFetcher()


# WeasyPrint renderiza fuentes marginalmente más altas que un motor de browser,
# lo que provoca que el flex container de 297mm desborde y genere una página
# extra con solo el footer. Para páginas de altura fija se fuerza body a 297mm
# y se corta el overflow. Para páginas de contenido dinámico (evaluaciones con
# n escalas variable) se deja que WeasyPrint pagine libremente y solo se
# restablecen los márgenes.
_WP_FIX_FIXED = (
    '<style>'
    'html,body{height:297mm!important;margin:0!important;padding:0!important}'
    '.am-report{overflow:hidden!important}'
    '</style>'
)

_WP_FIX_FLOW = (
    '<style>'
    'html,body{margin:0!important;padding:0!important}'
    # Primera página del documento: sin margen superior (la cabecera es full-bleed)
    # Páginas de continuación (2, 3…): margen superior para que el contenido
    # no aparezca pegado al borde cuando un cuestionario ocupa varias páginas.
    '@page :first{margin-top:0}'
    '@page{margin-top:18pt}'
    '</style>'
)

# Clases CSS que identifican páginas diseñadas para ocupar exactamente 297mm.
_FIXED_PAGE_CLASSES = {'am-report', 'am-ev-cover-page'}


def _build_page_html(main_node, base_tag, inline_styles):
    style_attr = re.sub(r'(?:page-break|break)-\w+\s*:\s*[^;]+;?\s*', '', main_node.get('style', '')).strip()
    if style_attr:
        main_node.set('style', style_attr)
    elif 'style' in main_node.attrib:
        del main_node.attrib['style']

    node_classes = set((main_node.get('class', '') or '').split())
    wp_fix = _WP_FIX_FIXED if node_classes & _FIXED_PAGE_CLASSES else _WP_FIX_FLOW

    return (
        '<!DOCTYPE html><html>\n'
        '<head>\n'
        '<meta charset="utf-8"/>\n'
        f'{base_tag}\n'
        f'{inline_styles}\n'
        f'{wp_fix}\n'
        '</head>\n'
        f'<body>\n{lxml.html.tostring(main_node, encoding="unicode")}\n</body>\n'
        '</html>'
    )


def _split_html_by_main(html_string):
    root = lxml.html.fromstring(html_string, parser=lxml.html.HTMLParser(encoding='utf-8'))
    mains = root.xpath('//main')
    if not mains:
        return None

    base_tag = ''
    head_node = root.find('.//head')
    if head_node is not None:
        for child in head_node:
            if (child.tag or '').lower() == 'base':
                base_tag = lxml.html.tostring(child, encoding='unicode')
                break

    inline_styles = '\n'.join(
        lxml.html.tostring(s, encoding='unicode')
        for s in root.xpath('//body//style')
    )

    return [_build_page_html(main, base_tag, inline_styles) for main in mains]


class IrActionsReportWeasyprint(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(
            self,
            bodies,
            report_ref=False,
            header=None,
            footer=None,
            landscape=False,
            specific_paperformat_args=None,
            set_viewport_size=False):

        try:
            from weasyprint import HTML
        except ImportError:
            return super()._run_wkhtmltopdf(
                bodies, report_ref=report_ref, header=header, footer=footer,
                landscape=landscape, specific_paperformat_args=specific_paperformat_args,
                set_viewport_size=set_viewport_size,
            )

        try:
            base_url = self._get_report_url()
        except Exception:
            base_url = self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url', 'http://localhost:8069'
            )

        session_id = None
        try:
            if http_request and http_request.db and http_request.session.sid:
                session_id = http_request.session.sid
        except RuntimeError:
            pass

        url_fetcher = _make_url_fetcher(base_url, session_id)
        all_streams = []

        for body in bodies:
            page_docs = _split_html_by_main(body)
            if page_docs is None:
                fixed = re.sub(
                    r'(<html[^>]*style=["\'])([^"\']*)',
                    lambda m: m.group(1) + m.group(2).replace('height: 0', 'height: auto'),
                    body, count=1,
                )
                all_streams.append(io.BytesIO(HTML(string=fixed, base_url=base_url, url_fetcher=url_fetcher).write_pdf()))
            else:
                for page_doc in page_docs:
                    all_streams.append(io.BytesIO(HTML(string=page_doc, base_url=base_url, url_fetcher=url_fetcher).write_pdf()))

        if len(all_streams) == 1:
            return all_streams[0].getvalue()

        writer = PdfFileWriter()
        for stream in all_streams:
            reader = PdfFileReader(stream)
            for i in range(reader.numPages):
                writer.addPage(reader.getPage(i))

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
