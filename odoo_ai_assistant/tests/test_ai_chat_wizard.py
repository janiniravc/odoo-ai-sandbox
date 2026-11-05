from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestOdooAIChatWizardSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ai_group = cls.env.ref(
            "odoo_ai_assistant.group_ai_assistant_user"
        )
        internal_group = cls.env.ref("base.group_user")
        cls.owner = cls.env["res.users"].create({
            "name": "AI Wizard Owner",
            "login": "ai_wizard_owner",
        })
        cls.other_user = cls.env["res.users"].create({
            "name": "AI Wizard Other User",
            "login": "ai_wizard_other",
        })
        cls.unauthorized_user = cls.env["res.users"].create({
            "name": "AI Wizard Unauthorized User",
            "login": "ai_wizard_unauthorized",
        })
        internal_group.write({
            "user_ids": [
                (4, cls.owner.id),
                (4, cls.other_user.id),
                (4, cls.unauthorized_user.id),
            ]
        })
        cls.ai_group.write({
            "user_ids": [(4, cls.owner.id), (4, cls.other_user.id)]
        })

    def test_chat_wizard_is_private_to_its_creator(self):
        owner_env = self.env(user=self.owner.id, su=False)
        wizard = owner_env["odoo.ai.chat.wizard"].create({
            "question": "Find my customer",
        })

        other_env = self.env(user=self.other_user.id, su=False)
        with self.assertRaises(AccessError):
            other_env["odoo.ai.chat.wizard"].browse(wizard.id).read()

    def test_chat_wizard_cannot_be_manually_unlinked(self):
        owner_env = self.env(user=self.owner.id, su=False)
        wizard = owner_env["odoo.ai.chat.wizard"].create({
            "question": "Find my customer",
        })

        with self.assertRaises(AccessError):
            wizard.unlink()

    def test_user_without_ai_group_cannot_invoke_action(self):
        owner_env = self.env(user=self.owner.id, su=False)
        wizard = owner_env["odoo.ai.chat.wizard"].create({
            "question": "Find my customer",
        })
        unauthorized_wizard = wizard.with_user(self.unauthorized_user)

        with patch(
            "odoo.addons.odoo_ai_assistant.wizard.ai_chat_wizard."
            "OdooAIToolService.ask"
        ) as mock_ask:
            with self.assertRaises(AccessError):
                unauthorized_wizard.action_ask_ai()

        mock_ask.assert_not_called()
