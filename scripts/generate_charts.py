"""
generate_charts.py
Business analysis charts for az.bilet.com dataset (130 entertainment events).
Outputs 8 PNG charts to charts/ directory.
"""

import os
import warnings
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "data.csv")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
BLUE_DARK  = "#1B4F72"
BLUE_MID   = "#2E86C1"
ORANGE     = "#E67E22"
GREEN      = "#27AE60"
GREY       = "#95A5A6"
RED        = "#C0392B"
PURPLE     = "#8E44AD"

PALETTE = [BLUE_DARK, BLUE_MID, ORANGE, GREEN, GREY, RED, PURPLE]

def setup_style():
    plt.rcParams.update({
        "font.family":       "DejaVu Sans",
        "font.size":         11,
        "axes.titlesize":    14,
        "axes.titleweight":  "bold",
        "axes.labelsize":    11,
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.grid":         True,
        "axes.axisbelow":    True,
        "grid.color":        "#E0E0E0",
        "grid.linestyle":    "-",
        "grid.linewidth":    0.7,
        "figure.dpi":        120,
        "savefig.dpi":       150,
        "savefig.bbox":      "tight",
        "figure.facecolor":  "white",
        "axes.facecolor":    "white",
    })

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_data():
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

    # Keep only active events
    df = df[df["status"] == 1].copy()

    # Derived columns
    df["has_discount"] = df["price_before_discount"].notna() & (df["price_before_discount"] > df["min_price"])

    # Primary category (first tag)
    df["primary_category"] = (
        df["categories"]
        .fillna("Unknown")
        .str.split("|")
        .str[0]
        .str.strip()
    )

    # Rating tiers
    def rating_tier(r):
        if pd.isna(r) or r < 1:
            return "Minimal (1-9)"
        elif r < 10:
            return "Minimal (1-9)"
        elif r < 100:
            return "Low (10-99)"
        elif r < 500:
            return "Mid (100-499)"
        else:
            return "Top (500+)"

    df["rating_tier"] = df["rating"].apply(rating_tier)

    # City — clean encoding artefacts
    df["city"] = df["place_city"].fillna("Unknown").str.strip()

    return df

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def save(fig, filename):
    path = os.path.join(CHARTS_DIR, filename)
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved: {filename}")

# ---------------------------------------------------------------------------
# Chart 1 · Event Distribution by City
# ---------------------------------------------------------------------------
def chart_1_city_count(df):
    counts = df["city"].value_counts().sort_values()

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(counts.index, counts.values, color=BLUE_MID, edgecolor="white")

    for bar, val in zip(bars, counts.values):
        ax.text(val + 0.4, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=10, color=BLUE_DARK, fontweight="bold")

    ax.set_xlabel("Number of Events")
    ax.set_title("Event Distribution by City")
    ax.set_xlim(0, counts.max() * 1.18)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, "01_city_event_count.png")

# ---------------------------------------------------------------------------
# Chart 2 · Average Entry Price by City
# ---------------------------------------------------------------------------
def chart_2_city_price(df):
    avg = df.groupby("city")["min_price"].mean().sort_values()

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(avg.index, avg.values, color=BLUE_DARK, edgecolor="white")

    for bar, val in zip(bars, avg.values):
        ax.text(val + 5, bar.get_y() + bar.get_height() / 2,
                f"{val:,.0f} TRY", va="center", ha="left", fontsize=10, color=BLUE_DARK, fontweight="bold")

    ax.set_xlabel("Average Min Price (TRY)")
    ax.set_title("Average Entry Price by City")
    ax.set_xlim(0, avg.max() * 1.22)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, "02_city_avg_price.png")

# ---------------------------------------------------------------------------
# Chart 3 · Events by Category
# ---------------------------------------------------------------------------
def chart_3_category_count(df):
    counts = df["primary_category"].value_counts().sort_values()

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(counts.index, counts.values, color=GREEN, edgecolor="white")

    for bar, val in zip(bars, counts.values):
        ax.text(val + 0.4, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=10, color=BLUE_DARK, fontweight="bold")

    ax.set_xlabel("Number of Events")
    ax.set_title("Events by Category")
    ax.set_xlim(0, counts.max() * 1.18)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, "03_category_count.png")

# ---------------------------------------------------------------------------
# Chart 4 · Average Price by Category
# ---------------------------------------------------------------------------
def chart_4_category_price(df):
    grp = df.groupby("primary_category").agg(
        avg_price=("min_price", "mean"),
        count=("min_price", "count")
    ).sort_values("avg_price")

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(grp.index, grp["avg_price"], color=ORANGE, edgecolor="white")

    for bar, (_, row) in zip(bars, grp.iterrows()):
        ax.text(row["avg_price"] + 10,
                bar.get_y() + bar.get_height() / 2,
                f"{row['avg_price']:,.0f} TRY  (n={int(row['count'])})",
                va="center", ha="left", fontsize=9, color=BLUE_DARK)

    ax.set_xlabel("Average Min Price (TRY)")
    ax.set_title("Average Price by Category")
    ax.set_xlim(0, grp["avg_price"].max() * 1.30)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, "04_category_avg_price.png")

