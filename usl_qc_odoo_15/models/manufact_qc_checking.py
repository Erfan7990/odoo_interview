from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ManufactureQC(models.Model):
    _name = 'manufact.qc.checking'
    _description = 'Manufacture QC Checking'
    _rec_name = 'id'


    product_id = fields.Many2one(
        'product.product',
        string='Product',
        # domain="[('id', 'in', manufacture_product_ids)]",
    )
    qty = fields.Integer(string='Quantity',readonly=True)
    inspection_basis = fields.Many2one('qc.inspection.basis', string='Inspection Basis')
    inspection_methods = fields.Many2one('qc.inspection.methods', string='Inspection Methods')
    use_equipment = fields.Many2one('qc.use.equipment', string='Use Equipment')
    inspection_quantity = fields.Integer(string='Inspection Quantity', default=1, readonly=True)
    inspection_form = fields.Many2one('qc.inspection.form', string='Inspection Form')
    exception_handling = fields.Text(string='Exception Handling')
    responsibility_units = fields.Many2one('qc.responsibility.units', string='Responsibility Units')
    customer_qc_line_ids = fields.One2many('customer.qc.checking.line', 'manufact_qc_id')
    qc_state = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ], string='Status')
    remarks = fields.Html(string="Remarks")
    manufacture_id = fields.Many2one(
        'mrp.production', string='Source'
    )
    # pre_qc_config_id = fields.Many2one(
    #     'pre.qc.config', string='Type'
    # )
    pre_qc_config_line_id = fields.Many2one(
        'pre.qc.config.line', string='Type'
    )
    # manufacture_product_ids = fields.Many2many(
    #     'product.product',
    #     string='Products from Manufacturing Order',
    #     # compute='_compute_product_ids',
    # )
    passed_qty = fields.Integer(string='Passed Quantity', compute='_compute_passed_failed_qty', store=True)
    failed_qty = fields.Integer(string='Failed Quantity', compute='_compute_passed_failed_qty', store=True)
    quantity_on_hand = fields.Integer(string='Quantity on Hand', compute='_compute_quantity_on_hand', store=True)

    failed_item_loc = fields.Many2one('stock.location', string="Transfer Location (QC Failed)", readonly=True, compute='_compute_failed_item_loc')

    @api.depends('qc_state', 'pre_qc_config_line_id')
    def _compute_failed_item_loc(self):
        for record in self:
            if record.qc_state == 'failed':
                res = record.pre_qc_config_line_id.failed_dest_loc
                record.failed_item_loc = res if res else False
            else:
                record.failed_item_loc = False

    @api.depends('customer_qc_line_ids.qc_state')
    def _compute_passed_failed_qty(self):
        for record in self:
            passed_qty = len(record.customer_qc_line_ids.filtered(lambda line: line.qc_state == 'passed'))
            failed_qty = len(record.customer_qc_line_ids.filtered(lambda line: line.qc_state == 'failed'))

            record.passed_qty = passed_qty
            record.failed_qty = failed_qty

    @api.depends('qty', 'passed_qty', 'failed_qty')
    def _compute_quantity_on_hand(self):
        for record in self:
            remaining_qty = record.qty - record.passed_qty - record.failed_qty
            record.quantity_on_hand = remaining_qty

    # @api.onchange('pre_qc_config_id', 'manufacture_id')
    # def _onchange_check_duplicate_entry(self):
    #     if self.pre_qc_config_id and self.manufacture_id:
    #         existing_entry = self.env['manufact.qc.checking'].search([
    #             ('manufacture_id', '=', self.manufacture_id.id),
    #             ('pre_qc_config_id', '=', self.pre_qc_config_id.id),
    #         ], limit=1)
    #
    #         if existing_entry:
    #             raise ValidationError(_("A QC entry with the same Type already exists for the selected product."))

    # @api.depends('manufacture_id')
    # def _compute_product_ids(self):
    #     for record in self:
    #         manufacture_product_ids = record.manufacture_id.move_raw_ids.mapped('product_id')
    #
    #         record.manufacture_product_ids = manufacture_product_ids.ids

    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     if self.product_id and self.manufacture_id:
    #         product_move = self.manufacture_id.move_raw_ids.filtered(
    #             lambda move: move.product_id == self.product_id)
    #
    #         self.qty = product_move.product_uom_qty if product_move else 0.0

    def action_add_product_in_line(self):
        if not self.product_id:
            raise UserError(_("Product is not selected. Please select a product."))

        # existing_entry = self.customer_qc_line_ids.filtered(
        #     lambda line: line.product_id == self.product_id and line.pre_manuf_qctype == self.pre_qc_config_id
        # )
        #
        # if existing_entry:
        #     raise ValidationError(_("A QC entry with the same Type already exists for the selected product."))

        qc_line = self.env['customer.qc.checking.line'].create({
            'product_id': self.product_id.id,
            'inspection_basis': self.inspection_basis.name,
            'inspection_methods': self.inspection_methods.name,
            'use_equipment': self.use_equipment.name,
            'inspection_quantity': self.inspection_quantity,
            'inspection_form': self.inspection_form.name,
            'exception_handling': self.exception_handling,
            'responsibility_units': self.responsibility_units.name,
            'manufact_qc_id': self.id,
            'qc_state': self.qc_state,
            # 'pre_manuf_qctype': self.pre_qc_config_id.id,
        })

        # Link the customer_qc_line record to the customer.qc.checking record
        self.write({'customer_qc_line_ids': [(4, qc_line.id)]})

        qc_done_count = len(self.env['customer.qc.checking.line'].search(
            [('product_id', '=', self.product_id.id),('manufact_qc_id','=',self.id)]))

        if self.qty < qc_done_count:
            raise ValidationError(_("Can not overwrite the Quantity"))


