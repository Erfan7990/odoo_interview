from datetime import date, datetime
import time
from dateutil import relativedelta

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class EmployeeClearanceReport(models.AbstractModel):
    _name = 'report.om_employee_clearance.report_for_employee_clearance'
    _description = 'Employee Clearance Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        # pass all employee.clearance data and also find that login user department is accepted or rejected his approval request

        report_data = []
        # Retrieve the current user's department
        user_department = self.env.user.employee_id.department_id.ids

        # Retrieve relevant data from approval.clearance.relation
        print("------------->>>",self.env['approval.clearance.relation'].search([('department_name', 'in', user_department)]))
        for clearance in self.env['approval.clearance.relation'].search([('department_name', 'in', user_department)]):
            if clearance.status == 'accepted':
                report_data.append(clearance.status)
                break
            elif clearance.status == 'rejected':
                report_data.append(clearance.status)
                break
            elif clearance.status == 'pending':
                report_data.append(clearance.status)
                break

        return {
            'doc_ids': docids,
            'doc_model': 'employee.clearance',
            'docs': self.env['employee.clearance'].browse(docids),
            'report_data': report_data,
        }
