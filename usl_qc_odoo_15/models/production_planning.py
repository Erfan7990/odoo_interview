from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ProductionPlanning(models.Model):
    _name = 'production.planning'
    _description = 'Production Planning'
    _order = 'id desc'

    name = fields.Char(readonly=True, default=lambda self: _('New'), string="Reference")
    date = fields.Date(string="Date", default=fields.Date.today())
    # source_doc = fields.Char(string="Source Document")
    bom_line = fields.One2many('production.planning.bom.line', 'production_planning_id', string="BOM")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id.id)
    production_planning_line_ids = fields.One2many('production.planning.line', 'production_planning_id',
                                                   string="Allocation Ids")
    product_manager = fields.Many2one('res.users', default=lambda self: self.env.user.id, string='Production Manager')
    remarks = fields.Html("Remarks")

    location_id = fields.Many2one(
        'stock.location', "BoM Location",
        check_company=True, required=True,
        default=lambda self: self._get_default_warehouse()
    )
    location_dest_id = fields.Many2one(
        'stock.location', "Finished Good Location",
        check_company=True, required=True,
        default=lambda self: self._get_default_warehouse()
    )
    mrp_order_id = fields.Many2one('mrp.production', string='Related Manufacturing Order', readonly=True, copy=False)
    mrp_count = fields.Integer(compute='_compute_mrp_count', string="MRP", readonly=True)
    picking_transfer_count = fields.Integer(compute='_compute_picking_transfer_count', string="Picking Transfer",
                                            readonly=True)
    finish_goods_count = fields.Integer(compute='_compute_finish_goods_count',
                              string='Finish Goods Count', store=False)

    count_assigned = fields.Integer(compute='_compute_count_assigned',
                              string='Finish Goods Count', store=False)
    color = fields.Integer(string='Color', compute='_get_color')

    def _get_color(self):
        for rec in self:
            if rec.state == 'draft':
                rec.color = 4
            if rec.state == 'slm':
                rec.color = 3
            if rec.state == 'cancel':
                rec.color = 1

    def _get_default_warehouse(self):
        warehouse_location = self.env['stock.warehouse'].search([('id', '=', self.env.user.property_warehouse_id.id)])
        return warehouse_location.lot_stock_id.id


    def _compute_count_assigned(self):
        assign_cnt = self.env['engineer.profile'].search_count([('production_planning_id', '=', self.id)])
        self.count_assigned = assign_cnt

    def _compute_finish_goods_count(self):
        production_cnt =self.env['mrp.production'].search_count([
            ('production_planning_id', '=', self.id),
            ('state', '=', 'done')
        ])
        self.finish_goods_count = production_cnt


    def _compute_mrp_count(self):
        for rec in self:
            domain = [("planning_no", "=", self.id)]
            # rec.loan_disbursement_count = self.env['loan.application.line'].sudo().search_count(
            #     [('loan_id', '=', rec.id)])
            rec.mrp_count = self.env["mrp.production"].search_count(domain)

    def _compute_picking_transfer_count(self):
        for rec in self:
            domain = [("planning_no", "=", self.id)]
            rec.picking_transfer_count = self.env["stock.picking"].search_count(domain)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('slm', 'Sent to Line Manager'),
        ('cancel', 'Cancelled'),
    ], group_expand='_expand_groups', string='state', default='draft', readonly=True, tracking=True)

    @api.model
    def _expand_groups(self, states, domain, order):
        return ['draft', 'slm', 'cancel']

    def state_cancel(self):
        self.state = 'cancel'

    def create_line_management_entries(self):
        line_management_vals = {}
        for planning in self:
            for line in planning.production_planning_line_ids:
                product_id = self.env['product.product'].search(
                    [('product_tmpl_id', '=', line.bom_id.product_tmpl_id.id)])

                if product_id.tracking == 'serial' and not line.lot_ids:
                    raise ValidationError(f"You must assign serial/lot no. for {line.bom_id.product_tmpl_id.name}")

                key = line.line_manager.id
                if key not in line_management_vals:
                    line_management_vals[key] = {
                        'line_manager': line.line_manager.id,
                        'assembly_line': line.assembly_line.id,
                        'date': planning.date,
                        'planning_id': planning.id,
                        'state': 'pending_approval',
                        'source': planning.name,
                        'src_location_id': planning.location_id.id,
                        'dest_location_id': planning.location_dest_id.id,
                        'line_management_line_ids': [(0, 0, {
                            'bom_id': line.bom_id.id,
                            'qty': line.qty,
                            'remaining_qty': line.qty,
                            'lot_ids': [(6, 0, line.lot_ids.ids)],
                        })],
                    }
                else:
                    line_management_vals[key]['assembly_line'] = line.assembly_line.id
                    line_management_vals[key]['line_management_line_ids'].append((0, 0, {
                        'bom_id': line.bom_id.id,
                        'qty': line.qty,
                        'remaining_qty': line.qty,
                        'lot_ids': [(6, 0, line.lot_ids.ids)],
                    }))

        line_management = self.env['line.management']
        for vals in line_management_vals.values():
            line_management |= line_management.create(vals)

        return line_management

    def button_reset(self):
        self.state = 'draft'

    def state_submit_approval(self):
        self.ensure_one()
        self.state = 'slm'
        for planning in self:

            for bom_line in planning.bom_line:
                product = bom_line.product_id
                if product and product.type == 'product':
                    quantity_available = product.with_context({'location': planning.location_id.id}).qty_available
                    if quantity_available < bom_line.product_qty:
                        raise ValidationError("Product %s is not available in sufficient quantity at location %s" %
                                              (product.display_name, planning.location_id.name))
        line_management = self.create_line_management_entries()

        return True

    def action_finish_goods(self):
        return {
            'name': 'Finished Goods',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'tree',
            'views': [],
            'target': 'current',
            'context': {},
            'domain': [('production_planning_id', '=', self.id),('state', '=', 'done')],
        }

    def assign_planning_history(self):
        return {
            'name': 'Production Progress',
            'type': 'ir.actions.act_window',
            'res_model': 'engineer.profile',
            'view_mode': 'tree,kanban',
            'views': [],
            'target': 'current',
            'context': {},
            'domain': [('production_planning_id', '=', self.id)],
        }
    @api.model
    def create(self, vals):
        datas = super(ProductionPlanning, self).create(vals)
        if vals.get('name', ('New')) == ('New'):
            val = self.env['ir.sequence'].next_by_code('production.planning') or _('New')
            datas.name = val

        bom_line_value = []
        for line in datas.production_planning_line_ids:
            for bom_line in line.bom_id.bom_line_ids:
                if line.qty > 0:
                    product_qty = line.qty * bom_line.product_qty
                else:
                    product_qty = bom_line.product_qty
                bom_line_value.append({
                    'bom_id': line.bom_id.id,
                    'production_planning_id': line.production_planning_id.id,
                    'production_planning_line_id': line.id,
                    'product_id': bom_line.product_id.id,
                    'product_qty': product_qty,
                    'product_uom_id': bom_line.product_id.uom_id.id,
                    'company_id': line.production_planning_id.company_id.id,
                })

            datas.bom_line.create(bom_line_value)
        return datas

    def write(self, vals):
        super(ProductionPlanning, self).write(vals)
        if vals.get('production_planning_line_ids', False):
            bom_line_value = []
            for line in vals.get('production_planning_line_ids'):
                if line[0] == 0:
                    if 'bom_id' in line[2].keys() and line[2]['bom_id']:
                        bom_id = line[2].get('bom_id')
                        production_planning_line_ids = self.env['production.planning.line'].search([
                            ('bom_id', '=', bom_id),
                            ('assembly_line', '=', line[2].get('assembly_line')),
                            ('id', 'in', self.production_planning_line_ids.ids)
                        ])
                        bom_line_ids = self.env['mrp.bom.line'].search([('bom_id', '=', bom_id)])
                        for bom_line in bom_line_ids:
                            if 'qty' in line[2].keys() and line[2]['qty'] > 0:
                                product_qty = line[2].get('qty') * bom_line.product_qty
                            else:
                                product_qty = bom_line.product_qty
                            bom_line_value.append({
                                'bom_id': bom_id,
                                'production_planning_id': self.id,
                                'production_planning_line_id': production_planning_line_ids.id,
                                'product_id': bom_line.product_id.id,
                                'product_qty': product_qty,
                                'product_uom_id': bom_line.product_id.uom_id.id,
                                'company_id': self.company_id.id,
                            })
                        self.bom_line.create(bom_line_value)
                if line[0] == 1:
                    if line[2] != False:
                        production_planning_line_ids = self.env['production.planning.line'].search([('id', '=', line[1])])
                        if 'assembly_line' in line[2].keys() and line[2]['assembly_line']:
                            production_planning_line_ids.write({
                                'assembly_line': line[2].get('assembly_line')
                            })
                        if 'line_manager' in line[2].keys() and line[2]['line_manager']:
                            production_planning_line_ids.write({
                                'line_manager': line[2].get('line_manager')
                            })
                        if 'note' in line[2].keys() and line[2]['note']:
                            production_planning_line_ids.write({
                                'note': line[2].get('note')
                            })

                        production_planning_bom_line_ids = self.env['production.planning.bom.line'].search([
                                    ('production_planning_id', '=', self.id),
                                    ('production_planning_line_id', '=', line[1]),
                                    ('bom_id', '=', production_planning_line_ids.bom_id.id),
                                ])

                        for pp_bom_line in production_planning_bom_line_ids:
                            mrp_bom_line = self.env['mrp.bom.line'].search([
                                ('bom_id', '=', pp_bom_line.bom_id.id),
                                ('product_id', '=', pp_bom_line.product_id.id)
                            ])
                            if 'qty' in line[2].keys() and line[2]['qty'] > 0:

                                pp_bom_line.write({
                                    'product_qty': line[2].get('qty') * mrp_bom_line.product_qty
                                })
                            else:
                                pp_bom_line.write({
                                    'product_qty': pp_bom_line.product_qty
                                })


    def unlink(self):
        return super(ProductionPlanning, self).unlink()