# ---------------------------------------------------------------------------
# Chart 5 · Price Distribution (bucketed)
# ---------------------------------------------------------------------------
def chart_5_price_distribution(df):
    bins   = [0, 500, 1000, 1500, 2000, 3000]
    labels = ["100–500", "501–1,000", "1,001–1,500", "1,501–2,000", "2,001–2,850"]

    df["price_bucket"] = pd.cut(df["min_price"], bins=bins, labels=labels, right=True)
    counts = df["price_bucket"].value_counts().reindex(labels)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, counts.values, color=BLUE_MID, edgecolor="white", width=0.6)

    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                str(val), ha="center", va="bottom", fontsize=11, fontweight="bold", color=BLUE_DARK)

    ax.set_xlabel("Price Range (TRY)")
    ax.set_ylabel("Number of Events")
    ax.set_title("Price Distribution — All Events")
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    save(fig, "05_price_distribution.png")

# ---------------------------------------------------------------------------
# Chart 6 · Discount Coverage by Category (stacked horizontal bar)
# ---------------------------------------------------------------------------
def chart_6_discount_coverage(df):
    grp = df.groupby("primary_category")["has_discount"].agg(
        discounted="sum",
        total="count"
    )
    grp["full_price"] = grp["total"] - grp["discounted"]
    grp["pct_disc"] = grp["discounted"] / grp["total"] * 100
    grp = grp.sort_values("total")

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.barh(grp.index, grp["full_price"], color=GREY, label="Full-Price", edgecolor="white")
    ax.barh(grp.index, grp["discounted"], left=grp["full_price"], color=GREEN, label="Discounted", edgecolor="white")

    for i, (_, row) in enumerate(grp.iterrows()):
        ax.text(row["total"] + 0.3, i,
                f"{row['pct_disc']:.0f}% disc.",
                va="center", ha="left", fontsize=9, color=BLUE_DARK)

    ax.set_xlabel("Number of Events")
    ax.set_title("Discount Coverage by Category")
    ax.legend(loc="lower right")
    ax.set_xlim(0, grp["total"].max() * 1.25)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, "06_discount_coverage.png")

# ---------------------------------------------------------------------------
# Chart 7 · Provider Share: Volume vs Avg Price (grouped bar, dual axis)
# ---------------------------------------------------------------------------
def chart_7_provider_share(df):
    grp = df.groupby("adapter").agg(
        count=("id", "count"),
        avg_price=("min_price", "mean")
    ).sort_values("count", ascending=False)

    x = range(len(grp))
    width = 0.4

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()

    bars1 = ax1.bar([xi - width / 2 for xi in x], grp["count"],
                    width=width, color=BLUE_MID, label="Event Count", edgecolor="white")
    bars2 = ax2.bar([xi + width / 2 for xi in x], grp["avg_price"],
                    width=width, color=ORANGE, label="Avg Price (TRY)", edgecolor="white")

    for bar, val in zip(bars1, grp["count"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                 str(int(val)), ha="center", va="bottom", fontsize=9, color=BLUE_DARK, fontweight="bold")

    for bar, val in zip(bars2, grp["avg_price"]):
        ax2.text(bar.get_x() + bar.get_width() / 2, val + 5,
                 f"{val:,.0f}", ha="center", va="bottom", fontsize=9, color=ORANGE, fontweight="bold")

    ax1.set_xticks(list(x))
    ax1.set_xticklabels(grp.index, rotation=15, ha="right")
    ax1.set_ylabel("Number of Events", color=BLUE_MID)
    ax2.set_ylabel("Avg Min Price (TRY)", color=ORANGE)
    ax1.set_title("Provider Share: Volume vs Average Price")
    ax1.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    fig.tight_layout()
    save(fig, "07_provider_share.png")

# ---------------------------------------------------------------------------
# Chart 8 · Engagement: Rating Tier Distribution
# ---------------------------------------------------------------------------
def chart_8_rating_tiers(df):
    tier_order  = ["Minimal (1-9)", "Low (10-99)", "Mid (100-499)", "Top (500+)"]
    tier_colors = [RED, ORANGE, BLUE_MID, GREEN]

    counts = df["rating_tier"].value_counts().reindex(tier_order).fillna(0).astype(int)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(tier_order, counts.values, color=tier_colors, edgecolor="white", width=0.55)

    for bar, val in zip(bars, counts.values):
        pct = val / counts.sum() * 100
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                f"{val}\n({pct:.0f}%)",
                ha="center", va="bottom", fontsize=11, fontweight="bold", color=BLUE_DARK)

    ax.set_xlabel("Rating Tier")
    ax.set_ylabel("Number of Events")
    ax.set_title("Customer Engagement: Rating Tier Distribution")
    ax.set_ylim(0, counts.max() * 1.22)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)

    legend_patches = [Patch(color=c, label=t) for c, t in zip(tier_colors, tier_order)]
    ax.legend(handles=legend_patches, loc="upper right")

    fig.tight_layout()
    save(fig, "08_rating_tiers.png")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("az.bilet.com Business Analysis — Chart Generator")
    print("=" * 50)
    setup_style()
    df = load_data()
    print(f"  Loaded {len(df)} active events\n")

    chart_1_city_count(df)
    chart_2_city_price(df)
    chart_3_category_count(df)
    chart_4_category_price(df)
    chart_5_price_distribution(df)
    chart_6_discount_coverage(df)
    chart_7_provider_share(df)
    chart_8_rating_tiers(df)

    print(f"\nAll charts saved to: {CHARTS_DIR}")

if __name__ == "__main__":
    main()
