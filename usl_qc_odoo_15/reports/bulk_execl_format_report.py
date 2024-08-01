from odoo import models
from odoo.exceptions import AccessError, UserError, ValidationError



class BulkFormatReportXlsx(models.AbstractModel):
    _name = 'report.usl_qc.bulk_format_report_xls'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, partners):

        vals = data
        for obj in partners:

            if obj.qc_state != 'bulk_qc':
                ValidationError("You can download the execl format when you choose Bulk QC")


            iqc_line_ids = obj.iqc_line_id

            report_name = "Bulk QC"
            # One sheet by partner
            sheet = workbook.add_worksheet(report_name)
            bold = workbook.add_format({'bold': True})
            sheet.write(0, 0, report_name, bold)