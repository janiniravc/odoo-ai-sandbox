
import os

import openai
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
from openai import APIConnectionError, APITimeoutError, APIStatusError
from odoo.exceptions import UserError


class CustomerAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    customer_summary: str = Field(
        min_length=1,
        max_length=1000,
        description="A concise factual summary of the customer.",
    )
    recommended_action: str = Field(
        min_length=1,
        max_length=500,
        description="A practical next action based only on supplied data.",
    )
    follow_up_needed: bool = Field(
        description="Whether a follow-up is recommended based on the supplied data.",
    )


class OdooAIService:

    MODEL = "gpt-6-astra"
    TIMEOUT_SECONDS = 20.0
    MAX_RETRIES = 2

    MAX_PROMPT_CHARS = 12_000
    MAX_TEXT_OUTPUT_TOKENS = 600
    MAX_ANALYSIS_OUTPUT_TOKENS = 500

    @staticmethod
    def _get_client():
        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key or not api_key.strip():
            raise ValueError(
                "OPENAI_API_KEY environment variable is not configured."
            )

        return OpenAI(
            api_key=api_key,
            timeout=OdooAIService.TIMEOUT_SECONDS,
            max_retries=OdooAIService.MAX_RETRIES,
        )

    @staticmethod
    def _validate_prompt(prompt):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("The AI prompt must not be empty.")

        if len(prompt) > OdooAIService.MAX_PROMPT_CHARS:
            raise ValueError(
                f"The AI prompt exceeds the maximum length of "
                f"{OdooAIService.MAX_PROMPT_CHARS} characters."
            )

    @staticmethod
    def _call_provider(operation):
        """Run an API operation and raise safe, actionable errors."""
        try:
            return operation()

        except openai.APITimeoutError:
            raise ValueError(
                "The AI provider request timed out. Please try again."
            ) from None

        except openai.APIConnectionError:
            raise ValueError(
                "Could not connect to the AI provider. Please try again."
            ) from None

        except openai.RateLimitError:
            raise ValueError(
                "The AI provider rate limit was reached. Please try again later."
            ) from None

        except openai.APIStatusError as exc:
            # Log the status code, not request data or credentials.
            status_code = exc.status_code
            raise ValueError(
                f"The AI provider returned an HTTP error ({status_code})."
            ) from None

        except openai.APIError:
            raise ValueError(
                "The AI provider encountered an error. Please try again."
            ) from None

    @staticmethod
    def generate_text(prompt):
        OdooAIService._validate_prompt(prompt)
        client = OdooAIService._get_client()

        try:

            response = OdooAIService._call_provider(
                lambda: client.responses.create(
                    model=OdooAIService.MODEL,
                    input=prompt,
                    max_output_tokens=OdooAIService.MAX_TEXT_OUTPUT_TOKENS,
                )
            )
        except (APIConnectionError, APITimeoutError) as exc:
            raise UserError(
                "The AI service is temporarily unavailable. "
                "Please check your internet connection and try again."
            ) from exc
        except APIStatusError as exc:
            raise UserError(
                "The AI service could not process your request. "
                "Please try again later."
            ) from exc

        if getattr(response, "status", None) != "completed":
            raise ValueError(
                "The AI response did not complete successfully."
            )

        text = response.output_text

        if not text or not text.strip():
            raise ValueError("The AI provider returned an empty response.")

        return text.strip()

    @staticmethod
    def generate_customer_analysis(customer_name, is_company):
        prompt = f"""
        Analyze this Odoo customer using only the supplied information.

        Customer name: {customer_name or "Not provided"}
        Is a company: {"Yes" if is_company else "No"}

        Rules:
        - Do not invent purchase, payment, or credit history.
        - Keep the summary concise and factual.
        - Recommend a reasonable next action.
        - Set follow_up_needed to true only if a follow-up is reasonably useful.
        """

        OdooAIService._validate_prompt(prompt)
        client = OdooAIService._get_client()



        response = OdooAIService._call_provider(
            lambda: client.responses.parse(
                model=OdooAIService.MODEL,
                input=prompt,
                text_format=CustomerAnalysis,
                max_output_tokens=OdooAIService.MAX_ANALYSIS_OUTPUT_TOKENS,
            )
        )

        if getattr(response, "status", None) != "completed":
            raise ValueError(
                "The AI response did not complete successfully."
            )

        result = response.output_parsed

        if result is None:
            raise ValueError(
                "The AI returned no structured analysis. "
                "The response may have been refused or incomplete."
            )

        if isinstance(result, dict):
            return CustomerAnalysis.model_validate(result)

        return CustomerAnalysis.model_validate(result.model_dump())
