from odoo import api, fields, models


class ManufacturingQcWizard(models.TransientModel):
    _name = 'pre.qc.wizard'
    _description = 'Manufacturing Pre-QC Wizard'

    manufacture_id = fields.Many2one(
        'mrp.production', string='Manufacturing Order', required=True,
    )

    pre_qc_config_id = fields.Many2one(
        'pre.qc.config', string='QC Type',  required=True,
    )

    def action_proceed(self):
        default_values = {
            'default_manufacture_id': self.manufacture_id.id,
            'default_pre_qc_config_id': self.pre_qc_config_id.id,
        }
        return {
            'name': 'Manufacture QC Checking',
            'type': 'ir.actions.act_window',
            'res_model': 'manufact.qc.checking',
            'view_mode': 'tree,form',
            'context': default_values,
            'target': 'current',
            'domain': [('manufacture_id', '=', self.manufacture_id.id)],
        }

