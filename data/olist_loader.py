"""
olist_loader.py
───────────────
Loads, joins, and cleans the 9 Olist CSV files into module-ready DataFrames.
Falls back to synthetic data automatically if CSVs are not present.

Olist file → what we use it for
─────────────────────────────────────────────────────────────
olist_orders_dataset.csv            → order timestamps, status
olist_order_items_dataset.csv       → revenue per order (price + freight)
olist_order_payments_dataset.csv    → payment type, installments
olist_order_reviews_dataset.csv     → review score (proxy for NPS)
olist_customers_dataset.csv         → customer_id, state (geo)
olist_products_dataset.csv          → product_category_name
olist_sellers_dataset.csv           → seller state
olist_product_category_name_translation.csv  → Portuguese → English category
olist_geolocation_dataset.csv       → lat/lon (not used in v1)
"""

import os
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path

RAW_DIR = Path(__file__).parent / "olist_raw"

# English category groupings — Olist has 74 raw categories; we bucket them
CATEGORY_MAP = {
    "health_beauty":               "Health & Beauty",
    "bed_bath_table":              "Home & Living",
    "sports_leisure":              "Sports & Leisure",
    "computers_accessories":       "Electronics",
    "furniture_decor":             "Home & Living",
    "housewares":                  "Home & Living",
    "watches_gifts":               "Fashion & Gifts",
    "telephony":                   "Electronics",
    "auto":                        "Auto",
    "toys":                        "Toys & Kids",
    "garden_tools":                "Home & Living",
    "cool_stuff":                  "Fashion & Gifts",
    "perfumery":                   "Health & Beauty",
    "baby":                        "Toys & Kids",
    "electronics":                 "Electronics",
    "fashion_bags_accessories":    "Fashion & Gifts",
    "stationery":                  "Books & Stationery",
    "pet_shop":                    "Pet Shop",
    "office_furniture":            "Home & Living",
    "books_general_interest":      "Books & Stationery",
    "musical_instruments":         "Sports & Leisure",
    "food_drink":                  "Food & Drink",
    "construction_tools_safety":   "Auto",
    "agro_industry_and_commerce":  "Food & Drink",
    "small_appliances":            "Electronics",
    "luggage_accessories":         "Fashion & Gifts",
    "air_conditioning":            "Home & Living",
    "fashion_shoes":               "Fashion & Gifts",
    "fashion_male_clothing":       "Fashion & Gifts",
    "party_supplies":              "Toys & Kids",
    "Christmas_supplies":          "Toys & Kids",
    "arts_and_craftmanship":       "Books & Stationery",
    "tablets_printing_image":      "Electronics",
    "books_imported":              "Books & Stationery",
    "home_appliances":             "Electronics",
    "dvds_blu_ray":                "Books & Stationery",
    "drinks":                      "Food & Drink",
    "food":                        "Food & Drink",
    "flowers":                     "Health & Beauty",
    "fashion_underwear_beach":     "Fashion & Gifts",
    "fashion_sport":               "Fashion & Gifts",
    "fixed_telephony":             "Electronics",
    "consoles_games":              "Electronics",
    "audio":                       "Electronics",
    "industry_commerce_and_business": "Auto",
    "diapers_and_hygiene":         "Toys & Kids",
    "cine_photo":                  "Electronics",
    "home_construction":           "Home & Living",
    "market_place":                "Other",
    "furniture_living_room":       "Home & Living",
    "furniture_bedroom":           "Home & Living",
    "furniture_mattress_and_upholstery": "Home & Living",
    "signaling_and_security":      "Auto",
    "costruction_tools_tools":     "Auto",
    "la_cuisine":                  "Food & Drink",
    "home_comfort":                "Home & Living",
    "home_comfort_2":              "Home & Living",
    "fashion_childrens_clothes":   "Fashion & Gifts",
}

PAYMENT_LABELS = {
    "credit_card":  "Credit Card",
    "boleto":       "Boleto",
    "voucher":      "Voucher",
    "debit_card":   "Debit Card",
    "not_defined":  "Other",
}


def olist_available() -> bool:
    """Return True if at least the two core CSVs are present."""
    required = [
        "olist_orders_dataset.csv",
        "olist_order_items_dataset.csv",
    ]
    return all((RAW_DIR / f).exists() for f in required)


