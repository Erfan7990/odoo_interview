from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RoleManagement(models.Model):
    _name = 'role.manage'
    _description = 'Production Roles'
    _rec_name = 'role'

    role = fields.Many2one('res.groups', string="Role", required=True, domain="[('category_id','=',category_id)]")
    users = fields.Many2many('res.users', string="Users", relation='role_users_rel')
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    category_id = fields.Integer(string='Category ID', default=lambda self: self._get_category_id())
    role_select = fields.Selection([
        ('production_manager', 'Production Manager'),
        ('line_manager', 'Line Manager'),
        ('engineer', 'Engineer'),
    ])

    @api.onchange('role')
    def _onchange_role(self):

        if self.role.name == 'Engineer':
            self.role_select = 'engineer'
        if self.role.name == 'Line Manager':
            self.role_select = 'line_manager'
        if self.role.name == 'Production Manager':
            self.role_select = 'production_manager'


    def _get_category_id(self):
        category_id = self.env['ir.module.category'].search([('name', '=', 'Smart Hi-Tech')])
        return category_id

    @api.model
    def create(self, vals):
        if 'role' in vals:
            existing_role = self.search([('role', '=', vals.get('role'))])
            if existing_role:
                raise ValidationError('This Role already exists!')

        new_role = super(RoleManagement, self).create(vals)

        if 'users' in vals:
            users_ids = vals.get('users')[0][2]
            new_role.role.write({'users': [(6, 0, users_ids)]})

        return new_role

    def write(self, vals):
        if 'role' in vals:
            existing_role = self.search([('role', '=', vals.get('role'))])
            if existing_role:
                raise ValidationError('Role already exists in Role Management!')
        if 'users' in vals:
            users_ids = vals.get('users')[0][2]
            self.role.write({'users': [(6, 0, users_ids)]})

        return super(RoleManagement, self).write(vals)

    @api.onchange('users')
    def _onchange_users(self):
        existing_users = self.search([('id', '!=', self.id.origin), ('users', 'in', self.users.ids)])
        if existing_users:
            raise ValidationError(f'Selected user is already assigned in {existing_users.role.name} Role')

