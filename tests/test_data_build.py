from pathlib import Path
import duckdb
import pytest
from copilot.data.build import (
    DEFAULT_DB_PATH,
    TABLE_CONFIGS,
    build_database,
    count_csv_rows,
    find_data_dir,
)


def test_find_data_dir():
    data_dir = find_data_dir()
    assert data_dir.exists()
    assert (data_dir / "olist_orders_dataset.csv").exists()


def test_database_build_and_row_counts(tmp_path):
    test_db = tmp_path / "test_olist.duckdb"
    summary = build_database(db_path=test_db)

    assert len(summary) == len(TABLE_CONFIGS)
    for table_name, counts in summary.items():
        assert counts["db_rows"] == counts["csv_rows"], f"Mismatch in {table_name}"
        assert counts["db_rows"] > 0, f"Table {table_name} is empty"

    # Verify DuckDB schema datatypes on the built DB
    con = duckdb.connect(str(test_db), read_only=True)
    try:
        # Check timestamp casting in orders table
        orders_info = con.execute("DESCRIBE orders").fetchall()
        col_types = {row[0]: row[1] for row in orders_info}
        assert col_types["order_purchase_timestamp"].upper() == "TIMESTAMP"
        assert col_types["order_delivered_customer_date"].upper() == "TIMESTAMP"

        # Check numeric types in order_items
        items_info = con.execute("DESCRIBE order_items").fetchall()
        item_col_types = {row[0]: row[1] for row in items_info}
        assert item_col_types["price"].upper() in ("DOUBLE", "FLOAT")
        assert item_col_types["order_item_id"].upper() == "INTEGER"
    finally:
        con.close()


def test_build_database_idempotency(tmp_path):
    test_db = tmp_path / "test_idempotent.duckdb"
    first_run = build_database(db_path=test_db)
    second_run = build_database(db_path=test_db)

    assert first_run == second_run
    con = duckdb.connect(str(test_db), read_only=True)
    try:
        orders_count = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        assert orders_count == 99441
    finally:
        con.close()
