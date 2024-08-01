from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class EngDeskSetupConf(models.Model):
    _name = 'desk.setup.configuration'
    _description = 'Engineer Desk setup'

    name = fields.Char(string='Name')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True, string='Active')

