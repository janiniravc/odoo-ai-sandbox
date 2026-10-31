
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from openai import APIConnectionError
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from ..services.ai_tool_service import OdooAIToolService


PATCH_PATH = (
    "odoo.addons.odoo_ai_assistant.services.ai_tool_service"
)


class TestOdooAIToolService(TransactionCase):

    def setUp(self):
        super().setUp()

        self.question = "Find the customer named ABC Ltd."

        self.mock_client = MagicMock()

    def _function_call(
        self,
        name="lookup_customers",
        arguments=None,
        call_id="call_123",
    ):
        """Build a mocked OpenAI function-call item."""

        if arguments is None:
            arguments = {
                "query": "ABC Ltd.",
                "limit": 5,
            }

        return SimpleNamespace(
            type="function_call",
            name=name,
            arguments=json.dumps(arguments),
            call_id=call_id,
        )

    def _response(
        self,
        output=None,
        output_text="",
        status="completed",
    ):
        """Build a mocked OpenAI Responses API response."""

        return SimpleNamespace(
            status=status,
            output=output or [],
            output_text=output_text,
        )

    @patch(f"{PATCH_PATH}.OdooTools")
    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_successful_customer_lookup(
        self,
        mock_get_client,
        mock_odoo_tools,
    ):
        """Verify successful customer lookup and final AI response."""

        mock_get_client.return_value = self.mock_client

        function_call = self._function_call()

        self.mock_client.responses.create.side_effect = [
            self._response(output=[function_call]),
            self._response(
                output_text="I found ABC Ltd."
            ),
        ]

        mock_odoo_tools.lookup_customers.return_value = {
            "returned_count": 1,
            "customers": [
                {
                    "id": 10,
                    "name": "ABC Ltd.",
                    "is_company": True,
                    "email": "abc@example.com",
                    "city": "Ahmedabad",
                    "country": "India",
                }
            ],
        }

        answer = OdooAIToolService.ask(
            self.env,
            self.question,
        )

        self.assertEqual(answer, "I found ABC Ltd.")

        mock_get_client.assert_called_once()

        mock_odoo_tools.lookup_customers.assert_called_once_with(
            self.env,
            query="ABC Ltd.",
            limit=5,
        )

        self.assertEqual(
            self.mock_client.responses.create.call_count,
            2,
        )

        # Verify the tool result was returned to the model.
        second_call = (
            self.mock_client.responses.create.call_args_list[1]
        )

        input_items = second_call.kwargs["input"]

        tool_outputs = [
            item for item in input_items
            if isinstance(item, dict)
            and item.get("type") == "function_call_output"
        ]

        self.assertEqual(len(tool_outputs), 1)
        self.assertEqual(
            tool_outputs[0]["call_id"],
            "call_123",
        )

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_empty_question_is_rejected(self, mock_get_client):
        """An empty question should be rejected."""

        with self.assertRaisesRegex(
            UserError,
            "Please enter a question.",
        ):
            OdooAIToolService.ask(self.env, "")

        mock_get_client.assert_not_called()

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_whitespace_question_is_rejected(self, mock_get_client):
        """A whitespace-only question should be rejected."""

        with self.assertRaisesRegex(
            UserError,
            "Please enter a question.",
        ):
            OdooAIToolService.ask(self.env, "   ")

        mock_get_client.assert_not_called()

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_non_string_question_is_rejected(self, mock_get_client):
        """A non-string question should be rejected."""

        with self.assertRaises(UserError):
            OdooAIToolService.ask(self.env, 123)

        mock_get_client.assert_not_called()

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_oversized_question_is_rejected(self, mock_get_client):
        """Questions exceeding the configured maximum are rejected."""

        question = "A" * (
            OdooAIToolService.MAX_QUESTION_CHARS + 1
        )

        with self.assertRaisesRegex(
            UserError,
            "cannot exceed",
        ):
            OdooAIToolService.ask(self.env, question)

        mock_get_client.assert_not_called()

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_unsupported_tool_is_rejected(self, mock_get_client):
        """The service must reject unsupported tools."""

        mock_get_client.return_value = self.mock_client

        function_call = self._function_call(
            name="delete_customer",
            arguments={"customer_id": 10},
        )

        self.mock_client.responses.create.return_value = (
            self._response(output=[function_call])
        )

        with self.assertRaisesRegex(
            UserError,
            "unsupported tool",
        ):
            OdooAIToolService.ask(self.env, self.question)

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_invalid_json_arguments_are_rejected(self, mock_get_client):
        """Invalid JSON arguments must not be processed."""

        mock_get_client.return_value = self.mock_client

        function_call = SimpleNamespace(
            type="function_call",
            name="lookup_customers",
            arguments="{invalid json",
            call_id="call_123",
        )

        self.mock_client.responses.create.return_value = (
            self._response(output=[function_call])
        )

        with self.assertRaisesRegex(
            UserError,
            "Customer lookup could not be completed",
        ):
            OdooAIToolService.ask(self.env, self.question)

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_unexpected_argument_is_rejected(self, mock_get_client):
        """Unexpected function arguments must be rejected."""

        mock_get_client.return_value = self.mock_client

        function_call = self._function_call(
            arguments={
                "query": "ABC Ltd.",
                "limit": 5,
                "sudo": True,
            }
        )

        self.mock_client.responses.create.return_value = (
            self._response(output=[function_call])
        )

        with self.assertRaisesRegex(
            UserError,
            "Customer lookup could not be completed",
        ):
            OdooAIToolService.ask(self.env, self.question)

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_missing_argument_is_rejected(self, mock_get_client):
        """Required function arguments must be present."""

        mock_get_client.return_value = self.mock_client

        function_call = self._function_call(
            arguments={"query": "ABC Ltd."}
        )

        self.mock_client.responses.create.return_value = (
            self._response(output=[function_call])
        )

        with self.assertRaisesRegex(
            UserError,
            "Customer lookup could not be completed",
        ):
            OdooAIToolService.ask(self.env, self.question)

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_invalid_limit_is_rejected(self, mock_get_client):
        """Invalid result limits must be rejected."""

        mock_get_client.return_value = self.mock_client

        function_call = self._function_call(
            arguments={
                "query": "ABC Ltd.",
                "limit": 100,
            }
        )

        self.mock_client.responses.create.return_value = (
            self._response(output=[function_call])
        )

        with self.assertRaisesRegex(
            UserError,
            "Customer lookup could not be completed",
        ):
            OdooAIToolService.ask(self.env, self.question)

    @patch(f"{PATCH_PATH}.OdooTools")
    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_access_error_returns_generic_tool_error(
        self,
        mock_get_client,
        mock_odoo_tools,
    ):
        """Access errors should become a generic user-facing error."""

        mock_get_client.return_value = self.mock_client

        function_call = self._function_call()

        self.mock_client.responses.create.return_value = (
            self._response(output=[function_call])
        )

        mock_odoo_tools.lookup_customers.side_effect = AccessError(
            "Access denied for confidential customer data."
        )

        with self.assertRaisesRegex(
            UserError,
            "Customer lookup could not be completed. Please try again.",
        ):
            OdooAIToolService.ask(self.env, self.question)

        mock_odoo_tools.lookup_customers.assert_called_once()

        # The failed lookup must not trigger another OpenAI request.
        self.mock_client.responses.create.assert_called_once()

    @patch(f"{PATCH_PATH}.OdooTools")
    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_access_error_does_not_leak_lookup_result(
        self,
        mock_get_client,
        mock_odoo_tools,
    ):
        """Internal lookup errors must not be exposed to the user."""

        mock_get_client.return_value = self.mock_client

        function_call = self._function_call()

        self.mock_client.responses.create.return_value = (
            self._response(output=[function_call])
        )

        sensitive_error = (
            "Access denied for confidential customer: Secret Company"
        )

        mock_odoo_tools.lookup_customers.side_effect = AccessError(
            sensitive_error
        )

        with self.assertRaises(UserError) as error:
            OdooAIToolService.ask(self.env, self.question)

        self.assertEqual(
            str(error.exception),
            "Customer lookup could not be completed. Please try again.",
        )

        self.assertNotIn(
            "Secret Company",
            str(error.exception),
        )

        # Only one API request should occur.
        self.mock_client.responses.create.assert_called_once()

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_api_connection_error(self, mock_get_client):
        """Connection errors should be converted into a UserError."""

        mock_get_client.return_value = self.mock_client

        self.mock_client.responses.create.side_effect = (
            APIConnectionError(request=MagicMock())
        )

        with self.assertRaisesRegex(
            UserError,
            "temporarily unavailable",
        ):
            OdooAIToolService.ask(self.env, self.question)

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_incomplete_response_is_rejected(self, mock_get_client):
        """Incomplete OpenAI responses should not be accepted."""

        mock_get_client.return_value = self.mock_client

        self.mock_client.responses.create.return_value = (
            self._response(
                status="incomplete",
                output=[],
            )
        )

        with self.assertRaisesRegex(
            UserError,
            "could not complete the request",
        ):
            OdooAIToolService.ask(self.env, self.question)

    @patch(f"{PATCH_PATH}.OdooAIService._get_client")
    def test_empty_ai_response_is_rejected(self, mock_get_client):
        """An empty final response should be rejected."""

        mock_get_client.return_value = self.mock_client

        self.mock_client.responses.create.return_value = (
            self._response(
                status="completed",
                output=[],
                output_text="",
            )
        )

        with self.assertRaisesRegex(
            UserError,
            "empty response",
        ):
            OdooAIToolService.ask(self.env, self.question)
