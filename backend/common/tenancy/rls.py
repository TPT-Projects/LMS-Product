"""PostgreSQL Row Level Security helpers used from migrations.

Every tenant table gets the same policy: a row is visible and writable only
when its tenant column equals the `app.tenant_id` setting of the current
transaction (or a system block turned on `app.rls_bypass`).

`FORCE ROW LEVEL SECURITY` makes the policy apply to the table owner too,
because the app role owns the tables it migrates.
"""

from django.db import migrations

POLICY_NAME = "tenant_isolation"


def _policy_expression(column: str) -> str:
    return (
        "(current_setting('app.rls_bypass', true) = 'on' "
        f"OR {column} = NULLIF(current_setting('app.tenant_id', true), '')::bigint)"
    )


def enable_rls_sql(table: str, column: str = "tenant_id") -> str:
    expr = _policy_expression(column)
    return (
        f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;\n'
        f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;\n'
        f'CREATE POLICY {POLICY_NAME} ON "{table}" USING {expr} WITH CHECK {expr};'
    )


def disable_rls_sql(table: str) -> str:
    return (
        f'DROP POLICY IF EXISTS {POLICY_NAME} ON "{table}";\n'
        f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY;\n'
        f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY;'
    )


class EnableRLS(migrations.RunSQL):
    """Migration operation: `EnableRLS("teams")` or `EnableRLS("tenants", column="id")`."""

    def __init__(self, table: str, column: str = "tenant_id"):
        super().__init__(sql=enable_rls_sql(table, column), reverse_sql=disable_rls_sql(table))
