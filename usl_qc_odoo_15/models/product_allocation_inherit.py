from odoo import api, fields, models


class ProductAllocationInherit(models.Model):
    _inherit = "product.allocation"

    def customer_qc_button(self):
        customer_qc = self.env['customer.qc.checking'].search([('customer', '=', self.allocate_for.id)])
        return {
            'name': 'Customer QC Checking',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.qc.checking',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'default_customer': self.allocate_for.id,
                'default_pa_ref': self.ref,
            },
            'domain': [('pa_ref', '=', self.ref)],
        }

    @api.model
    def default_get(self, fields):
        res = super(ProductAllocationInherit, self).default_get(fields)

        if 'parent_id' in self.env.context:
            product_lines_vals = self.env['customer.order.req'].sudo().search([('id','=',int(self.env.context.get("parent_id")))])

            val_list=[]
            for line in product_lines_vals.product_lines:
                val_list.append((0,0,{
                    'product_id': line.product.id,
                    'qty': line.quantity,
                }))

            res.update({
                'product_details_lines': val_list,
            })

        return res


class ProductForAllocationInherit(models.Model):
    _inherit = "product.for.allocation"

    qc_done = fields.Integer(string="QC Done", default=0, readonly=True)