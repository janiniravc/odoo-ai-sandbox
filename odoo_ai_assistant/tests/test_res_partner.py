from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from ..services.ai_service import CustomerAnalysis


class TestPartnerAISummary(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "AI Test Customer Ltd.",
            "is_company": True,
        })

    @patch(
        "odoo.addons.odoo_ai_assistant.models.res_partner."
        "OdooAIService.generate_customer_analysis"
    )
    def test_structured_analysis_saves_fields(self, mock_generate):
        mock_generate.return_value = CustomerAnalysis(
            customer_summary="A company customer.",
            recommended_action="Review the customer profile.",
            follow_up_needed=True,
        )

        self.partner.action_generate_structured_ai_summary()

        self.assertEqual(
            self.partner.ai_summary,
            "A company customer.",
        )
        self.assertEqual(
            self.partner.ai_recommended_action,
            "Review the customer profile.",
        )
        self.assertTrue(self.partner.ai_follow_up_needed)

        mock_generate.assert_called_once_with(
            customer_name="AI Test Customer Ltd.",
            is_company=True,
        )

    @patch(
        "odoo.addons.odoo_ai_assistant.models.res_partner."
        "OdooAIService.generate_customer_analysis",
        side_effect=RuntimeError("Simulated API failure"),
    )
    def test_api_failure_returns_friendly_error(self, mock_generate):
        with self.assertRaises(UserError) as error:
            self.partner.action_generate_structured_ai_summary()

        self.assertIn(
            "Could not generate a valid AI analysis",
            str(error.exception),
        )

    @patch(
        "odoo.addons.odoo_ai_assistant.models.res_partner."
        "OdooAIService.generate_customer_analysis"
    )
    def test_write_access_denied_blocks_ai_request(self, mock_generate):
        original_check_access = type(self.partner).check_access

        def check_access(recordset, operation):
            if operation == "write":
                raise AccessError("Write access denied")
            return original_check_access(recordset, operation)

        with patch.object(
            type(self.partner),
            "check_access",
            autospec=True,
            side_effect=check_access,
        ):
            with self.assertRaises(AccessError):
                self.partner.action_generate_structured_ai_summary()

        mock_generate.assert_not_called()

    @patch(
        "odoo.addons.odoo_ai_assistant.models.res_partner."
        "OdooAIService.generate_customer_analysis",
        side_effect=RuntimeError("Simulated API failure"),
    )
    def test_api_failure_preserves_existing_summary(self, mock_generate):
        self.partner._write_ai_fields({
            "ai_summary": "Previously validated summary.",
            "ai_recommended_action": "Existing action.",
            "ai_follow_up_needed": True,
        })

        with self.assertRaises(UserError):
            self.partner.action_generate_structured_ai_summary()

        self.assertEqual(
            self.partner.ai_summary,
            "Previously validated summary.",
        )
        self.assertEqual(
            self.partner.ai_recommended_action,
            "Existing action.",
        )
        self.assertTrue(self.partner.ai_follow_up_needed)

    def test_direct_write_to_ai_fields_is_rejected(self):
        with self.assertRaises(AccessError):
            self.partner.write({
                "ai_summary": "Manually injected summary.",
            })

        self.assertNotEqual(
            self.partner.ai_summary,
            "Manually injected summary.",
        )