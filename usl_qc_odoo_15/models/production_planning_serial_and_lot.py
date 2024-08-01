from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import re


class ProductionSerialNo(models.Model):
    _name = 'production.planning.serial'
    _description = 'Production Planning Lot and Serial Number'

    product_id = fields.Many2one('product.product', string='Product')
    bom_id = fields.Many2one('mrp.bom', string="Product")
    qty = fields.Integer(string="Qty", required=True)
    assign_serial = fields.Text(string='Assign Serial/Lot')
    is_clicked_button = fields.Boolean(string='is clicked', default=False)
    production_planning_line_id = fields.Many2one('production.planning.line', string='production_planning_line_id')
    production_planning_id = fields.Many2one('production.planning', string='Engineer Location', ondelete='cascade')
    pp_serial_line_ids = fields.One2many('production.planning.serial.line', 'pp_serial_id',
                                         string='Production Planning Serial Line ID')

    def action_assign_serial_number(self):
        pattern = r'[`=~!@#$%^&*()+\[\]{};\'\\:"|<,./<>?\n ]'
        serial_values = re.split(pattern, self.assign_serial)

        self.is_clicked_button = True

        if self.qty < len(serial_values):
            raise ValidationError(
                f'You can not overwrite the qty.\nBecause you assign serial number for {len(serial_values)} products. But on hand quantity is {self.qty}')

        exist_serials = self.env['stock.production.lot'].search([('name', 'in', serial_values)])
        if exist_serials:

            if len(exist_serials.ids) == len(serial_values):
                existing_products = set(serial.product_id.name for serial in exist_serials)
                raise ValidationError(
                    f'Those given serial/lot already exist for these product: {", ".join(existing_products)}')


        line_values = []
        exist_pp_serial_line_ids = self.env['production.planning.serial.line'].search([('lot_id', 'in', exist_serials.ids)])
        if not exist_pp_serial_line_ids:
            exist_pp_lot_ids = self.env['production.planning.serial.line'].search([('pp_serial_id', '=', self.id)])
            query = """delete from production_planning_serial_line where pp_serial_id = {}""".format(self.id)
            self._cr.execute(query)

            # lot_query = """select from stock_production_lot where id in {}""".format(exist_pp_lot_ids.lot_id.ids)
            # self._cr.execute(lot_query)

        exist_name_serials = exist_serials.mapped('name')
        new_serial_data = list(set(serial_values) - set(exist_name_serials))
        for val in new_serial_data:
            exist_serial = self.env['stock.production.lot'].search([('name', '=', val)])
            if exist_serial:
                raise ValidationError(
                    f'The given serial/lot {val} already exist for this {exist_serial.product_id.name}')

            create_serial_data = {
                'name': val,
                'product_id': self.product_id.id,
                'product_uom_id': self.product_id.uom_id.id,
                'company_id': self.env.user.company_id.id
            }
            serial_lot_id = self.env['stock.production.lot'].create(create_serial_data)

            create_line = {
                'product_id': self.product_id.id,
                'bom_id': self.bom_id.id,
                'lot_id': serial_lot_id.id,
                'qty': 1,
                'pp_serial_id': self.id,
            }
            pp_line_id = self.env['production.planning.serial.line'].create(create_line)
            if exist_pp_serial_line_ids:
                if len(line_values) < len(exist_pp_serial_line_ids.ids):
                    line_values = exist_pp_serial_line_ids.ids

                line_values.append(pp_line_id.id)
            else:
                line_values.append(pp_line_id.id)

        self.pp_serial_line_ids = line_values

        return {
            'name': _('Assign Product Serial Number'),
            'type': 'ir.actions.act_window',
            'res_model': 'production.planning.serial',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def save_and_close(self):
        pattern = r'[`=~!@#$%^&*()+\[\]{};\'\\:"|<,./<>?\n ]'
        serial_values = re.split(pattern, self.assign_serial)

        lot_ids = self.env['stock.production.lot'].search([('name', 'in', serial_values)])
        if lot_ids:
            production_planning_line_id = self.env['production.planning.line'].search(
                [('id', '=', self.production_planning_line_id.id)])
            if production_planning_line_id.qty != len(lot_ids.ids):
                raise ValidationError(
                    f'You left to assign {production_planning_line_id.qty - len(lot_ids.ids)} quantity serial/lot numbers')
            production_planning_line_id.write({
                'lot_ids': lot_ids.ids,
                'qty_done': len(lot_ids.ids)
            })


class ProductionSerialNoLine(models.Model):
    _name = 'production.planning.serial.line'
    _description = 'Production Planning Lot and Serial Number'
    _order = 'lot_id desc'

    product_id = fields.Many2one('product.product', string='Product')
    bom_id = fields.Many2one('mrp.bom', string="Product")
    lot_id = fields.Many2one('stock.production.lot', string='Serial/Lots')
    qty = fields.Integer(string="Qty", required=True)

    pp_serial_id = fields.Many2one('production.planning.serial', string='Production Planning Serial ID')
