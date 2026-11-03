from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError

from ..services.ai_tool_service import OdooAIToolService


class OdooAIChatWizard(models.TransientModel):
    _name = "odoo.ai.chat.wizard"
    _description = "Odoo AI Assistant Chat"

    question = fields.Text(
        string="Your Question",
        required=True,
    )
    answer = fields.Text(
        string="AI Response",
        readonly=True,
    )

    def action_ask_ai(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "odoo_ai_assistant.group_ai_assistant_user"
        ):
            raise AccessError(_("You are not allowed to use the AI Assistant."))

        if not self.question or not self.question.strip():
            raise UserError(_("Please enter a question."))

        # Use the current user's environment. Do not use sudo().
        answer = OdooAIToolService.ask(
            self.env,
            self.question.strip(),
        )

        self.write({"answer": answer})

        return {
            "type": "ir.actions.act_window",
            "name": _("Odoo AI Assistant"),
            "res_model": "odoo.ai.chat.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }