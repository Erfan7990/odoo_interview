import random

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PatientAppointment(models.Model):
    _name = 'hospital.appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Hospital Patient Appointment Information'
    _rec_name = 'patient_appointment_ids'
    _order = 'id desc'

    patient_appointment_ids = fields.Char(string='Appointment Id')
    patient_id = fields.Many2one('hospital.patient', string='Patient', ondelete="cascade")
    operation = fields.Many2one('hospital.operation', string="Operation")
    gender = fields.Selection([('male', "Male"), ('female', 'Female')], related='patient_id.gender',
                              help='Enter the gender of a patient')
    appointment_time = fields.Datetime(string="Appointment Date")
    booking_date = fields.Date(string="Booking Date", default=fields.Datetime.now)
    reference = fields.Char(string='Reference', help='Reference from the patient records')
    age = fields.Char(string='Age')
    prescription = fields.Html(string='prescription')
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High'),
    ], string="Priority")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_consultant', 'In Consultant'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='draft', required=True)
    doctor_id = fields.Many2one('res.users', string='Doctor')
    pharmacy_line_ids = fields.One2many('hospital.appointment.line', 'appointment_id', string='Pharmacy Line')
    hide_sales_price = fields.Boolean(string='Hide Sales Price')
    progress = fields.Integer(string="Progress", compute='_compute_progress')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    # total_price = fields.
    total_price = fields.Monetary(string="Total", compute='_compute_total_price', store=True)



    @api.depends('pharmacy_line_ids')
    def _compute_total_price(self):

        for rec in self:
            total = 0.0
            for i in rec.pharmacy_line_ids:
                total += i.price_unit * i.quantity

            rec.total_price = total

    @api.model
    def create(self, vals_list):
        vals_list['patient_appointment_ids'] = self.env['ir.sequence'].next_by_code('hospital.appointment')
        return super(PatientAppointment, self).create(vals_list)

    def write(self, vals):
        if not self.patient_appointment_ids and not vals.get('patient_appointment_ids'):
            vals['patient_appointment_ids'] = self.env['ir.sequence'].next_by_code('hospital.appointment')
        return super(PatientAppointment, self).write(vals)

    @api.onchange('patient_id')
    def onchange_patient_id(self):
        self.reference = self.patient_id.reference

    @api.onchange('patient_id')
    def onchange_patient_age(self):
        self.age = self.patient_id.age

    def test_action(self):
        print('Button Clicked............')
        # URL action.........
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': 'https://www.odoo.com/',
        }

    # Whatsapp btn
    def action_whatsapp_btn(self):
        if not self.patient_id.phone:
            raise ValidationError(_('Missing your whatsapp number'))
        message = 'Hi %s, your appointment number is %s' % (self.patient_id.name, self.patient_appointment_ids)
        whatsapp_url = 'https://api.whatsapp.com/send?phone=%s&test=%s' % (self.patient_id.phone, message)
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': whatsapp_url,
        }

    # Creating button to control statusbar
    def action_in_consultant_btn(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'in_consultant'

    def action_done_btn(self):
        for rec in self:
            rec.state = 'done'
        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'Click successful!!',
                'type': 'rainbow_man',
            }
        }

    def action_cancelled_btn(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_cancellation(self):
        action = self.env.ref('om_hospital.action_cancel_appointment').read()[0]
        return action

    def action_draft_btn(self):
        for rec in self:
            rec.state = 'draft'

    @api.depends('state')
    def _compute_progress(self):
        for rec in self:
            if rec.state == 'draft':
                progress = random.randrange(0, 25)
            elif rec.state == 'in_consultant':
                progress = random.randrange(25, 99)
            elif rec.state == 'done':
                progress = 100
            else:
                progress = 0
            rec.progress = progress

    def unlink(self):
        if self.state != 'draft':
            raise ValidationError(_("You can only delete in Draft state !"))
        return super(PatientAppointment, self).unlink()


class Appointment_pharmacy_Lines(models.Model):
    _name = 'hospital.appointment.line'
    _description = 'Appointment for pharmacy Line'

    product_id = fields.Many2one('product.product', required=True)
    price_unit = fields.Float(related="product_id.lst_price")
    quantity = fields.Integer(string='Quantity', default='1')
    appointment_id = fields.Many2one('hospital.appointment', string='Appointment')
    company_currency_id = fields.Many2one('res.currency', related='appointment_id.currency_id')
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price_subtotal',
                                     currency_field='company_currency_id', store=True)
    


    @api.depends('price_unit', 'quantity')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = rec.price_unit * rec.quantity
            print("-->>", rec.price_subtotal)

