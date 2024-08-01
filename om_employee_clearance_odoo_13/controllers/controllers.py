# -*- coding: utf-8 -*-
# from odoo import http


# class OmEmployeeClearance(http.Controller):
#     @http.route('/om_employee_clearance/om_employee_clearance/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/om_employee_clearance/om_employee_clearance/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('om_employee_clearance.listing', {
#             'root': '/om_employee_clearance/om_employee_clearance',
#             'objects': http.request.env['om_employee_clearance.om_employee_clearance'].search([]),
#         })

#     @http.route('/om_employee_clearance/om_employee_clearance/objects/<model("om_employee_clearance.om_employee_clearance"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('om_employee_clearance.object', {
#             'object': obj
#         })
