import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random

np.random.seed(42)
random.seed(42)

START_DATE = datetime(2024, 1, 1)
END_DATE   = datetime(2024, 12, 31)
N_USERS    = 12000
N_ORDERS   = 45000

CATEGORIES = ["Skincare", "Haircare", "Supplements", "Apparel", "Accessories"]
CHANNELS   = ["Organic Search", "Paid Social", "Email", "Direct", "Referral", "Paid Search"]
DEVICES    = ["Mobile", "Desktop", "Tablet"]

def rand_dates(n, start, end):
    delta = (end - start).days
    return [start + timedelta(days=int(np.random.randint(0, delta))) for _ in range(n)]

# ---------- orders ----------
def get_orders():
    dates = rand_dates(N_ORDERS, START_DATE, END_DATE)
    channels = np.random.choice(CHANNELS, N_ORDERS, p=[0.25, 0.30, 0.15, 0.12, 0.08, 0.10])
    categories = np.random.choice(CATEGORIES, N_ORDERS)
    aov_base = {"Skincare": 68, "Haircare": 52, "Supplements": 44, "Apparel": 85, "Accessories": 38}
    aov = [round(aov_base[c] + np.random.normal(0, 12), 2) for c in categories]
    user_ids = np.random.randint(1, N_USERS + 1, N_ORDERS)
    devices = np.random.choice(DEVICES, N_ORDERS, p=[0.62, 0.31, 0.07])

    df = pd.DataFrame({
        "order_id": range(1, N_ORDERS + 1),
        "user_id": user_ids,
        "date": dates,
        "channel": channels,
        "category": categories,
        "revenue": aov,
        "device": devices,
        "units": np.random.randint(1, 5, N_ORDERS),
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["revenue"] > 0].copy()
    df["month"] = df["date"].dt.to_period("M")
    df["week"]  = df["date"].dt.to_period("W")
    return df

# ---------- funnel ----------
def get_funnel():
    visits       = 180000
    pdp_views    = int(visits * np.random.uniform(0.52, 0.58))
    add_to_cart  = int(pdp_views * np.random.uniform(0.28, 0.34))
    checkout     = int(add_to_cart * np.random.uniform(0.55, 0.65))
    purchase     = int(checkout * np.random.uniform(0.68, 0.76))

    return pd.DataFrame({
        "stage":       ["Visit", "PDP View", "Add to Cart", "Checkout", "Purchase"],
        "users":       [visits, pdp_views, add_to_cart, checkout, purchase],
        "stage_order": [1, 2, 3, 4, 5],
    })

# ---------- cohort retention ----------
def get_cohort():
    cohorts = pd.period_range(start="2024-01", periods=10, freq="M")
    sizes   = [np.random.randint(600, 1200) for _ in cohorts]

    # Retention curve: week 0=100%, decays realistically
    def retention_curve(n_weeks):
        base = [1.0, 0.42, 0.28, 0.22, 0.18, 0.16, 0.14, 0.13, 0.12, 0.11, 0.10, 0.10]
        return [round(base[min(i, len(base)-1)] + np.random.uniform(-0.02, 0.02), 3)
                for i in range(n_weeks)]

    records = []
    for cohort, size in zip(cohorts, sizes):
        n_weeks = 12 - cohorts.tolist().index(cohort)
        curve   = retention_curve(n_weeks)
        for w, rate in enumerate(curve):
            records.append({"cohort": str(cohort), "week": w, "retention": rate, "cohort_size": size})

    return pd.DataFrame(records)

# ---------- north star daily ----------
def get_daily_metrics():
    dates = pd.date_range(START_DATE, END_DATE)
    n = len(dates)

    # Add seasonality + trend
    trend = np.linspace(1.0, 1.35, n)
    season = 1 + 0.15 * np.sin(np.linspace(0, 4 * np.pi, n))
    noise  = np.random.normal(1.0, 0.04, n)

    dau    = (trend * season * noise * 2800).astype(int)
    mau    = (dau * np.random.uniform(6.5, 8.5, n)).astype(int)
    gmv    = (dau * np.random.uniform(4.2, 5.8, n)).round(0)
    orders = (dau * np.random.uniform(0.18, 0.26, n)).astype(int)

    return pd.DataFrame({
        "date":   dates,
        "dau":    dau,
        "mau":    mau,
        "gmv":    gmv,
        "orders": orders,
        "arpu":   (gmv / dau).round(2),
        "dau_mau_ratio": (dau / mau * 100).round(1),
    })

# ---------- RFM ----------
def get_rfm():
    orders = get_orders()
    snapshot = orders["date"].max()

    rfm = orders.groupby("user_id").agg(
        recency  = ("date", lambda x: (snapshot - x.max()).days),
        frequency= ("order_id", "count"),
        monetary = ("revenue", "sum"),
    ).reset_index()

    # Score 1-5
    for col, asc in [("recency", True), ("frequency", False), ("monetary", False)]:
        label = col[0].upper()
        rfm[f"{label}_score"] = pd.qcut(rfm[col], 5, labels=[5,4,3,2,1] if asc else [1,2,3,4,5])

    rfm["rfm_score"] = rfm["R_score"].astype(int) + rfm["F_score"].astype(int) + rfm["M_score"].astype(int)

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

# ---------- product analytics ----------
def get_product_analytics():
    pages = ["Homepage", "Category Page", "PDP", "Cart", "Checkout", "Account", "Search Results", "Blog"]
    records = []
    for page in pages:
        base_sessions = np.random.randint(8000, 60000)
        records.append({
            "page": page,
            "sessions":       base_sessions,
            "avg_time_sec":   int(np.random.uniform(35, 240)),
            "bounce_rate":    round(np.random.uniform(0.28, 0.72), 2),
            "exit_rate":      round(np.random.uniform(0.18, 0.55), 2),
            "scroll_depth":   round(np.random.uniform(0.35, 0.85), 2),
            "add_to_cart_rate": round(np.random.uniform(0.04, 0.22) if page == "PDP" else 0.0, 2),
        })
    return pd.DataFrame(records)
