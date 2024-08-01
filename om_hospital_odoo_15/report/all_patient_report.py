from odoo import api, fields, models, _


class AllPatientReport(models.AbstractModel):
    _name = 'report.om_hospital.report_all_patient_list'
    _description = 'Patient Report'


    @api.model
    def _get_report_values(self, docids, data=None):

        print("docids:------------->", docids)
        print("\ndata:------------->", data)

        domain=[]
        gender = data.get('data_form').get('gender')
        age = data.get('data_form').get('age')
        if gender:
            domain += [('gender', '=', gender)]
        if age != 0:
            domain += [('age', '=', age)]

        docs = self.env['hospital.patient'].search(domain)

        return {
            'docs': docs
        }


class AllPatientReport(models.AbstractModel):
    _name = 'report.om_hospital.report_patient_detail'
    _description = 'Patient Information'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hospital.patient'].browse(docids)
        # docs = self.env['hospital.patient'].search([])

        return {
            'docs': docs,
        }