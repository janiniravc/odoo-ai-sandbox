from odoo.exceptions import AccessError, UserError


class OdooTools:
    """Read-only tools for retrieving data from the current Odoo environment."""

    MAX_RESULTS = 5
    MAX_QUERY_LENGTH = 100

    @staticmethod
    def lookup_customers(
        env, query, limit=5, include_email=False, include_location=False
    ):
        """Find active partners visible to the current user.

        Contact details are excluded by default. The caller may request only
        the specific optional fields relevant to the user's original question.
        Normal Odoo access rights and record rules always apply.
        """
        if env.su:
            raise AccessError(
                "AI customer lookup cannot run in superuser mode."
            )

        if not isinstance(query, str) or not query.strip():
            raise UserError("Please provide a customer name or email to search.")

        query = query.strip()
        if len(query) > OdooTools.MAX_QUERY_LENGTH:
            raise UserError(
                f"Search text cannot exceed "
                f"{OdooTools.MAX_QUERY_LENGTH} characters."
            )

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > OdooTools.MAX_RESULTS
        ):
            raise UserError(
                f"Result limit must be between 1 and "
                f"{OdooTools.MAX_RESULTS}."
            )

        if not isinstance(include_email, bool) or not isinstance(
            include_location, bool
        ):
            raise UserError("Optional customer field flags must be boolean.")

        Partner = env["res.partner"]
        Partner.check_access("read")

        domain = [
            ("active", "=", True),
            "|",
            ("name", "ilike", query),
            ("email", "ilike", query),
        ]
        fields_to_read = ["id", "name", "is_company"]
        if include_email:
            fields_to_read.append("email")
        if include_location:
            fields_to_read.extend(["city", "country_id"])

        records = Partner.search_read(
            domain,
            fields=fields_to_read,
            limit=limit,
            order="name, id",
        )

        results = []
        for record in records:
            item = {
                "id": record["id"],
                "name": record["name"],
                "is_company": record["is_company"],
            }
            if include_email:
                item["email"] = record.get("email") or None
            if include_location:
                country = record.get("country_id")
                item["city"] = record.get("city") or None
                item["country"] = country[1] if country else None
            results.append(item)

        return {
            "returned_count": len(results),
            "customers": results,
        }

    @staticmethod
    def lookup_products(env, query, limit=5):
        """Find active, saleable product templates visible to the current user.

        Only basic product identity and public list-price information are
        returned. Odoo access rights and record rules are always enforced.
        """
        if env.su:
            raise AccessError(
                "AI product lookup cannot run in superuser mode."
            )

        if not isinstance(query, str) or not query.strip():
            raise UserError("Please provide a product name or internal reference.")

        query = query.strip()
        if len(query) > OdooTools.MAX_QUERY_LENGTH:
            raise UserError(
                f"Search text cannot exceed "
                f"{OdooTools.MAX_QUERY_LENGTH} characters."
            )

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > OdooTools.MAX_RESULTS
        ):
            raise UserError(
                f"Result limit must be between 1 and "
                f"{OdooTools.MAX_RESULTS}."
            )

        Product = env["product.template"]
        Product.check_access("read")
        domain = [
            ("active", "=", True),
            ("sale_ok", "=", True),
            "|",
            ("name", "ilike", query),
            ("default_code", "ilike", query),
        ]
        records = Product.search_read(
            domain,
            fields=["id", "name", "default_code", "list_price", "currency_id"],
            limit=limit,
            order="name, id",
        )

        products = []
        for record in records:
            currency = record.get("currency_id")
            products.append({
                "id": record["id"],
                "name": record["name"],
                "default_code": record.get("default_code") or None,
                "list_price": record["list_price"],
                "currency": currency[1] if currency else None,
            })

        return {
            "returned_count": len(products),
            "products": products,
        }

    @staticmethod
    def lookup_sales_orders(env, query, limit=5):
        """Find non-cancelled sales orders by reference or customer name.

        Returns order reference, customer, order date, status, total and
        currency. Normal Odoo access rights and record rules always apply.
        """
        if env.su:
            raise AccessError(
                "AI sales order lookup cannot run in superuser mode."
            )

        if not isinstance(query, str) or not query.strip():
            raise UserError(
                "Please provide a sales order reference or customer name."
            )

        query = query.strip()
        if len(query) > OdooTools.MAX_QUERY_LENGTH:
            raise UserError(
                f"Search text cannot exceed "
                f"{OdooTools.MAX_QUERY_LENGTH} characters."
            )

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > OdooTools.MAX_RESULTS
        ):
            raise UserError(
                f"Result limit must be between 1 and "
                f"{OdooTools.MAX_RESULTS}."
            )

        SaleOrder = env["sale.order"]
        SaleOrder.check_access("read")
        records = SaleOrder.search_read(
            [
                ("state", "!=", "cancel"),
                "|",
                ("name", "ilike", query),
                ("partner_id.name", "ilike", query),
            ],
            fields=[
                "id", "name", "partner_id", "date_order",
                "state", "amount_total", "currency_id",
            ],
            limit=limit,
            order="date_order desc, id desc",
        )

        orders = []
        for record in records:
            partner = record.get("partner_id")
            currency = record.get("currency_id")
            orders.append({
                "id": record["id"],
                "name": record["name"],
                "customer": partner[1] if partner else None,
                "date_order": (
                    record["date_order"].isoformat()
                    if hasattr(record.get("date_order"), "isoformat")
                    else record.get("date_order") or None
                ),
                "state": record["state"],
                "amount_total": record["amount_total"],
                "currency": currency[1] if currency else None,
            })

        return {
            "returned_count": len(orders),
            "sales_orders": orders,
        }

    @staticmethod
    def lookup_invoices(env, query, limit=5):
        """Find customer invoices by invoice number, reference or customer.

        Only customer invoices are included. Returned financial details are
        limited to totals, outstanding balance, dates and payment status.
        Normal Odoo access rights and record rules always apply.
        """
        if env.su:
            raise AccessError(
                "AI invoice lookup cannot run in superuser mode."
            )

        if not isinstance(query, str) or not query.strip():
            raise UserError(
                "Please provide an invoice number, reference or customer name."
            )

        query = query.strip()
        if len(query) > OdooTools.MAX_QUERY_LENGTH:
            raise UserError(
                f"Search text cannot exceed "
                f"{OdooTools.MAX_QUERY_LENGTH} characters."
            )

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > OdooTools.MAX_RESULTS
        ):
            raise UserError(
                f"Result limit must be between 1 and "
                f"{OdooTools.MAX_RESULTS}."
            )

        Move = env["account.move"]
        Move.check_access("read")
        records = Move.search_read(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "!=", "cancel"),
                "|", "|",
                ("name", "ilike", query),
                ("ref", "ilike", query),
                ("partner_id.name", "ilike", query),
            ],
            fields=[
                "id", "name", "partner_id", "invoice_date",
                "invoice_date_due", "state", "payment_state",
                "amount_total", "amount_residual", "currency_id",
            ],
            limit=limit,
            order="invoice_date desc, id desc",
        )

        def serialize_date(value):
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return value or None

        invoices = []
        for record in records:
            partner = record.get("partner_id")
            currency = record.get("currency_id")
            invoices.append({
                "id": record["id"],
                "name": record["name"],
                "customer": partner[1] if partner else None,
                "invoice_date": serialize_date(record.get("invoice_date")),
                "due_date": serialize_date(record.get("invoice_date_due")),
                "state": record["state"],
                "payment_state": record.get("payment_state"),
                "amount_total": record["amount_total"],
                "amount_due": record["amount_residual"],
                "currency": currency[1] if currency else None,
            })

        return {
            "returned_count": len(invoices),
            "invoices": invoices,
        }

    @staticmethod
    def lookup_crm_leads(env, query, limit=5):
        """Find active CRM leads and opportunities by name or related owner/stage.

        Returns only concise pipeline information. Normal Odoo access rights
        and record rules always apply.
        """
        if env.su:
            raise AccessError(
                "AI CRM lead lookup cannot run in superuser mode."
            )

        if not isinstance(query, str) or not query.strip():
            raise UserError(
                "Please provide a lead, customer, salesperson or stage name."
            )

        query = query.strip()
        if len(query) > OdooTools.MAX_QUERY_LENGTH:
            raise UserError(
                f"Search text cannot exceed "
                f"{OdooTools.MAX_QUERY_LENGTH} characters."
            )

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > OdooTools.MAX_RESULTS
        ):
            raise UserError(
                f"Result limit must be between 1 and "
                f"{OdooTools.MAX_RESULTS}."
            )

        Lead = env["crm.lead"]
        Lead.check_access("read")
        records = Lead.search_read(
            [
                ("active", "=", True),
                "|", "|", "|",
                ("name", "ilike", query),
                ("partner_id.name", "ilike", query),
                ("user_id.name", "ilike", query),
                ("stage_id.name", "ilike", query),
            ],
            fields=[
                "id", "name", "partner_id", "user_id", "stage_id",
                "type", "probability", "expected_revenue", "company_currency",
            ],
            limit=limit,
            order="write_date desc, id desc",
        )

        leads = []
        for record in records:
            partner = record.get("partner_id")
            salesperson = record.get("user_id")
            stage = record.get("stage_id")
            currency = record.get("company_currency")
            leads.append({
                "id": record["id"],
                "name": record["name"],
                "customer": partner[1] if partner else None,
                "salesperson": salesperson[1] if salesperson else None,
                "stage": stage[1] if stage else None,
                "type": record["type"],
                "probability": record["probability"],
                "expected_revenue": record["expected_revenue"],
                "currency": currency[1] if currency else None,
            })

        return {
            "returned_count": len(leads),
            "leads": leads,
        }
