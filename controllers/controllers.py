# -*- coding: utf-8 -*-
# from odoo import http


# class AulaMetrics(http.Controller):
#     @http.route('/aula_metrics/aula_metrics', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/aula_metrics/aula_metrics/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('aula_metrics.listing', {
#             'root': '/aula_metrics/aula_metrics',
#             'objects': http.request.env['aula_metrics.aula_metrics'].search([]),
#         })

#     @http.route('/aula_metrics/aula_metrics/objects/<model("aula_metrics.aula_metrics"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('aula_metrics.object', {
#             'object': obj
#         })

