import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class SearchAppointmentWizard(models.TransientModel):
    _name = 'search.appointment.wizard'
    _description = 'Print Appointment Report'

    patient_id = fields.Many2one('hospital.patient', string='Patient')
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')

    def action_search(self):
        domain = []
        patient_id = self.patient_id
        start_date = self.start_date
        end_date = self.end_date

        if patient_id:
            domain += [('patient_id', '=', patient_id.id)]
        if start_date:
            domain += [('appointment_time', '>=', start_date)]
        if end_date:
            domain += [('appointment_time', '<=', end_date)]



        appointments = self.env['hospital.appointment'].search_read(domain)
        print("test------->", self.read()[0])
        data = {
            'form_data': self.read()[0],
            'appointments': appointments
        }
        return self.env.ref('om_hospital.action_search_appointment').report_action(self, data=data)



