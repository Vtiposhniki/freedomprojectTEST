# dashboard.py
"""
FIRE Engine — Streamlit Dashboard
Запуск: streamlit run dashboard.py
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

# ─────────────────────────────────────────────
# КОНФИГ
# ─────────────────────────────────────────────

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="FIRE Engine Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Цветовая схема
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
TYPE_COLORS = px.colors.qualitative.Bold

# ─────────────────────────────────────────────
# КАСТОМНЫЕ СТИЛИ
# ─────────────────────────────────────────────

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

    /* ── BASE ── */
    html, body {{
        background-color: {COLORS['dark']} !important;
    }}
    .stApp {{
        background: linear-gradient(135deg, {COLORS['dark']} 0%, {COLORS['surface']} 100%) !important;
    }}

    /* ── ГЛОБАЛЬНЫЙ ТЕКСТ — всё должно быть светлым ── */
    html, body, p, span, div, label, li, a,
    [class*="css"], .stMarkdown, .stText {{
        color: {COLORS['text']} !important;
        font-family: 'Syne', sans-serif !important;
    }}

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] {{
        background: {COLORS['surface']} !important;
        border-right: 1px solid rgba(255,75,43,0.25) !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {COLORS['text']} !important;
    }}

    /* Радио кнопки в сайдбаре */
    [data-testid="stSidebar"] .stRadio label,
    [data-testid="stSidebar"] .stRadio div,
    [data-testid="stSidebar"] .stRadio p,
    [data-testid="stSidebar"] .stRadio span {{
        color: #FFFFFF !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
    }}
    /* Активный пункт меню */
    [data-testid="stSidebar"] .stRadio [aria-checked="true"] + div p,
    [data-testid="stSidebar"] .stRadio [aria-checked="true"] ~ div {{
        color: {COLORS['accent']} !important;
        font-weight: 700 !important;
    }}
    /* Кружки radio */
    [data-testid="stSidebar"] .stRadio [role="radio"] {{
        border-color: {COLORS['primary']} !important;
        background: transparent !important;
    }}
    [data-testid="stSidebar"] .stRadio [aria-checked="true"] {{
        background: {COLORS['primary']} !important;
        border-color: {COLORS['primary']} !important;
    }}

    /* Selectbox в сайдбаре */
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSelectbox span {{
        color: #CCCCCC !important;
        font-size: 0.8rem !important;
    }}
    [data-testid="stSidebar"] .stSelectbox > div > div {{
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(255,75,43,0.3) !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
    }}
    [data-testid="stSidebar"] .stSelectbox > div > div > div {{
        color: #FFFFFF !important;
    }}

    /* Divider */
    [data-testid="stSidebar"] hr {{
        border-color: rgba(255,75,43,0.25) !important;
        margin: 0.8rem 0 !important;
    }}

    /* ── ЗАГОЛОВОК ── */
    .fire-header {{
        background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['secondary']}, {COLORS['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-family: 'Syne', sans-serif !important;
        font-weight: 800;
        font-size: 2.8rem;
        letter-spacing: -1px;
        line-height: 1.1;
        margin-bottom: 0.2rem;
    }}

    /* ── KPI КАРТОЧКИ ── */
    .kpi-card {{
        background: {COLORS['card']};
        border: 1px solid rgba(255,75,43,0.25);
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        text-align: center;
        transition: border-color 0.2s, transform 0.2s;
    }}
    .kpi-card:hover {{
        border-color: {COLORS['primary']};
        transform: translateY(-2px);
    }}
    .kpi-value {{
        font-family: 'Space Mono', monospace !important;
        font-size: 2.2rem;
        font-weight: 700;
        color: {COLORS['accent']} !important;
        line-height: 1;
    }}
    .kpi-label {{
        font-size: 0.72rem;
        color: #AAAAAA !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-top: 0.4rem;
    }}

    /* ── SECTION TITLE ── */
    .section-title {{
        font-family: 'Syne', sans-serif !important;
        font-weight: 700;
        font-size: 1rem;
        color: #FFFFFF !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 0.8rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid {COLORS['primary']};
    }}

    /* ── ЧАТ ── */
    .chat-user {{
        background: rgba(255,75,43,0.12);
        border-left: 3px solid {COLORS['primary']};
        border-radius: 0 8px 8px 0;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        color: #FFFFFF !important;
    }}
    .chat-bot {{
        background: rgba(247,151,30,0.1);
        border-left: 3px solid {COLORS['accent']};
        border-radius: 0 8px 8px 0;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        color: #FFFFFF !important;
    }}
    .chat-source {{
        font-size: 0.65rem;
        color: #777777 !important;
        font-family: 'Space Mono', monospace !important;
    }}

    /* ── BADGES ── */
    .badge-pos {{ background: rgba(0,201,167,0.2); color: #00C9A7 !important; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 700; }}
    .badge-neu {{ background: rgba(247,151,30,0.2); color: #F7971E !important; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 700; }}
    .badge-neg {{ background: rgba(255,75,43,0.2);  color: #FF6B50 !important; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 700; }}

    /* ── КНОПКИ ── */
    .stButton > button {{
        background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['secondary']}) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Space Mono', monospace !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px;
        transition: opacity 0.2s;
    }}
    .stButton > button:hover {{ opacity: 0.85 !important; }}
    .stButton > button p {{ color: #FFFFFF !important; }}

    /* ── ФОРМА / ИНПУТ ── */
    .stTextInput > div > div > input {{
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,75,43,0.35) !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
    }}
    .stTextInput label {{ color: #CCCCCC !important; }}

    /* ── МЕТРИКИ ── */
    [data-testid="stMetricValue"] {{ color: {COLORS['accent']} !important; }}
    [data-testid="stMetricLabel"] {{ color: #AAAAAA !important; }}

    /* ── СТАТУС ── */
    .status-ok  {{ color: {COLORS['pos']} !important; font-family: 'Space Mono', monospace !important; font-size: 0.85rem; }}
    .status-err {{ color: {COLORS['neg']} !important; font-family: 'Space Mono', monospace !important; font-size: 0.85rem; }}

    /* ── ТАБЛИЦА ── */
    .dataframe th {{
        background: {COLORS['card']} !important;
        color: {COLORS['accent']} !important;
    }}
    .dataframe td {{ color: {COLORS['text']} !important; }}

    /* ── PLOTLY ── */
    .js-plotly-plot {{ border-radius: 10px; overflow: hidden; }}

    /* ── NUMBER INPUT ── */
    .stNumberInput label {{ color: #CCCCCC !important; }}
    .stNumberInput input {{ color: #FFFFFF !important; background: rgba(255,255,255,0.06) !important; border-color: rgba(255,75,43,0.3) !important; }}

    /* ── SPINNER ── */
    .stSpinner > div {{ border-top-color: {COLORS['primary']} !important; }}

    /* Убираем белый фон у виджетов */
    .stSelectbox > div, .stMultiSelect > div {{
        background: transparent !important;
    }}

    /* Warning/Info блоки */
    .stAlert {{ background: rgba(255,75,43,0.1) !important; border: 1px solid rgba(255,75,43,0.3) !important; }}
    .stAlert p {{ color: #FFFFFF !important; }}
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


def post(endpoint: str, data: dict):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"answer": f"⚠️ Ошибка подключения к API: {e}", "source": "error"}


# ─────────────────────────────────────────────
# КОМПОНЕНТЫ
# ─────────────────────────────────────────────

def kpi_card(col, value, label, prefix="", suffix=""):
    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{prefix}{value}{suffix}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def section_title(text: str):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def plotly_dark_layout(fig, height=350):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(22,33,62,0.6)",
        font=dict(family="Syne, sans-serif", color=COLORS["text"]),
        height=height,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)")
    return fig


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown('<div class="fire-header">🔥 FIRE</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#888;font-size:0.75rem;letter-spacing:2px;margin-bottom:1.5rem;">ENGINE DASHBOARD</div>', unsafe_allow_html=True)

    # Health check — лёгкий запрос
    health = fetch("/health")
    if health:
        db_icon  = "🟢" if health.get("db")  else "🔴"
        llm_icon = "🟢" if health.get("llm") else "🟡"
        st.markdown(f'<span class="status-ok">{db_icon} Database &nbsp; {llm_icon} LLM</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-err">🔴 API offline — запустите uvicorn api:app</span>', unsafe_allow_html=True)

    st.divider()

    # Навигация
    page = st.radio(
        "Раздел",
        ["📊 Обзор", "🎫 Тикеты", "👥 Менеджеры", "🗺️ Карта", "🤖 AI Аналитик"],
        label_visibility="collapsed",
    )

    st.divider()

    # Фильтры — только мета (один лёгкий запрос)
    filters_meta = fetch("/meta/filters") or {}
    offices   = ["Все"] + filters_meta.get("offices",   [])
    ai_types  = ["Все"] + filters_meta.get("ai_types",  [])
    sentiments= ["Все"] + filters_meta.get("sentiments",[])
    languages = ["Все"] + filters_meta.get("languages", [])

    st.markdown('<div style="font-size:0.7rem;color:#888;text-transform:uppercase;letter-spacing:2px;margin-bottom:0.5rem;">Фильтры</div>', unsafe_allow_html=True)
    f_office    = st.selectbox("Офис",      offices,    index=0)
    f_type      = st.selectbox("Тип",       ai_types,   index=0)
    f_sentiment = st.selectbox("Сентимент", sentiments, index=0)
    f_lang      = st.selectbox("Язык",      languages,  index=0)

    filter_params = {}
    if f_office    != "Все": filter_params["office"]    = f_office
    if f_type      != "Все": filter_params["ai_type"]   = f_type
    if f_sentiment != "Все": filter_params["sentiment"] = f_sentiment
    if f_lang      != "Все": filter_params["ai_lang"]   = f_lang


# ─────────────────────────────────────────────
# СТРАНИЦА: ОБЗОР
# ─────────────────────────────────────────────

if page == "📊 Обзор":
    st.markdown('<div class="fire-header">Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#888;margin-bottom:1.5rem;">Аналитика обращений в реальном времени</div>', unsafe_allow_html=True)

    summary = fetch("/stats/summary")
    if not summary:
        st.warning("⚠️ Нет данных. Убедитесь что API запущен и БД заполнена.")
        st.code("uvicorn api:app --reload --port 8000", language="bash")
        st.stop()

    # KPI
    c1, c2, c3, c4, c5 = st.columns(5)
    kpi_card(c1, summary["total_tickets"], "Всего тикетов")
    kpi_card(c2, f"{summary['escalation_rate_pct']}%", "Эскалаций")
    kpi_card(c3, summary["avg_priority"], "Ср. приоритет")
    kpi_card(c4, f"{summary['negative_sentiment_pct']}%", "Негатив")
    kpi_card(c5, summary["unique_managers"], "Менеджеров")

    st.markdown("<br>", unsafe_allow_html=True)

    # Ряд 1: Типы + Сентимент
    col1, col2 = st.columns([2, 1])

    with col1:
        section_title("Распределение по типам")
        data = fetch("/stats/by_type") or []
        if data:
            df_type = pd.DataFrame(data)
            fig = px.bar(
                df_type, x="count", y="ai_type", orientation="h",
                color="avg_priority",
                color_continuous_scale=["#1a1a2e", "#FF416C", "#FF4B2B"],
                labels={"count": "Тикетов", "ai_type": "", "avg_priority": "Ср. приоритет"},
                text="count",
            )
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            fig = plotly_dark_layout(fig, height=320)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        section_title("Сентимент")
        data = fetch("/stats/by_sentiment") or []
        if data:
            df_sent = pd.DataFrame(data)
            fig = px.pie(
                df_sent, values="count", names="sentiment",
                color="sentiment",
                color_discrete_map=SENTIMENT_COLORS,
                hole=0.55,
            )
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            fig = plotly_dark_layout(fig, height=320)
            st.plotly_chart(fig, use_container_width=True)

    # Ряд 2: Офисы + Приоритеты
    col3, col4 = st.columns([1.5, 1])

    with col3:
        section_title("Тикеты по офисам")
        data = fetch("/stats/by_office") or []
        if data:
            df_off = pd.DataFrame(data)
            fig = px.bar(
                df_off, x="office", y="tickets",
                color="escalations",
                color_continuous_scale=[[0, "#16213E"], [1, "#FF4B2B"]],
                labels={"tickets": "Тикетов", "office": "", "escalations": "Эскалации"},
                text="tickets",
            )
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            fig.update_xaxes(tickangle=-30)
            fig = plotly_dark_layout(fig, height=300)
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        section_title("Распределение приоритетов")
        data = fetch("/stats/by_priority") or []
        if data:
            df_pri = pd.DataFrame(data)
            fig = px.bar(
                df_pri, x="priority", y="count",
                color="count",
                color_continuous_scale=["#16213E", "#F7971E", "#FF4B2B"],
                labels={"priority": "Приоритет", "count": "Тикетов"},
            )
            fig = plotly_dark_layout(fig, height=300)
            st.plotly_chart(fig, use_container_width=True)

    # Ряд 3: Языки
    col5, col6 = st.columns([1, 2])

    with col5:
        section_title("Языки обращений")
        data = fetch("/stats/by_lang") or []
        if data:
            df_lang = pd.DataFrame(data)
            fig = px.pie(
                df_lang, values="count", names="ai_lang",
                color_discrete_sequence=[COLORS["primary"], COLORS["accent"], COLORS["pos"]],
                hole=0.4,
            )
            fig = plotly_dark_layout(fig, height=280)
            st.plotly_chart(fig, use_container_width=True)

    with col6:
        section_title("Нагрузка vs Офис (топ-10 менеджеров)")
        data = fetch("/managers/load") or []
        if data:
            df_mgr = pd.DataFrame(data).head(10)
            fig = px.bar(
                df_mgr, x="manager", y="tickets",
                color="office",
                color_discrete_sequence=px.colors.qualitative.Bold,
                labels={"tickets": "Тикетов", "manager": ""},
                text="tickets",
            )
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            fig.update_xaxes(tickangle=-30)
            fig = plotly_dark_layout(fig, height=280)
            st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────
# СТРАНИЦА: ТИКЕТЫ
# ─────────────────────────────────────────────

elif page == "🎫 Тикеты":
    st.markdown('<div class="fire-header">Тикеты</div>', unsafe_allow_html=True)

    # Счётчик
    count_data = fetch("/tickets/count", filter_params) or {"count": 0}
    total_count = count_data["count"]
    st.markdown(f'<div style="color:#888;margin-bottom:1rem;">Найдено: <span style="color:{COLORS["accent"]};font-weight:700;">{total_count}</span> тикетов</div>', unsafe_allow_html=True)

    # Пагинация
    per_page = 50
    page_num = st.number_input("Страница", min_value=1, max_value=max(1, (total_count // per_page) + 1), value=1)
    offset = (page_num - 1) * per_page

    params = {**filter_params, "limit": per_page, "offset": offset}
    tickets = fetch("/tickets", params) or []

    if tickets:
        df = pd.DataFrame(tickets)

        # Цветные бейджи сентимента
        def sentiment_badge(s):
            cls = {"POS": "badge-pos", "NEU": "badge-neu", "NEG": "badge-neg"}.get(s, "badge-neu")
            return f'<span class="{cls}">{s}</span>'

        # Отображаем колонки
        display_cols = ["guid", "city", "ai_type", "sentiment", "priority", "office", "manager", "is_escalation"]
        available = [c for c in display_cols if c in df.columns]
        df_display = df[available].copy()

        # Форматирование
        if "priority" in df_display.columns:
            df_display["priority"] = df_display["priority"].apply(
                lambda x: f"🔴 {x}" if x >= 8 else (f"🟡 {x}" if x >= 5 else f"🟢 {x}")
            )
        if "is_escalation" in df_display.columns:
            df_display["is_escalation"] = df_display["is_escalation"].apply(
                lambda x: "⚡ Да" if x else "—"
            )

        st.dataframe(
            df_display,
            use_container_width=True,
            height=500,
            hide_index=True,
        )

        # Детальный просмотр тикета
        st.markdown("---")
        section_title("Детали тикета")
        selected_guid = st.selectbox("Выберите GUID", [""] + [t["guid"] for t in tickets])
        if selected_guid:
            detail = fetch(f"/tickets/{selected_guid}")
            if detail:
                c1, c2, c3 = st.columns(3)
                c1.metric("Тип", detail.get("ai_type", "—"))
                c2.metric("Приоритет", detail.get("priority", "—"))
                c3.metric("Сентимент", detail.get("sentiment", "—"))

                c4, c5 = st.columns(2)
                c4.markdown(f"**Офис:** {detail.get('office', '—')}")
                c4.markdown(f"**Менеджер:** {detail.get('manager', '—')}")
                c4.markdown(f"**Город:** {detail.get('city', '—')} / {detail.get('country', '—')}")
                c5.markdown(f"**Сегмент:** {detail.get('segment', '—')}")
                c5.markdown(f"**Язык:** {detail.get('ai_lang', '—')}")
                c5.markdown(f"**Причина маршрута:** {detail.get('office_reason', '—')}")

                if detail.get("summary"):
                    st.markdown(f"**Резюме:** {detail['summary']}")
                if detail.get("recommendation"):
                    st.info(f"💡 **Рекомендация:** {detail['recommendation']}")
    else:
        st.info("Нет тикетов по выбранным фильтрам.")


# ─────────────────────────────────────────────
# СТРАНИЦА: МЕНЕДЖЕРЫ
# ─────────────────────────────────────────────

elif page == "👥 Менеджеры":
    st.markdown('<div class="fire-header">Менеджеры</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        section_title("Нагрузка менеджеров")
        data = fetch("/managers/load") or []
        if data:
            df_mgr = pd.DataFrame(data)
            fig = px.bar(
                df_mgr, x="tickets", y="manager", orientation="h",
                color="office",
                color_discrete_sequence=px.colors.qualitative.Bold,
                labels={"tickets": "Тикетов", "manager": ""},
                text="tickets",
            )
            fig.update_traces(textposition="outside", textfont_color=COLORS["text"])
            fig = plotly_dark_layout(fig, height=600)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        section_title("Распределение по офисам")
        data = fetch("/managers/fairness") or []
        if data:
            df_fair = pd.DataFrame(data)

            fig = px.scatter(
                df_fair, x="managers", y="tickets",
                size="mean_load", color="office",
                color_discrete_sequence=px.colors.qualitative.Bold,
                hover_name="office",
                labels={
                    "managers": "Менеджеров в офисе",
                    "tickets": "Всего тикетов",
                    "mean_load": "Ср. нагрузка",
                },
                text="office",
            )
            fig.update_traces(textposition="top center")
            fig = plotly_dark_layout(fig, height=400)
            st.plotly_chart(fig, use_container_width=True)

        section_title("Таблица")
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
# СТРАНИЦА: КАРТА
# ─────────────────────────────────────────────

elif page == "🗺️ Карта":
    st.markdown('<div class="fire-header">Карта</div>', unsafe_allow_html=True)

    try:
        import folium
        from streamlit_folium import st_folium

        geo_tickets = fetch("/geo/tickets") or []
        geo_offices = fetch("/geo/offices") or []

        m = folium.Map(
            location=[48.0, 67.0],
            zoom_start=5,
            tiles="CartoDB dark_matter",
        )

        # Офисы
        for o in geo_offices:
            if o.get("lat") and o.get("lon"):
                folium.Marker(
                    [o["lat"], o["lon"]],
                    popup=f"<b>{o['name']}</b><br>{o.get('address', '')}",
                    tooltip=o["name"],
                    icon=folium.Icon(color="red", icon="building", prefix="fa"),
                ).add_to(m)

        # Тикеты
        color_map = {"NEG": "red", "NEU": "orange", "POS": "green"}
        for t in geo_tickets:
            if t.get("lat") and t.get("lon"):
                folium.CircleMarker(
                    [t["lat"], t["lon"]],
                    radius=6 if t.get("is_escalation") else 4,
                    color=color_map.get(t.get("sentiment", "NEU"), "orange"),
                    fill=True,
                    fill_opacity=0.7,
                    popup=f"<b>{t.get('ai_type')}</b><br>Офис: {t.get('office')}<br>Приоритет: {t.get('priority')}",
                    tooltip=f"{t.get('city')} — {t.get('ai_type')}",
                ).add_to(m)

        st_folium(m, width=None, height=600)

        st.markdown("""
        <div style="font-size:0.75rem;color:#888;margin-top:0.5rem;">
        🔴 Негатив &nbsp; 🟠 Нейтральный &nbsp; 🟢 Позитив &nbsp; | &nbsp; 📍 Офисы &nbsp; ⚡ Большой кружок = эскалация
        </div>
        """, unsafe_allow_html=True)

    except ImportError:
        st.warning("Для карты установите: `pip install folium streamlit-folium --break-system-packages`")
        # Fallback на Plotly scatter
        geo_offices = fetch("/geo/offices") or []
        if geo_offices:
            df_off = pd.DataFrame(geo_offices)
            fig = px.scatter_mapbox(
                df_off, lat="lat", lon="lon", text="name",
                hover_name="name", zoom=4,
                mapbox_style="carto-darkmatter",
            )
            fig.update_layout(height=500, paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────
# СТРАНИЦА: AI АНАЛИТИК
# ─────────────────────────────────────────────

elif page == "🤖 AI Аналитик":
    st.markdown('<div class="fire-header">AI Аналитик</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#888;margin-bottom:1.5rem;">Задайте вопрос по данным на русском языке</div>', unsafe_allow_html=True)

    # Инициализация истории чата
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "llm_history" not in st.session_state:
        st.session_state.llm_history = []

    # Быстрые вопросы
    section_title("Быстрые вопросы")
    suggested = [
        "Сколько всего тикетов и какой процент эскалаций?",
        "Какой офис обрабатывает больше всего обращений?",
        "Какие типы обращений встречаются чаще всего?",
        "Кто из менеджеров перегружен больше всего?",
        "Сколько тикетов с негативным сентиментом?",
        "В каком офисе больше всего эскалаций?",
    ]
    cols = st.columns(3)
    for i, q in enumerate(suggested):
        if cols[i % 3].button(q, key=f"sq_{i}", use_container_width=True):
            st.session_state._quick_question = q

    st.markdown("---")

    # Чат
    section_title("Чат с данными")

    # Отображение истории
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-user">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
            else:
                source_label = "🤖 LLM" if msg.get("source") == "llm" else "📊 Rule-based"
                st.markdown(
                    f'<div class="chat-bot">{msg["content"]}'
                    f'<br><span class="chat-source">{source_label}</span></div>',
                    unsafe_allow_html=True,
                )

    # Инпут
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Ваш вопрос",
            placeholder="Например: Сколько тикетов в Астане с негативным сентиментом?",
            label_visibility="collapsed",
        )
        send_col, clear_col = st.columns([4, 1])
        submitted = send_col.form_submit_button("Отправить →", use_container_width=True)
        cleared   = clear_col.form_submit_button("Очистить", use_container_width=True)

    # Обработка быстрого вопроса
    if hasattr(st.session_state, "_quick_question"):
        user_input = st.session_state._quick_question
        submitted = True
        del st.session_state._quick_question

    if cleared:
        st.session_state.chat_history = []
        st.session_state.llm_history  = []
        st.rerun()

    if submitted and user_input.strip():
        # Добавляем вопрос в историю
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Анализирую данные..."):
            result = post("/ai/chat", {
                "question": user_input,
                "history": st.session_state.llm_history[-6:],
            })

        answer = result.get("answer", "Нет ответа")
        source = result.get("source", "unknown")

        # Добавляем ответ в историю
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer,
            "source": source,
        })
        # История для LLM контекста
        st.session_state.llm_history.append({"role": "user", "content": user_input})
        st.session_state.llm_history.append({"role": "assistant", "content": answer})

        st.rerun()

    # Подсказка если нет истории
    if not st.session_state.chat_history:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#444;">
            <div style="font-size:3rem;margin-bottom:1rem;">🤖</div>
            <div style="font-size:1rem;">Задайте вопрос по данным выше<br>или выберите быстрый вопрос</div>
        </div>
        """, unsafe_allow_html=True)