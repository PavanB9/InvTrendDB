"""
InvTrendDB — Inventory Analytics Dashboard with Anomaly Detection
Built with Streamlit · Plotly · Pandas
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import StringIO
from pathlib import Path

# ──────────────────────────────────────────────
# Page configuration
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="InvTrendDB — Inventory Analytics",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Custom CSS for a premium dark look
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Metric cards ── */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(99, 102, 241, .25);
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 4px 24px rgba(99, 102, 241, .08);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-weight: 600;
        letter-spacing: .03em;
        text-transform: uppercase;
        font-size: .72rem !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
        font-weight: 700;
        font-size: 1.6rem !important;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e1b4b 100%);
        border-right: 1px solid rgba(99, 102, 241, .15);
    }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #c4b5fd !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 24px;
        font-weight: 600;
    }

    /* ── Expander ── */
    details[data-testid="stExpander"] {
        border: 1px solid rgba(99, 102, 241, .2) !important;
        border-radius: 10px !important;
        background: rgba(15, 23, 42, .45);
    }

    /* ── Dataframe ── */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* ── Divider ── */
    hr {
        border-color: rgba(99, 102, 241, .15) !important;
    }

    /* ── Header badge ── */
    .header-badge {
        display: inline-block;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: .75rem;
        font-weight: 600;
        letter-spacing: .05em;
        margin-left: 8px;
        vertical-align: middle;
    }

    /* ── Anomaly indicator ── */
    .anomaly-high { color: #f87171; font-weight: 700; }
    .anomaly-med  { color: #fbbf24; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  DATA PROCESSING HELPERS
# ══════════════════════════════════════════════

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip, replace spaces/hyphens with underscores."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-]+", "_", regex=True)
        .str.replace(r"[^\w]", "", regex=True)
    )
    return df


def detect_date_column(df: pd.DataFrame) -> str | None:
    """Heuristic: find the first column whose name contains 'date' or whose
    values look like dates."""
    for col in df.columns:
        if "date" in col:
            return col
    # fallback — try parsing each object column
    for col in df.select_dtypes(include="object").columns:
        try:
            pd.to_datetime(df[col].dropna().head(20))
            return col
        except Exception:
            continue
    return None


def detect_quantity_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if "quantity" in col or "qty" in col or "amount" in col or "count" in col:
            return col
    return None


def detect_delay_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if "delay" in col or "lag" in col or "lead_time" in col:
            return col
    return None


def detect_item_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if "item" in col or "product" in col or "sku" in col or "name" in col:
            return col
    return None


def detect_status_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if "status" in col or "state" in col:
            return col
    return None


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Full cleaning pipeline.
    Returns (cleaned_df, list_of_cleaning_notes).
    """
    notes: list[str] = []
    original_rows = len(df)

    # 1. Normalize column names
    df = normalize_columns(df)
    notes.append("✅ Column names normalized (lowercased, underscores)")

    # 2. Drop fully empty rows
    df.dropna(how="all", inplace=True)
    dropped = original_rows - len(df)
    if dropped:
        notes.append(f"🗑️ Dropped {dropped} fully-empty row(s)")

    # 3. Parse dates
    date_col = detect_date_column(df)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        bad_dates = df[date_col].isna().sum()
        if bad_dates:
            notes.append(f"⚠️ {bad_dates} unparseable date(s) coerced to NaT")
        else:
            notes.append(f"✅ Parsed dates in `{date_col}`")

    # 4. Coerce numeric columns
    qty_col = detect_quantity_column(df)
    delay_col = detect_delay_column(df)
    for col in [qty_col, delay_col]:
        if col and col in df.columns:
            before_na = df[col].isna().sum()
            df[col] = pd.to_numeric(df[col], errors="coerce")
            after_na = df[col].isna().sum()
            new_na = after_na - before_na
            if new_na > 0:
                notes.append(f"⚠️ {new_na} non-numeric value(s) in `{col}` coerced to NaN")

    # 5. Fill missing numeric values with column median
    for col in [qty_col, delay_col]:
        if col and col in df.columns:
            missing = df[col].isna().sum()
            if missing:
                median_val = df[col].median()
                df[col].fillna(median_val, inplace=True)
                notes.append(f"🔧 Filled {missing} missing `{col}` value(s) with median ({median_val:.1f})")

    # 6. Fill missing status values
    status_col = detect_status_column(df)
    if status_col and status_col in df.columns:
        missing = df[status_col].isna().sum()
        if missing:
            df[status_col].fillna("unknown", inplace=True)
            notes.append(f"🔧 Filled {missing} missing `{status_col}` value(s) with 'unknown'")
        # normalize status text
        df[status_col] = df[status_col].astype(str).str.strip().str.lower()

    # 7. Sort by date if available
    if date_col and date_col in df.columns:
        df.sort_values(date_col, inplace=True)
        df.reset_index(drop=True, inplace=True)
        notes.append("✅ Rows sorted by date")

    return df, notes


