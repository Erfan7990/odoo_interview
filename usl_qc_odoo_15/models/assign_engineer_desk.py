from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AssignDeskEngineerWizard(models.Model):
    _name = 'assign.desk.engineer.wizard'

    def _get_engineer(self):
        data = self.env['role.manage'].search([('role_select', '=', 'engineer')])
        return data.users.ids

    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    reassign_desk = fields.Many2one('desk.setup.configuration', string='Reassign Desk')
    assign_qty = fields.Integer("Assign Quantity")
    reassign_qty = fields.Integer("Reassign Quantity")
    line_manager = fields.Many2one('res.users', string='Line Manager')
    production_planning_id = fields.Many2one('production.planning', string='Production Planning Id')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')
    line_management_id = fields.Many2one('line.management')
    default_bom_ids = fields.Many2many('mrp.bom', string="Product")
    bom_id = fields.Many2one('mrp.bom', string="Product", domain="[('id', 'in', default_bom_ids)]")
    qty = fields.Integer(string="Total Quantity")
    date = fields.Datetime(string='Date', default=fields.Datetime.now())
    remaining_qty = fields.Integer(string="Remaining Quantity")
    engineer = fields.Many2one('res.users', string='Engineer',
                               domain=lambda self: [('id', 'in', self._get_engineer())])
    reassign_engineer = fields.Many2one('res.users', string='Reassign Engineer',
                                        domain=lambda self: [('id', 'in', self._get_engineer())])
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    wizard_line_id = fields.One2many('assign.desk.engineer.wizard.table', 'wizard_id', string='Table Field')
    src_location_id = fields.Many2one(
        'stock.location', "BoM Location",
    )
    dest_location_id = fields.Many2one(
        'stock.location', "Finished Good Location",
    )
    engineer_type = fields.Selection([
        ('pre_assign', 'Pre Engineer Assign'),
        ('post_assign', 'Post/Reassign Engineer'),
        ('assign_qc_fail', 'QC Failed Product Assign'),
    ], compute='_compute_engineer_type', store=True)

    def _compute_engineer_type(self):
        if self.line_management_id.state == 'qc_failed':
            self.engineer_type = 'assign_qc_fail'
        else:
            return

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        exist_lot_ids = []
        wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search(
            [('line_management_id', '=', self.line_management_id.id), ('bom_id', '=', self.bom_id.id)])
        line_ids = self.env['line.management.line'].search(
            [('line_management_id', '=', self.line_management_id.id), ('bom_id', '=', self.bom_id.id)])

        if self.engineer_type == 'pre_assign':

            self.qty = line_ids.qty
            if line_ids.lot_ids:
                self.lot_ids = line_ids.lot_ids.ids
            if wizard_line_id:
                existing_qty = sum([data.qty for data in wizard_line_id])
                self.remaining_qty = line_ids.qty - existing_qty
            else:
                self.remaining_qty = line_ids.qty

        if self.engineer_type == 'post_assign':
            desk_ids = wizard_line_id.desk.ids
            self.desk = desk_ids
            # Set domain for self.desk
            return {
                'domain': {
                    'desk': [('id', 'in', desk_ids)]
                }
            }

        if self.engineer_type == 'assign_qc_fail':
            self.desk = wizard_line_id.desk.id
            # self.engineer = wizard_line_id.engineer.id
    @api.onchange('desk')
    def _onchange_desk(self):
        wizard_line_id = False

        if self.engineer_type == 'post_assign':
            wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search([
                ('line_management_id', '=', self.line_management_id.id),
                ('bom_id', '=', self.bom_id.id),
                ('desk', '=', self.desk.id),
                ('engineer_type', '=', 'pre_assign')
            ])
        if self.engineer_type == 'assign_qc_fail':
            wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search([
                ('line_management_id', '=', self.line_management_id.id),
                ('bom_id', '=', self.bom_id.id),
                ('desk', '=', self.desk.id),
            ])

        if wizard_line_id:
            self.qty = wizard_line_id.remaining_qty
            self.remaining_qty = wizard_line_id.remaining_qty
            self.engineer = wizard_line_id.engineer.id

    def assign_product(self):
        global wizard_line, name, form_id
        # assign Engineer until the remaining_qty is Zero
        if self.engineer_type == 'pre_assign':
            name = _('Assign Desk Engineer')
            form_id = self.env.ref("usl_qc.pre_assign_desk_engineer_form_view")
            if self.remaining_qty == 0:
                raise ValidationError('You already assign all products to your engineer')

            if not self.desk:
                raise ValidationError('You Must Select Desk')

            if not self.engineer:
                raise ValidationError('You Must Select Engineer')

            self.remaining_qty = self.remaining_qty - self.assign_qty

            existing_ids = self.env['assign.desk.engineer.wizard.table'].search([
                ('bom_id', '=', self.bom_id.id),
                # ('assembly_line', '=', self.assembly_line.id),
                ('lot_ids', '!=', False),
                ('line_management_id', '=', self.line_management_id.id),
                ('engineer_type', '=', 'pre_assign')
            ])
            existing_lot_ids = existing_ids.mapped('lot_ids')
            existing_desk = existing_ids.mapped('desk')
            existing_engineer = existing_ids.mapped('engineer')

            if self.assign_qty == 0 or not self.assign_qty:
                raise ValidationError('Please Enter Assign Quantity value.')
            #
            # if self.desk.id in existing_desk.ids:
            #     raise ValidationError('Selected Desk is already assigned.')
            #
            if self.engineer.id in existing_engineer.ids:
                raise ValidationError('Selected Engineer is already assigned')
            #
            if self.qty < self.assign_qty + sum([data.qty for data in existing_ids]):
                raise ValidationError('Quantity Exceeds!\nPlease Enter valid Quantity')

            all_lot_ids = list(set(self.lot_ids.ids) | set(existing_lot_ids.ids))

            if existing_lot_ids:
                # length = len(existing_lot_ids.ids) + int(self.assign_qty)
                new_lot_ids = list(set(all_lot_ids) - set(existing_lot_ids.ids))
                assign_lot_ids = new_lot_ids[0:int(self.assign_qty)]

            else:
                assign_lot_ids = all_lot_ids[0:int(self.assign_qty)]


            if assign_lot_ids:
                create_wizard_table = {
                    'bom_id': self.bom_id.id,
                    'qty': self.assign_qty,
                    'desk': self.desk.id,
                    'assembly_line': self.assembly_line.id,
                    'date': self.date,
                    'engineer': self.engineer.id,
                    'line_management_id': self.line_management_id.id,
                    'lot_ids': assign_lot_ids,
                    'wizard_id': self.id,
                    'engineer_type': self.engineer_type,
                }
                wizard_line = self.env['assign.desk.engineer.wizard.table'].create(create_wizard_table)
                wizard_line._onchange_qty()

            # Update the remaining_qty filed which is in line.management.line
            line_management_line_id = self.env['line.management.line'].search(
                [('line_management_id', '=', self.line_management_id.id), ('bom_id', '=', self.bom_id.id)])

            exist_line_lot_ids = list(set(line_management_line_id.lot_ids.ids) - set(assign_lot_ids))
            line_management_line_id.write({
                'remaining_qty': self.remaining_qty,
                'total_assigned_qty': line_management_line_id.qty - self.remaining_qty,
                'lot_ids': exist_line_lot_ids if exist_line_lot_ids else False
            })
            self.desk = False
            self.engineer = False
            self.assign_qty = False
        # Reassign engineer when production is not complete
        if self.engineer_type == 'post_assign':
            name = _('Reassign Desk Engineer')
            form_id = self.env.ref("usl_qc.post_assign_desk_engineer_form_view")

            if self.remaining_qty == 0:
                raise ValidationError('You already assign all products to your engineer')

            if not self.reassign_desk:
                raise ValidationError('You Must Select Desk')

            if not self.reassign_engineer:
                raise ValidationError('You Must Select Engineer')

            if self.reassign_qty == 0 or not self.reassign_qty:
                raise ValidationError("Reassign Quantity can't be zero")

            wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search([
                ('bom_id', '=', self.bom_id.id),
                ('engineer', '=', self.engineer.id),
                ('desk', '=', self.desk.id),
                ('line_management_id', '=', self.line_management_id.id),
                ('engineer_type', '=', 'pre_assign')
            ])

            new_exist_wizard_ids = self.env['assign.desk.engineer.wizard.table'].search([
                ('bom_id', '=', self.bom_id.id),
                ('line_management_id', '=', self.line_management_id.id),
                ('engineer_type', '=', 'post_assign')
            ])

            existing_new_lot_ids = new_exist_wizard_ids.mapped('lot_ids')
            existing_engineer = new_exist_wizard_ids.mapped('engineer')

            if self.reassign_engineer.id in existing_engineer.ids:
                raise ValidationError('Selected Engineer is already assigned')

            manufacture_ids = self.env['mrp.production'].search([
                ('line_management_id', '=', self.line_management_id.id),
                ('lot_producing_id', 'in', wizard_line_id.lot_ids.ids),
                ('state', '=', 'done')
            ])

            exist_lot_ids = list(set(wizard_line_id.lot_ids.ids) - set(manufacture_ids.lot_producing_id.ids))



            self.remaining_qty -= self.reassign_qty

            new_lot_ids = []

            if existing_new_lot_ids.ids in exist_lot_ids:
                pass
            else:
                new_lot_ids = exist_lot_ids[0:int(self.reassign_qty)]

            if new_lot_ids:
                wizard_line_id.lot_ids = [(3, lot_id.id) for lot_id in wizard_line_id.lot_ids if
                                          lot_id.id in new_lot_ids]

                wizard_line_id.write({
                    'remaining_qty': wizard_line_id.remaining_qty - len(new_lot_ids),
                    'qty': wizard_line_id.qty - len(new_lot_ids),
                })

            create_wizard_table = {
                'bom_id': self.bom_id.id,
                'qty': self.reassign_qty,
                'desk': self.reassign_desk.id,
                'assembly_line': self.assembly_line.id,
                'date': self.date,
                'engineer': self.reassign_engineer.id,
                'line_management_id': self.line_management_id.id,
                'lot_ids': [(6, 0, new_lot_ids)],
                'wizard_id': self.id,
                'engineer_type': self.engineer_type,
            }
            wizard_line = self.env['assign.desk.engineer.wizard.table'].create(create_wizard_table)
            wizard_line._onchange_qty()

            line_management_line_id = self.env['line.management.line'].search(
                [('line_management_id', '=', self.line_management_id.id), ('bom_id', '=', self.bom_id.id)])
            line_management_line_id.write({
                'mrp_remaining_qty': line_management_line_id.mrp_remaining_qty - self.reassign_qty
            })
            self.reassign_desk = False
            self.reassign_engineer = False
            self.reassign_qty = False

        # when qc_failed items assign to engineer
        if self.engineer_type == 'assign_qc_fail':
            name = _('Reassign Desk Engineer')
            form_id = self.env.ref("usl_qc.post_assign_desk_engineer_form_view")

            if self.reassign_qty == 0 or not self.reassign_qty:
                raise ValidationError('Please Enter Assign Quantity value.')

            if not self.reassign_desk:
                raise ValidationError('You Must Select Desk')

            if not self.reassign_engineer:
                raise ValidationError('You Must Select Engineer')

            if self.remaining_qty == 0:
                raise ValidationError('You already assign all products to your engineer')

            self.remaining_qty = (self.remaining_qty - self.reassign_qty) if self.remaining_qty > 0 else 0


            wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search([
                ('bom_id', '=', self.bom_id.id),
                ('engineer', '=', self.engineer.id),
                ('desk', '=', self.desk.id),
                ('line_management_id', '=', self.line_management_id.id),
            ])
            new_line_values = self.line_management_id.new_wizard_line_ids
            line_values = self.line_management_id.wizard_line_ids

            if wizard_line_id:
                for line in wizard_line_id:
                    if self.reassign_engineer == wizard_line_id.engineer:
                        line_values.write({
                            'bom_id': line.bom_id.id,
                            'desk': self.reassign_desk.id,
                            'engineer': self.reassign_engineer.id,
                            'lot_ids': line.lot_ids.ids,
                            'qty': line.qty,
                            'remaining_qty': line.remaining_qty,
                            'wizard_id': self.id,
                        })
                    else:
                        new_line_values.write({
                            'bom_id': line.bom_id.id,
                            'reassign_desk': self.reassign_desk.id,
                            'reassign_engineer': self.reassign_engineer.id,
                            'lot_ids': line.lot_ids.ids,
                            'qty': line.qty,
                            'remaining_qty': line.remaining_qty,
                            'wizard_id': self.id,
                            'engineer_type': 'assign_qc_fail',
                            'line_management_id': self.line_management_id.id
                        })
                        self.line_management_id.write({
                            'is_engineer_reassign': True,
                        })

            existing_lot_ids = wizard_line_id.mapped('lot_ids')



            line_management_line_id = self.env['line.management.line'].search([
                ('line_management_id', '=', self.line_management_id.id),
                ('bom_id', '=', self.bom_id.id),
                ('lot_ids', 'in', existing_lot_ids.ids)
                 ])

            exist_line_lot_ids = list(set(line_management_line_id.lot_ids.ids) - set(existing_lot_ids.ids))
            line_management_line_id.write({
                'remaining_qty': self.remaining_qty,
                'total_assigned_qty': line_management_line_id.qty - self.remaining_qty,
                'lot_ids': exist_line_lot_ids if exist_line_lot_ids else False
            })
            self.reassign_desk = False
            self.reassign_engineer = False
            self.reassign_qty = False

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'assign.desk.engineer.wizard',
            'res_id': self.id,
            'views': [(form_id.id, 'form')],
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        '''
            Here we create mrp.production and also create engineer.profile.......
        '''

        global engineer_state, line_management_id
        manufacture_id = False
        for line in self.wizard_line_id:
            product_id = self.env['product.product'].search([('product_tmpl_id', '=', line.bom_id.product_tmpl_id.id)])
            warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', self.src_location_id.id)])
            picking_type_id = self.env['stock.picking.type'].search(
                [('warehouse_id', '=', warehouse_id.id), ('sequence_code', '=', 'MO')])

            if self.engineer_type == 'pre_assign' or self.engineer_type == 'assign_qc_fail':
                line_management_id = self.env['line.management'].search([('id', '=', line.line_management_id.id)])
                # if state is qc_failed then remove those data from engineer.profile and mrp.production
                if line_management_id.state == 'qc_failed':
                    prev_engineer_id = self.env['engineer.profile'].search([('lot_production_id', '=', line.lot_ids.id)])
                    prev_engineer_id.unlink()

                    manufacture_id = self.env['mrp.production'].search([('lot_producing_id', '=', line.lot_ids.id)])
                    engineer_state = 'qc_failed'
                else:
                    line_management_id.write({
                        'is_engineer_assign': True,
                    })
                    engineer_state = 'pending'


                line_management_line_id = self.env['line.management.line'].search([
                    ('line_management_id', '=', line_management_id.id)
                ])
                # vals = all(line.remaining_qty == 0 for line in line_management_line_id)
                if all(line.remaining_qty == 0 for line in line_management_line_id):
                    line_management_id.write({
                        'state': 'complete',
                    })
                else:
                    line_management_id.write({
                        'state': 'in_progress',
                    })

            for lot_data in line.lot_ids:
                if self.engineer_type == 'post_assign':
                    prev_engineer_id = self.env['engineer.profile'].search([('lot_production_id', '=', lot_data.id)])
                    prev_engineer_id.unlink()

                    manufacture_id = self.env['mrp.production'].search([('lot_producing_id', '=', lot_data.id)])
                    # manufacture_id.state = 'cancel'
                    if manufacture_id.state != 'done':
                        manufacture_id.do_unreserve()
                        manufacture_id.action_cancel()
                        manufacture_id.unlink()
                    engineer_state = 'pending'

                if self.engineer_type != 'assign_qc_fail':
                    create_mo = {
                        'user_id': line.engineer.id,
                        'company_id': line.engineer.company_id.id,
                        'product_id': product_id.id,
                        # 'product_qty': 1,
                        'product_uom_id': product_id.uom_id.id,
                        # 'lot_producing_id': lot_data.id,
                        # 'qty_producing': 1,
                        # 'product_uom_qty': 1,
                        'bom_id': line.bom_id.id,
                        'picking_type_id': picking_type_id.id,
                        'location_src_id': self.src_location_id.id,
                        'location_dest_id': self.dest_location_id.id,
                        'date_planned_start': self.date,
                        'line_management_id': line.line_management_id.id,
                        'production_planning_id': self.production_planning_id.id,
                        'desk_id': line.desk.id,
                        'assembly_line': line.assembly_line.id,
                        # 'components_availability': _('Available'),
                        # 'components_availability_state': 'available',
                    }

                    mo_id = self.env['mrp.production'].create(create_mo)
                    mo_id.action_confirm()
                    mo_id._onchange_bom_id()
                    mo_id._onchange_move_raw()
                    mo_id._onchange_move_finished_product()
                    mo_id._onchange_location()
                    mo_id.write({
                        'lot_producing_id': lot_data.id,
                    })
                    mo_id._onchange_producing()
                    mo_id._onchange_lot_producing()

                    manufacture_id = mo_id
                    engineer = line.engineer
                    desk = line.desk
                    remarks = False
                else:
                    manufacture_id = manufacture_id
                    engineer = line.reassign_engineer if line.reassign_engineer else line.engineer
                    desk = line.reassign_desk if line.reassign_desk else line.desk
                    remarks = line_management_id.remarks


                create_engineer = {
                    'desk': desk.id,
                    'engineer': engineer.id,
                    'line_management_id': line.line_management_id.id,
                    'manufacture_id': manufacture_id.id,
                    'bom_id': line.bom_id.id,
                    'product_id': product_id.id,
                    'reason': remarks,
                    'qty': 1,
                    'line_manager': self.line_manager.id,
                    'assembly_line_id': self.assembly_line.id,
                    'production_planning_id': self.production_planning_id.id,
                    'date': self.date,
                    'state': engineer_state,
                    'lot_production_id': lot_data.id,
                }
                engineer_id = self.env['engineer.profile'].create(create_engineer)
                engineer_id._onchange_bom_id()
                engineer_id._onchange_date()

                if self.engineer_type == 'assign_qc_fail':

                    if manufacture_id.state == 'done':
                        engineer_line_ids = engineer_id.engineer_line_ids
                        for line in engineer_line_ids:
                            move_data = self.env['stock.move'].search([
                                ('raw_material_production_id', '=', manufacture_id.id),
                                ('product_id', '=', line.product_id.id)
                            ])

                            line.write({
                                'lot_ids': move_data.lot_ids.ids,
                            })
                            line._onchange_lot_ids()




