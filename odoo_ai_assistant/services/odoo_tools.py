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

        products_by_key = {}
        for product, uom, currency, line_count, quantity, revenue in grouped_values:
            if not product:
                continue
            key = (product.id, uom.id if uom else False)
            if key not in products_by_key:
                products_by_key[key] = {
                    "product_id": product.id,
                    "product": product.display_name,
                    "default_code": product.default_code or None,
                    "quantity_sold": 0.0,
                    "uom": uom.name if uom else None,
                    "sales_line_count": 0,
                    "revenue_by_currency": {},
                }
            item = products_by_key[key]
            item["quantity_sold"] += quantity or 0.0
            item["sales_line_count"] += line_count
            currency_name = currency.name if currency else None
            if currency_name not in item["revenue_by_currency"]:
                item["revenue_by_currency"][currency_name] = 0.0
            item["revenue_by_currency"][currency_name] += revenue or 0.0

        products = list(products_by_key.values())
        for item in products:
            item["revenue_by_currency"] = [
                {"currency": currency, "revenue": revenue}
                for currency, revenue in sorted(
                    item["revenue_by_currency"].items(),
                    key=lambda pair: pair[0] or "",
                )
            ]

        # Rank by quantity, never by revenue across unlike currencies.
        products.sort(
            key=lambda item: (
                -item["quantity_sold"],
                item["product"].casefold(),
                item["uom"] or "",
            )
        )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "ranking": "quantity_sold",
            "returned_count": min(len(products), limit),
            "products": products[:limit],
        }


    @staticmethod
    def get_outstanding_receivables_report(env, date_as_of, limit=10):
        """Summarize posted, unpaid customer invoices using due-date aging.

        All amounts remain separated by invoice currency. Aggregation and
        invoice detail searches use the current user's ORM access and record
        rules and are restricted to the current company.
        """
        if env.su:
            raise AccessError(
                "AI receivables reporting cannot run in superuser mode."
            )

        if not isinstance(date_as_of, str):
            raise UserError("The report date must use YYYY-MM-DD format.")
        try:
            as_of = date.fromisoformat(date_as_of)
        except ValueError:
            raise UserError("The report date must use YYYY-MM-DD format.") from None
        if as_of.isoformat() != date_as_of:
            raise UserError("The report date must use YYYY-MM-DD format.")

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > 10
        ):
            raise UserError("The invoice detail limit must be between 1 and 10.")

        Move = env["account.move"]
        Move.check_access("read")
        base_domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("company_id", "=", env.company.id),
        ]
        buckets = [
            ("not_yet_due", "Not yet due", [("invoice_date_due", ">=", date_as_of)]),
            (
                "1_30_days",
                "1–30 days overdue",
                [
                    ("invoice_date_due", ">=", (as_of - timedelta(days=30)).isoformat()),
                    ("invoice_date_due", "<", date_as_of),
                ],
            ),
            (
                "31_60_days",
                "31–60 days overdue",
                [
                    ("invoice_date_due", ">=", (as_of - timedelta(days=60)).isoformat()),
                    ("invoice_date_due", "<", (as_of - timedelta(days=30)).isoformat()),
                ],
            ),
            (
                "61_90_days",
                "61–90 days overdue",
                [
                    ("invoice_date_due", ">=", (as_of - timedelta(days=90)).isoformat()),
                    ("invoice_date_due", "<", (as_of - timedelta(days=60)).isoformat()),
                ],
            ),
            (
                "over_90_days",
                "More than 90 days overdue",
                [("invoice_date_due", "<", (as_of - timedelta(days=90)).isoformat())],
            ),
            ("no_due_date", "No due date", [("invoice_date_due", "=", False)]),
        ]

        currency_totals = {}
        aging = []
        for key, label, date_domain in buckets:
            grouped = Move._read_group(
                base_domain + date_domain,
                groupby=["currency_id"],
                aggregates=["__count", "amount_residual:sum"],
            )
            currency_rows = []
            for currency, count, amount_due in grouped:
                currency_name = currency.name if currency else env.company.currency_id.name
                amount_due = amount_due or 0.0
                currency_rows.append({
                    "currency": currency_name,
                    "invoice_count": count,
                    "amount_due": amount_due,
                })
                total = currency_totals.setdefault(
                    currency_name,
                    {"currency": currency_name, "invoice_count": 0, "amount_due": 0.0},
                )
                total["invoice_count"] += count
                total["amount_due"] += amount_due
            aging.append({
                "bucket": key,
                "label": label,
                "currency_totals": currency_rows,
            })

        overdue_domain = base_domain + [
            ("invoice_date_due", "<", date_as_of),
        ]
        records = Move.search_read(
            overdue_domain,
            fields=[
                "id", "name", "partner_id", "invoice_date",
                "invoice_date_due", "amount_residual", "currency_id",
                "payment_state",
            ],
            limit=limit,
            order="invoice_date_due asc, id asc",
        )
        overdue_invoices = []
        for record in records:
            due_date = record.get("invoice_date_due")
            if hasattr(due_date, "date"):
                due_date = due_date.date()
            elif isinstance(due_date, str):
                due_date = date.fromisoformat(due_date)
            days_overdue = (as_of - due_date).days if due_date else None
            partner = record.get("partner_id")
            currency = record.get("currency_id")
            overdue_invoices.append({
                "id": record["id"],
                "name": record["name"],
                "customer": partner[1] if partner else None,
                "invoice_date": (
                    record["invoice_date"].isoformat()
                    if hasattr(record.get("invoice_date"), "isoformat")
                    else record.get("invoice_date") or None
                ),
                "due_date": due_date.isoformat() if due_date else None,
                "days_overdue": days_overdue,
                "amount_due": record["amount_residual"],
                "currency": currency[1] if currency else None,
                "payment_state": record.get("payment_state"),
            })

        return {
            "date_as_of": date_as_of,
            "currency_totals": list(currency_totals.values()),
            "aging": aging,
            "overdue_invoice_count_returned": len(overdue_invoices),
            "overdue_invoices": overdue_invoices,
        }



    @staticmethod
    def get_top_customers_report(env, date_from, date_to, limit=10):
        """Rank customers by confirmed sales revenue over a bounded period.

        Orders are restricted to the current company and inclusive date range.
        Contacts are consolidated under their commercial partner. Results and
        rankings remain separated by transaction currency; the limit applies
        independently to each currency. ORM aggregation enforces access rights
        and record rules for the current user.
        """
        if env.su:
            raise AccessError(
                "AI customer performance reporting cannot run in superuser mode."
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
            raise UserError("Customer report limit must be between 1 and 10.")

        SaleOrder = env["sale.order"]
        Partner = env["res.partner"]
        SaleOrder.check_access("read")
        Partner.check_access("read")
        end_exclusive = end_date + timedelta(days=1)
        domain = [
            ("state", "in", ["sale", "done"]),
            ("date_order", ">=", f"{date_from} 00:00:00"),
            ("date_order", "<", f"{end_exclusive.isoformat()} 00:00:00"),
            ("company_id", "=", env.company.id),
            ("partner_id", "!=", False),
        ]
        grouped_values = SaleOrder._read_group(
            domain,
            groupby=["partner_id", "currency_id"],
            aggregates=["__count", "amount_total:sum"],
        )

        consolidated = {}
        totals_by_currency = {}
        for partner, currency, order_count, revenue in grouped_values:
            if not partner:
                continue
            commercial_partner = partner.commercial_partner_id
            currency_name = currency.name if currency else env.company.currency_id.name
            key = (commercial_partner.id, currency_name)
            if key not in consolidated:
                consolidated[key] = {
                    "customer_id": commercial_partner.id,
                    "customer": commercial_partner.display_name,
                    "currency": currency_name,
                    "order_count": 0,
                    "revenue": 0.0,
                }
            row = consolidated[key]
            row["order_count"] += order_count
            row["revenue"] += revenue or 0.0

            total = totals_by_currency.setdefault(
                currency_name,
                {"currency": currency_name, "customer_count": 0,
                 "order_count": 0, "revenue": 0.0},
            )
            total["order_count"] += order_count
            total["revenue"] += revenue or 0.0

        by_currency = {}
        for row in consolidated.values():
            row["average_order_value"] = (
                row["revenue"] / row["order_count"]
                if row["order_count"] else 0.0
            )
            by_currency.setdefault(row["currency"], []).append(row)

        top_customers = []
        for currency_name, rows in sorted(by_currency.items()):
            rows.sort(key=lambda row: (-row["revenue"], row["customer"].casefold()))
            previous_revenue = None
            current_rank = 0
            for index, row in enumerate(rows, start=1):
                if previous_revenue is None or row["revenue"] != previous_revenue:
                    current_rank = index
                    previous_revenue = row["revenue"]
                row["rank_within_currency"] = current_rank
                if index <= limit:
                    top_customers.append(row)
            totals_by_currency[currency_name]["customer_count"] = len(rows)

        return {
            "date_from": date_from,
            "date_to": date_to,
            "ranking_basis": "revenue_within_currency",
            "limit_per_currency": limit,
            "currency_totals": sorted(
                totals_by_currency.values(), key=lambda row: row["currency"]
            ),
            "customers": top_customers,
        }


    @staticmethod
    def get_delivery_performance_report(env, date_from, date_to):
        """Report completed outgoing delivery timeliness for the current company.

        Delivery completion dates are filtered inclusively. A delivery is on
        time when its completion timestamp is not later than its scheduled
        timestamp. Records without a scheduled timestamp are reported
        separately and excluded from the on-time percentage.
        """
        if env.su:
            raise AccessError("AI delivery reporting cannot run in superuser mode.")
        if not isinstance(date_from, str) or not isinstance(date_to, str):
            raise UserError("Report dates must use YYYY-MM-DD format.")
        try:
            start_date, end_date = date.fromisoformat(date_from), date.fromisoformat(date_to)
        except ValueError:
            raise UserError("Report dates must use YYYY-MM-DD format.") from None
        if start_date.isoformat() != date_from or end_date.isoformat() != date_to:
            raise UserError("Report dates must use YYYY-MM-DD format.")
        if end_date < start_date:
            raise UserError("The report end date must not be before the start date.")
        if (end_date - start_date).days > 365:
            raise UserError("The report date range cannot exceed 366 days.")

        Picking = env["stock.picking"]
        Picking.check_access("read")
        env["res.partner"].check_access("read")
        end_exclusive = end_date + timedelta(days=1)
        domain = [
            ("picking_type_id.code", "=", "outgoing"),
            ("state", "=", "done"),
            ("date_done", ">=", f"{date_from} 00:00:00"),
            ("date_done", "<", f"{end_exclusive.isoformat()} 00:00:00"),
            ("company_id", "=", env.company.id),
        ]
        total_matching = Picking.search_count(domain)
        # Refuse to produce misleading partial KPIs for very large datasets.
        if total_matching > 5000:
            raise UserError(
                "The delivery report contains more than 5,000 records. "
                "Please use a shorter date range."
            )
        pickings = Picking.search(
            domain, order="date_done asc, id asc"
        )

        totals = {
            "completed_deliveries": 0,
            "on_time_deliveries": 0,
            "late_deliveries": 0,
            "without_scheduled_date": 0,
            "total_late_days": 0.0,
        }
        customers = {}
        for picking in pickings:
            done_at = picking.date_done
            scheduled_at = picking.scheduled_date
            partner = picking.partner_id
            partner_id = partner.id if partner else False
            partner_name = partner.display_name if partner else "Unknown customer"
            row = customers.setdefault(partner_id, {
                "customer_id": partner_id,
                "customer": partner_name,
                "completed_deliveries": 0,
                "on_time_deliveries": 0,
                "late_deliveries": 0,
                "without_scheduled_date": 0,
                "_late_days": 0.0,
            })
            totals["completed_deliveries"] += 1
            row["completed_deliveries"] += 1
            if not scheduled_at or not done_at:
                totals["without_scheduled_date"] += 1
                row["without_scheduled_date"] += 1
                continue
            delay_days = (done_at - scheduled_at).total_seconds() / 86400.0
            if delay_days <= 0:
                totals["on_time_deliveries"] += 1
                row["on_time_deliveries"] += 1
            else:
                totals["late_deliveries"] += 1
                totals["total_late_days"] += delay_days
                row["late_deliveries"] += 1
                row["_late_days"] += delay_days

        eligible = totals["on_time_deliveries"] + totals["late_deliveries"]
        totals["on_time_percentage"] = (
            round(totals["on_time_deliveries"] * 100.0 / eligible, 2)
            if eligible else None
        )
        totals["average_late_days"] = (
            round(totals["total_late_days"] / totals["late_deliveries"], 2)
            if totals["late_deliveries"] else 0.0
        )
        totals.pop("total_late_days")
        customer_rows = []
        for row in customers.values():
            eligible_customer = row["on_time_deliveries"] + row["late_deliveries"]
            row["on_time_percentage"] = (
                round(row["on_time_deliveries"] * 100.0 / eligible_customer, 2)
                if eligible_customer else None
            )
            row["average_late_days"] = (
                round(row.pop("_late_days") / row["late_deliveries"], 2)
                if row["late_deliveries"] else 0.0
            )
            if "_late_days" in row:
                row.pop("_late_days")
            customer_rows.append(row)
        customer_rows.sort(
            key=lambda row: (
                row["on_time_percentage"] is None,
                -(row["on_time_percentage"] or 0),
                row["customer"].casefold(),
            )
        )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "delivery_scope": "completed_outgoing_deliveries",
            "totals": totals,
            "customer_count": len(customer_rows),
            "customers": customer_rows,
            "note": (
                "On-time percentage excludes deliveries without a scheduled date. "
                "A delivery is on time when date_done is less than or equal to "
                "scheduled_date."
            ),
        }

    @staticmethod
    def get_sales_by_product_category_report(env, date_from, date_to, limit=10):
        """Rank categories by confirmed sales revenue; never combine currencies."""
        if env.su:
            raise AccessError("AI category sales reporting cannot run in superuser mode.")
        if not isinstance(date_from, str) or not isinstance(date_to, str):
            raise UserError("Report dates must use YYYY-MM-DD format.")
        try:
            start_date, end_date = date.fromisoformat(date_from), date.fromisoformat(date_to)
        except ValueError:
            raise UserError("Report dates must use YYYY-MM-DD format.") from None
        if start_date.isoformat() != date_from or end_date.isoformat() != date_to:
            raise UserError("Report dates must use YYYY-MM-DD format.")
        if end_date < start_date:
            raise UserError("The report end date must not be before the start date.")
        if (end_date - start_date).days > 365:
            raise UserError("The report date range cannot exceed 366 days.")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
            raise UserError("Category report limit must be between 1 and 10.")

        lines = env["sale.order.line"]
        env["product.product"].check_access("read")
        env["product.category"].check_access("read")
        lines.check_access("read")
        end_exclusive = end_date + timedelta(days=1)
        domain = [
            ("order_id.state", "in", ["sale", "done"]),
            ("order_id.date_order", ">=", f"{date_from} 00:00:00"),
            ("order_id.date_order", "<", f"{end_exclusive.isoformat()} 00:00:00"),
            ("order_id.company_id", "=", env.company.id),
            ("product_id", "!=", False),
        ]
        grouped = lines._read_group(
            domain, groupby=["product_id", "currency_id"],
            aggregates=["__count", "price_total:sum"],
        )
        by_category, totals = {}, {}
        for product, currency, line_count, revenue in grouped:
            if not product:
                continue
            category = product.categ_id
            cid = category.id if category else None
            cname = category.display_name if category else "Uncategorized"
            curr = currency.name if currency else env.company.currency_id.name
            key = (cid, curr)
            row = by_category.setdefault(key, {
                "category_id": cid, "category": cname, "currency": curr,
                "_products": set(), "sales_line_count": 0, "revenue": 0.0,
            })
            row["_products"].add(product.id)
            row["sales_line_count"] += line_count
            row["revenue"] += revenue or 0.0
            total = totals.setdefault(curr, {
                "currency": curr, "category_count": 0,
                "sales_line_count": 0, "revenue": 0.0,
            })
            total["sales_line_count"] += line_count
            total["revenue"] += revenue or 0.0

        currency_groups = {}
        for row in by_category.values():
            row["product_count"] = len(row.pop("_products"))
            currency_groups.setdefault(row["currency"], []).append(row)
        result_rows = []
        for curr, rows in sorted(currency_groups.items()):
            rows.sort(key=lambda x: (-x["revenue"], x["category"].casefold()))
            rank = 0
            previous = None
            for index, row in enumerate(rows, 1):
                if previous is None or row["revenue"] != previous:
                    rank, previous = index, row["revenue"]
                row["rank_within_currency"] = rank
                if index <= limit:
                    result_rows.append(row)
            totals[curr]["category_count"] = len(rows)
        return {
            "date_from": date_from, "date_to": date_to,
            "ranking_basis": "revenue_within_currency",
            "limit_per_currency": limit,
            "currency_totals": sorted(totals.values(), key=lambda x: x["currency"]),
            "categories": result_rows,
        }

    @staticmethod
    def get_salesperson_performance_report(env, date_from, date_to):
        """Compare salesperson order counts and revenue over a date range.

        Only confirmed orders for the current company are included. Results
        are grouped by salesperson and transaction currency; rankings are
        calculated independently within each currency. ORM aggregation
        enforces the current user's access rights and record rules.
        """
        if env.su:
            raise AccessError(
                "AI salesperson reporting cannot run in superuser mode."
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
            groupby=["user_id", "currency_id"],
            aggregates=["__count", "amount_total:sum"],
        )

        grouped_rows = []
        totals_by_currency = {}
        for salesperson, currency, order_count, revenue in grouped_values:
            salesperson_name = (
                salesperson.display_name if salesperson else "Unassigned"
            )
            currency_name = currency.name if currency else env.company.currency_id.name
            revenue = revenue or 0.0
            grouped_rows.append({
                "salesperson_id": salesperson.id if salesperson else None,
                "salesperson": salesperson_name,
                "currency": currency_name,
                "order_count": order_count,
                "revenue": revenue,
            })
            total = totals_by_currency.setdefault(
                currency_name,
                {"currency": currency_name, "order_count": 0, "revenue": 0.0},
            )
            total["order_count"] += order_count
            total["revenue"] += revenue

        # A salesperson can appear once per currency. Never rank across
        # currencies because the amounts are not directly comparable.
        grouped_rows.sort(
            key=lambda row: (
                row["currency"],
                -row["revenue"],
                row["salesperson"].casefold(),
            )
        )
        previous_currency = None
        rank = 0
        for row in grouped_rows:
            if row["currency"] != previous_currency:
                previous_currency = row["currency"]
                rank = 1
            else:
                rank += 1
            row["rank_within_currency"] = rank

        return {
            "date_from": date_from,
            "date_to": date_to,
            "currency_totals": sorted(
                totals_by_currency.values(),
                key=lambda row: row["currency"],
            ),
            "salespeople": grouped_rows,
            "ranking_basis": "revenue_within_currency",
        }

    @staticmethod
    def get_customer_sales_history_report(env, customer_query, limit=5):
        """Return lifetime sales totals and recent orders for one customer.

        Customer matching is deliberately unambiguous. Totals are grouped by
        transaction currency and never combined across currencies. ORM access
        rights and record rules apply to partners and sales orders.
        """
        if env.su:
            raise AccessError(
                "AI customer sales reporting cannot run in superuser mode."
            )

        if not isinstance(customer_query, str) or not customer_query.strip():
            raise UserError("Please provide a customer name.")
        customer_query = customer_query.strip()
        if len(customer_query) > OdooTools.MAX_QUERY_LENGTH:
            raise UserError(
                f"Search text cannot exceed {OdooTools.MAX_QUERY_LENGTH} characters."
            )
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 10
        ):
            raise UserError("Customer sales history limit must be between 1 and 10.")

        Partner = env["res.partner"]
        SaleOrder = env["sale.order"]
        Partner.check_access("read")
        SaleOrder.check_access("read")

        matches = Partner.search(
            [("active", "=", True), ("name", "ilike", customer_query)],
            limit=20,
            order="name, id",
        )
        # Contacts belonging to the same company represent one customer.
        commercial_partners = matches.mapped("commercial_partner_id")
        commercial_partners = commercial_partners.exists()
        unique_partners = commercial_partners.sorted("id")
        if not unique_partners:
            return {
                "customer": None,
                "lifetime_totals": [],
                "first_order_date": None,
                "last_order_date": None,
                "returned_order_count": 0,
                "recent_orders": [],
            }
        if len(unique_partners) != 1:
            raise UserError(
                "Customer name is ambiguous. Please provide a more specific name."
            )

        customer = unique_partners[0]
        domain = [
            ("state", "in", ["sale", "done"]),
            ("company_id", "=", env.company.id),
            ("partner_id.commercial_partner_id", "=", customer.id),
        ]
        grouped_values = SaleOrder._read_group(
            domain,
            groupby=["currency_id"],
            aggregates=[
                "__count",
                "amount_total:sum",
                "date_order:min",
                "date_order:max",
            ],
        )

        lifetime_totals = []
        first_dates = []
        last_dates = []
        for currency, order_count, revenue, first_order, last_order in grouped_values:
            lifetime_totals.append({
                "currency": currency.name if currency else None,
                "order_count": order_count,
                "lifetime_revenue": revenue or 0.0,
            })
            if first_order:
                first_dates.append(first_order)
            if last_order:
                last_dates.append(last_order)

        orders = SaleOrder.search_read(
            domain,
            fields=[
                "id", "name", "date_order", "state", "amount_total", "currency_id"
            ],
            limit=limit,
            order="date_order desc, id desc",
        )
        recent_orders = []
        for order in orders:
            currency = order.get("currency_id")
            order_date = order.get("date_order")
            recent_orders.append({
                "id": order["id"],
                "name": order["name"],
                "date_order": (
                    order_date.isoformat()
                    if hasattr(order_date, "isoformat")
                    else order_date or None
                ),
                "state": order["state"],
                "amount_total": order["amount_total"],
                "currency": currency[1] if currency else None,
            })

        lifetime_totals.sort(key=lambda item: item["currency"] or "")
        return {
            "customer": {
                "id": customer.id,
                "name": customer.display_name,
            },
            "lifetime_totals": lifetime_totals,
            "first_order_date": (
                min(first_dates).isoformat() if first_dates else None
            ),
            "last_order_date": (
                max(last_dates).isoformat() if last_dates else None
            ),
            "returned_order_count": len(recent_orders),
            "recent_orders": recent_orders,
        }

