from odoo import models, fields, _, api
from odoo.exceptions import AccessError, UserError, ValidationError



class InheritStockMove(models.Model):
    _inherit = 'stock.move'

    customer_qc_line_ids = fields.Many2one('customer.qc.checking.line', string='Customer QC line')
    is_from_qc = fields.Boolean(default=False, string='Is From QC')

class InheritStockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    qc_state = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ], string='Status')

    # qc_state_visible = fields.Boolean(default=False, compute='visibility_check')
    #
    # @api.depends('qc_state')
    # def visibility_check(self):
    #     for rec in self:
    #         if rec.product_id.tracking != 'none':
    #             rec.qc_state_visible = True

