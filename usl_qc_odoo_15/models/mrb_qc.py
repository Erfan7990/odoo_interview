from odoo import api, fields, models, _, exceptions
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError


class mrb_qc_product(models.Model):
    _name = 'mrb.qc.product'
    _description = 'MRB qc Products'
    _rec_name = 'seq'

    def _get_purchase_order_domain(self):
        domain = []
        incoming_qc_id = self.env['incoming.material.qc'].search(
            ['|', ('qc_type', '=', 'pre_qc'), ('qc_type', '=', 'incoming_qc')])
        l = [i.purchase_order.id for i in incoming_qc_id]
        # self.incoming_qc_id = incoming_qc_id.ids
        if incoming_qc_id:
            domain = [('id', '=', l)]
        return domain

    seq = fields.Char(string='Reference', readonly=True)
    purchase_order = fields.Many2one('purchase.order', string='PO Number',
                                     domain=lambda self: self._get_purchase_order_domain())
    vendor = fields.Many2one('res.partner', related='purchase_order.partner_id', string='Supplier')
    mrb_qc_line_id = fields.One2many('mrb.qc.product.line', 'mrb_qc_id')
    incoming_qc_id = fields.Many2one('incoming.material.qc', 'Incoming Material QC')
    user_id = fields.Many2one('res.partner', string='User', default=lambda self: self.env.user.partner_id.id,
                              readonly=True)

    def action_batch_annealing_qc(self):
        for rec in self:
            warehouse_id = self.env['stock.warehouse'].search([('id', '=', self.env.user.property_warehouse_id.id)])
            destination_location_id = self.env['stock.location'].search([('is_batch_annealing_location', '=', True)]).id

            batch_annealing_qc = self.env['mrb.qc.product.line'].search(
                [('mrb_choose', '=', 'batch_annealing'), ('mrb_qc_id', '=', rec.id)]).ids

            partner = rec.user_id.id
            source_location = warehouse_id.lot_stock_id.location_id.id

            if len(batch_annealing_qc) != 0:
                picking_data = {
                    'origin': rec.seq,
                    'partner_id': partner,
                    'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                    'location_id': source_location,
                    'branch_id': self.env.user.branch_id.id,
                    'location_dest_id': destination_location_id,
                    'is_from_allocate': True,
                }
                stock_picking = self.env['stock.picking'].create(picking_data)

                for line in rec.mrb_qc_line_id:
                    if line.mrb_choose == 'batch_annealing':
                        move_data = {
                            'origin': rec.seq,
                            'name': line.product.name,
                            'product_id': line.product.id,
                            'product_uom_qty': 1,
                            'product_uom': line.product.uom_id.id,
                            'location_id': source_location,
                            'location_dest_id': destination_location_id,
                            'picking_id': stock_picking.id,
                        }
                        move = self.env['stock.move'].create(move_data)

                pickings = self.env['stock.picking'].search([('origin', '=', self.seq)])
                action = self.env.ref('stock.action_picking_tree_all').read()[0]
                action['domain'] = [('id', 'in', pickings.ids)]

                return action
            else:
                raise UserError(_("You do not have enough product quantity to store."))


    def action_special_mining_qc(self):
        for rec in self:
            warehouse_id = self.env['stock.warehouse'].search([('id', '=', self.env.user.property_warehouse_id.id)])
            destination_location_id = self.env['stock.location'].search([('is_special_mining_location', '=', True)]).id

            batch_annealing_qc = self.env['mrb.qc.product.line'].search(
                [('mrb_choose', '=', 'special_mining'), ('mrb_qc_id', '=', rec.id)]).ids

            partner = rec.user_id.id
            source_location = warehouse_id.lot_stock_id.location_id.id

            if len(batch_annealing_qc) != 0:
                picking_data = {
                    'origin': rec.seq,
                    'partner_id': partner,
                    'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                    'location_id': source_location,
                    'branch_id': self.env.user.branch_id.id,
                    'location_dest_id': destination_location_id,
                    'is_from_allocate': True,
                }
                stock_picking = self.env['stock.picking'].create(picking_data)

                for line in rec.mrb_qc_line_id:
                    if line.mrb_choose == 'special_mining':
                        move_data = {
                            'origin': rec.seq,
                            'name': line.product.name,
                            'product_id': line.product.id,
                            'product_uom_qty': 1,
                            'product_uom': line.product.uom_id.id,
                            'location_id': source_location,
                            'location_dest_id': destination_location_id,
                            'picking_id': stock_picking.id,
                        }
                        move = self.env['stock.move'].create(move_data)

                pickings = self.env['stock.picking'].search([('origin', '=', self.seq)])
                action = self.env.ref('stock.action_picking_tree_all').read()[0]
                action['domain'] = [('id', 'in', pickings.ids)]

                return action
            else:
                raise UserError(_("You do not have enough product quantity to store."))

    @api.onchange('purchase_order')
    def onchange_purchase_order(self):
        for rec in self:
            rec.mrb_qc_line_id = [(5, 0, 0)]
            order_lines = rec.purchase_order.order_line
            mrb_qc_line_id_values = []

            incoming_qc_id = self.env['incoming.material.qc'].search(
                ['|', ('qc_type', '=', 'pre_qc'), ('qc_type', '=', 'incoming_qc')])
            for order_line in order_lines:
                mrb_qty_records = rec.env['incoming.material.qc.line'].search(
                    [('iqc_id', 'in', incoming_qc_id.ids), ('product', '=', order_line.product_id.id)])

                for mrb_qty in mrb_qty_records:
                    for i in range(int(mrb_qty.mrb_qty)):
                        mrb_qc_line_id_values.append((0, 0, {
                            'product': order_line.product_id.id,
                            'mrb_qty': 1
                        }))

            rec.mrb_qc_line_id = mrb_qc_line_id_values
    @api.model
    def create(self, vals):
        existing_record = self.search([('purchase_order', '=', vals.get('purchase_order'))])
        if existing_record:
            raise ValidationError("You cannot create a new record with the same purchase order.")
        vals['seq'] = self.env['ir.sequence'].next_by_code('usl_qc.mrb_qc')
        return super(mrb_qc_product, self).create(vals)


class mrb_qc_proudct_line(models.Model):
    _name = 'mrb.qc.product.line'

    product = fields.Many2one('product.product', string='Product', readonly=True)
    mrb_qty = fields.Float(string='MRB Qty', default=0.0)
    mrb_choose = fields.Selection([
        ('batch_annealing', 'Batch Annealing'),
        ('special_mining', 'Special Mining'),
    ], string='Choose MRB')
    mrb_qc_id = fields.Many2one('mrb.qc.product', string='MRB QC', ondelete='cascade')
