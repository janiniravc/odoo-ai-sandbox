from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    archiplan_url = fields.Char(related='company_id.archiplan_url', readonly=False, string='ArchiPlan URL')
    archiplan_schedule_link = fields.Char(related='company_id.archiplan_schedule_link', readonly=False, string='Schedule link')

    @api.constrains('archiplan_url', 'archiplan_schedule_link')
    def _check_archiplan_schedule_link(self):
        for settings in self:
            link = settings.archiplan_schedule_link
            base = (settings.archiplan_url or '').rstrip('/')
            if link and (not base or not link.startswith(base + '/embed/schedule/')):
                raise ValidationError(_('Schedule link must start with the ArchiPlan URL followed by /embed/schedule/.'))

    def action_create_archiplan_access(self):
        users = self.env['res.users'].sudo()
        group_field = 'group_ids' if 'group_ids' in users._fields else 'groups_id'
        user = users.search([('login', '=', 'archiplan')], limit=1)
        group = self.env.ref('archiplan_connector.group_archiplan_readonly')
        if not user:
            user = users.create({
                'name': 'ArchiPlan', 'login': 'archiplan', 'email': 'archiplan@archiplan.io',
                group_field: [(6, 0, [])],
            })
        user.sudo().with_context(no_add_implied_groups=True).write({
            'active': True,
            group_field: [(6, 0, [self.env.ref('base.group_user').id, group.id])],
        })
        self.env['res.users.apikeys'].sudo().search([('user_id', '=', user.id)])._remove()
        key = self.env['res.users.apikeys'].with_user(user).sudo()._generate('rpc', 'ArchiPlan Connector', None)
        parameters = self.env['ir.config_parameter'].sudo()
        base_url_getter = getattr(parameters, 'get_str', None) or parameters.get_param
        return {
            'type': 'ir.actions.act_window', 'name': _('ArchiPlan access'),
            'res_model': 'archiplan.access.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_odoo_url': base_url_getter('web.base.url'),
                        'default_database': self.env.cr.dbname, 'default_login': user.login, 'default_api_key': key},
        }

    def action_revoke_archiplan_access(self):
        user = self.env['res.users'].sudo().search([('login', '=', 'archiplan')], limit=1)
        if user:
            self.env['res.users.apikeys'].sudo().search([('user_id', '=', user.id)])._remove()
            user.write({'active': False})
        return {'type': 'ir.actions.client', 'tag': 'reload'}
