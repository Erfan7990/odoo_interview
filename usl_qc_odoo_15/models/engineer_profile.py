from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class EngineerProfile(models.Model):
    _name = 'engineer.profile'
    _description = 'Engineer Profile Assign'
    _order = 'id desc'
    _rec_name = 'name'

    name = fields.Char(readonly=True, default=lambda self: _('New'), string="Reference")
    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    line_management_id = fields.Many2one('line.management', string='Source')
    manufacture_id = fields.Many2one('mrp.production', string='Manufacture Order')
    bom_id = fields.Many2one('mrp.bom', string="Bill of Material")
    product_id = fields.Many2one('product.product', string="Product")
    qty = fields.Integer('Quantity')
    line_manager = fields.Many2one('res.users', string='Line Manager')
    lot_production_id = fields.Many2one('stock.production.lot', string='Serial/Lot Number')
    assembly_line_id = fields.Many2one('mrp.workcenter', string='Assembly Line')
    engineer = fields.Many2one('res.users', string='Engineer')
    date = fields.Date(string="Date", default=fields.Date.today())
    date_planned_start = fields.Date(string="Scheduled Date")
    mrp_timer = fields.Char()
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'Production In Progress'),
        ('done', 'Complete'),
        ('cancel', 'Cancelled'),
        ('qc_failed', 'QC Failed')
    ], group_expand='_expand_groups', default='pending', string='Status')
    engineer_line_ids = fields.One2many('engineer.profile.line', 'engineer_id', string='Desks')
    product_image = fields.Binary(string="Product Image", related="bom_id.product_tmpl_id.image_1920", readonly=True)
    auto_cancel = fields.Boolean(string='Auto Cancel', default=False)
    production_planning_id = fields.Many2one('production.planning', string='Production Planning Id')
    raw_materials_barcode = fields.Char(string="Barcode")
    duration = fields.Float(string='Duration')
    reason = fields.Html(string='Reason')
    remarks = fields.Html(string='Remarks')
    start_time = fields.Datetime(string="Production Start Time")
    finish_time = fields.Datetime(string="Production Finish Time")
    date_result = fields.Char(string="Duration", compute='_compute_date_result', store=True)
    color = fields.Integer(string='Color', compute='_get_color')
    is_qc_failed = fields.Boolean('Is Qc Failed?', default=False, compute='_compute_qc_failed')


    def _compute_qc_failed(self):
        if self.state == 'qc_failed':
            self.is_qc_failed = True
        else:
            self.is_qc_failed = False

    def _get_color(self):
        for rec in self:
            if rec.state == 'pending':
                rec.color = 4
            if rec.state == 'in_progress':
                rec.color = 3
            if rec.state == 'done':
                rec.color = 10
            if rec.state == 'cancel':
                rec.color = 1
            if rec.state == 'qc_failed':
                rec.color = 6

    @api.depends('start_time', 'finish_time')
    def _compute_date_result(self):
        for record in self:
            if record.start_time and record.finish_time:
                start_dt = fields.Datetime.from_string(record.start_time)
                finish_dt = fields.Datetime.from_string(record.finish_time)
                duration = finish_dt - start_dt
                days = duration.days
                hours, remainder = divmod(duration.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                record.date_result = "{:02} Days, {:02}:{:02}:{:02}".format(days, hours, minutes, seconds)
            else:
                record.date_result = ''

    def action_start_production(self):
        for record in self:
            record.start_time = fields.Datetime.now()

            wizard_line_ids = self.env['assign.desk.engineer.wizard.table'].search(
                [('line_management_id', '=', self.line_management_id.id)])
            for line_data in wizard_line_ids:
                if line_data.engineer.id == self.engineer.id:
                    line_data.write({
                        'state': 'in_progress'
                    })

                    record.state = 'in_progress'

    def action_finish_production(self):
        for record in self:
            record.finish_time = fields.Datetime.now()

    @api.onchange('raw_materials_barcode')
    def onchange_raw_barcode(self):
        lot_datas = self.env['stock.production.lot'].search([('name', '=', self.raw_materials_barcode)])
        if len(lot_datas.ids) > 1:
            raise ValidationError('Invalid Serial. The serial is already used for another production!')
        if lot_datas:
            duplicates = self.env['stock.move.line'].search_count([
                ('lot_id', '=', lot_datas.id),
                ('qty_done', '=', 1),
                ('state', '=', 'done'),
                ('location_dest_id.usage', '=', 'production'),
            ])
            if duplicates:
                raise ValidationError('Invalid Serial. The serial is already used for another production!')
            for line in self.engineer_line_ids:
                if lot_datas.id not in line.lot_ids.ids:
                    if lot_datas.product_id.id == line.product_id.id:
                        if line.qty > len(line.lot_ids):
                            line.lot_ids += lot_datas
                            line.qty_done = len(line.lot_ids)
                        else:
                            raise ValidationError(f'You can not assign more than {line.qty} serial/lot number.')
                else:
                    if line.qty != line.qty_done:
                        if lot_datas.product_id.id == line.product_id.id:
                            existing_lot_ids = line.lot_ids.ids
                            new_lot_ids = [lot.id for lot in lot_datas if lot.id not in existing_lot_ids]
                            line.lot_ids += lot_datas
                            line.qty_done = len(line.lot_ids)
                    else:
                        raise ValidationError(f'You can not assign more than {line.qty} serial/lot number.')
        self.raw_materials_barcode = False

    # def _auto_cancel_entries(self):
    #     '''
    #     we update the remaining qty for engineer and line manager in  assign.desk.engineer.wizard.table wizard model
    #     and line.management.line model and also update the manufacturing state and stock_move and stock_move_line state
    #     others things also.
    #
    #     '''
    #     records = self.search([
    #         ('state', '=', 'pending'),
    #         ('date', '<=', fields.Date.context_today(self)),
    #         ('auto_cancel', '=', True),
    #     ])
    #     for rec in records:
    #         rec.write({
    #             'state': 'cancel'
    #         })
    #
    #         manufacture_id = self.env['mrp.production'].search([('id', '=', rec.manufacture_id.id)])
    #         manufacture_id.write({
    #             'state': 'cancel'
    #         })
    #         manufacture_id.do_unreserve()
    #         manufacture_id.action_cancel()
    #
    #
    #         # here update the engineer remaining quantity in assign.desk.engineer.wizard.table
    #         wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search([
    #             ('line_management_id', '=', rec.line_management_id.id),
    #             ('bom_id', '=', rec.bom_id.id),
    #             ('desk', '=', rec.desk.id),
    #             ('engineer', '=', rec.engineer.id),
    #         ])
    #         wizard_line_id.write({
    #             'remaining_qty': wizard_line_id.remaining_qty - self.qty if wizard_line_id.remaining_qty > 0 else 0
    #         })
    #
    #         # here update the line manager remaining quantity in line.management.line model
    #         line_management_line_id = self.env['line.management.line'].search([
    #             ('line_management_id', '=', rec.line_management_id.id),
    #             ('bom_id', '=', rec.bom_id.id)
    #         ])
    #         cnt = self.search_count([('state', '=', 'done'), ('bom_id', '=', rec.bom_id.id)])
    #
    #         line_management_line_id.write({
    #             'mrp_remaining_qty': line_management_line_id.total_assigned_qty - cnt
    #         })

    # color = fields.Integer('Color Index', compute="change_colore_on_kanban", store=True)

    @api.model
    def _expand_groups(self, states, domain, order):
        return ['pending', 'in_progress', 'done', 'cancel', 'qc_failed']

    @api.onchange('date')
    def _onchange_date(self):
        self.date_planned_start = self.date
        self.auto_cancel = True

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        self.engineer_line_ids = [(5, 0, 0)]

        engineer_line_values = []

        for line in self.bom_id.bom_line_ids:
            lot_ids = self.env['stock.production.lot'].search([('product_id', '=', line.product_id.id)])
            engineer_line_values.append((0, 0, {
                'bom_id': self.bom_id.id,
                'product_id': line.product_id.id,
                'qty': line.product_qty,
                'product_uom_id': line.product_uom_id.id,
                'qty_done': 0,
                # 'lot_ids': lot_ids.ids,
            }))
        self.engineer_line_ids = engineer_line_values

    def action_done(self):
        '''
        * In first phase we are going to update the stock.move.line, stock.move and mrp.production based on
        product and their lot_ids.
        * In second phase we update the remaining qty for engineer and line manager in  assign.desk.engineer.wizard.table wizard model
        and line.management.line model.
        '''
        if self.state != 'qc_failed':
            manufacture_id = self.env['mrp.production'].search([('id', '=', self.manufacture_id.id)])
            product_id = self.env['product.product'].search([('product_tmpl_id', '=', self.bom_id.product_tmpl_id.id)])
            move_line_lot_mapping = {}
            self.finish_time = fields.Datetime.now()

            for data in self.engineer_line_ids:
                if data.qty != data.qty_done:
                    raise ValidationError('You must enter all the serial numbers before Confirming.')

                move_lines = self.env['stock.move.line'].search([
                    ('move_id', 'in', self.manufacture_id.move_raw_ids.ids),
                    ('production_id', '=', self.manufacture_id.id),
                    ('product_id', '=', data.product_id.id)
                ])

                serial_numbers = [serial.id for serial in data.lot_ids]
                for move_line, serial in zip(move_lines, serial_numbers):
                    move_line.write({
                        'lot_id': serial,
                        'qty_done': 1
                    })
                    move_line._onchange_qty_done()
                    stock_moves = self.env['stock.move'].search([('move_line_ids', '=', move_line.id)])

            # Update the state of the current object to 'done'
            manufacture_id.write({
                'engineer_id': self.id,
            })
            self.state = 'done'
            # manufacture_id._get_produced_qty()
            manufacture_id.button_mark_done()
            # here update the engineer remaining quantity in assign.desk.engineer.wizard.table
            wizard_line_id = self.env['assign.desk.engineer.wizard.table'].search([
                ('line_management_id', '=', self.line_management_id.id),
                ('bom_id', '=', self.bom_id.id),
                ('desk', '=', self.desk.id),
                ('engineer', '=', self.engineer.id),
            ])
            wizard_line_id.write({
                'remaining_qty': wizard_line_id.remaining_qty - self.qty if wizard_line_id.remaining_qty > 0 else 0
            })

            # here update the line manager remaining quantity in line.management.line model
            line_management_line_id = self.env['line.management.line'].search([
                ('line_management_id', '=', self.line_management_id.id),
                ('bom_id', '=', self.bom_id.id)
            ])
            cnt = self.env['mrp.production'].search_count([
                ('state', '=', 'done'),
                ('line_management_id', '=', self.line_management_id.id)
            ])

            line_management_line_id.write({
                'mrp_remaining_qty': line_management_line_id.total_assigned_qty - cnt,
                'production_done_qty': cnt
            })

            # update line.management status and assign.desk.engineer.wizard.table production_complete_qty field
            cnt_eng_wise = self.search_count([('state', '=', 'done'),
                                              ('bom_id', '=', self.bom_id.id),
                                              ('engineer', '=', self.engineer.id),
                                              ('line_management_id', '=', self.line_management_id.id)
                                              ])

            wizard_line_ids = self.env['assign.desk.engineer.wizard.table'].search(
                [('line_management_id', '=', self.line_management_id.id)])

            for line_data in wizard_line_ids:
                if line_data.engineer.id == self.engineer.id:
                    line_data.write({
                        'production_complete_qty': cnt_eng_wise
                    })

        else:
            self.state = 'done'
            self.is_qc_failed = True
            # manufacture_id = self.env['mrp.production'].search([
            #     ('id', '=', self.manufacture_id.id),
            #     ('state', '=', 'done')
            # ])
            #
            # for line in self.engineer_line_ids:
            #     move_id = self.env['stock.move'].search([
            #         ('product_id', '=', line.product_id.id),
            #         ('raw_material_production_id', '=', manufacture_id.id)
            #     ])


    def action_cancel(self):

        wizard_line_ids = self.env['assign.desk.engineer.wizard.table'].search(
            [('line_management_id', '=', self.line_management_id.id)])
        for line_data in wizard_line_ids:
            if line_data.engineer.id == self.engineer.id:
                line_data.write({
                    'state': 'cancel'
                })
                cancel_cnt = self.env['assign.desk.engineer.wizard.table'].search_count([
                    ('line_management_id', '=', self.line_management_id.id),
                    ('state', '=', 'cancel')
                ])

                if len(wizard_line_ids.ids) == cancel_cnt:
                    self.line_management_id.state = 'cancel'

    @api.model
    def create(self, vals):
        res = super(EngineerProfile, self).create(vals)
        if vals.get('name', ('New')) == ('New'):
            val = self.env['ir.sequence'].next_by_code('engineer.profile') or _('New')
            res.name = val
        return res

    def unlink(self):
        engineer_role_ids = self.env['role.manage'].search([('role_select', '=', 'engineer')])
        if self.env.user.id in engineer_role_ids.users.ids:
            raise ValidationError("You Cannot delete any record. Contact with your Line Manager")
        return super().unlink()


class EngineerProfileLine(models.Model):
    _name = 'engineer.profile.line'
    _description = 'Engineer Profile Line Assign'

    engineer_id = fields.Many2one('engineer.profile', string='Engineer Profile')
    bom_id = fields.Many2one('mrp.bom', string="Product")
    product_id = fields.Many2one('product.product', string="Product")
    qty = fields.Integer(string="Quantity")
    qty_done = fields.Integer(string='Done Quantity')
    product_uom_id = fields.Many2one('uom.uom', string='UoM')
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')

    # is_component_replace = fields.Boolean(string='')

    @api.onchange('lot_ids')
    def _onchange_lot_ids(self):
        if self.lot_ids:
            self.qty_done = len(self.lot_ids.ids)

    def action_replace_component(self):
        context = {
            'default_engineer_id': self.engineer_id.id,
            'default_bom_id': self.bom_id.id,
            'default_product_id': self.product_id.id,
            'default_qty': self.qty,
            'default_qty_done': self.qty_done,
            'default_product_uom_id': self.product_uom_id.id,
            'default_lot_ids': self.lot_ids.ids,
        }

        return {
            'name': 'Replace Component',
            'type': 'ir.actions.act_window',
            'res_model': 'replace.component.wizard',
            'view_mode': 'form',
            'views': [],
            'target': 'new',
            'context': context,
            'domain': [],
        }
