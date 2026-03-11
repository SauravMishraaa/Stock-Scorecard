import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io



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
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family="DM Mono", color=FONT_CLR, size=11),
        margin=dict(l=10, r=10, t=36, b=10),
        xaxis=dict(gridcolor=GRID, zeroline=False),
        yaxis=dict(gridcolor=GRID, zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        hovermode="x unified",
    )
    return fig

# Helper function
def fmt_inr(v):
    v = float(v)
    if abs(v) >= 1e7:
        return f"₹{v/1e7:.2f} Cr"
    if abs(v) >= 1e5:
        return f"₹{v/1e5:.2f} L"
    return f"₹{v:,.0f}"

# Charts
def cum_pnl_chart(cum_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum_df["sell_date"], y=cum_df["cum_pnl"],
        mode="lines", fill="tozeroy",
        line=dict(color=GREEN, width=2),
        fillcolor="rgba(0,255,135,0.06)",
        name="Cumulative P&L",
        hovertemplate="%{x|%d %b %Y}<br>P&L: ₹%{y:,.0f}<extra></extra>",
    ))
    return plot_layout(fig, title="Cumulative P&L Over Time", height=300)

def monthly_bar_chart(monthly_df):
    colors = [GREEN if v>=0 else RED for v in monthly_df["realized_pnl"]]
    fig = go.Figure(go.Bar(
        x=monthly_df["month"], y=monthly_df["realized_pnl"],
        marker_color=colors, name="Monthly P&L",
        hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
    ))
    fig = plot_layout(fig, title="Monthly P&L", height=280)
    fig.update_xaxes(tickangle=-45)
    return fig
