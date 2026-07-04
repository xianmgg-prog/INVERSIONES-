import math
import io
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="Valuation Hub — Informes de Valoración",
    page_icon="📄",
    layout="wide",
)

ACCENT_GOLD = "#B68A52"
BG_MAIN = "#F7F1E8"
TEXT_PRIMARY = "#2F241B"
TEXT_SECONDARY = "#7A6856"
BORDER = "#D9C8B4"
CARD_BG = "#FFFDF9"

st.markdown(
    f"""
    <style>
    .stApp {{ background: {BG_MAIN}; color: {TEXT_PRIMARY}; font-family: "Inter", sans-serif; }}
    .report-header {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 16px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# HELPERS GENERALES
# =========================

def safe_float(x, default=None):
    if x is None:
        return default
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


def fmt_large(x):
    v = safe_float(x, None)
    if v is None:
        return "N/A"
    sign = -1 if v < 0 else 1
    v = abs(v)
    if v >= 1e12:
        return f"{sign*v/1e12:.2f}T"
    elif v >= 1e9:
        return f"{sign*v/1e9:.2f}B"
    elif v >= 1e6:
        return f"{sign*v/1e6:.2f}M"
    return f"{sign*v:,.0f}"


def html_to_pdf_bytes(html_content):
    try:
        from weasyprint import HTML as WeasyHTML
        buf = io.BytesIO()
        WeasyHTML(string=html_content).write_pdf(buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        st.error("WeasyPrint no está instalado. Ejecuta `pip install weasyprint`.")
        return None
    except Exception as e:
        st.warning(f"No se pudo generar el PDF: {e}")
        return None


PDF_BASE_CSS = """
body { font-family: Arial, sans-serif; color: #2F241B; margin: 2cm; }
h1 { color: #B68A52; margin-bottom: 0; }
.meta { color: #7A6856; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; margin-top: 1.2rem; }
th, td { border: 1px solid #D9C8B4; padding: 6px 8px; font-size: 11px; text-align: left; }
th { background: #EFE2D2; }
.veredicto { margin-top: 1.5rem; padding: 12px; background: #F9F4EC; border-radius: 8px; }
.disclaimer { margin-top: 2rem; font-size: 9px; color: #A08F7C; }
"""


# =========================
# MÓDULO 1 — ACCIONES
# =========================

def compute_stock_valuations(info):
    methods = []
    price = safe_float(info.get("currentPrice")) or safe_float(info.get("regularMarketPrice"))
    shares = safe_float(info.get("sharesOutstanding"))
    fcf = safe_float(info.get("freeCashflow"))
    revenue = safe_float(info.get("totalRevenue"))
    ebitda = safe_float(info.get("ebitda"))
    eps = safe_float(info.get("trailingEps"))
    fwd_eps = safe_float(info.get("forwardEps"))
    bvps = safe_float(info.get("bookValue"))
    div = safe_float(info.get("dividendRate"))
    total_debt = safe_float(info.get("totalDebt"), 0.0)
    cash = safe_float(info.get("totalCash"), 0.0)

    def dcf(fcf0, g_high, g_low, r, label, cal):
        if fcf0 is None or not shares or shares <= 0 or r <= g_low:
            return
        pv = sum(fcf0 * (1 + g_high) ** t / (1 + r) ** t for t in range(1, 6))
        pv += sum(fcf0 * (1 + g_high) ** 5 * (1 + g_low) ** (t - 5) / (1 + r) ** t for t in range(6, 11))
        terminal = fcf0 * (1 + g_high) ** 5 * (1 + g_low) ** 6 / (r - g_low)
        equity = pv + terminal / (1 + r) ** 10 + cash - total_debt
        methods.append({"Método": label, "Tipo": "DCF", "Calidad": cal, "Valor": equity / shares})

    if fcf:
        dcf(fcf, 0.15, 0.04, 0.11, "DCF Agresivo", "Media")
        dcf(fcf, 0.10, 0.03, 0.10, "DCF Base", "Alta")
        dcf(fcf, 0.06, 0.02, 0.09, "DCF Conservador", "Alta")

    if ebitda and ebitda > 0 and shares and shares > 0:
        for mult, cal in [(8, "Alta"), (10, "Alta"), (12, "Media"), (15, "Baja")]:
            val = (ebitda * mult + cash - total_debt) / shares
            methods.append({"Método": f"EV/EBITDA {mult}×", "Tipo": "Múltiplo", "Calidad": cal, "Valor": val})

    eps_use = eps if (eps and eps > 0) else fwd_eps
    if eps_use and eps_use > 0:
        for mult, cal in [(10, "Alta"), (15, "Alta"), (20, "Media"), (25, "Baja")]:
            methods.append({"Método": f"P/E {mult}×", "Tipo": "Múltiplo", "Calidad": cal, "Valor": eps_use * mult})

    if revenue and shares and shares > 0:
        for mult, cal in [(1, "Alta"), (2, "Alta"), (4, "Media")]:
            methods.append({"Método": f"P/Ventas {mult}×", "Tipo": "Múltiplo", "Calidad": cal, "Valor": revenue * mult / shares})

    if bvps and bvps > 0:
        for mult, cal in [(1, "Alta"), (1.5, "Alta"), (2, "Media")]:
            methods.append({"Método": f"P/Valor Libros {mult}×", "Tipo": "Múltiplo", "Calidad": cal, "Valor": bvps * mult})

    if eps_use and eps_use > 0 and bvps and bvps > 0:
        methods.append({"Método": "Graham Number", "Tipo": "Mixto", "Calidad": "Alta", "Valor": math.sqrt(22.5 * eps_use * bvps)})

    if div and div > 0:
        for g, r, label in [(0.02, 0.08, "DDM (g2%,r8%)"), (0.03, 0.09, "DDM (g3%,r9%)")]:
            if r > g:
                methods.append({"Método": label, "Tipo": "DDM", "Calidad": "Media", "Valor": div * (1 + g) / (r - g)})

    for m in methods:
        m["Precio"] = price
        m["Upside %"] = round((m["Valor"] - price) / price * 100, 1) if price else None

    return methods, price


def generar_html_informe_accion(company_name, ticker, sector, industry, currency, price, df_val):
    filas = "".join(
        f"<tr><td>{r['Método']}</td><td>{r['Tipo']}</td><td>{r['Calidad']}</td>"
        f"<td>{r['Valor']:.2f}</td><td>{r['Upside %']:+.1f}%</td></tr>"
        for _, r in df_val.iterrows()
    )
    upside_medio = df_val["Upside %"].dropna().mean()
    veredicto = (
        "Infravalorada" if upside_medio and upside_medio > 15 else
        "Sobrevalorada" if upside_medio and upside_medio < -15 else
        "En línea con su valor razonable"
    )
    return f"""
    <html><head><style>{PDF_BASE_CSS}</style></head>
    <body>
        <h1>Informe de Valoración — Acción</h1>
        <div class="meta">{company_name} ({ticker}) · {sector} · {industry}</div>
        <p>Precio actual: <b>{price:.2f} {currency}</b></p>
        <table>
            <tr><th>Método</th><th>Tipo</th><th>Calidad</th><th>Valor estimado</th><th>Upside</th></tr>
            {filas}
        </table>
        <div class="veredicto">
            <b>Upside medio:</b> {upside_medio:+.1f}% &nbsp;|&nbsp; <b>Veredicto:</b> {veredicto}
        </div>
        <div class="disclaimer">
            Informe generado automáticamente con fines informativos. No constituye asesoramiento financiero.
        </div>
    </body></html>
    """


def modulo_acciones():
    st.subheader("📈 Valoración de acciones")
    st.caption("Introduce un ticker y genera un informe de valoración con múltiples métodos.")

    ticker_input = st.text_input("Ticker (ej: AAPL, MSFT, TEF.MC)", "", key="stock_ticker")
    analyze = st.button("Analizar", type="primary", key="stock_analyze")

    if analyze and ticker_input:
        st.session_state["stock_active_ticker"] = ticker_input.strip().upper()

    if "stock_active_ticker" not in st.session_state:
        st.info("Introduce un ticker y pulsa Analizar para comenzar.")
        return

    ticker = st.session_state["stock_active_ticker"]
    with st.spinner(f"Cargando datos de {ticker}..."):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
        except Exception as e:
            st.error(f"Error al obtener datos: {e}")
            return

    price = safe_float(info.get("currentPrice")) or safe_float(info.get("regularMarketPrice"))
    if price is None:
        st.error("No se pudo obtener el precio de mercado. Verifica el ticker.")
        return

    company_name = info.get("longName") or ticker
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    currency = info.get("currency", "USD")

    st.markdown(
        f"""
        <div class="report-header">
            <h3 style="margin:0;">{company_name} ({ticker})</h3>
            <div style="color:{TEXT_SECONDARY};">{sector} · {industry} · {currency}</div>
            <div style="font-size:1.6rem; font-weight:700; color:{ACCENT_GOLD}; margin-top:0.4rem;">
                {price:.2f} {currency}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    methods, current_price = compute_stock_valuations(info)

    if not methods:
        st.warning("No se pudieron calcular valoraciones por falta de datos.")
        return

    df_val = pd.DataFrame(methods).sort_values("Upside %", ascending=False)
    st.dataframe(
        df_val[["Método", "Tipo", "Calidad", "Valor", "Upside %"]],
        use_container_width=True,
        hide_index=True,
    )

    upside_medio = df_val["Upside %"].dropna().mean()
    c1, c2, c3 = st.columns(3)
    c1.metric("Métodos calculados", len(df_val))
    c2.metric("Upside medio", f"{upside_medio:+.1f}%" if pd.notna(upside_medio) else "N/A")
    c3.metric("Precio actual", f"{price:.2f} {currency}")

    fig = go.Figure(go.Bar(
        x=df_val["Upside %"], y=df_val["Método"], orientation="h",
        marker_color=ACCENT_GOLD,
    ))
    fig.update_layout(
        height=400, template="plotly_white",
        xaxis_title="Upside vs precio actual (%)",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Generar informe PDF")

    if st.button("📄 Generar PDF", key="stock_pdf_btn"):
        html_informe = generar_html_informe_accion(company_name, ticker, sector, industry, currency, price, df_val)
        pdf_bytes = html_to_pdf_bytes(html_informe)
        if pdf_bytes:
            st.session_state["stock_pdf_bytes"] = pdf_bytes
            st.session_state["stock_pdf_name"] 
