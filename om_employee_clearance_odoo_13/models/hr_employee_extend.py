import datetime

from odoo import fields, models, api, _
from odoo.modules.module import get_module_resource
import base64
from odoo.exceptions import ValidationError
import re
from datetime import datetime, timedelta


class HrEmployeeExtend(models.Model):
    _inherit = 'hr.employee'

    @api.onchange("job_history")
    def onchange_job_history(self):
        count_end_date = 0
        for rec in self.job_history:
            if rec.end_date is False or rec.end_date is None:
                count_end_date = count_end_date + 1
        # if count_end_date>1:
        #     raise ValidationError("End date not to be Null for more then '1' row")

    def write(self, val_list):
        if 'work_email' in val_list.keys():
            work_email = val_list['work_email'].strip()
            val_list['work_email'] = work_email

        return super(HrEmployeeExtend, self).write(val_list)

    def init(self):
        super(HrEmployeeExtend, self).init()
        image_path = get_module_resource('hr', 'static/src/img', 'default_image.png')

        employee_list = self.env['hr.employee'].search([('image_1920', '=', False)])
        print(employee_list)
        if employee_list:
            for employee in employee_list:
                if not employee.image_1920:
                    employee.image_1920 = base64.b64encode(open(image_path, 'rb').read())

    @api.model
    def _get_default_country(self):
        country = self.env['res.country'].search([('code', '=', 'BD')], limit=1)
        return country

    @api.onchange('emp_type', 'joining_date')
    def _compute_probation_end(self):
        if self.joining_date and self.emp_type.id == 3:
            self.probation_end = self.joining_date + timedelta(days=180)
        else:
            self.probation_end = datetime.now() + timedelta(days=180)

    hr_team = fields.Many2one("hr.team", string="Team")

    social_facebook = fields.Char(
        string='Facebook',
        required=False)

    social_twitter = fields.Char(
        string='Twitter',
        required=False)

    social_linkedin = fields.Char(
        string='Linkedin',
        required=False)

    social_pinterest = fields.Char(
        string='Pinterest',
        required=False)

    social_instagram = fields.Char(
        string='instagram',
        required=False)

    present_house = fields.Char(string='House No./ Street')
    present_village = fields.Char(string='Village/Town/City')
    present_state = fields.Char(string='State/provenance/District')
    present_postal = fields.Char(string='Postal/Zip Code')
    present_country = fields.Many2one('res.country', string="Country", default=_get_default_country)

    permanent_house = fields.Char(string='House No./ Street')
    permanent_village = fields.Char(string='Village/Town/City')
    permanent_state = fields.Char(string='State/provenance/District')
    permanent_postal = fields.Char(string='Postal/Zip Code')
    permanent_country = fields.Many2one('res.country', string="Country", default=_get_default_country)

    # employee history
    # job_history = fields.One2many('department.history', 'employee_id', string='Job History')
    # job_description = fields.Html(string='Job Description')
    # salary_history = fields.One2many('salary.history', 'employee_id', string='Salary History')
    # contract_history = fields.One2many('contract.history', 'employee_id', string='Contract History')
    # timesheet_history = fields.One2many('timesheet.cost', 'employee_id', string='Timesheet History')
    # job_position_history = fields.One2many('job.position.history', 'employee_id', string='Promotion History')
    # salary_lock_unlock_history = fields.One2many('salary.lock.unlock.history', 'employee_id',
    #                                              string='Salary Lock History')

    # for attendance purpose
    employee_code = fields.Char(string="Employee Code", groups="hr.group_hr_user", copy=False)
    pin = fields.Char(string="Attendance Code", groups="hr.group_hr_user", copy=False, tracking=True,
                      help="Code used to Check In/Out in Kiosk Mode (if enabled in Configuration).")
    make_readonly = fields.Boolean(help="Used to make fields readonly to regular users", compute="_compute_group")

    # salary lock history
    is_salary_lock = fields.Boolean('Salary Lock', default=False)
    allow_remote_attendance = fields.Boolean('Remote Attendance', default=False)

    emp_type = fields.Many2one(
        comodel_name='employment.type',
        string='Employee Type',
        required=True)
    probation_end = fields.Date('Probation End Date')
    employee_branch = fields.Many2one('res.branch', 'Branch', store=True)
    sub_department = fields.Many2one('hr.sub.department', 'Sub Department', store=True)
    job_grade = fields.Many2one('hr.job.grade', 'Job Grade', store=True)
    religion = fields.Selection(
        string='Religion',
        selection=[('muslim', 'Muslim'),
                   ('hindu', 'Hindu'),
                   ('buddhist', 'Buddhist'),
                   ('christian', 'Christian'),
                   ('other', 'Others'),
                   ],
        required=False, )
    birth_certification_id = fields.Char('Birth Certificate No', groups="hr.group_hr_user", tracking=True)
    marital = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('widower', 'Widower'),
        ('divorced', 'Divorced')
    ], string='Marital Status', groups="hr.group_hr_user", default='single', tracking=True)

    # certificate = fields.Selection(selection_add=[('doctorate', 'Doctorate')])
    certificate = fields.Selection([
        ('doctorate', 'Doctorate'),
        ('master', "Master's"),
        ('bachelor', 'Bachelor'),
        ('other', 'Other'),
    ], 'Certificate Level', default='bachelor', groups="hr.group_hr_user", tracking=True)

    blood_group = fields.Selection(
        string='Blood Group',
        selection=[('a+', 'A+'),
                   ('a-', 'A-'),
                   ('b+', 'B+'),
                   ('b-', 'B-'),
                   ('o+', 'O+'),
                   ('o-', 'O-'),
                   ('ab+', 'AB+'),
                   ('ab-', 'AB-'), ],
        required=False, )
    # reference_id = fields.One2many(
    #     comodel_name='employee.reference',
    #     inverse_name='employee_id',
    #     string='Reference Id')
    # reference_ids = fields.One2many('employee.reference', 'employee_id', string='Reference Info')
    employee_attendance_state = fields.Text(compute="_compute_employee_attendance_state", default="to_define")

    def _compute_group(self):
        for rec in self:
            if not self.env.user.has_group('hr.group_hr_manager'):
                rec.make_readonly = True
            else:
                rec.make_readonly = False

    # Unique constraint using function
    @api.constrains('pin')
    def _check_unique_pin_id(self):
        for record in self:
            obj = self.search([('pin', '=', record.pin), ('id', '!=', record.id)])
            if record.pin:
                if obj:
                    raise ValidationError("Attendance Code must be unique")

    # @api.depends('name')
    # def _compute_employee_attendance_state(self):
    #     for rec in self:
    #         attendance_status = self.env['hr.attendance'].sudo().search(
    #             [('employee_id', '=', rec.id), ('date', '=', datetime.today())])
    #         if attendance_status.delay_status in ('L', 'P', 'E', 'LE'):
    #             rec.employee_attendance_state = 'present'
    #         elif attendance_status.delay_status == 'A':
    #             rec.employee_attendance_state = 'absent'
    #         else:
    #             rec.employee_attendance_state = 'to_define'

    @api.constrains('employee_code')
    def _check_unique_code_id(self):
        for record in self:
            obj = self.search([('employee_code', '=', record.employee_code), ('id', '!=', record.id)])
            if record.employee_code:
                if obj:
                    raise ValidationError("Employee Code Must Be Unique")

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = args + ['|', '|', ('pin', operator, name), ('name', operator, name), ('work_email', operator, name)]
        return super(HrEmployeeExtend, self).search(domain, limit=limit).name_get()

    # employee_branch = fields.Many2one('res.branch', string='Branch')

    @api.onchange('employee_code')
    def _onchange_emp_code(self):
        for rec in self:
            if rec.employee_code:
                if not rec.pin:
                    rec.pin = ''.join([n for n in rec.employee_code if n.isdigit()])

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name
            if rec.pin:
                name = f'({rec.employee_code}) - {name}'
            result.append((rec.id, name))
        return result

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        for rec in self:
            rec.coach_id = rec.parent_id

    @api.onchange('resource_calendar_id')
    def _onchange_resource_id(self):
        for rec in self:
            rec.contract_id.resource_calendar_id = self.resource_calendar_id

    # rewrite is needed to clear default mobile and phone number
    @api.onchange('address_id')
    def _onchange_address(self):
        pass

    @api.constrains('identification_id', 'birth_certification_id', 'passport_id')
    def _check_identification(self):
        for rec in self:
            if rec.identification_id == False and rec.birth_certification_id == False and rec.passport_id == False:
                raise ValidationError("Nid or Birth Certificate or Passport Id need to provide")

    # add nominee info in hr_employee
    # nominee_ids = fields.One2many('nominee.info', 'employee_id', string='Nominee Info')

    # parent info add
    # father info
    father_name = fields.Char(string='Father Name')
    father_contact = fields.Char(string='Father Contact')
    parent_address = fields.Text(string='Address')

    # mother info
    mother_name = fields.Char(string='Mother Name')
    mother_contact = fields.Char(string='Mother Contact')
    mobile_no = fields.Char(string="Mobile No (Personal)")
    personal_email = fields.Char(string="Personal Email")

    # mother_address = fields.Char(string='Mother Address')

    # employee img change on user image change
    def _sync_user(self, user):
        vals = dict(
            work_email=user.email,
            user_id=user.id,
        )
        if user.tz:
            vals['tz'] = user.tz
        return vals

    country_of_birth = fields.Many2one('res.country', string="Country of Birth", groups="hr.group_hr_user",
                                       tracking=True, default=_get_default_country)
    country_id = fields.Many2one(
        'res.country', 'Nationality (Country)', groups="hr.group_hr_user", tracking=True, default=_get_default_country)

    @api.constrains('pin', 'identification_id', 'birth_certification_id', 'present_postal', 'permanent_postal')
    def _verify_pin(self):
        for employee in self:
            if employee.pin and not employee.pin.isdigit():
                raise ValidationError(_("Attendance Code must be numeric number."))
            if employee.identification_id and not employee.identification_id.isdigit():
                raise ValidationError(_("NID must be numeric number."))
            if employee.birth_certification_id and not employee.birth_certification_id.isdigit():
                raise ValidationError(_("Birth Certificate must be numeric number."))
            if employee.present_postal and not employee.present_postal.isdigit():
                raise ValidationError(_("Zip Code (Present) must be numeric number."))
            if employee.permanent_postal and not employee.permanent_postal.isdigit():
                raise ValidationError(_("Zip Code (Permanent) must be numeric number."))

    @api.constrains('personal_email', 'work_email')
    def validate_mail(self):
        for rec in self:
            if rec.personal_email:
                match = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$',
                                 rec.personal_email)
                if match == None:
                    raise ValidationError('Not a valid Personal email ID')
            if rec.work_email:
                match = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$',
                                 rec.work_email)
                if match == None:
                    raise ValidationError('Not a valid office email ID')

    @api.constrains('mobile_phone', 'work_phone', 'mobile_no', 'father_contact', 'mother_contact', 'emergency_phone')
    def validate_mail(self):
        for rec in self:
            if rec.mobile_phone:
                match = re.match('^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$',
                                 rec.mobile_phone)
                if match == None:
                    raise ValidationError('Not a valid Mobile No (Office)')
            if rec.work_phone:
                match = re.match('^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$',
                                 rec.work_phone)
                if match == None:
                    raise ValidationError('Not a valid IP Ext number')
            if rec.mobile_no:
                match = re.match('^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$',
                                 rec.mobile_no)
                if match == None:
                    raise ValidationError('Not a valid Mobile No(Personal)')
            if rec.father_contact:
                match = re.match('^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$',
                                 rec.father_contact)
                if match == None:
                    raise ValidationError("Father Contact is not valid mobile number")
            if rec.mother_contact:
                match = re.match('^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$',
                                 rec.mother_contact)
                if match == None:
                    raise ValidationError('Mother Contact is not valid mobile number')
            if rec.emergency_phone:
                match = re.match('^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$',
                                 rec.emergency_phone)
                if match == None:
                    raise ValidationError('Emergency Phone is not valid mobile number')

    @api.onchange('work_email')
    def _onchange_work_email(self):
        for rec in self:
            rec.address_home_id = None
            return {
                'domain':
                    {'address_home_id': [('email', '=', rec.work_email)]}
            }
