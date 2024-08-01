from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class CustomerQC(models.Model):
    _name = 'customer.qc.checking'
    _description = 'Customer QC Checking'
    _rec_name = 'id'

    # customer_order_qc = fields.Many2one('customer.order.req', string='Customer Order QC')

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        domain="[('id', 'in', available_product_ids)]",
        required=True
    )
    customer = fields.Many2one('res.partner', string='Customer', required=True, readonly=True)
    qty = fields.Integer(string='Quantity', readonly=True)
    inspection_basis = fields.Many2one('qc.inspection.basis', string='Inspection Basis')
    inspection_methods = fields.Many2one('qc.inspection.methods', string='Inspection Methods')
    use_equipment = fields.Many2one('qc.use.equipment', string='Use Equipment')
    inspection_quantity = fields.Integer(string='Inspection Quantity', default=1, readonly=True)
    inspection_form = fields.Many2one('qc.inspection.form', string='Inspection Form')
    exception_handling = fields.Text(string='Exception Handling')
    responsibility_units = fields.Many2one('qc.responsibility.units', string='Responsibility Units')
    customer_qc_line_ids = fields.One2many('customer.qc.checking.line', 'customer_qc_id')
    remarks = fields.Html(string="Remarks")

    available_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_product_ids',
        string='Available Products',
    )
    pa_ref = fields.Char(string="Reference")

    # @api.onchange('customer_order_qc')
    # def _onchange_product_line(self):
    #     if self.customer_order_qc:
    #         product_line = self.customer_order_qc.mapped('product_lines')
    #         self.product_line = [(6, 0, product_line.ids)]
    #         print(self.product_line)

    def action_add_product_in_line(self):
        if not self.product_id:
            raise UserError(_("Product is not selected. Please select a product."))

        # existing_entry = self.customer_qc_line_ids.filtered(
        #     lambda line: line.product_id == self.product_id
        # )
        #
        # if existing_entry:
        #     raise ValidationError(_("Product already added. Cannot add the same product again."))

        customer_qc_line = self.env['customer.qc.checking.line'].create({
            'product_id': self.product_id.id,
            'inspection_basis': self.inspection_basis.name,
            'inspection_methods': self.inspection_methods.name,
            'use_equipment': self.use_equipment.name,
            'inspection_quantity': self.inspection_quantity,
            'inspection_form': self.inspection_form.name,
            'exception_handling': self.exception_handling,
            'responsibility_units': self.responsibility_units.name,
            'customer_qc_id': self.id,
        })

        # Link the customer_qc_line record to the customer.qc.checking record
        self.write({'customer_qc_line_ids': [(4, customer_qc_line.id)]})
        qc_done_count = len(self.env['customer.qc.checking.line'].search(
            [('product_id', '=', self.product_id.id), ('customer_qc_id', '=', self.id)]))

        if self.qty >= qc_done_count:
            product_allocation_line = self.env['product.for.allocation'].search(
                [('product_id', '=', self.product_id.id), ('allocation_id.ref', '=', self.pa_ref)])
            product_allocation_line.write({
                'qc_done': qc_done_count,
            })
        else:
            raise ValidationError(_("Can not overwrite the Quantity"))

        # # Link the customer_qc_line record to the customer.qc.checking record
        # self.write({'customer_qc_line_ids': [(4, customer_qc_line.id)]})
        #
        # # Count only the new entries for the same product
        # qc_done_count = len(self.customer_qc_line_ids.filtered(
        #     lambda line: line.product_id == self.product_id
        # ))
        #
        # if self.qty >= qc_done_count:
        #     product_allocation_line = self.env['product.for.allocation'].search(
        #         [('product_id', '=', self.product_id.id)]
        #     )
        #     product_allocation_line.write({
        #         'qc_done': qc_done_count,
        #     })
        # else:
        #     raise ValidationError(_("Cannot overwrite the Quantity"))

    @api.depends('customer')
    def _compute_available_product_ids(self):
        if self.customer:

            products = self.env['product.allocation'].search([
                ('allocate_for', '=', self.customer.id),
            ]).mapped('product_details_lines.product_id')
            self.available_product_ids = products.ids
        else:
            self.available_product_ids = []

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            get_pa = self._context.get('default_pa_ref')
            allocation_record = self.env['product.allocation'].search([
                ('ref', '=', get_pa)
            ], limit=1)

            for pa_line in allocation_record.product_details_lines:
                if pa_line.product_id == self.product_id:
                    self.qty = pa_line.done_qty
            self.pa_ref = allocation_record.ref if allocation_record else False


        else:
            self.pa_ref = False
            self.qty = 0


class CustomerQCLine(models.Model):
    _name = 'customer.qc.checking.line'
    _description = 'Customer QC Checking'
    _order = 'im_qc_ref desc'

    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    vendor = fields.Many2one('res.partner', string='Supplier', readonly=True)
    qty = fields.Integer(string='Quantity')
    inspection_basis = fields.Many2one('qc.inspection.basis', string='Inspection Basis')
    inspection_methods = fields.Many2one('qc.inspection.methods', string='Inspection Methods')
    use_equipment =fields.Many2one('qc.use.equipment', string='Use Equipment')
    inspection_quantity = fields.Integer(string='Inspection Quantity')
    inspection_form = fields.Many2one('qc.inspection.form', string='Inspection Form')
    exception_handling = fields.Text(string='Exception Handling')
    responsibility_units = fields.Many2one('qc.responsibility.units', string='Responsibility Units')
    customer_qc_id = fields.Many2one('customer.qc.checking', string='Customer QC', ondelete='cascade')
    supplier_qc_id = fields.Many2one('supplier.qc.checking', string='Supplier QC', ondelete='cascade')
    manufact_qc_id = fields.Many2one('manufact.qc.checking', string='Manufacture QC', ondelete='cascade')
    # pre_manuf_qctype = fields.Many2one('pre.qc.config', string='Pre-MF QC Type', ondelete='cascade')
    qc_state = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ], string='Status')
    mrb_choose = fields.Selection([
        ('batch_annealing', 'Batch Annealing'),
        ('special_mining', 'Special Mining'),
    ], string='Choose MRB')
    im_qc_ref = fields.Char(string='Reference')
    lot_ids = fields.Many2one('stock.production.lot', string='Serial/Lot Number')
    is_clicked_on_action_cho_stock = fields.Boolean(string='Is Clicked', default=False)
    passed_picking_id = fields.Many2one('stock.picking', string='Passed Picking ids')
    failed_picking_id = fields.Many2one('stock.picking', string='Failed Picking ids')

    image_field = fields.Binary(string='Image')

    qc_stages = fields.Many2one('pre.qc.config.line', string="QC Name")

    line_manager = fields.Many2one('res.users', string='Line Manager')
    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    engineer = fields.Many2one('res.users', string='Engineer')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')

    #  compute='_compute_is_clicked_on_action_cho_stock'
    @api.onchange('image_field')
    def _onchange_image_field(self):
        print('*****')




    def action_button_visible(self):
        raise ValidationError("You already Completed your Transfer Process")
