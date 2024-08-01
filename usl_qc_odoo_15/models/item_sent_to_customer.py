from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ItemSentToCustomer(models.Model):
    _name = 'item.sent.to.customer'
    _description = 'Item Sent to Customer'

    customer = fields.Char(string='Customer', readonly=True)
    address = fields.Char(string='Address', readonly=True)
    date = fields.Date(string="Create Date", readonly=True)
    product_lines = fields.One2many('item.sent.to.customer.line', 'item_id', string='Product Lines')


class ItemSentToCustomerLine(models.Model):
    _name = 'item.sent.to.customer.line'
    _description = 'Item Sent to Customer Line'

    item_id = fields.Many2one('item.sent.to.customer', string='Item Reference')
    product = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price = fields.Float(string='Price')





