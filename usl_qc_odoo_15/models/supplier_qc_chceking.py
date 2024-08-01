from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date


class SupplierQC(models.Model):
    _name = 'supplier.qc.checking'
    _description = 'Supplier Material QC Checking'
    _rec_name = 'im_qc_ref'

    def _get_last_seq(self):
        domain = []
        pre_qc_conf = self.env['pre.qc.config.line'].search([])
        val_ids = [record.id for record in pre_qc_conf[:-1]]  # Extracting IDs from vals
        domain = [('id', 'in', val_ids)]
        return domain

    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    vendor = fields.Many2one('res.partner', string='Supplier')
    qty = fields.Float(string='Inspection Quantity')
    inspection_basis = fields.Many2one('qc.inspection.basis', string='Inspection Basis')
    inspection_methods = fields.Many2one('qc.inspection.methods', string='Inspection Methods')
    use_equipment = fields.Many2one('qc.use.equipment', string='Use Equipment')
    # inspection_quantity = fields.Integer(string='Inspection Quantity', default=1, readonly=True)
    inspection_form = fields.Many2one('qc.inspection.form', string='Inspection Form')
    exception_handling = fields.Text(string='Exception Handling')
    responsibility_units = fields.Many2one('qc.responsibility.units', string='Responsibility Units')
    supplier_qc_line_ids = fields.One2many('customer.qc.checking.line', 'supplier_qc_id')
    qc_state = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ], string='Status', default='passed')
    date = fields.Date(string='QC Date', default=date.today(), readonly=True)
    mrb_choose = fields.Selection([
        ('batch_annealing', 'Batch Annealing'),
        ('special_mining', 'Special Mining'),
    ], string='Choose MRB')
    im_qc_ref = fields.Char(string='Reference')
    remarks = fields.Html(string="Remarks")
    im_qc_id = fields.Many2one('incoming.material.qc', string='Incoming Material ID')
    iqc_line_ids = fields.Many2one('incoming.material.qc.line', string='IQC line id', ondelete='cascade')
    purchase_order = fields.Many2one(
        'purchase.order',
        string='PO Number',
    )
    manufacture_order = fields.Many2one(
        'mrp.production',
        string='Manufacture Order',
    )
    fpo_order = fields.Many2one(
        'account.move',
        string='FPO Order',
    )
    passed_qty = fields.Integer(string="Passed Quantity")
    failed_qty = fields.Integer(string="Failed Quantity")
    is_bulk_button_clicked = fields.Boolean(string='Is Button Clicked', default=False)
    is_have_serial_number = fields.Boolean(string='Is Have Serial Number', default=False)
    is_single_qc = fields.Boolean(string='Is single qc', default=False)
    is_bulk_qc = fields.Boolean(string='Is Bulk qc', default=False)
    default_lot_ids = fields.Many2many('stock.production.lot', string='Lot/Serial Numbers')
    lot_ids = fields.Many2one('stock.production.lot', string='Lot/Serial Numbers',
                              domain="[('id', 'in', default_lot_ids)]")
    qc_stages = fields.Many2one('pre.qc.config.line', string="QC Name", domain=lambda self: self._get_last_seq())
    qc_type = fields.Selection([
        ('incoming_qc', 'Incoming Material QC (Purchased Goods)'),
        ('fpo_qc', 'Foreign Purchase QC'),
        ('pre_mrp_qc', 'Pre-MRP QC (Raw Materials)'),
        ('post_mrp_qc', 'Post-MRP QC (Finished Goods)'),
    ], string="QC Type")

    picking_ids = fields.Many2one('stock.picking', string='Stock Picking Id')

    line_manager = fields.Many2one('res.users', string='Line Manager')
    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    engineer = fields.Many2one('res.users', string='Engineer')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')

    @api.onchange('passed_qty')
    def _onchange_passed_qty(self):
        if self.qty and self.passed_qty:
            self.failed_qty = self.qty - self.passed_qty
            if self.failed_qty < 0:
                raise ValidationError('Invalid Entry')

    @api.onchange('failed_qty')
    def _onchange_failed_qty(self):
        if self.qty and self.failed_qty:
            self.passed_qty = self.qty - self.failed_qty
            if self.passed_qty < 0:
                raise ValidationError('Invalid Entry')

    def action_add_bulk_product_in_line(self):
        # current_sequence = self.qc_stages.sequence
        # next_stage = self.env['pre.qc.config.line'].search([('sequence', '>', current_sequence)], limit=1)
        self.is_bulk_button_clicked = True
        if self.qty > 1:
            if self.passed_qty == 0 and self.failed_qty == 0:
                raise ValidationError(_("Passed Quantity or Failed Quantity cannot be empty!"))

        if self.qc_type == 'post_mrp_qc':
            existing_qc_stage = self.env['customer.qc.checking.line'].search(
                [('im_qc_ref', '=', self.im_qc_ref), ('qc_stages', '=', self.qc_stages.id)])
            if existing_qc_stage:
                raise ValidationError(_("Entries with the same QC Type already exists!"))

        iqc_line_id = self.env['incoming.material.qc.line'].search(
            [('id', '=', self.iqc_line_ids.id), ('product', '=', self.product_id.id)])

        mrp = self.env['stock.move.line'].search([
            ('production_id', '=', self.manufacture_order.id),
            ('product_id', '=', self.product_id.id)
        ])

        # check that any lot_id exist in customer.qc.checking.line
        lot_id_exist = self.env['customer.qc.checking.line'].search([('supplier_qc_id', '=', self.id)])
        if self.qc_type == 'incoming_qc':
            lot_ids = iqc_line_id.lot_ids.ids
            # Check if any lot_id exists in customer.qc.checking.line
            if lot_id_exist.lot_ids.ids:
                lot_ids = [lot_id for lot_id in lot_ids if lot_id not in lot_id_exist.lot_ids.ids]
            else:
                lot_ids = lot_ids

        if self.qc_type == 'pre_mrp_qc':
            lot_ids = mrp.lot_id.ids
            if lot_id_exist.lot_ids.ids:
                lot_ids = [lot_id for lot_id in lot_ids if lot_id not in lot_id_exist.lot_ids.ids]
            else:
                lot_ids = lot_ids

        if self.qc_type == 'post_mrp_qc':
            lot_ids = ""

        if self.qc_type == 'fpo_qc':
            lot_ids = ""
        supplier_qc_lines = []
        for i in range(len(lot_ids) if len(lot_ids) > 0 else int(self.qty)):
            supplier_qc_line = self.env['customer.qc.checking.line'].create({
                'qc_stages': self.qc_stages.id,
                'product_id': self.product_id.id,
                'qty': 1,  # Quantity for each entry in bulk add
                'inspection_basis': self.inspection_basis.id,
                'inspection_methods': self.inspection_methods.id,
                'use_equipment': self.use_equipment.id,
                'inspection_form': self.inspection_form.id,
                'exception_handling': self.exception_handling,
                'responsibility_units': self.responsibility_units.id,
                'qc_state': 'passed',
                'lot_ids': lot_ids[i] if self.qc_type != 'post_mrp_qc' and i < len(lot_ids) else "",
                'im_qc_ref': self.im_qc_ref,
                'supplier_qc_id': self.id,
                'line_manager': self.line_manager.id,
                'desk': self.desk.id,
                'engineer': self.engineer.id,
            })
            supplier_qc_lines.append(supplier_qc_line)

        # Update the relation field supplier_qc_line_ids
        self.write({'supplier_qc_line_ids': [(4, line.id) for line in supplier_qc_lines]})

        im_qc_id = self.env['incoming.material.qc'].search([('seq', '=', self.im_qc_ref)])

        # if self.qc_type == 'post_mrp_qc' and next_stage:
        #     im_qc_id.write({
        #         'stage_id': next_stage.id
        #     })
        return {
            'name': _('IQC'),
            'type': 'ir.actions.act_window',
            'res_model': 'supplier.qc.checking',  # Model of the form to open
            'res_id': self.id,  # ID of the current record
            'view_mode': 'form',  # Display the form view
            'target': 'new',  # Open in a new window
        }

    def action_add_product_in_line(self):

        # if not self.inspection_basis:
        #     raise ValidationError('Select Your Inspection Basis')
        # if not self.inspection_methods:
        #     raise ValidationError('Select Your Inspection Methods')
        # if not self.use_equipment:
        #     raise ValidationError('Select Your Use Equipment')
        # if not self.inspection_form:
        #     raise ValidationError('Select Your Inspection Form')
        # if not self.exception_handling:
        #     raise ValidationError('Select Your Exception Handling')
        # if not self.responsibility_units:
        #     raise ValidationError('Select Your Responsibility Units')
        if self.is_have_serial_number == True and not self.lot_ids:
            raise ValidationError('Select Your Serial/Lot Id')
        if not self.qc_state:
            raise ValidationError('Select Your State')

        lot_id_exist = self.env['customer.qc.checking.line'].search([('supplier_qc_id', '=', self.id)])
        if self.lot_ids.id in lot_id_exist.lot_ids.ids:
            raise ValidationError('Same Serial/Lot already exist in line')

        supplier_qc_line = self.env['customer.qc.checking.line'].create({
            'qc_stages': self.qc_stages.id,
            'product_id': self.product_id.id,
            'qty': 1,  # Quantity for each entry in bulk add
            'inspection_basis': self.inspection_basis.id,
            'inspection_methods': self.inspection_methods.id,
            'use_equipment': self.use_equipment.id,
            'inspection_form': self.inspection_form.id,
            'exception_handling': self.exception_handling,
            'responsibility_units': self.responsibility_units.id,
            'qc_state': self.qc_state,
            'lot_ids': self.lot_ids.id if self.lot_ids else False,
            'im_qc_ref': self.im_qc_ref,
            'supplier_qc_id': self.id,
            'line_manager': self.line_manager.id,
            'desk': self.desk.id,
            'engineer': self.engineer.id,
            'assembly_line': self.assembly_line.id,
        })

        self.write({'supplier_qc_line_ids': [(4, supplier_qc_line.id)]})

        self.qc_state = False
        self.inspection_basis = False
        self.inspection_methods = False
        self.use_equipment = False
        self.inspection_form = False
        self.exception_handling = False
        self.responsibility_units = False
        self.lot_ids = False

        qc_checking_line_cnt = self.env['customer.qc.checking.line'].search_count([('supplier_qc_id', '=', self.id)])

        if self.qty < 0:
            raise ValidationError('You can not overwrite the Quantity')
        else:
            self.qty -= 1

        return {
            'name': _('IQC'),
            'type': 'ir.actions.act_window',
            'res_model': 'supplier.qc.checking',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def save_and_close(self):
        passed_count = self.env['customer.qc.checking.line'].search_count(
            [('supplier_qc_id', '=', self.id), ('qc_state', '=', 'passed')])
        failed_count = self.env['customer.qc.checking.line'].search_count(
            [('supplier_qc_id', '=', self.id), ('qc_state', '=', 'failed')])

        incoming_material_qc_line = self.env['incoming.material.qc.line'].search(
            [('product', '=', self.product_id.id), ('iqc_id.seq', '=', self.im_qc_ref),
             ('id', '=', self.iqc_line_ids.id)])
        hand_on_qty = 0
        if incoming_material_qc_line:
            if incoming_material_qc_line.iqc_id.qc_state == 'single_qc':
                hand_on_qty = incoming_material_qc_line.hand_on_qty - (passed_count + failed_count)

            if incoming_material_qc_line.iqc_id.qc_state == 'bulk_qc':
                if self.qty < incoming_material_qc_line.product_qty:
                    hand_on_qty = self.qty - (self.passed_qty + self.failed_qty)
                else:
                    if self.passed_qty != passed_count:
                        raise ValidationError("Invalid Entries")
                    if self.failed_qty != failed_count:
                        raise ValidationError("Invalid Entries")
                    hand_on_qty = self.qty - (passed_count + failed_count)

            incoming_material_qc_line.write({
                'passed_qty': passed_count,
                'mrb_qty': failed_count,
                'hand_on_qty': hand_on_qty if hand_on_qty >= 0 else 0,
            })

            if self.manufacture_order and self.qc_type == 'post_mrp_qc':
                # if failed_count == 0:
                #     current_qty = passed_count
                # else:

                current_qty = passed_count
                incoming_material_qc_line.write({
                    'current_qty': current_qty,
                })

                current_sequence = self.qc_stages.sequence
                next_stage = self.env['pre.qc.config.line'].search([('sequence', '>', current_sequence)], limit=1)
                im_qc_id = self.env['incoming.material.qc'].search([('seq', '=', self.im_qc_ref)])

                qc_line_data = self.env['customer.qc.checking.line'].search(
                    [('supplier_qc_id', '=', self.id)])

                # failed_data = self.env['customer.qc.checking.line'].search([('supplier_qc_id', '=', self.id),('qc_state', '=', 'failed')])
                # if failed_data:
                #     line_manage_vals = {
                #         'line_manager': failed_data.line_manager.id,
                #         'assembly_line': failed_data.assembly_line.id,
                #         'date': self.date,
                #         'source': self.im_qc_ref,
                #         'state': 'qc_failed',
                #         'line_management_line_ids': [(0, 0, {
                #             'bom_id': self.supplier_qc_line_ids.product_id.product_tmpl_id.bom_ids.id,
                #             'qty': self.supplier_qc_line_ids.qty,
                #             'remaining_qty': self.supplier_qc_line_ids.qty,
                #             'lot_ids': self.supplier_qc_line_ids.lot_ids.ids,
                #         })],
                #     }

                if not qc_line_data:
                    raise ValidationError("Line is Empty!")

                if next_stage:
                    im_qc_id.write({
                        'stage_id': next_stage.id,
                        'post_mrp_failed_qty': failed_count
                    })
