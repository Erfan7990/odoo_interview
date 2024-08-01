import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AllPatientReportWizard(models.TransientModel):
    _name = 'patient.report.wizard'
    _description = 'Showing All Patient Data'

    gender = fields.Selection([('male', "Male"), ('female', 'Female')], string="Gender")
    age = fields.Integer(string="Age")

    def action_all_patient(self):
        data = {
            'data_form': self.read()[0],
        }
        return self.env.ref('om_hospital.action_patient_report_details').report_action(self, data = data)