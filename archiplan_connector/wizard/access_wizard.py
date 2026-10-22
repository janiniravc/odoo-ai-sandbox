from odoo import fields, models


class ArchiplanAccessWizard(models.TransientModel):
    _name = 'archiplan.access.wizard'
    _description = 'ArchiPlan access details'

    odoo_url = fields.Char(readonly=True)
    database = fields.Char(readonly=True)
    login = fields.Char(readonly=True)
    api_key = fields.Char(readonly=True)
