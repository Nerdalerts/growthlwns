"""
GrowthLens data layer
─────────────────────
Priority order:
  1. Real Olist CSVs in  data/olist/   → full fidelity, auto-detected
  2. Legacy path         data/olist_raw/ (local only, gitignored)
  3. Synthetic fallback  (~96 k orders, Olist schema) → works out-of-the-box

Download real data locally (never commit CSVs):
  python download_olist.py
"""
import os
import warnings
from functools import lru_cache

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(__file__)
_OLIST_DIR = os.path.join(_HERE, "olist")
_OLIST_LEGACY = os.path.join(_HERE, "olist_raw")
os.makedirs(_OLIST_DIR, exist_ok=True)

# ── Olist schema constants ────────────────────────────────────────────────────
CATEGORIES = [
    "Health Beauty", "Bed Bath Table", "Sports Leisure",
    "Computers Accessories", "Furniture Decor", "Housewares",
    "Watches Gifts", "Telephony", "Toys", "Fashion Bags Accessories",
]
CHANNELS        = ["Credit Card", "Boleto", "Voucher", "Debit Card"]
CHANNEL_WEIGHTS = [0.73, 0.19, 0.05, 0.03]
START_DATE      = "2017-01-01"
END_DATE        = "2018-08-31"

_REQUIRED = ["olist_orders_dataset.csv", "olist_order_items_dataset.csv",
             "olist_customers_dataset.csv"]


def _resolve_data_dir() -> str:
    """Prefer data/olist/, fall back to local-only data/olist_raw/."""
    for directory in (_OLIST_DIR, _OLIST_LEGACY):
        if all(os.path.exists(os.path.join(directory, f)) for f in _REQUIRED):
            return directory
    return _OLIST_DIR


def _olist_present() -> bool:
    return all(
        os.path.exists(os.path.join(_resolve_data_dir(), f)) for f in _REQUIRED
    )


# ── Real Olist loader ─────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_olist_orders() -> pd.DataFrame:
    data_dir = _resolve_data_dir()
    orders    = pd.read_csv(os.path.join(data_dir, "olist_orders_dataset.csv"),
                            parse_dates=["order_purchase_timestamp"])
    items     = pd.read_csv(os.path.join(data_dir, "olist_order_items_dataset.csv"))
    customers = pd.read_csv(os.path.join(data_dir, "olist_customers_dataset.csv"))

    # ── Products + category translation ───────────────────────────────────
    prod_path  = os.path.join(data_dir, "olist_products_dataset.csv")
    trans_path = os.path.join(data_dir, "product_category_name_translation.csv")

    if os.path.exists(prod_path):
        products = pd.read_csv(prod_path)
        if os.path.exists(trans_path):
            trans    = pd.read_csv(trans_path)
            products = products.merge(trans, on="product_category_name", how="left")
            products["category"] = (
                products["product_category_name_english"]
                .fillna(products["product_category_name"])
                .str.replace("_", " ").str.title()
            )
        else:
            products["category"] = (
                products["product_category_name"]
                .str.replace("_", " ").str.title()
            )
    else:
        products = pd.DataFrame({"product_id": items["product_id"].unique()})
        products["category"] = "General"

    # ── Payment type → channel ─────────────────────────────────────────────
    pay_path = os.path.join(data_dir, "olist_order_payments_dataset.csv")
    if os.path.exists(pay_path):
        payments = pd.read_csv(pay_path)
        ch_map   = {"credit_card": "Credit Card", "boleto": "Boleto",
                    "voucher": "Voucher", "debit_card": "Debit Card"}
        pay_type = payments.groupby("order_id")["payment_type"].first().reset_index()
        pay_type["channel"] = pay_type["payment_type"].map(ch_map).fillna("Other")
    else:
        pay_type = pd.DataFrame(columns=["order_id", "channel"])

    # ── Revenue per order ──────────────────────────────────────────────────
    order_rev = items.groupby("order_id")["price"].sum().reset_index()
    order_rev.columns = ["order_id", "revenue"]

    # ── Category per order ─────────────────────────────────────────────────
    order_cat = (
        items.merge(products[["product_id", "category"]], on="product_id", how="left")
        .groupby("order_id")["category"].first().reset_index()
    )

    # ── Assemble ───────────────────────────────────────────────────────────
    df = (
        orders[orders["order_status"] == "delivered"]
        [["order_id", "customer_id", "order_purchase_timestamp"]]
        .merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
        .merge(order_rev,                                         on="order_id",    how="left")
        .merge(order_cat,                                         on="order_id",    how="left")
    )
    if not pay_type.empty:
        df = df.merge(pay_type[["order_id", "channel"]], on="order_id", how="left")
    else:
        df["channel"] = "Credit Card"

    df.rename(columns={"customer_unique_id": "user_id",
                        "order_purchase_timestamp": "date"}, inplace=True)
    df["date"]     = pd.to_datetime(df["date"])
    df["month"]    = df["date"].dt.to_period("M")
    df["revenue"]  = df["revenue"].fillna(0)
    df["category"] = df["category"].fillna("Other")
    df["channel"]  = df["channel"].fillna("Other")

    return df.dropna(subset=["date", "user_id"]).reset_index(drop=True)


