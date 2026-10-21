import csv
import os
from pathlib import Path
from typing import Dict, Optional
import duckdb

DEFAULT_DB_PATH = Path("data") / "olist.duckdb"
CANDIDATE_DATA_DIRS = [
    Path("data") / "olist_raw",
    Path("data") / "olist",
]

TABLE_CONFIGS = {
    "orders": {
        "csv_file": "olist_orders_dataset.csv",
        "sql": """
            CREATE OR REPLACE TABLE orders AS
            SELECT
                order_id,
                customer_id,
                order_status,
                TRY_CAST(order_purchase_timestamp AS TIMESTAMP) AS order_purchase_timestamp,
                TRY_CAST(order_approved_at AS TIMESTAMP) AS order_approved_at,
                TRY_CAST(order_delivered_carrier_date AS TIMESTAMP) AS order_delivered_carrier_date,
                TRY_CAST(order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
                TRY_CAST(order_estimated_delivery_date AS TIMESTAMP) AS order_estimated_delivery_date
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
    "order_items": {
        "csv_file": "olist_order_items_dataset.csv",
        "sql": """
            CREATE OR REPLACE TABLE order_items AS
            SELECT
                order_id,
                CAST(order_item_id AS INTEGER) AS order_item_id,
                product_id,
                seller_id,
                TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_date,
                CAST(price AS DOUBLE) AS price,
                CAST(freight_value AS DOUBLE) AS freight_value
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
    "order_payments": {
        "csv_file": "olist_order_payments_dataset.csv",
        "sql": """
            CREATE OR REPLACE TABLE order_payments AS
            SELECT
                order_id,
                CAST(payment_sequential AS INTEGER) AS payment_sequential,
                payment_type,
                CAST(payment_installments AS INTEGER) AS payment_installments,
                CAST(payment_value AS DOUBLE) AS payment_value
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
    "customers": {
        "csv_file": "olist_customers_dataset.csv",
        "sql": """
            CREATE OR REPLACE TABLE customers AS
            SELECT
                customer_id,
                customer_unique_id,
                CAST(customer_zip_code_prefix AS INTEGER) AS customer_zip_code_prefix,
                customer_city,
                customer_state
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
    "products": {
        "csv_file": "olist_products_dataset.csv",
        "sql": """
            CREATE OR REPLACE TABLE products AS
            SELECT
                product_id,
                product_category_name,
                TRY_CAST(product_name_lenght AS INTEGER) AS product_name_lenght,
                TRY_CAST(product_description_lenght AS INTEGER) AS product_description_lenght,
                TRY_CAST(product_photos_qty AS INTEGER) AS product_photos_qty,
                TRY_CAST(product_weight_g AS DOUBLE) AS product_weight_g,
                TRY_CAST(product_length_cm AS DOUBLE) AS product_length_cm,
                TRY_CAST(product_height_cm AS DOUBLE) AS product_height_cm,
                TRY_CAST(product_width_cm AS DOUBLE) AS product_width_cm
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
    "sellers": {
        "csv_file": "olist_sellers_dataset.csv",
        "sql": """
            CREATE OR REPLACE TABLE sellers AS
            SELECT
                seller_id,
                CAST(seller_zip_code_prefix AS INTEGER) AS seller_zip_code_prefix,
                seller_city,
                seller_state
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
    "order_reviews": {
        "csv_file": "olist_order_reviews_dataset.csv",
        "sql": """
            CREATE OR REPLACE TABLE order_reviews AS
            SELECT
                review_id,
                order_id,
                TRY_CAST(review_score AS INTEGER) AS review_score,
                review_comment_title,
                review_comment_message,
                TRY_CAST(review_creation_date AS TIMESTAMP) AS review_creation_date,
                TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
    "product_category_name_translation": {
        "csv_file": "product_category_name_translation.csv",
        "sql": """
            CREATE OR REPLACE TABLE product_category_name_translation AS
            SELECT
                product_category_name,
                product_category_name_english
            FROM read_csv_auto('{csv_path}', header=True)
        """,
    },
}


def find_data_dir() -> Path:
    for candidate in CANDIDATE_DATA_DIRS:
        if candidate.exists() and (candidate / "olist_orders_dataset.csv").exists():
            return candidate
    raise FileNotFoundError(
        f"Could not locate Olist CSV directory. Checked: {[str(c) for c in CANDIDATE_DATA_DIRS]}"
    )


def count_csv_rows(csv_path: Path) -> int:
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # Skip header
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def build_database(
    db_path: Path = DEFAULT_DB_PATH,
    data_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, int]]:
    resolved_data_dir = data_dir or find_data_dir()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    counts: Dict[str, Dict[str, int]] = {}

    con = duckdb.connect(str(db_path))
    try:
        for table_name, config in TABLE_CONFIGS.items():
            csv_path = resolved_data_dir / config["csv_file"]
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing required CSV: {csv_path}")

            # Normalize path for DuckDB SQL literal
            csv_path_str = str(csv_path.resolve()).replace("\\", "/")
            create_query = config["sql"].format(csv_path=csv_path_str)

            con.execute(create_query)

            db_rows = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            csv_rows = count_csv_rows(csv_path)

            counts[table_name] = {
                "db_rows": db_rows,
                "csv_rows": csv_rows,
            }

            match_symbol = "OK" if db_rows == csv_rows else "MISMATCH"
            print(f"[{match_symbol:^8}] {table_name:<34} DB: {db_rows:>7,d} | CSV: {csv_rows:>7,d}")
    finally:
        con.close()

    return counts


if __name__ == "__main__":
    print(f"Building DuckDB database at {DEFAULT_DB_PATH}...")
    summary = build_database()
    mismatches = [t for t, c in summary.items() if c["db_rows"] != c["csv_rows"]]
    if mismatches:
        print(f"\nWarning: Row count mismatch in tables: {mismatches}")
    else:
        print("\nAll tables loaded successfully. Row counts match CSVs exactly.")
