# dashboard.py
"""
FIRE Engine — Streamlit Dashboard
Запуск: streamlit run dashboard.py
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import json
import io

# ─────────────────────────────────────────────
# КОНФИГ
# ─────────────────────────────────────────────

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="FIRE Engine Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

COLORS = {
    "primary":   "#FF4B2B",
    "secondary": "#FF416C",
    "accent":    "#F7971E",
    "dark":      "#0F0F0F",
    "surface":   "#1A1A2E",
    "card":      "#16213E",
    "text":      "#E0E0E0",
    "muted":     "#888",
    "pos":       "#00C9A7",
    "neu":       "#F7971E",
    "neg":       "#FF4B2B",
}
SENTIMENT_COLORS = {"POS": COLORS["pos"], "NEU": COLORS["neu"], "NEG": COLORS["neg"]}

# ─────────────────────────────────────────────
# СТИЛИ
# ─────────────────────────────────────────────

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

/* ── УБИРАЕМ ВСЁ ЛИШНЕЕ STREAMLIT ── */
header[data-testid="stHeader"] {{ display: none !important; }}
[data-testid="stSidebar"] {{ display: none !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
.main .block-container {{
    padding-top: 0 !important;
    max-width: 100% !important;
}}

/* ── BASE ── */
html, body {{ background-color: {COLORS['dark']} !important; }}
.stApp {{
    background: linear-gradient(135deg, {COLORS['dark']} 0%, {COLORS['surface']} 100%) !important;
}}
html, body, p, span, div, label, li, a, [class*="css"], .stMarkdown {{
    color: {COLORS['text']} !important;
    font-family: 'Syne', sans-serif !important;
}}

/* ── ТОПБАР ── */
.fire-topbar {{
    display: flex;
    align-items: center;
    background: rgba(22,33,62,0.95);
    border-bottom: 1px solid rgba(255,75,43,0.2);
    padding: 0 2rem;
    height: 58px;
    position: sticky;
    top: 0;
    z-index: 9999;
    backdrop-filter: blur(10px);
    gap: 0;
    margin-bottom: 2rem;
}}
.fire-topbar-logo {{
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 1.4rem;
    letter-spacing: -0.5px;
    background: linear-gradient(90deg, #FF4B2B, #FF416C, #F7971E);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-right: 2.5rem;
    white-space: nowrap;
    flex-shrink: 0;
}}
.fire-topbar-status {{
    font-family: 'Space Mono', monospace;
    font-size: 0.68rem;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-right: 2rem;
    flex-shrink: 0;
}}
.fire-topbar-nav {{
    display: flex;
    align-items: center;
    gap: 2px;
    flex: 1;
}}
.fire-nav-item {{
    font-family: 'Syne', sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: #555 !important;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.15s ease;
    white-space: nowrap;
    text-decoration: none;
    background: transparent;
}}
.fire-nav-item:hover {{
    color: #CCC !important;
    background: rgba(255,75,43,0.08) !important;
}}
.fire-nav-item.active {{
    color: #FFFFFF !important;
    background: rgba(255,75,43,0.15) !important;
    border-color: rgba(255,75,43,0.4) !important;
}}
.fire-topbar-filters {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    flex-shrink: 0;
}}

/* ── Скрываем лейблы selectbox в топбаре ── */
.topbar-filter .stSelectbox label {{ display: none !important; }}
.topbar-filter .stSelectbox > div > div {{
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,75,43,0.2) !important;
    border-radius: 6px !important;
    min-height: 32px !important;
    height: 32px !important;
}}
.topbar-filter .stSelectbox [data-baseweb="select"] > div {{
    min-height: 30px !important;
    height: 30px !important;
    padding: 0 8px !important;
}}
.topbar-filter .stSelectbox [data-baseweb="select"] span {{
    color: #888 !important;
    font-size: 0.75rem !important;
    font-family: 'Space Mono', monospace !important;
}}

/* ── СТИЛИ НАВИГАЦИИ (кнопки Streamlit в топбаре) ── */
.topbar-nav-btn .stButton > button {{
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 6px !important;
    color: #555 !important;
    font-family: 'Syne', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
    padding: 5px 14px !important;
    height: 34px !important;
    transition: all 0.15s !important;
    white-space: nowrap !important;
    box-shadow: none !important;
}}
.topbar-nav-btn .stButton > button:hover {{
    background: rgba(255,75,43,0.08) !important;
    color: #CCC !important;
    border-color: rgba(255,75,43,0.2) !important;
    transform: none !important;
}}
.topbar-nav-btn .stButton > button p {{
    color: inherit !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
}}
.topbar-nav-btn-active .stButton > button {{
    background: rgba(255,75,43,0.15) !important;
    border-color: rgba(255,75,43,0.4) !important;
    color: #FFFFFF !important;
}}
.topbar-nav-btn-active .stButton > button p {{
    color: #FFFFFF !important;
}}

/* ── KPI КАРТОЧКИ ── */
.kpi-card {{
    background: {COLORS['card']};
    border: 1px solid rgba(255,75,43,0.18);
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    text-align: center;
    transition: border-color 0.2s, transform 0.2s;
}}
.kpi-card:hover {{ border-color: rgba(255,75,43,0.5); transform: translateY(-2px); }}
.kpi-value {{
    font-family: 'Space Mono', monospace !important;
    font-size: 2rem; font-weight: 700;
    color: {COLORS['accent']} !important; line-height: 1;
}}
.kpi-label {{
    font-size: 0.68rem; color: #555 !important;
    text-transform: uppercase; letter-spacing: 1.5px;
    margin-top: 0.4rem; font-family: 'Space Mono', monospace !important;
}}

/* ── SECTION TITLE ── */
.section-title {{
    font-family: 'Space Mono', monospace !important;
    font-weight: 700; font-size: 0.72rem;
    color: #FFFFFF !important; text-transform: uppercase;
    letter-spacing: 3px; margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(255,75,43,0.3);
}}

/* ── ЧАТ ── */
.chat-user {{
    background: rgba(255,75,43,0.08); border-left: 2px solid {COLORS['primary']};
    border-radius: 0 8px 8px 0; padding: 0.75rem 1rem; margin: 0.5rem 0;
}}
.chat-bot {{
    background: rgba(247,151,30,0.07); border-left: 2px solid {COLORS['accent']};
    border-radius: 0 8px 8px 0; padding: 0.75rem 1rem; margin: 0.5rem 0;
}}
.chat-label {{
    font-family: 'Space Mono', monospace !important; font-size: 0.65rem !important;
    text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.4rem;
    display: flex; align-items: center; gap: 6px;
}}
.chat-source {{ font-size: 0.6rem; color: #444 !important; font-family: 'Space Mono', monospace !important; margin-top: 0.4rem; }}

/* ── ОСНОВНЫЕ КНОПКИ ── */
.stButton > button {{
    background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['secondary']}) !important;
    color: #FFFFFF !important; border: none !important; border-radius: 8px !important;
    font-family: 'Syne', sans-serif !important; font-weight: 700 !important;
    font-size: 0.88rem !important; transition: opacity 0.15s, transform 0.15s !important;
}}
.stButton > button:hover {{ opacity: 0.85 !important; transform: translateY(-1px) !important; }}
.stButton > button p {{ color: #FFFFFF !important; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; }}

/* ── ФОРМА ЧАТА ── */
[data-testid="stForm"] {{ background: transparent !important; border: none !important; padding: 0 !important; }}
[data-testid="stForm"] .stTextInput > div > div > input {{
    background: #0d0d1a !important; border: 1px solid rgba(255,75,43,0.35) !important;
    color: #FFFFFF !important; font-size: 0.92rem !important;
}}
[data-testid="stForm"] .stTextInput > div > div > input::placeholder {{ color: #444 !important; }}
[data-testid="stForm"] .stTextInput > div > div > input:focus {{
    border-color: #FF4B2B !important; box-shadow: 0 0 0 2px rgba(255,75,43,0.12) !important;
}}
[data-testid="stForm"] .stButton > button {{
    background: rgba(255,255,255,0.04) !important; border: 1px solid rgba(255,75,43,0.2) !important;
    color: #666 !important;
}}
[data-testid="stForm"] .stButton > button p {{ color: inherit !important; }}
[data-testid="stFormSubmitButton"] button {{
    background: linear-gradient(90deg, rgba(255,75,43,0.85), rgba(255,65,108,0.85)) !important;
    border: none !important; color: #FFFFFF !important;
}}
[data-testid="stFormSubmitButton"] button p {{ color: #FFFFFF !important; }}

/* ── SELECTBOX ── */
.stSelectbox [data-baseweb="select"] > div {{
    background: rgba(255,255,255,0.05) !important;
    border-color: rgba(255,75,43,0.25) !important;
}}
.stSelectbox [data-baseweb="select"] span {{
    color: #FFFFFF !important; font-family: 'Syne', sans-serif !important; font-weight: 600 !important;
}}
[data-baseweb="popover"], [data-baseweb="menu"] {{
    background: #1a1a2e !important; border: 1px solid rgba(255,75,43,0.25) !important; border-radius: 8px !important;
}}
[data-baseweb="menu"] li, [role="option"] {{
    background: #1a1a2e !important; color: #FFFFFF !important; font-family: 'Syne', sans-serif !important;
}}
[data-baseweb="menu"] li:hover, [role="option"]:hover {{ background: rgba(255,75,43,0.2) !important; }}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {{
    background: rgba(255,255,255,0.03) !important;
    border: 2px dashed rgba(255,75,43,0.3) !important; border-radius: 12px !important;
}}
[data-testid="stFileUploader"] label, [data-testid="stFileUploader"] p,
[data-testid="stFileUploader"] span {{ color: #888 !important; font-family: 'Space Mono', monospace !important; font-size: 0.82rem !important; }}

/* ── UPLOAD STEPS ── */
.upload-step {{ display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; margin: 4px 0; font-family: 'Space Mono', monospace; font-size: 0.78rem; }}
.step-ok  {{ background: rgba(0,201,167,0.1); border-left: 2px solid #00C9A7; color: #00C9A7 !important; }}
.step-err {{ background: rgba(255,75,43,0.1);  border-left: 2px solid #FF4B2B; color: #FF6B50 !important; }}
.step-run {{ background: rgba(247,151,30,0.1); border-left: 2px solid #F7971E; color: #F7971E !important; }}
.step-wait{{ background: rgba(255,255,255,0.03); border-left: 2px solid #333; color: #555 !important; }}

/* ── DETAILS/SUMMARY ── */
details > summary {{ list-style: none !important; }}
details > summary::-webkit-details-marker {{ display: none !important; }}

/* ── ПРОЧЕЕ ── */
hr {{ border-color: rgba(255,75,43,0.15) !important; }}
[data-testid="stMetricValue"] {{ color: {COLORS['accent']} !important; font-family: 'Space Mono', monospace !important; }}
[data-testid="stMetricLabel"] {{ color: #666 !important; }}
.stTextInput > div > div > input {{
    background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,75,43,0.3) !important;
    color: #FFFFFF !important; border-radius: 8px !important;
}}
.stNumberInput input {{ color: #FFFFFF !important; background: rgba(255,255,255,0.05) !important; }}
.stAlert {{ background: rgba(255,75,43,0.08) !important; border: 1px solid rgba(255,75,43,0.25) !important; }}
.stAlert p {{ color: #FFFFFF !important; }}
.dataframe th {{ background: {COLORS['card']} !important; color: {COLORS['accent']} !important; font-family: 'Space Mono', monospace !important; }}
.dataframe td {{ color: {COLORS['text']} !important; }}
.stSpinner > div {{ border-top-color: {COLORS['primary']} !important; }}

/* ── SKELETON ── */
.page-skeleton {{
    background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,75,43,0.05) 50%, rgba(255,255,255,0.03) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.2s infinite;
    border-radius: 8px; margin-bottom: 10px;
}}
@keyframes shimmer {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}
@keyframes pageFadeIn {{ from {{ opacity: 0; transform: translateY(5px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.main .block-container {{ animation: pageFadeIn 0.15s ease-out both; }}

/* ── FIRE HEADER ── */
.fire-header {{
    background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['secondary']}, {COLORS['accent']});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    font-family: 'Syne', sans-serif !important; font-weight: 800;
    font-size: 2.6rem; letter-spacing: -1px; line-height: 1.1; margin-bottom: 0.2rem;
}}
.page-sub {{
    color: #555 !important; font-size: 0.82rem;
    font-family: 'Space Mono', monospace !important; letter-spacing: 1px;
    text-transform: uppercase; margin-bottom: 1.5rem;
}}

/* ── CHART БЛОК В ЧАТЕ ── */
.chart-reveal {{
    background: rgba(13,13,26,0.8);
    border: 1px solid rgba(255,75,43,0.2);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-top: 1rem;
    animation: pageFadeIn 0.2s ease-out both;
}}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# API КЛИЕНТ
# ─────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def fetch(endpoint: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        st.error(f"API Error {endpoint}: {e}")
        return None

def post_api(endpoint: str, data: dict):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"answer": f"Ошибка: {e}", "source": "error"}


# ─────────────────────────────────────────────
# КОМПОНЕНТЫ
# ─────────────────────────────────────────────

def kpi_card(col, value, label):
    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)

def section_title(text: str):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)

def plotly_dark(fig, height=350):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(22,33,62,0.5)",
        font=dict(family="Syne, sans-serif", color=COLORS["text"]),
        height=height, margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)")
    return fig


# ─────────────────────────────────────────────
# ОПРЕДЕЛЕНИЕ ТИПА ГРАФИКА ПО ВОПРОСУ
# ─────────────────────────────────────────────

def detect_chart_type(question: str):
    """Определяет нужный график по ключевым словам вопроса."""
    q = question.lower()
    if any(w in q for w in ["тип", "категори", "вид обращени", "типам", "типов"]):
        return ("type", "Распределение по типам обращений")
    if any(w in q for w in ["офис", "город", "городам", "офисам", "регион"]):
        return ("office", "Распределение по офисам")
    if any(w in q for w in ["тональност", "сентимент", "sentiment", "негатив", "позитив", "настроени"]):
        return ("sentiment", "Распределение тональности")
    if any(w in q for w in ["менеджер", "нагрузк", "перегружен", "загружен", "сотрудник"]):
        return ("manager", "Нагрузка менеджеров")
    if any(w in q for w in ["язык", "lang", "языкам", "kz", "eng", "рус"]):
        return ("lang", "Распределение по языкам обращений")
    if any(w in q for w in ["приоритет", "priority", "срочност", "приоритетам"]):
        return ("priority", "Распределение по приоритетам")
    if any(w in q for w in ["эскалаци", "escalat"]):
        return ("office", "Эскалации по офисам")
    return None


# ─────────────────────────────────────────────
# РЕНДЕР ГРАФИКА ДЛЯ AI-ЧАТА
# ─────────────────────────────────────────────

def render_chat_chart(chart_type: str, chart_title: str):
    st.markdown('<div class="chart-reveal">', unsafe_allow_html=True)
    section_title(f"📊 {chart_title}")

    if chart_type == "type":
        data = fetch("/stats/by_type") or []
        if data:
            df_c = pd.DataFrame(data)
            fig = px.bar(df_c, x="count", y="ai_type", orientation="h",
                         color="avg_priority",
                         color_continuous_scale=["#1a1a2e", "#FF416C", "#FF4B2B"],
                         labels={"count": "Тикетов", "ai_type": "", "avg_priority": "Приоритет"},
                         text="count")
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            st.plotly_chart(plotly_dark(fig, 320), use_container_width=True)

    elif chart_type == "office":
        data = fetch("/stats/by_office") or []
        if data:
            df_c = pd.DataFrame(data)
            fig = px.bar(df_c, x="office", y="tickets",
                         color="escalations",
                         color_continuous_scale=[[0, "#16213E"], [1, "#FF4B2B"]],
                         labels={"tickets": "Тикетов", "office": "", "escalations": "Эскалации"},
                         text="tickets")
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            fig.update_xaxes(tickangle=-30)
            st.plotly_chart(plotly_dark(fig, 320), use_container_width=True)

    elif chart_type == "sentiment":
        data = fetch("/stats/by_sentiment") or []
        if data:
            df_c = pd.DataFrame(data)
            fig = px.pie(df_c, values="count", names="sentiment",
                         color="sentiment", color_discrete_map=SENTIMENT_COLORS, hole=0.55)
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            st.plotly_chart(plotly_dark(fig, 320), use_container_width=True)

    elif chart_type == "manager":
        data = fetch("/managers/load") or []
        if data:
            df_c = pd.DataFrame(data).head(10)
            fig = px.bar(df_c, x="tickets", y="manager", orientation="h",
                         color="office",
                         color_discrete_sequence=px.colors.qualitative.Bold,
                         labels={"tickets": "Тикетов", "manager": ""},
                         text="tickets")
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            st.plotly_chart(plotly_dark(fig, 400), use_container_width=True)

    elif chart_type == "lang":
        data = fetch("/stats/by_lang") or []
        if data:
            df_c = pd.DataFrame(data)
            fig = px.pie(df_c, values="count", names="ai_lang",
                         color_discrete_sequence=[COLORS["primary"], COLORS["accent"], COLORS["pos"]],
                         hole=0.4)
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            st.plotly_chart(plotly_dark(fig, 300), use_container_width=True)

    elif chart_type == "priority":
        data = fetch("/stats/by_priority") or []
        if data:
            df_c = pd.DataFrame(data)
            fig = px.bar(df_c, x="priority", y="count",
                         color="count",
                         color_continuous_scale=["#16213E", "#F7971E", "#FF4B2B"],
                         labels={"priority": "Приоритет", "count": "Тикетов"})
            st.plotly_chart(plotly_dark(fig, 300), use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# НАВИГАЦИЯ — ТОПБАР
# ─────────────────────────────────────────────

if "page" not in st.session_state:
    st.session_state.page = "Обзор"

NAV = [
    ("Обзор",       "Обзор"),
    ("Тикеты",      "Тикеты"),
    ("Менеджеры",   "Менеджеры"),
    ("Карта",       "Карта"),
    ("Загрузка",    "Загрузка CSV"),
    ("AI Аналитик", "AI Аналитик"),
]

health = fetch("/health")
db_c   = COLORS["pos"] if health and health.get("db")  else COLORS["neg"]
llm_c  = COLORS["pos"] if health and health.get("llm") else COLORS["neu"]
db_dot = f'<span style="color:{db_c};">●</span> <span style="color:#555;font-size:0.7rem;">DB</span>'
llm_dot= f'<span style="color:{llm_c};">●</span> <span style="color:#555;font-size:0.7rem;">LLM</span>'

logo_col, nav_col = st.columns([1, 4])

with logo_col:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;height:52px;padding-left:4px;">
        <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:1.5rem;
                    background:linear-gradient(90deg,#FF4B2B,#FF416C,#F7971E);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                    background-clip:text;white-space:nowrap;">🔥 FIRE</div>
        <div style="font-family:'Space Mono',monospace;font-size:0.68rem;
                    display:flex;gap:10px;align-items:center;">
            {db_dot} {llm_dot}
        </div>
    </div>
    """, unsafe_allow_html=True)