# ── Synthetic fallback ────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _synthetic_orders() -> pd.DataFrame:
    rng     = np.random.default_rng(42)
    n       = 96_000
    n_users = 40_000

    dates = pd.to_datetime(START_DATE) + pd.to_timedelta(
        rng.integers(0, (pd.to_datetime(END_DATE) - pd.to_datetime(START_DATE)).days, n),
        unit="D",
    )
    df = pd.DataFrame({
        "order_id": [f"ORD{i:06d}" for i in range(n)],
        "user_id":  [f"u{rng.integers(0, n_users):05d}" for _ in range(n)],
        "date":     dates,
        "revenue":  np.round(rng.lognormal(mean=3.8, sigma=0.8, size=n).clip(10, 2000), 2),
        "category": rng.choice(CATEGORIES, size=n,
                                p=[0.15,0.14,0.12,0.11,0.10,0.09,0.08,0.07,0.07,0.07]),
        "channel":  rng.choice(CHANNELS, size=n, p=CHANNEL_WEIGHTS),
    })
    df["month"] = df["date"].dt.to_period("M")
    return df.sort_values("date").reset_index(drop=True)


# ── Public API ────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_orders() -> pd.DataFrame:
    return _load_olist_orders() if _olist_present() else _synthetic_orders()


@lru_cache(maxsize=1)
def get_funnel() -> pd.DataFrame:
    stages = ["Visit", "Product View", "Add to Cart", "Checkout", "Purchase"]
    users  = [180_000, 98_000, 42_000, 22_000, int(len(get_orders()))]
    return pd.DataFrame({"stage": stages, "users": users,
                          "stage_order": range(len(stages))})


@lru_cache(maxsize=1)
def get_cohort() -> pd.DataFrame:
    orders = get_orders().copy()
    orders["cohort"] = (
        orders.groupby("user_id")["date"].transform("min").dt.to_period("M")
    )
    orders["order_month"] = orders["date"].dt.to_period("M")
    orders["week_offset"] = (
        (orders["order_month"] - orders["cohort"])
        .apply(lambda x: x.n if hasattr(x, "n") else 0)
        .clip(0, 11)
    )

    cohort_sizes = orders.groupby("cohort")["user_id"].nunique().rename("cohort_size")
    cohort_act   = (
        orders.groupby(["cohort", "week_offset"])["user_id"]
        .nunique().reset_index()
        .merge(cohort_sizes, on="cohort")
    )
    cohort_act["retention"] = (cohort_act["user_id"] / cohort_act["cohort_size"]).round(3)
    cohort_act.rename(columns={"week_offset": "week"}, inplace=True)
    cohort_act["cohort"] = cohort_act["cohort"].astype(str)

    top_cohorts = (
        cohort_act[cohort_act["week"] == 0]
        .nlargest(10, "cohort_size")["cohort"]
    )
    result = cohort_act[cohort_act["cohort"].isin(top_cohorts)]
    return result[["cohort", "week", "retention", "cohort_size"]].reset_index(drop=True)


