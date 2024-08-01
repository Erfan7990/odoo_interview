from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpWorkCenterInherit(models.Model):
    _inherit = 'mrp.workcenter'

    desk_ids = fields.Many2many('desk.setup.configuration', string='Engineers Desk',
                                default=lambda self: self._get_default_desk_ids())

    def _get_default_desk_ids(self):

        default_desk_ids = self.env['desk.setup.configuration'].search([('active', '=', True)]).ids
        return [(6, 0, default_desk_ids)]