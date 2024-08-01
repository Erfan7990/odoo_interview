from odoo import models, fields, api

class ApprovalClearanceDepartment(models.Model):
    _name = 'approval.clearance.department'
    _description = 'Approval Clearance Department'

    department_name = fields.Many2one('hr.department', string='Department Name', required=True)
    employees = fields.Many2many('hr.employee', string='Employees')

    permission = fields.Boolean(string='Permission For Approval', default=False)
    depends = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),

    ], string='Dependency', default='no')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], string="Status", default='pending')
    signature = fields.Binary(string='Signature', attachment=True, help="Select an image here.")
    # approve_id = fields.Many2one('employee.clearance', string="approve id")
    #

    @api.onchange('department_name')
    def _onchange_employees(self):
        for clearance in self:
            if clearance.department_name:
                domain = [
                    ('department_id', '=', clearance.department_name.id),
                ]
                employees = self.env['hr.employee'].search(domain)
                clearance.employees = employees.ids
            else:
                clearance.employees = [(5, 0, 0)]