with nav_col:
    nav_cols = st.columns(len(NAV))
    for i, (key, label) in enumerate(NAV):
        is_active = st.session_state.page == key
        css_class = "topbar-nav-btn-active" if is_active else "topbar-nav-btn"
        with nav_cols[i]:
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                if st.session_state.page != key:
                    st.session_state.page = key
                    st.session_state.page_loading = True
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<hr style="margin:0 0 0.8rem 0;border-color:rgba(255,75,43,0.15);">', unsafe_allow_html=True)

filters_meta = fetch("/meta/filters") or {}
offices    = ["Все"] + filters_meta.get("offices",   [])
ai_types   = ["Все"] + filters_meta.get("ai_types",  [])
sentiments = ["Все"] + filters_meta.get("sentiments",[])
languages  = ["Все"] + filters_meta.get("languages", [])

fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    st.markdown('<div class="topbar-filter">', unsafe_allow_html=True)
    f_office = st.selectbox("Офис", offices, index=0, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
with fc2:
    st.markdown('<div class="topbar-filter">', unsafe_allow_html=True)
    f_type = st.selectbox("Тип", ai_types, index=0, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
with fc3:
    st.markdown('<div class="topbar-filter">', unsafe_allow_html=True)
    f_sentiment = st.selectbox("Сентимент", sentiments, index=0, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
with fc4:
    st.markdown('<div class="topbar-filter">', unsafe_allow_html=True)
    f_lang = st.selectbox("Язык", languages, index=0, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

filter_params = {}
if f_office    != "Все": filter_params["office"]    = f_office
if f_type      != "Все": filter_params["ai_type"]   = f_type
if f_sentiment != "Все": filter_params["sentiment"] = f_sentiment
if f_lang      != "Все": filter_params["ai_lang"]   = f_lang

st.markdown("---")

page = st.session_state.page

if st.session_state.get("page_loading"):
    st.session_state.page_loading = False
    st.markdown(f"""
    <div style="padding: 1rem 0;">
        <div class="page-skeleton" style="height:48px;width:35%;margin-bottom:6px;"></div>
        <div class="page-skeleton" style="height:14px;width:18%;margin-bottom:2rem;opacity:0.5;"></div>
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:2rem;">
            {''.join(['<div class="page-skeleton" style="height:90px;"></div>']*5)}
        </div>
        <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;">
            <div class="page-skeleton" style="height:300px;"></div>
            <div class="page-skeleton" style="height:300px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.rerun()

# ─────────────────────────────────────────────
# СТРАНИЦА: ОБЗОР
# ─────────────────────────────────────────────

if page == "Обзор":
    st.markdown('<div class="fire-header">Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Аналитика обращений в реальном времени</div>', unsafe_allow_html=True)

    summary = fetch("/stats/summary")
    if not summary:
        st.warning("Нет данных. Убедитесь что API запущен и БД заполнена.")
        st.code("uvicorn api:app --reload --port 8000", language="bash")
        st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    kpi_card(c1, summary["total_tickets"],             "Всего тикетов")
    kpi_card(c2, f"{summary['escalation_rate_pct']}%", "Эскалаций")
    kpi_card(c3, summary["avg_priority"],              "Ср. приоритет")
    kpi_card(c4, f"{summary['negative_sentiment_pct']}%", "Негатив")
    kpi_card(c5, summary["unique_managers"],           "Менеджеров")

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        section_title("Распределение по типам")
        data = fetch("/stats/by_type") or []
        if data:
            df_t = pd.DataFrame(data)
            fig = px.bar(df_t, x="count", y="ai_type", orientation="h",
                         color="avg_priority",
                         color_continuous_scale=["#1a1a2e","#FF416C","#FF4B2B"],
                         labels={"count":"Тикетов","ai_type":"","avg_priority":"Приоритет"},
                         text="count")
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            st.plotly_chart(plotly_dark(fig, 320), use_container_width=True)

    with col2:
        section_title("Сентимент")
        data = fetch("/stats/by_sentiment") or []
        if data:
            df_s = pd.DataFrame(data)
            fig = px.pie(df_s, values="count", names="sentiment",
                         color="sentiment", color_discrete_map=SENTIMENT_COLORS, hole=0.55)
            fig.update_traces(textinfo="percent+label", textfont_size=11)
            st.plotly_chart(plotly_dark(fig, 320), use_container_width=True)

    col3, col4 = st.columns([1.5, 1])
    with col3:
        section_title("Тикеты по офисам")
        data = fetch("/stats/by_office") or []
        if data:
            df_o = pd.DataFrame(data)
            fig = px.bar(df_o, x="office", y="tickets", color="escalations",
                         color_continuous_scale=[[0,"#16213E"],[1,"#FF4B2B"]],
                         labels={"tickets":"Тикетов","office":"","escalations":"Эскалации"},
                         text="tickets")
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            fig.update_xaxes(tickangle=-30)
            st.plotly_chart(plotly_dark(fig, 300), use_container_width=True)

    with col4:
        section_title("Приоритеты")
        data = fetch("/stats/by_priority") or []
        if data:
            df_p = pd.DataFrame(data)
            fig = px.bar(df_p, x="priority", y="count", color="count",
                         color_continuous_scale=["#16213E","#F7971E","#FF4B2B"],
                         labels={"priority":"Приоритет","count":"Тикетов"})
            st.plotly_chart(plotly_dark(fig, 300), use_container_width=True)

    col5, col6 = st.columns([1, 2])
    with col5:
        section_title("Языки")
        data = fetch("/stats/by_lang") or []
        if data:
            df_l = pd.DataFrame(data)
            fig = px.pie(df_l, values="count", names="ai_lang",
                         color_discrete_sequence=[COLORS["primary"], COLORS["accent"], COLORS["pos"]],
                         hole=0.4)
            st.plotly_chart(plotly_dark(fig, 280), use_container_width=True)

    with col6:
        section_title("Топ-10 менеджеров по нагрузке")
        data = fetch("/managers/load") or []
        if data:
            df_m = pd.DataFrame(data).head(10)
            fig = px.bar(df_m, x="manager", y="tickets", color="office",
                         color_discrete_sequence=px.colors.qualitative.Bold,
                         labels={"tickets":"Тикетов","manager":""}, text="tickets")
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            fig.update_xaxes(tickangle=-30)
            st.plotly_chart(plotly_dark(fig, 280), use_container_width=True)


# ─────────────────────────────────────────────
# СТРАНИЦА: ТИКЕТЫ
# ─────────────────────────────────────────────

elif page == "Тикеты":
    st.markdown('<div class="fire-header">Тикеты</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Список обращений</div>', unsafe_allow_html=True)

    count_data = fetch("/tickets/count", filter_params) or {"count": 0}
    total_count = count_data["count"]
    st.markdown(f'<div style="color:#555;margin-bottom:1rem;font-family:\'Space Mono\',monospace;font-size:0.8rem;">Найдено: <span style="color:{COLORS["accent"]};font-weight:700;">{total_count}</span></div>', unsafe_allow_html=True)

    per_page = 50
    page_num = st.number_input("Страница", min_value=1, max_value=max(1,(total_count//per_page)+1), value=1)
    offset = (page_num - 1) * per_page

    try:
        r = requests.get(f"{API_BASE}/tickets", params={**filter_params, "limit": per_page, "offset": offset}, timeout=10)
        r.raise_for_status()
        tickets = r.json()
    except Exception as e:
        st.error(f"Ошибка загрузки тикетов: {e}")
        tickets = []

    if tickets:
        df = pd.DataFrame(tickets)
        cols = ["guid","city","ai_type","sentiment","priority","office","manager","is_escalation"]
        df_d = df[[c for c in cols if c in df.columns]].copy()

        if "priority" in df_d.columns:
            df_d["priority"] = df_d["priority"].apply(
                lambda x: f"HI {x}" if x >= 8 else (f"MD {x}" if x >= 5 else f"LO {x}")
            )
        if "is_escalation" in df_d.columns:
            df_d["is_escalation"] = df_d["is_escalation"].apply(lambda x: "ESC" if x else "—")

        st.dataframe(df_d, use_container_width=True, height=480, hide_index=True)

        st.markdown("---")
        section_title("Детали тикета")
        sel = st.selectbox("GUID", [""] + [t["guid"] for t in tickets])
        if sel:
            d = fetch(f"/tickets/{sel}")
            if d:
                c1,c2,c3 = st.columns(3)
                c1.metric("Тип", d.get("ai_type","—"))
                c2.metric("Приоритет", d.get("priority","—"))
                c3.metric("Сентимент", d.get("sentiment","—"))
                c4,c5 = st.columns(2)
                c4.markdown(f"**Офис:** {d.get('office','—')}  \n**Менеджер:** {d.get('manager','—')}  \n**Город:** {d.get('city','—')}")
                c5.markdown(f"**Сегмент:** {d.get('segment','—')}  \n**Язык:** {d.get('ai_lang','—')}  \n**Маршрут:** {d.get('office_reason','—')}")
                if d.get("summary"):        st.markdown(f"**Резюме:** {d['summary']}")
                if d.get("recommendation"): st.info(f"Рекомендация: {d['recommendation']}")
    elif total_count == 0:
        st.info("Нет тикетов по выбранным фильтрам.")


# ─────────────────────────────────────────────
# СТРАНИЦА: МЕНЕДЖЕРЫ
# ─────────────────────────────────────────────

elif page == "Менеджеры":
    st.markdown('<div class="fire-header">Менеджеры</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Нагрузка и распределение</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        section_title("Нагрузка менеджеров")
        data = fetch("/managers/load") or []
        if data:
            df_m = pd.DataFrame(data)
            fig = px.bar(df_m, x="tickets", y="manager", orientation="h",
                         color="office", color_discrete_sequence=px.colors.qualitative.Bold,
                         labels={"tickets":"Тикетов","manager":""}, text="tickets")
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            st.plotly_chart(plotly_dark(fig, 600), use_container_width=True)

    with col2:
        section_title("Офисы — нагрузка vs менеджеры")
        data = fetch("/managers/fairness") or []
        if data:
            df_f = pd.DataFrame(data)
            fig = px.scatter(df_f, x="managers", y="tickets", size="mean_load",
                             color="office", color_discrete_sequence=px.colors.qualitative.Bold,
                             hover_name="office", text="office",
                             labels={"managers":"Менеджеров","tickets":"Тикетов","mean_load":"Ср. нагрузка"})
            fig.update_traces(textposition="top center")
            st.plotly_chart(plotly_dark(fig, 400), use_container_width=True)

        section_title("Таблица")
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
# СТРАНИЦА: КАРТА
# ─────────────────────────────────────────────

elif page == "Карта":
    st.markdown('<div class="fire-header">Карта</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Геораспределение тикетов</div>', unsafe_allow_html=True)

    try:
        import folium
        from folium import IFrame
        from streamlit_folium import st_folium

        geo_tickets = fetch("/geo/tickets") or []
        geo_offices = fetch("/geo/offices") or []

        m = folium.Map(location=[48.0, 67.0], zoom_start=5, tiles="CartoDB dark_matter")

        import re as _re
        _OFFICE_ADDR = {
            "актау":            "17-й микрорайон, Бизнес-центр «Urban», зд. 22",
            "актобе":           "пр. Алии Молдагуловой, 44",
            "алматы":           "пр-т Аль-Фараби, 77/7 БЦ «Esentai Tower», 7 этаж",
            "астана":           "Есиль район, Достық 16, БЦ «Talan Towers», 27 этаж",
            "атырау":           "ул. Студенческая 52, БЦ «Адал», 2 этаж, 201 офис",
            "караганда":        "пр. Нуркена Абдирова, ст 12 НП 3, 2 этаж",
            "кокшетау":         "пр-т Назарбаева, д. 4/2",
            "костанай":         "пр-т Аль-Фараби 65, 12 этаж, офис №1201",
            "кызылорда":        "ул. Кунаева 4, БЦ Прима Парк",
            "павлодар":         "ул. Луговая 16, «Дом инвесторов», 7 этаж",
            "петропавловск":    "ул. Букетова 31А",
            "тараз":            "ул. Желтоксан 86",
            "уральск":          "ул. Ескалиева, д. 177, оф. 505",
            "орал":             "ул. Ескалиева, д. 177, оф. 505",
            "усть-каменогорск": "ул. Максима Горького, д. 50",
            "шымкент":          "ул. Кунаева, д. 59, 1 этаж",
        }

        def _addr(name: str, db_addr: str) -> str:
            if db_addr and str(db_addr).strip() not in ("", "nan", "none", "None", "Адрес не указан"):
                return str(db_addr).strip()
            key = _re.sub(r"\s*\(.*?\)$", "", str(name)).lower().strip().replace("ё", "е")
            for pfx in ("г.", "город ", "city "):
                if key.startswith(pfx):
                    key = key[len(pfx):].strip()
            return _OFFICE_ADDR.get(key, "")

        for o in geo_offices:
            if not (o.get("lat") and o.get("lon")):
                continue
            name    = o.get("name", "—")
            address = _addr(name, o.get("address", ""))
            lat     = o["lat"]
            lon     = o["lon"]
            office_tickets = [t for t in geo_tickets if t.get("office") == name]
            neg_count = sum(1 for t in office_tickets if t.get("sentiment") == "NEG")
            esc_count = sum(1 for t in office_tickets if t.get("is_escalation"))
            popup_html = f"""
            <div style="font-family:Arial,sans-serif;min-width:200px;max-width:260px;">
                <div style="font-size:14px;font-weight:700;color:#FF4B2B;
                            border-bottom:1px solid #eee;padding-bottom:6px;margin-bottom:8px;">{name}</div>
                <div style="font-size:12px;color:#555;margin-bottom:8px;line-height:1.5;">{address}</div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;">
                    <div style="text-align:center;background:#f8f8f8;border-radius:4px;padding:4px;">
                        <div style="font-size:16px;font-weight:700;color:#333;">{len(office_tickets)}</div>
                        <div style="font-size:10px;color:#888;">тикетов</div>
                    </div>
                    <div style="text-align:center;background:#fff5f5;border-radius:4px;padding:4px;">
                        <div style="font-size:16px;font-weight:700;color:#FF4B2B;">{neg_count}</div>
                        <div style="font-size:10px;color:#888;">негатив</div>
                    </div>
                    <div style="text-align:center;background:#fff8f0;border-radius:4px;padding:4px;">
                        <div style="font-size:16px;font-weight:700;color:#F7971E;">{esc_count}</div>
                        <div style="font-size:10px;color:#888;">эскал.</div>
                    </div>
                </div>
                <div style="font-size:10px;color:#aaa;margin-top:6px;">{lat:.4f}, {lon:.4f}</div>
            </div>
            """
            folium.Marker(
                [lat, lon],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"🏢 {name}",
                icon=folium.Icon(color="red", icon="building", prefix="fa"),
            ).add_to(m)

        cmap = {"NEG": "red", "NEU": "orange", "POS": "green"}
        sentiment_ru = {"NEG": "Негатив", "NEU": "Нейтрал", "POS": "Позитив"}

        for t in geo_tickets:
            if not (t.get("lat") and t.get("lon")):
                continue
            sentiment  = t.get("sentiment", "NEU")
            ai_type    = t.get("ai_type", "—")
            office     = t.get("office", "—")
            city       = t.get("city", "—")
            priority   = t.get("priority", "—")
            is_esc     = t.get("is_escalation", False)
            color      = cmap.get(sentiment, "orange")
            sent_ru    = sentiment_ru.get(sentiment, sentiment)
            priority_color = "#FF4B2B" if str(priority).isdigit() and int(priority) >= 8 else \
                             "#F7971E" if str(priority).isdigit() and int(priority) >= 5 else "#00C9A7"
            esc_badge = '<span style="background:#FF4B2B;color:white;font-size:10px;padding:1px 6px;border-radius:3px;margin-left:4px;">ESC</span>' if is_esc else ""
            popup_html = f"""
            <div style="font-family:Arial,sans-serif;min-width:190px;max-width:240px;">
                <div style="font-size:13px;font-weight:700;color:#333;
                            border-bottom:1px solid #eee;padding-bottom:5px;margin-bottom:7px;">
                    {ai_type}{esc_badge}</div>
                <table style="font-size:12px;color:#555;width:100%;border-collapse:collapse;">
                    <tr><td style="padding:2px 0;color:#999;">Город</td>
                        <td style="padding:2px 0;font-weight:600;">{city}</td></tr>
                    <tr><td style="padding:2px 0;color:#999;">Офис</td>
                        <td style="padding:2px 0;font-weight:600;">{office}</td></tr>
                    <tr><td style="padding:2px 0;color:#999;">Приоритет</td>
                        <td style="padding:2px 0;font-weight:700;color:{priority_color};">{priority}</td></tr>
                    <tr><td style="padding:2px 0;color:#999;">Сентимент</td>
                        <td style="padding:2px 0;font-weight:600;color:{color};">{sent_ru}</td></tr>
                </table>
            </div>
            """
            folium.CircleMarker(
                [t["lat"], t["lon"]],
                radius=7 if is_esc else 5,
                color=color, weight=2 if is_esc else 1,
                fill=True, fill_color=color, fill_opacity=0.65,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{city} · {ai_type} · P{priority}",
            ).add_to(m)

        st_folium(m, width=None, height=580, returned_objects=[])

        col_l1, col_l2, col_l3, col_l4, col_l5 = st.columns(5)
        for col, color, label in [
            (col_l1, "#FF4B2B", "Негатив"),
            (col_l2, "#F7971E", "Нейтрал"),
            (col_l3, "#00C9A7", "Позитив"),
            (col_l4, "#FF4B2B", "Офис"),
            (col_l5, "#FF4B2B", "Большой = ESC"),
        ]:
            col.markdown(
                f'<div style="font-family:\'Space Mono\',monospace;font-size:0.68rem;'
                f'color:#555;display:flex;align-items:center;gap:6px;">'
                f'<span style="width:10px;height:10px;border-radius:50%;'
                f'background:{color};display:inline-block;flex-shrink:0;"></span>'
                f'{label}</div>',
                unsafe_allow_html=True
            )

    except ImportError:
        st.warning("Установите: `pip install folium streamlit-folium --break-system-packages`")


# ─────────────────────────────────────────────
# СТРАНИЦА: ЗАГРУЗКА CSV
# ─────────────────────────────────────────────

elif page == "Загрузка":
    st.markdown('<div class="fire-header">Загрузка CSV</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Импорт данных · тикеты · менеджеры · офисы</div>', unsafe_allow_html=True)

    st.markdown("""
    <details style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,75,43,0.2);
                    border-radius:10px;padding:0;margin-bottom:1rem;overflow:hidden;">
        <summary style="padding:12px 18px;cursor:pointer;font-family:'Space Mono',monospace;
                        font-size:0.78rem;font-weight:700;color:#888;letter-spacing:1.5px;
                        text-transform:uppercase;list-style:none;display:flex;
                        align-items:center;gap:8px;user-select:none;">
            <span style="color:#FF4B2B;font-size:1rem;">▸</span>
            ТРЕБОВАНИЯ К ФАЙЛАМ
        </summary>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;padding:0 18px 16px 18px;">
            <div style="background:#0d0d1a;border:1px solid rgba(255,75,43,0.15);border-radius:8px;padding:14px;">
                <div style="font-family:'Space Mono',monospace;font-size:0.72rem;color:#FF4B2B;
                            font-weight:700;letter-spacing:1px;margin-bottom:10px;">tickets.csv</div>
                <div style="font-family:'Space Mono',monospace;font-size:0.72rem;color:#666;line-height:2;">
                    GUID клиента<br>Пол клиента<br>Дата рождения<br>Описание<br>
                    Вложения<br>Сегмент клиента<br>Страна<br>Область<br>
                    Населённый пункт<br>Улица<br>Дом
                </div>
            </div>
            <div style="background:#0d0d1a;border:1px solid rgba(255,75,43,0.15);border-radius:8px;padding:14px;">
                <div style="font-family:'Space Mono',monospace;font-size:0.72rem;color:#FF4B2B;
                            font-weight:700;letter-spacing:1px;margin-bottom:10px;">managers.csv</div>
                <div style="font-family:'Space Mono',monospace;font-size:0.72rem;color:#666;line-height:2;">
                    ФИО<br>Должность<br>Офис<br>Навыки<br>Количество обращений в работе
                </div>
            </div>
            <div style="background:#0d0d1a;border:1px solid rgba(255,75,43,0.15);border-radius:8px;padding:14px;">
                <div style="font-family:'Space Mono',monospace;font-size:0.72rem;color:#FF4B2B;
                            font-weight:700;letter-spacing:1px;margin-bottom:10px;">business_units.csv</div>
                <div style="font-family:'Space Mono',monospace;font-size:0.72rem;color:#666;line-height:2;">
                    Офис<br>Адрес
                </div>
            </div>
        </div>
    </details>
    """, unsafe_allow_html=True)

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="section-title">Тикеты</div>', unsafe_allow_html=True)
        tickets_file = st.file_uploader("tickets.csv", type=["csv"], key="upload_tickets", label_visibility="collapsed")
        if tickets_file:
            try:
                df_preview = pd.read_csv(tickets_file, nrows=5, encoding="utf-8-sig")
                st.markdown(f'<div class="upload-step step-ok">&#10003; Загружен · {tickets_file.size // 1024} KB · {len(df_preview.columns)} колонок</div>', unsafe_allow_html=True)
                tickets_file.seek(0)
            except Exception as e:
                st.markdown(f'<div class="upload-step step-err">&#10007; Ошибка чтения: {e}</div>', unsafe_allow_html=True)
                tickets_file = None

    with col2:
        st.markdown('<div class="section-title">Менеджеры</div>', unsafe_allow_html=True)
        managers_file = st.file_uploader("managers.csv", type=["csv"], key="upload_managers", label_visibility="collapsed")
        if managers_file:
            try:
                df_preview = pd.read_csv(managers_file, nrows=5, encoding="utf-8-sig")
                st.markdown(f'<div class="upload-step step-ok">&#10003; Загружен · {managers_file.size // 1024} KB · {len(df_preview.columns)} колонок</div>', unsafe_allow_html=True)
                managers_file.seek(0)
            except Exception as e:
                st.markdown(f'<div class="upload-step step-err">&#10007; Ошибка чтения: {e}</div>', unsafe_allow_html=True)
                managers_file = None

    with col3:
        st.markdown('<div class="section-title">Офисы</div>', unsafe_allow_html=True)
        units_file = st.file_uploader("business_units.csv", type=["csv"], key="upload_units", label_visibility="collapsed")
        if units_file:
            try:
                df_preview = pd.read_csv(units_file, nrows=5, encoding="utf-8-sig")
                st.markdown(f'<div class="upload-step step-ok">&#10003; Загружен · {units_file.size // 1024} KB · {len(df_preview.columns)} колонок</div>', unsafe_allow_html=True)
                units_file.seek(0)
            except Exception as e:
                st.markdown(f'<div class="upload-step step-err">&#10007; Ошибка чтения: {e}</div>', unsafe_allow_html=True)
                units_file = None

    st.markdown("---")

    if any([tickets_file, managers_file, units_file]):
        section_title("Предпросмотр данных")
        tab_names, tab_files = [], []
        if tickets_file:  tab_names.append("Тикеты");    tab_files.append(tickets_file)
        if managers_file: tab_names.append("Менеджеры"); tab_files.append(managers_file)
        if units_file:    tab_names.append("Офисы");     tab_files.append(units_file)

        tabs = st.tabs(tab_names)
        for tab, f in zip(tabs, tab_files):
            with tab:
                try:
                    df_prev = pd.read_csv(f, nrows=10, encoding="utf-8-sig")
                    st.dataframe(df_prev, use_container_width=True, hide_index=True)
                    f.seek(0)
                    total_rows = sum(1 for _ in f) - 1
                    f.seek(0)
                    st.markdown(f'<div style="font-family:\'Space Mono\',monospace;font-size:0.72rem;color:#555;margin-top:0.4rem;">Показано 10 из ~{total_rows} строк · {len(df_prev.columns)} колонок</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Ошибка предпросмотра: {e}")

    st.markdown("---")

    all_ready = tickets_file and managers_file and units_file
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if not all_ready:
            missing = []
            if not tickets_file:  missing.append("tickets.csv")
            if not managers_file: missing.append("managers.csv")
            if not units_file:    missing.append("business_units.csv")
            st.markdown(f'<div class="upload-step step-wait">Ожидание: {", ".join(missing)}</div>', unsafe_allow_html=True)
        run_btn = st.button("Запустить импорт и маршрутизацию", disabled=not all_ready, use_container_width=True, key="run_import")

    with col_info:
        st.markdown("""
        <div style="background:rgba(255,255,255,0.03);border-radius:8px;padding:12px 16px;
                    font-family:'Space Mono',monospace;font-size:0.72rem;color:#555;line-height:1.8;">
            <div style="color:#888;margin-bottom:4px;">Что произойдёт:</div>
            1. Файлы сохранятся во временную директорию<br>
            2. БД очистится и заполнится новыми данными<br>
            3. Запустится AI-обогащение тикетов<br>
            4. FIRE Engine распределит тикеты по менеджерам<br>
            5. Дашборд обновится автоматически
        </div>
        """, unsafe_allow_html=True)

    if run_btn and all_ready:
        import tempfile, os, subprocess, sys
        st.markdown("---")
        section_title("Выполнение")
        log_container = st.container()

        def step(msg, status="run"):
            log_container.markdown(f'<div class="upload-step step-{status}">{msg}</div>', unsafe_allow_html=True)

        with st.spinner("Идёт импорт..."):
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    t_path = os.path.join(tmpdir, "tickets.csv")
                    m_path = os.path.join(tmpdir, "managers.csv")
                    u_path = os.path.join(tmpdir, "business_units.csv")

                    tickets_file.seek(0); managers_file.seek(0); units_file.seek(0)
                    with open(t_path, "wb") as f: f.write(tickets_file.read())
                    with open(m_path, "wb") as f: f.write(managers_file.read())
                    with open(u_path, "wb") as f: f.write(units_file.read())

                    step("&#10003; Файлы сохранены во временную директорию", "ok")
                    step("&#9654; Инициализация БД и загрузка данных...", "run")

                    try:
                        project_root = os.path.dirname(os.path.abspath(__file__))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)

                        from db import init_db, load_csv, get_connection
                        conn = get_connection()
                        with conn.cursor() as cur:
                            cur.execute("TRUNCATE TABLE assignments  RESTART IDENTITY CASCADE;")
                            cur.execute("TRUNCATE TABLE ai_analysis  RESTART IDENTITY CASCADE;")
                            cur.execute("TRUNCATE TABLE tickets      RESTART IDENTITY CASCADE;")
                            cur.execute("TRUNCATE TABLE managers     RESTART IDENTITY CASCADE;")
                            cur.execute("TRUNCATE TABLE offices      RESTART IDENTITY CASCADE;")
                        conn.commit(); conn.close()
                        init_db()
                        load_csv(tickets_path=t_path, managers_path=m_path, units_path=u_path)
                        step("&#10003; БД заполнена", "ok")
                    except Exception as e:
                        step(f"&#10007; Ошибка БД: {e}", "err")
                        st.stop()

                    step("&#9654; Запуск AI-обогащения и маршрутизации...", "run")
                    step("&#9432; Это может занять 1-3 минуты", "wait")

                    try:
                        result = subprocess.run(
                            [sys.executable, os.path.join(project_root, "run.py")],
                            capture_output=True, text=True, timeout=300, cwd=project_root,
                        )
                        if result.returncode == 0:
                            step("&#10003; Маршрутизация завершена успешно", "ok")
                            for line in [l for l in result.stdout.strip().split("\n") if l.strip()][-6:]:
                                log_container.markdown(f'<div style="font-family:\'Space Mono\',monospace;font-size:0.7rem;color:#555;padding:2px 12px;">{line}</div>', unsafe_allow_html=True)
                        else:
                            step("&#10007; run.py завершился с ошибкой", "err")
                            if result.stderr:
                                log_container.code(result.stderr[-1000:], language="text")
                    except subprocess.TimeoutExpired:
                        step("&#10007; Таймаут 5 минут превышен", "err")
                    except Exception as e:
                        step(f"&#10007; Ошибка запуска: {e}", "err")

                step("&#10003; Импорт завершён", "ok")
                st.success("Данные загружены. Перейдите на страницу Обзор.")
                st.cache_data.clear()

            except Exception as e:
                step(f"&#10007; Неожиданная ошибка: {e}", "err")


# ─────────────────────────────────────────────
# СТРАНИЦА: AI АНАЛИТИК
# ─────────────────────────────────────────────

elif page == "AI Аналитик":
    st.markdown("""
    <style>
    .chat-wrap {
        display:flex;flex-direction:column;gap:12px;
        max-height:480px;overflow-y:auto;padding:16px;margin-bottom:16px;
        background:rgba(13,13,26,0.6);border:1px solid rgba(255,75,43,0.12);
        border-radius:14px;scroll-behavior:smooth;
    }
    .chat-wrap::-webkit-scrollbar{width:4px;}
    .chat-wrap::-webkit-scrollbar-thumb{background:rgba(255,75,43,0.3);border-radius:4px;}
    .msg-user{display:flex;justify-content:flex-end;margin:2px 0;}
    .msg-user-inner{max-width:72%;}
    .msg-user-label{font-family:'Space Mono',monospace;font-size:0.6rem;
        color:rgba(255,75,43,0.6)!important;text-align:right;margin-bottom:3px;letter-spacing:1px;}
    .msg-user-bubble{background:linear-gradient(135deg,rgba(255,75,43,0.22),rgba(255,65,108,0.16));
        border:1px solid rgba(255,75,43,0.3);border-radius:16px 16px 4px 16px;
        padding:10px 16px;font-family:'Syne',sans-serif;font-size:0.88rem;
        color:#FFFFFF!important;line-height:1.55;}
    .msg-ai{display:flex;align-items:flex-start;gap:10px;margin:2px 0;}
    .msg-ai-ava{width:28px;height:28px;flex-shrink:0;
        background:linear-gradient(135deg,#F7971E,#FF4B2B);border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        font-size:0.75rem;margin-top:18px;}
    .msg-ai-wrap{flex:1;max-width:78%;}
    .msg-ai-label{font-family:'Space Mono',monospace;font-size:0.6rem;
        color:rgba(247,151,30,0.65)!important;margin-bottom:3px;letter-spacing:1px;}
    .msg-ai-bubble{background:rgba(247,151,30,0.07);
        border:1px solid rgba(247,151,30,0.18);
        border-radius:4px 16px 16px 16px;padding:10px 16px;
        font-family:'Syne',sans-serif;font-size:0.88rem;
        color:#DDDDDD!important;line-height:1.6;}
    .msg-ai-bubble strong,.msg-ai-bubble b{color:#FFFFFF!important;}
    .chat-empty{display:flex;flex-direction:column;align-items:center;
        justify-content:center;padding:3rem;gap:10px;}
    .quick-btn .stButton > button{
        background:rgba(255,255,255,0.03)!important;
        border:1px solid rgba(255,75,43,0.18)!important;
        color:#666!important;font-size:0.78rem!important;
        font-family:'Syne',sans-serif!important;font-weight:500!important;
        text-align:left!important;padding:9px 14px!important;
        border-radius:8px!important;height:auto!important;
        min-height:44px!important;transition:all 0.15s!important;}
    .quick-btn .stButton > button:hover{
        background:rgba(255,75,43,0.1)!important;
        border-color:rgba(255,75,43,0.4)!important;
        color:#FFFFFF!important;transform:none!important;}
    .quick-btn .stButton > button p{
        color:inherit!important;font-size:0.78rem!important;
        white-space:normal!important;text-align:left!important;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="fire-header">AI Аналитик</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Аналитика данных · задайте вопрос · графики по запросу</div>', unsafe_allow_html=True)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "llm_history" not in st.session_state:
        st.session_state.llm_history = []
    if "chat_chart" not in st.session_state:
        st.session_state.chat_chart = None

    # ── Быстрые вопросы ──
    suggested = [
        "Сколько всего тикетов и какой процент эскалаций?",
        "Какой офис обрабатывает больше всего обращений?",
        "Какие типы обращений встречаются чаще всего?",
        "Кто из менеджеров перегружен больше всего?",
        "Сколько тикетов с негативным сентиментом?",
        "В каком офисе больше всего эскалаций?",
    ]
    section_title("Быстрые вопросы")
    q_cols = st.columns(3)
    for i, q in enumerate(suggested):
        with q_cols[i % 3]:
            st.markdown('<div class="quick-btn">', unsafe_allow_html=True)
            if st.button(q, key=f"sq_{i}", use_container_width=True):
                st.session_state._quick_question = q
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    section_title("Чат с данными")

    # ── История чата ──
    if st.session_state.chat_history:
        msgs_html = '<div class="chat-wrap">'
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                msgs_html += f"""
                <div class="msg-user">
                  <div class="msg-user-inner">
                    <div class="msg-user-label">ВЫ</div>
                    <div class="msg-user-bubble">{msg['content']}</div>
                  </div>
                </div>"""
            else:
                src_label = "LLM" if msg.get("source") == "llm" else "RULE"
                msgs_html += f"""
                <div class="msg-ai">
                  <div class="msg-ai-ava">🔥</div>
                  <div class="msg-ai-wrap">
                    <div class="msg-ai-label">FIRE AI &nbsp;<span style="color:#2a2a2a;font-size:0.55rem;">{src_label}</span></div>
                    <div class="msg-ai-bubble">{msg['content']}</div>
                  </div>
                </div>"""
        msgs_html += '</div>'
        st.markdown(msgs_html, unsafe_allow_html=True)
    else:
        st.markdown('''
        <div class="chat-wrap">
          <div class="chat-empty">
            <div style="font-size:2.2rem;opacity:0.3;">🔥</div>
            <div style="font-family:'Space Mono',monospace;font-size:0.72rem;
                        color:#333!important;letter-spacing:2px;text-transform:uppercase;">
              Задайте вопрос или выберите из быстрых
            </div>
          </div>
        </div>
        ''', unsafe_allow_html=True)

    # ── Динамический график под чатом ──
    if st.session_state.chat_chart:
        chart_type, chart_title = st.session_state.chat_chart
        render_chat_chart(chart_type, chart_title)

    # ── Форма ввода ──
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "q", placeholder="Например: Распределение тональности по городам",
            label_visibility="collapsed"
        )
        sc, cc = st.columns([5, 1])
        submitted = sc.form_submit_button("⚡  Отправить", use_container_width=True)
        cleared   = cc.form_submit_button("✕  Очистить",  use_container_width=True)

    if hasattr(st.session_state, "_quick_question"):
        user_input = st.session_state._quick_question
        submitted = True
        del st.session_state._quick_question

    if cleared:
        st.session_state.chat_history = []
        st.session_state.llm_history  = []
        st.session_state.chat_chart   = None
        st.rerun()

    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Анализирую..."):
            result = post_api("/ai/chat", {"question": user_input, "history": st.session_state.llm_history[-6:]})

        answer = result.get("answer", "Нет ответа")
        source = result.get("source", "unknown")
        st.session_state.chat_history.append({"role": "assistant", "content": answer, "source": source})
        st.session_state.llm_history.append({"role": "user", "content": user_input})
        st.session_state.llm_history.append({"role": "assistant", "content": answer})

        # ── Определяем нужен ли график ──
        st.session_state.chat_chart = detect_chart_type(user_input)

        st.rerun()