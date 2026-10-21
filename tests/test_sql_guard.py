import pytest
from copilot.sql_guard import (
    ALLOWED_TABLES,
    SQLGuardError,
    validate_and_sanitize_sql,
)


def test_valid_select_query():
    sql = "SELECT order_id, order_status FROM orders WHERE order_status = 'delivered'"
    sanitized = validate_and_sanitize_sql(sql)
    assert "LIMIT 1000" in sanitized
    assert "orders" in sanitized


def test_valid_cte_query():
    sql = """
        WITH monthly_rev AS (
            SELECT 
                DATE_TRUNC('month', o.order_purchase_timestamp) AS mo,
                SUM(oi.price) AS gmv
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY 1
        )
        SELECT mo, gmv FROM monthly_rev ORDER BY mo
    """
    sanitized = validate_and_sanitize_sql(sql)
    assert "LIMIT 1000" in sanitized
    assert "monthly_rev" in sanitized


def test_blocks_drop_table():
    sql = "DROP TABLE orders;"
    with pytest.raises(SQLGuardError, match="Only SELECT queries are allowed"):
        validate_and_sanitize_sql(sql)


def test_blocks_delete_from():
    sql = "DELETE FROM orders WHERE 1=1;"
    with pytest.raises(SQLGuardError, match="Only SELECT queries are allowed"):
        validate_and_sanitize_sql(sql)


def test_blocks_update():
    sql = "UPDATE orders SET order_status = 'cancelled' WHERE 1=1;"
    with pytest.raises(SQLGuardError, match="Only SELECT queries are allowed"):
        validate_and_sanitize_sql(sql)


def test_blocks_insert():
    sql = "INSERT INTO orders (order_id) VALUES ('fake_order');"
    with pytest.raises(SQLGuardError, match="Only SELECT queries are allowed"):
        validate_and_sanitize_sql(sql)


def test_blocks_multi_statement():
    sql = "SELECT * FROM orders; DROP TABLE customers;"
    with pytest.raises(SQLGuardError, match="Multiple statements are not permitted"):
        validate_and_sanitize_sql(sql)


def test_blocks_comment_trick():
    # Attempting to hide malicious statement after comment
    sql = "SELECT * FROM orders -- comment\n; DROP TABLE sellers;"
    with pytest.raises(SQLGuardError):
        validate_and_sanitize_sql(sql)


def test_blocks_read_csv():
    sql = "SELECT * FROM read_csv('data/secret.csv')"
    with pytest.raises(SQLGuardError, match="Forbidden"):
        validate_and_sanitize_sql(sql)


def test_blocks_read_parquet():
    sql = "SELECT * FROM read_parquet('s3://bucket/data.parquet')"
    with pytest.raises(SQLGuardError, match="Forbidden"):
        validate_and_sanitize_sql(sql)


def test_blocks_disallowed_table():
    sql = "SELECT * FROM sqlite_master"
    with pytest.raises(SQLGuardError, match="Access to table 'sqlite_master' is not permitted"):
        validate_and_sanitize_sql(sql)


def test_forces_limit_when_absent():
    sql = "SELECT order_id FROM orders"
    sanitized = validate_and_sanitize_sql(sql)
    assert "LIMIT 1000" in sanitized


def test_preserves_smaller_limit():
    sql = "SELECT order_id FROM orders LIMIT 25"
    sanitized = validate_and_sanitize_sql(sql)
    assert "LIMIT 25" in sanitized


def test_clamps_excessive_limit():
    sql = "SELECT order_id FROM orders LIMIT 50000"
    sanitized = validate_and_sanitize_sql(sql)
    assert "LIMIT 1000" in sanitized
