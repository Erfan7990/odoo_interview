from odoo import models, fields, _, api
from odoo.exceptions import AccessError, UserError, ValidationError


class InheritPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_button_visible = fields.Boolean(string='Is Button Visible', default=False)


class InheritStockPicking(models.Model):
    _inherit = 'stock.picking'

    incoming_material_qc_id = fields.Many2one('incoming.material.qc', string='Incoming Material QC ID')
    show_hide_check_availability = fields.Boolean(default=False, string='Show Check Availability?',
                                             compute='_compute_hide_show_check_availability')
    is_from_qc = fields.Boolean(default=False)

    @api.depends('show_check_availability')
    def _compute_hide_show_check_availability(self):
        if self.is_from_qc:
            for line in self.move_lines:
                if line.product_uom_qty == line.reserved_availability:
                    self.show_check_availability = True
                else:
                    self.show_check_availability = False

    def action_set_quantities_to_reservation(self):
        if self.is_from_qc:
            stock_move_ids = self.env['stock.move'].search([('picking_id', '=', self.id)])
            for data in stock_move_ids:
                stock_move_line_ids = self.env['stock.move.line'].search([
                    ('picking_id', '=', self.id),
                    ('move_id', '=', data.id)
                ])
                for line_data in stock_move_line_ids:
                    line_data.write({
                        'qty_done': 1
                    })
                    line_data._onchange_qty_done()

        if not self.is_from_qc:
            super().action_set_quantities_to_reservation()


    def action_confirm(self):

        for rec in self:
            if rec.is_from_qc:
                passed_customer_qc_line_ids = self.env['customer.qc.checking.line'].search([
                    ('im_qc_ref', '=', rec.origin),
                    ('qc_state', '=', 'passed'),
                    ('passed_picking_id', '=', self.id)
                ])
                failed_customer_qc_line_ids = self.env['customer.qc.checking.line'].search([
                    ('im_qc_ref', '=', rec.origin),
                    ('qc_state', '=', 'failed'),
                    ('failed_picking_id', '=', self.id)
                ])
                move_lines = self.env['stock.move'].search([('id', 'in', self.move_lines.ids)])

                move_line_records = []
                for line in move_lines:
                    rec.state = 'assigned'
                    line.state = rec.state
                    if passed_customer_qc_line_ids:
                        for data in passed_customer_qc_line_ids:
                            if data.lot_ids:
                                if line.product_id == data.product_id:
                                    move_line_vals = {
                                        'move_id': line.id,
                                        'product_id': line.product_id.id,
                                        'picking_id': rec.id,
                                        'lot_id': data.lot_ids.id,
                                        'product_uom_id': line.product_id.uom_id.id,
                                        'product_uom_qty': 1,
                                        'location_id': line.location_id.id,
                                        'location_dest_id': line.location_dest_id.id,
                                    }
                                    move_line_records.append(move_line_vals)
                                    # if the product is serial then update the stock_quant
                                    # reserved_quantity based on lot_ids where qty is one by one
                                    stock_quant = self.env['stock.quant'].search([
                                        ('product_id', '=', line.product_id.id),
                                        ('lot_id', '=', line.lot_ids.id),
                                        ('location_id', '=', line.location_id.id)
                                    ])
                                    if stock_quant:
                                        stock_quant.write({
                                            'reserved_quantity': 1,
                                        })
                                    else:
                                        # Create a new stock_quant record if it doesn't exist
                                        stock_quant = self.env['stock.quant'].create({
                                            'lot_id': data.lot_ids.id,
                                            'product_id': line.product_id.id,
                                            'location_id': line.location_id.id,
                                            'reserved_quantity': 1,
                                        })

                            else:
                                if line.product_id == data.product_id:
                                    move_line_vals = {
                                        'move_id': line.id,
                                        'product_id': line.product_id.id,
                                        'picking_id': rec.id,
                                        'lot_id': False,
                                        'product_uom_id': line.product_id.uom_id.id,
                                        'product_uom_qty': line.product_uom_qty,
                                        'location_id': line.location_id.id,
                                        'location_dest_id': line.location_dest_id.id,
                                    }
                                    move_line_records.append(move_line_vals)

                                    # if the product is non-serial then update the stock_quant
                                    # reserved_quantity with the product_uom_qty
                                    stock_quant = self.env['stock.quant'].search([
                                        ('product_id', '=', line.product_id.id),
                                        ('location_id', '=', line.location_id.id)
                                    ])
                                    if stock_quant:
                                        for data in stock_quant:
                                            data.write({
                                                'reserved_quantity': data.reserved_quantity + line.product_uom_qty,
                                            })

                                    break

                    if failed_customer_qc_line_ids:
                        for data in failed_customer_qc_line_ids:
                            if data.lot_ids:
                                if line.product_id == data.product_id:
                                    move_line_vals = {
                                        'move_id': line.id,
                                        'product_id': line.product_id.id,
                                        'picking_id': rec.id,
                                        'lot_id': data.lot_ids.id,
                                        'product_uom_id': line.product_id.uom_id.id,
                                        'product_uom_qty': 1,
                                        'location_id': line.location_id.id,
                                        'location_dest_id': line.location_dest_id.id,
                                    }
                                    move_line_records.append(move_line_vals)
                                    # if the product is serial then update the stock_quant
                                    # reserved_quantity based on lot_ids where qty is one by one
                                    stock_quant = self.env['stock.quant'].search([
                                        ('product_id', '=', line.product_id.id),
                                        ('lot_id', '=', line.lot_ids.id),
                                        ('location_id', '=', line.location_id.id)
                                    ])
                                    if stock_quant:
                                        stock_quant.write({
                                            'reserved_quantity': 1,
                                        })
                                    else:
                                        # Create a new stock_quant record if it doesn't exist
                                        stock_quant = self.env['stock.quant'].create({
                                            'lot_id': data.lot_ids.id,
                                            'product_id': line.product_id.id,
                                            'location_id': line.location_id.id,
                                            'reserved_quantity': 1,
                                        })

                            else:
                                if line.product_id == data.product_id:
                                    move_line_vals = {
                                        'move_id': line.id,
                                        'product_id': line.product_id.id,
                                        'picking_id': rec.id,
                                        'lot_id': False,
                                        'product_uom_id': line.product_id.uom_id.id,
                                        'product_uom_qty': line.product_uom_qty,
                                        'location_id': line.location_id.id,
                                        'location_dest_id': line.location_dest_id.id,
                                    }
                                    move_line_records.append(move_line_vals)

                                    # if the product is non-serial then update the stock_quant
                                    # reserved_quantity with the product_uom_qty
                                    stock_quant = self.env['stock.quant'].search([
                                        ('product_id', '=', line.product_id.id),
                                        ('location_id', '=', line.location_id.id)
                                    ])
                                    if stock_quant:
                                        for data in stock_quant:
                                            data.write({
                                                'reserved_quantity': data.reserved_quantity + line.product_uom_qty,
                                            })
                                    break

                self.env['stock.move.line'].create(move_line_records)

            else:
                return super(InheritStockPicking, rec).action_confirm()

    def action_iqc_qc(self):

        tree_id = self.env.ref("usl_qc.incoming_material_qc_tree_view")
        form_id = self.env.ref("usl_qc.incoming_material_qc_form_view")

        purchase_order = self.env['purchase.order'].search([('name', '=', self.origin)]).id
        incoming_material_qc = self.env['incoming.material.qc'].search([('stock_picking_id', '=', self.id)])

        return {
            'name': 'Incoming Material QC',
            'type': 'ir.actions.act_window',
            'res_model': 'incoming.material.qc',
            'view_mode': 'tree, form',
            'views': [(tree_id.id, 'tree'), (form_id.id, 'form')],
            'target': 'current',
            'context': {
                'default_vendor': self.partner_id.id,
                'default_purchase_order': purchase_order,
                'default_qc_type': 'pre_qc',
                'default_stock_picking_id': self.id,
            },
            'domain': [('vendor', '=', self.partner_id.id),
                       ('qc_type', '=', 'pre_qc'),
                       ('purchase_order', '=', purchase_order),
                       ('stock_picking_id', '=', self.id),
                       ],
        }


class CustomStockMoveLineExtend(models.Model):
    _inherit = 'stock.move.line'

    # @api.model
    # def _free_reservation(self, product_id, location_id, qty, lot_id=None, package_id=None, owner_id=None,
    #                       ml_to_ignore=None):
    #     return super(CustomStockMoveLineExtend, self)._free_reservation(product_id, location_id, qty, lot_id=lot_id,
    #                                                                     package_id=package_id, owner_id=owner_id)

    # @api.model
    # def _free_reservation(self, product_id, location_id, qty, lot_id=None, package_id=None, owner_id=None):
    #
    #     return super(CustomStockMoveLineExtend, self)._free_reservation(product_id, location_id, qty, lot_id=lot_id, package_id=package_id, owner_id=owner_id)

