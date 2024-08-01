from odoo import api, fields, models


class PreQCConfig(models.Model):
    _name = 'pre.qc.config'
    _description = 'Pre QC Configuration'
    _rec_name = 'name'

    name = fields.Char('QC Name', required=True)
    prefix = fields.Char('Prefix', required=True)
    seq_num = fields.Integer(string="Number of Stages")
    line_id = fields.One2many('pre.qc.config.line','pre_qc_config_id')


    def create_sequences(self):
        for config in self:
            if config.prefix and config.seq_num >= 1:
                sequences = []

                if config.seq_num > 1:
                    for i in range(1, config.seq_num + 1):
                        sequence_name = f"{config.prefix}-{i}"
                        sequences.append((0, 0, {'name': sequence_name}))
                else:
                    # If seq_num is 1, only add the base name
                    sequences.append((0, 0, {'name': config.prefix}))

                config.write({'line_id': sequences})



class PreQCConfigLine(models.Model):
    _name = 'pre.qc.config.line'
    _rec_name = 'name'

    name = fields.Char('QC Name', required=True)
    sequence = fields.Integer('Sequence', default=1, help="Used to order stages. Lower is better.")
    active = fields.Boolean(string="Active?", default=True)
    failed_dest_loc = fields.Many2one('stock.location',string="QC Failed Item Location")
    pre_qc_config_id = fields.Many2one('pre.qc.config')

    @api.model
    def create(self, values):
        values['sequence'] = self._get_next_sequence(values.get('pre_qc_config_id'))
        return super(PreQCConfigLine, self).create(values)

    def write(self, values):
        if 'pre_qc_config_id' in values:
            values['sequence'] = self._get_next_sequence(values['pre_qc_config_id'])
        return super(PreQCConfigLine, self).write(values)

    def _get_next_sequence(self, pre_qc_config_id):
        last_sequence = self.search([('pre_qc_config_id', '=', pre_qc_config_id)], order='sequence desc', limit=1)
        return last_sequence.sequence + 1 if last_sequence else 1
