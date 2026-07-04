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


PDF_BASE_CSS =
