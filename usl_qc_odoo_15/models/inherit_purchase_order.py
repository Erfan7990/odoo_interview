from odoo import models, fields, _, api
from odoo.exceptions import AccessError, UserError, ValidationError


class InheritPurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    transfer_type = fields.Selection([
        ('optional_qc', 'Optional QC'),
        ('mandatory_qc', 'Mandatory QC'),
    ], string='QC Option')
    qc_count = fields.Integer(compute='_compute_transfer_delivery_count',
                                             string='QC Count', store=False)

    def _compute_transfer_delivery_count(self):
        for record in self:
            qc_count = self.env['customer.qc.checking.line'].search_count([
                ('supplier_qc_id.purchase_order', '=', self.id)
            ])
            record.qc_count = qc_count
    @api.onchange('transfer_type')
    def _onchange_transfer_type(self):
        if self.transfer_type == 'mandatory_qc':
            warehouse_location = self.env['stock.warehouse'].search([('is_non_saleable_warehouse', '=', True)])
            picking_type = self.env['stock.picking.type'].search(
                [('code', '=', 'incoming'), ('warehouse_id', '=', warehouse_location.ids)])

            self.picking_type_id =  picking_type[:1]
        if self.transfer_type == 'optional_qc':
            warehouse_id = self.user_id.context_default_warehouse_id
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'incoming'),('warehouse_id', '=', warehouse_id.id)])
            if not picking_type:
                picking_type = self.env['stock.picking.type'].search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
            self.picking_type_id = picking_type[:1]



    def action_iqc_qc(self):

        tree_id = self.env.ref("usl_qc.customer_qc_checking_line_tree_view")
        form_id = self.env.ref("usl_qc.incoming_material_qc_form_view")

        purchase_order = self.env['purchase.order'].search([('name', '=', self.origin)]).id
        incoming_material_qc = self.env['incoming.material.qc'].search([('stock_picking_id', '=', self.id)])

        return {
            'name': 'Material QC',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.qc.checking.line',
            'view_mode': 'tree',
            'views': [(tree_id.id, 'tree')],
            'target': 'current',
            'context': {},
            'domain': [('supplier_qc_id.purchase_order','=', self.id)],
        }



