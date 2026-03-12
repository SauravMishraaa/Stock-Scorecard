from __future__ import annotations
import io
from datetime import datetime

try:
    from reportlab.lib.pagesizes import  A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    _RL_AVAILABLE = True
except ImportError:
    _RL_AVAILABLE = False

def _inr(v) -> str:
    v = float(v or 0)
    if abs(v) >= 1e7: return f"₹{v/1e7:.2f} Cr"
    if abs(v) >= 1e5: return f"₹{v/1e5:.2f} L"
    return f"₹{v:,.0f}"


def _pct(v) -> str:
    return f"{float(v or 0):.1f}%"


def generate_scorecard_pdf(
    eq_sc: dict | None,
    fo_sc: dict | None,
    mf_sc: dict | None,
    tax_eq: dict | None = None,
    tax_fo: dict | None = None,
    broker: str = "Zerodha",
) -> bytes | None:
    """Generate PDF report from scorecard data."""
    if not _RL_AVAILABLE:
        return None
    
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", fontSize=20, fontName="Helvetica-Bold",
                     textColor=colors.HexColor("#00cc6e"), spaceAfter=10)
    H2 = ParagraphStyle("H2", fontSize=12, fontName="Helvetica-Bold",
                         textColor=colors.HexColor("#1a1a2e"), spaceBefore=14, spaceAfter=4)
    BODY = ParagraphStyle("BODY", fontSize=9, fontName="Helvetica",
                          textColor=colors.HexColor("#333333"))
    SMALL = ParagraphStyle("SMALL", fontSize=8, fontName="Helvetica",
                           textColor=colors.HexColor("#888888"))

    def hr():
        return HRFlowable(width="100%", thickness=0.5,
                          color=colors.HexColor("#cccccc"), spaceAfter=6)
    
    def metric_table(rows: list[tuple[str, str]]) -> Table:
        """Render a 4-column key-value metric table."""
        cells = []
        for i in range(0, len(rows), 4):
            chunk = rows[i:i+4]
            label_row = []
            value_row = []
            for label, value in chunk:
                label_row.append(Paragraph(label, SMALL))
                color = "#00cc6e" if (isinstance(value, str) and value.startswith("▲")) else \
                        "#ff4d6d" if (isinstance(value, str) and value.startswith("▼")) else "#111111"
                val_style = ParagraphStyle("V", fontSize=11, fontName="Helvetica-Bold",
                                           textColor=colors.HexColor(color))
                value_row.append(Paragraph(str(value), val_style))
            # Pad to 4 if needed
            while len(label_row) < 4:
                label_row.append(Paragraph("", SMALL))
                value_row.append(Paragraph("", SMALL))
            cells.extend([label_row, value_row])
        
        col_w = [4.3*cm] * 4
        t = Table(cells, colWidths=col_w, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9f9f9")),
            ("GRID",       (0, 0), (-1, -1), 0.3, colors.HexColor("#e0e0e0")),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        return t
    
    def section_table(headers: list, data: list) -> Table:
        rows = [headers] + data
        col_w = [17.4 / len(headers) * cm] * len(headers)
        t = Table(rows, colWidths=col_w, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ]))
        return t
    
    story = []

    # Header
    story.append(Paragraph("STOCK SCORECARD", H1))
    story.append(Paragraph(
        f"{broker} Portfolio Report &nbsp;·&nbsp; Generated {datetime.now().strftime('%d %b %Y, %H:%M')}",
        SMALL,
    ))
    story.append(hr())

    # Summary Bar
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

    summary_rows = [
        ("Total Realised P&L", ("▲ " if total_pnl >= 0 else "▼ ") + _inr(total_pnl)),
        ("Capital Deployed",   _inr(total_cap)),
        ("Closed Trades",      str(total_tr)),
        ("Overall ROI",        _pct(roi)),
    ]
    story.append(metric_table(summary_rows))
    story.append(Spacer(1, 10))

    # Equity Section
    if eq_sc and eq_sc.get("has_trades"):
        story.append(Paragraph("📈 Equity", H2))
        pnl = eq_sc["total_realized_pnl"]
        rows = [
            ("Realised P&L",      ("▲ " if pnl >= 0 else "▼ ") + _inr(pnl)),
            ("Win Rate",          _pct(eq_sc["win_rate"])),
            ("Profit Factor",     f"{eq_sc['profit_factor']:.2f}x"),
            ("Avg Hold",          f"{eq_sc['avg_holding_days']:.0f} days"),
            ("Closed Trades",     str(eq_sc["total_trades"])),
            ("Avg Win",           _inr(eq_sc["avg_win"])),
            ("Avg Loss",          _inr(eq_sc["avg_loss"])),
            ("Unique Stocks",     str(eq_sc["unique_symbols"])),
            ("Sharpe",            f"{eq_sc['sharpe']:.2f}"),
            ("Max Consec Losses", str(eq_sc["max_consec_losses"])),
            ("Top-5 Conc.",       _pct(eq_sc["concentration_top5"])),
            ("Capital Deployed",  _inr(eq_sc["total_buy_value"])),
        ]
        story.append(metric_table(rows))
        
        # Top trades table
        if not eq_sc["trades_df"].empty:
            story.append(Spacer(1, 6))
            t_df = eq_sc["trades_df"].sort_values("realized_pnl").head(5)
            story.append(Paragraph("Worst 5 Trades", BODY))
            headers = ["Symbol", "Buy Date", "Sell Date", "Hold", "Inv.", "P&L", "Ret%"]
            data = [
                [
                    str(r["symbol"]),
                    r["buy_date"].strftime("%d %b %Y") if hasattr(r["buy_date"], "strftime") else str(r["buy_date"]),
                    r["sell_date"].strftime("%d %b %Y") if hasattr(r["sell_date"], "strftime") else str(r["sell_date"]),
                    f"{r['holding_days']}d",
                    _inr(r["investment"]),
                    _inr(r["realized_pnl"]),
                    f"{r['return_pct']:.1f}%",
                ]
                for _, r in t_df.iterrows()
            ]
            story.append(section_table(headers, data))

    # F&O Section
    if fo_sc and fo_sc.get("has_trades"):
        story.append(Paragraph("⚡ F&O", H2))
        pnl = fo_sc["total_realized_pnl"]
        rows = [
            ("Realised P&L",  ("▲ " if pnl >= 0 else "▼ ") + _inr(pnl)),
            ("Win Rate",      _pct(fo_sc["win_rate"])),
            ("Profit Factor", f"{fo_sc['profit_factor']:.2f}x"),
            ("Instruments",   str(fo_sc["unique_instruments"])),
            ("Closed Trades", str(fo_sc["total_trades"])),
            ("Avg Win",       _inr(fo_sc["avg_win"])),
            ("Avg Loss",      _inr(fo_sc["avg_loss"])),
            ("Avg Hold",      f"{fo_sc['avg_holding_days']:.1f} days"),
        ]
        story.append(metric_table(rows))

    # Mutual Fund Section
    if mf_sc:
        story.append(Paragraph("🏦 Mutual Funds", H2))
        rows = [
            ("Total Invested",  _inr(mf_sc["total_invested"])),
            ("Total Redeemed",  _inr(mf_sc["total_redeemed"])),
            ("Realised P&L",    _inr(mf_sc["total_realized_pnl"])),
            ("Unique Funds",    str(mf_sc["unique_funds"])),
        ]
        story.append(metric_table(rows))
    
    # Tax Summary Section
    if tax_eq:
        story.append(Paragraph("🧾 Tax Estimate (Equity)", H2))
        rows = [
            ("STCG Gains",     _inr(tax_eq["stcg_gains"])),
            ("STCG Tax @15%",  _inr(tax_eq["stcg_tax"])),
            ("LTCG Gains",     _inr(tax_eq["ltcg_gains"])),
            ("LTCG Tax @10%",  _inr(tax_eq["ltcg_tax"])),
            ("Net STCG",       _inr(tax_eq["net_stcg"])),
            ("Net LTCG",       _inr(tax_eq["net_ltcg"])),
            ("LTCG Exempt",    _inr(tax_eq["ltcg_exemption"])),
            ("Total Estimated Tax", _inr(tax_eq["total_tax"])),
        ]
        story.append(metric_table(rows))
        story.append(Paragraph(
            "* Estimate only. Consult a CA for precise tax liability.",
            SMALL,
        ))
    
    if tax_fo:
        story.append(Paragraph("🧾 Tax Estimate (F&O — Business Income)", H2))
        rows = [
            ("Net F&O Profit",    _inr(tax_fo["net_profit"])),
            ("Indicative Tax @30%", _inr(tax_fo["estimated_tax"])),
        ]
        story.append(metric_table(rows))
        story.append(Paragraph(
            "* F&O is treated as business income. Professional advice recommended.",
            SMALL,
        ))
    
    story.append(Spacer(1, 16))
    story.append(hr())
    story.append(Paragraph(
        "Generated by Stock Scorecard · FIFO P&amp;L · Indian Tax Rules FY 2024-25",
        SMALL,
    ))

    doc.build(story)
    return buf.getvalue()