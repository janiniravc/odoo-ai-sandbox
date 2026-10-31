import logging

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError

from ..services.ai_service import CustomerAnalysis, OdooAIService

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    ai_summary = fields.Text(
        string="AI Customer Summary",
        readonly=True,
        copy=False,
    )

    ai_recommended_action = fields.Text(
        string="AI Recommended Action",
        readonly=True,
        copy=False,
    )

    ai_follow_up_needed = fields.Boolean(
        string="AI Follow-up Needed",
        readonly=True,
        copy=False,
    )

    _AI_FIELDS = {
        "ai_summary",
        "ai_recommended_action",
        "ai_follow_up_needed",
    }

    def write(self, vals):
        if self._AI_FIELDS.intersection(vals):
            raise AccessError(
                _("AI-generated fields cannot be edited directly.")
            )
        return super().write(vals)

    def _write_ai_fields(self, vals):
        """Internal helper for trusted server-side AI actions."""
        if not vals or not set(vals).issubset(self._AI_FIELDS):
            raise ValueError("Invalid fields supplied for AI update.")

        return super(ResPartner, self).write(vals)

    def action_generate_ai_summary(self):
        self.ensure_one()

        # Verify the current user can read this customer.
        self.check_access("read")
        self.check_access("write")

        prompt = f"""
Create a concise business summary for this Odoo customer.

Customer name: {self.name or "Not provided"}
Company: {"Yes" if self.is_company else "No"}
Customer email available: {"Yes" if self.email else "No"}

Requirements:
- Describe the customer using only the information provided.
- Do not invent purchase history, payment history, or credit risk.
- Do not repeat or expose contact details.
- Keep the summary within 100 words.
"""

        try:
            summary = OdooAIService.generate_text(prompt)

            summary = summary.strip() if isinstance(summary, str) else ""

            if not summary:
                raise UserError(
                    _("The AI service returned an empty summary.")
                )

            if len(summary) > 1000:
                raise UserError(
                    _("The AI summary exceeds the maximum allowed length.")
                )

            self._write_ai_fields({"ai_summary": summary})


        except UserError:
            raise

        except Exception as exc:
            _logger.error(
                "AI summary generation failed for partner ID %s (error type: %s)",
                self.id,
                type(exc).__name__,
            )
            raise UserError(
                _("Could not generate the AI summary. Please try again later.")
            ) from None

        return True

    def action_generate_structured_ai_summary(self):
        self.ensure_one()

        self.check_access("read")
        self.check_access("write")

        try:
            result = OdooAIService.generate_customer_analysis(
                customer_name=self.name,
                is_company=self.is_company,
            )

            # Validate once more before writing to the database.
            result = CustomerAnalysis.model_validate(
                result.model_dump()
            )


        except Exception as exc:
            _logger.error(
                "Structured AI analysis failed for partner ID %s (error type: %s)",
                self.id,
                type(exc).__name__,
            )
            raise UserError(
                _("Could not generate a valid AI analysis. "
                  "Your existing summary has not been replaced. "
                  "Please try again later.")
            ) from None

        # Write only after successful validation.
        # self.write({
        #     "ai_summary": result.customer_summary,
        #     "ai_recommended_action": result.recommended_action,
        #     "ai_follow_up_needed": result.follow_up_needed,
        # })
        self._write_ai_fields({
            "ai_summary": result.customer_summary,
            "ai_recommended_action": result.recommended_action,
            "ai_follow_up_needed": result.follow_up_needed,
        })

        return True