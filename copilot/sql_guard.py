from typing import Optional, Set
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ALLOWED_TABLES: Set[str] = {
    "orders",
    "order_items",
    "order_payments",
    "customers",
    "products",
    "sellers",
    "order_reviews",
    "product_category_name_translation",
}

FORBIDDEN_FUNCTIONS: Set[str] = {
    "read_csv",
    "read_csv_auto",
    "read_parquet",
    "read_json",
    "read_json_auto",
    "scan_parquet",
    "scan_csv",
    "parquet_scan",
    "csv_scan",
    "glob",
    "write_csv",
    "copy",
    "load",
    "install",
    "pragma",
    "system",
    "query",
    "sniff_csv",
}


class SQLGuardError(Exception):
    """Raised when generated SQL violates safety constraints."""
    pass


def validate_and_sanitize_sql(
    sql: str,
    allowed_tables: Optional[Set[str]] = None,
    max_limit: int = 1000,
) -> str:
    if not sql or not sql.strip():
        raise SQLGuardError("SQL query is empty.")

    tables_whitelist = {t.lower() for t in (allowed_tables or ALLOWED_TABLES)}

    try:
        statements = sqlglot.parse(sql.strip(), read="duckdb")
    except ParseError as e:
        raise SQLGuardError(f"SQL syntax error: {str(e)}") from e

    if not statements:
        raise SQLGuardError("No valid SQL statement found.")

    if len(statements) > 1:
        raise SQLGuardError("Multiple statements are not permitted.")

    stmt = statements[0]

    # Validate that statement is purely a query (Select or Union)
    if not isinstance(stmt, (exp.Select, exp.Union)):
        raise SQLGuardError(
            f"Only SELECT queries are allowed. Disallowed statement type: {stmt.key.upper()}"
        )

    # Track locally defined CTE aliases so they are allowed in FROM/JOIN
    cte_names: Set[str] = set()
    for cte in stmt.find_all(exp.CTE):
        alias = cte.alias_or_name
        if alias:
            cte_names.add(alias.lower())

    # Check for forbidden functions or external file readers anywhere in the AST
    for node in stmt.walk():
        # Check standard and anonymous function names
        if isinstance(node, (exp.Func, exp.Anonymous)):
            func_name = getattr(node, "name", "").lower()
            if not func_name and hasattr(node, "key"):
                func_name = str(node.key).lower()
            if func_name in FORBIDDEN_FUNCTIONS:
                raise SQLGuardError(f"Forbidden function or external reader call: {func_name}")

        # Catch specific table read functions like ReadCSV, ReadParquet, Command, etc.
        node_class_name = node.__class__.__name__.lower()
        if any(f in node_class_name for f in ["readcsv", "readparquet", "readjson", "command"]):
            raise SQLGuardError(f"Forbidden reader operation detected: {node_class_name}")

    # Inspect all referenced tables
    for table_node in stmt.find_all(exp.Table):
        # A table node where .this is a function or non-identifier
        if not isinstance(table_node.this, exp.Identifier):
            table_str = str(table_node.this).lower()
            raise SQLGuardError(f"Dynamic or function-based table access is forbidden: {table_str}")

        tbl_name = table_node.name.lower()
        if tbl_name not in tables_whitelist and tbl_name not in cte_names:
            raise SQLGuardError(
                f"Access to table '{table_node.name}' is not permitted. Allowed tables: {sorted(tables_whitelist)}"
            )

    # Enforce forced LIMIT
    # For union queries, limit applies to the outer query
    limit_expr = stmt.args.get("limit")
    if limit_expr is None:
        stmt = stmt.limit(max_limit)
    else:
        try:
            # Check existing limit value
            limit_val = int(limit_expr.expression.this)
            if limit_val > max_limit or limit_val < 0:
                stmt = stmt.limit(max_limit)
        except (ValueError, AttributeError, TypeError):
            stmt = stmt.limit(max_limit)

    return stmt.sql(dialect="duckdb")