# ══════════════════════════════════════════════
#  ANOMALY DETECTION
# ══════════════════════════════════════════════

def detect_anomalies(df: pd.DataFrame, sigma: float = 2.0) -> pd.DataFrame:
    """
    Flag rows where quantity or delay_days fall outside
    mean ± sigma * std.  Returns the flagged subset with
    reason annotations.
    """
    qty_col = detect_quantity_column(df)
    delay_col = detect_delay_column(df)
    flags: list[dict] = []

    for col in [qty_col, delay_col]:
        if col is None or col not in df.columns:
            continue
        mean = df[col].mean()
        std = df[col].std()
        if std == 0:
            continue
        lower = mean - sigma * std
        upper = mean + sigma * std
        mask = (df[col] < lower) | (df[col] > upper)
        for idx in df[mask].index:
            val = df.at[idx, col]
            deviation = abs(val - mean) / std
            flags.append({
                "row": idx,
                "column": col,
                "value": val,
                "mean": round(mean, 2),
                "std": round(std, 2),
                "deviation_σ": round(deviation, 2),
                "direction": "HIGH" if val > upper else "LOW",
            })

    if not flags:
        return pd.DataFrame()

    anomaly_df = pd.DataFrame(flags)
    # merge back original row data
    original_cols = list(df.columns)
    merged = anomaly_df.merge(
        df.reset_index().rename(columns={"index": "row"}),
        on="row",
        how="left",
    )
    return merged


# ══════════════════════════════════════════════
#  CHART BUILDERS
# ══════════════════════════════════════════════

PLOTLY_TEMPLATE = "plotly_dark"
COLOR_PALETTE = px.colors.qualitative.Set2


