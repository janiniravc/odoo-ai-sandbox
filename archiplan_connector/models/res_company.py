from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    archiplan_url = fields.Char(default='https://app.archiplan.io')
    archiplan_schedule_link = fields.Char()
