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
            "groups_id": [(6, 0, [internal_group.id, cls.ai_group.id])],
        })
        cls.other_user = cls.env["res.users"].create({
            "name": "AI Wizard Other User",
            "login": "ai_wizard_other",
            "groups_id": [(6, 0, [internal_group.id, cls.ai_group.id])],
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
