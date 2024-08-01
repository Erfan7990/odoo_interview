from odoo import models, fields


class InheritStockLocation(models.Model):
    _inherit = 'stock.location'

    is_MRB_location = fields.Boolean(string='Is MRB Location', default=False)

    is_qc_failed_item_location = fields.Boolean(string='Is a QC Failed Item Location?', default=False)

    is_batch_annealing_location = fields.Boolean(string='Is Batch Annealing Stock', default=False)
    is_special_mining_location = fields.Boolean(string='Is Special Mining Stock', default=False)

