from datetime import date, datetime

from dateutil import relativedelta

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class DepartmentApproval(models.Model):
    _name = 'department.approval'
    _description = 'Approval From Department'

    user_name = fields.Char(string='Name')
    department_name = fields.Many2one('hr.department', string='Department', domain=[('can_approve', '=', True)])
    reason = fields.Text(string='Reason')
    depends = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),

    ], string='Dependency', default='no')
    remark = fields.Char(string="Remark")
    signature = fields.Binary(string='Signature', attachment=True, help="Select an image here.")
    # approve_id = fields.Many2one('employee.clearance', string="approve id")

