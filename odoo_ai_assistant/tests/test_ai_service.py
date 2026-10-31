from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase
import openai

from ..services.ai_service import (
    OdooAIService,
    CustomerAnalysis,
)


class TestOdooAIService(TransactionCase):

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_generate_customer_analysis(self, mock_openai_class):
        expected = CustomerAnalysis(
            customer_summary="A company customer.",
            recommended_action="Review the customer profile.",
            follow_up_needed=True,
        )

        mock_response = MagicMock()
        mock_response.status = "completed"
        mock_response.output_parsed = expected
        mock_openai_class.return_value.responses.parse.return_value = (
            mock_response
        )

        result = OdooAIService.generate_customer_analysis(
            customer_name="Example Ltd.",
            is_company=True,
        )

        self.assertEqual(result.customer_summary, "A company customer.")
        self.assertEqual(
            result.recommended_action,
            "Review the customer profile.",
        )
        self.assertTrue(result.follow_up_needed)

        mock_openai_class.return_value.responses.parse.assert_called_once()



    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_generate_customer_analysis_rejects_empty_result(
        self, mock_openai_class
    ):
        mock_response = MagicMock()
        mock_response.status = "completed"
        mock_response.output_parsed = None
        mock_openai_class.return_value.responses.parse.return_value = (
            mock_response
        )

        with self.assertRaises(ValueError):
            OdooAIService.generate_customer_analysis(
                customer_name="Example Ltd.",
                is_company=True,
            )

    def test_customer_analysis_rejects_empty_summary(self):
        with self.assertRaises(ValueError):
            CustomerAnalysis(
                customer_summary="   ",
                recommended_action="Review the customer profile.",
                follow_up_needed=True,
            )

    def test_customer_analysis_rejects_long_recommendation(self):
        with self.assertRaises(ValueError):
            CustomerAnalysis(
                customer_summary="A company customer.",
                recommended_action="A" * 501,
                follow_up_needed=True,
            )

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError, "OPENAI_API_KEY"
        ):
            OdooAIService.generate_customer_analysis(
                customer_name="Example Ltd.",
                is_company=True,
            )


    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_timeout_is_converted_to_safe_error(self, mock_openai_class):
        mock_openai_class.return_value.responses.parse.side_effect = (
            openai.APITimeoutError(request=MagicMock())
        )

        with self.assertRaisesRegex(ValueError, "timed out"):
            OdooAIService.generate_customer_analysis(
                customer_name="Example Ltd.",
                is_company=True,
            )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_rate_limit_is_converted_to_safe_error(self, mock_openai_class):
        mock_openai_class.return_value.responses.parse.side_effect = (
            openai.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(),
                body=None,
            )
        )

        with self.assertRaisesRegex(ValueError, "rate limit"):
            OdooAIService.generate_customer_analysis(
                customer_name="Example Ltd.",
                is_company=True,
            )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_connection_error_is_converted_to_safe_error(
        self, mock_openai_class
    ):
        mock_openai_class.return_value.responses.parse.side_effect = (
            openai.APIConnectionError(request=MagicMock())
        )

        with self.assertRaisesRegex(ValueError, "connect"):
            OdooAIService.generate_customer_analysis(
                customer_name="Example Ltd.",
                is_company=True,
            )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_incomplete_response_is_rejected(self, mock_openai_class):
        mock_response = MagicMock()
        mock_response.status = "incomplete"
        mock_response.output_parsed = None

        mock_openai_class.return_value.responses.parse.return_value = (
            mock_response
        )

        with self.assertRaisesRegex(ValueError, "did not complete"):
            OdooAIService.generate_customer_analysis(
                customer_name="Example Ltd.",
                is_company=True,
            )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_invalid_structured_data_is_rejected(self, mock_openai_class):
        mock_response = MagicMock()
        mock_response.status = "completed"
        mock_response.output_parsed = {
            "customer_summary": "",
            "recommended_action": "Review the customer profile.",
            "follow_up_needed": True,
        }

        mock_openai_class.return_value.responses.parse.return_value = (
            mock_response
        )

        with self.assertRaises(ValueError):
            OdooAIService.generate_customer_analysis(
                customer_name="Example Ltd.",
                is_company=True,
            )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("odoo.addons.odoo_ai_assistant.services.ai_service.OpenAI")
    def test_empty_text_response_is_rejected(self, mock_openai_class):
        mock_response = MagicMock()
        mock_response.status = "completed"
        mock_response.output_text = "   "

        mock_openai_class.return_value.responses.create.return_value = (
            mock_response
        )

        with self.assertRaisesRegex(ValueError, "empty response"):
            OdooAIService.generate_text("Create a short summary")

    def test_empty_prompt_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            OdooAIService.generate_text("   ")

    def test_oversized_prompt_is_rejected(self):
        prompt = "x" * (OdooAIService.MAX_PROMPT_CHARS + 1)

        with self.assertRaisesRegex(ValueError, "maximum length"):
            OdooAIService.generate_text(prompt)
