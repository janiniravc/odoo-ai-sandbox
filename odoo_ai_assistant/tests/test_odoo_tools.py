
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from ..services.odoo_tools import OdooTools


class TestOdooTools(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create({
            "name": "Week Two AI Customer",
            "email": "week2.customer@example.com",
            "is_company": True,
            "city": "Ahmedabad",
        })

        # Find the Test AI user.
        cls.test_user = cls.env["res.users"].search(
            [("login", "=", "test_ai")],
            limit=1,
        )

        if not cls.test_user:
            raise AssertionError(
                "Test AI user must exist in the test database."
            )

        # Always execute customer and product lookups as a normal user.
        # The test user already belongs to base.group_user through the
        # AI Assistant group; do not depend on version-specific product
        # group external IDs.
        # Sales order reads are granted through the standard Sales user group.
        sales_user_group = cls.env.ref("sales_team.group_sale_salesman")
        sales_user_group.write({"user_ids": [(4, cls.test_user.id)]})
        invoice_user_group = cls.env.ref("account.group_account_invoice")
        invoice_user_group.write({"user_ids": [(4, cls.test_user.id)]})

        cls.user_env = cls.env(
            user=cls.test_user.id,
            su=False,
        )

    # ---------------------------------------------------------
    # Successful customer lookup tests
    # ---------------------------------------------------------

    def test_lookup_customer_by_name(self):
        result = OdooTools.lookup_customers(
            self.user_env,
            "Week Two AI Customer",
        )

        self.assertGreaterEqual(result["returned_count"], 1)

        customer = next(
            (
                item
                for item in result["customers"]
                if item["id"] == self.partner.id
            ),
            None,
        )

        self.assertIsNotNone(customer)

        self.assertEqual(
            customer["name"],
            "Week Two AI Customer",
        )

        self.assertTrue(customer["is_company"])

        self.assertNotIn("email", customer)
        self.assertNotIn("city", customer)
        self.assertNotIn("country", customer)

    def test_lookup_customer_by_email(self):
        result = OdooTools.lookup_customers(
            self.user_env,
            "week2.customer@example.com",
        )

        self.assertGreaterEqual(result["returned_count"], 1)

        customer = next(
            (
                item
                for item in result["customers"]
                if item["id"] == self.partner.id
            ),
            None,
        )

        self.assertIsNotNone(customer)

        # Email can be used as a search key without disclosing it to AI.
        self.assertNotIn("email", customer)

    def test_lookup_includes_only_explicitly_requested_optional_fields(self):
        result = OdooTools.lookup_customers(
            self.user_env,
            "Week Two AI Customer",
            include_email=True,
            include_location=True,
        )
        customer = next(
            item for item in result["customers"]
            if item["id"] == self.partner.id
        )
        self.assertEqual(customer["email"], "week2.customer@example.com")
        self.assertEqual(customer["city"], "Ahmedabad")
        self.assertIn("country", customer)

    def test_non_boolean_optional_field_flags_are_rejected(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                "Week Two AI Customer",
                include_email="yes",
            )

    def test_lookup_returns_expected_structure(self):
        result = OdooTools.lookup_customers(
            self.user_env,
            "Week Two AI Customer",
        )

        self.assertIn("returned_count", result)
        self.assertIn("customers", result)

        self.assertIsInstance(result["returned_count"], int)
        self.assertIsInstance(result["customers"], list)

    # ---------------------------------------------------------
    # Input validation tests
    # ---------------------------------------------------------

    def test_empty_query_is_rejected(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                "   ",
            )

    def test_invalid_query_type_is_rejected(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                123,
            )

    def test_oversized_query_is_rejected(self):
        query = "x" * (
            OdooTools.MAX_QUERY_LENGTH + 1
        )

        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                query,
            )

    # ---------------------------------------------------------
    # Result limit validation tests
    # ---------------------------------------------------------

    def test_result_limit_cannot_exceed_maximum(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                "Customer",
                limit=OdooTools.MAX_RESULTS + 1,
            )

    def test_boolean_limit_is_rejected(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                "Customer",
                limit=True,
            )

    def test_zero_limit_is_rejected(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                "Customer",
                limit=0,
            )

    def test_negative_limit_is_rejected(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                "Customer",
                limit=-1,
            )

    def test_string_limit_is_rejected(self):
        with self.assertRaises(UserError):
            OdooTools.lookup_customers(
                self.user_env,
                "Customer",
                limit="5",
            )

    # ---------------------------------------------------------
    # Security tests
    # ---------------------------------------------------------

    def test_lookup_rejects_superuser_environment(self):
        superuser_env = self.env(su=True)

        self.assertTrue(superuser_env.su)

        with self.assertRaises(AccessError):
            OdooTools.lookup_customers(
                superuser_env,
                "Week Two AI Customer",
            )

    def test_lookup_customers_respects_record_rules(self):
        """A contact hidden by a record rule must not be returned."""

        restricted_partner = self.env["res.partner"].create({
            "name": "Restricted AI Security Test Contact",
            "email": "restricted-security@example.com",
            "city": "Ahmedabad",
        })

        # Create a temporary global rule for this test transaction.
        self.env["ir.rule"].create({
            "name": "Temporary AI security test restriction",
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "domain_force": (
                "[('id', '!=', %d)]" % restricted_partner.id
            ),
            "groups": [(5, 0, 0)],
        })

        # Explicitly use the normal Test AI user environment.
        user_env = self.env(
            user=self.test_user.id,
            su=False,
        )

        self.assertFalse(user_env.su)

        result = OdooTools.lookup_customers(
            user_env,
            "Restricted AI Security Test Contact",
            limit=5,
        )

        returned_ids = [
            customer["id"]
            for customer in result["customers"]
        ]

        self.assertNotIn(
            restricted_partner.id,
            returned_ids,
            "The lookup must not return a contact hidden by a record rule.",
        )

    def test_lookup_returns_accessible_customer_with_record_rule(self):
        """Accessible contacts should remain searchable."""

        accessible_partner = self.env["res.partner"].create({
            "name": "Accessible AI Security Test Contact",
            "email": "accessible-security@example.com",
        })

        restricted_partner = self.env["res.partner"].create({
            "name": "Restricted AI Security Test Contact",
            "email": "restricted-security@example.com",
        })

        self.env["ir.rule"].create({
            "name": "Temporary AI security test restriction",
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "domain_force": (
                "[('id', '!=', %d)]" % restricted_partner.id
            ),
            "groups": [(5, 0, 0)],
        })

        user_env = self.env(
            user=self.test_user.id,
            su=False,
        )

        result = OdooTools.lookup_customers(
            user_env,
            "AI Security Test Contact",
            limit=5,
        )

        returned_ids = [
            customer["id"]
            for customer in result["customers"]
        ]

        self.assertIn(
            accessible_partner.id,
            returned_ids,
        )

        self.assertNotIn(
            restricted_partner.id,
            returned_ids,
        )

    # ---------------------------------------------------------
    # Product lookup tests
    # ---------------------------------------------------------

    def test_lookup_product_by_name(self):
        product = self.env["product.template"].create({
            "name": "AI Test Laptop",
            "default_code": "AI-LAP-001",
            "list_price": 1250.0,
            "sale_ok": True,
        })
        result = OdooTools.lookup_products(
            self.user_env,
            "AI Test Laptop",
        )
        item = next(
            (row for row in result["products"] if row["id"] == product.id),
            None,
        )
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], "AI Test Laptop")
        self.assertEqual(item["default_code"], "AI-LAP-001")
        self.assertEqual(item["list_price"], 1250.0)
        self.assertTrue(item["currency"])

    def test_lookup_product_by_internal_reference(self):
        product = self.env["product.template"].create({
            "name": "Reference Search Laptop",
            "default_code": "REF-LAP-778",
            "sale_ok": True,
        })
        result = OdooTools.lookup_products(
            self.user_env,
            "REF-LAP-778",
        )
        self.assertIn(
            product.id,
            [row["id"] for row in result["products"]],
        )

    def test_product_lookup_excludes_archived_and_non_saleable_products(self):
        archived = self.env["product.template"].create({
            "name": "Archived AI Laptop",
            "active": False,
            "sale_ok": True,
        })
        non_saleable = self.env["product.template"].create({
            "name": "Non Saleable AI Laptop",
            "sale_ok": False,
        })
        result = OdooTools.lookup_products(
            self.user_env,
            "AI Laptop",
        )
        ids = [row["id"] for row in result["products"]]
        self.assertNotIn(archived.id, ids)
        self.assertNotIn(non_saleable.id, ids)

    def test_product_lookup_rejects_superuser_environment(self):
        with self.assertRaises(AccessError):
            OdooTools.lookup_products(
                self.env(su=True),
                "Laptop",
            )

    def test_product_lookup_rejects_invalid_query(self):
        for query in ("", "   ", 123, "x" * (OdooTools.MAX_QUERY_LENGTH + 1)):
            with self.subTest(query=query):
                with self.assertRaises(UserError):
                    OdooTools.lookup_products(self.user_env, query)

    def test_product_lookup_rejects_invalid_limit(self):
        for limit in (0, -1, 6, True, "5"):
            with self.subTest(limit=limit):
                with self.assertRaises(UserError):
                    OdooTools.lookup_products(
                        self.user_env,
                        "Laptop",
                        limit=limit,
                    )

    def test_product_lookup_respects_record_rules(self):
        restricted = self.env["product.template"].create({
            "name": "Restricted AI Product",
            "sale_ok": True,
        })
        self.env["ir.rule"].create({
            "name": "Temporary AI product lookup restriction",
            "model_id": self.env["ir.model"]._get_id("product.template"),
            "domain_force": "[('id', '!=', %d)]" % restricted.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.lookup_products(
            self.user_env,
            "Restricted AI Product",
        )
        self.assertNotIn(
            restricted.id,
            [row["id"] for row in result["products"]],
        )

    # ---------------------------------------------------------
    # Sales order lookup tests
    # ---------------------------------------------------------

    def _create_sales_order(self, name, customer_name="AI Sales Order Customer"):
        partner = self.env["res.partner"].create({"name": customer_name})
        return self.env["sale.order"].create({
            "name": name,
            "partner_id": partner.id,
            # Sales order record rules commonly restrict access to orders
            # assigned to the current salesperson. Make the fixture visible
            # to the normal user used by the lookup tests.
            "user_id": self.test_user.id,
        })

    def test_lookup_sales_order_by_reference(self):
        order = self._create_sales_order("AI-SO-REF-001")
        result = OdooTools.lookup_sales_orders(
            self.user_env,
            "AI-SO-REF-001",
        )
        item = next(
            (row for row in result["sales_orders"] if row["id"] == order.id),
            None,
        )
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], "AI-SO-REF-001")
        self.assertEqual(item["customer"], "AI Sales Order Customer")
        self.assertEqual(item["state"], "draft")
        self.assertEqual(item["amount_total"], 0.0)
        self.assertTrue(item["currency"])
        self.assertTrue(item["date_order"])

    def test_lookup_sales_order_by_customer_name(self):
        order = self._create_sales_order(
            "AI-SO-CUSTOMER-002",
            customer_name="Customer Search Example",
        )
        result = OdooTools.lookup_sales_orders(
            self.user_env,
            "Customer Search Example",
        )
        self.assertIn(
            order.id,
            [row["id"] for row in result["sales_orders"]],
        )

    def test_sales_order_lookup_excludes_cancelled_orders(self):
        order = self._create_sales_order("AI-SO-CANCEL-003")
        order.write({"state": "cancel"})
        result = OdooTools.lookup_sales_orders(
            self.user_env,
            "AI-SO-CANCEL-003",
        )
        self.assertNotIn(
            order.id,
            [row["id"] for row in result["sales_orders"]],
        )

    def test_sales_order_lookup_rejects_superuser_environment(self):
        with self.assertRaises(AccessError):
            OdooTools.lookup_sales_orders(
                self.env(su=True),
                "AI-SO",
            )

    def test_sales_order_lookup_rejects_invalid_query(self):
        for query in ("", "   ", 123, "x" * (OdooTools.MAX_QUERY_LENGTH + 1)):
            with self.subTest(query=query):
                with self.assertRaises(UserError):
                    OdooTools.lookup_sales_orders(self.user_env, query)

    def test_sales_order_lookup_rejects_invalid_limit(self):
        for limit in (0, -1, 6, True, "5"):
            with self.subTest(limit=limit):
                with self.assertRaises(UserError):
                    OdooTools.lookup_sales_orders(
                        self.user_env,
                        "AI-SO",
                        limit=limit,
                    )

    def test_sales_order_lookup_respects_record_rules(self):
        order = self._create_sales_order("AI-SO-RESTRICTED-004")
        self.env["ir.rule"].create({
            "name": "Temporary AI sales order lookup restriction",
            "model_id": self.env["ir.model"]._get_id("sale.order"),
            "domain_force": "[('id', '!=', %d)]" % order.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.lookup_sales_orders(
            self.user_env,
            "AI-SO-RESTRICTED-004",
        )
        self.assertNotIn(
            order.id,
            [row["id"] for row in result["sales_orders"]],
        )


    # ---------------------------------------------------------
    # Customer invoice lookup tests
    # ---------------------------------------------------------

    def _create_customer_invoice(self, customer_name="Invoice Lookup Customer"):
        partner = self.env["res.partner"].create({"name": customer_name})
        income_account = self.env["account.account"].search([
            ("account_type", "=", "income"),
            ("company_ids", "in", self.env.company.id),
        ], limit=1)
        if not income_account:
            raise AssertionError("An income account is required for invoice tests.")
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": "2026-10-01",
            "invoice_date_due": "2026-10-31",
            "invoice_line_ids": [(0, 0, {
                "name": "AI invoice test service",
                "quantity": 2,
                "price_unit": 125.0,
                "account_id": income_account.id,
            })],
        })
        invoice.action_post()
        return invoice

    def test_lookup_invoice_by_number(self):
        invoice = self._create_customer_invoice()
        result = OdooTools.lookup_invoices(self.user_env, invoice.name)
        item = next(
            (row for row in result["invoices"] if row["id"] == invoice.id),
            None,
        )
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], invoice.name)
        self.assertEqual(item["customer"], "Invoice Lookup Customer")
        self.assertEqual(item["state"], "posted")
        self.assertEqual(item["payment_state"], "not_paid")
        self.assertEqual(item["amount_total"], 250.0)
        self.assertEqual(item["amount_due"], 250.0)
        self.assertTrue(item["currency"])
        self.assertEqual(item["invoice_date"], "2026-10-01")
        self.assertEqual(item["due_date"], "2026-10-31")

    def test_lookup_invoice_by_customer_name(self):
        invoice = self._create_customer_invoice("Invoice Customer Search")
        result = OdooTools.lookup_invoices(
            self.user_env,
            "Invoice Customer Search",
        )
        self.assertIn(
            invoice.id,
            [row["id"] for row in result["invoices"]],
        )

    def test_invoice_lookup_excludes_cancelled_invoices(self):
        invoice = self._create_customer_invoice("Cancelled Invoice Customer")
        invoice.button_cancel()
        result = OdooTools.lookup_invoices(self.user_env, invoice.name)
        self.assertNotIn(
            invoice.id,
            [row["id"] for row in result["invoices"]],
        )

    def test_invoice_lookup_rejects_superuser_environment(self):
        with self.assertRaises(AccessError):
            OdooTools.lookup_invoices(self.env(su=True), "INV")

    def test_invoice_lookup_rejects_invalid_query_and_limit(self):
        for query in ("", "   ", 123, "x" * (OdooTools.MAX_QUERY_LENGTH + 1)):
            with self.subTest(query=query):
                with self.assertRaises(UserError):
                    OdooTools.lookup_invoices(self.user_env, query)
        for limit in (0, -1, 6, True, "5"):
            with self.subTest(limit=limit):
                with self.assertRaises(UserError):
                    OdooTools.lookup_invoices(
                        self.user_env,
                        "INV",
                        limit=limit,
                    )

    def test_invoice_lookup_respects_record_rules(self):
        invoice = self._create_customer_invoice("Restricted Invoice Customer")
        self.env["ir.rule"].create({
            "name": "Temporary AI invoice lookup restriction",
            "model_id": self.env["ir.model"]._get_id("account.move"),
            "domain_force": "[('id', '!=', %d)]" % invoice.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.lookup_invoices(
            self.user_env,
            "Restricted Invoice Customer",
        )
        self.assertNotIn(
            invoice.id,
            [row["id"] for row in result["invoices"]],
        )

    # ---------------------------------------------------------
    # CRM lead lookup tests
    # ---------------------------------------------------------

    def _create_crm_lead(self, name, **values):
        vals = {
            "name": name,
            "user_id": self.test_user.id,
            "type": "opportunity",
        }
        vals.update(values)
        return self.env["crm.lead"].create(vals)

    def test_lookup_crm_lead_by_name(self):
        lead = self._create_crm_lead("AI CRM Pipeline Upgrade")
        result = OdooTools.lookup_crm_leads(
            self.user_env,
            "AI CRM Pipeline Upgrade",
        )
        item = next(
            (row for row in result["leads"] if row["id"] == lead.id),
            None,
        )
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], "AI CRM Pipeline Upgrade")
        self.assertEqual(item["type"], "opportunity")
        self.assertEqual(item["salesperson"], self.test_user.name)
        self.assertIn("stage", item)
        self.assertIn("expected_revenue", item)
        self.assertIn("currency", item)

    def test_lookup_crm_lead_by_customer_name(self):
        customer = self.env["res.partner"].create({
            "name": "CRM Search Customer Example",
        })
        lead = self._create_crm_lead(
            "New ERP Opportunity",
            partner_id=customer.id,
        )
        result = OdooTools.lookup_crm_leads(
            self.user_env,
            "CRM Search Customer Example",
        )
        self.assertIn(
            lead.id,
            [row["id"] for row in result["leads"]],
        )

    def test_lookup_crm_lead_by_salesperson_name(self):
        lead = self._create_crm_lead("Salesperson Search Opportunity")
        result = OdooTools.lookup_crm_leads(
            self.user_env,
            self.test_user.name,
        )
        self.assertIn(
            lead.id,
            [row["id"] for row in result["leads"]],
        )

    def test_lookup_crm_lead_by_pipeline_stage(self):
        lead = self._create_crm_lead("Pipeline Stage Search Opportunity")
        self.assertTrue(lead.stage_id)
        result = OdooTools.lookup_crm_leads(
            self.user_env,
            lead.stage_id.name,
        )
        self.assertIn(
            lead.id,
            [row["id"] for row in result["leads"]],
        )

    def test_crm_lead_lookup_rejects_superuser_environment(self):
        with self.assertRaises(AccessError):
            OdooTools.lookup_crm_leads(
                self.env(su=True),
                "CRM",
            )

    def test_crm_lead_lookup_rejects_invalid_query_and_limit(self):
        for query in ("", "   ", 123, "x" * (OdooTools.MAX_QUERY_LENGTH + 1)):
            with self.subTest(query=query):
                with self.assertRaises(UserError):
                    OdooTools.lookup_crm_leads(self.user_env, query)
        for limit in (0, -1, 6, True, "5"):
            with self.subTest(limit=limit):
                with self.assertRaises(UserError):
                    OdooTools.lookup_crm_leads(
                        self.user_env,
                        "CRM",
                        limit=limit,
                    )

    def test_crm_lead_lookup_respects_record_rules(self):
        lead = self._create_crm_lead("Restricted CRM Lead Record")
        self.env["ir.rule"].create({
            "name": "Temporary AI CRM lead lookup restriction",
            "model_id": self.env["ir.model"]._get_id("crm.lead"),
            "domain_force": "[('id', '!=', %d)]" % lead.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.lookup_crm_leads(
            self.user_env,
            "Restricted CRM Lead Record",
        )
        self.assertNotIn(
            lead.id,
            [row["id"] for row in result["leads"]],
        )

    # ---------------------------------------------------------
    # CRM aggregate reporting tests
    # ---------------------------------------------------------

    def test_crm_pipeline_summary_report(self):
        self._create_crm_lead(
            "AI Report Summary Opportunity 1",
            expected_revenue=1200.0,
            probability=50.0,
        )
        self._create_crm_lead(
            "AI Report Summary Opportunity 2",
            expected_revenue=800.0,
            probability=75.0,
        )
        result = OdooTools.get_crm_pipeline_report(
            self.user_env,
            "pipeline_summary",
        )
        self.assertEqual(result["report_type"], "pipeline_summary")
        self.assertGreaterEqual(result["total_opportunities"], 2)
        self.assertGreaterEqual(result["total_expected_revenue"], 2000.0)
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(
            result["groups"][0]["group"],
            "All active opportunities",
        )

    def test_crm_pipeline_report_groups_by_stage(self):
        lead = self._create_crm_lead(
            "AI Report Stage Opportunity",
            expected_revenue=1500.0,
        )
        result = OdooTools.get_crm_pipeline_report(
            self.user_env,
            "pipeline_by_stage",
        )
        matching = [
            row for row in result["groups"]
            if row["group"] == lead.stage_id.display_name
        ]
        self.assertTrue(matching)
        self.assertGreaterEqual(matching[0]["opportunity_count"], 1)
        self.assertGreaterEqual(matching[0]["expected_revenue"], 1500.0)

    def test_crm_pipeline_report_groups_by_salesperson(self):
        self._create_crm_lead(
            "AI Report Salesperson Opportunity",
            expected_revenue=900.0,
        )
        result = OdooTools.get_crm_pipeline_report(
            self.user_env,
            "pipeline_by_salesperson",
        )
        matching = [
            row for row in result["groups"]
            if row["group"] == self.test_user.display_name
        ]
        self.assertTrue(matching)
        self.assertGreaterEqual(matching[0]["opportunity_count"], 1)

    def test_crm_pipeline_report_rejects_superuser(self):
        with self.assertRaises(AccessError):
            OdooTools.get_crm_pipeline_report(
                self.env(su=True),
                "pipeline_summary",
            )

    def test_crm_pipeline_report_rejects_unsupported_type(self):
        with self.assertRaises(UserError):
            OdooTools.get_crm_pipeline_report(
                self.user_env,
                "arbitrary_domain",
            )

    def test_crm_pipeline_report_respects_record_rules(self):
        lead = self._create_crm_lead(
            "AI Report Restricted Opportunity",
            expected_revenue=999999.0,
        )
        self.env["ir.rule"].create({
            "name": "Temporary AI CRM report restriction",
            "model_id": self.env["ir.model"]._get_id("crm.lead"),
            "domain_force": "[('id', '!=', %d)]" % lead.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.get_crm_pipeline_report(
            self.user_env,
            "pipeline_summary",
        )
        self.assertNotIn(
            999999.0,
            [row["expected_revenue"] for row in result["groups"]],
        )


    # ---------------------------------------------------------
    # Sales performance reporting tests
    # ---------------------------------------------------------

    def _create_confirmed_sales_order(self, name, order_date, state="sale"):
        order = self._create_sales_order(name)
        if state in ("sale", "done"):
            order.action_confirm()
            # Confirmation can update date_order; set the fixture date after
            # confirming so the report date-domain tests are deterministic.
            order.write({"date_order": f"{order_date} 12:00:00"})
        if state == "done":
            order.write({"state": "done"})
        return order

    def test_sales_performance_report_groups_confirmed_orders_by_month(self):
        first = self._create_confirmed_sales_order(
            "AI-REPORT-SALE-2026-01", "2026-01-15"
        )
        second = self._create_confirmed_sales_order(
            "AI-REPORT-SALE-2026-02", "2026-02-10"
        )
        result = OdooTools.get_sales_performance_report(
            self.user_env,
            "2026-01-01",
            "2026-02-28",
            "month",
        )
        self.assertEqual(result["date_from"], "2026-01-01")
        self.assertEqual(result["date_to"], "2026-02-28")
        self.assertEqual(result["group_by"], "month")
        self.assertTrue(result["currency_totals"])
        self.assertEqual(
            sum(item["order_count"] for item in result["currency_totals"]),
            2,
        )
        self.assertEqual(
            {row["period"] for row in result["periods"]},
            {"2026-01-01", "2026-02-01"},
        )
        self.assertEqual(
            sum(row["order_count"] for row in result["periods"]),
            2,
        )

    def test_sales_performance_report_excludes_draft_cancelled_and_out_of_range(self):
        draft = self._create_sales_order("AI-REPORT-DRAFT")
        draft.write({"date_order": "2026-01-15 12:00:00"})
        cancelled = self._create_sales_order("AI-REPORT-CANCEL")
        cancelled.write({"date_order": "2026-01-16 12:00:00"})
        cancelled.action_cancel()
        outside = self._create_confirmed_sales_order(
            "AI-REPORT-OUTSIDE", "2026-02-01"
        )
        included = self._create_confirmed_sales_order(
            "AI-REPORT-INCLUDED", "2026-01-20"
        )
        result = OdooTools.get_sales_performance_report(
            self.user_env,
            "2026-01-01",
            "2026-01-31",
        )
        self.assertEqual(
            sum(item["order_count"] for item in result["currency_totals"]),
            1,
        )
        self.assertEqual(
            sum(item["order_count"] for item in result["periods"]),
            1,
        )

    def test_sales_performance_report_rejects_superuser(self):
        with self.assertRaises(AccessError):
            OdooTools.get_sales_performance_report(
                self.env(su=True),
                "2026-01-01",
                "2026-01-31",
            )

    def test_sales_performance_report_validates_dates_and_grouping(self):
        invalid_cases = [
            ("2026-02-01", "2026-01-01", "month"),
            ("not-a-date", "2026-01-31", "month"),
            ("2026-01-01", "2026-01-31", "year"),
            ("2025-01-01", "2026-01-02", "month"),
        ]
        for date_from, date_to, group_by in invalid_cases:
            with self.subTest(date_from=date_from, date_to=date_to, group_by=group_by):
                with self.assertRaises(UserError):
                    OdooTools.get_sales_performance_report(
                        self.user_env,
                        date_from,
                        date_to,
                        group_by,
                    )

    def test_sales_performance_report_respects_record_rules(self):
        order = self._create_confirmed_sales_order(
            "AI-REPORT-RESTRICTED", "2026-01-20"
        )
        self.env["ir.rule"].create({
            "name": "Temporary AI sales report restriction",
            "model_id": self.env["ir.model"]._get_id("sale.order"),
            "domain_force": "[('id', '!=', %d)]" % order.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.get_sales_performance_report(
            self.user_env,
            "2026-01-01",
            "2026-01-31",
        )
        self.assertEqual(
            sum(item["order_count"] for item in result["currency_totals"]),
            0,
        )


    # ---------------------------------------------------------
    # Top-selling products reporting tests
    # ---------------------------------------------------------

    def _create_product_sales_order(self, order_name, order_date, product_quantities):
        order = self._create_sales_order(order_name)
        for product, quantity in product_quantities:
            self.env["sale.order.line"].create({
                "order_id": order.id,
                "product_id": product.id,
                "name": product.display_name,
                "product_uom_id": product.uom_id.id,
                "product_uom_qty": quantity,
                "price_unit": product.lst_price,
            })
        order.action_confirm()
        order.write({"date_order": f"{order_date} 12:00:00"})
        return order

    def test_top_selling_products_report_ranks_confirmed_quantity(self):
        product_a = self.env["product.product"].create({
            "name": "AI Top Seller Product A",
            "sale_ok": True,
            "list_price": 100.0,
        })
        product_b = self.env["product.product"].create({
            "name": "AI Top Seller Product B",
            "sale_ok": True,
            "list_price": 50.0,
        })
        self._create_product_sales_order(
            "AI-TOP-SELLER-ORDER-1",
            "2026-03-10",
            [(product_a, 2), (product_b, 5)],
        )
        self._create_product_sales_order(
            "AI-TOP-SELLER-ORDER-2",
            "2026-03-20",
            [(product_a, 4)],
        )

        result = OdooTools.get_top_selling_products_report(
            self.user_env,
            "2026-03-01",
            "2026-03-31",
            limit=5,
        )
        self.assertEqual(result["ranking"], "quantity_sold")
        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["products"][0]["product_id"], product_a.id)
        self.assertEqual(result["products"][0]["quantity_sold"], 6.0)
        self.assertEqual(result["products"][1]["product_id"], product_b.id)
        self.assertEqual(result["products"][1]["quantity_sold"], 5.0)
        self.assertTrue(result["products"][0]["revenue_by_currency"])
        self.assertTrue(result["products"][0]["uom"])

    def test_top_selling_products_report_excludes_draft_and_out_of_range(self):
        product = self.env["product.product"].create({
            "name": "AI Top Seller Date Filter Product",
            "sale_ok": True,
            "list_price": 25.0,
        })
        draft = self._create_sales_order("AI-TOP-SELLER-DRAFT")
        self.env["sale.order.line"].create({
            "order_id": draft.id,
            "product_id": product.id,
            "name": product.display_name,
            "product_uom_id": product.uom_id.id,
            "product_uom_qty": 99,
            "price_unit": product.lst_price,
        })
        self._create_product_sales_order(
            "AI-TOP-SELLER-OUTSIDE",
            "2026-04-01",
            [(product, 7)],
        )
        self._create_product_sales_order(
            "AI-TOP-SELLER-INCLUDED",
            "2026-03-15",
            [(product, 3)],
        )
        result = OdooTools.get_top_selling_products_report(
            self.user_env,
            "2026-03-01",
            "2026-03-31",
        )
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["products"][0]["quantity_sold"], 3.0)

    def test_top_selling_products_report_rejects_superuser(self):
        with self.assertRaises(AccessError):
            OdooTools.get_top_selling_products_report(
                self.env(su=True),
                "2026-03-01",
                "2026-03-31",
            )

    def test_top_selling_products_report_validates_dates_and_limit(self):
        invalid_cases = [
            ("2026-04-01", "2026-03-01", 5),
            ("not-a-date", "2026-03-31", 5),
            ("2025-03-01", "2026-03-02", 5),
            ("2026-03-01", "2026-03-31", 0),
            ("2026-03-01", "2026-03-31", 11),
            ("2026-03-01", "2026-03-31", True),
        ]
        for date_from, date_to, limit in invalid_cases:
            with self.subTest(date_from=date_from, date_to=date_to, limit=limit):
                with self.assertRaises(UserError):
                    OdooTools.get_top_selling_products_report(
                        self.user_env,
                        date_from,
                        date_to,
                        limit=limit,
                    )

    def test_top_selling_products_report_respects_sales_line_record_rules(self):
        product = self.env["product.product"].create({
            "name": "AI Restricted Top Seller Product",
            "sale_ok": True,
            "list_price": 10.0,
        })
        order = self._create_product_sales_order(
            "AI-TOP-SELLER-RESTRICTED",
            "2026-03-15",
            [(product, 8)],
        )
        line = order.order_line.filtered(lambda item: item.product_id == product)
        self.env["ir.rule"].create({
            "name": "Temporary AI top-selling line restriction",
            "model_id": self.env["ir.model"]._get_id("sale.order.line"),
            "domain_force": "[('id', '!=', %d)]" % line.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.get_top_selling_products_report(
            self.user_env,
            "2026-03-01",
            "2026-03-31",
        )
        self.assertNotIn(
            product.id,
            [row["product_id"] for row in result["products"]],
        )

    # ---------------------------------------------------------
    # Customer lifetime sales history tests
    # ---------------------------------------------------------

    def test_customer_sales_history_returns_lifetime_totals_and_recent_orders(self):
        customer = self.env["res.partner"].create({
            "name": "AI Lifetime History Customer",
            "is_company": True,
        })
        first = self.env["sale.order"].create({
            "partner_id": customer.id,
            "user_id": self.test_user.id,
        })
        first.action_confirm()
        first.write({"date_order": "2025-01-15 12:00:00"})
        second = self.env["sale.order"].create({
            "partner_id": customer.id,
            "user_id": self.test_user.id,
        })
        second.action_confirm()
        second.write({"date_order": "2026-02-20 12:00:00"})

        result = OdooTools.get_customer_sales_history_report(
            self.user_env,
            "AI Lifetime History Customer",
            limit=5,
        )
        self.assertEqual(
            result["customer"]["id"],
            customer.id,
        )
        self.assertEqual(
            result["lifetime_totals"][0]["order_count"],
            2,
        )
        self.assertEqual(
            result["lifetime_totals"][0]["lifetime_revenue"],
            first.amount_total + second.amount_total,
        )
        self.assertEqual(result["first_order_date"], "2025-01-15T12:00:00")
        self.assertEqual(result["last_order_date"], "2026-02-20T12:00:00")
        self.assertEqual(result["returned_order_count"], 2)
        self.assertEqual(
            {row["id"] for row in result["recent_orders"]},
            {first.id, second.id},
        )

    def test_customer_sales_history_excludes_draft_cancelled_and_other_company_orders(self):
        customer = self.env["res.partner"].create({
            "name": "AI Lifetime Filter Customer",
            "is_company": True,
        })
        draft = self.env["sale.order"].create({
            "partner_id": customer.id,
            "user_id": self.test_user.id,
        })
        cancelled = self.env["sale.order"].create({
            "partner_id": customer.id,
            "user_id": self.test_user.id,
        })
        cancelled.action_cancel()
        confirmed = self.env["sale.order"].create({
            "partner_id": customer.id,
            "user_id": self.test_user.id,
        })
        confirmed.action_confirm()

        result = OdooTools.get_customer_sales_history_report(
            self.user_env,
            "AI Lifetime Filter Customer",
        )
        self.assertEqual(result["lifetime_totals"][0]["order_count"], 1)
        self.assertEqual(
            [row["id"] for row in result["recent_orders"]],
            [confirmed.id],
        )
        self.assertNotIn(draft.id, [row["id"] for row in result["recent_orders"]])
        self.assertNotIn(cancelled.id, [row["id"] for row in result["recent_orders"]])

    def test_customer_sales_history_returns_empty_result_for_unknown_customer(self):
        result = OdooTools.get_customer_sales_history_report(
            self.user_env,
            "No Such AI Customer Exists",
        )
        self.assertIsNone(result["customer"])
        self.assertEqual(result["lifetime_totals"], [])
        self.assertEqual(result["recent_orders"], [])

    def test_customer_sales_history_rejects_ambiguous_customer_name(self):
        self.env["res.partner"].create({"name": "AI Ambiguous History Customer"})
        self.env["res.partner"].create({"name": "AI Ambiguous History Customer"})
        with self.assertRaisesRegex(UserError, "ambiguous"):
            OdooTools.get_customer_sales_history_report(
                self.user_env,
                "AI Ambiguous History Customer",
            )

    def test_customer_sales_history_validates_query_and_limit(self):
        for query in ("", "   ", 123, "x" * (OdooTools.MAX_QUERY_LENGTH + 1)):
            with self.subTest(query=query):
                with self.assertRaises(UserError):
                    OdooTools.get_customer_sales_history_report(
                        self.user_env,
                        query,
                    )
        for limit in (0, -1, 11, True, "5"):
            with self.subTest(limit=limit):
                with self.assertRaises(UserError):
                    OdooTools.get_customer_sales_history_report(
                        self.user_env,
                        "AI Lifetime History Customer",
                        limit=limit,
                    )

    def test_customer_sales_history_rejects_superuser(self):
        with self.assertRaises(AccessError):
            OdooTools.get_customer_sales_history_report(
                self.env(su=True),
                "AI Lifetime History Customer",
            )

    def test_customer_sales_history_respects_sales_order_record_rules(self):
        customer = self.env["res.partner"].create({
            "name": "AI Lifetime Restricted Customer",
            "is_company": True,
        })
        order = self.env["sale.order"].create({
            "partner_id": customer.id,
            "user_id": self.test_user.id,
        })
        order.action_confirm()
        self.env["ir.rule"].create({
            "name": "Temporary AI customer lifetime history restriction",
            "model_id": self.env["ir.model"]._get_id("sale.order"),
            "domain_force": "[('id', '!=', %d)]" % order.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.get_customer_sales_history_report(
            self.user_env,
            "AI Lifetime Restricted Customer",
        )
        self.assertEqual(result["lifetime_totals"], [])
        self.assertEqual(result["recent_orders"], [])



    # ---------------------------------------------------------
    # Outstanding receivables report tests
    # ---------------------------------------------------------

    def _create_receivables_invoice(self, customer_name, due_date, amount=250.0):
        partner = self.env["res.partner"].create({"name": customer_name})
        income_account = self.env["account.account"].search([
            ("account_type", "=", "income"),
            ("company_ids", "in", self.env.company.id),
        ], limit=1)
        if not income_account:
            raise AssertionError("An income account is required for invoice tests.")
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": "2026-01-01",
            "invoice_date_due": due_date,
            "invoice_line_ids": [(0, 0, {
                "name": "AI receivables test service",
                "quantity": 1,
                "price_unit": amount,
                "account_id": income_account.id,
            })],
        })
        invoice.action_post()
        return invoice

    def test_outstanding_receivables_report_returns_aging_and_overdue_details(self):
        overdue = self._create_receivables_invoice(
            "AI Receivables Overdue Customer", "2026-09-15", 250.0
        )
        current = self._create_receivables_invoice(
            "AI Receivables Current Customer", "2026-12-15", 500.0
        )
        result = OdooTools.get_outstanding_receivables_report(
            self.user_env, "2026-11-10", limit=5
        )
        totals = {row["currency"]: row for row in result["currency_totals"]}
        currency = self.env.company.currency_id.name
        self.assertEqual(totals[currency]["invoice_count"], 2)
        self.assertEqual(totals[currency]["amount_due"], 750.0)
        buckets = {row["bucket"]: row for row in result["aging"]}
        overdue_total = sum(
            row["amount_due"]
            for row in buckets["1_30_days"]["currency_totals"]
        )
        self.assertEqual(overdue_total, 250.0)
        current_total = sum(
            row["amount_due"]
            for row in buckets["not_yet_due"]["currency_totals"]
        )
        self.assertEqual(current_total, 500.0)
        detail = next(
            row for row in result["overdue_invoices"]
            if row["id"] == overdue.id
        )
        self.assertEqual(detail["days_overdue"], 56)
        self.assertEqual(detail["amount_due"], 250.0)
        self.assertNotIn(
            current.id,
            [row["id"] for row in result["overdue_invoices"]],
        )

    def test_outstanding_receivables_excludes_draft_and_cancelled_invoices(self):
        draft = self._create_receivables_invoice(
            "AI Receivables Draft Customer", "2026-10-01"
        )
        draft.button_draft()
        cancelled = self._create_receivables_invoice(
            "AI Receivables Cancelled Customer", "2026-10-01"
        )
        cancelled.button_cancel()
        result = OdooTools.get_outstanding_receivables_report(
            self.user_env, "2026-11-10"
        )
        self.assertEqual(result["currency_totals"], [])
        self.assertEqual(result["overdue_invoices"], [])

    def test_outstanding_receivables_rejects_superuser(self):
        with self.assertRaises(AccessError):
            OdooTools.get_outstanding_receivables_report(
                self.env(su=True), "2026-11-10"
            )

    def test_outstanding_receivables_validates_date_and_limit(self):
        for date_value in ("", "2026-2-01", "not-a-date", 20261110):
            with self.subTest(date_value=date_value):
                with self.assertRaises(UserError):
                    OdooTools.get_outstanding_receivables_report(
                        self.user_env, date_value
                    )
        for limit in (0, 11, True, "5"):
            with self.subTest(limit=limit):
                with self.assertRaises(UserError):
                    OdooTools.get_outstanding_receivables_report(
                        self.user_env, "2026-11-10", limit=limit
                    )

    def test_outstanding_receivables_respects_invoice_record_rules(self):
        invoice = self._create_receivables_invoice(
            "AI Receivables Restricted Customer", "2026-10-01"
        )
        self.env["ir.rule"].create({
            "name": "Temporary AI receivables invoice restriction",
            "model_id": self.env["ir.model"]._get_id("account.move"),
            "domain_force": "[('id', '!=', %d)]" % invoice.id,
            "groups": [(5, 0, 0)],
        })
        result = OdooTools.get_outstanding_receivables_report(
            self.user_env, "2026-11-10"
        )
        self.assertNotIn(
            invoice.id,
            [row["id"] for row in result["overdue_invoices"]],
        )
        self.assertEqual(result["currency_totals"], [])

