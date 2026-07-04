import math
import io
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

# =========================
# CSS
# =========================
st.markdown(
    f"""
    <style>
    .stApp {{
        background: {BG_MAIN};
        color: {TEXT_PRIMARY};
        font-family: "Inter", "Segoe UI", sans-serif;
    }}

    .block-container {{
        padding-top: 2rem;
        max-width: 1200px;
    }}

    .report-header {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 16px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }}

    .stButton > button {{
        background: {ACCENT_GOLD} !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }}

    .stTabs [data-baseweb="tab"] {{
        background: {CARD_BG};
        border-radius: 10px 10px 0 0;
        color: {TEXT_SECONDARY};
        padding: 0.6rem 1rem;
    }}

    .stTabs [aria-selected="true"] {{
        color: {TEXT_PRIMARY} !important;
        font-weight: 700 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📄 Valuation Hub")
st.caption("Genera informes de valoración de acciones, activos físicos y compara opciones de financiación.")

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


def build_pdf_report(titulo, meta_lineas, tabla_headers, tabla_filas, veredicto_texto, disclaimer_texto):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm
    )
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "TitleGold", parent=styles["Heading1"],
        textColor=colors.HexColor("#B68A52"), spaceAfter=6
    )
    style_meta = ParagraphStyle(
        "Meta", parent=styles["Normal"],
        textColor=colors.HexColor("#7A6856"), spaceAfter=12
    )
    style_disclaimer = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"],
        fontSize=7, textColor=colors.HexColor("#A08F7C"), spaceBefore=20
    )
    style_veredicto = ParagraphStyle(
        "Veredicto", parent=styles["Normal"],
        backColor=colors.HexColor("#F9F4EC"),
        borderPadding=8, spaceAfter=10
    )

    elementos = [Paragraph(titulo, style_title)]
    for linea in meta_lineas:
        elementos.append(Paragraph(linea, style_meta))

    tabla_data = [tabla_headers] + tabla_filas
    tabla = Table(tabla_data, hAlign="LEFT")
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFE2D2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2F241B")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9C8B4")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFDF9"), colors.HexColor("#FAF5EE")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 16))
    elementos.append(Paragraph(veredicto_texto, style_veredicto))
    elementos.append(Paragraph(disclaimer_texto, style_disclaimer))

    doc.build(elementos)
    buf.seek(0)
    return buf.read()


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
        veredicto = (
            "Infravalorada" if upside_medio and upside_medio > 15 else
            "Sobrevalorada" if upside_medio and upside_medio < -15 else
            "En línea con su valor razonable"
        )
        tabla_filas = [
            [r["Método"], r["Tipo"], r["Calidad"], f"{r['Valor']:.2f}", f"{r['Upside %']:+.1f}%"]
            for _, r in df_val.iterrows()
        ]
        pdf_bytes = build_pdf_report(
            titulo=f"Informe de Valoración — {company_name} ({ticker})",
            meta_lineas=[
                f"{sector} · {industry} · {currency}",
                f"Precio actual: {price:.2f} {currency}"
            ],
            tabla_headers=["Método", "Tipo", "Calidad", "Valor estimado", "Upside"],
            tabla_filas=tabla_filas,
            veredicto_texto=f"Upside medio: {upside_medio:+.1f}% | Veredicto: {veredicto}",
            disclaimer_texto="Informe generado automáticamente con fines informativos. No constituye asesoramiento financiero."
        )
        st.session_state["stock_pdf_bytes"] = pdf_bytes
        st.session_state["stock_pdf_name"] = f"informe_accion_{ticker}.pdf"
        st.success("Informe generado correctamente.")

    if "stock_pdf_bytes" in st.session_state:
        st.download_button(
            "⬇️ Descargar informe PDF",
            data=st.session_state["stock_pdf_bytes"],
            file_name=st.session_state["stock_pdf_name"],
            mime="application/pdf",
            key="stock_pdf_download",
        )


# =========================
# MÓDULO 2 — MAQUINARIA
# =========================

def compute_machinery_valuation(precio_nuevo, antiguedad, vida_util, horas_uso, horas_max,
                                 estado_pct, obsolescencia_pct, precio_mercado_similar):
    dep_tiempo = min(antiguedad / vida_util, 1.0) if vida_util > 0 else 1.0
    dep_uso = min(horas_uso / horas_max, 1.0) if horas_max > 0 else 0.0
    dep_estado = (100 - estado_pct) / 100
    dep_obsolescencia = obsolescencia_pct / 100

    dep_total = min(
        0.35 * dep_tiempo + 0.25 * dep_uso + 0.25 * dep_estado + 0.15 * dep_obsolescencia,
        0.95
    )

    grado_operatividad = 1 - dep_obsolescencia * 0.3
    valor_coste_reposicion = precio_nuevo * (1 - dep_total) * grado_operatividad

    resultados = [
        {
            "Método": "Coste de reposición − Depreciación",
            "Descripción": f"Precio nuevo × (1 − depreciación {dep_total*100:.1f}%) × operatividad {grado_operatividad*100:.1f}%",
            "Valor": valor_coste_reposicion,
        }
    ]

    if precio_mercado_similar and precio_mercado_similar > 0:
        resultados.append({
            "Método": "Método de mercado (comparables)",
            "Descripción": "Precio de mercado de equipos similares de segunda mano",
            "Valor": precio_mercado_similar,
        })

    valores = [r["Valor"] for r in resultados]
    valor_medio = sum(valores) / len(valores)

    resultados.append({
        "Método": "Valor medio recomendado",
        "Descripción": "Promedio de los métodos aplicados",
        "Valor": valor_medio,
    })

    return resultados, dep_total, grado_operatividad


def modulo_maquinaria():
    st.subheader("🏗️ Valoración de maquinaria y equipos")
    st.caption("Introduce los datos del activo para estimar su valor por coste de reposición y comparables de mercado.")

    with st.form("form_maquinaria"):
        col1, col2 = st.columns(2)
        with col1:
            nombre_activo = st.text_input("Nombre del activo", "Torno CNC")
            marca_modelo = st.text_input("Marca / Modelo", "")
            precio_nuevo = st.number_input("Precio de compra nuevo (€)", min_value=0.0, value=50000.0, step=500.0)
            antiguedad = st.number_input("Antigüedad (años)", min_value=0.0, value=5.0, step=0.5)
            vida_util = st.number_input("Vida útil estimada (años)", min_value=1.0, value=15.0, step=1.0)
        with col2:
            horas_uso = st.number_input("Horas de uso acumuladas", min_value=0.0, value=8000.0, step=100.0)
            horas_max = st.number_input("Horas de vida útil estimadas", min_value=1.0, value=40000.0, step=1000.0)
            estado_pct = st.slider("Estado de conservación (0=muy malo, 100=como nuevo)", 0, 100, 70)
            obsolescencia_pct = st.slider("Obsolescencia tecnológica (0=actual, 100=obsoleta)", 0, 100, 20)
            precio_mercado_similar = st.number_input("Precio de mercado de equipos similares (€, opcional)", min_value=0.0, value=0.0, step=500.0)

        submitted = st.form_submit_button("Calcular valoración", type="primary")

    if submitted:
        resultados, dep_total, grado_op = compute_machinery_valuation(
            precio_nuevo, antiguedad, vida_util, horas_uso, horas_max,
            estado_pct, obsolescencia_pct, precio_mercado_similar or None
        )
        st.session_state["maq_resultados"] = resultados
        st.session_state["maq_dep_total"] = dep_total
        st.session_state["maq_grado_op"] = grado_op
        st.session_state["maq_nombre"] = nombre_activo
        st.session_state["maq_marca"] = marca_modelo
        st.session_state["maq_precio_nuevo"] = precio_nuevo
        st.session_state["maq_antiguedad"] = antiguedad
        st.session_state["maq_estado"] = estado_pct
        st.session_state["maq_obsolescencia"] = obsolescencia_pct

    if "maq_resultados" in st.session_state:
        resultados = st.session_state["maq_resultados"]
        dep_total = st.session_state["maq_dep_total"]
        grado_op = st.session_state["maq_grado_op"]

        st.markdown("---")
        df_res = pd.DataFrame(resultados)
        st.dataframe(df_res, use_container_width=True, hide_index=True)

        valor_final = resultados[-1]["Valor"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Depreciación total", f"{dep_total*100:.1f}%")
        c2.metric("Grado de operatividad", f"{grado_op*100:.1f}%")
        c3.metric("Valor recomendado", f"{valor_final:,.2f} €")

        fig = go.Figure(go.Bar(
            x=[r["Valor"] for r in resultados],
            y=[r["Método"] for r in resultados],
            orientation="h",
            marker_color=ACCENT_GOLD,
        ))
        fig.update_layout(
            height=300, template="plotly_white",
            xaxis_title="Valor estimado (€)",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Generar informe PDF")

        if st.button("📄 Generar PDF", key="maq_pdf_btn"):
            tabla_filas = [[r["Método"], r["Descripción"], f"{r['Valor']:,.2f} €"] for r in resultados]
            pdf_bytes = build_pdf_report(
                titulo=f"Informe de Valoración — {st.session_state['maq_nombre']}",
                meta_lineas=[
                    f"{st.session_state['maq_marca']} · Precio nuevo: {st.session_state['maq_precio_nuevo']:,.2f} €",
                    f"Antigüedad: {st.session_state['maq_antiguedad']} años · Estado: {st.session_state['maq_estado']}/100 · Obsolescencia: {st.session_state['maq_obsolescencia']}/100"
                ],
                tabla_headers=["Método", "Descripción", "Valor estimado"],
                tabla_filas=tabla_filas,
                veredicto_texto=f"Depreciación total: {dep_total*100:.1f}% | Operatividad: {grado_op*100:.1f}% | Valor recomendado: {valor_final:,.2f} €",
                disclaimer_texto="Informe generado automáticamente con fines informativos. No sustituye una tasación pericial oficial."
            )
            st.session_state["maq_pdf_bytes"] = pdf_bytes
            st.session_state["maq_pdf_name"] = f"informe_maquinaria_{st.session_state['maq_nombre'].replace(' ', '_')}.pdf"
            st.success("Informe generado correctamente.")

        if "maq_pdf_bytes" in st.session_state:
            st.download_button(
                "⬇️ Descargar informe PDF",
                data=st.session_state["maq_pdf_bytes"],
                file_name=st.session_state["maq_pdf_name"],
                mime="application/pdf",
                key="maq_pdf_download",
            )


# =========================
# MÓDULO 3 — FINANCIACIÓN
# =========================

def calcular_cuota_frances(capital, tasa_anual, anios, pagos_por_anio=12):
    i = tasa_anual / pagos_por_anio
    n = anios * pagos_por_anio
    if i == 0:
        return capital / n
    cuota = capital * i * (1 + i) ** n / ((1 + i) ** n - 1)
    return cuota


def tabla_amortizacion_frances(capital, tasa_anual, anios, pagos_por_anio=12):
    i = tasa_anual / pagos_por_anio
    n = int(anios * pagos_por_anio)
    cuota = calcular_cuota_frances(capital, tasa_anual, anios, pagos_por_anio)

    filas = []
    capital_pendiente = capital
    total_intereses = 0.0
    for periodo in range(1, n + 1):
        interes = capital_pendiente * i
        amortizacion = cuota - interes
        capital_pendiente -= amortizacion
        total_intereses += interes
        filas.append({
            "Periodo": periodo,
            "Cuota": cuota,
            "Interés": interes,
            "Amortización": amortizacion,
            "Capital pendiente": max(capital_pendiente, 0),
        })
    return filas, cuota, total_intereses


def calcular_leasing(valor_activo, tasa_anual, anios, valor_residual_pct, pagos_por_anio=12):
    valor_residual = valor_activo * (valor_residual_pct / 100)
    capital_a_financiar = valor_activo - valor_residual
    cuota = calcular_cuota_frances(capital_a_financiar, tasa_anual, anios, pagos_por_anio)
    n = anios * pagos_por_anio
    coste_total = cuota * n + valor_residual
    return cuota, valor_residual, coste_total


def calcular_renting(valor_activo, cuota_mensual_estimada_pct, anios):
    n = anios * 12
    cuota = valor_activo * (cuota_mensual_estimada_pct / 100)
    coste_total = cuota * n
    return cuota, coste_total


def modulo_financiacion():
    st.subheader("💰 Comparador de financiación")
    st.caption("Compara préstamo, leasing y renting para la compra de un activo (maquinaria, vehículo, inmueble).")

    with st.form("form_financiacion"):
        col1, col2 = st.columns(2)
        with col1:
            valor_activo = st.number_input("Valor del activo (€)", min_value=0.0, value=50000.0, step=500.0)
            anios = st.number_input("Plazo (años)", min_value=1, value=5, step=1)
            tasa_prestamo = st.number_input("Tipo de interés préstamo (% anual)", min_value=0.0, value=6.0, step=0.1) / 100
        with col2:
            tasa_leasing = st.number_input("Tipo de interés leasing (% anual)", min_value=0.0, value=5.5, step=0.1) / 100
            valor_residual_pct = st.number_input("Valor residual leasing (% del activo)", min_value=0.0, max_value=100.0, value=10.0, step=1.0)
            cuota_renting_pct = st.number_input("Cuota mensual renting estimada (% del valor del activo)", min_value=0.0, value=2.5, step=0.1)

        submitted = st.form_submit_button("Comparar opciones", type="primary")

    if submitted:
        filas_amort, cuota_prestamo, intereses_prestamo = tabla_amortizacion_frances(valor_activo, tasa_prestamo, anios)
        coste_total_prestamo = cuota_prestamo * anios * 12

        cuota_leasing, valor_residual, coste_total_leasing = calcular_leasing(
            valor_activo, tasa_leasing, anios, valor_residual_pct
        )

        cuota_renting, coste_total_renting = calcular_renting(valor_activo, cuota_renting_pct, anios)

        st.session_state["fin_resultados"] = {
            "valor_activo": valor_activo,
            "anios": anios,
            "prestamo": {"cuota": cuota_prestamo, "coste_total": coste_total_prestamo, "intereses": intereses_prestamo},
            "leasing": {"cuota": cuota_leasing, "coste_total": coste_total_leasing, "valor_residual": valor_residual},
            "renting": {"cuota": cuota_renting, "coste_total": coste_total_renting},
        }

    if "fin_resultados" in st.session_state:
        r = st.session_state["fin_resultados"]

        st.markdown("---")
        df_comp = pd.DataFrame([
            {"Opción": "Préstamo", "Cuota mensual (€)": r["prestamo"]["cuota"], "Coste total (€)": r["prestamo"]["coste_total"], "Propiedad": "Sí (desde el inicio)"},
            {"Opción": "Leasing", "Cuota mensual (€)": r["leasing"]["cuota"], "Coste total (€)": r["leasing"]["coste_total"], "Propiedad": "Sí (al finalizar)"},
            {"Opción": "Renting", "Cuota mensual (€)": r["renting"]["cuota"], "Coste total (€)": r["renting"]["coste_total"], "Propiedad": "No"},
        ])
        st.dataframe(
            df_comp.style.format({"Cuota mensual (€)": "{:,.2f}", "Coste total (€)": "{:,.2f}"}),
            use_container_width=True, hide_index=True
        )

        opcion_mas_barata = df_comp.loc[df_comp["Coste total (€)"].idxmin(), "Opción"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Cuota préstamo", f"{r['prestamo']['cuota']:,.2f} €/mes")
        c2.metric("Cuota leasing", f"{r['leasing']['cuota']:,.2f} €/mes")
        c3.metric("Cuota renting", f"{r['renting']['cuota']:,.2f} €/mes")

        st.info(f"💡 La opción con menor coste total en {r['anios']} años es: **{opcion_mas_barata}**")

        fig = go.Figure(go.Bar(
            x=df_comp["Opción"], y=df_comp["Coste total (€)"],
            marker_color=[ACCENT_GOLD, "#5E8B6F", "#B85C5C"],
        ))
        fig.update_layout(
            height=350, template="plotly_white",
            yaxis_title="Coste total (€)",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Generar informe PDF")

        if st.button("📄 Generar PDF", key="fin_pdf_btn"):
            tabla_filas = [
                ["Préstamo", f"{r['prestamo']['cuota']:,.2f} €", f"{r['prestamo']['coste_total']:,.2f} €", "Sí (desde el inicio)"],
                ["Leasing", f"{r['leasing']['cuota']:,.2f} €", f"{r['leasing']['coste_total']:,.2f} €", "Sí (al finalizar)"],
                ["Renting", f"{r['renting']['cuota']:,.2f} €", f"{r['renting']['coste_total']:,.2f} €", "No"],
            ]
            pdf_bytes = build_pdf_report(
                titulo="Informe Comparativo de Financiación",
                meta_lineas=[
                    f"Valor del activo: {r['valor_activo']:,.2f} € · Plazo: {r['anios']} años"
                ],
                tabla_headers=["Opción", "Cuota mensual", "Coste total", "Propiedad"],
                tabla_filas=tabla_filas,
                veredicto_texto=f"Opción recomendada por menor coste total: {opcion_mas_barata}",
                disclaimer_texto="Informe generado automáticamente con fines informativos. No constituye asesoramiento financiero."
            )
            st.session_state["fin_pdf_bytes"] = pdf_bytes
            st.session_state["fin_pdf_name"] = "informe_financiacion.pdf"
            st.success("Informe generado correctamente.")

        if "fin_pdf_bytes" in st.session_state:
            st.download_button(
                "⬇️ Descargar informe PDF",
                data=st.session_state["fin_pdf_bytes"],
                file_name=st.session_state["fin_pdf_name"],
                mime="application/pdf",
                key="fin_pdf_download",
            )


# =========================
# NAVEGACIÓN PRINCIPAL
# =========================

tab1, tab2, tab3 = st.tabs(["📈 Acciones", "🏗️ Maquinaria", "💰 Financiación"])

with tab1:
    modulo_acciones()

with tab2:
    modulo_maquinaria()

with tab3:
    modulo_financiacion()
