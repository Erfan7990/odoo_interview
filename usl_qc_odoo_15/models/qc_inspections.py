from odoo import api, fields, models


class InspectionBasis(models.Model):
    _name = "qc.inspection.basis"

    name = fields.Char(string="Name", required=True)
    desc = fields.Text(string="Description")

class InspectionMethods(models.Model):
    _name = "qc.inspection.methods"

    name = fields.Char(string="Name", required=True)
    desc = fields.Text(string="Description")

class UseEquipment(models.Model):
    _name = "qc.use.equipment"

    name = fields.Char(string="Name", required=True)
    desc = fields.Text(string="Description")

class InspectionForm(models.Model):
    _name = "qc.inspection.form"

    name = fields.Char(string="Name", required=True)
    desc = fields.Text(string="Description")

class ResponsibilityUnits(models.Model):
    _name = "qc.responsibility.units"

    name = fields.Char(string="Name", required=True)
    desc = fields.Text(string="Description")