class AssignDeskEngineerWizardTable(models.Model):
    _name = 'assign.desk.engineer.wizard.table'
    _description = 'Transient Table for Assign Desk Engineer Wizard'

    bom_id = fields.Many2one('mrp.bom', string="Product")
    qty = fields.Integer(string="Quantity")
    remaining_qty = fields.Integer(string="Remaining Production Quantity")
    production_complete_qty = fields.Integer(string="Production Complete")
    date = fields.Date(string='Date', default=fields.Date.today())
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    wizard_id = fields.Many2one('assign.desk.engineer.wizard', string='Wizard', ondelete='cascade')
    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    engineer = fields.Many2one('res.users', string='Engineer')
    reassign_desk = fields.Many2one('desk.setup.configuration', string='Desk')
    reassign_engineer = fields.Many2one('res.users', string='Engineer')
    line_management_id = fields.Many2one('line.management')
    engineer_type = fields.Selection([
        ('pre_assign', 'Pre Engineer Assign'),
        ('post_assign', 'Post Engineer Assign'),
        ('assign_qc_fail', 'QC Failed Product Assign'),
    ])
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'Production In Progress'),
        ('done', 'Complete'),
        ('cancel', 'Cancelled'),
    ], default='pending', string='Status')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')

    @api.onchange('qty')
    def _onchange_qty(self):
        self.remaining_qty = self.qty
