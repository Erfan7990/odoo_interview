from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, date


class FailedItemResend(models.TransientModel):
    _name = 'failed.item.resend.wizard'

    line_manager = fields.Many2one('res.users', string='Line Manager', required=True,
                                   domain=lambda self: [('id', 'in', self._get_line_manager())])
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    lot_ids = fields.Many2one('stock.production.lot', string='Serial Number')
    im_qc_id = fields.Many2one('incoming.material.qc')
    remarks = fields.Html(string="Comments")

    def _get_line_manager(self):
        data = self.env['role.manage'].search([('role_select', '=', 'line_manager')])
        return data.users.ids

    def action_confirm(self):
        failed_data = self.env['customer.qc.checking.line'].search([
            ('im_qc_ref', '=', self.im_qc_id.seq), ('qc_state', '=', 'failed')
        ])
        line_manage_vals = {}
        if failed_data:
            line_manage_vals = {
                'line_manager': self.line_manager.id,
                'assembly_line': self.assembly_line.id,
                'date': datetime.now(),
                'source': failed_data.im_qc_ref,
                'state': 'qc_failed',
                'remarks': self.remarks,
                'line_management_line_ids': [(0, 0, {
                    'bom_id': failed_data.product_id.product_tmpl_id.bom_ids.id,
                    'qty': failed_data.qty,
                    'remaining_qty': failed_data.qty,
                    'lot_ids': failed_data.lot_ids.ids,
                })],
                'wizard_line_ids': [(0, 0, {
                    'bom_id': failed_data.product_id.product_tmpl_id.bom_ids.id,
                    'qty': failed_data.qty,
                    'desk': failed_data.desk.id,
                    'assembly_line': failed_data.assembly_line.id,
                    'date': datetime.now(),
                    'engineer': failed_data.engineer.id,
                    'lot_ids': failed_data.lot_ids.ids,
                    # 'engineer_type': 'assign_qc_fail',
                })]

            }
        line_manager_id = self.env['line.management'].create(line_manage_vals)
        if line_manager_id:
            wizard_line = self.env['assign.desk.engineer.wizard.table'].search([('line_management_id', '=', line_manager_id.id)])
            wizard_line._onchange_qty()