@lru_cache(maxsize=1)
def get_daily_metrics() -> pd.DataFrame:
    orders = get_orders()
    daily  = (
        orders.groupby("date")
        .agg(orders_count=("order_id", "count"), gmv=("revenue", "sum"))
        .reset_index()
    )
    daily["dau"]           = (daily["orders_count"] * 8).astype(int)
    daily["mau"]           = (daily["dau"] * 7.2).astype(int)
    daily["arpu"]          = (daily["gmv"] / daily["dau"]).round(2)
    daily["dau_mau_ratio"] = (daily["dau"] / daily["mau"] * 100).round(1)
    daily.rename(columns={"orders_count": "orders"}, inplace=True)
    return daily


@lru_cache(maxsize=1)
def get_rfm() -> pd.DataFrame:
    orders   = get_orders()
    snapshot = orders["date"].max()

    rfm = orders.groupby("user_id").agg(
        recency  =("date",     lambda x: (snapshot - x.max()).days),
        frequency=("order_id", "count"),
        monetary =("revenue",  "sum"),
    ).reset_index()

    for col, labels in [
        ("recency",   [5, 4, 3, 2, 1]),
        ("frequency", [1, 2, 3, 4, 5]),
        ("monetary",  [1, 2, 3, 4, 5]),
    ]:
        lbl = col[0].upper()
        try:
            rfm[f"{lbl}_score"] = pd.qcut(rfm[col], 5, labels=labels, duplicates="drop")
        except Exception:
            rfm[f"{lbl}_score"] = 3

    rfm["rfm_score"] = (
        rfm["R_score"].astype(int) + rfm["F_score"].astype(int) + rfm["M_score"].astype(int)
    )

    def segment(row):
        r, f = int(row["R_score"]), int(row["F_score"])
        if r >= 4 and f >= 4: return "Champions"
        if r >= 3 and f >= 3: return "Loyal"
        if r >= 4 and f <= 2: return "New Customers"
        if r <= 2 and f >= 3: return "At Risk"
        if r <= 2 and f <= 2: return "Lost"
        return "Potential Loyalists"

    rfm["segment"] = rfm.apply(segment, axis=1)
    return rfm


@lru_cache(maxsize=1)
def get_product_analytics() -> pd.DataFrame:
    orders = get_orders()
    rows   = []
    for cat in sorted(orders["category"].unique()):
        sub  = orders[orders["category"] == cat]
        seed = hash(cat) % (2 ** 32)
        rng  = np.random.default_rng(seed)
        rows.append({
            "page":             cat,
            "sessions":         len(sub) * 8,
            "avg_time_sec":     int(rng.uniform(45, 220)),
            "bounce_rate":      round(float(rng.uniform(0.28, 0.70)), 2),
            "exit_rate":        round(float(rng.uniform(0.18, 0.55)), 2),
            "scroll_depth":     round(float(rng.uniform(0.38, 0.85)), 2),
            "add_to_cart_rate": round(sub["revenue"].count() / max(len(sub) * 8, 1), 2),
            "revenue":          round(float(sub["revenue"].sum()), 2),
        })
    return (
        pd.DataFrame(rows)
        .sort_values("sessions", ascending=False)
        .reset_index(drop=True)
    )


def data_source_label() -> str:
    if _olist_present():
        o = get_orders()
        return (
            f"Olist dataset · {len(o):,} delivered orders · "
            f"{o['date'].min().strftime('%b %Y')} – {o['date'].max().strftime('%b %Y')}"
        )
    return "Synthetic Olist-schema data · ~96k orders · Jan 2017 – Aug 2018"
