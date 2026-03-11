import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io

from cleaner import clean_tradebook, split_segments
from scorecard import compute_equity_scorecard, compute_fo_scorecard, compute_mf_scorecard
from demo_data import generate_equity_trades, generate_fo_trades, generate_mf_trades


st.set_page_config(
    page_title="Stock Scorecard - Zerodha",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&family=Syne:wght@400;600;700;800&display=swap');

html, body, .stApp { background: #07070f !important; }
* { font-family: 'DM Mono', monospace; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }

section[data-testid="stSidebar"] {
    background: #0d0d1a !important;
    border-right: 1px solid #1a1a2e;
}
div[data-testid="stMetric"] {
    background: #0f0f1c;
    border: 1px solid #1e1e32;
    border-radius: 10px;
    padding: 1rem 1.2rem !important;
}
div[data-testid="stMetricLabel"] > div {
    color: #6b7280 !important;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
div[data-testid="stMetricValue"] {
    color: #f0f0f5 !important;
    font-family: 'Syne', sans-serif !important;
    font-size: 1.5rem !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #6b7280 !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00ff87 !important;
}
div[data-testid="stFileUploader"] {
    background: #0f0f1c;
    border: 1px dashed #2a2a44;
    border-radius: 10px;
}
hr { border-color: #1e1e32 !important; }

.sc-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    color: #00ff87;
    line-height: 1;
    letter-spacing: -0.03em;
}
.sc-sub {
    color: #3d3d5e;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-top: 0.2rem;
    margin-bottom: 1.5rem;
}
.section-tag {
    font-family: 'Syne', sans-serif;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #00ff87;
    border-left: 3px solid #00ff87;
    padding-left: 0.6rem;
    margin: 1.6rem 0 0.8rem;
}
.demo-bar {
    background: rgba(99,179,255,0.08);
    border: 1px solid rgba(99,179,255,0.2);
    border-radius: 8px;
    padding: 0.7rem 1rem;
    color: #63b3ff;
    font-size: 0.76rem;
    margin-bottom: 1.2rem;
}
</style>
""", unsafe_allow_html=True)

PLOT_BG  = "#07070f"
GRID     = "#12122a"
FONT_CLR = "#9090b0"
GREEN    = "#00ff87"
RED      = "#ff4d6d"
BLUE     = "#63b3ff"
AMBER    = "#ffbe50"


def plot_layout(fig, title="", height=320):
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(family="Syne", size=13, color="#c0c0d8")),
        paper_bgcolor=PLOT_BG, plot_bgcolor=PLOT_BG,
        font=dict(family="DM Mono", color=FONT_CLR, size=11),
        margin=dict(l=10, r=10, t=36, b=10),
        xaxis=dict(gridcolor=GRID, zeroline=False),
        yaxis=dict(gridcolor=GRID, zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        hovermode="x unified",
    )
    return fig


def fmt_inr(v):
    v = float(v)
    if abs(v) >= 1e7: return f"₹{v/1e7:.2f} Cr"
    if abs(v) >= 1e5: return f"₹{v/1e5:.2f} L"
    return f"₹{v:,.0f}"


# Charts

def cum_pnl_chart(cum_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum_df["sell_date"], y=cum_df["cum_pnl"],
        mode="lines", fill="tozeroy",
        line=dict(color=GREEN, width=2),
        fillcolor="rgba(0,255,135,0.06)",
        hovertemplate="%{x|%d %b %Y}<br>P&L: ₹%{y:,.0f}<extra></extra>",
    ))
    return plot_layout(fig, "Cumulative P&L Over Time", height=300)

def monthly_bar_chart(monthly_df):
    colors = [GREEN if v >= 0 else RED for v in monthly_df["realized_pnl"]]
    fig = go.Figure(go.Bar(
        x=monthly_df["month"], y=monthly_df["realized_pnl"],
        marker_color=colors,
        hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
    ))
    fig = plot_layout(fig, "Monthly P&L", height=280)
    fig.update_xaxes(tickangle=-45)
    return fig

def win_loss_donut(win, loss):
    fig = go.Figure(go.Pie(
        labels=["Wins", "Losses"], values=[max(win,0), max(loss,0)],
        hole=0.65, marker_colors=[GREEN, RED], textinfo="percent",
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    return plot_layout(fig, "Win/Loss", height=260)

def holding_histogram(trades_df):
    fig = px.histogram(trades_df, x="holding_days", nbins=30,
                       color_discrete_sequence=[BLUE])
    return plot_layout(fig, "Holding Period Distribution (days)", height=270)

def pnl_by_symbol_chart(trades_df):
    sym_pnl = trades_df.groupby("symbol")["realized_pnl"].sum().sort_values()
    colors  = [GREEN if v >= 0 else RED for v in sym_pnl.values]
    fig = go.Figure(go.Bar(
        x=sym_pnl.values, y=sym_pnl.index, orientation="h",
        marker_color=colors,
        hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>",
    ))
    fig = plot_layout(fig, "P&L by Symbol", height=max(300, len(sym_pnl)*22))
    fig.update_xaxes(tickprefix="₹")
    return fig

def return_scatter(trades_df):
    fig = px.scatter(
        trades_df, x="holding_days", y="return_pct",
        size="investment", color="return_pct",
        color_continuous_scale=["#ff4d6d", "#1a1a2e", "#00ff87"],
        range_color=[-50, 50],
        labels={"holding_days": "Holding Days", "return_pct": "Return %"},
        hover_data=["symbol", "buy_date", "sell_date"],
    )
    fig = plot_layout(fig, "Return % vs Holding Days (bubble = investment size)", height=320)
    fig.update_coloraxes(showscale=False)
    return fig

def top_symbols_bar(top_df):
    top_df = top_df.head(10).sort_values("trade_value")
    fig = go.Figure(go.Bar(
        x=top_df["trade_value"], y=top_df["symbol"], orientation="h",
        marker_color=BLUE,
        hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>",
    ))
    fig = plot_layout(fig, "Top Symbols by Trade Volume", height=310)
    fig.update_xaxes(tickprefix="₹")
    return fig


# Tab renderers

def render_equity_tab(sc):
    st.markdown('<div class="section-tag">Performance</div>', unsafe_allow_html=True)
    pnl = sc.get("total_realized_pnl", 0)
    pf  = sc.get("profit_factor", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realised P&L", fmt_inr(pnl),
              delta=f"{'▲' if pnl >= 0 else '▼'} {abs(pnl)/max(sc.get('total_buy_value',1),1)*100:.1f}% of capital")
    c2.metric("Win Rate", f"{sc.get('win_rate',0):.1f}%",
              delta=f"{sc.get('win_count',0)}W / {sc.get('loss_count',0)}L")
    c3.metric("Profit Factor", f"{min(pf,99):.2f}x")
    c4.metric("Avg Hold",      f"{sc.get('avg_holding_days',0):.0f} days")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Closed Trades", f"{sc.get('total_trades',0):,}")
    c6.metric("Avg Win",       fmt_inr(sc.get("avg_win", 0)))
    c7.metric("Avg Loss",      fmt_inr(sc.get("avg_loss", 0)))
    c8.metric("Unique Stocks", str(sc.get("unique_symbols", 0)))

    if sc.get("has_trades"):
        trades = sc["trades_df"]
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.plotly_chart(cum_pnl_chart(sc["cum_pnl"]), use_container_width=True)
        with col_b:
            st.plotly_chart(win_loss_donut(sc.get("win_count",0), sc.get("loss_count",0)),
                            use_container_width=True)
        col_c, col_d = st.columns(2)
        with col_c:
            st.plotly_chart(monthly_bar_chart(sc["monthly_pnl"]), use_container_width=True)
        with col_d:
            st.plotly_chart(holding_histogram(trades), use_container_width=True)

    st.markdown('<div class="section-tag">Risk</div>', unsafe_allow_html=True)
    r1, r2, r3, r4 = st.columns(4)
    wt = sc.get("worst_trade")
    worst_pnl = float(wt["realized_pnl"]) if wt is not None and isinstance(wt, dict) else 0
    r1.metric("Return Volatility",   f"±{sc.get('return_std',0):.1f}%")
    r2.metric("Sharpe (simplified)", f"{sc.get('sharpe',0):.2f}")
    r3.metric("Max Consec. Losses",  str(sc.get("max_consec_losses", 0)))
    r4.metric("Worst Trade",         fmt_inr(worst_pnl))

    st.markdown('<div class="section-tag">Conviction</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Median Investment / Trade", fmt_inr(sc.get("median_investment", 0)))
    k2.metric("Capital Deployed",          fmt_inr(sc.get("total_buy_value", 0)))
    k3.metric("Max Consec. Wins",          str(sc.get("max_consec_wins", 0)))
    k4.metric("Top-5 Concentration",       f"{sc.get('concentration_top5', 0):.1f}%")

    if sc.get("has_trades"):
        trades = sc["trades_df"]
        col_e, col_f = st.columns(2)
        with col_e:
            st.plotly_chart(pnl_by_symbol_chart(trades), use_container_width=True)
        with col_f:
            st.plotly_chart(return_scatter(trades), use_container_width=True)
        top_sym = sc.get("top_symbols")
        if top_sym is not None and not top_sym.empty:
            st.plotly_chart(top_symbols_bar(top_sym), use_container_width=True)

    pos = sc.get("open_positions")
    if pos is not None and not pos.empty:
        st.markdown('<div class="section-tag">Open Positions</div>', unsafe_allow_html=True)
        dp = pos.copy()
        dp.columns = [c.replace("_"," ").title() for c in dp.columns]
        st.dataframe(dp, use_container_width=True, hide_index=True)

    if sc.get("has_trades"):
        with st.expander("📋 All Closed Trades"):
            t = sc["trades_df"].copy()
            t["buy_date"]     = t["buy_date"].dt.strftime("%d %b %Y")
            t["sell_date"]    = t["sell_date"].dt.strftime("%d %b %Y")
            t["realized_pnl"] = t["realized_pnl"].round(2)
            t["return_pct"]   = t["return_pct"].round(2)
            t.columns = [c.replace("_"," ").title() for c in t.columns]
            st.dataframe(t, use_container_width=True, hide_index=True)


def render_fo_tab(sc):
    st.markdown('<div class="section-tag">Performance</div>', unsafe_allow_html=True)
    pnl = sc.get("total_realized_pnl", 0)
    pf  = sc.get("profit_factor", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realised P&L",  fmt_inr(pnl))
    c2.metric("Win Rate",      f"{sc.get('win_rate',0):.1f}%",
              delta=f"{sc.get('win_count',0)}W / {sc.get('loss_count',0)}L")
    c3.metric("Profit Factor", f"{min(pf,99):.2f}x")
    c4.metric("Instruments",   str(sc.get("unique_instruments", 0)))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Closed Trades", f"{sc.get('total_trades',0):,}")
    c6.metric("Avg Win",       fmt_inr(sc.get("avg_win", 0)))
    c7.metric("Avg Loss",      fmt_inr(sc.get("avg_loss", 0)))
    c8.metric("Avg Hold",      f"{sc.get('avg_holding_days',0):.1f} days")

    if sc.get("has_trades"):
        c_a, c_b = st.columns([2, 1])
        with c_a:
            st.plotly_chart(cum_pnl_chart(sc["cum_pnl"]), use_container_width=True)
        with c_b:
            st.plotly_chart(win_loss_donut(sc.get("win_count",0), sc.get("loss_count",0)),
                            use_container_width=True)
        st.plotly_chart(monthly_bar_chart(sc["monthly_pnl"]), use_container_width=True)

        ib = sc.get("instrument_breakdown")
        if ib is not None and not ib.empty:
            fig = px.pie(ib, names="instrument_type", values="trade_value",
                         color_discrete_sequence=[GREEN, RED, BLUE, AMBER],
                         title="CE / PE / FUT Volume Mix")
            plot_layout(fig, height=280)
            st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 All Closed Trades"):
            t = sc["trades_df"].copy()
            t["buy_date"]     = t["buy_date"].dt.strftime("%d %b %Y")
            t["sell_date"]    = t["sell_date"].dt.strftime("%d %b %Y")
            t["realized_pnl"] = t["realized_pnl"].round(2)
            t.columns = [c.replace("_"," ").title() for c in t.columns]
            st.dataframe(t, use_container_width=True, hide_index=True)


def render_mf_tab(sc):
    st.markdown('<div class="section-tag">Overview</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Invested",  fmt_inr(sc.get("total_invested",     0)))
    c2.metric("Total Redeemed",  fmt_inr(sc.get("total_redeemed",     0)))
    c3.metric("Realised P&L",    fmt_inr(sc.get("total_realized_pnl", 0)))
    c4.metric("Funds",           str(sc.get("unique_funds",           0)))

    if sc.get("has_trades"):
        c_a, c_b = st.columns(2)
        with c_a:
            st.plotly_chart(cum_pnl_chart(sc["cum_pnl"]), use_container_width=True)
        with c_b:
            st.plotly_chart(monthly_bar_chart(sc["monthly_pnl"]), use_container_width=True)

    fb = sc.get("fund_breakdown")
    if fb is not None and not fb.empty:
        top = fb.head(10).sort_values("trade_value")
        fig = go.Figure(go.Bar(
            x=top["trade_value"], y=top["symbol"], orientation="h",
            marker_color=BLUE,
            hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>",
        ))
        plot_layout(fig, "Investment by Fund", height=300)
        fig.update_xaxes(tickprefix="₹")
        st.plotly_chart(fig, use_container_width=True)


with st.sidebar:
    st.markdown('<div class="sc-title" style="font-size:1.4rem;margin-bottom:0.3rem">📊 SCORECARD</div>',
                unsafe_allow_html=True)
    st.markdown('<div style="color:#3d3d5e;font-size:0.7rem;letter-spacing:0.12em;'
                'text-transform:uppercase;margin-bottom:1rem">Zerodha Portfolio Analyser</div>',
                unsafe_allow_html=True)
    st.divider()
    st.markdown("**Upload Tradebook CSVs**")
    st.caption("Download from Console → Reports → Tradebook")
    eq_fo_file = st.file_uploader("Equity + F&O Tradebook", type=["csv"], key="eq_fo")
    mf_file    = st.file_uploader("Mutual Fund Tradebook",  type=["csv"], key="mf")
    st.divider()
    use_demo = st.toggle("🎮 Use demo data", value=(eq_fo_file is None and mf_file is None))
    if use_demo:
        st.caption("📌 Showing synthetic demo trades. Upload your CSVs to see real data.")
    st.divider()
    st.markdown("""
    <div style="color:#444;font-size:0.68rem;line-height:1.8">
    <b style="color:#555">Supported</b><br>
    • EQ tradebook (NSE/BSE)<br>
    • F&amp;O tradebook<br>
    • MF tradebook<br><br>
    P&amp;L uses <b style="color:#555">FIFO</b> matching.
    </div>
    """, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_and_clean(eq_bytes, mf_bytes):
    """Load CSVs, clean, and split into EQ / FNO / MF DataFrames."""
    eq_only = fo_only = mf_out = None

    if eq_bytes:
        raw  = pd.read_csv(io.BytesIO(eq_bytes), thousands=",")
        segs = split_segments(raw)       
        eq_only = segs.get("EQ")
        fo_only = segs.get("FNO")

    if mf_bytes:
        raw    = pd.read_csv(io.BytesIO(mf_bytes), thousands=",")
        result = clean_tradebook(raw)
        mf_out = result[0]

    return eq_only, fo_only, mf_out


eq_bytes = eq_fo_file.read() if eq_fo_file else None
mf_bytes = mf_file.read()    if mf_file    else None

if use_demo and eq_bytes is None and mf_bytes is None:
    with st.spinner("Generating demo data…"):
        eq_clean_raw = clean_tradebook(generate_equity_trades())[0]
        fo_clean_raw = clean_tradebook(generate_fo_trades())[0]
        mf_clean_raw = clean_tradebook(generate_mf_trades())[0]

        eq_only  = eq_clean_raw if (eq_clean_raw is not None and not eq_clean_raw.empty) else None
        fo_only  = fo_clean_raw if (fo_clean_raw is not None and not fo_clean_raw.empty) else None
        mf_cleaned = mf_clean_raw

        # also build a combined df for the Raw Data tab
        eq_combined = pd.concat(
            [d for d in [eq_only, fo_only] if d is not None],
            ignore_index=True
        ) if any(d is not None for d in [eq_only, fo_only]) else None

    demo_mode = True
else:
    with st.spinner("Cleaning tradebook…"):
        eq_only, fo_only, mf_cleaned = load_and_clean(eq_bytes, mf_bytes)

    eq_combined = pd.concat(
        [d for d in [eq_only, fo_only] if d is not None],
        ignore_index=True
    ) if any(d is not None for d in [eq_only, fo_only]) else None
    demo_mode = False

eq_sc = compute_equity_scorecard(eq_only)   if (eq_only   is not None and not eq_only.empty)   else None
fo_sc = compute_fo_scorecard(fo_only)       if (fo_only   is not None and not fo_only.empty)   else None
mf_sc = compute_mf_scorecard(mf_cleaned)   if (mf_cleaned is not None and not mf_cleaned.empty) else None


# Main UI

st.markdown('<div class="sc-title">STOCK SCORECARD</div>', unsafe_allow_html=True)
st.markdown('<div class="sc-sub">Performance · Risk · Conviction — all in one view</div>',
            unsafe_allow_html=True)

if demo_mode:
    st.markdown("""
    <div class="demo-bar">
    🎮 <strong>Demo mode</strong> — Synthetic Zerodha-style trades (2021-2024).
    Toggle off demo and upload your CSVs in the sidebar.
    </div>
    """, unsafe_allow_html=True)

if eq_sc or fo_sc or mf_sc:
    total_pnl = sum([
        (eq_sc or {}).get("total_realized_pnl", 0),
        (fo_sc or {}).get("total_realized_pnl", 0),
        (mf_sc or {}).get("total_realized_pnl", 0),
    ])
    total_cap = sum([
        (eq_sc or {}).get("total_buy_value", 0),
        (fo_sc or {}).get("total_buy_value", 0),
        (mf_sc or {}).get("total_invested",  0),
    ])
    total_tr = sum([
        (eq_sc or {}).get("total_trades", 0),
        (fo_sc or {}).get("total_trades", 0),
        (mf_sc or {}).get("total_trades", 0),
    ])
    roi = total_pnl / max(total_cap, 1) * 100

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Realised P&L", fmt_inr(total_pnl),
              delta="Profit" if total_pnl >= 0 else "Loss")
    s2.metric("Capital Deployed",   fmt_inr(total_cap))
    s3.metric("Closed Trades",      f"{total_tr:,}")
    s4.metric("Overall ROI",        f"{roi:.1f}%")
    st.divider()

    tab_labels = []
    if eq_sc: tab_labels.append("📈 Equity")
    if fo_sc: tab_labels.append("⚡ F&O")
    if mf_sc: tab_labels.append("🏦 Mutual Funds")
    tab_labels.append("📂 Raw Data")

    tabs = st.tabs(tab_labels)
    idx  = 0

    if eq_sc:
        with tabs[idx]: render_equity_tab(eq_sc)
        idx += 1
    if fo_sc:
        with tabs[idx]: render_fo_tab(fo_sc)
        idx += 1
    if mf_sc:
        with tabs[idx]: render_mf_tab(mf_sc)
        idx += 1

    with tabs[idx]:
        st.markdown('<div class="section-tag">Cleaned Data Preview</div>', unsafe_allow_html=True)
        if eq_combined is not None and not eq_combined.empty:
            st.markdown("**Equity / F&O Tradebook**")
            st.dataframe(eq_combined.head(500), use_container_width=True, hide_index=True)
            csv = eq_combined.to_csv(index=False).encode()
            st.download_button("⬇ Download Cleaned CSV", csv, "cleaned_tradebook.csv", "text/csv")
        if mf_cleaned is not None and not mf_cleaned.empty:
            st.markdown("**Mutual Fund Tradebook**")
            st.dataframe(mf_cleaned.head(200), use_container_width=True, hide_index=True)
else:
    st.markdown("""
    <div style="text-align:center;padding:5rem 0">
        <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:700;
                    margin-bottom:0.75rem;color:#333">
            Upload your Zerodha tradebook to begin
        </div>
        <div style="font-size:0.8rem;color:#2a2a44;max-width:400px;margin:0 auto;line-height:1.8">
            Console → Reports → Tradebook → Download CSV<br>
            Then upload in the sidebar.<br><br>
            Or enable <span style="color:#63b3ff">demo data</span> to preview.
        </div>
    </div>
    """, unsafe_allow_html=True)