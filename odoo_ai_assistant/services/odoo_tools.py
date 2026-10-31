from odoo.exceptions import AccessError, UserError


class OdooTools:
    """Read-only tools for retrieving data from the current Odoo environment."""

    MAX_RESULTS = 5
    MAX_QUERY_LENGTH = 100

    @staticmethod
    def lookup_customers(env, query, limit=5):
        """Find active customer/partner records visible to the current user.

        This method deliberately does not use sudo(), create(), write(),
        or unlink(). Odoo's normal access rights and record rules apply.
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

        Partner = env["res.partner"]

        # Check permissions explicitly; search_read also applies normal
        # record rules and does not bypass them.
        Partner.check_access("read")

        domain = [
            ("active", "=", True),
            "|",
            ("name", "ilike", query),
            ("email", "ilike", query),
        ]

        records = Partner.search_read(
            domain,
            fields=[
                "id",
                "name",
                "is_company",
                "email",
                "city",
                "country_id",
            ],
            limit=limit,
            order="name, id",
        )

        results = []
        for record in records:
            country = record.get("country_id")
            results.append({
                "id": record["id"],
                "name": record["name"],
                "is_company": record["is_company"],
                "email": record.get("email") or None,
                "city": record.get("city") or None,
                "country": country[1] if country else None,
            })

        return {
            "returned_count": len(results),
            "customers": results,
        }
