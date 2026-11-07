
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

        # Always execute customer lookups as a normal user.
        # Product templates require the standard product user group.
        product_user_group = cls.env.ref("product.group_product_user")
        product_user_group.write({"user_ids": [(4, cls.test_user.id)]})

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
