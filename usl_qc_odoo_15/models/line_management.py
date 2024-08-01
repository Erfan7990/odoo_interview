from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class LineManagement(models.Model):
    _name = 'line.management'
    _description = 'Line Management'
    _rec_name = 'name'
    _order = 'id desc'

    name = fields.Char(readonly=True, default=lambda self: _('New'), string="Reference")
    source = fields.Char(string="Source")
    line_manager = fields.Many2one('res.users', string='Line Manager')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')
    date = fields.Date(string="Date", default=fields.Date.today())
    line_management_line_ids = fields.One2many('line.management.line', 'line_management_id', string='Desks')
    wizard_line_ids = fields.One2many('assign.desk.engineer.wizard.table', 'line_management_id',
                                      domain=[('state', '!=', 'assign_qc_fail')])
    new_wizard_line_ids = fields.One2many('assign.desk.engineer.wizard.table', 'line_management_id',
                                          domain=[('state', '=', 'assign_qc_fail')], related='wizard_line_ids')
    is_engineer_assign = fields.Boolean('Engineer Assigned ?', default=False)
    is_engineer_reassign = fields.Boolean('Engineer ReAssigned after QC Failed ?', default=False)
    state = fields.Selection([
        ('pending_approval', 'Pending'),
        ('in_progress', 'Assign In Progress'),
        ('complete', 'Assign Complete'),
        ('cancel', 'Cancelled'),
        ('qc_failed', 'QC Failed'),
    ], group_expand='_expand_groups', default='pending_approval', readonly=True)

    count_assigned = fields.Integer(compute='_compute_count_assigned',
                                    string='QC Count', store=False)
    count_mo = fields.Integer(compute='_compute_count_mo',
                              string='MO Count', store=False)
    planning_id = fields.Many2one('production.planning', string='Production Planning Id')
    src_location_id = fields.Many2one(
        'stock.location', "BoM Location",
    )
    dest_location_id = fields.Many2one(
        'stock.location', "Finished Good Location",
    )
    remarks = fields.Html(string="Comments")
    color = fields.Integer(string='Color', compute='_get_color')

    def _get_color(self):
        for rec in self:
            if rec.state == 'pending_approval':
                rec.color = 4
            if rec.state == 'in_progress':
                rec.color = 3
            if rec.state == 'complete':
                rec.color = 10
            if rec.state == 'cancel':
                rec.color = 1
            if rec.state == 'qc_failed':
                rec.color = 6

    @api.model
    def _expand_groups(self, states, domain, order):
        return ['pending_approval', 'in_progress', 'complete', 'cancel', 'qc_failed']

    @api.model
    def create(self, vals):
        res = super(LineManagement, self).create(vals)
        if vals.get('name', ('New')) == ('New'):
            val = self.env['ir.sequence'].next_by_code('line.management') or _('New')
            res.name = val
        return res

    def _compute_count_assigned(self):
        for record in self:
            data = self.env['assign.desk.engineer.wizard.table'].search_count(
                [('wizard_id.line_management_id', '=', self.id)])
            record.count_assigned = data

    def _compute_count_mo(self):
        for rec in self:
            line_manager_cnt = self.env['mrp.production'].search_count([('line_management_id', '=', self.id)])
            rec.count_mo = line_manager_cnt

    def pre_assign_history(self):
        tree_id = self.env.ref("usl_qc.pre_assign_desk_engineer_table_tree_view")

        return {
            'name': 'Planning History',
            'type': 'ir.actions.act_window',
            'res_model': 'assign.desk.engineer.wizard.table',
            'view_mode': 'tree',
            'views': [(tree_id.id, 'tree')],
            'target': 'current',
            'context': {},
            'domain': [
                ('wizard_id.line_management_id', '=', self.id),
                ('engineer_type', 'in', ['pre_assign', 'post_assign'])
            ],
        }

    def action_cancel(self):
        if self.state != 'cancel':
            self.state = 'cancel'

    def action_created_manufacture_order(self):
        return {
            'name': 'Manufacturing Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'tree',
            'views': [],
            'target': 'current',
            'context': {},
            'domain': [('line_management_id', '=', self.id)],
        }

    def pre_assign_desk_engineer(self):
        vals = self.line_management_line_ids
        bom_ids = vals.mapped('bom_id.id')

        if self.state == 'qc_failed':
            name = 'Reassign Engineer'
            form_id = self.env.ref('usl_qc.post_assign_desk_engineer_form_view')
            context = {
                'default_line_manager': self.line_manager.id,
                'default_assembly_line': self.assembly_line.id,
                'default_production_planning_id': self.planning_id.id,
                'default_line_management_id': self.id,
                'default_default_bom_ids': bom_ids,
                'default_src_location_id': self.src_location_id.id,
                'default_dest_location_id': self.dest_location_id.id,
                'default_engineer_type': 'assign_qc_fail',
            }
            domain = [('engineer_type', '=', 'assign_qc_fail')]
        else:
            name = 'Assign Engineer'
            form_id = self.env.ref("usl_qc.pre_assign_desk_engineer_form_view")
            context = {
                'default_line_manager': self.line_manager.id,
                'default_assembly_line': self.assembly_line.id,
                'default_production_planning_id': self.planning_id.id,
                'default_line_management_id': self.id,
                'default_default_bom_ids': bom_ids,
                'default_src_location_id': self.src_location_id.id,
                'default_dest_location_id': self.dest_location_id.id,
                'default_engineer_type': 'pre_assign',
            }
            domain = [('engineer_type', '=', 'pre_assign')]

        for line in vals:
            if line.remaining_qty == 0:
                bom_id = line.bom_id.id
                bom_ids.remove(bom_id)

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'assign.desk.engineer.wizard',
            'view_mode': 'form',
            'views': [(form_id.id, 'form')],
            'target': 'new',
            'context': context,
            'domain': domain,
        }

    def post_assign_desk_engineer(self):
        vals = self.line_management_line_ids
        bom_ids = vals.mapped('bom_id.id')
        form_id = self.env.ref("usl_qc.post_assign_desk_engineer_form_view")

        for line in vals:
            if line.remaining_qty == line.qty and line.remaining_qty > 0:
                bom_id = line.bom_id.id
                bom_ids.remove(bom_id)

        context = {
            'default_line_manager': self.line_manager.id,
            'default_assembly_line': self.assembly_line.id,
            'default_line_management_id': self.id,
            'default_production_planning_id': self.planning_id.id,
            'default_default_bom_ids': bom_ids,
            'default_src_location_id': self.src_location_id.id,
            'default_dest_location_id': self.dest_location_id.id,
            'default_engineer_type': 'post_assign',
        }
        return {
            'name': 'Reassign Engineer',
            'type': 'ir.actions.act_window',
            'res_model': 'assign.desk.engineer.wizard',
            'view_mode': 'form',
            'views': [(form_id.id, 'form')],
            'target': 'new',
            'context': context,
            'domain': [('engineer_type', '=', 'post_assign')],
        }


class LineManagementLine(models.Model):
    _name = 'line.management.line'
    _description = 'Line Management Line'

    line_management_id = fields.Many2one('line.management')
    bom_id = fields.Many2one('mrp.bom', string="Product")
    qty = fields.Integer(string="Qty")
    remaining_qty = fields.Integer(string="Remaining Assign Quantity")
    total_assigned_qty = fields.Integer(string="Total Assign Quantity")
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    mrp_remaining_qty = fields.Integer(string="Remaining MRP Quantity")
    production_done_qty = fields.Integer(string="Production Done Quantity")
    engineer = fields.Many2one('res.users', string='Engineer')
