from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AssignDeskEngineerWizard(models.TransientModel):
    _name = 'assign.desk.engineer.wizard'

    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    assign_qty = fields.Integer("Assign Quantity")
    line_manager = fields.Many2one('res.users', string='Line Manager')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')
    line_management_id = fields.Many2one('line.management')
    default_bom_ids = fields.Many2many('mrp.bom', string="Product")
    bom_id = fields.Many2one('mrp.bom', string="Product", domain="[('id', 'in', default_bom_ids)]")
    qty = fields.Integer(string="Total Quantity", readonly=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now())
    remaining_qty = fields.Integer(string="Remaining Quantity", readonly=True)
    engineer = fields.Many2one('res.users', string='Engineer', required=True)
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    wizard_line_id = fields.One2many('assign.desk.engineer.wizard.table', 'wizard_id', string='Table Field')
    src_location_id = fields.Many2one(
        'stock.location', "BoM Location",
    )
    dest_location_id = fields.Many2one(
        'stock.location', "Finished Good Location",
    )

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        exist_lot_ids = []
        line_ids = self.env['line.management.line'].search(
            [('line_management_id', '=', self.line_management_id.id), ('bom_id', '=', self.bom_id.id)])

        self.qty = line_ids.qty
        if line_ids.lot_ids:
            self.lot_ids = line_ids.lot_ids.ids

        wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search(
            [('line_management_id', '=', self.line_management_id.id), ('bom_id', '=', self.bom_id.id)])

        if wizard_line_id:
            existing_qty = sum([data.qty for data in wizard_line_id])
            self.remaining_qty = line_ids.qty - existing_qty
        else:
            self.remaining_qty = line_ids.qty

    def assign_product(self):
        global wizard_line
        self.remaining_qty = self.remaining_qty - self.assign_qty

        existing_ids = self.env['assign.desk.engineer.wizard.table'].search([
            ('bom_id', '=', self.bom_id.id),
            ('lot_ids', '!=', False),
            ('line_management_id', '=', self.line_management_id.id)
        ])
        existing_lot_ids = existing_ids.mapped('lot_ids')
        existing_desk = existing_ids.mapped('desk')
        existing_engineer = existing_ids.mapped('engineer')

        if self.assign_qty == 0 or not self.assign_qty:
            raise ValidationError('Please Enter Assign Quantity value.')

        if self.desk.id in existing_desk.ids:
            raise ValidationError('Selected Desk is already assigned.')

        if self.engineer.id in existing_engineer.ids:
            raise ValidationError('Selected Engineer is already assigned')

        if self.qty < self.assign_qty + sum([data.qty for data in existing_ids]):
            raise ValidationError('Quantity Exceeds!\nPlease Enter valid Quantity')

        if existing_lot_ids:
            length = len(existing_lot_ids.ids) + int(self.assign_qty)
            lot_ids_slice = self.lot_ids.ids[0:length]
        else:
            lot_ids_slice = self.lot_ids.ids[0:int(self.assign_qty)]

        new_lot_ids = list(set(lot_ids_slice) - set(existing_lot_ids.ids))
        if new_lot_ids:
            create_wizard_table = {
                'bom_id': self.bom_id.id,
                'qty': self.assign_qty,
                'desk': self.desk.id,
                'date': self.date,
                'engineer': self.engineer.id,
                'line_management_id': self.line_management_id.id,
                'lot_ids': [(6, 0, new_lot_ids)],
                'wizard_id': self.id,
            }
            wizard_line = self.env['assign.desk.engineer.wizard.table'].create(create_wizard_table)
            wizard_line._onchange_qty()
        # Update the remaining_qty filed which is in line.management.line
        line_management_line_id = self.env['line.management.line'].search(
            [('line_management_id', '=', self.line_management_id.id), ('bom_id', '=', self.bom_id.id)])
        line_management_line_id.write({
            'remaining_qty': self.remaining_qty,
            'total_assigned_qty': line_management_line_id.qty - self.remaining_qty,
        })

        return {
            'name': _('Assign Desk Engineer'),
            'type': 'ir.actions.act_window',
            'res_model': 'assign.desk.engineer.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        '''
            Here we create mrp.production and also create engineer.profile.......
        '''

        for line in self.wizard_line_id:
            product_id = self.env['product.product'].search([('product_tmpl_id', '=', line.bom_id.product_tmpl_id.id)])
            warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', self.src_location_id.id)])
            picking_type_id = self.env['stock.picking.type'].search(
                [('warehouse_id', '=', warehouse_id.id), ('sequence_code', '=', 'MO')])
            for lot_data in line.lot_ids:
                create_mo = {
                    'user_id': self.engineer.id,
                    'company_id': self.engineer.company_id.id,
                    'product_id': product_id.id,
                    'product_qty': 1,
                    'product_uom_id': product_id.uom_id.id,
                    'lot_producing_id': lot_data.id,
                    'qty_producing': 1,
                    # 'product_uom_qty': 1,
                    'bom_id': line.bom_id.id,
                    'picking_type_id': picking_type_id.id,
                    'location_src_id': self.src_location_id.id,
                    'location_dest_id': self.dest_location_id.id,
                    'date_planned_start': self.date,
                    'line_management_id': self.line_management_id.id,
                    'desk_id': self.desk.id,
                    # 'components_availability': _('Available'),
                    # 'components_availability_state': 'available',
                }

                mo_id = self.env['mrp.production'].create(create_mo)
                mo_id._onchange_bom_id()
                # mo_id._onchange_date_planned_start()
                mo_id._onchange_move_raw()
                # mo_id._onchange_location()

                create_engineer = {
                    'desk': self.desk.id,
                    'line_management_id': self.line_management_id.id,
                    'manufacture_id': mo_id.id,
                    'bom_id': self.bom_id.id,
                    'product_id': product_id.id,
                    'qty': 1,
                    'line_manager': self.line_manager.id,
                    'assembly_line_id': self.assembly_line.id,
                    'engineer': self.engineer.id,
                    'date': self.date,
                    'state': 'pending',
                    'lot_production_id': lot_data.id,
                }
                engineer_id = self.env['engineer.profile'].create(create_engineer)
                engineer_id._onchange_bom_id()
                engineer_id._onchange_date()


class AssignDeskEngineerWizardTable(models.TransientModel):
    _name = 'assign.desk.engineer.wizard.table'
    _description = 'Transient Table for Assign Desk Engineer Wizard'

    bom_id = fields.Many2one('mrp.bom', string="Product")
    qty = fields.Integer(string="Quantity")
    remaining_qty = fields.Integer(string="Remaining Quantity")
    date = fields.Date(string='Date', default=fields.Date.today())
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    wizard_id = fields.Many2one('assign.desk.engineer.wizard', string='Wizard', ondelete='cascade')
    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    engineer = fields.Many2one('res.users', string='Engineer')
    line_management_id = fields.Many2one('line.management')

    @api.onchange('qty')
    def _onchange_qty(self):
        self.remaining_qty = self.qty
