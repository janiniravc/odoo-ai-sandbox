from datetime import date, datetime, timedelta

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

    @staticmethod
    def get_crm_pipeline_report(env, report_type):
        """Return fixed, read-only CRM opportunity aggregates.

        Aggregation is performed by the ORM, which applies the current user's
        access rights and record rules. Only active opportunities are included.
        """
        if env.su:
            raise AccessError(
                "AI CRM reporting cannot run in superuser mode."
            )

        allowed_reports = {
            "pipeline_summary": None,
            "pipeline_by_stage": "stage_id",
            "pipeline_by_salesperson": "user_id",
        }
        if report_type not in allowed_reports:
            raise UserError("Unsupported CRM report type.")

        Lead = env["crm.lead"]
        Lead.check_access("read")
        domain = [
            ("active", "=", True),
            ("type", "=", "opportunity"),
            ("company_id", "in", [False, env.company.id]),
        ]
        group_field = allowed_reports[report_type]
        groupby = [group_field] if group_field else []
        grouped_values = Lead._read_group(
            domain,
            groupby=groupby,
            aggregates=[
                "__count",
                "expected_revenue:sum",
                "probability:avg",
            ],
        )

        rows = []
        for values in grouped_values:
            if group_field:
                group_record, count, expected_revenue, probability = values
                label = group_record.display_name if group_record else "Unassigned"
            else:
                count, expected_revenue, probability = values
                label = "All active opportunities"

            rows.append({
                "group": label,
                "opportunity_count": count,
                "expected_revenue": expected_revenue or 0.0,
                "average_probability": probability or 0.0,
            })

        # Keep the aggregate in one currency by limiting records to the
        # current company and company-independent opportunities.
        currency = env.company.currency_id
        return {
            "report_type": report_type,
            "currency": currency.name,
            "total_opportunities": sum(
                row["opportunity_count"] for row in rows
            ),
            "total_expected_revenue": sum(
                row["expected_revenue"] for row in rows
            ),
            "groups": rows,
        }


    @staticmethod
    def get_sales_performance_report(env, date_from, date_to, group_by="month"):
        """Aggregate confirmed sales orders over a bounded date range.

        Results are separated by transaction currency to avoid adding amounts
        that belong to different currencies. ORM grouping applies access rights
        and record rules for the current user.
        """
        if env.su:
            raise AccessError(
                "AI sales reporting cannot run in superuser mode."
            )

        if not isinstance(date_from, str) or not isinstance(date_to, str):
            raise UserError("Report dates must use YYYY-MM-DD format.")

        try:
            start_date = date.fromisoformat(date_from)
            end_date = date.fromisoformat(date_to)
        except ValueError:
            raise UserError("Report dates must use YYYY-MM-DD format.") from None

        if start_date.isoformat() != date_from or end_date.isoformat() != date_to:
            raise UserError("Report dates must use YYYY-MM-DD format.")
        if end_date < start_date:
            raise UserError("The report end date must not be before the start date.")
        if (end_date - start_date).days > 365:
            raise UserError("The report date range cannot exceed 366 days.")

        if group_by not in ("day", "week", "month"):
            raise UserError("Unsupported sales report grouping.")

        SaleOrder = env["sale.order"]
        SaleOrder.check_access("read")
        end_exclusive = end_date + timedelta(days=1)
        domain = [
            ("state", "in", ["sale", "done"]),
            ("date_order", ">=", f"{date_from} 00:00:00"),
            ("date_order", "<", f"{end_exclusive.isoformat()} 00:00:00"),
            ("company_id", "=", env.company.id),
        ]
        grouped_values = SaleOrder._read_group(
            domain,
            groupby=[f"date_order:{group_by}", "currency_id"],
            aggregates=["__count", "amount_total:sum"],
        )

        rows = []
        totals_by_currency = {}
        for period_value, currency_record, order_count, revenue in grouped_values:
            # Odoo's date_order date grouping can return a midnight
            # datetime. Report buckets are calendar dates, so serialize them
            # consistently as YYYY-MM-DD rather than including a time suffix.
            if isinstance(period_value, datetime):
                period = period_value.date().isoformat()
            elif hasattr(period_value, "isoformat"):
                period = period_value.isoformat()
            else:
                period = str(period_value)
            currency_name = currency_record.name if currency_record else None
            rows.append({
                "period": period,
                "currency": currency_name,
                "order_count": order_count,
                "revenue": revenue or 0.0,
            })
            key = currency_record.id if currency_record else False
            if key not in totals_by_currency:
                totals_by_currency[key] = {
                    "currency": currency_name,
                    "order_count": 0,
                    "revenue": 0.0,
                }
            totals_by_currency[key]["order_count"] += order_count
            totals_by_currency[key]["revenue"] += revenue or 0.0

        rows.sort(key=lambda row: (row["period"], row["currency"] or ""))
        currency_totals = sorted(
            totals_by_currency.values(),
            key=lambda item: item["currency"] or "",
        )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "group_by": group_by,
            "currency_totals": currency_totals,
            "periods": rows,
        }

    @staticmethod
    def get_top_selling_products_report(
        env, date_from, date_to, limit=5
    ):
        """Rank products by confirmed sales quantity for a bounded period.

        Revenue is reported per transaction currency and is never combined
        across currencies. ORM aggregation enforces the current user's access
        rights and record rules on sales lines and products.
        """
        if env.su:
            raise AccessError(
                "AI product reporting cannot run in superuser mode."
            )

        if not isinstance(date_from, str) or not isinstance(date_to, str):
            raise UserError("Report dates must use YYYY-MM-DD format.")
        try:
            start_date = date.fromisoformat(date_from)
            end_date = date.fromisoformat(date_to)
        except ValueError:
            raise UserError("Report dates must use YYYY-MM-DD format.") from None

        if start_date.isoformat() != date_from or end_date.isoformat() != date_to:
            raise UserError("Report dates must use YYYY-MM-DD format.")
        if end_date < start_date:
            raise UserError("The report end date must not be before the start date.")
        if (end_date - start_date).days > 365:
            raise UserError("The report date range cannot exceed 366 days.")
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 10
        ):
            raise UserError("Product report limit must be between 1 and 10.")

        SaleLine = env["sale.order.line"]
        Product = env["product.product"]
        SaleLine.check_access("read")
        Product.check_access("read")
        end_exclusive = end_date + timedelta(days=1)
        domain = [
            ("order_id.state", "in", ["sale", "done"]),
            ("order_id.date_order", ">=", f"{date_from} 00:00:00"),
            ("order_id.date_order", "<", f"{end_exclusive.isoformat()} 00:00:00"),
            ("order_id.company_id", "=", env.company.id),
            ("display_type", "=", False),
            ("product_id", "!=", False),
        ]
        grouped_values = SaleLine._read_group(
            domain,
            groupby=["product_id", "product_uom_id", "currency_id"],
            aggregates=[
                "__count",
                "product_uom_qty:sum",
                "price_subtotal:sum",
            ],
        )

        products = []
        for product, uom, currency, line_count, quantity, revenue in grouped_values:
            if not product:
                continue
            products.append({
                "product_id": product.id,
                "product": product.display_name,
                "default_code": product.default_code or None,
                "quantity_sold": quantity or 0.0,
                "uom": uom.name if uom else None,
                "sales_line_count": line_count,
                "revenue": revenue or 0.0,
                "currency": currency.name if currency else None,
            })

        # Rank by quantity, never by revenue across unlike currencies.
        products.sort(
            key=lambda item: (
                -item["quantity_sold"],
                item["product"].casefold(),
                item["currency"] or "",
            )
        )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "ranking": "quantity_sold",
            "returned_count": min(len(products), limit),
            "products": products[:limit],
        }
