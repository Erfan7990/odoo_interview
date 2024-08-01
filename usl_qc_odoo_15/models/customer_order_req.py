from odoo import models, fields, api, _
from odoo.exceptions import UserError



# Models

from odoo import models, fields, api, _

class CustomerOrderRequest(models.Model):
    _name = 'customer.order.req'
    _description = 'Customer Order Request'
    _rec_name = 'customer'
    _order = 'id desc'

    customer = fields.Many2one('res.partner', string='Customer', required=True)
    address = fields.Char(string='Address', related='customer.street', readonly=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, readonly=True)
    product_lines = fields.One2many('customer.order.req.line', 'order_id', string='Product Lines')
    item_sent_to_customer = fields.Many2one('item.sent.to.customer', string='Item Sent to Customer',
                                            ondelete='set null', readonly=True)

    @api.depends('customer')
    def _compute_address(self):
        for order in self:
            if order.customer:
                order.address = order.customer.street or ''

    def send_sample_to_customer_button(self):
        return {
            'name': 'Product Allocation',
            'type': 'ir.actions.act_window',
            'res_model': 'product.allocation',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'default_allocate_for': self.customer.id,
                'parent_id': self.id,
            },
            'domain': [('allocate_for', '=', self.customer.id)],
        }

    # def customer_qc_button(self):
    #     # qc_id = self.env['customer.qc.checking'].search([('customer', '=', self.customer.id)])
    #     return {
    #         'name': 'QC Checking',
    #         'type': 'ir.actions.act_window',
    #         'view_mode': 'tree,form',
    #         'res_model': 'customer.qc.checking',
    #         'context': {},
    #         'target': 'current',
    #         # 'domain': [('id', 'in', qc_id.ids)],
    #         'domain': [],
    #     }



class CustomerOrderRequestLine(models.Model):
    _name = 'customer.order.req.line'
    _description = 'Order Request Line'
    _rec_name = 'product'

    order_id = fields.Many2one('customer.order.req', string='Order Reference')
    product = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price = fields.Float(string='Price')
    product_specifications = fields.One2many('product.specification', 'order_line_id', string='Specifications')
    allocation_id = fields.Many2one('product.allocation', string='Allocation')

    def action_specification(self):
        # Check if there is an existing specification for this product line
        existing_specification = self.env['customer.order.req.line.specification.wizard'].search([('order_line_id','=',self.id)],limit=1)

        if existing_specification:
            # If there is existing data, open it for editing
            return {
                'name': _('Product Specification'),
                'type': 'ir.actions.act_window',
                'res_model': 'customer.order.req.line.specification.wizard',
                'view_mode': 'form',
                'target': 'new',
                'res_id': existing_specification.id,
                'context': {'default_order_line_id': self.id,'default_specification_text':existing_specification},
            }
        else:
            # If no data exists, open an empty form
            return {
                'name': _('Product Specification'),
                'type': 'ir.actions.act_window',
                'res_model': 'customer.order.req.line.specification.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_order_line_id': self.id},
            }

class CustomerOrderRequestLineSpecificationWizard(models.Model):
    _name = 'customer.order.req.line.specification.wizard'
    _description = 'Specification Editor Wizard'

    # @api.model
    # def default_get(self, fields_list):
    #     res=super().default_get(fields_list)
    #     # res['']=
    #     print("*******")
    specification_text = fields.Html(string='Specification Text')
    order_line_id = fields.Many2one('customer.order.req.line', string='Order Line')

    # @api.onchange('order_line_id')
    # def set_data(self):
    #     for rec in self:
    #         print(rec)

    def save_specification_text(self):
        self.ensure_one()

        specification = self.order_line_id.product_specifications
        if specification:
            specification.write({'specification_text': self.specification_text})
        else:
            self.env['product.specification'].create({
                'product_line_id': self.order_line_id.id,
                'specification_text': self.specification_text,
            })

        return {'type': 'ir.actions.act_window_close'}

class ProductSpecification(models.Model):
    _name = 'product.specification'
    _description = 'Product Specification'

    order_line_id = fields.Many2one('customer.order.req.line', string='Order Line')
    specification_text = fields.Html(string='Specification Text')





