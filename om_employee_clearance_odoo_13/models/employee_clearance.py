import base64
from datetime import date, datetime
import time
from dateutil import relativedelta

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class EmployeesData(models.Model):
    _name = 'employee.clearance'
    _description = 'Employees Clearance Data'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'user_id'

    def _get_approval_departments(self):
        approval_list = [
            (0, 0, {'department_name': department.department_name, 'employees': department.employees, 'status': department.status,
                    'signature': department.signature,
                    'depends': department.depends, 'approve_id': self.id})
            for department in self.env['approval.clearance.department'].search([('permission', '=', True)])
        ]
        return approval_list

    user_id = fields.Many2one('hr.employee', 'Employee Name', default=lambda self: self.env.user.employee_id.id)
    job_title = fields.Char(string='Job Position', related='user_id.job_title')
    employee_code = fields.Char(string='Company Code', related='user_id.employee_code')
    company_name = fields.Char(string='Company Name', related='user_id.company_id.name')
    company_street = fields.Char(string='Company street', related='user_id.company_id.street')
    company_city = fields.Char(string='Company city', related='user_id.company_id.city')
    company_zip = fields.Char(string='Company zip', related='user_id.company_id.zip')
    email = fields.Char(string='Email', related='user_id.work_email')
    phone = fields.Char(string='Phone', related='user_id.work_phone')
    department = fields.Char(string='Department', related='user_id.department_id.name')
    branch = fields.Char(string='Branch', default=lambda self: self.env.user.branch_id.name)
    clearance_date = fields.Date(string='Clearance Date', default=date.today(), readonly=True)
    team_manager = fields.Char(string='Team Manager', related='user_id.parent_id.name')
    reason = fields.Text(string='Reason', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('request_for_approval', 'Waiting For Approval'),
        ('approved', 'Approved'),
        ('cancelled', 'Rejected')

    ], string='Status', default='draft')

    department_name = fields.Many2many('hr.department', string='Approve Department')

    employee_clearance_line = fields.One2many('approval.clearance.relation', 'approve_id',
                                              default=_get_approval_departments)

    attachment = fields.Binary(string='Attachment', attachment=True)

    reference = fields.Char(string='Reference')

    @api.model
    def create(self, vals_list):
        vals_list['reference'] = self.env['ir.sequence'].next_by_code('employee.clearance')
        return super(EmployeesData, self).create(vals_list)

    def _user_profile_view_render(self):
        tree_id = self.env.ref("om_employee_clearance.view_employee_clearance_tree")
        form_id = self.env.ref("om_employee_clearance.view_employee_clearance_form")
        current_user = self.env.user
        domain = []
        if current_user.has_group('om_employee_clearance.access_super_admin_approval_group') == False:
            domain = [('create_uid', '=', current_user.id)]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Employee',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'employee.clearance',
            'domain': domain,
            'views': [(tree_id.id, 'tree'), (form_id.id, 'form')],
            'context': {},
            'target': 'current'
        }

    def superuser_action_approve(self):
        self.ensure_one()
        if self.env.user.has_group('om_employee_clearance.access_super_admin_approval_group'):
            self.write({'state': 'approved'})
            self.employee_clearance_line.filtered(lambda r: r.status == 'pending' or r.status == 'rejected').write(
                {'status': 'accepted'})

    def superuser_action_reject(self):
        self.ensure_one()
        if self.env.user.has_group('om_employee_clearance.access_super_admin_approval_group'):
            self.write({'state': 'cancelled'})
            self.employee_clearance_line.filtered(lambda r: r.status == 'pending').write({'status': 'rejected'})

    def action_request_for_approval(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'request_for_approval'
                # self.employee_clearance_line.write({'reason': self.reason})

                # department_employees = self.env['approval.clearance.department'].search([('permission', '=', True)])

                #     for clearance_line in rec.employee_clearance_line:
                #         if clearance_line.department_name.id == department_id.id:
                #             pending_approval = self.env['pending.approval'].create({
                #                 'user_name': clearance_line.user_id.id,
                #                 'department_name': department_id.id,
                #                 'reason': self.reason,
                #                 'depends': clearance_line.depends,
                #                 'status': clearance_line.status,
                #                 'signature': clearance_line.signature,
                #             })
                #             pending_approval.action_request_for_approval()

    def _compute_approval_status(self):
        for rec in self:
            pending_count = 0
            accepted_count = 0
            rejected_count = 0
            department_name_count = len(rec.mapped('employee_clearance_line.department_name'))

            for clearance_line in rec.employee_clearance_line:
                if clearance_line.status == 'pending':
                    pending_count += 1
                elif clearance_line.status == 'accepted':
                    accepted_count += 1
                elif clearance_line.status == 'rejected':
                    rejected_count += 1

            print("pending count", pending_count)
            print("accepted count", accepted_count)
            print("department count", department_name_count)
            if accepted_count == department_name_count and pending_count == 0:
                rec.state = 'approved'
            elif rejected_count == department_name_count and pending_count == 0:
                rec.state = 'cancelled'
            else:
                rec.state = 'request_for_approval'


class ApprovalClearanceRelation(models.Model):
    _name = 'approval.clearance.relation'
    _description = 'Approval Clearance Relation'

    user_id = fields.Many2one('res.users', 'Employee Name', default=lambda self: self.env.user.id)
    compute_user_flag = fields.Boolean(default=False, compute='get_login_user_id')
    department_name = fields.Many2one('hr.department', string='Department Name')
    employees = fields.Many2many('hr.employee', string='Employees')
    # employee_id = fields.Many2one('hr.employee', string='Employees', default=lambda self: self.env.user.employee_id.id)


    depends = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),

    ], string='Outstanding', default='no', required=True)
    description_of_outstanding = fields.Text(string="Description of Outstanding")
    status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], string="Status", default='pending')

    signature = fields.Binary(string='Signature', attachment=True, help="Select an image here.", required=True)

    department_approval_clearance_ids = fields.Many2one('approval.clearance.department',
                                                        string='department_approval_clearance_ids')
    approve_id = fields.Many2one('employee.clearance', string="approve id", ondelete='cascade')
    reason = fields.Text(string='Reason', related='approve_id.reason')
    hr_employee = fields.Char(string="Hr Employee")
    hr_employee_job_title = fields.Char(string="Hr Job Title")
    hr_employee_department = fields.Char(string="Hr Department")





    def get_login_user_id(self):
        print(self.env.user.id, self.user_id.id)
        if self.env.user.id == self.user_id.id:
            self.compute_user_flag = True
        else:
            self.compute_user_flag = False


    def _department_wise_view_render(self):
        tree_id = self.env.ref("om_employee_clearance.view_approval_clearance_relation_tree")
        form_id = self.env.ref("om_employee_clearance.view_approval_clearance_relation_form")
        user_department_ids = self.env.user.employee_id.department_id.ids

        return {
            'type': 'ir.actions.act_window',
            'name': 'Pending Approval',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'approval.clearance.relation',
            'domain': [('department_name.id', 'in', user_department_ids)],
            'views': [(tree_id.id, 'tree'), (form_id.id, 'form')],
            'context': {},
            'target': 'current'
        }


    @api.onchange('approve_id')
    def _onchange_reason(self):
        self.reason = self.approve_id.reason


    # @api.onchange('approve_id')
    # def _onchange_request_state(self):
    #     self.request_state = self.approve_id.state

    def can_approve_clearance(self, employee_id):
        current_user_department = self.env.user.employee_id.department_id.ids


        access_department_employee = self.env['approval.clearance.department'].search([
            ('department_name', 'in', current_user_department),
            ('permission', '=', True),
        ])

        if access_department_employee and employee_id in access_department_employee.employees.ids:
            return True
        return False

    def get_administrator_employee(self):
        administrator_department = self.env['hr.department'].search([('name', '=', 'Administration')])
        administrator_department_employee = self.env['approval.clearance.department'].search([('department_name', '=', 'Administration'),('permission', '=', True)]).employees

        if administrator_department:
            administrator_employee = self.env['hr.employee'].search([
                ('id', 'in', self.env.user.employee_ids.ids),
                ('department_id', '=', administrator_department.id)
            ], limit=1)

            if administrator_employee:
                return {
                    'name': administrator_employee.name,
                    'job_title': administrator_employee.job_title,
                    'department_name': administrator_employee.department_id.name,
                }
        return {}


    def action_approve(self):
        if self.can_approve_clearance(self.env.user.employee_id.id):
            self.status = 'accepted'
            administrator_employee = self.get_administrator_employee()
            self.hr_employee = administrator_employee.get('name', '')
            self.hr_employee_job_title = administrator_employee.get('job_title', '')
            self.hr_employee_department = administrator_employee.get('department_name', '')
            self.approve_id._compute_approval_status()
        else:
            raise ValidationError("You don't have permission to approve this clearance.")


    def action_reject(self):
        if self.can_approve_clearance(self.env.user.employee_id.id):
            self.status = 'rejected'
            administrator_employee = self.get_administrator_employee()
            self.hr_employee = administrator_employee.get('name', '')
            self.hr_employee_job_title = administrator_employee.get('job_title', '')
            self.hr_employee_department = administrator_employee.get('department_name', '')
            self.approve_id._compute_approval_status()
        else:
            raise ValidationError("You don't have permission to reject this clearance.")
        # else:
        #     assign_engineer_lines = self.env['assign.engineer.lines'].search([
        #
        #         ('engineer_name', '=', self.env['res.users'].browse(self._context.get('uid')).id),
        #         # ('assign_for', '=', 'quality assurance'),
        #     ])
        #     so_list_for_assigned_qa = []
        #     for i in assign_engineer_lines:
        #         so_list_for_assigned_qa.append(i.engineer_id.order_id.id)
        #
        #     return {
        #         'type': 'ir.actions.act_window',
        #         'name': 'Quality Assurance',
        #         'view_type': 'form',
        #         'view_mode': 'tree,form',
        #         'res_model': 'field.service',
        #         'domain': [
        #             '|',
        #             ('repair_status1', '=', 'Ready For QC'),
        #             ('repair_status1', '=', 'Under QC'),
        #             ('id', 'in', so_list_for_assigned_qa),
        #             ('branch_name', '=', self.env['res.users'].browse(self._context.get('uid')).branch_id.id)],
        #         'views': [(tree_id.id, 'tree'), (form_id.id, 'form')],
        #         'target': 'current',
        #     }

    # @api.depends('user_id', 'department_name', 'employees')
    # def _compute_can_create_record(self):
    #     for record in self:
    #         user_department_ids = record.env.user.employee_id.department_id.ids
    #         current_user_id = record.env.user.employee_id.id
    #
    #         if (record.department_name.id in user_department_ids) or (current_user_id in record.employees.ids):
    #             record.can_create_record = True
    #         else:
    #             record.can_create_record = False


    # can_approve_reject = fields.Boolean(default=False,compute='_compute_can_approve_reject')
    # #
    # #
    # #
    # # @api.onchange('user_id')
    #
    # def _compute_can_approve_reject(self):
    #     print("Computing can_approve_reject field...")
    #     current_user_department_id = self.env.user.department_id.id
    #     for rec in self:
    #         print(current_user_department_id, rec.approve_id.department ,rec)
    #
    #         if rec.department_name.id == current_user_department_id:
    #             rec.can_approve_reject = True
    #         else:
    #             rec.can_approve_reject = False
    #     print("Computed can_approve_reject field for records:", self.ids)

    # @api.model
    # def test(self):
    #     department_employees = self.env['approval.clearance.department'].search([('permission', '=', True)]).mapped('employees')
    #     user_department_ids = self.env.user.employee_id.department_id.ids
    #
    #     domain = [('department_name.id', 'in', user_department_ids)]
    #     return domain


    # def action_approval_clearance_relation(self):
    #     print(self.department_name)
    #
    # class Inherit_res_users(models.Model):
    #     _inherit = 'res.users'
    #
    #     def test(self):
    #         active_model = self.env.context.get('active_model', False)
    #         user_department_ids = self.env.user.employee_id.department_id.ids
    #         current_user_id = self.env.user.employee_id.id
    #
    #         domain = [
    #             '|',
    #             ('department_name', 'in', user_department_ids),
    #             ('employees', 'in', current_user_id)
    #         ]
    #
    #         return domain

    # user_department_id = self.env.user.employee_id.department_id.id
    # department_clearance_rels = self.env['approval.clearance.relation'].search(
    #     [('department_name.id', '=', user_department_id)])
    #
    # domain = [
    #     ('department_name', 'in', department_clearance_rels.mapped('department_name').ids),
    # ]
    #
    # return domain


    # department_employees = self.env['approval.clearance.department'].search([('permission', '=', True),('name','=', self.env.user.employee_id.department_id.id)])
    # print(department_employees.employees.user_id.ids,self.user_id.id)
    # user_department_ids = self.env.user.employee_id.department_id.ids
    # domain = [
    #     "|",
    #     ("department_name", "=", False),
    #     ('department_name.id', 'in', user_department_ids)
    # ]
    # return domain
