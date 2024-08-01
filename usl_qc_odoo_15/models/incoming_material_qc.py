# -*- coding: utf-8 -*-
import base64
import io
import os
import xlrd
import logging
import tempfile
import binascii
from odoo import api, fields, models, _, exceptions
from datetime import datetime, date
from odoo.osv import expression
from odoo.tools.convert import xml_import
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT, BytesIO, xlsxwriter, unquote, convert
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')


class IncomingMaterialQC(models.Model):
    _name = 'incoming.material.qc'
    _description = "Incoming Material QC"
    _rec_name = 'seq'
    _order = 'id desc'

    def _get_purchase_order_domain(self):
        domain = []
        stock_picking_id = self.env['stock.picking'].search(
            [('state', '=', 'done'), ('purchase_id', '!=', False)]
        )
        l = [i.purchase_id.id for i in stock_picking_id]
        existing_po_ids = self.search([('purchase_order', 'in', l)]).purchase_order
        # self.incoming_qc_id = incoming_qc_id.ids
        if stock_picking_id:
            domain = [('id', '=', l), ('id', 'not in', existing_po_ids.ids)]
        return domain




    # def _get_manufacture_order_domain(self):
    #     global manufacture_orders_not_in_qc
    #     domain = []
    #     pre_manufacture_orders = self.env['mrp.production'].search([('state', '=', 'confirmed')])
    #     post_manufacture_orders = self.env['mrp.production'].search([('state', '=', 'done')])
    #     if pre_manufacture_orders:
    #         qc_line = self.search([('manufacture_order.id', 'in', pre_manufacture_orders.ids)])
    #         pre_manufacture_orders = pre_manufacture_orders - qc_line.mapped('manufacture_order')
    #         domain = [('id', 'in', pre_manufacture_orders.ids)]
    #
    #     if post_manufacture_orders:
    #         qc_line = self.search([('manufacture_order.id', 'in', post_manufacture_orders.ids)])
    #         post_manufacture_orders = post_manufacture_orders - qc_line.mapped('manufacture_order')
    #
    #     # Create the final domain
    #         domain = [('id', 'in', post_manufacture_orders.ids)]
    #
    #     return domain

    seq = fields.Char(string='Reference', readonly=True)
    purchase_order = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        # domain=[('state', '=', 'purchase'), ('picking_ids', '!=', False)]
        domain=lambda self: self._get_purchase_order_domain()
    )
    manufacture_order = fields.Many2one(
        'mrp.production',
        string='Manufacture Order',
        domain=[],
    )
    fpo_order = fields.Many2one(
        'account.move',
        string='FPO Order',
        domain=[]
    )
    is_mandatory_po = fields.Boolean(string='Is Po Created', default=False)
    is_optional_po = fields.Boolean(string='Is Po Created', default=False)
    vendor = fields.Many2one('res.partner', string='Supplier')
    qc_state = fields.Selection([
        ('single_qc', 'Single QC'),
        ('bulk_qc', 'Bulk QC'),
    ], string='QC Choose', default='bulk_qc')
    iqc_line_id = fields.One2many('incoming.material.qc.line', 'iqc_id')
    user_id = fields.Many2one('res.partner', string='User', default=lambda self: self.env.user.partner_id.id,
                              readonly=True)
    qc_type = fields.Selection([
        ('incoming_qc', 'Incoming Material QC (Purchased Goods)'),
        ('fpo_qc', 'Foreign Purchase QC'),
        ('pre_mrp_qc', 'Pre-MRP QC (Raw Materials)'),
        ('post_mrp_qc', 'Post-MRP QC (Finished Goods)'),
    ], string="QC Type")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('cancel', 'Cancelled'),

    ], string='Type', default='draft', readonly=True)

    excel_state = fields.Selection([
        ('draft', 'Draft'),
        ('imported', 'Imported'),
    ], default='draft', store=False, string='Excel Import State')

    pre_mrp_state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('done', 'Done'),

    ], string='Type', default='in_progress', readonly=True)

    attachment_ids = fields.Many2many('ir.attachment', string='Upload Execl File', required=True, store=True,
                                      help='Upload Your QC Execl Document.')

    picking_id = fields.Many2one('stock.picking', string='Stock Picking Id')

    incoming_material_qc_created = fields.Boolean(string='incoming material qc created', default=False)
    qc_count = fields.Integer(compute='_compute_qc_count',
                              string='QC Count', store=False)
    count_transfer = fields.Integer(compute='_compute_count_transfer',
                                    string='Transfer', store=False)

    passed_location = fields.Many2one(
        'stock.location',
        string="Passed Stock Location",
    )

    post_mrp_failed_qty = fields.Float(string='Post Mrp Failed Qty')
    #
    # @api.depends('attachment_ids')
    # def _test_func(self):
    #     print("worked")
    #     self.test_field = None

    failed_location = fields.Many2one(
        'stock.location',
        string="MRB Stock Location",
    )
    is_clicked_on_download_execl = fields.Boolean(default=False, string='Is Clicked On Download Execl')
    passed_qc_responsible_person = fields.Many2one('res.users', string='Responsible Person (Passed)')
    failed_qc_responsible_person = fields.Many2one('res.users', string='Responsible Person (MRB)')
    datas = fields.Binary('File', readonly=True)
    datas_fname = fields.Char('Filename', readonly=True)

    stage_id = fields.Many2one('pre.qc.config.line', string='Stage', index=True, tracking=True,
                               default=lambda self: self._get_default_stage())

    product_id = fields.Many2one('product.product', string="Product")
    product_qty = fields.Float(string="Quantity")
    can_produce_qty = fields.Float(string="Produceable Quantity")
    is_clicked_post_manufact_confirm = fields.Boolean(default=False)

    line_manager = fields.Many2one('res.users', string='Line Manager')
    desk = fields.Many2one('desk.setup.configuration', string='Desk')
    engineer = fields.Many2one('res.users', string='Engineer')
    assembly_line = fields.Many2one('mrp.workcenter', string='Assembly Line')

    def action_resend_item(self):

        if self.iqc_line_id.current_qty != 0:
            raise ValidationError('Only an unsuccessful QC can Send To Line Manager')

        form_id = self.env.ref("usl_qc.failed_item_resend_form_view")
        line = self.iqc_line_id
        lot_ids = line.mapped('lot_ids')
        product_id = line.mapped('product')
        context = {
            'default_product_id': product_id.id,
            'default_lot_ids': lot_ids.id,
            'default_im_qc_id': self.id,
        }
        return {
            'name': 'Resend To Line Manager',
            'type': 'ir.actions.act_window',
            'res_model': 'failed.item.resend.wizard',
            'view_mode': 'form',
            'views': [(form_id.id, 'form')],
            'target': 'new',
            'context': context,
            'domain': [],
        }

    def reassign_qc_failed_items(self):
        pass

    def action_done(self):
        if self.qc_type == 'pre_mrp_qc':
            if any(line.hand_on_qty != 0 for line in self.iqc_line_id):
                raise UserError("Pre-MRP QC is not Complete!")

        last_sequence = self.env['pre.qc.config.line'].search(
            [('pre_qc_config_id', '=', self.stage_id.pre_qc_config_id.id)],
            order='sequence desc',
            limit=1
        )

        if self.qc_type == 'post_mrp_qc' and self.stage_id.sequence != last_sequence.sequence:
            raise UserError(
                "Post-MRP QC is not Complete!")
        elif self.qc_type == 'post_mrp_qc' and self.stage_id.sequence == last_sequence.sequence:
            self.is_clicked_post_manufact_confirm = True

            val = self.is_clicked_post_manufact_confirm

        global failed_move_data, source_location, failed_stock_picking
        if self.qc_type == 'pre_mrp_qc':
            mrp_bom_data = self.env['mrp.bom'].search([('id', '=', self.manufacture_order.bom_id.id)])
            val = []
            for line in mrp_bom_data.bom_line_ids:
                product = line.product_id.id
                qty = line.product_qty
                for iqc_line in self.iqc_line_id:
                    if product == iqc_line.product.id:
                        val.append(iqc_line.passed_qty // qty)
            self.can_produce_qty = min(val)
            self.manufacture_order.qty_producing = self.can_produce_qty
            mrp_production_instance = self.env['mrp.production'].browse(self.manufacture_order.id)
            mrp_production_instance._set_qty_producing()

            for line in self.iqc_line_id:
                self.pre_mrp_state = 'done'
                # self.is_clicked_manufact_confirm = True

                supplier_id = self.env['supplier.qc.checking'].search([('iqc_line_ids', '=', line.id)])
                qc_ids = self.env['customer.qc.checking.line'].search([('supplier_qc_id', '=', supplier_id.id)])

                for val in qc_ids:
                    state = val.qc_state
                    stock_move_line = self.env['stock.move.line'].search([('lot_id', '=', val.lot_ids.id)])
                    stock_move_line.write({
                        'qc_state': state,
                    })

                    stock_move = self.env['stock.move'].search([('move_line_ids', 'in', stock_move_line.ids)])
                    stock_move.write({
                        'is_from_qc': True,
                    })

        for rec in self:
            if rec.post_mrp_failed_qty != 0 or self.product_qty != self.can_produce_qty:
                source_location = rec.manufacture_order.location_src_id
                failed_picking_data = rec._transfer_picking_data(rec.failed_qc_responsible_person, source_location,
                                                                 rec.failed_location)
                failed_stock_picking = self.env['stock.picking'].create(failed_picking_data)

                for line in rec.iqc_line_id:
                    iqc_line_ids = self.env['supplier.qc.checking'].search(
                        [('iqc_line_ids', '=', line.id), ('product_id', '=', line.product.id)])
                    customer_qc_line_ids = self.env['customer.qc.checking.line'].search(
                        [('supplier_qc_id.id', 'in', iqc_line_ids.ids)])

                    passed_qty_by_product = {}
                    failed_qty_by_product = {}

                    for customer_qc_line_id in customer_qc_line_ids:
                        product = customer_qc_line_id.product_id
                        qty = abs(customer_qc_line_id.qty)
                        if customer_qc_line_id.qc_state == 'passed':
                            passed_qty_by_product[product] = passed_qty_by_product.get(product, 0) + qty
                        if customer_qc_line_id.qc_state == 'failed':
                            failed_qty_by_product[product] = failed_qty_by_product.get(product, 0) + qty

                    if failed_qty_by_product:
                        for product, failed_qty in failed_qty_by_product.items():
                            failed_move_data = rec._transfer_picking_move_data(line, source_location,
                                                                               rec.failed_location,
                                                                               failed_stock_picking.id, failed_qty)

                        move = self.env['stock.move'].create(failed_move_data)

                    customer_qc_line_ids.write({
                        'failed_picking_id': failed_stock_picking.id
                    })

                pickings = self.env['stock.picking'].search([('origin', '=', self.seq)])

                action = self.env.ref('stock.action_picking_tree_all').read()[0]
                action['domain'] = [('id', 'in', pickings.ids)]

                return action

    def _get_default_stage(self):
        # Find the first stage in usl.stage.model and set it as the default
        first_stage = self.env['pre.qc.config.line'].search([], order='sequence', limit=1)
        return first_stage.id if first_stage else False

    @api.onchange('qc_type')
    def _onchange_qc_type(self):
        domain = []
        pre_manufacture_orders = self.env['mrp.production'].search([('state', '=', 'confirmed')])
        post_manufacture_orders = self.env['mrp.production'].search([('state', '=', 'done')])
        if pre_manufacture_orders and self.qc_type == 'pre_mrp_qc':
            qc_line = self.search(
                [('manufacture_order.id', 'in', pre_manufacture_orders.ids), ('qc_type', '=', 'pre_mrp_qc')])
            pre_manufacture_orders = pre_manufacture_orders - qc_line.mapped('manufacture_order')
            domain = [('id', 'in', pre_manufacture_orders.ids)]
            return {'domain': {'manufacture_order': domain}}
        if post_manufacture_orders and self.qc_type == 'post_mrp_qc':
            self.qc_state = 'single_qc'
            qc_line = self.search(
                [('manufacture_order.id', 'in', post_manufacture_orders.ids), ('qc_type', '=', 'post_mrp_qc')])
            post_manufacture_orders = post_manufacture_orders - qc_line.mapped('manufacture_order')
            domain = [('id', 'in', post_manufacture_orders.ids)]
            return {'domain': {'manufacture_order': domain}}
        if self.qc_type == 'fpo_qc':
            # str(tuple(other_expense_account.bp_account_id.ids)).replace(',)', ')')
            landed_cost_ids = self.env['stock.landed.cost'].search([('state', '=', 'done')])
            fpo_query = """
                select id from account_move where move_type='in_invoice' 
                and state='posted' and invoice_origin like 'FPO%' and name like 'CINV%' and id in {}
                """.format(str(tuple(landed_cost_ids.vendor_bill_id.ids)).replace(',)', ',)'))
            self._cr.execute(fpo_query)
            result = self._cr.fetchall()
            l = [data[0] for data in result]
            domain = [('id', 'in', l)]
            return {'domain': {'fpo_order': domain}}



    def _compute_qc_count(self):
        qc_count = 0
        for record in self:
            if self.qc_type == 'incoming_qc':
                qc_count = self.env['customer.qc.checking.line'].search_count([
                    ('supplier_qc_id.purchase_order', '=', self.purchase_order.id)
                ])
            if self.qc_type == 'pre_mrp_qc':
                qc_count = self.env['customer.qc.checking.line'].search_count([
                    ('supplier_qc_id.manufacture_order', '=', self.manufacture_order.id),
                    ('supplier_qc_id.qc_type', '=', self.qc_type),
                ])
            if self.qc_type == 'post_mrp_qc':
                qc_count = self.env['customer.qc.checking.line'].search_count([
                    ('supplier_qc_id.manufacture_order', '=', self.manufacture_order.id),
                    ('supplier_qc_id.qc_type', '=', self.qc_type),

                ])
            if self.qc_type == 'fpo_qc':
                qc_count = self.env['customer.qc.checking.line']
            record.qc_count = qc_count

    def _compute_count_transfer(self):
        for rec in self:
            transfer_count = self.env['stock.picking'].search_count([('origin', '=', rec.seq)])

            rec.count_transfer = transfer_count

    def action_iqc_qc(self):
        domain = []
        tree_id = self.env.ref("usl_qc.customer_qc_checking_line_tree_view")
        form_id = self.env.ref("usl_qc.customer_qc_checking_line_form_view")

        if self.qc_type == 'incoming_qc':
            domain = [('supplier_qc_id.purchase_order', '=', self.purchase_order.id)]
        if self.qc_type == 'pre_mrp_qc':
            domain = [('supplier_qc_id.manufacture_order', '=', self.manufacture_order.id),
                      ('supplier_qc_id.qc_type', '=', self.qc_type), ]
        if self.qc_type == 'post_mrp_qc':
            domain = [('supplier_qc_id.manufacture_order', '=', self.manufacture_order.id),
                      ('supplier_qc_id.qc_type', '=', self.qc_type), ]

        return {
            'name': 'Material QC',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.qc.checking.line',
            'view_mode': 'tree,form',
            'views': [(tree_id.id, 'tree'), (form_id.id, 'form')],
            'target': 'current',
            'context': {'search_default_qc_state': 1},
            'domain': domain,
        }

    def print_serial_product(self, worksheet, serial_products, columns, workbook):
        wbf, _ = self.add_workbook_format(workbook)
        options = ['passed', 'failed']
        inspection_basis = {basis.id: basis.name for basis in self.env['qc.inspection.basis'].search([])}
        inspection_method = {method.id: method.name for method in self.env['qc.inspection.methods'].search([])}
        use_equipment = {equipment.id: equipment.name for equipment in self.env['qc.use.equipment'].search([])}
        inspection_form = {form.id: form.name for form in self.env['qc.inspection.form'].search([])}
        exception_handling = ""
        responsibilities_unit = {unit.id: unit.name for unit in self.env['qc.responsibility.units'].search([])}

        col = 0
        row = 1
        for column in columns:
            column_name = column[0]
            column_width = column[1]
            worksheet.set_column(col, col, column_width)
            worksheet.write(row - 1, col, column_name, wbf['header_orange'])
            col += 1

        for item in serial_products:
            for data in item.lot_ids:
                col = 0
                # worksheet.merge_range(row, col, rowspan, col, item.product.name, wbf['data_doc'])
                worksheet.write(row, col, item.product.name)
                col += 1
                worksheet.write(row, col, data.name)
                col += 1
                worksheet.write(row, col, 1)
                col += 1
                worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                               'source': list(inspection_basis.values())})
                col += 1
                worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                               'source': list(inspection_method.values())})
                col += 1
                worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                               'source': list(use_equipment.values())})
                col += 1
                worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                               'source': list(inspection_form.values())})
                col += 1
                worksheet.write(row, col, exception_handling)
                col += 1
                worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                               'source': list(responsibilities_unit.values())})
                col += 1
                worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                               'source': options})
                worksheet.write(row, col, "passed")
                col += 1
                row += 1
            row += 1
            # worksheet.write(row, col, item[4])
            # col += 1
            # worksheet.write(row, col, item[5])
            # col += 1

    def print_non_serial_product(self, worksheet, non_serial_products, columns, workbook):
        wbf, _ = self.add_workbook_format(workbook)
        inspection_basis = {basis.id: basis.name for basis in self.env['qc.inspection.basis'].search([])}
        inspection_method = {method.id: method.name for method in self.env['qc.inspection.methods'].search([])}
        use_equipment = {equipment.id: equipment.name for equipment in self.env['qc.use.equipment'].search([])}
        inspection_form = {form.id: form.name for form in self.env['qc.inspection.form'].search([])}
        exception_handling = ""
        responsibilities_unit = {unit.id: unit.name for unit in self.env['qc.responsibility.units'].search([])}

        col = 0
        row = 1
        for column in columns:
            column_name = column[0]
            column_width = column[1]
            worksheet.set_column(col, col, column_width)
            worksheet.write(row - 1, col, column_name, wbf['header_orange'])
            col += 1
        for item in non_serial_products:
            col = 0
            worksheet.write(row, col, item.product.name, wbf['data_doc'])
            worksheet.set_row(row, 30)
            col += 1
            worksheet.write(row, col, item.product_qty)
            col += 1
            worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                           'source': list(inspection_basis.values())})
            col += 1
            worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                           'source': list(inspection_method.values())})
            col += 1
            worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                           'source': list(use_equipment.values())})
            col += 1
            worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                           'source': list(inspection_form.values())})
            col += 1
            worksheet.write(row, col, exception_handling)
            col += 1
            worksheet.data_validation(row, col, row, col, {'validate': 'list',
                                                           'source': list(responsibilities_unit.values())})
            col += 1
            worksheet.write(row, col, 0)
            col += 1
            worksheet.write(row, col, 0)
            col += 1
            row += 1

    # download execl file format
    def action_download_execl_format(self):

        self.is_clicked_on_download_execl = True
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)

        serial_columns = [
            ('Product Name', 50, 'char', 'char'),
            ('Serial/Lot Number', 30, 'char', 'char'),
            ('Quantity', 30, 'float', 'float'),
            ('Inspection Basis', 30, 'char', 'char'),
            ('Inspection Method', 30, 'char', 'char'),
            ('Use Equipment', 30, 'char', 'char'),
            ('Inspection Form', 30, 'char', 'char'),
            ('Exception Handling', 30, 'char', 'char'),
            ('Responsibilities Unit', 30, 'char', 'char'),
            ('Status', 30, 'char', 'char'),
        ]

        non_serial_columns = [
            ('Product Name', 50, 'char', 'char'),
            ('Quantity', 30, 'float', 'float'),
            ('Inspection Basis', 30, 'char', 'char'),
            ('Inspection Method', 30, 'char', 'char'),
            ('Use Equipment', 30, 'char', 'char'),
            ('Inspection Form', 30, 'char', 'char'),
            ('Exception Handling', 30, 'char', 'char'),
            ('Responsibilities Unit', 30, 'char', 'char'),
            ('Passed Qty', 30, 'float', 'float'),
            ('Failed Qty', 30, 'float', 'float'),
        ]
        serial_product_worksheet = workbook.add_worksheet('Serial Product QC')
        non_serial_product_worksheet = workbook.add_worksheet('Non-Serial Product QC')

        serial_products = []
        non_serial_products = []

        for item in self.iqc_line_id:
            if item.hand_on_qty == 0:
                raise ValidationError(
                    'Can not Downloaded the Excel File\nBecause, You already completed your QC process')
            if item.lot_ids:
                serial_products.append(item)
            else:
                non_serial_products.append(item)

        if serial_products:
            self.print_serial_product(serial_product_worksheet, serial_products, serial_columns, workbook)
        if non_serial_products:
            self.print_non_serial_product(non_serial_product_worksheet, non_serial_products, non_serial_columns,
                                          workbook)

        workbook.close()
        report_name = 'QC products execl'
        filename = '%s' % (report_name)
        # Save the Excel file in binary format

        out = base64.encodestring(output.getvalue())
        self.write({'datas': out, 'datas_fname': filename})
        output.close()
        filename += '%2Exlsx'

        # You can then save or return the 'excel_file' as needed, for example:
        # self.report_data = base64.encodestring(excel_file)
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': 'web/content/?model=' + self._name + '&id=' + str(
                self.id) + '&field=datas&download=true&filename=' + filename,
        }

    def process_serial_product_tab(self, sheet):
        data = []
        for row in range(1, sheet.nrows):
            values = [sheet.cell_value(row, i) for i in range(sheet.ncols)]
            data.append(values)

        return data

    def process_non_serial_product_tab(self, sheet):
        data = []
        for row in range(1, sheet.nrows):
            values = [sheet.cell_value(row, i) for i in range(sheet.ncols)]
            data.append(values)

        return data

    # Import Execl File
    def import_file(self):

        global passed_lot_ids
        for record in self:
            if self.excel_state != 'draft':
                raise ValidationError('You already imported your Excel File')
            else:
                self.excel_state = 'imported'

            if self.state != 'draft':
                raise ValidationError("Only in Draft state you can Import the Excel File")
            # Assuming there is only one attachment, you may need to modify this logic if handling multiple attachments
            if len(record.attachment_ids) != 1:
                raise UserError(_("Please attach exactly one Excel file for import."))

            attachment = record.attachment_ids[0]

            # Check file extension
            file_extension = os.path.splitext(attachment.name)[-1].lower()
            if file_extension != '.xlsx':
                raise UserError(_("Invalid file format. Please attach an Excel file with .xlsx extension."))

            # Read Excel file content
            file_content = base64.b64decode(attachment.datas)
            workbook = xlrd.open_workbook(file_contents=file_content)

            serial_data = []
            non_serial_data = []

            for i in range(workbook.nsheets):
                product_sheet = workbook.sheet_by_index(i)
                if product_sheet.name == 'Serial Product QC':
                    # Process serial product tab
                    serial_data = self.process_serial_product_tab(product_sheet)
                if product_sheet.name == 'Non-Serial Product QC':
                    # Process non-serial product tab
                    non_serial_data = self.process_non_serial_product_tab(product_sheet)

            existing_lines = {line.product.name: line for line in record.iqc_line_id}

            product_counts = {}
            product_with_lot_id = {}
            product_without_lot_id = {}

            # for serial product
            for value in serial_data:
                product_name = value[0]
                lot_id = value[1]
                status = value[9]

                if product_name:
                    if product_name in existing_lines:
                        if product_name not in product_counts:
                            product_counts[product_name] = {'passed': 0, 'failed': 0}
                        product_counts[product_name][status] += 1

                    # Check if product_name is not empty and not in product_with_lot_id
                    if product_name and product_name not in product_with_lot_id:
                        product_with_lot_id[product_name] = {'passed': {}, 'failed': {}}

                        # Add values based on lot_id
                    if product_name:
                        if product_name not in product_with_lot_id[product_name]:
                            product_with_lot_id[product_name][status][lot_id] = {
                                'inspection_basis': value[3],
                                'inspection_method': value[4],
                                'use_equipment': value[5],
                                'inspection_form': value[6],
                                'exception_handling': value[7],
                                'responsibilities_unit': value[8]
                            }

            # for non-serial product store those value in product_without_lot_id dictionary
            for value in non_serial_data:
                product_name = value[0]
                passed_count = value[8]
                failed_count = value[9]

                if product_name in existing_lines:
                    if product_name not in product_counts:
                        product_counts[product_name] = {'passed': 0, 'failed': 0}
                        product_counts[product_name]['passed'] = passed_count
                        product_counts[product_name]['failed'] = failed_count

                        product_without_lot_id[product_name] = {
                            'passed_count': value[8],
                            'failed_count': value[9],
                            'inspection_basis': value[2],
                            'inspection_method': value[3],
                            'use_equipment': value[4],
                            'inspection_form': value[5],
                            'exception_handling': value[6],
                            'responsibilities_unit': value[7],
                        }

            lines = []
            # update incoming.material.qc.line value based on product
            for product_name, counts in product_counts.items():
                existing_line = existing_lines.get(product_name)
                if existing_line:
                    hand_on_qty = existing_line.hand_on_qty - (counts.get('passed', 0) + counts.get('failed', 0))
                    line_data = {
                        'passed_qty': counts.get('passed', 0),
                        'mrb_qty': counts.get('failed', 0),
                        'hand_on_qty': 0 if hand_on_qty < 0 else hand_on_qty,
                    }
                    existing_line.write(line_data)
                    lines.append((1, existing_line.id, line_data))

            # Update or create lines in the record
            record.write({'iqc_line_id': lines})

            _logger.info("Imported %d lines from Excel for %s." % (len(lines), record.seq))

            # create the QC Checking Process
            for line in record.iqc_line_id:
                product_name = line.product.name

                if line.lot_ids:
                    product_lot_data = product_with_lot_id.get(product_name)
                    if product_lot_data:
                        passed_lot_ids = product_lot_data.get('passed', {})
                        failed_lot_ids = product_lot_data.get('failed', {})
                    else:
                        passed_lot_ids = {}
                        failed_lot_ids = {}
                    passed_cnt = len(passed_lot_ids)
                    failed_cnt = len(failed_lot_ids)
                    lot_ids = line.lot_ids
                    merge_lot_ids = passed_lot_ids.copy()
                    merge_lot_ids.update(failed_lot_ids)
                else:
                    product_data = product_without_lot_id.get(product_name)
                    passed_cnt = product_data.get('passed_count', 0)
                    failed_cnt = product_data.get('failed_count', 0)
                    lot_ids = False
                    merge_lot_ids = product_without_lot_id.copy()

                # creating supplier.qc.checking model data which is the
                # parent model of customer.qc.checking.line model
                qc_checking_data = {
                    'purchase_order': record.purchase_order.id,
                    'product_id': line.product.id,
                    'vendor': record.vendor.id,
                    'qty': line.product_qty,
                    'im_qc_ref': record.seq,
                    'im_qc_id': record.id,
                    'iqc_line_ids': line.id,
                    'is_have_serial_number': True if line.lot_ids else False,
                    'picking_ids': line.picking_ids.id,
                    'default_lot_ids': lot_ids,
                    'passed_qty': passed_cnt,
                    'failed_qty': failed_cnt,
                }
                qc_checking_id = self.env['supplier.qc.checking'].create(qc_checking_data)

                # Right now creating customer.qc.checking.line model

                if qc_checking_id:
                    supplier_qc_line_data = []
                    vals = []
                    if qc_checking_id.default_lot_ids:
                        for lot_id, lot_data in merge_lot_ids.items():
                            inspection_basis = self.env['qc.inspection.basis'].search(
                                [('name', '=', lot_data.get('inspection_basis', False))])
                            inspection_method = self.env['qc.inspection.methods'].search(
                                [('name', '=', lot_data.get('inspection_method', False))])
                            use_equipment = self.env['qc.use.equipment'].search(
                                [('name', '=', lot_data.get('use_equipment', False))])
                            inspection_form = self.env['qc.inspection.form'].search(
                                [('name', '=', lot_data.get('inspection_form', False))])
                            exception_handling = lot_data.get('exception_handling', False)
                            responsibilities_unit = self.env['qc.responsibility.units'].search(
                                [('name', '=', lot_data.get('responsibilities_unit', False))])

                            qc_state = 'passed' if lot_id in passed_lot_ids else 'failed'
                            serial_lot_id = self.env['stock.production.lot'].search(
                                [('name', '=', lot_id), ('product_id', '=', line.product.id)])
                            qc_checking_line_data = {
                                'product_id': line.product.id,
                                'qty': 1,
                                'inspection_basis': inspection_basis.id,
                                'inspection_methods': inspection_method.id,
                                'use_equipment': use_equipment.id,
                                'inspection_form': inspection_form.id,
                                'exception_handling': exception_handling,
                                'responsibility_units': responsibilities_unit.id,
                                'qc_state': qc_state,
                                'lot_ids': serial_lot_id.id,
                                'im_qc_ref': self.seq,
                                'supplier_qc_id': qc_checking_id.id,
                            }
                            line_ids = self.env['customer.qc.checking.line'].create(qc_checking_line_data)
                            vals.append(line_ids.id)
                        # qc_checking_id.supplier_qc_line_ids = vals

                    else:
                        vals = []
                        for product_name, product_data in merge_lot_ids.items():
                            product_id = self.env['product.product'].search([('name', '=', product_name)])
                            if line.product.id == product_id.id:
                                inspection_basis = self.env['qc.inspection.basis'].search(
                                    [('name', '=', product_data.get('inspection_basis', False))])
                                inspection_method = self.env['qc.inspection.methods'].search(
                                    [('name', '=', product_data.get('inspection_method', False))])
                                use_equipment = self.env['qc.use.equipment'].search(
                                    [('name', '=', product_data.get('use_equipment', False))])
                                inspection_form = self.env['qc.inspection.form'].search(
                                    [('name', '=', product_data.get('inspection_form', False))])

                                exception_handling = product_data.get('exception_handling', False)

                                responsibilities_unit = self.env['qc.responsibility.units'].search(
                                    [('name', '=', product_data.get('responsibilities_unit', False))])

                                for i in range(
                                        int(product_data.get('passed_count', False) + product_data.get('failed_count', False))):
                                    if i < int(product_data.get('passed_count', False)):
                                        qc_state = 'passed'
                                    else:
                                        qc_state = 'failed'
                                    qc_checking_line_data = {
                                        'product_id': line.product.id,
                                        'qty': 1,
                                        'inspection_basis': inspection_basis.id,
                                        'inspection_methods': inspection_method.id,
                                        'use_equipment': use_equipment.id,
                                        'inspection_form': inspection_form.id,
                                        'exception_handling': exception_handling,
                                        'responsibility_units': responsibilities_unit.id,
                                        'qc_state': qc_state,
                                        'lot_ids': False,
                                        'im_qc_ref': self.seq,
                                        'supplier_qc_id': qc_checking_id.id,
                                    }
                                    line_ids = self.env['customer.qc.checking.line'].create(qc_checking_line_data)
                                    vals.append(line_ids.id)
                    qc_checking_id.supplier_qc_line_ids = vals

    def action_transfer_button(self):
        return {
            'name': 'Transfers',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {},
            'domain': [('origin', '=', self.seq)],
        }

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def _transfer_picking_data(self, user=False, source_location=False, destination_location=False):
        picking_data = {
            'origin': self.seq,
            'partner_id': user.partner_id.id,
            'picking_type_id': destination_location.warehouse_id.int_type_id.id,
            'location_id': source_location.id,
            'branch_id': self.env.user.branch_id.id,
            'location_dest_id': destination_location.id,
            'is_from_qc': True,
        }
        return picking_data

    def _transfer_picking_move_data(self, line=False, source_location=False, destination_location=False,
                                    picking_ids=False, qty=False, data=False):

        move_data = {
            'origin': self.seq,
            'name': line.product.name,
            'product_id': line.product.id,
            'product_uom_qty': qty,
            # 'quantity_done': qty,
            'product_uom': line.product.uom_id.id,
            'location_id': source_location.id,
            'location_dest_id': destination_location.id,
            'picking_id': picking_ids,
        }
        return move_data

    # @api.model
    # def _get_default_picking_type(self):
    #     company_id = self.env.context.get('default_company_id', self.env.company.id)
    #     return self.env['stock.picking.type'].search([
    #         ('code', '=', 'mrp_operation'),
    #         ('warehouse_id.company_id', '=', company_id),
    #     ], limit=1).id
    def action_fpo_transfer(self):
        for rec in self:
            if not rec.passed_qc_responsible_person:
                raise ValidationError('Assign Responsible Person for Main(passed) Stock')

            if not rec.failed_qc_responsible_person:
                raise ValidationError('Assign Responsible Person for MRB Stock')

            if any(line.hand_on_qty != 0 for line in rec.iqc_line_id):
                raise UserError(_("You have to Complete Your QC Process."))

            warehouse_id = self.env['stock.warehouse'].search([('is_non_saleable_warehouse', '=', True)])
            source_location = warehouse_id.lot_stock_id

            rec.state = 'assigned'
            passed_picking_data = rec._transfer_picking_data(rec.passed_qc_responsible_person, source_location,
                                                             rec.passed_location)
            passed_stock_picking = self.env['stock.picking'].create(passed_picking_data)
            passed_stock_picking.write({
                'is_nonsalealewarehouse_transfar': True
            })
            failed_picking_data = rec._transfer_picking_data(rec.failed_qc_responsible_person, source_location,
                                                             rec.failed_location)
            failed_stock_picking = self.env['stock.picking'].create(failed_picking_data)
            failed_stock_picking.write({
                'is_nonsalealewarehouse_transfar': True
            })


            for line in rec.iqc_line_id:
                iqc_line_ids = self.env['supplier.qc.checking'].search(
                    [('iqc_line_ids', '=', line.id), ('product_id', '=', line.product.id)])
                customer_qc_line_ids = self.env['customer.qc.checking.line'].search(
                    [('supplier_qc_id.id', 'in', iqc_line_ids.ids)])

                passed_qty_by_product = {}
                failed_qty_by_product = {}

                for customer_qc_line_id in customer_qc_line_ids:
                    product = customer_qc_line_id.product_id
                    qty = abs(customer_qc_line_id.qty)
                    if customer_qc_line_id.qc_state == 'passed':
                        passed_qty_by_product[product] = passed_qty_by_product.get(product, 0) + qty
                    elif customer_qc_line_id.qc_state == 'failed':
                        failed_qty_by_product[product] = failed_qty_by_product.get(product, 0) + qty

                if passed_qty_by_product:
                    for product, passed_qty in passed_qty_by_product.items():
                        move_data = rec._transfer_picking_move_data(line, source_location, rec.passed_location,
                                                                    passed_stock_picking.id, passed_qty)
                        move = self.env['stock.move'].create(move_data)
                if failed_qty_by_product:
                    for product, failed_qty in failed_qty_by_product.items():
                        move_data = rec._transfer_picking_move_data(line, source_location, rec.failed_location,
                                                                    failed_stock_picking.id, failed_qty)
                        move = self.env['stock.move'].create(move_data)

                    # Assign pickings to customer_qc_line_ids
                customer_qc_line_ids.write({
                    'passed_picking_id': passed_stock_picking.id if passed_stock_picking else False,
                    'failed_picking_id': failed_stock_picking.id if failed_stock_picking else False,
                })

            pickings = self.env['stock.picking'].search([('origin', '=', self.seq)])
            for data in pickings:
                data.write({
                    'commercial_invoice': rec.fpo_order.id,
                })
                data.action_confirm()
            action = self.env.ref('stock.action_picking_tree_all').read()[0]
            action['domain'] = [('id', 'in', pickings.ids)]

            return action
        pass

    def action_confirm(self):
        global source_location, destination_location_id, failed_stock_picking

        for rec in self:
            if not rec.passed_qc_responsible_person:
                raise ValidationError('Assign Responsible Person for Main(passed) Stock')

            if not rec.failed_qc_responsible_person:
                raise ValidationError('Assign Responsible Person for MRB Stock')

            if any(line.hand_on_qty != 0 for line in rec.iqc_line_id):
                raise UserError(_("You have to Complete Your QC Process."))

            rec.state = 'assigned'
            passed_stock_picking = False
            if rec.purchase_order.transfer_type == 'mandatory_qc':
                warehouse_id = self.env['stock.warehouse'].search([('is_non_saleable_warehouse', '=', True)])
                source_location = warehouse_id.lot_stock_id

                passed_picking_data = rec._transfer_picking_data(rec.passed_qc_responsible_person, source_location,
                                                                 rec.passed_location)
                passed_stock_picking = self.env['stock.picking'].create(passed_picking_data)

                failed_picking_data = rec._transfer_picking_data(rec.failed_qc_responsible_person, source_location,
                                                                 rec.failed_location)
                failed_stock_picking = self.env['stock.picking'].create(failed_picking_data)

            if rec.purchase_order.transfer_type == 'optional_qc':
                picking_id = self.env['stock.picking'].search([('purchase_id', '=', rec.purchase_order.id)])
                source_location = picking_id.location_dest_id

                failed_picking_data = rec._transfer_picking_data(rec.failed_qc_responsible_person, source_location,
                                                                 rec.failed_location)
                failed_stock_picking = self.env['stock.picking'].create(failed_picking_data)

            passed_qty_by_product = {}
            failed_qty_by_product = {}

            for line in rec.iqc_line_id:
                iqc_line_ids = self.env['supplier.qc.checking'].search(
                    [('iqc_line_ids', '=', line.id), ('product_id', '=', line.product.id)])
                customer_qc_line_ids = self.env['customer.qc.checking.line'].search(
                    [('supplier_qc_id.id', 'in', iqc_line_ids.ids)])

                passed_qty_by_product = {}
                failed_qty_by_product = {}

                for customer_qc_line_id in customer_qc_line_ids:
                    product = customer_qc_line_id.product_id
                    qty = abs(customer_qc_line_id.qty)
                    if customer_qc_line_id.qc_state == 'passed':
                        passed_qty_by_product[product] = passed_qty_by_product.get(product, 0) + qty
                    elif customer_qc_line_id.qc_state == 'failed':
                        failed_qty_by_product[product] = failed_qty_by_product.get(product, 0) + qty

                if rec.purchase_order.transfer_type == 'mandatory_qc':
                    if passed_qty_by_product:
                        for product, passed_qty in passed_qty_by_product.items():
                            move_data = rec._transfer_picking_move_data(line, source_location, rec.passed_location,
                                                                        passed_stock_picking.id, passed_qty)
                            move = self.env['stock.move'].create(move_data)
                if failed_qty_by_product:
                    for product, failed_qty in failed_qty_by_product.items():
                        move_data = rec._transfer_picking_move_data(line, source_location, rec.failed_location,
                                                                    failed_stock_picking.id, failed_qty)
                        move = self.env['stock.move'].create(move_data)

                    # Assign pickings to customer_qc_line_ids
                customer_qc_line_ids.write({
                    'passed_picking_id': passed_stock_picking.id if passed_stock_picking else False,
                    'failed_picking_id': failed_stock_picking.id if failed_stock_picking else False,
                })

            pickings = self.env['stock.picking'].search([('origin', '=', self.seq)])
            for data in pickings:
                data.action_confirm()
                data.action_set_quantities_to_reservation()
                data.button_submit_approval()
            action = self.env.ref('stock.action_picking_tree_all').read()[0]
            action['domain'] = [('id', 'in', pickings.ids)]

            return action

    @api.onchange('attachment_ids')
    def _onchange_attachment_ids(self):
        if self.state != 'draft':
            raise ValidationError('Only in Draft state you can delete Excel File.')
        iqc_line_ids = self.env['incoming.material.qc.line'].search([('iqc_id', '=', self.id.origin)])
        for line in iqc_line_ids:
            query = """update incoming_material_qc_line set hand_on_qty={}, passed_qty={}, mrb_qty={} where id = {}""".format(
                line.product_qty, 0.0, 0.0, line.id)
            self._cr.execute(query)

            #         drop supplier.qc.checking data
            supplier_qc_query = """delete from supplier_qc_checking where iqc_line_ids = {}""".format(line.id)
            self._cr.execute(supplier_qc_query)

    @api.onchange('failed_qc_responsible_person')
    def _onchange_failed_qc_responsible_person(self):
        warehouse_id = self.env['stock.warehouse'].search(
            [('id', '=', self.failed_qc_responsible_person.property_warehouse_id.id)])
        location = self.env['stock.location'].search(
            [('warehouse_id', '=', warehouse_id.id), ('is_MRB_location', '=', True)])
        if location.warehouse_id.id == warehouse_id.id:
            self.failed_location = location.id
        else:
            self.failed_location = False

    @api.onchange('passed_qc_responsible_person')
    def _onchange_passed_qc_responsible_person(self):
        warehouse_id = self.env['stock.warehouse'].search([
            ('id', '=', self.passed_qc_responsible_person.property_warehouse_id.id),
        ])
        location_id = self.env['stock.location'].search([
            ('id', '=', warehouse_id.lot_stock_id.id),
            ('is_MRB_location', '=', False)
        ])

        if location_id:
            self.passed_location = location_id.id
        else:
            self.passed_location = False

    @api.onchange('manufacture_order')
    def onchange_manufacture_order(self):
        if self.manufacture_order:
            eng_profile = self.env['engineer.profile'].search([
                ('manufacture_id', '=', self.manufacture_order.id),
                ('state', '=', 'done')
            ])
            if eng_profile:
                self.desk = eng_profile.desk.id
                self.line_manager = eng_profile.line_manager.id
                self.engineer = eng_profile.engineer.id
                self.assembly_line = eng_profile.assembly_line_id.id

        if self.qc_type == 'pre_mrp_qc':
            self.product_id = self.manufacture_order.product_id.id
            self.product_qty = self.manufacture_order.product_qty

            if self.manufacture_order:
                self.iqc_line_id = [(5, 0, 0)]

                incoming_qc_lines = []
                for move_raw in self.manufacture_order.move_raw_ids:
                    move_line_lot_id = self.env['stock.move.line'].search(
                        [('production_id', '=', self.manufacture_order.id),
                         ('product_id', '=', move_raw.product_id.id)])

                    incoming_qc_lines.append((0, 0, {
                        'product': move_raw.product_id.id,
                        'product_qty': move_raw.product_uom_qty,
                        'hand_on_qty': move_raw.product_uom_qty,
                        'lot_ids': [lot_id.id for lot_id in
                                    move_line_lot_id.lot_id] if move_line_lot_id.lot_id else False,
                        'iqc_id': self.id,
                    }))
                self.iqc_line_id = incoming_qc_lines

        if self.qc_type == 'post_mrp_qc':
            if self.manufacture_order:
                self.iqc_line_id = [(5, 0, 0)]
                incoming_qc_lines = []
                mo = self.manufacture_order
                lot_ids = [mo.lot_producing_id.id]

                incoming_qc_lines.append((0, 0, {
                    'product': mo.product_id.id,
                    'product_qty': mo.product_qty,
                    'current_qty': mo.product_qty,
                    'hand_on_qty': mo.product_qty,
                    'lot_ids': lot_ids if lot_ids else False,
                    'iqc_id': self.id,
                }))
                self.iqc_line_id = incoming_qc_lines

    @api.onchange('fpo_order')
    def onchange_fpo_order(self):
        iqc_line_values = []
        self.vendor = self.fpo_order.partner_id.id
        for move_line in self.fpo_order.invoice_line_ids:
            if move_line.move_name == self.fpo_order.name:
                iqc_line_values.append((0, 0, {
                    'product': move_line.product_id.id,
                    'product_qty': move_line.quantity,
                    'hand_on_qty': move_line.quantity,
                    'state': move_line.parent_state,
                    'lot_ids': False,
                    'picking_ids': False,
                }))

        self.iqc_line_id = iqc_line_values


    @api.onchange('purchase_order')
    def onchange_purchase_order(self):
        state = ''
        for rec in self:
            rec.vendor = rec.purchase_order.partner_id.id

            rec.iqc_line_id = [(5, 0, 0)]
            if rec.purchase_order.transfer_type == 'mandatory_qc':
                rec.is_mandatory_po = True
                rec.is_optional_po = False
            if rec.purchase_order.transfer_type == 'optional_qc':
                rec.is_mandatory_po = False
                rec.is_optional_po = True

            picking_ids = self.env['stock.picking'].search(
                [('id', 'in', rec.purchase_order.picking_ids.ids), ('state', '=', 'done')])

            stock_move_line_ids = self.env['stock.move'].search(
                [('id', 'in', picking_ids.move_ids_without_package.ids)])

            iqc_line_values = []

            for move_line in stock_move_line_ids:
                if move_line.origin == rec.purchase_order.name:
                    lot_ids = [(6, 0, move_line.lot_ids.ids)]
                    if len(move_line.lot_ids) > 0:
                        iqc_line_values.append((0, 0, {
                            'product': move_line.product_id.id,
                            'product_qty': move_line.quantity_done,
                            'hand_on_qty': move_line.quantity_done,
                            'state': rec.purchase_order.state,
                            'lot_ids': lot_ids,
                            'picking_ids': picking_ids.id,
                        }))
                    else:
                        iqc_line_values.append((0, 0, {
                            'product': move_line.product_id.id,
                            'product_qty': move_line.quantity_done,
                            'hand_on_qty': move_line.quantity_done,
                            'state': rec.purchase_order.state,
                            'picking_ids': picking_ids.id,
                        }))
            rec.iqc_line_id = iqc_line_values

    def reload_action(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def create(self, vals):

        vals['seq'] = self.env['ir.sequence'].next_by_code('usl_qc.incoming_material')
        return super(IncomingMaterialQC, self).create(vals)
        # record = super(IncomingMaterialQC, self).create(vals)
        #
        # # Reload the page using the web client action
        # return record.reload_action()

    def add_workbook_format(self, workbook):
        colors = {
            'white_orange': '#FFFFDB',
            'orange': '#FFC300',
            'red': '#FF0000',
            'yellow': '#F6FA03',
        }

        wbf = {}
        wbf['header'] = workbook.add_format(
            {'bold': 1, 'align': 'center', 'bg_color': '#FFFFDB', 'font_color': '#000000'})
        wbf['header'].set_border()

        wbf['header_orange'] = workbook.add_format(
            {'bold': 1, 'align': 'center', 'bg_color': colors['white_orange'], 'font_color': '#000000'
             })
        wbf['header_orange'].set_border()
        # wbf['header_orange'].set_row(0, 30)

        wbf['data_doc'] = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        return wbf, workbook


class IncomingMaterialQCLine(models.Model):
    _name = 'incoming.material.qc.line'

    product = fields.Many2one('product.product', string='Product', readonly=True)
    product_qty = fields.Float(string="Quantity", readonly=True)
    current_qty = fields.Float(string="Current Quantity", readonly=True)
    hand_on_qty = fields.Float(string='Quantity on Hand', readonly=True)
    state = fields.Char(string='Status', readonly=True)
    passed_qty = fields.Float(string='Passed Quantity', default=0.0, readonly=True)
    mrb_qty = fields.Float(string='MRB Quantity', default=0.0, readonly=True)
    iqc_id = fields.Many2one('incoming.material.qc', string='IQC_id', ondelete='cascade')
    lot_ids = fields.Many2many('stock.production.lot', string='Serial/Lot Number')
    picking_ids = fields.Many2one('stock.picking', string='Stock Picking Id')

    def action_customer_qc(self):
        if self.iqc_id.qc_type == 'post_mrp_qc' and self.current_qty == 0:
            raise ValidationError(_("No Product left to QC"))

        customer_qc_checking = self.env['supplier.qc.checking'].search([
            ('vendor', '=', self.iqc_id.vendor.id),
            ('product_id', '=', self.product.id),
            ('iqc_line_ids', '=', self.id),
        ], limit=1)

        quantity_to_pass = 0.0
        is_single_qc = False
        is_bulk_qc = False

        if self.iqc_id.qc_type != 'post_mrp_qc':
            # Check if a record is found
            if customer_qc_checking:
                # If record is found, return the action to open it
                if self.iqc_id.qc_state == 'single_qc':
                    customer_qc_checking.write({
                        'qty': self.hand_on_qty,
                        'is_single_qc': True,
                        'is_bulk_qc': False,

                    })
                elif self.iqc_id.qc_state == 'bulk_qc':
                    customer_qc_checking.write({
                        'qty': self.hand_on_qty,
                        'is_single_qc': False,
                        'is_bulk_qc': True,

                    })

                context = {'default_id': customer_qc_checking.id}

                # context = self.env.context

                return {
                    'type': 'ir.actions.act_window',
                    'name': 'QC',
                    'res_model': 'supplier.qc.checking',
                    'res_id': customer_qc_checking.id,
                    'view_mode': 'form',
                    'target': 'new',
                    'context': context,
                }
            else:
                # If no record is found, create a new one
                name = 'QC'
                if self.iqc_id.qc_state == 'single_qc':
                    quantity_to_pass = self.hand_on_qty
                    is_single_qc = True
                    is_bulk_qc = False
                elif self.iqc_id.qc_state == 'bulk_qc':
                    quantity_to_pass = self.hand_on_qty
                    is_single_qc = False
                    is_bulk_qc = True

                lot_id = False if not self.lot_ids else True

                context = {
                    'default_purchase_order': self.iqc_id.purchase_order.id,
                    'default_manufacture_order': self.iqc_id.manufacture_order.id,
                    'default_product_id': self.product.id,
                    'default_vendor': self.iqc_id.vendor.id,
                    'default_qty': quantity_to_pass,
                    'default_qc_type': self.iqc_id.qc_type,
                    'default_im_qc_ref': self.iqc_id.seq,
                    'default_im_qc_id': self.iqc_id.id,
                    'default_default_lot_ids': self.lot_ids.ids,
                    'default_iqc_line_ids': self.id,
                    'default_is_have_serial_number': lot_id,
                    'default_picking_ids': self.picking_ids.id,
                    'default_is_single_qc': is_single_qc,
                    'default_is_bulk_qc': is_bulk_qc,
                }

                return {
                    'name': name,
                    'res_model': 'supplier.qc.checking',
                    'view_mode': 'form',
                    'context': context,
                    'target': 'new',
                    'type': 'ir.actions.act_window',
                    'domain': [
                        ('im_qc_ref', '=', self.iqc_id.seq),
                        ('product_id', '=', self.product.id),
                        ('iqc_line_ids', '=', self.id),
                    ],
                }
        else:
            name = 'QC'
            if self.iqc_id.qc_state == 'single_qc':
                quantity_to_pass = 1
                is_single_qc = True
                is_bulk_qc = False
            elif self.iqc_id.qc_state == 'bulk_qc':
                quantity_to_pass = self.current_qty
                is_single_qc = False
                is_bulk_qc = True

            lot_id = False if not self.lot_ids else True

            context = {
                'default_purchase_order': self.iqc_id.purchase_order.id,
                'default_manufacture_order': self.iqc_id.manufacture_order.id,
                'default_product_id': self.product.id,
                'default_vendor': self.iqc_id.vendor.id,
                'default_qty': quantity_to_pass,
                'default_im_qc_ref': self.iqc_id.seq,
                'default_iqc_line_ids': self.id,
                'default_is_have_serial_number': lot_id,
                'default_default_lot_ids': self.lot_ids.ids,
                'default_qc_type': self.iqc_id.qc_type,
                'default_qc_stages': self.iqc_id.stage_id.id,
                'default_is_single_qc': is_single_qc,
                'default_is_bulk_qc': is_bulk_qc,
                'default_line_manager': self.iqc_id.line_manager.id,
                'default_desk': self.iqc_id.desk.id,
                'default_engineer': self.iqc_id.engineer.id,
                'default_assembly_line': self.iqc_id.assembly_line.id,
            }
            last_sequence = self.env['pre.qc.config.line'].search(
                [('pre_qc_config_id', '=', self.iqc_id.stage_id.pre_qc_config_id.id)],
                order='sequence desc',
                limit=1
            )

            if self.iqc_id.stage_id.sequence == last_sequence.sequence:
                raise UserError(
                    "QC is Already Complete!")
            else:
                return {
                    'name': name,
                    'res_model': 'supplier.qc.checking',
                    'view_mode': 'form',
                    'context': context,
                    'target': 'new',
                    'type': 'ir.actions.act_window',
                    # 'domain': [
                    #     ('im_qc_ref', '=', self.iqc_id.seq),
                    #     ('product_id', '=', self.product.id),
                    #     ('iqc_line_ids', '=', self.id),
                    # ],
                }
