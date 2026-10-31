{
    "name": "Odoo AI Assistant",
    "version": "19.0.1.0.0",
    "summary": "AI-powered customer summaries",
    "category": "Productivity",
    "license": "LGPL-3",
    "author": "Nio Digital",
    "depends": ["base"],
    "data": [
        "views/res_partner_views.xml",
        "security/ir.model.access.csv",
        "wizard/ai_chat_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}