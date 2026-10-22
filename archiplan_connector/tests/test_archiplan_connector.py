from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestArchiPlanConnector(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'ArchiPlan test customer'})
        cls.uom = cls.env.ref('uom.product_uom_unit')
        cls.template = cls.env['product.template'].create({'name': 'ArchiPlan ACL product'})
        cls.product = cls.template.product_variant_id
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner.id})
        uom_field = 'product_uom_id' if 'product_uom_id' in cls.env['sale.order.line']._fields else 'product_uom'
        cls.line = cls.env['sale.order.line'].create({
            'order_id': cls.order.id,
            'product_id': cls.product.id,
            uom_field: cls.uom.id,
            'product_uom_qty': 1,
        })

    def _expected_groups(self):
        return {
            self.env.ref('base.group_user').id,
            self.env.ref('archiplan_connector.group_archiplan_readonly').id,
        }

    def _groups(self, user):
        field = 'group_ids' if 'group_ids' in user._fields else 'groups_id'
        return getattr(user, field)

    def _assert_read_only_models(self, user):
        records = {
            'sale.order': self.order,
            'sale.order.line': self.line,
            'product.product': self.product,
            'product.template': self.template,
            'uom.uom': self.uom,
            'res.partner': self.partner,
        }
        for model_name, record in records.items():
            with self.subTest(model=model_name):
                record.with_user(user).read(['id'])
                with self.assertRaises(AccessError):
                    self.env[model_name].with_user(user).create({})
                with self.assertRaises(AccessError):
                    record.with_user(user).write({'name': 'blocked'})
                with self.assertRaises(AccessError):
                    record.with_user(user).unlink()

    def test_access_creation_rotation_rights_and_revocation(self):
        settings = self.env['res.config.settings'].create({})
        action = settings.action_create_archiplan_access()
        user = self.env['res.users'].sudo().search([('login', '=', 'archiplan')], limit=1)
        self.assertEqual(set(self._groups(user).ids), self._expected_groups())
        self.assertEqual(action['res_model'], 'archiplan.access.wizard')
        self.assertTrue(action['context']['default_api_key'])
        first_key = action['context']['default_api_key']
        keys = self.env['res.users.apikeys'].sudo().search([('user_id', '=', user.id)])
        self.assertEqual(len(keys), 1)
        self._assert_read_only_models(user)

        field = 'group_ids' if 'group_ids' in user._fields else 'groups_id'
        user.sudo().write({field: [(4, self.env.ref('base.group_partner_manager').id)]})
        self.assertIn(self.env.ref('base.group_partner_manager'), self._groups(user))
        second_action = settings.action_create_archiplan_access()
        self.assertEqual(set(self._groups(user).ids), self._expected_groups())
        self.assertNotEqual(second_action['context']['default_api_key'], first_key)
        self.assertFalse(self.env['res.users.apikeys']._check_credentials(scope='rpc', key=first_key))
        self.assertEqual(
            self.env['res.users.apikeys']._check_credentials(
                scope='rpc', key=second_action['context']['default_api_key']),
            user.id,
        )
        self.assertEqual(
            len(self.env['res.users.apikeys'].sudo().search([('user_id', '=', user.id)])),
            1,
        )

        settings.action_revoke_archiplan_access()
        self.assertFalse(user.active)
        self.assertFalse(self.env['res.users.apikeys'].sudo().search([('user_id', '=', user.id)]))

    def test_schedule_link_validation_uses_current_url(self):
        settings = self.env['res.config.settings'].create({})
        settings.write({
            'archiplan_url': 'https://workspace.archiplan.io/',
            'archiplan_schedule_link': 'https://workspace.archiplan.io/embed/schedule/abc123',
        })
        with self.cr.savepoint():
            with self.assertRaises(ValidationError):
                settings.write({'archiplan_schedule_link': 'https://evil.example/embed/schedule/abc123'})
        with self.cr.savepoint():
            with self.assertRaises(ValidationError):
                settings.write({'archiplan_url': 'https://other.archiplan.io'})
        self.assertEqual(settings.archiplan_url, 'https://workspace.archiplan.io/')
        self.assertEqual(settings.archiplan_schedule_link, 'https://workspace.archiplan.io/embed/schedule/abc123')

        settings.write({
            'archiplan_url': 'https://other.archiplan.io',
            'archiplan_schedule_link': 'https://other.archiplan.io/embed/schedule/xyz789',
        })
        self.assertEqual(settings.archiplan_schedule_link, 'https://other.archiplan.io/embed/schedule/xyz789')

    def test_schedule_menu_and_action(self):
        menu = self.env.ref('archiplan_connector.menu_archiplan_schedule')
        action = self.env.ref('archiplan_connector.action_archiplan_schedule')
        self.assertEqual(menu.parent_id, self.env.ref('mrp.mrp_planning_menu_root'))
        self.assertEqual(menu.action, action)
        self.assertEqual(action.tag, 'archiplan_connector.schedule')