def build_weekly_throughput(df: pd.DataFrame):
    date_col = detect_date_column(df)
    qty_col = detect_quantity_column(df)
    if not date_col or not qty_col:
        return None

    weekly = (
        df.groupby(pd.Grouper(key=date_col, freq="W-MON"))
        [qty_col].sum()
        .reset_index()
    )
    weekly.columns = ["week", "total_quantity"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["week"],
        y=weekly["total_quantity"],
        marker=dict(
            color=weekly["total_quantity"],
            colorscale=[[0, "#6366f1"], [0.5, "#8b5cf6"], [1, "#c084fc"]],
            line=dict(width=0),
            cornerradius=5,
        ),
        hovertemplate="<b>Week of %{x|%b %d}</b><br>Quantity: %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=dict(text="Weekly Throughput", font=dict(size=18)),
        xaxis_title="Week",
        yaxis_title="Total Quantity",
        height=380,
        margin=dict(t=50, b=40, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_delay_frequency(df: pd.DataFrame):
    date_col = detect_date_column(df)
    delay_col = detect_delay_column(df)
    if not date_col or not delay_col:
        return None

    weekly = (
        df[df[delay_col] > 0]
        .groupby(pd.Grouper(key=date_col, freq="W-MON"))
        .size()
        .reset_index(name="delayed_shipments")
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weekly[date_col],
        y=weekly["delayed_shipments"],
        mode="lines+markers",
        line=dict(color="#f472b6", width=3, shape="spline"),
        marker=dict(size=8, color="#f472b6", line=dict(width=2, color="#1e1b4b")),
        fill="tozeroy",
        fillcolor="rgba(244,114,182,.12)",
        hovertemplate="<b>Week of %{x|%b %d}</b><br>Delayed: %{y}<extra></extra>",
    ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=dict(text="Delay Frequency Over Time", font=dict(size=18)),
        xaxis_title="Week",
        yaxis_title="Delayed Shipments",
        height=380,
        margin=dict(t=50, b=40, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_top_items(df: pd.DataFrame, top_n: int = 10):
    item_col = detect_item_column(df)
    qty_col = detect_quantity_column(df)
    if not item_col or not qty_col:
        return None

    top = (
        df.groupby(item_col)[qty_col]
        .sum()
        .sort_values(ascending=True)
        .tail(top_n)
        .reset_index()
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top[qty_col],
        y=top[item_col],
        orientation="h",
        marker=dict(
            color=top[qty_col],
            colorscale=[[0, "#22d3ee"], [0.5, "#6366f1"], [1, "#a855f7"]],
            line=dict(width=0),
            cornerradius=5,
        ),
        hovertemplate="<b>%{y}</b><br>Total Qty: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=dict(text="Top Items by Volume", font=dict(size=18)),
        xaxis_title="Total Quantity",
        yaxis_title="",
        height=380,
        margin=dict(t=50, b=40, l=140, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_status_breakdown(df: pd.DataFrame):
    status_col = detect_status_column(df)
    if not status_col:
        return None

    counts = df[status_col].value_counts().reset_index()
    counts.columns = ["status", "count"]

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=counts["status"],
        values=counts["count"],
        hole=0.55,
        marker=dict(
            colors=["#6366f1", "#22d3ee", "#f472b6", "#fbbf24", "#34d399"],
            line=dict(color="#0f172a", width=2),
        ),
        textinfo="label+percent",
        textfont=dict(size=13),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
    ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=dict(text="Status Breakdown", font=dict(size=18)),
        height=380,
        margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def build_anomaly_scatter(df: pd.DataFrame, anomalies: pd.DataFrame):
    """Overlay anomalies on a quantity time-series scatter."""
    date_col = detect_date_column(df)
    qty_col = detect_quantity_column(df)
    if not date_col or not qty_col or anomalies.empty:
        return None

    qty_anomalies = anomalies[anomalies["column"] == qty_col]

    fig = go.Figure()
    # normal points
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df[qty_col],
        mode="markers",
        marker=dict(size=7, color="#6366f1", opacity=.5),
        name="Normal",
        hovertemplate="%{x|%b %d}: %{y:,.0f}<extra></extra>",
    ))
    # anomaly points
    if not qty_anomalies.empty:
        fig.add_trace(go.Scatter(
            x=qty_anomalies[date_col], y=qty_anomalies["value"],
            mode="markers",
            marker=dict(size=14, color="#f87171", symbol="diamond",
                        line=dict(width=2, color="#fef2f2")),
            name="Anomaly",
            hovertemplate="<b>ANOMALY</b><br>%{x|%b %d}: %{y:,.0f}<extra></extra>",
        ))
    # mean ± 2σ bands
    mean = df[qty_col].mean()
    std = df[qty_col].std()
    fig.add_hline(y=mean, line_dash="dash", line_color="#94a3b8",
                  annotation_text=f"μ = {mean:.0f}", annotation_font_color="#94a3b8")
    fig.add_hrect(y0=mean - 2 * std, y1=mean + 2 * std,
                  fillcolor="rgba(99,102,241,.07)", line_width=0,
                  annotation_text="±2σ", annotation_font_color="#6366f1")

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=dict(text="Quantity Distribution with Anomalies", font=dict(size=18)),
        xaxis_title="Date", yaxis_title="Quantity",
        height=400,
        margin=dict(t=50, b=40, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ══════════════════════════════════════════════
#  MAIN UI
# ══════════════════════════════════════════════

def main():
    # ── Sidebar ──
    with st.sidebar:
        st.markdown("# 📦 InvTrendDB")
        st.markdown(
            '<span class="header-badge">v1.0</span>',
            unsafe_allow_html=True,
        )
        st.caption("Inventory Analytics & Anomaly Detection")
        st.divider()

        st.markdown("### 📂 Data Source")
        upload = st.file_uploader(
            "Upload CSV",
            type=["csv"],
            help="Drag & drop your inventory / shipment CSV here.",
        )
        
        with st.expander("📋 What kind of CSV does this expect?"):
            st.markdown("""
            Each row should be a **shipment or transaction event**, not a product listing.
            
            **Required columns:** `date`, `item` (or `product`/`sku`), `quantity`, `delay` (or `lead_time`)  
            **Optional:** `status`
            
            ⚠️ A product catalog won't work here. Download `sample_data.csv` from the repo to see the expected format.
            """)
            
        use_sample = st.checkbox("Use sample dataset", value=not bool(upload))

        st.divider()
        st.markdown("### ⚙️ Settings")
        sigma = st.slider(
            "Anomaly threshold (σ)",
            min_value=1.0, max_value=4.0, value=2.0, step=0.25,
            help="Rows beyond this many standard deviations from the mean are flagged.",
        )
        top_n = st.slider("Top-N items", 3, 20, 8)

    # ── Load data ──
    if upload:
        raw_text = upload.read().decode("utf-8", errors="replace")
        raw_df = pd.read_csv(StringIO(raw_text))
        source_label = upload.name
    elif use_sample:
        sample_path = Path(__file__).parent / "sample_data.csv"
        if not sample_path.exists():
            st.error("sample_data.csv not found in the app directory.")
            return
        raw_df = pd.read_csv(sample_path)
        source_label = "sample_data.csv"
    else:
        st.info("👈 Upload a CSV or enable the sample dataset to get started.")
        return

    # ── Clean ──
    df, cleaning_notes = clean_dataframe(raw_df.copy())

    # ── Detect anomalies ──
    anomalies = detect_anomalies(df, sigma=sigma)

    # ── Header ──
    st.markdown(
        "# 📦 Inventory Analytics Dashboard"
        '<span class="header-badge">LIVE</span>',
        unsafe_allow_html=True,
    )
    st.caption(f"Analyzing **{source_label}** · {len(df):,} rows · σ = {sigma}")

    # ── Summary metrics ──
    date_col = detect_date_column(df)
    qty_col = detect_quantity_column(df)
    delay_col = detect_delay_column(df)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Shipments", f"{len(df):,}")
    m2.metric("Total Quantity", f"{df[qty_col].sum():,.0f}" if qty_col else "—")
    m3.metric("Avg Delay", f"{df[delay_col].mean():.1f} days" if delay_col else "—")
    m4.metric("Anomalies", f"{len(anomalies)}")
    if date_col:
        min_d = df[date_col].min()
        max_d = df[date_col].max()
        m5.metric("Date Range", f"{min_d:%b %d} – {max_d:%b %d, %Y}")
    else:
        m5.metric("Date Range", "—")

    st.divider()

    # ── Tabs ──
    tab_charts, tab_anomalies, tab_cleaning, tab_raw = st.tabs([
        "📊 Trend Charts",
        "🚨 Anomaly Detection",
        "🧹 Data Cleaning Log",
        "📋 Raw Data",
    ])

    # ── TAB: Charts ──
    with tab_charts:
        col_a, col_b = st.columns(2)
        with col_a:
            fig = build_weekly_throughput(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Cannot build throughput chart — missing date or quantity column.")

        with col_b:
            fig = build_delay_frequency(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Cannot build delay chart — missing date or delay column.")

        col_c, col_d = st.columns(2)
        with col_c:
            fig = build_top_items(df, top_n=top_n)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Cannot build item chart — missing item or quantity column.")

        with col_d:
            fig = build_status_breakdown(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Cannot build status chart — missing status column.")

    # ── TAB: Anomalies ──
    with tab_anomalies:
        if anomalies.empty:
            st.success("🎉 No anomalies detected at the current threshold.")
        else:
            st.markdown(f"### 🚨 {len(anomalies)} Anomalous Data Point(s) Detected")
            st.caption(f"Flagged using **{sigma}σ** from the mean")

            # Scatter overlay
            fig = build_anomaly_scatter(df, anomalies)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            # Anomaly table — colour-coded
            display_cols = []
            for c in ["direction", "column", "value", "mean", "std", "deviation_σ"]:
                if c in anomalies.columns:
                    display_cols.append(c)
            # Add original data columns
            date_col_name = detect_date_column(df)
            item_col_name = detect_item_column(df)
            for c in [date_col_name, item_col_name]:
                if c and c in anomalies.columns:
                    display_cols.insert(0, c)

            styled = anomalies[display_cols].copy()
            if date_col_name and date_col_name in styled.columns:
                styled[date_col_name] = styled[date_col_name].dt.strftime("%Y-%m-%d")

            def color_direction(val):
                if val == "HIGH":
                    return "background-color: rgba(248,113,113,.25); color: #f87171; font-weight:700"
                elif val == "LOW":
                    return "background-color: rgba(251,191,36,.2); color: #fbbf24; font-weight:700"
                return ""

            def color_deviation(val):
                try:
                    v = float(val)
                    if v >= 4:
                        return "background-color: rgba(248,113,113,.3); color: #f87171"
                    elif v >= 3:
                        return "background-color: rgba(248,113,113,.15); color: #fca5a5"
                    else:
                        return "background-color: rgba(251,191,36,.15); color: #fbbf24"
                except Exception:
                    return ""

            st.dataframe(
                styled.style
                    .map(color_direction, subset=["direction"] if "direction" in styled.columns else [])
                    .map(color_deviation, subset=["deviation_σ"] if "deviation_σ" in styled.columns else [])
                    .format({"value": "{:,.1f}", "mean": "{:,.1f}", "std": "{:,.1f}", "deviation_σ": "{:.2f}σ"}),
                use_container_width=True,
                height=min(400, 60 + 35 * len(styled)),
            )

    # ── TAB: Cleaning ──
    with tab_cleaning:
        st.markdown("### 🧹 Data Cleaning Report")
        st.caption("Automated preprocessing applied to your dataset")
        for note in cleaning_notes:
            st.markdown(f"- {note}")
        st.divider()
        with st.expander("Column Mapping"):
            col_map = {
                "Date": detect_date_column(df),
                "Item / Product": detect_item_column(df),
                "Quantity": detect_quantity_column(df),
                "Delay": detect_delay_column(df),
                "Status": detect_status_column(df),
            }
            st.json({k: v or "❌ not detected" for k, v in col_map.items()})

    # ── TAB: Raw Data ──
    with tab_raw:
        st.markdown(f"### 📋 Full Dataset  ({len(df):,} rows)")
        st.dataframe(df, use_container_width=True, height=500)

        csv_bytes = df.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Download cleaned CSV",
            data=csv_bytes,
            file_name="cleaned_inventory.csv",
            mime="text/csv",
        )

    # ── Footer ──
    st.divider()
    st.caption("InvTrendDB v1.0 · Built with Streamlit · Plotly · Pandas")


if __name__ == "__main__":
    main()
