
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

        self.assertEqual(
            customer["email"],
            "week2.customer@example.com",
        )

        self.assertEqual(
            customer["city"],
            "Ahmedabad",
        )

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

        self.assertEqual(
            customer["email"],
            "week2.customer@example.com",
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
