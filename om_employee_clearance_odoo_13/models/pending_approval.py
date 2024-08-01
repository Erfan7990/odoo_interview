from datetime import date, datetime

from dateutil import relativedelta

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class PendingApproval(models.Model):
    _name = 'pending.approval'
    _description = 'Pending Approval'

    user_name = fields.Many2one('res.users', string='Employee name')
    department_name = fields.Many2one('hr.department', string='Department')
    reason = fields.Text(string='Reason')
    depends = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Dependency')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], string="Status")
    signature = fields.Binary(string='Signature', attachment=True, help="Select an image here")
    # approve_id = fields.Many2one('employee.clearance', string="approve id")

    def action_request_for_approval(self):
        for rec in self:
            # Fetch the current user's department
            current_department = self.env.user.department_id

            # Search for related data in approval.clearance.relation based on the current department
            related_data = self.env['approval.clearance.relation'].search([
                ('approve_id', '=', rec.id),
                ('department_name', '=', current_department.id),
            ], limit=1)

            if related_data:
                rec.user_name = related_data.user_id
                rec.department_name = related_data.department_name
                rec.depends = related_data.depends
                rec.status = related_data.status
                rec.signature = related_data.signature
                rec.reason = related_data.reason