@st.cache_data(show_spinner=False)
def _load_raw() -> dict[str, pd.DataFrame]:
    """Read all present CSVs into a dict keyed by short name."""
    files = {
        "orders":      "olist_orders_dataset.csv",
        "items":       "olist_order_items_dataset.csv",
        "payments":    "olist_order_payments_dataset.csv",
        "reviews":     "olist_order_reviews_dataset.csv",
        "customers":   "olist_customers_dataset.csv",
        "products":    "olist_products_dataset.csv",
        "sellers":     "olist_sellers_dataset.csv",
        "translation": "olist_product_category_name_translation.csv",
    }
    raw = {}
    for key, fname in files.items():
        path = RAW_DIR / fname
        if path.exists():
            raw[key] = pd.read_csv(path)
    return raw


@st.cache_data(show_spinner=False)
def get_master() -> pd.DataFrame:
    """
    Build the master orders DataFrame used by all modules.
    Joins: orders + items + customers + products + translation + payments.

    Returns one row per order with columns:
      order_id, customer_id, order_date, month, week,
      revenue, freight, category, state,
      payment_type, review_score, device (synthetic)
    """
    raw = _load_raw()

    # ── Core join ──────────────────────────────────────────
    orders = raw["orders"].copy()
    orders["order_date"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    orders = orders[orders["order_status"] == "delivered"].copy()
    orders = orders.dropna(subset=["order_date"])

    # Revenue per order  (sum of price + freight across items)
    items = raw["items"].copy()
    items["revenue"] = items["price"] + items["freight_value"]
    rev = items.groupby("order_id").agg(
        revenue=("revenue", "sum"),
        units=("order_item_id", "count"),
    ).reset_index()

    # Product category per order (most common item category)
    if "products" in raw:
        prods = raw["products"][["product_id", "product_category_name"]].copy()
        if "translation" in raw:
            trans = raw["translation"].rename(
                columns={
                    "product_category_name": "product_category_name",
                    "product_category_name_english": "category_en",
                }
            )
            prods = prods.merge(trans, on="product_category_name", how="left")
            prods["category_en"] = prods["category_en"].fillna(
                prods["product_category_name"]
            )
        else:
            prods["category_en"] = (
                prods["product_category_name"]
                .fillna("Other")
                .astype(str)
                .str.replace("_", " ")
                .str.title()
            )

        prods["category"] = (
            prods["category_en"]
            .map(CATEGORY_MAP)
            .fillna(prods["category_en"])
        )
        items_cat = items[["order_id", "product_id"]].merge(
            prods[["product_id", "category"]], on="product_id", how="left"
        )
        cat_per_order = (
            items_cat.groupby("order_id")["category"]
            .agg(lambda x: x.mode()[0] if len(x) > 0 else "Other")
            .reset_index()
        )
    else:
        cat_per_order = pd.DataFrame(
            {"order_id": rev["order_id"], "category": "Other"}
        )

    # Customer state
    if "customers" in raw:
        cust = raw["customers"][
            ["customer_id", "customer_unique_id", "customer_state"]
        ].rename(columns={"customer_state": "state",
                          "customer_unique_id": "unique_customer_id"})
    else:
        cust = pd.DataFrame(
            {"customer_id": orders["customer_id"], "unique_customer_id": orders["customer_id"],
             "state": "Unknown"}
        )

    # Payment type (most common per order)
    if "payments" in raw:
        pay = (
            raw["payments"]
            .groupby("order_id")["payment_type"]
            .agg(lambda x: x.mode()[0])
            .reset_index()
        )
        pay["payment_type"] = pay["payment_type"].map(PAYMENT_LABELS).fillna("Other")
    else:
        pay = pd.DataFrame(
            {"order_id": rev["order_id"], "payment_type": "Credit Card"}
        )

    # Review score
    if "reviews" in raw:
        reviews = (
            raw["reviews"]
            .groupby("order_id")["review_score"]
            .mean()
            .reset_index()
        )
    else:
        reviews = pd.DataFrame(
            {"order_id": rev["order_id"],
             "review_score": np.random.choice([1, 2, 3, 4, 5], len(rev))}
        )

    # ── Merge everything ───────────────────────────────────
    df = (
        orders[["order_id", "customer_id", "order_date"]]
        .merge(rev,          on="order_id",   how="left")
        .merge(cat_per_order,on="order_id",   how="left")
        .merge(cust,         on="customer_id",how="left")
        .merge(pay,          on="order_id",   how="left")
        .merge(reviews,      on="order_id",   how="left")
    )

    # Fill gaps
    df["category"]     = df["category"].fillna("Other")
    df["state"]        = df["state"].fillna("Unknown")
    df["payment_type"] = df["payment_type"].fillna("Credit Card")
    df["review_score"] = df["review_score"].fillna(
        df["review_score"].median()
    )
    df["revenue"]      = df["revenue"].fillna(0)
    df = df[df["revenue"] > 0].copy()

    # Use unique_customer_id as the stable user key
    df["user_id"] = df["unique_customer_id"].fillna(df["customer_id"])

    # Time dimensions
    df["month"] = df["order_date"].dt.to_period("M")
    df["week"]  = df["order_date"].dt.to_period("W")

    # Synthetic device split (Olist has no clickstream)
    rng = np.random.default_rng(42)
    df["device"] = rng.choice(
        ["Mobile", "Desktop", "Tablet"],
        size=len(df),
        p=[0.62, 0.31, 0.07],
    )

    # Rename payment_type → channel proxy
    df["channel"] = df["payment_type"]

    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def get_orders() -> pd.DataFrame:
    """Alias used by all views — same signature as synthetic generator."""
    return get_master()


@st.cache_data(show_spinner=False)
def get_daily_metrics() -> pd.DataFrame:
    df = get_master()
    daily = (
        df.groupby("order_date")
        .agg(orders=("order_id", "count"), gmv=("revenue", "sum"))
        .reset_index()
    )
    # Approximate DAU as unique buyers per day
    dau = df.groupby("order_date")["user_id"].nunique().reset_index()
    dau.columns = ["order_date", "dau"]
    daily = daily.merge(dau, on="order_date", how="left")
    daily = daily.rename(columns={"order_date": "date"})

    # Rolling 30-day MAU
    daily = daily.sort_values("date").reset_index(drop=True)
    daily["mau"] = (
        daily["dau"].rolling(30, min_periods=1).sum().astype(int)
    )
    daily["arpu"]          = (daily["gmv"] / daily["dau"].replace(0, np.nan)).round(2)
    daily["dau_mau_ratio"] = (daily["dau"] / daily["mau"].replace(0, np.nan) * 100).round(1)
    return daily


@st.cache_data(show_spinner=False)
def get_funnel() -> pd.DataFrame:
    """
    Olist has no clickstream → funnel stages are estimated from
    order-status transitions + industry conversion benchmarks.
    This is clearly labelled in the UI.
    """
    df = get_master()
    raw = _load_raw()

    # Count all orders by status to derive funnel stages
    if "orders" in raw:
        all_orders = raw["orders"].copy()
        total      = len(all_orders)
        approved   = len(all_orders[all_orders["order_status"].isin(
            ["approved","processing","shipped","delivered","invoiced"])])
        shipped    = len(all_orders[all_orders["order_status"].isin(
            ["shipped","delivered"])])
        delivered  = len(all_orders[all_orders["order_status"] == "delivered"])
    else:
        total     = len(df) * 4
        approved  = len(df) * 2
        shipped   = int(len(df) * 1.3)
        delivered = len(df)

    # Estimate upstream sessions from delivered orders + benchmarks
    sessions   = int(total / 0.032)   # ~3.2% overall e-commerce CVR
    pdp_views  = int(sessions * 0.54)
    add_cart   = int(pdp_views * 0.31)
    checkout   = int(add_cart  * 0.62)
    purchase   = delivered

    return pd.DataFrame({
        "stage":       ["Session", "PDP View", "Add to Cart", "Checkout Start", "Order Placed"],
        "users":       [sessions, pdp_views, add_cart, checkout, purchase],
        "stage_order": [1, 2, 3, 4, 5],
        "is_estimated": [True, True, True, True, False],
    })


@st.cache_data(show_spinner=False)
def get_cohort() -> pd.DataFrame:
    """Monthly acquisition cohorts — actual repurchase rates from Olist data."""
    df = get_master()

    # First order month per customer
    first = (
        df.groupby("user_id")["order_date"]
        .min()
        .dt.to_period("M")
        .reset_index()
        .rename(columns={"order_date": "cohort_month"})
    )
    df2 = df.merge(first, on="user_id")
    df2["order_month"] = df2["order_date"].dt.to_period("M")
    df2["period_num"]  = (
        df2["order_month"].astype(int) - df2["cohort_month"].astype(int)
    )

    cohort_sizes = (
        first.groupby("cohort_month")["user_id"].count().reset_index()
        .rename(columns={"user_id": "cohort_size"})
    )

    cohort_data = (
        df2.groupby(["cohort_month", "period_num"])["user_id"]
        .nunique()
        .reset_index()
        .rename(columns={"user_id": "users"})
    )
    cohort_data = cohort_data.merge(cohort_sizes, on="cohort_month")
    cohort_data["retention"] = (
        cohort_data["users"] / cohort_data["cohort_size"]
    ).round(3)
    cohort_data["cohort"] = cohort_data["cohort_month"].astype(str)

    return cohort_data.rename(columns={"period_num": "week"})[
        ["cohort", "week", "retention", "cohort_size"]
    ]


@st.cache_data(show_spinner=False)
def get_rfm() -> pd.DataFrame:
    """RFM on unique customers using real Olist purchase history."""
    df = get_master()
    snapshot = df["order_date"].max()

    rfm = (
        df.groupby("user_id")
        .agg(
            recency  =("order_date", lambda x: (snapshot - x.max()).days),
            frequency=("order_id",   "count"),
            monetary =("revenue",    "sum"),
        )
        .reset_index()
    )

    for col, asc in [("recency", True), ("frequency", False), ("monetary", False)]:
        label = col[0].upper()
        try:
            # Try with 5 quantiles and specified labels
            scores = pd.qcut(
                rfm[col], 5,
                labels=[5, 4, 3, 2, 1] if asc else [1, 2, 3, 4, 5],
                duplicates="drop",
            )
        except ValueError:
            # If duplicates cause fewer bins, use automatic labels
            scores = pd.qcut(
                rfm[col], 5,
                duplicates="drop",
            )
            # Remap labels to match the 1-5 scale
            n_bins = scores.cat.categories.size
            labels_map = [5, 4, 3, 2, 1] if asc else [1, 2, 3, 4, 5]
            # Create a mapping from auto-generated labels to our 1-5 scale
            label_mapping = {old: labels_map[i] for i, old in enumerate(sorted(scores.cat.categories))}
            scores = scores.map(label_mapping)
        rfm[f"{label}_score"] = scores

    def segment(row):
        try:
            r, f = int(row["R_score"]), int(row["F_score"])
        except (ValueError, TypeError):
            return "Other"
        if r >= 4 and f >= 4: return "Champions"
        if r >= 3 and f >= 3: return "Loyal"
        if r >= 4 and f <= 2: return "New Customers"
        if r <= 2 and f >= 3: return "At Risk"
        if r <= 2 and f <= 2: return "Lost"
        return "Potential Loyalists"

    rfm["segment"] = rfm.apply(segment, axis=1)
    return rfm


@st.cache_data(show_spinner=False)
def get_product_analytics() -> pd.DataFrame:
    """
    Page-level analytics derived from category performance.
    Maps Olist product categories to 'page' equivalents.
    """
    df = get_master()

    cat_stats = (
        df.groupby("category")
        .agg(
            sessions  =("order_id", "count"),
            revenue   =("revenue",  "sum"),
            avg_review=("review_score", "mean"),
        )
        .reset_index()
        .rename(columns={"category": "page"})
    )

    rng = np.random.default_rng(99)
    n   = len(cat_stats)

    # Derive realistic proxy metrics from review score
    cat_stats["bounce_rate"]   = (
        0.8 - (cat_stats["avg_review"] - 1) / 4 * 0.4 +
        rng.uniform(-0.05, 0.05, n)
    ).clip(0.15, 0.85).round(3)

    cat_stats["scroll_depth"]  = (
        0.3 + (cat_stats["avg_review"] - 1) / 4 * 0.5 +
        rng.uniform(-0.05, 0.05, n)
    ).clip(0.2, 0.95).round(3)

    cat_stats["avg_time_sec"]  = (
        40 + (cat_stats["avg_review"] - 1) / 4 * 160 +
        rng.integers(-20, 20, n)
    ).clip(20, 240).astype(int)

    cat_stats["exit_rate"]     = (
        cat_stats["bounce_rate"] * 0.7 +
        rng.uniform(-0.05, 0.05, n)
    ).clip(0.1, 0.7).round(3)

    cat_stats["add_to_cart_rate"] = (
        cat_stats["sessions"] /
        cat_stats["sessions"].sum() *
        rng.uniform(0.08, 0.22, n)
    ).round(3)

    return cat_stats
