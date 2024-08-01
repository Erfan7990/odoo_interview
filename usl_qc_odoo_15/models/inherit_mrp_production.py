from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpProductionInherit(models.Model):
    _inherit = 'mrp.production'

    overall_passed = fields.Integer(string='Overall Passed', compute='_compute_overall_passed', store=True)
    overall_failed = fields.Integer(string='Overall Failed', compute='_compute_overall_failed', store=True)
    qc_complete = fields.Boolean(string="QC Complete?", compute='_compute_qc_complete', default=False, store=True)
    is_assigned_by_line_manager = fields.Boolean('Assign By Line Manager', default=False)
    manufact_qc_ids = fields.One2many('manufact.qc.checking', 'manufacture_id', string='Manufacture QC Checking')
    engineer_id = fields.Many2one('engineer.profile', string='Engineer Id')
    line_management_id = fields.Many2one('line.management', string='Line Manager Id')
    desk_id = fields.Many2one('desk.setup.configuration', string='Desk')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')
    production_planning_id =  fields.Many2one('production.planning', string='Production Planning Id')

    # pre_qc_done = fields.Boolean(default=False)

    # qty_produced = fields.Float(compute='_get_produced_qty', string='Quantity Produced')
    #
    # @api.depends('overall_passed')
    # def _get_produced_qty(self):
    #     for production in self:
    #         production.qty_produced = production.overall_passed


    # def button_mark_done(self):
    #     # return super(MrpProductionInherit, self).button_mark_done()
    #     if self.is_assigned_by_line_manager:
    #         stock_moves = self.env['stock.move'].search([('raw_material_production_id', '=', self.id)])
    #         vals = stock_moves


    @api.depends('manufact_qc_ids.quantity_on_hand')
    def _compute_qc_complete(self):
        for record in self:
            qc_complete_values = record.manufact_qc_ids.mapped('quantity_on_hand')
            record.qc_complete = all(qty == 0 for qty in qc_complete_values)

    @api.depends('manufact_qc_ids.passed_qty')
    def _compute_overall_passed(self):
        for record in self:
            passed_qty_values = record.manufact_qc_ids.mapped('passed_qty')
            record.overall_passed = min(passed_qty_values) if passed_qty_values else 0
            # record.qty_producing = min(passed_qty_values) if passed_qty_values else 0


    # def button_mark_done(self):
    #     for production in self:
    #         if production.overall_passed == 0 and production.overall_failed == 0:
    #             raise ValidationError(_("QC is not complete. Cannot mark production as done."))
    #
    #         if production.qty_producing == 0:
    #             raise ValidationError(_("QC is not complete. Cannot mark production as done."))
    #
    #         qc_complete_values = production.manufact_qc_ids.mapped('quantity_on_hand')
    #         for data in qc_complete_values:
    #             if data > 0:
    #                 raise ValidationError(_("QC is not complete. Cannot mark production as done."))
    #
    #         if production.overall_passed == 0:
    #             raise ValidationError(_("Cannot Proceed, All the quantity has failed the Quality Check"))
    #
    #     return super(MrpProductionInherit, self).button_mark_done()

    # def button_mark_done(self):
    #
    #     pre_qc = self.env['incoming.material.qc'].search(
    #         [('manufacture_order', '=', self.name),('qc_type', '=', 'pre_mrp_qc')])
    #
    #     # val = any(line.hand_on_qty != 0 for line in pre_qc.iqc_line_id)
    #     # if any(line.hand_on_qty != 0 for line in pre_qc.iqc_line_id):
    #     #     raise ValidationError(_("Pre-QC is not complete. Cannot mark production as done."))
    #     if pre_qc.pre_mrp_state != 'done':
    #         raise ValidationError(_("Pre-QC is not complete. Cannot mark production as done."))
    #
    #     # for line in pre_qc.iqc_line_id:
    #     #     if line.hand_on_qty != 0:
    #     #         raise ValidationError(_("Pre-QC is not complete. Cannot mark production as done."))
    #         # if line.mrb_qty != 0:
    #         #     raise ValidationError(_("Some item has failed the Pre-QC process. Cannot mark production as done."))
    #
    #     if not pre_qc:
    #         raise ValidationError(_("Pre-QC is not complete. Cannot mark production as done."))
    #
    #     return super(MrpProductionInherit, self).button_mark_done()

    @api.depends('manufact_qc_ids.failed_qty')
    def _compute_overall_failed(self):
        for record in self:
            failed_qty_values = record.manufact_qc_ids.mapped('failed_qty')
            record.overall_failed = max(failed_qty_values) if failed_qty_values else 0

    # qc_fail_location_id = fields.Many2one(
    #     'stock.location',
    #     domain="[('is_qc_failed_item_location','=',True)]",
    #     string="QC Failed Item Location",
    #     default=lambda self: self._get_default_qc_fail_location_id(),
    #     readonly=True)
    #
    # def _get_default_qc_fail_location_id(self):
    #     return self.env['stock.location'].search([('is_qc_failed_item_location', '=', True)], limit=1)

    def manufacture_qc_button(self):
        for record in self:
            pre_qc_configs = self.env['pre.qc.config'].search([('line_id.active', '=', True)])
            for config in pre_qc_configs:
                for line in config.line_id:
                    if self.env['manufact.qc.checking'].search([
                        ('pre_qc_config_line_id', '=', line.id),
                        ('manufacture_id', '=', record.id)]).id == False:

                        record.env['manufact.qc.checking'].create({
                            'product_id': record.product_id.id,
                            'qty': record.product_qty,
                            'pre_qc_config_line_id': line.id,
                            'manufacture_id': record.id,
                        })

        return {
            'name': 'Manufacture QC Checking',
            'type': 'ir.actions.act_window',
            'res_model': 'manufact.qc.checking',
            'view_mode': 'tree,form',
            'target': 'current',
            # 'context': {
            #     'default_customer': self.allocate_for.id,
            #     'default_pa_ref': self.ref,
            # },
            'domain': [('manufacture_id', '=', self.id)],
        }

    # def action_open_wizard(self):
    #     # Set default values for the wizard
    #     default_values = {
    #         'default_manufacture_id': self.id,
    #         # Add other default values as needed
    #     }
    #
    #     # Open the wizard form view with default values in the context
    #     return {
    #         'name': 'Manufacturing Pre-QC',
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'pre.qc.wizard',
    #         'view_mode': 'form',
    #         # 'view_id': self.env.ref('view_pre_qc_wizard_form').id,
    #         'context': default_values,
    #         'target': 'new',
    #     }
