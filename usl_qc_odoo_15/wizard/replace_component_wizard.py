from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ReplaceComponentWizard(models.TransientModel):
    _name = 'replace.component.wizard'

    engineer_id = fields.Many2one('engineer.profile', string='Engineer Profile')
    bom_id = fields.Many2one('mrp.bom', string="Product")
    product_id = fields.Many2one('product.product', string="Product")
    qty = fields.Integer(string="Quantity")
    qty_done = fields.Integer(string='Done Quantity')
    product_uom_id = fields.Many2one('uom.uom', string='UoM')
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    lot_id = fields.Many2one('stock.production.lot', string='Serial/Lot Number',  domain="[('id', 'in', lot_ids)]")
    replace_lot_name = fields.Char(string='Replace Serial/Lot Number')

    def action_replace_component(self):
        query = """ update stock_production_lot set name = '{}' where id = {}""".format(self.replace_lot_name, self.lot_id.id)
        self._cr.execute(query)

