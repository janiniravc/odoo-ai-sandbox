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