class ProductionPlanningLine(models.Model):
    _name = 'production.planning.line'
    _description = 'Production Planning Line'

    def _get_line_manager(self):
        data = self.env['role.manage'].search([('role_select', '=', 'line_manager')])
        return data.users.ids

    bom_id = fields.Many2one('mrp.bom', string="Product")
    # engineer = fields.Many2one('res.users', string="Engineer")
    # eng_location = fields.Many2one('stock.location', string="Engineer Location", compute='_get_engineer_location')
    qty = fields.Integer(string="Quantity", default=1, required=True)
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    is_product_have_serial = fields.Boolean(string='Is Product Have Serial Number', default=False)
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line', required=True)
    line_manager = fields.Many2one('res.users', string='Line Manager', required=True,
                                   domain=lambda self: [('id', 'in', self._get_line_manager())])
    note = fields.Text(string="Note")
    qty_done = fields.Integer(string='Done Quantity')
    production_planning_id = fields.Many2one('production.planning', string='Engineer Location', ondelete='cascade')

    # @api.onchange('assembly_line')
    # def _onchange_assembly_line(self):
    #     exist_assembly_line = self.search([('assembly_line','=',self.assembly_line.id), ('production_planning_id', '=', self.production_planning_id.id.origin)])
    #     if exist_assembly_line:
    #         raise ValidationError('Your selected Assembly Line Already exist.')


    def action_assign_serial_number(self):
        product_id = self.env['product.product'].search([('product_tmpl_id', '=', self.bom_id.product_tmpl_id.id)])

        if product_id.tracking != 'serial':
            raise ValidationError(f"This {product_id.name} doesn't have serial/lot permission")

        exist_pp_line_id = self.env['production.planning.serial'].search(
            [('production_planning_line_id', '=', self.id)])



        if exist_pp_line_id:

            if exist_pp_line_id.qty != self.qty:
                exist_pp_line_id.write({
                    'qty': self.qty,
                    'is_clicked_button': False
                })

            context = {'default_id': exist_pp_line_id.id}
            return {
                'type': 'ir.actions.act_window',
                'name': 'Assign Product Serial Number',
                'res_model': 'production.planning.serial',
                'res_id': exist_pp_line_id.id,
                'view_mode': 'form',
                'target': 'new',
                'context': context,
            }
        else:
            context = {
                'default_product_id': product_id.id,
                'default_bom_id': self.bom_id.id,
                'default_qty': self.qty,
                'default_production_planning_line_id': self.id,
                'default_production_planning_id': self.production_planning_id.id,
            }
            return {
                'name': 'Assign Product Serial Number',
                'res_model': 'production.planning.serial',
                'view_mode': 'form',
                'context': context,
                'target': 'new',
                'type': 'ir.actions.act_window',
                'domain': [],
            }

    def unlink(self):
        production_planning_bom_line_ids = self.env['production.planning.bom.line'].search([
            ('production_planning_id', '=', self.production_planning_id.id),
            ('production_planning_line_id', '=', self.id),
            ('bom_id', '=', self.bom_id.id),
        ])
        for line in production_planning_bom_line_ids:
            line.unlink()
        return super(ProductionPlanningLine, self).unlink()

class BomLine(models.Model):
    _name = 'production.planning.bom.line'

    bom_id = fields.Many2one('mrp.bom', string="Product")
    production_planning_id = fields.Many2one('production.planning', string="Production Planning Lines", ondelete='cascade')
    production_planning_line_id = fields.Many2one('production.planning.line', string="Production Lines", ondelete='cascade')

    product_id = fields.Many2one('product.product', 'Component', required=True, check_company=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id',
                                      store=True, index=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id.id)
    product_qty = fields.Float(
        'Quantity', default=1.0,
        digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one(
        'uom.uom', 'Product Unit of Measure',
        default=lambda self: self._get_default_product_uom_id(),
        required=True,
        help="Unit of Measure (Unit of Measure) is the unit of measurement for the inventory control",
        domain="[('category_id', '=', product_uom_category_id)]")

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')


class MrpProductionCustom(models.Model):
    _inherit = 'mrp.production'

    planning_no = fields.Char(string='Planning No', help='Description of the custom field.')


class PickingTransferCustom(models.Model):
    _inherit = 'stock.picking'

    planning_no = fields.Char(string='Planning No', help='Description of the custom field.')
