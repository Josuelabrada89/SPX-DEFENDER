import json
import math
import os
import re
import tempfile
import uuid
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

import spx_defender as defender


st.set_page_config(page_title="SPX Defender", page_icon="🛡️", layout="wide")
TRADES_FILE = Path(defender.SCRIPT_DIR) / "operaciones_spx.json"
LIVE_MARKET_REFRESH_SECONDS = 5
TRADIER_BROKERAGE_URL = "https://api.tradier.com/v1"
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"
if st.session_state.get("tradier_connection_base_url") in {TRADIER_BROKERAGE_URL, TRADIER_SANDBOX_URL}:
    defender.BASE_URL = st.session_state["tradier_connection_base_url"]
CANDLE_INTERVAL_LABELS = {
    "1min": "1 minuto",
    "5min": "5 minutos",
    "15min": "15 minutos",
    "1h": "1 hora",
    "4h": "4 horas",
    "1d": "1 día",
}


def apply_defender_theme():
    st.markdown(
        """
        <style>
        :root {
            color-scheme: dark;
            --spx-background: #0a0f18;
            --spx-panel: #101722;
            --spx-panel-soft: #151e2b;
            --spx-border: #263142;
            --spx-text: #e9edf5;
            --spx-muted: #90a0b8;
            --spx-green: #21d19f;
            --spx-red: #ff6276;
            --spx-blue: #57a9ff;
        }
        .stApp, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(ellipse at 90% 0%, rgba(55, 111, 216, .09), transparent 34%),
                var(--spx-background);
            color: var(--spx-text);
        }
        [data-testid="stHeader"] { background: rgba(10, 15, 24, .94); }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #101722 0%, #0c121c 100%);
            border-right: 1px solid var(--spx-border);
        }
        [data-testid="stMainBlockContainer"] {
            padding-top: 2rem;
            padding-bottom: 2.5rem;
            max-width: 1650px;
        }
        h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] {
            color: var(--spx-text);
        }
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
            color: var(--spx-muted) !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            background: linear-gradient(180deg, rgba(20, 29, 42, .96), rgba(15, 22, 33, .98));
            border-color: var(--spx-border) !important;
            border-radius: 15px;
        }
        [data-testid="stMetric"] {
            background: rgba(18, 26, 38, .72);
            border: 1px solid rgba(54, 67, 87, .72);
            border-radius: 12px;
            padding: .72rem .85rem;
        }
        [data-testid="stMetricLabel"] p { color: var(--spx-muted) !important; }
        [data-testid="stMetricValue"] { color: var(--spx-text) !important; }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"],
        div[data-baseweb="base-input"] {
            background-color: #131c29 !important;
            border-color: #334054 !important;
            color: var(--spx-text) !important;
            border-radius: 9px !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--spx-border);
            border-radius: 11px;
            overflow: hidden;
        }
        .stButton > button {
            border: 1px solid #334155;
            border-radius: 10px;
            background: #172232;
            color: var(--spx-text);
            font-weight: 650;
            transition: all .15s ease;
        }
        .stButton > button:hover {
            background: #23334a;
            border-color: var(--spx-blue);
            color: #fff;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem;
            border-bottom: 1px solid var(--spx-border);
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            color: var(--spx-muted);
            border-radius: 8px 8px 0 0;
        }
        .stTabs [aria-selected="true"] {
            background: #192536 !important;
            color: #f4f7fc !important;
        }
        .builder-heading {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: .7rem;
            padding: .25rem 0 1.1rem;
        }
        .builder-heading h1 {
            font-size: 2rem;
            line-height: 1.08;
            letter-spacing: -.045em;
            margin: .25rem 0;
        }
        .builder-kicker {
            font-size: .74rem;
            font-weight: 750;
            letter-spacing: .14em;
            color: #71abff;
        }
        .builder-subtitle { color: #98a7bc; font-size: .9rem; }
        .market-pill {
            border: 1px solid #314359;
            background: #131d2b;
            color: #e8eef7;
            border-radius: 999px;
            padding: .58rem .93rem;
            font-size: .9rem;
        }
        .market-pill strong { color: #23d49f; }
        .strategy-stat {
            min-height: 104px;
            padding: .88rem .9rem .78rem;
            border-radius: 12px;
            border: 1px solid #293649;
            background: linear-gradient(145deg, #151e2b, #101722);
        }
        .strategy-stat-label {
            color: #9aabc1;
            font-size: .72rem;
            letter-spacing: .035em;
            text-transform: uppercase;
        }
        .strategy-stat-value {
            margin-top: .48rem;
            font-size: 1.38rem;
            line-height: 1.13;
            font-weight: 750;
            letter-spacing: -.04em;
        }
        .strategy-stat-note { color: #8394aa; font-size: .72rem; margin-top: .34rem; }
        .strategy-stat-green .strategy-stat-value { color: #2ee0a8; }
        .strategy-stat-red .strategy-stat-value { color: #ff7483; }
        .strategy-stat-blue .strategy-stat-value { color: #76b5ff; }
        .strategy-stat-neutral .strategy-stat-value { color: #eef3fb; }
        .leg-card {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: .69rem .76rem;
            margin: .42rem 0;
            border-radius: 9px;
            background: #111a27;
            border-left: 3px solid #718097;
        }
        .leg-card.call { border-left-color: #20ce98; }
        .leg-card.put { border-left-color: #ff6276; }
        .leg-main { color: #edf2fa; font-size: .83rem; font-weight: 670; }
        .leg-detail { color: #90a0b8; font-size: .73rem; }
        .leg-premium { text-align: right; font-weight: 720; color: #eaf0fa; }
        .sim-section-label {
            color: #91a2ba;
            font-size: .71rem;
            font-weight: 760;
            letter-spacing: .095em;
            text-transform: uppercase;
            margin: .7rem 0 .22rem;
        }
        .market-terminal-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: .8rem;
            padding: 1rem 1.08rem .84rem;
            border: 1px solid #27364a;
            border-bottom: 0;
            border-radius: 13px 13px 0 0;
            background: linear-gradient(135deg, #101a27 0%, #0c131e 100%);
        }
        .market-terminal-symbol {
            color: #eff5fd;
            font-size: 1.02rem;
            font-weight: 750;
            letter-spacing: .055em;
        }
        .market-terminal-meta {
            margin-top: .18rem;
            color: #899bb3;
            font-size: .73rem;
        }
        .market-terminal-price {
            color: #f2f6fd;
            font-size: 1.6rem;
            font-weight: 750;
            line-height: 1.05;
            text-align: right;
        }
        .market-terminal-change {
            margin-top: .22rem;
            font-size: .79rem;
            font-weight: 650;
            text-align: right;
        }
        .market-terminal-change.positive { color: #24dbad; }
        .market-terminal-change.negative { color: #ff687b; }
        .market-terminal-ohlc,
        .market-terminal-legend {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: .75rem;
            padding: .55rem 1.08rem;
            border-left: 1px solid #27364a;
            border-right: 1px solid #27364a;
            background: #0d1520;
        }
        .market-terminal-ohlc { border-top: 1px solid #202d3d; }
        .market-terminal-legend {
            padding-top: .28rem;
            padding-bottom: .65rem;
            border-bottom: 1px solid #202d3d;
        }
        .market-terminal-ohlc span,
        .market-terminal-legend span {
            color: #a9b7ca;
            font-size: .72rem;
            white-space: nowrap;
        }
        .market-terminal-ohlc strong { color: #eaf1fb; font-weight: 650; }
        .market-terminal-indicator {
            display: inline-flex;
            align-items: center;
            gap: .32rem;
        }
        .market-terminal-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_strategy_stat(label, value, note="", tone="neutral"):
    safe_tone = tone if tone in {"green", "red", "blue", "neutral"} else "neutral"
    st.markdown(
        f'<div class="strategy-stat strategy-stat-{safe_tone}">'
        f'<div class="strategy-stat-label">{escape(str(label))}</div>'
        f'<div class="strategy-stat-value">{escape(str(value))}</div>'
        f'<div class="strategy-stat-note">{escape(str(note))}</div></div>',
        unsafe_allow_html=True,
    )


def render_strategy_leg_cards(legs):
    cards = []
    for leg in legs:
        type_name = leg["type"].upper()
        action_name = "COMPRA" if leg["action"] == "COMPRAR" else "VENTA"
        cards.append(
            f'<div class="leg-card {escape(leg["type"])}">'
            f'<div><div class="leg-main">{action_name} {type_name} {leg["strike"]:,.2f}</div>'
            f'<div class="leg-detail">{leg["contracts"]} contrato(s) · '
            f'Δ {leg["delta"]:+.2f} · IV {leg["iv"] * 100:.1f}%</div></div>'
            f'<div class="leg-premium">${leg["premium"]:,.2f}</div></div>'
        )
    st.markdown("".join(cards), unsafe_allow_html=True)


apply_defender_theme()


def money(value):
    value = float(value or 0)
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


def compact(value):
    value = float(value or 0)
    for suffix, divisor in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= divisor:
            return f"{value / divisor:,.2f}{suffix}"
    return f"{value:,.0f}"


def expiration_name(expiration):
    return f"{expiration} — {defender.calculate_days_remaining(expiration)} días"


def selected_symbol():
    symbol = str(st.session_state.get("active_symbol", "SPX") or "SPX").strip().upper()
    if not re.fullmatch(r"[A-Z0-9./^_-]{1,16}", symbol):
        raise RuntimeError("El símbolo contiene caracteres que no son válidos.")
    return symbol


def nearest_strike(spx):
    price = float(spx)
    increment = 0.5 if price < 25 else 1 if price < 100 else 2.5 if price < 300 else 5
    return round(price / increment) * increment


def adaptive_strategy_settings(price):
    price = max(float(price), 0.5)
    step = 0.5 if price < 25 else 1.0 if price < 100 else 2.5 if price < 300 else 5.0
    widths = sorted({round(step * number, 2) for number in (1, 2, 3, 4, 5, 8, 10)})
    distances = sorted({0.0, *(round(step * number, 2) for number in (1, 2, 3, 4, 6, 8, 10, 15, 20, 30))})
    ranges = sorted({round(max(price * ratio, step * 4), 2) for ratio in (0.03, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35)})
    default_width = min(widths, key=lambda value: abs(value - step * 2))
    default_distance = min(distances, key=lambda value: abs(value - price * 0.045))
    default_range = min(ranges, key=lambda value: abs(value - price * 0.10))
    return {
        "step": step,
        "widths": widths,
        "distances": distances,
        "ranges": ranges,
        "default_width": default_width,
        "default_distance": default_distance,
        "default_range": default_range,
    }


def use_fragment(function, seconds=None):
    fragment = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    if callable(fragment):
        fragment(run_every=f"{seconds}s" if seconds else None)(function)()
        return

    function()
    if not seconds:
        return

    refresh_label = "🔄 Actualizar en vivo"
    st.button(refresh_label, key=f"automatic_refresh_{function.__name__}")
    try:
        import streamlit.components.v1 as legacy_components

        legacy_components.html(
            "<script>"
            "window.setTimeout(function () {"
            "const buttons = window.parent.document.querySelectorAll('button');"
            f"const label = {json.dumps(refresh_label, ensure_ascii=False)};"
            "const refresh = Array.from(buttons).find(button => button.textContent.trim() === label);"
            "if (refresh && !refresh.disabled) refresh.click();"
            f"}}, {max(int(float(seconds) * 1000), 1000)});"
            "</script>",
            height=0,
            scrolling=False,
        )
        st.caption(f"Actualización automática cada {seconds} segundos.")
    except Exception:
        st.caption("Utiliza el botón para actualizar o instala una versión reciente de Streamlit.")


@st.cache_resource
def get_client():
    session_token = str(st.session_state.get("tradier_connection_token") or "").strip()
    return defender.TradierClient(session_token or defender.load_token())


@st.cache_data(ttl=LIVE_MARKET_REFRESH_SECONDS, show_spinner=False)
def load_spx(symbol="SPX"):
    quote = load_spx_quote(symbol)
    for field in ("last", "close", "prevclose"):
        price = defender.number(quote.get(field))
        if price > 0:
            return price
    bid = defender.number(quote.get("bid"))
    ask = defender.number(quote.get("ask"))
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    raise RuntimeError(f"No se encontró un precio disponible para {symbol}.")


@st.cache_data(ttl=LIVE_MARKET_REFRESH_SECONDS, show_spinner=False)
def load_spx_quote(symbol="SPX"):
    response = get_client().get("/markets/quotes", {"symbols": symbol})
    quote = (response.get("quotes") or {}).get("quote")
    if isinstance(quote, list):
        quote = quote[0] if quote else None
    if not quote or str(quote.get("type") or "").lower() == "error":
        raise RuntimeError(f"Tradier no encontró una cotización para {symbol}.")
    return quote


@st.cache_data(ttl=600, show_spinner=False)
def load_expirations(symbol="SPX"):
    response = get_client().get(
        "/markets/options/expirations",
        {"symbol": symbol, "includeAllRoots": "true", "strikes": "false"},
    )
    dates = (response.get("expirations") or {}).get("date") or []
    if isinstance(dates, str):
        dates = [dates]
    valid = sorted(item for item in dates if str(item) >= date.today().isoformat())
    if not valid:
        raise RuntimeError(f"{symbol} no tiene vencimientos de opciones disponibles en Tradier.")
    return valid


@st.cache_data(ttl=55, show_spinner=False)
def load_chain(expiration, symbol="SPX"):
    response = get_client().get(
        "/markets/options/chains",
        {"symbol": symbol, "expiration": expiration, "greeks": "true"},
    )
    options = (response.get("options") or {}).get("option") or []
    if isinstance(options, dict):
        options = [options]
    if not options:
        raise RuntimeError(f"No se encontraron opciones de {symbol} para {expiration}.")
    return options


@st.cache_data(ttl=300, show_spinner=False)
def search_symbols(query):
    query = str(query or "").strip()
    if len(query) < 1:
        return []
    response = get_client().get("/markets/search", {"q": query, "indexes": "true"})
    securities = (response.get("securities") or {}).get("security") or []
    if isinstance(securities, dict):
        securities = [securities]
    results = []
    for item in securities:
        symbol = str(item.get("symbol") or "").strip().upper()
        kind = str(item.get("type") or "").lower()
        if symbol and kind in {"stock", "etf", "index", ""}:
            results.append(
                {"symbol": symbol, "description": str(item.get("description") or symbol), "type": kind}
            )
    return results[:18]


def aggregate_intraday_candles(candles, interval_minutes):
    frame = pd.DataFrame(candles)
    time_column = next((column for column in ("time", "timestamp", "date") if column in frame.columns), None)
    if time_column is None:
        raise RuntimeError("Las velas de Tradier no contienen una fecha válida.")

    frame["Hora"] = pd.to_datetime(frame[time_column], errors="coerce")
    for column in ("open", "high", "low", "close"):
        if column not in frame.columns:
            raise RuntimeError(f"Las velas de Tradier no contienen {column}.")
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "volume" not in frame.columns:
        frame["volume"] = 0
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0)
    frame = frame.dropna(subset=["Hora", "open", "high", "low", "close"]).sort_values("Hora")
    if frame.empty:
        return []

    frame["Sesión"] = frame["Hora"].dt.normalize()
    minutes_after_open = frame["Hora"].dt.hour * 60 + frame["Hora"].dt.minute - 9 * 60 - 30
    frame["Bloque"] = minutes_after_open.clip(lower=0).floordiv(interval_minutes)
    grouped = frame.groupby(["Sesión", "Bloque"], sort=True).agg(
        time=("Hora", "first"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    return [
        {
            "time": row.time.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": int(row.volume),
        }
        for row in grouped.itertuples(index=False)
    ]


def candle_date_range(candles):
    times = []
    for candle in candles:
        timestamp = candle.get("time") or candle.get("timestamp") or candle.get("date")
        parsed = pd.to_datetime(timestamp, errors="coerce")
        if pd.notna(parsed):
            times.append(parsed.strftime("%Y-%m-%d"))
    if not times:
        return str(date.today())
    first, last = min(times), max(times)
    return first if first == last else f"{first} — {last}"


def latest_quote_time(quote):
    if not isinstance(quote, dict):
        return None

    eastern = ZoneInfo("America/New_York")
    for field in ("trade_date", "trade_timestamp", "last_trade_time", "timestamp"):
        raw = quote.get(field)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            numeric = float(raw)
            magnitude = abs(numeric)
            if magnitude >= 1e17:
                numeric /= 1_000_000_000
            elif magnitude >= 1e14:
                numeric /= 1_000_000
            elif magnitude >= 1e11:
                numeric /= 1_000
            return datetime.fromtimestamp(numeric, tz=eastern)
        except (TypeError, ValueError, OverflowError, OSError):
            try:
                parsed = pd.to_datetime(raw, errors="coerce")
                if pd.isna(parsed):
                    continue
                if parsed.tzinfo is None:
                    return parsed.to_pydatetime().replace(tzinfo=eastern)
                return parsed.to_pydatetime().astimezone(eastern)
            except (TypeError, ValueError, OverflowError, AttributeError):
                continue
    return None


@st.cache_data(ttl=900, show_spinner=False)
def load_previous_intraday_candles(interval, symbol, session):
    session_date = date.fromisoformat(str(session))
    response = get_client().get(
        "/markets/timesales",
        {
            "symbol": symbol,
            "interval": interval,
            "start": f"{session_date - timedelta(days=7)} 09:30",
            "end": f"{session_date - timedelta(days=1)} 16:00",
            "session_filter": "open",
        },
    )
    candles = (response.get("series") or {}).get("data") or []
    if isinstance(candles, dict):
        candles = [candles]
    return candles[-240:]


def extend_intraday_chart_history(candles, interval, symbol, session):
    target = {"1min": 180, "5min": 150, "15min": 90}.get(interval, 150)
    current = list(candles or [])
    if len(current) >= target:
        return current[-target:]

    try:
        previous = load_previous_intraday_candles(interval, symbol, str(session))
    except Exception:
        return current

    unique = {}
    for candle in [*previous, *current]:
        timestamp = candle.get("time") or candle.get("timestamp") or candle.get("date")
        parsed = pd.to_datetime(timestamp, errors="coerce")
        if pd.isna(parsed):
            continue
        if parsed.tzinfo is not None:
            parsed = parsed.tz_convert("America/New_York").tz_localize(None)
        unique[parsed.isoformat()] = candle
    return [unique[key] for key in sorted(unique)][-target:]


@st.cache_data(ttl=LIVE_MARKET_REFRESH_SECONDS, show_spinner=False)
def load_candles(interval, requested_symbol="SPX"):
    client = get_client()
    last_error = None
    candidates = (requested_symbol, "SPY") if requested_symbol == "SPX" else (requested_symbol,)

    if interval == "1d":
        for symbol in candidates:
            try:
                response = client.get(
                    "/markets/history",
                    {
                        "symbol": symbol,
                        "interval": "daily",
                        "start": str(date.today() - timedelta(days=150)),
                        "end": str(date.today()),
                    },
                )
                candles = (response.get("history") or {}).get("day") or []
                if isinstance(candles, dict):
                    candles = [candles]
                candles = [
                    {**candle, "time": candle.get("time") or f"{candle.get('date')} 09:30"}
                    for candle in candles
                    if candle.get("date") or candle.get("time")
                ]
                if candles:
                    return {
                        "symbol": symbol,
                        "date": candle_date_range(candles),
                        "candles": candles,
                        "interval": interval,
                    }
            except Exception as error:
                last_error = str(error)
        raise RuntimeError(last_error or f"No hay velas diarias disponibles para {requested_symbol}.")

    if interval in {"1h", "4h"}:
        days_back = 12 if interval == "1h" else 32
        interval_minutes = 60 if interval == "1h" else 240
        for symbol in candidates:
            try:
                response = client.get(
                    "/markets/timesales",
                    {
                        "symbol": symbol,
                        "interval": "15min",
                        "start": f"{date.today() - timedelta(days=days_back)} 09:30",
                        "end": f"{date.today()} 16:00",
                        "session_filter": "open",
                    },
                )
                source = (response.get("series") or {}).get("data") or []
                if isinstance(source, dict):
                    source = [source]
                candles = aggregate_intraday_candles(source, interval_minutes) if source else []
                if candles:
                    return {
                        "symbol": symbol,
                        "date": candle_date_range(candles),
                        "candles": candles,
                        "interval": interval,
                    }
            except Exception as error:
                last_error = str(error)
        raise RuntimeError(last_error or f"No hay velas horarias disponibles para {requested_symbol}.")

    if interval not in {"1min", "5min", "15min"}:
        raise RuntimeError(f"La temporalidad {interval} no está disponible.")

    for days_back in range(5):
        session = date.today() - timedelta(days=days_back)
        if session.weekday() >= 5:
            continue
        for symbol in candidates:
            try:
                response = client.get(
                    "/markets/timesales",
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "start": f"{session} 09:30",
                        "end": f"{session} 16:00",
                        "session_filter": "open",
                    },
                )
                candles = (response.get("series") or {}).get("data") or []
                if isinstance(candles, dict):
                    candles = [candles]
                if candles:
                    candles = extend_intraday_chart_history(candles, interval, symbol, session)
                    return {
                        "symbol": symbol,
                        "date": candle_date_range(candles),
                        "candles": candles,
                        "interval": interval,
                    }
            except Exception as error:
                last_error = str(error)
    raise RuntimeError(last_error or f"No hay velas disponibles para {requested_symbol}.")


def update_live_candles(data, quote, now=None):
    candles = [dict(candle) for candle in data.get("candles", [])]
    updated = {**data, "candles": candles, "is_live": False}
    if not candles or not isinstance(quote, dict):
        return updated

    current_time = now or market_time()
    if current_time.tzinfo is not None:
        current_time = current_time.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
    market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
    if current_time.weekday() >= 5 or not market_open <= current_time < market_close:
        updated["live_status"] = "mercado_cerrado"
        return updated

    latest_price = 0.0
    for field in ("last", "close"):
        value = defender.number(quote.get(field))
        if value > 0:
            latest_price = float(value)
            break
    if latest_price <= 0:
        bid = defender.number(quote.get("bid"))
        ask = defender.number(quote.get("ask"))
        if bid > 0 and ask > 0:
            latest_price = float((bid + ask) / 2)
    if latest_price <= 0:
        return updated

    interval = str(data.get("interval") or "5min")
    interval_minutes = {
        "1min": 1,
        "5min": 5,
        "15min": 15,
        "1h": 60,
        "4h": 240,
        "1d": 390,
    }.get(interval)
    if interval_minutes is None:
        return updated

    quote_time = latest_quote_time(quote)
    effective_time = current_time
    if quote_time is not None:
        local_quote_time = quote_time.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
        quote_age = max(int((current_time - local_quote_time).total_seconds()), 0)
        updated["quote_updated_at"] = local_quote_time.strftime("%I:%M:%S %p")
        updated["quote_age_seconds"] = quote_age
        updated["quote_delayed"] = quote_age >= 90
        if market_open <= local_quote_time < market_close and local_quote_time <= current_time:
            effective_time = local_quote_time
        elif updated["quote_delayed"]:
            updated["live_status"] = "cotizacion_retrasada"
            updated["updated_at"] = current_time.strftime("%I:%M:%S %p")
            updated["live_price"] = latest_price
            return updated

    elapsed_minutes = int((effective_time - market_open).total_seconds() // 60)
    bucket_start = market_open + timedelta(minutes=(elapsed_minutes // interval_minutes) * interval_minutes)
    bucket_end = bucket_start + timedelta(minutes=interval_minutes)
    latest = candles[-1]
    timestamp = latest.get("time") or latest.get("timestamp") or latest.get("date")
    latest_time = pd.to_datetime(timestamp, errors="coerce")
    if pd.isna(latest_time):
        return updated
    if latest_time.tzinfo is not None:
        latest_time = latest_time.tz_convert("America/New_York").tz_localize(None)
    latest_time = latest_time.to_pydatetime()

    quote_open = defender.number(quote.get("open"))
    quote_high = defender.number(quote.get("high"))
    quote_low = defender.number(quote.get("low"))
    quote_volume = defender.integer(quote.get("volume"))
    same_bucket = bucket_start <= latest_time < bucket_end

    if same_bucket:
        latest["close"] = latest_price
        latest["high"] = max(defender.number(latest.get("high")), latest_price)
        previous_low = defender.number(latest.get("low"))
        latest["low"] = min(previous_low, latest_price) if previous_low > 0 else latest_price
        if interval == "1d":
            if quote_open > 0:
                latest["open"] = float(quote_open)
            if quote_high > 0:
                latest["high"] = max(float(latest["high"]), float(quote_high))
            if quote_low > 0:
                latest["low"] = min(float(latest["low"]), float(quote_low))
            if quote_volume > 0:
                latest["volume"] = quote_volume
    elif latest_time < bucket_start:
        previous_close = defender.number(latest.get("close"))
        opening_price = float(quote_open) if latest_time.date() != bucket_start.date() and quote_open > 0 else float(previous_close or latest_price)
        new_candle = {
            "time": bucket_start.strftime("%Y-%m-%d %H:%M:%S"),
            "open": opening_price,
            "high": max(opening_price, latest_price),
            "low": min(opening_price, latest_price),
            "close": latest_price,
            "volume": 0,
        }
        if interval == "1d":
            if quote_high > 0:
                new_candle["high"] = max(new_candle["high"], float(quote_high))
            if quote_low > 0:
                new_candle["low"] = min(new_candle["low"], float(quote_low))
            if quote_volume > 0:
                new_candle["volume"] = quote_volume
        candles.append(new_candle)
        updated["date"] = candle_date_range(candles)
    else:
        return updated

    updated["is_live"] = True
    updated["live_status"] = "cotizacion_retrasada" if updated.get("quote_delayed") else "actualizando"
    updated["updated_at"] = current_time.strftime("%I:%M:%S %p")
    updated["live_price"] = latest_price
    return updated


class SymbolTradierClient:
    def __init__(self, symbol):
        self.symbol = symbol

    def option_chain(self, expiration):
        return load_chain(expiration, self.symbol)


def clear_data():
    load_spx.clear()
    load_spx_quote.clear()
    load_expirations.clear()
    load_chain.clear()
    load_candles.clear()
    load_previous_intraday_candles.clear()
    search_symbols.clear()
    get_client().chain_cache.clear()


def change_tradier_connection(base_url, token=None):
    if base_url not in {TRADIER_BROKERAGE_URL, TRADIER_SANDBOX_URL}:
        raise RuntimeError("La conexión de Tradier seleccionada no es válida.")
    if base_url == TRADIER_BROKERAGE_URL and not str(token or "").strip():
        raise RuntimeError("Ingresa el API token de tu cuenta real de Tradier.")

    clear_data()
    get_client.clear()
    st.session_state["tradier_connection_base_url"] = base_url
    if base_url == TRADIER_BROKERAGE_URL:
        st.session_state["tradier_connection_token"] = str(token).strip()
    else:
        st.session_state.pop("tradier_connection_token", None)
    defender.BASE_URL = base_url
    st.rerun()


def read_trades():
    if not TRADES_FILE.exists():
        return []
    try:
        with TRADES_FILE.open("r", encoding="utf-8") as source:
            trades = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudieron leer tus operaciones guardadas: {error}") from error
    if not isinstance(trades, list):
        raise RuntimeError("El archivo de operaciones tiene un formato inesperado.")
    return trades


def write_trades(trades):
    temporary_name = None
    try:
        TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            with TRADES_FILE.open("w", encoding="utf-8") as destination:
                json.dump(trades, destination, ensure_ascii=False, indent=2)
                destination.flush()
                os.fsync(destination.fileno())
            return

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(TRADES_FILE.parent), delete=False
        ) as temporary:
            temporary_name = temporary.name
            json.dump(trades, temporary, ensure_ascii=False, indent=2)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, TRADES_FILE)
    except OSError as error:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
        raise RuntimeError(f"No se pudieron guardar las operaciones: {error}") from error


def validate_position(strategy, short_strike, long_strike, credit, contracts):
    if short_strike <= 0 or long_strike <= 0:
        raise RuntimeError("Los strikes deben ser superiores a cero.")
    if strategy == "PCS" and long_strike >= short_strike:
        raise RuntimeError("En un PCS, el strike comprado debe ser menor que el vendido.")
    if strategy == "CCS" and long_strike <= short_strike:
        raise RuntimeError("En un CCS, el strike comprado debe ser mayor que el vendido.")
    width = abs(short_strike - long_strike)
    if credit <= 0 or credit >= width:
        raise RuntimeError("El crédito debe ser mayor que cero y menor que el ancho del spread.")
    return {
        "strategy": strategy,
        "option_type": "put" if strategy == "PCS" else "call",
        "short_strike": float(short_strike),
        "long_strike": float(long_strike),
        "credit": float(credit),
        "contracts": int(contracts),
        "width": float(width),
    }


def save_trade(position, expiration, source="manual", symbol=None, market_context=None):
    trades = read_trades()
    trade = dict(position)
    trade.update(
        {
            "id": uuid.uuid4().hex,
            "expiration": expiration,
            "symbol": str(symbol or position.get("symbol") or selected_symbol()).upper(),
            "status": "OPEN",
            "source": source,
            "opened_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    trade["initial_snapshot"] = build_trade_snapshot(trade, market_context)
    trades.append(trade)
    write_trades(trades)
    return trade


def close_trade(trade_id, close_value):
    trades = read_trades()
    for trade in trades:
        if trade.get("id") == trade_id and trade.get("status") == "OPEN":
            trade["status"] = "CLOSED"
            trade["closed_at"] = datetime.now().isoformat(timespec="seconds")
            trade["close_price"] = float(close_value)
            trade["realized_pnl"] = (
                (float(trade["credit"]) - float(close_value))
                * int(trade["contracts"])
                * defender.CONTRACT_MULTIPLIER
            )
            write_trades(trades)
            return
    raise RuntimeError("La operación ya estaba cerrada o no se encontró.")


def remove_trade(trade_id):
    trades = read_trades()
    remaining = [trade for trade in trades if trade.get("id") != trade_id]
    if len(remaining) == len(trades):
        raise RuntimeError("No se encontró la operación que quieres eliminar.")
    write_trades(remaining)


def request_trade_removal(trade_id, scope):
    st.session_state[f"confirm_remove_trade_{scope}_{trade_id}"] = True


def render_trade_removal_confirmation(trade, scope):
    trade_id = str(trade.get("id") or "")
    confirmation_key = f"confirm_remove_trade_{scope}_{trade_id}"
    if not trade_id or not st.session_state.get(confirmation_key):
        return

    description = (
        f"{trade.get('symbol', 'SPX')} · {trade.get('strategy', '')} "
        f"{float(trade.get('short_strike') or 0):,.2f}/{float(trade.get('long_strike') or 0):,.2f}"
    )
    st.warning(
        f"¿De verdad quieres eliminar {description}? Se sacará por completo de la lista "
        "y esta acción no se puede deshacer."
    )
    confirm_column, cancel_column, _ = st.columns([1.25, 1, 3])
    if confirm_column.button(
        "Sí, eliminar",
        key=f"remove_trade_yes_{scope}_{trade_id}",
        use_container_width=True,
    ):
        try:
            remove_trade(trade_id)
            st.session_state.pop(confirmation_key, None)
            st.rerun()
        except Exception as error:
            st.error(str(error))
    if cancel_column.button(
        "Cancelar",
        key=f"remove_trade_no_{scope}_{trade_id}",
        use_container_width=True,
    ):
        st.session_state.pop(confirmation_key, None)
        st.rerun()


def market_time():
    try:
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now()


def option_implied_volatility(option):
    greeks = option.get("greeks") or {}
    for source in (greeks, option):
        for field in ("mid_iv", "smv_vol", "iv", "implied_volatility", "ask_iv", "bid_iv"):
            value = defender.number(source.get(field))
            if value <= 0:
                continue
            if value > 3:
                value /= 100
            if 0.005 <= value <= 3:
                return value
    return None


def years_to_expiration(expiration):
    dte = defender.calculate_days_remaining(expiration) or 0
    if dte > 0:
        return dte / 365
    now = market_time()
    close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    remaining_minutes = max((close - now).total_seconds() / 60, 1)
    return min(remaining_minutes / 390, 1) / 252


def estimate_gamma_flip(options, spx, expiration, fallback_iv, strike_range):
    years = years_to_expiration(expiration)
    if years <= 0:
        return None

    terms = []
    for option in options:
        strike = defender.number(option.get("strike"))
        option_type = str(option.get("option_type") or "").lower()
        oi = defender.integer(option.get("open_interest"))
        volatility = option_implied_volatility(option) or fallback_iv
        if (
            strike <= 0
            or abs(strike - spx) > strike_range
            or option_type not in ("call", "put")
            or oi <= 0
            or not volatility
        ):
            continue
        terms.append((strike, volatility, oi, 1 if option_type == "call" else -1))

    if not terms:
        return None

    root_time = math.sqrt(years)
    normalizer = math.sqrt(2 * math.pi)

    def net_gamma_at(price):
        total = 0.0
        for strike, volatility, oi, sign in terms:
            denominator = volatility * root_time
            d1 = (math.log(price / strike) + 0.5 * volatility**2 * years) / denominator
            density = math.exp(-0.5 * d1**2) / normalizer
            gamma = density / (price * denominator)
            total += sign * gamma * oi * defender.CONTRACT_MULTIPLIER * price**2 * 0.01
        return total

    radius = min(max(strike_range, 100), 400)
    step = max(5, radius / 45)
    previous_price = max(spx - radius, 1)
    previous_value = net_gamma_at(previous_price)
    roots = []
    current_price = previous_price + step

    while current_price <= spx + radius:
        current_value = net_gamma_at(current_price)
        if current_value == 0:
            roots.append(current_price)
        elif previous_value * current_value < 0:
            fraction = abs(previous_value) / (abs(previous_value) + abs(current_value))
            roots.append(previous_price + fraction * (current_price - previous_price))
        previous_price, previous_value = current_price, current_value
        current_price += step

    return min(roots, key=lambda value: abs(value - spx)) if roots else None


def calculate_expected_levels(options, spx, expiration, frame, strike_range=150):
    index = defender.build_option_index(options)
    paired_strikes = sorted(
        {
            strike
            for option_type, strike in index
            if option_type == "call" and ("put", strike) in index
        },
        key=lambda strike: abs(strike - spx),
    )
    if not paired_strikes:
        return {
            "atm_strike": None,
            "atm_iv": None,
            "straddle_price": None,
            "daily_move": None,
            "daily_lower": None,
            "daily_upper": None,
            "expiry_move": None,
            "expiry_lower": None,
            "expiry_upper": None,
            "gamma_magnet": None,
            "gamma_flip": None,
            "method": "No disponible",
        }

    atm_strike = paired_strikes[0]
    atm_call = defender.get_option(index, "call", atm_strike)
    atm_put = defender.get_option(index, "put", atm_strike)
    straddle_price = defender.option_midpoint(atm_call) + defender.option_midpoint(atm_put)
    iv_values = [value for value in (option_implied_volatility(atm_call), option_implied_volatility(atm_put)) if value]
    atm_iv = sum(iv_values) / len(iv_values) if iv_values else None
    dte = defender.calculate_days_remaining(expiration) or 0

    if atm_iv:
        daily_move = spx * atm_iv / math.sqrt(252)
        expiry_move = spx * atm_iv * math.sqrt(years_to_expiration(expiration))
        method = "Volatilidad implícita ATM · estimación de 1 desviación estándar"
    elif straddle_price > 0:
        expiry_move = straddle_price
        daily_move = straddle_price / math.sqrt(max(dte, 1))
        method = "Straddle ATM · aproximación, no equivale necesariamente a 1 desviación estándar"
    else:
        daily_move = None
        expiry_move = None
        method = "No disponible"

    try:
        quote = load_spx_quote(selected_symbol())
        daily_anchor = defender.number(quote.get("prevclose")) or spx
    except Exception:
        daily_anchor = spx

    gamma_magnet = None
    if "GEX" in frame.columns and frame["GEX"].abs().sum() > 0:
        profile = frame.assign(GEX_ABS=frame["GEX"].abs()).groupby("Strike", as_index=False)["GEX_ABS"].sum()
        gamma_magnet = float(profile.loc[profile["GEX_ABS"].idxmax(), "Strike"])

    gamma_flip = estimate_gamma_flip(options, spx, expiration, atm_iv, strike_range) if atm_iv else None

    return {
        "atm_strike": float(atm_strike),
        "atm_iv": atm_iv,
        "straddle_price": straddle_price,
        "daily_anchor": daily_anchor,
        "daily_move": daily_move,
        "daily_lower": daily_anchor - daily_move if daily_move is not None else None,
        "daily_upper": daily_anchor + daily_move if daily_move is not None else None,
        "expiry_move": expiry_move,
        "expiry_lower": spx - expiry_move if expiry_move is not None else None,
        "expiry_upper": spx + expiry_move if expiry_move is not None else None,
        "gamma_magnet": gamma_magnet,
        "gamma_flip": gamma_flip,
        "method": method,
    }


def summarize_chain(options, spx, strike_range=150):
    rows = []
    has_greeks = False
    for option in options:
        strike = defender.number(option.get("strike"), default=-1)
        option_type = str(option.get("option_type") or "").lower()
        if strike <= 0 or abs(strike - spx) > strike_range or option_type not in ("put", "call"):
            continue
        greeks = option.get("greeks") or {}
        has_greeks = has_greeks or greeks.get("gamma") is not None or greeks.get("delta") is not None
        gamma = defender.number(greeks.get("gamma"))
        oi = defender.integer(option.get("open_interest"))
        gex = gamma * oi * defender.CONTRACT_MULTIPLIER * spx**2 * 0.01
        midpoint = defender.option_midpoint(option)
        if midpoint <= 0:
            midpoint = defender.number(option.get("last"))
        midpoint = max(float(midpoint or 0), 0.0)
        rows.append(
            {
                "Strike": strike,
                "Tipo": option_type.upper(),
                "Open interest": oi,
                "Volumen": defender.integer(option.get("volume")),
                "Delta": defender.number(greeks.get("delta")),
                "Gamma": gamma,
                "GEX": -gex if option_type == "put" else gex,
                "Bid": defender.number(option.get("bid")),
                "Ask": defender.number(option.get("ask")),
                "Prima media": round(midpoint, 4),
                "Valor abierto $": round(midpoint * oi * defender.CONTRACT_MULTIPLIER, 2),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("No hay opciones disponibles dentro del rango seleccionado.")

    calls = frame[frame["Tipo"] == "CALL"]
    puts = frame[frame["Tipo"] == "PUT"]
    call_candidates = calls[calls["Strike"] >= spx]
    put_candidates = puts[puts["Strike"] <= spx]
    if call_candidates.empty:
        call_candidates = calls
    if put_candidates.empty:
        put_candidates = puts

    def wall(candidates):
        if candidates.empty or candidates["Open interest"].max() <= 0:
            return None
        return float(candidates.loc[candidates["Open interest"].idxmax(), "Strike"])

    mvs_profile = frame.groupby("Strike", as_index=False).agg(
        valor_abierto=("Valor abierto $", "sum"),
        open_interest=("Open interest", "sum"),
        volumen=("Volumen", "sum"),
    )
    mvs_profile["distancia"] = (mvs_profile["Strike"] - spx).abs()
    total_open_value = float(mvs_profile["valor_abierto"].sum())
    if total_open_value > 0:
        ranking = mvs_profile.sort_values(
            ["valor_abierto", "open_interest", "distancia"],
            ascending=[False, False, True],
        )
        mvs_method = "prima_abierta"
    elif int(mvs_profile["open_interest"].sum()) > 0:
        ranking = mvs_profile.sort_values(
            ["open_interest", "volumen", "distancia"],
            ascending=[False, False, True],
        )
        mvs_method = "open_interest"
    else:
        ranking = mvs_profile.iloc[0:0]
        mvs_method = "no_disponible"
    mvs_row = ranking.iloc[0] if not ranking.empty else None

    return {
        "frame": frame,
        "has_greeks": has_greeks,
        "put_wall": wall(put_candidates),
        "call_wall": wall(call_candidates),
        "mvs": float(mvs_row["Strike"]) if mvs_row is not None else None,
        "mvs_notional": float(mvs_row["valor_abierto"]) if mvs_row is not None else None,
        "mvs_oi": int(mvs_row["open_interest"]) if mvs_row is not None else 0,
        "mvs_volume": int(mvs_row["volumen"]) if mvs_row is not None else 0,
        "mvs_share": float(mvs_row["valor_abierto"]) / total_open_value if mvs_row is not None and total_open_value else None,
        "mvs_method": mvs_method,
        "gamma_levels": defender.calculate_gamma_levels(options, spx),
        "put_oi": int(puts["Open interest"].sum()),
        "call_oi": int(calls["Open interest"].sum()),
    }


def render_market_chart_header(data, frame, settings, has_vwap=False, mvs=None):
    latest = frame.iloc[-1]
    latest_session = frame["Hora"].dt.normalize() == latest["Hora"].normalize()
    if data.get("interval") == "1d" and len(frame) > 1:
        reference = float(frame.iloc[-2]["close"])
    else:
        reference = float(frame.loc[latest_session].iloc[0]["open"])
    change = float(latest["close"]) - reference
    percent = change / reference * 100 if reference else 0.0
    direction = "positive" if change >= 0 else "negative"
    symbol = escape(str(data.get("symbol") or "—"))
    interval_name = escape(CANDLE_INTERVAL_LABELS.get(data.get("interval"), str(data.get("interval") or "")))
    period = escape(str(data.get("date") or ""))

    indicators = []
    if settings.get("ema9"):
        indicators.append(("#f3bd62", f"EMA 9 · {float(latest['EMA 9']):,.2f}"))
    if settings.get("ema21"):
        indicators.append(("#5aa9ff", f"EMA 21 · {float(latest['EMA 21']):,.2f}"))
    if settings.get("vwap") and has_vwap:
        valid_vwap = frame["VWAP"].dropna()
        if not valid_vwap.empty:
            indicators.append(("#d58cff", f"VWAP · {float(valid_vwap.iloc[-1]):,.2f}"))
    if settings.get("levels") and mvs is not None and data.get("symbol") == selected_symbol():
        indicators.append(("#fb923c", f"MVS · {float(mvs):,.2f}"))
    indicator_html = "".join(
        '<span class="market-terminal-indicator">'
        f'<i class="market-terminal-dot" style="background:{color}"></i>{escape(label)}</span>'
        for color, label in indicators
    )

    st.markdown(
        '<div class="market-terminal-header">'
        f'<div><div class="market-terminal-symbol">{symbol} · MERCADO</div>'
        f'<div class="market-terminal-meta">{interval_name} · {period} · Tradier</div></div>'
        f'<div><div class="market-terminal-price">{float(latest["close"]):,.2f}</div>'
        f'<div class="market-terminal-change {direction}">{change:+,.2f} ({percent:+.2f}%)</div></div></div>'
        '<div class="market-terminal-ohlc">'
        f'<span>O <strong>{float(latest["open"]):,.2f}</strong></span>'
        f'<span>H <strong>{float(latest["high"]):,.2f}</strong></span>'
        f'<span>L <strong>{float(latest["low"]):,.2f}</strong></span>'
        f'<span>C <strong>{float(latest["close"]):,.2f}</strong></span>'
        f'<span>Vol <strong>{compact(latest["volume"]) if latest["volume"] > 0 else "N/D"}</strong></span>'
        '</div>'
        f'<div class="market-terminal-legend">{indicator_html}</div>',
        unsafe_allow_html=True,
    )


def show_candles(data, put_wall, call_wall, expected=None, spx=None, mvs=None, settings=None):
    settings = {
        "ema9": True,
        "ema21": True,
        "vwap": True,
        "volume": True,
        "levels": True,
        "expected_range": True,
        "visible_candles": 80,
        **(settings or {}),
    }
    frame = pd.DataFrame(data["candles"])
    time_column = next((column for column in ("time", "timestamp", "date") if column in frame.columns), None)
    if time_column is None:
        raise RuntimeError("Las velas no contienen un campo de hora.")
    frame["Hora"] = pd.to_datetime(frame[time_column], errors="coerce")
    for column in ("open", "high", "low", "close"):
        if column not in frame.columns:
            raise RuntimeError(f"Las velas no contienen {column}.")
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "volume" not in frame.columns:
        frame["volume"] = 0
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).clip(lower=0)
    frame = frame.dropna(subset=["Hora", "open", "high", "low", "close"]).sort_values("Hora").reset_index(drop=True)
    if frame.empty:
        raise RuntimeError("No hay velas válidas para el gráfico.")

    selected_interval = data.get("interval")
    is_daily = selected_interval == "1d"
    frame["EMA 9"] = frame["close"].ewm(span=9, adjust=False).mean()
    frame["EMA 21"] = frame["close"].ewm(span=21, adjust=False).mean()
    frame["Sesión"] = frame["Hora"].dt.strftime("%Y-%m-%d")
    has_volume = bool((frame["volume"] > 0).any())
    if has_volume:
        typical_price = (frame["high"] + frame["low"] + frame["close"]) / 3
        weighted_price = typical_price * frame["volume"]
        if is_daily:
            cumulative_price = weighted_price.cumsum()
            cumulative_volume = frame["volume"].cumsum()
        else:
            cumulative_price = weighted_price.groupby(frame["Sesión"]).cumsum()
            cumulative_volume = frame["volume"].groupby(frame["Sesión"]).cumsum()
        frame["VWAP"] = cumulative_price / cumulative_volume.where(cumulative_volume > 0)
    else:
        frame["VWAP"] = float("nan")

    visible_count = max(min(defender.integer(settings.get("visible_candles", 80)), 240), 25)
    frame = frame.tail(visible_count).copy().reset_index(drop=True)
    frame["Posición"] = range(len(frame))
    spans_several_sessions = frame["Hora"].dt.normalize().nunique() > 1
    axis_format = "%d %b" if is_daily else "%d %b %H:%M" if spans_several_sessions else "%H:%M"
    tooltip_format = "%d %b %Y" if is_daily else "%d %b %Y · %H:%M"
    axis_title = "Fecha" if is_daily else "Fecha y hora" if spans_several_sessions else "Hora"
    candle_size = max(4, min(17, int(760 / max(len(frame), 1) * 0.72)))

    visible_low = float(frame["low"].min())
    visible_high = float(frame["high"].max())
    latest_close = float(frame.iloc[-1]["close"])
    movement = max(visible_high - visible_low, latest_close * 0.0007, 0.05)
    price_padding = max(movement * 0.16, latest_close * 0.00035, 0.025)
    price_domain = [max(visible_low - price_padding, 0.0), visible_high + price_padding]
    minimum_body = max((price_domain[1] - price_domain[0]) * 0.002, 0.002)
    frame["Cuerpo inferior"] = frame[["open", "close"]].min(axis=1)
    frame["Cuerpo superior"] = frame[["open", "close"]].max(axis=1)
    flat_bodies = (frame["Cuerpo superior"] - frame["Cuerpo inferior"]) < minimum_body
    frame.loc[flat_bodies, "Cuerpo inferior"] -= minimum_body / 2
    frame.loc[flat_bodies, "Cuerpo superior"] += minimum_body / 2

    tick_step = max(math.ceil(len(frame) / 7), 1)
    tick_positions = sorted({0, len(frame) - 1, *range(0, len(frame), tick_step)})
    axis_label_expression = " : ".join(
        f"datum.value === {position} ? {json.dumps(frame.iloc[position]['Hora'].strftime(axis_format), ensure_ascii=False)}"
        for position in tick_positions
    ) + " : ''"
    time_domain = [-1, len(frame) + 2]
    has_vwap = bool(frame["VWAP"].notna().any())
    show_volume = bool(settings["volume"] and has_volume)

    render_market_chart_header(data, frame, settings, has_vwap=has_vwap, mvs=mvs)

    price_axis = alt.Axis(
        values=tick_positions,
        labelExpr=axis_label_expression,
        labelAngle=0,
        labels=not show_volume,
        ticks=not show_volume,
        domain=not show_volume,
        title=None if show_volume else axis_title,
    )
    price_x = alt.X(
        "Posición:Q",
        title=None if show_volume else axis_title,
        scale=alt.Scale(domain=time_domain, nice=False, zero=False),
        axis=price_axis,
    )
    tooltips = [
        alt.Tooltip("Hora:T", title="Fecha" if is_daily else "Fecha y hora", format=tooltip_format),
        alt.Tooltip("open:Q", title="Apertura", format=",.2f"),
        alt.Tooltip("high:Q", title="Máximo", format=",.2f"),
        alt.Tooltip("low:Q", title="Mínimo", format=",.2f"),
        alt.Tooltip("close:Q", title="Cierre", format=",.2f"),
    ]
    if has_volume:
        tooltips.append(alt.Tooltip("volume:Q", title="Volumen", format=","))

    base = alt.Chart(frame).encode(
        x=price_x,
        color=alt.condition("datum.open <= datum.close", alt.value("#20d4a7"), alt.value("#ff6178")),
        tooltip=tooltips,
    )
    wick = base.mark_rule(strokeWidth=1.35, clip=True).encode(
        y=alt.Y(
            "low:Q",
            title="Precio",
            scale=alt.Scale(domain=price_domain, nice=False, zero=False),
            axis=alt.Axis(orient="right", format=",.2f", tickCount=8),
        ),
        y2="high:Q",
    )
    body = base.mark_bar(size=candle_size, clip=True).encode(y="Cuerpo inferior:Q", y2="Cuerpo superior:Q")
    chart = wick + body

    if spans_several_sessions and not is_daily:
        session_starts = frame.loc[frame["Sesión"].ne(frame["Sesión"].shift())].iloc[1:]
        if not session_starts.empty:
            separators = alt.Chart(session_starts).mark_rule(
                color="#536176", strokeDash=[3, 6], opacity=0.52, clip=True
            ).encode(x="Posición:Q")
            chart += separators

    if settings["ema9"]:
        ema_nine = alt.Chart(frame).mark_line(color="#f3bd62", strokeWidth=1.8, clip=True).encode(
            x=price_x,
            y="EMA 9:Q",
            tooltip=[alt.Tooltip("EMA 9:Q", title="EMA 9", format=",.2f")],
        )
        chart += ema_nine
    if settings["ema21"]:
        ema_twenty_one = alt.Chart(frame).mark_line(color="#5aa9ff", strokeWidth=1.8, clip=True).encode(
            x=price_x,
            y="EMA 21:Q",
            tooltip=[alt.Tooltip("EMA 21:Q", title="EMA 21", format=",.2f")],
        )
        chart += ema_twenty_one
    if settings["vwap"] and has_vwap:
        vwap = alt.Chart(frame.dropna(subset=["VWAP"])).mark_line(
            color="#d58cff", strokeWidth=2.1, strokeDash=[6, 3], clip=True
        ).encode(
            x=price_x,
            y="VWAP:Q",
            tooltip=[alt.Tooltip("VWAP:Q", title="VWAP", format=",.2f")],
        )
        if not is_daily:
            vwap = vwap.encode(detail="Sesión:N")
        chart += vwap

    if data["symbol"] == selected_symbol() and settings["levels"]:
        levels = []
        if put_wall is not None:
            levels.append({"Nivel": put_wall, "Nombre": "Put wall", "Color": "#22c55e"})
        if call_wall is not None:
            levels.append({"Nivel": call_wall, "Nombre": "Call wall", "Color": "#ef4444"})
        if mvs is not None:
            levels.append({"Nivel": mvs, "Nombre": "MVS · Most Valuable Strike", "Color": "#fb923c"})
        if spx is not None:
            levels.append({"Nivel": spx, "Nombre": f"{selected_symbol()} actual", "Color": "#38bdf8"})
        if expected:
            expected_fields = [
                ("gamma_magnet", "Imán gamma", "#facc15"),
                ("gamma_flip", "Gamma flip estimado", "#c084fc"),
            ]
            if settings["expected_range"]:
                expected_fields.extend(
                    [
                        ("daily_lower", "Movimiento esperado inferior", "#86efac"),
                        ("daily_upper", "Movimiento esperado superior", "#fca5a5"),
                    ]
                )
            for field, label, color in expected_fields:
                value = expected.get(field)
                if value is not None:
                    levels.append({"Nivel": value, "Nombre": label, "Color": color})
            lower = expected.get("daily_lower")
            upper = expected.get("daily_upper")
            if settings["expected_range"] and lower is not None and upper is not None:
                bounded_lower = max(float(lower), price_domain[0])
                bounded_upper = min(float(upper), price_domain[1])
                if bounded_lower < bounded_upper:
                    band_frame = pd.DataFrame(
                        {
                            "Posición": [0, len(frame) - 1],
                            "Inferior": [bounded_lower, bounded_lower],
                            "Superior": [bounded_upper, bounded_upper],
                        }
                    )
                    expected_band = alt.Chart(band_frame).mark_area(
                        color="#63a8ff", opacity=0.065, clip=True
                    ).encode(
                        x=price_x,
                        y="Inferior:Q",
                        y2="Superior:Q",
                    )
                    chart = expected_band + chart
        if levels:
            visible_levels = [level for level in levels if price_domain[0] <= float(level["Nivel"]) <= price_domain[1]]
            if visible_levels:
                level_frame = pd.DataFrame(visible_levels)
                level_frame["Posición"] = max(len(frame) - 1, 0)
                level_frame["Etiqueta"] = level_frame.apply(
                    lambda row: f"{row['Nombre']} · {float(row['Nivel']):,.2f}", axis=1
                )
                lines = alt.Chart(level_frame).mark_rule(
                    strokeDash=[7, 5], strokeWidth=1.4, opacity=0.8, clip=True
                ).encode(
                    y="Nivel:Q",
                    color=alt.Color("Color:N", scale=None),
                    tooltip=["Nombre:N", alt.Tooltip("Nivel:Q", format=",.2f")],
                )
                labels = alt.Chart(level_frame).mark_text(
                    align="right", dx=-7, dy=-8, fontSize=10, fontWeight=600, clip=True
                ).encode(
                    x="Posición:Q",
                    y="Nivel:Q",
                    text="Etiqueta:N",
                    color=alt.Color("Color:N", scale=None),
                )
                chart += lines + labels

    last_candle = frame.iloc[-1]
    last_color = "#20d4a7" if float(last_candle["close"]) >= float(last_candle["open"]) else "#ff6178"
    current_price_frame = pd.DataFrame(
        {
            "Posición": [int(last_candle["Posición"])],
            "Precio actual": [float(last_candle["close"])],
            "Etiqueta": [f"{float(last_candle['close']):,.2f}"],
        }
    )
    current_price_line = alt.Chart(current_price_frame).mark_rule(
        color=last_color, strokeDash=[4, 4], strokeWidth=1, opacity=0.7, clip=True
    ).encode(y="Precio actual:Q")
    current_price_label = alt.Chart(current_price_frame).mark_text(
        align="left", dx=9, dy=-7, color=last_color, fontSize=11, fontWeight=600, clip=True
    ).encode(x="Posición:Q", y="Precio actual:Q", text="Etiqueta:N")
    chart += current_price_line + current_price_label

    selection_factory = getattr(alt, "selection_point", None)
    if callable(selection_factory):
        hover = selection_factory(
            nearest=True,
            on="pointermove",
            fields=["Posición"],
            empty=False,
            clear="pointerout",
        )
        selectors = alt.Chart(frame).mark_point(opacity=0, size=100).encode(
            x=price_x,
            y="close:Q",
        ).add_params(hover)
        vertical_guide = alt.Chart(frame).mark_rule(
            color="#8da3bf", strokeDash=[4, 4], opacity=0.7
        ).encode(x=price_x).transform_filter(hover)
        current_point = alt.Chart(frame).mark_point(
            filled=True,
            color="#eff6ff",
            stroke="#38bdf8",
            strokeWidth=2,
            size=80,
        ).encode(x=price_x, y="close:Q", tooltip=tooltips).transform_filter(hover)
        chart += selectors + vertical_guide + current_point

    chart = chart.properties(height=460 if show_volume else 555)
    if show_volume:
        volume_chart = alt.Chart(frame).mark_bar(size=candle_size, opacity=0.72, clip=True).encode(
            x=alt.X(
                "Posición:Q",
                title=axis_title,
                scale=alt.Scale(domain=time_domain, nice=False, zero=False),
                axis=alt.Axis(values=tick_positions, labelExpr=axis_label_expression, labelAngle=0),
            ),
            y=alt.Y(
                "volume:Q",
                title="Volumen",
                axis=alt.Axis(orient="right", format="~s", tickCount=3, grid=False),
            ),
            color=alt.condition("datum.open <= datum.close", alt.value("#20d4a7"), alt.value("#ff6178")),
            tooltip=[
                alt.Tooltip("Hora:T", title="Fecha y hora", format=tooltip_format),
                alt.Tooltip("volume:Q", title="Volumen", format=","),
            ],
        ).properties(height=105)
        chart = alt.vconcat(chart, volume_chart, spacing=5).resolve_scale(x="shared")

    chart = (
        chart.interactive()
        .configure(background="#0d1520")
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor="#263346",
            gridOpacity=0.58,
            domainColor="#354458",
            tickColor="#354458",
            labelColor="#9dacbf",
            titleColor="#aebbd0",
            labelFontSize=10,
            titleFontSize=11,
            labelPadding=7,
        )
        .configure_legend(labelColor="#d7dfeb", titleColor="#d7dfeb")
    )
    st.altair_chart(chart, use_container_width=True)
    if (settings["vwap"] or settings["volume"]) and not has_volume:
        st.caption("Este símbolo no informa volumen negociado; VWAP y barras de volumen se muestran cuando Tradier lo proporciona.")


def show_oi_chart(frame, mvs=None):
    aggregated = frame.groupby(["Strike", "Tipo"], as_index=False)["Open interest"].sum()
    aggregated["Exposición"] = aggregated.apply(
        lambda row: -row["Open interest"] if row["Tipo"] == "PUT" else row["Open interest"], axis=1
    )
    chart = alt.Chart(aggregated).mark_bar().encode(
        x=alt.X("Strike:O", title="Strike"),
        y=alt.Y("Exposición:Q", title="Open interest"),
        color=alt.Color("Tipo:N", scale=alt.Scale(domain=["PUT", "CALL"], range=["#ff5a70", "#00d084"])),
        tooltip=["Strike:O", "Tipo:N", "Open interest:Q"],
    )
    if mvs is not None:
        marker = alt.Chart(pd.DataFrame({"Strike": [mvs], "Nombre": ["MVS · Most Valuable Strike"]})).mark_rule(
            color="#fb923c", strokeDash=[5, 4], strokeWidth=3
        ).encode(x=alt.X("Strike:O"), tooltip=["Nombre:N", alt.Tooltip("Strike:O", title="Strike")])
        chart += marker
    st.altair_chart(chart.properties(height=290), use_container_width=True)


def generate_ideas(
    expiration,
    width,
    minimum_credit,
    maximum_risk,
    target_delta,
    contracts,
    require_outside_expected=False,
    require_behind_wall=False,
):
    spx = load_spx(selected_symbol())
    options = load_chain(expiration, selected_symbol())
    index = defender.build_option_index(options)
    summary = summarize_chain(options, spx, 400)
    expected = calculate_expected_levels(options, spx, expiration, summary["frame"], 400)
    dte = defender.calculate_days_remaining(expiration)
    ideas = {"PCS": [], "CCS": []}

    for (option_type, short_strike), short_option in index.items():
        if option_type not in ("put", "call"):
            continue
        strategy = "PCS" if option_type == "put" else "CCS"
        if (strategy == "PCS" and short_strike >= spx) or (strategy == "CCS" and short_strike <= spx):
            continue

        long_strike = short_strike - width if strategy == "PCS" else short_strike + width
        long_option = defender.get_option(index, option_type, long_strike)
        if long_option is None:
            continue

        greek_data = short_option.get("greeks") or {}
        if greek_data.get("delta") is None:
            continue
        delta = abs(defender.number(greek_data.get("delta")))
        if delta <= 0 or delta > min(target_delta + 0.12, 0.35):
            continue

        midpoint_credit = defender.option_midpoint(short_option) - defender.option_midpoint(long_option)
        bid_credit = max(defender.number(short_option.get("bid")) - defender.number(long_option.get("ask")), 0)
        if midpoint_credit < minimum_credit or midpoint_credit >= width:
            continue

        max_loss = (width - midpoint_credit) * 100 * contracts
        if max_loss > maximum_risk:
            continue

        wall = summary["put_wall"] if strategy == "PCS" else summary["call_wall"]
        behind_wall = wall is not None and (
            (strategy == "PCS" and short_strike <= wall) or (strategy == "CCS" and short_strike >= wall)
        )
        expected_boundary = expected["expiry_lower"] if strategy == "PCS" else expected["expiry_upper"]
        outside_expected = expected_boundary is not None and (
            (strategy == "PCS" and short_strike <= expected_boundary)
            or (strategy == "CCS" and short_strike >= expected_boundary)
        )
        if require_outside_expected and expected_boundary is not None and not outside_expected:
            continue
        if require_behind_wall and wall is not None and not behind_wall:
            continue
        gamma = defender.number(greek_data.get("gamma"))
        distance = abs(spx - short_strike)
        score = (
            100
            - abs(delta - target_delta) * 250
            + (15 if behind_wall else 0)
            + (18 if outside_expected else 0)
            + min(distance / 25, 10)
        )
        score += min(defender.integer(short_option.get("open_interest")) / 500, 8)

        ideas[strategy].append(
            {
                "strategy": strategy,
                "short_strike": float(short_strike),
                "long_strike": float(long_strike),
                "expiration": expiration,
                "contracts": int(contracts),
                "credit": round(midpoint_credit, 2),
                "bid_credit": round(bid_credit, 2),
                "max_profit": midpoint_credit * 100 * contracts,
                "max_loss": max_loss,
                "delta": delta,
                "gamma": gamma,
                "distance": distance,
                "wall": wall,
                "behind_wall": behind_wall,
                "outside_expected": outside_expected,
                "expected_boundary": expected_boundary,
                "score": score,
                "dte": dte,
            }
        )

    for strategy in ideas:
        ideas[strategy].sort(key=lambda idea: idea["score"], reverse=True)
        ideas[strategy] = ideas[strategy][:3]
    return ideas, summary, expected, spx


def normal_cdf(value):
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def option_theoretical_value(price, strike, years, volatility, option_type, rate=0.04):
    if price <= 0:
        return strike * math.exp(-rate * max(years, 0)) if option_type == "put" else 0.0
    if years <= 0 or volatility <= 0:
        return max(price - strike, 0.0) if option_type == "call" else max(strike - price, 0.0)

    root_time = math.sqrt(years)
    d1 = (math.log(price / strike) + (rate + 0.5 * volatility**2) * years) / (volatility * root_time)
    d2 = d1 - volatility * root_time
    discounted_strike = strike * math.exp(-rate * years)
    if option_type == "call":
        return price * normal_cdf(d1) - discounted_strike * normal_cdf(d2)
    return discounted_strike * normal_cdf(-d2) - price * normal_cdf(-d1)


def nearest_available_option(index, option_type, desired_strike):
    strikes = [strike for current_type, strike in index if current_type == option_type]
    if not strikes:
        raise RuntimeError(f"No hay opciones {option_type} disponibles para este vencimiento.")
    strike = min(strikes, key=lambda current: abs(current - desired_strike))
    return strike, defender.get_option(index, option_type, strike)


def build_strategy_template(strategy, index, spx, distance, width, contracts):
    center = nearest_strike(spx)
    definitions = {
        "PCS": [("VENDER", "PUT", center - distance), ("COMPRAR", "PUT", center - distance - width)],
        "CCS": [("VENDER", "CALL", center + distance), ("COMPRAR", "CALL", center + distance + width)],
        "Iron Condor": [
            ("VENDER", "PUT", center - distance),
            ("COMPRAR", "PUT", center - distance - width),
            ("VENDER", "CALL", center + distance),
            ("COMPRAR", "CALL", center + distance + width),
        ],
        "Call comprada": [("COMPRAR", "CALL", center)],
        "Put comprada": [("COMPRAR", "PUT", center)],
        "Call vendida": [("VENDER", "CALL", center + distance)],
        "Put vendida": [("VENDER", "PUT", center - distance)],
        "Bull Call Spread": [("COMPRAR", "CALL", center), ("VENDER", "CALL", center + width)],
        "Bear Put Spread": [("COMPRAR", "PUT", center), ("VENDER", "PUT", center - width)],
        "Long Straddle": [("COMPRAR", "CALL", center), ("COMPRAR", "PUT", center)],
        "Long Strangle": [("COMPRAR", "CALL", center + distance), ("COMPRAR", "PUT", center - distance)],
        "Short Straddle": [("VENDER", "CALL", center), ("VENDER", "PUT", center)],
        "Short Strangle": [("VENDER", "CALL", center + distance), ("VENDER", "PUT", center - distance)],
        "Iron Butterfly": [
            ("VENDER", "PUT", center),
            ("COMPRAR", "PUT", center - width),
            ("VENDER", "CALL", center),
            ("COMPRAR", "CALL", center + width),
        ],
        "Call Butterfly": [
            ("COMPRAR", "CALL", center - width),
            ("VENDER", "CALL", center),
            ("VENDER", "CALL", center),
            ("COMPRAR", "CALL", center + width),
        ],
        "Put Butterfly": [
            ("COMPRAR", "PUT", center + width),
            ("VENDER", "PUT", center),
            ("VENDER", "PUT", center),
            ("COMPRAR", "PUT", center - width),
        ],
        "Personalizada": [("VENDER", "PUT", center - distance), ("COMPRAR", "PUT", center - distance - width)],
    }
    rows = []
    for action, kind, desired_strike in definitions[strategy]:
        strike, option = nearest_available_option(index, kind.lower(), desired_strike)
        rows.append(
            {
                "Acción": action,
                "Tipo": kind,
                "Strike": float(strike),
                "Prima": round(defender.option_midpoint(option), 2),
                "Contratos": int(contracts),
            }
        )
    return pd.DataFrame(rows)


def normalize_simulator_legs(edited, index, default_iv):
    legs = []
    if edited.empty:
        raise RuntimeError("Agrega por lo menos una pata de opciones.")

    for _, row in edited.iterrows():
        action = str(row.get("Acción") or "").strip().upper()
        kind = str(row.get("Tipo") or "").strip().lower()
        strike = defender.number(row.get("Strike"))
        premium = defender.number(row.get("Prima"), default=-1)
        contracts = defender.integer(row.get("Contratos"))
        if action not in ("COMPRAR", "VENDER") or kind not in ("call", "put"):
            raise RuntimeError("Cada pata debe indicar COMPRAR/VENDER y CALL/PUT.")
        if strike <= 0 or premium < 0 or contracts <= 0:
            raise RuntimeError("Revisa strike, prima y contratos en todas las patas.")

        option = defender.get_option(index, kind, strike)
        if option is None:
            raise RuntimeError(f"No se encontró {kind.upper()} {strike:.0f} en la cadena de Tradier.")
        greeks = option.get("greeks") or {}
        legs.append(
            {
                "action": action,
                "type": kind,
                "strike": strike,
                "premium": premium,
                "contracts": contracts,
                "sign": 1 if action == "COMPRAR" else -1,
                "mid": defender.option_midpoint(option),
                "iv": option_implied_volatility(option) or default_iv or 0.20,
                "delta": defender.number(greeks.get("delta")),
                "gamma": defender.number(greeks.get("gamma")),
                "theta": defender.number(greeks.get("theta")),
                "vega": defender.number(greeks.get("vega")),
            }
        )
    return legs


def simulator_entry_cashflow(legs):
    return -sum(leg["sign"] * leg["premium"] * leg["contracts"] * 100 for leg in legs)


def simulator_expiration_pnl(legs, price):
    result = simulator_entry_cashflow(legs)
    for leg in legs:
        intrinsic = (
            max(price - leg["strike"], 0.0)
            if leg["type"] == "call"
            else max(leg["strike"] - price, 0.0)
        )
        result += leg["sign"] * intrinsic * leg["contracts"] * 100
    return result


def simulator_scenario_pnl(legs, price, years, iv_change, rate):
    result = simulator_entry_cashflow(legs)
    for leg in legs:
        volatility = max(leg["iv"] + iv_change, 0.01)
        value = option_theoretical_value(price, leg["strike"], years, volatility, leg["type"], rate)
        result += leg["sign"] * value * leg["contracts"] * 100
    return result


def simulator_bounds(legs, spx):
    strikes = sorted({float(leg["strike"]) for leg in legs})
    nodes = [0.0] + strikes
    tail_price = max(max(strikes) + max(spx, 100), spx * 2)
    checkpoints = nodes + [tail_price]
    values = [simulator_expiration_pnl(legs, price) for price in checkpoints]
    right_slope = sum(
        leg["sign"] * leg["contracts"] * 100
        for leg in legs
        if leg["type"] == "call"
    )
    max_profit = None if right_slope > 0 else max(values)
    max_loss = None if right_slope < 0 else min(values)

    breakevens = []
    for left, right in zip(checkpoints, checkpoints[1:]):
        first = simulator_expiration_pnl(legs, left)
        second = simulator_expiration_pnl(legs, right)
        if abs(first) < 0.00001:
            breakevens.append(left)
        if first * second < 0:
            fraction = abs(first) / (abs(first) + abs(second))
            breakevens.append(left + fraction * (right - left))
    if right_slope and values[-1] * right_slope < 0:
        breakevens.append(tail_price - values[-1] / right_slope)

    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakevens": sorted({round(point, 2) for point in breakevens if point >= 0}),
    }


def simulator_greeks(legs):
    return {
        greek: sum(leg["sign"] * leg[greek] * leg["contracts"] * 100 for leg in legs)
        for greek in ("delta", "gamma", "theta", "vega")
    }


def simulator_probability_of_profit(legs, spx, years, volatility, rate, breakevens):
    if spx <= 0 or volatility is None or volatility <= 0:
        return None
    if years <= 0:
        return 100.0 if simulator_expiration_pnl(legs, spx) > 0 else 0.0

    average = math.log(spx) + (rate - 0.5 * volatility**2) * years
    deviation = volatility * math.sqrt(years)

    def distribution(price):
        if price <= 0:
            return 0.0
        return normal_cdf((math.log(price) - average) / deviation)

    limits = [0.0] + sorted({point for point in breakevens if point > 0})
    probability = 0.0
    for index, lower in enumerate(limits):
        upper = limits[index + 1] if index + 1 < len(limits) else None
        if upper is None:
            test_price = max(lower + spx, spx * 2)
            segment_probability = 1.0 - distribution(lower)
        else:
            test_price = (lower + upper) / 2
            segment_probability = distribution(upper) - distribution(lower)
        if simulator_expiration_pnl(legs, test_price) > 0:
            probability += segment_probability
    return min(max(probability * 100, 0.0), 100.0)


def trade_option_snapshot(option, fallback_iv=0.20):
    option = option or {}
    greeks = option.get("greeks") or {}
    try:
        midpoint = defender.option_midpoint(option) if option else 0.0
    except Exception:
        midpoint = defender.number(option.get("last"))
    implied_volatility = option_implied_volatility(option) if option else None
    return {
        "mid": round(max(float(midpoint or 0), 0.0), 6),
        "iv": round(max(float(implied_volatility or fallback_iv or 0.20), 0.01), 6),
        "delta": round(defender.number(greeks.get("delta")), 6),
        "gamma": round(defender.number(greeks.get("gamma")), 8),
        "theta": round(defender.number(greeks.get("theta")), 6),
        "vega": round(defender.number(greeks.get("vega")), 6),
    }


def saved_trade_legs(trade, short_option, long_option):
    option_type = str(trade.get("option_type") or ("put" if trade["strategy"] == "PCS" else "call")).lower()
    contracts = max(int(trade.get("contracts") or 1), 1)
    long_premium = max(float(long_option.get("mid") or 0.0), 0.0)
    short_premium = long_premium + max(float(trade.get("credit") or 0.0), 0.0)
    return [
        {
            "action": "VENDER",
            "type": option_type,
            "strike": float(trade["short_strike"]),
            "premium": short_premium,
            "contracts": contracts,
            "sign": -1,
            "mid": float(short_option.get("mid") or 0.0),
            "iv": float(short_option.get("iv") or 0.20),
            "delta": float(short_option.get("delta") or 0.0),
            "gamma": float(short_option.get("gamma") or 0.0),
            "theta": float(short_option.get("theta") or 0.0),
            "vega": float(short_option.get("vega") or 0.0),
        },
        {
            "action": "COMPRAR",
            "type": option_type,
            "strike": float(trade["long_strike"]),
            "premium": long_premium,
            "contracts": contracts,
            "sign": 1,
            "mid": float(long_option.get("mid") or 0.0),
            "iv": float(long_option.get("iv") or 0.20),
            "delta": float(long_option.get("delta") or 0.0),
            "gamma": float(long_option.get("gamma") or 0.0),
            "theta": float(long_option.get("theta") or 0.0),
            "vega": float(long_option.get("vega") or 0.0),
        },
    ]


def build_trade_snapshot(trade, market_context=None):
    context = market_context if isinstance(market_context, dict) else {}
    symbol = str(trade.get("symbol") or "SPX").upper()
    spot = defender.number(context.get("spot"))
    if spot <= 0:
        try:
            spot = load_spx(symbol)
        except Exception:
            spot = (float(trade["short_strike"]) + float(trade["long_strike"])) / 2

    options = context.get("options")
    if options is None:
        try:
            options = load_chain(trade["expiration"], symbol)
        except Exception:
            options = []

    option_type = str(trade.get("option_type") or ("put" if trade["strategy"] == "PCS" else "call")).lower()
    fallback_iv = max(float(context.get("atm_iv") or 0.20), 0.01)
    short_raw = None
    long_raw = None
    if options:
        try:
            option_index = defender.build_option_index(options)
            short_raw = defender.get_option(option_index, option_type, float(trade["short_strike"]))
            long_raw = defender.get_option(option_index, option_type, float(trade["long_strike"]))
        except Exception:
            short_raw = None
            long_raw = None

    short_option = trade_option_snapshot(short_raw, fallback_iv)
    long_option = trade_option_snapshot(long_raw, fallback_iv)
    legs = saved_trade_legs(trade, short_option, long_option)
    days = max(int(defender.calculate_days_remaining(trade["expiration"]) or 0), 0)
    elapsed_days = min(max(int(context.get("elapsed_days") or 0), 0), days)
    if days == 0:
        years = years_to_expiration(trade["expiration"])
    else:
        years = max(days - elapsed_days, 0) / 365

    spread_width = abs(float(trade["short_strike"]) - float(trade["long_strike"]))
    strike_distance = max(abs(spot - float(trade["short_strike"])), abs(spot - float(trade["long_strike"])))
    graph_range = max(
        float(context.get("graph_range") or 0.0),
        spread_width * 4,
        strike_distance * 1.28,
        spot * 0.018,
        2.0,
    )
    iv_change = float(context.get("iv_change") or 0.0)
    rate = max(float(context.get("rate") or 0.04), 0.0)
    market_spread = max(short_option["mid"] - long_option["mid"], 0.0)
    if "target_pnl" in context and context.get("target_pnl") is not None:
        target_pnl = float(context["target_pnl"])
    elif short_raw or long_raw:
        target_pnl = (float(trade["credit"]) - market_spread) * int(trade["contracts"]) * 100
    else:
        target_pnl = 0.0

    theoretical_spot_pnl = simulator_scenario_pnl(legs, spot, years, iv_change, rate)
    curve_adjustment = target_pnl - theoretical_spot_pnl
    lower = max(spot - graph_range, 0.01)
    upper = max(spot + graph_range, lower + 0.01)
    curve = []
    for number in range(141):
        price = lower + (upper - lower) * number / 140
        curve.append(
            {
                "price": round(price, 4),
                "expiration": round(simulator_expiration_pnl(legs, price), 2),
                "scenario": round(simulator_scenario_pnl(legs, price, years, iv_change, rate) + curve_adjustment, 2),
            }
        )

    return {
        "symbol": symbol,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "spot": round(float(spot), 4),
        "expiration": str(trade["expiration"]),
        "days": days,
        "elapsed_days": elapsed_days,
        "graph_range": round(graph_range, 4),
        "atm_iv": round((short_option["iv"] + long_option["iv"]) / 2, 6),
        "iv_change": round(iv_change, 6),
        "rate": round(rate, 6),
        "spread_value": round(market_spread, 6),
        "pnl": round(target_pnl, 2),
        "target_price": round(float(context.get("target_price") or spot), 4),
        "short_option": short_option,
        "long_option": long_option,
        "curve": curve,
    }


def split_payoff_color_areas(frame, price_column):
    ordered = frame[[price_column, "Resultado"]].copy()
    ordered[price_column] = pd.to_numeric(ordered[price_column], errors="coerce")
    ordered["Resultado"] = pd.to_numeric(ordered["Resultado"], errors="coerce")
    ordered = ordered.dropna().sort_values(price_column)
    points = []
    previous = None

    for row in ordered.itertuples(index=False, name=None):
        price, result = float(row[0]), float(row[1])
        if previous is not None:
            previous_price, previous_result = previous
            if previous_result * result < 0:
                crossing = previous_price + (price - previous_price) * abs(previous_result) / (
                    abs(previous_result) + abs(result)
                )
                points.append({price_column: crossing, "Resultado": 0.0})
        points.append({price_column: price, "Resultado": result})
        previous = (price, result)

    separated = pd.DataFrame(points, columns=[price_column, "Resultado"])
    separated["Ganancia"] = separated["Resultado"].clip(lower=0)
    separated["Pérdida"] = separated["Resultado"].clip(upper=0)
    return separated


def payoff_color_layers(frame, price_column, price_encoding, opacity=0.30):
    separated = split_payoff_color_areas(frame, price_column)
    profit_area = alt.Chart(separated).mark_area(
        color="#23d59f", opacity=opacity, interpolate="linear"
    ).encode(
        x=price_encoding,
        y=alt.Y("Ganancia:Q", title="Ganancia / pérdida ($)"),
        y2=alt.Y2(datum=0),
    )
    loss_area = alt.Chart(separated).mark_area(
        color="#ff6276", opacity=opacity, interpolate="linear"
    ).encode(
        x=price_encoding,
        y=alt.Y("Pérdida:Q", title="Ganancia / pérdida ($)"),
        y2=alt.Y2(datum=0),
    )
    return profit_area + loss_area


def render_saved_trade_graph(trade, snapshot, live=False, original_snapshot=None):
    curve = snapshot.get("curve") if isinstance(snapshot, dict) else None
    if not curve:
        st.info("Esta operación no tiene una gráfica disponible.")
        return

    symbol = str(snapshot.get("symbol") or trade.get("symbol") or "SPX").upper()
    curve_name = "Situación actual" if live else "Situación al guardar"
    rows = []
    for point in curve:
        rows.append({"Precio": point["price"], "Resultado": point["expiration"], "Curva": "Al vencimiento"})
        rows.append({"Precio": point["price"], "Resultado": point["scenario"], "Curva": curve_name})
    frame = pd.DataFrame(rows)
    expiration_frame = frame[frame["Curva"] == "Al vencimiento"]
    price_encoding = alt.X("Precio:Q", title=f"Precio de {symbol}", scale=alt.Scale(zero=False))
    pnl_encoding = alt.Y("Resultado:Q", title="Ganancia / pérdida ($)")
    area = payoff_color_layers(expiration_frame, "Precio", price_encoding, opacity=0.32)
    lines = alt.Chart(frame).mark_line(strokeWidth=2.8).encode(
        x=price_encoding,
        y=pnl_encoding,
        color=alt.Color(
            "Curva:N",
            scale=alt.Scale(domain=["Al vencimiento", curve_name], range=["#eaf0fa", "#64b5ff"]),
            legend=alt.Legend(orient="bottom", title=None),
        ),
        tooltip=[
            alt.Tooltip("Precio:Q", title=symbol, format=",.2f"),
            alt.Tooltip("Resultado:Q", title="Resultado", format="+,.2f"),
            "Curva:N",
        ],
    )
    zero = alt.Chart(pd.DataFrame({"Resultado": [0]})).mark_rule(color="#9aa7b8", opacity=0.8).encode(
        y="Resultado:Q"
    )
    levels = [
        {
            "Precio": float(snapshot.get("spot") or 0),
            "Nivel": f"{symbol} {'actual' if live else 'inicial'}",
            "Color": "#5db5ff",
        },
        {
            "Precio": float(trade["short_strike"]),
            "Nivel": f"Strike vendido {float(trade['short_strike']):,.2f}",
            "Color": "#ff7386",
        },
        {
            "Precio": float(trade["long_strike"]),
            "Nivel": f"Strike comprado {float(trade['long_strike']):,.2f}",
            "Color": "#33d9a6",
        },
    ]
    if live and isinstance(original_snapshot, dict) and original_snapshot.get("spot"):
        levels.append(
            {
                "Precio": float(original_snapshot["spot"]),
                "Nivel": f"{symbol} cuando abriste la operación",
                "Color": "#f2c66d",
            }
        )
    rules = alt.Chart(pd.DataFrame(levels)).mark_rule(strokeDash=[6, 5], strokeWidth=1.6).encode(
        x="Precio:Q",
        color=alt.Color("Color:N", scale=None),
        tooltip=["Nivel:N", alt.Tooltip("Precio:Q", format=",.2f")],
    )
    current_point = alt.Chart(
        pd.DataFrame(
            [{"Precio": float(snapshot.get("spot") or 0), "Resultado": float(snapshot.get("pnl") or 0)}]
        )
    ).mark_point(size=145, filled=True, stroke="#edf2fa", strokeWidth=1.5).encode(
        x="Precio:Q",
        y="Resultado:Q",
        color=alt.condition("datum.Resultado >= 0", alt.value("#27d9a4"), alt.value("#ff687b")),
        tooltip=[
            alt.Tooltip("Precio:Q", title=symbol, format=",.2f"),
            alt.Tooltip("Resultado:Q", title="Ganancia / pérdida", format="+,.2f"),
        ],
    )
    chart = (
        (area + lines + zero + rules + current_point)
        .properties(height=330)
        .interactive()
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor="#253042",
            domainColor="#344155",
            tickColor="#344155",
            labelColor="#a2b0c4",
            titleColor="#b7c3d4",
        )
        .configure_legend(labelColor="#d7dfeb", titleColor="#d7dfeb")
    )
    st.altair_chart(chart, use_container_width=True)


LIVE_BUILDER_HTML = """
<section class="live-builder">
  <header class="live-header">
    <div><span class="live-kicker">OPTIONS STRATEGY BUILDER</span><h2 id="live-title">Estrategia</h2></div>
    <div id="live-spot" class="live-spot"></div>
  </header>
  <div class="section-label">VENCIMIENTOS · DESLIZA Y SELECCIONA</div>
  <div id="date-rail" class="date-rail"></div>
  <div class="strike-heading">
    <div class="section-label">STRIKES · ARRASTRA LOS CÍRCULOS DE CADA PATA</div>
    <button id="strike-zoom-toggle" class="strike-zoom-toggle" type="button">🔍 AMPLIAR</button>
  </div>
  <div id="strike-stage" class="strike-stage">
    <svg id="strike-rail" class="strike-rail" viewBox="0 0 920 180" preserveAspectRatio="none"></svg>
    <div id="strike-tooltip" class="strike-tooltip hidden"></div>
  </div>
  <div class="strike-help">Pasa el mouse para ampliar · desliza horizontalmente · arrastra los círculos</div>
  <div id="leg-sliders" class="leg-sliders"></div>
  <div id="live-stats" class="live-stats"></div>
  <div class="chart-toolbar">
    <div><button id="graph-mode" class="mode-button selected">GRÁFICO</button><button id="table-mode" class="mode-button">TABLA</button></div>
    <div id="curve-label" class="curve-label"></div>
  </div>
  <div class="chart-shell">
    <svg id="payoff-chart" class="payoff-chart" viewBox="0 0 920 410" preserveAspectRatio="none"></svg>
    <div id="profit-table" class="profit-table hidden"></div>
    <div id="chart-tooltip" class="chart-tooltip hidden"></div>
  </div>
  <div class="control-grid">
    <label>PRECIO OBJETIVO <strong id="target-label"></strong><input id="target-slider" type="range" min="0" max="1000" value="500"></label>
    <label>DÍAS TRANSCURRIDOS <strong id="days-label"></strong><input id="days-slider" type="range" min="0" max="30" value="0"></label>
    <label>VOLATILIDAD IMPLÍCITA <strong id="iv-label"></strong><input id="iv-slider" type="range" min="-30" max="40" value="0"></label>
    <label>RANGO DEL GRÁFICO <strong id="range-label"></strong><input id="range-slider" type="range" min="2" max="40" value="12"></label>
  </div>
  <div id="live-greeks" class="live-greeks"></div>
  <div class="live-disclaimer">Estimaciones teóricas: los precios reales, la volatilidad y la ejecución pueden variar.</div>
</section>
"""


LIVE_BUILDER_CSS = """
.live-builder{box-sizing:border-box;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#edf2fa;background:linear-gradient(145deg,#111827,#0b111b 72%);border:1px solid #2b3648;border-radius:16px;padding:18px 19px 15px;width:100%;min-width:310px}.live-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.live-header h2{font-size:20px;letter-spacing:-.045em;margin:4px 0 10px}.live-kicker,.section-label{font-size:10px;letter-spacing:.12em;color:#8da0ba;font-weight:750}.section-label{margin:13px 0 8px}.live-spot{padding:8px 12px;border:1px solid #34445a;background:#111d2b;border-radius:999px;color:#43e0ad;font-weight:750}.date-rail{display:flex;gap:7px;overflow-x:auto;padding-bottom:6px;scrollbar-color:#40506a #101722}.date-chip{min-width:69px;padding:7px 8px;border:1px solid #303b4e;border-radius:8px;background:#141d2a;color:#b6c2d2;cursor:pointer;text-align:center;font-size:11px}.date-chip b{display:block;color:#edf2fa;font-size:13px}.date-chip.selected{background:#18344f;border-color:#63a9ff;color:#a9ceff}.strike-rail{height:156px;width:100%;background:#0f1622;border-radius:10px;touch-action:none}.leg-sliders{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:8px;margin-top:8px}.leg-slider{padding:8px 9px;background:#111b29;border:1px solid #283448;border-radius:8px}.leg-slider span{display:flex;justify-content:space-between;font-size:11px;color:#d5deeb}.leg-slider strong.call{color:#31d8a2}.leg-slider strong.put{color:#ff7385}.leg-slider input,.control-grid input{width:100%;margin:8px 0 0;accent-color:#65a9ff}.live-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:15px}.stat-box{padding:9px 8px;background:#111a27;border:1px solid #29364a;border-radius:9px}.stat-box span{display:block;font-size:9px;letter-spacing:.055em;color:#91a1b8}.stat-box strong{display:block;margin-top:6px;font-size:17px;color:#edf2fa;white-space:nowrap}.stat-box.green strong{color:#30d9a0}.stat-box.red strong{color:#ff7182}.stat-box.blue strong{color:#76b7ff}.chart-toolbar{display:flex;justify-content:space-between;align-items:center;gap:9px;margin-top:15px}.mode-button{background:#111a27;color:#a4b1c4;border:1px solid #2a384b;padding:7px 12px;font-size:10px;font-weight:720;cursor:pointer}.mode-button:first-child{border-radius:7px 0 0 7px}.mode-button:last-child{border-radius:0 7px 7px 0}.mode-button.selected{background:#20334e;color:#f1f5fb;border-color:#5478ad}.curve-label{font-size:10px;color:#9baac0}.chart-shell{position:relative;margin-top:9px;border:1px solid #293548;border-radius:10px;background:#0d141f;overflow:hidden}.payoff-chart{width:100%;height:375px;display:block}.chart-tooltip{position:absolute;pointer-events:none;padding:8px 10px;background:#1b293c;border:1px solid #476180;border-radius:7px;color:#f3f6fc;font-size:11px;z-index:3}.profit-table{height:375px;overflow:auto;padding:8px}.heat-grid{display:grid;gap:2px}.heat-header,.heat-price,.heat-cell{text-align:center;padding:7px 4px;font-size:10px;border-radius:3px}.heat-header,.heat-price{color:#aab8cc;background:#121d2b}.heat-cell{color:white;font-weight:650}.hidden{display:none!important}.control-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 17px;padding-top:14px}.control-grid label{color:#9dacbf;font-size:10px;letter-spacing:.025em}.control-grid label strong{float:right;color:#edf2fa;font-size:11px}.live-greeks{display:flex;flex-wrap:wrap;gap:13px;margin-top:15px;padding-top:11px;border-top:1px solid #273348;color:#aab8ca;font-size:10px}.live-greeks strong{color:#eaf0f9}.live-disclaimer{font-size:9px;color:#8290a5;margin-top:11px}@media(max-width:680px){.live-builder{padding:13px}.live-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.control-grid{grid-template-columns:1fr}.payoff-chart{height:320px}.chart-toolbar{align-items:flex-start;flex-direction:column}.stat-box strong{font-size:15px}}
"""


LIVE_BUILDER_CSS += """
.strike-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:4px}
.strike-heading .section-label{margin:12px 0 8px}
.strike-zoom-toggle{flex-shrink:0;padding:6px 9px;border:1px solid #405977;border-radius:7px;background:#142238;color:#b8d8ff;font-size:10px;font-weight:700;cursor:pointer;transition:background .16s ease,border-color .16s ease}
.strike-zoom-toggle:hover,.strike-zoom-toggle.selected{background:#224364;border-color:#71b6ff;color:#f0f7ff}
.strike-stage{position:relative;overflow-x:auto;overflow-y:hidden;border:1px solid #28364b;border-radius:10px;background:#0f1622;scrollbar-width:thin;scrollbar-color:#6485ad #111a27;transition:border-color .18s ease,box-shadow .18s ease}
.strike-stage.expanded{border-color:#608fbe;box-shadow:0 0 0 1px rgba(93,164,237,.23)}
.strike-stage .strike-rail{display:block;width:100%;min-width:100%;height:176px;border-radius:0;transition:width .2s ease,height .2s ease}
.strike-stage.expanded .strike-rail{width:190%;min-width:900px;height:272px}
.strike-marker{cursor:grab}
.strike-marker:active{cursor:grabbing}
.strike-tooltip{position:absolute;pointer-events:none;top:10px;z-index:4;min-width:120px;padding:8px 10px;background:#17263a;border:1px solid #527298;border-radius:8px;color:#eef4fc;font-size:11px;line-height:1.45;box-shadow:0 7px 18px rgba(0,0,0,.24)}
.strike-tooltip b{display:block;color:#7bc1ff;font-size:13px}
.strike-help{margin-top:6px;color:#9bb0ca;font-size:10px;text-align:right}
@media(max-width:680px){.strike-heading{align-items:flex-start}.strike-heading .section-label{max-width:66%;line-height:1.45}.strike-stage.expanded .strike-rail{width:215%;min-width:840px;height:252px}.strike-help{text-align:left}}
"""


LIVE_BUILDER_JS = r"""
export default function(component) {
  const { parentElement, data, setStateValue } = component;
  const root = parentElement.querySelector(".live-builder");
  if (!root || !data || !Array.isArray(data.options) || !data.options.length) return;

  const byId = (name) => root.querySelector("#" + name);
  const spot = Number(data.spot) || 1;
  const symbol = String(data.symbol || "SPX");
  const chain = data.options.map((item) => ({ ...item, strike: Number(item.strike), mid: Number(item.mid || 0) }));
  const available = [...new Set(chain.map((item) => item.strike))].sort((a, b) => a - b);
  const optionFor = (type, strike) => chain.find((item) => item.type === type && Math.abs(item.strike - strike) < 0.0001);
  const previous = data.selection && data.selection.expiration === data.expiration ? data.selection : {};
  const sourceLegs = Array.isArray(previous.legs) && previous.legs.length ? previous.legs : data.legs;
  const state = {
    legs: sourceLegs.map((leg) => ({ ...leg, strike: Number(leg.strike), premium: Number(leg.premium), contracts: Number(leg.contracts || 1) })),
    elapsed: Math.min(Number(previous.elapsed || 0), Math.max(Number(data.days || 0), 0)),
    ivShift: Number(previous.iv_shift || 0),
    target: Number(previous.target || spot),
    rangePercent: Math.max(2, Math.min(40, Number(previous.range_percent || data.range_percent || 12))),
    mode: previous.mode === "table" ? "table" : "graph",
    strikeZoomPinned: previous.strike_zoom === true
  };
  const rate = Number(data.rate || 0.04);
  const atmIv = Math.max(Number(data.atm_iv || 0.2), 0.01);
  const totalDays = Math.max(Number(data.days || 0), 0);
  const money = (value) => {
    const absolute = Math.abs(Number(value || 0)).toLocaleString("en-US", { maximumFractionDigits: 0 });
    return (value < 0 ? "-$" : "$") + absolute;
  };
  const priceFormat = (value) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const cdf = (value) => {
    const sign = value < 0 ? -1 : 1;
    const x = Math.abs(value) / Math.SQRT2;
    const t = 1 / (1 + 0.3275911 * x);
    const erf = 1 - (((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t) * Math.exp(-x * x);
    return 0.5 * (1 + sign * erf);
  };
  const optionPrice = (price, strike, years, iv, type) => {
    if (years <= 0 || iv <= 0) return type === "call" ? Math.max(price - strike, 0) : Math.max(strike - price, 0);
    if (price <= 0) return type === "put" ? strike * Math.exp(-rate * years) : 0;
    const rootTime = Math.sqrt(years);
    const d1 = (Math.log(price / strike) + (rate + 0.5 * iv * iv) * years) / (iv * rootTime);
    const d2 = d1 - iv * rootTime;
    return type === "call"
      ? price * cdf(d1) - strike * Math.exp(-rate * years) * cdf(d2)
      : strike * Math.exp(-rate * years) * cdf(-d2) - price * cdf(-d1);
  };
  const signFor = (leg) => leg.action === "COMPRAR" ? 1 : -1;
  const cashflow = () => -state.legs.reduce((total, leg) => total + signFor(leg) * leg.premium * leg.contracts * 100, 0);
  const payoff = (price, years = 0, theoretical = false) => {
    let value = cashflow();
    for (const leg of state.legs) {
      const option = optionFor(leg.type, leg.strike) || {};
      const iv = Math.max(Number(option.iv || leg.iv || atmIv) + state.ivShift / 100, 0.01);
      const premium = theoretical
        ? optionPrice(price, leg.strike, years, iv, leg.type)
        : leg.type === "call" ? Math.max(price - leg.strike, 0) : Math.max(leg.strike - price, 0);
      value += signFor(leg) * premium * leg.contracts * 100;
    }
    return value;
  };
  const bounds = () => {
    const strikes = [...new Set(state.legs.map((leg) => leg.strike))].sort((a, b) => a - b);
    const tail = Math.max(spot * 2, (strikes[strikes.length - 1] || spot) + spot);
    const nodes = [0, ...strikes, tail];
    const values = nodes.map((price) => payoff(price));
    const slope = state.legs.filter((leg) => leg.type === "call").reduce((total, leg) => total + signFor(leg) * leg.contracts * 100, 0);
    const breakevens = [];
    for (let i = 0; i < nodes.length - 1; i++) {
      const left = values[i], right = values[i + 1];
      if (Math.abs(left) < 0.001) breakevens.push(nodes[i]);
      if (left * right < 0) breakevens.push(nodes[i] + Math.abs(left) / (Math.abs(left) + Math.abs(right)) * (nodes[i + 1] - nodes[i]));
    }
    if (slope && values[values.length - 1] * slope < 0) breakevens.push(tail - values[values.length - 1] / slope);
    return {
      maximum: slope > 0 ? null : Math.max(...values),
      minimum: slope < 0 ? null : Math.min(...values),
      breakevens: [...new Set(breakevens.map((item) => Math.round(item * 100) / 100))]
    };
  };
  const profitChance = (breakevens) => {
    const years = Math.max(totalDays, 0.15) / 365;
    const mu = Math.log(spot) + (rate - atmIv * atmIv / 2) * years;
    const sigma = atmIv * Math.sqrt(years);
    const dist = (value) => value <= 0 ? 0 : cdf((Math.log(value) - mu) / sigma);
    const points = [0, ...breakevens.filter((value) => value > 0).sort((a, b) => a - b)];
    let chance = 0;
    points.forEach((lower, index) => {
      const upper = index + 1 < points.length ? points[index + 1] : null;
      const test = upper === null ? Math.max(lower + spot, spot * 2) : (lower + upper) / 2;
      if (payoff(test) > 0) chance += upper === null ? 1 - dist(lower) : dist(upper) - dist(lower);
    });
    return Math.min(Math.max(chance * 100, 0), 100);
  };
  const refreshLeg = (index, strike) => {
    const leg = state.legs[index];
    const found = optionFor(leg.type, strike);
    if (!leg || !found) return;
    leg.strike = found.strike;
    leg.premium = found.mid;
    leg.iv = Number(found.iv || atmIv);
  };
  const serialize = () => ({
    expiration: data.expiration,
    legs: state.legs.map(({ action, type, strike, premium, contracts }) => ({ action, type, strike, premium, contracts })),
    elapsed: state.elapsed,
    iv_shift: state.ivShift,
    target: state.target,
    range_percent: state.rangePercent,
    mode: state.mode,
    strike_zoom: state.strikeZoomPinned
  });
  let commitTimer;
  const commit = () => {
    if (typeof setStateValue !== "function") return;
    clearTimeout(commitTimer);
    commitTimer = setTimeout(() => setStateValue("selection", serialize()), 130);
  };

  byId("live-title").textContent = String(data.strategy || "Estrategia");
  byId("live-spot").textContent = symbol + "  " + priceFormat(spot);

  const renderDates = () => {
    const rail = byId("date-rail");
    rail.replaceChildren();
    const currentIndex = Math.max(data.expirations.indexOf(data.expiration), 0);
    const first = Math.max(currentIndex - 5, 0);
    const last = Math.min(Math.max(currentIndex + 10, 15), data.expirations.length);
    data.expirations.slice(first, last).forEach((value) => {
      const day = new Date(value + "T12:00:00");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "date-chip" + (value === data.expiration ? " selected" : "");
      button.innerHTML = day.toLocaleDateString("es", { weekday: "short" }) + "<b>" + day.toLocaleDateString("es", { month: "short", day: "numeric" }) + "</b>";
      button.onclick = () => {
        if (value !== data.expiration && typeof setStateValue === "function") setStateValue("expiration", value);
      };
      rail.appendChild(button);
      if (value === data.expiration) requestAnimationFrame(() => button.scrollIntoView({ block: "nearest", inline: "center" }));
    });
  };

  const railSvg = byId("strike-rail");
  const railStage = byId("strike-stage");
  const strikeTooltip = byId("strike-tooltip");
  const zoomButton = byId("strike-zoom-toggle");
  let railDomain = [];
  const setStrikeZoom = (expanded, pointerX = null) => {
    const wasExpanded = railStage.classList.contains("expanded");
    if (wasExpanded === expanded) {
      zoomButton.classList.toggle("selected", state.strikeZoomPinned);
      zoomButton.textContent = state.strikeZoomPinned ? "📌 ZOOM FIJO" : "🔍 AMPLIAR";
      return;
    }
    const viewport = railStage.getBoundingClientRect();
    const anchor = pointerX === null ? viewport.width / 2 : Math.max(pointerX - viewport.left, 0);
    const ratio = (railStage.scrollLeft + anchor) / Math.max(railSvg.getBoundingClientRect().width, 1);
    railStage.classList.toggle("expanded", expanded);
    zoomButton.classList.toggle("selected", state.strikeZoomPinned);
    zoomButton.textContent = state.strikeZoomPinned ? "📌 ZOOM FIJO" : "🔍 AMPLIAR";
    requestAnimationFrame(() => {
      const totalWidth = Math.max(railSvg.getBoundingClientRect().width, railStage.clientWidth);
      railStage.scrollLeft = Math.max(0, Math.min(ratio * totalWidth - anchor, totalWidth - railStage.clientWidth));
    });
  };
  const renderRail = () => {
    const radius = Math.max(spot * state.rangePercent / 100, 4);
    railDomain = available.filter((strike) => strike >= spot - radius * 0.72 && strike <= spot + radius * 0.72);
    state.legs.forEach((leg) => { if (!railDomain.includes(leg.strike)) railDomain.push(leg.strike); });
    railDomain.sort((a, b) => a - b);
    if (railDomain.length > 48) railDomain = railDomain.filter((_, index) => index % Math.ceil(railDomain.length / 48) === 0 || state.legs.some((leg) => Math.abs(leg.strike - railDomain[index]) < 0.001));
    if (!railDomain.length) return;
    const x = (strike) => 45 + (strike - railDomain[0]) / Math.max(railDomain[railDomain.length - 1] - railDomain[0], 0.001) * 830;
    let highest = 1;
    railDomain.forEach((strike) => ["call", "put"].forEach((type) => { highest = Math.max(highest, Number((optionFor(type, strike) || {}).oi || 0)); }));
    const width = Math.max(3, Math.min(15, 710 / railDomain.length));
    let svg = '<line x1="38" y1="84" x2="882" y2="84" stroke="#3b4a60" stroke-width="1"/>';
    railDomain.forEach((strike, index) => {
      const call = optionFor("call", strike) || {}, put = optionFor("put", strike) || {};
      const callHeight = Math.max(Math.sqrt(Number(call.oi || 0) / highest) * 58, 2);
      const putHeight = Math.max(Math.sqrt(Number(put.oi || 0) / highest) * 52, 2);
      const currentX = x(strike);
      svg += '<rect x="' + (currentX - width / 2).toFixed(1) + '" y="' + (84 - callHeight).toFixed(1) + '" width="' + width + '" height="' + callHeight.toFixed(1) + '" rx="2" fill="#1fc797" opacity=".75"/>';
      svg += '<rect x="' + (currentX - width / 2).toFixed(1) + '" y="85" width="' + width + '" height="' + putHeight.toFixed(1) + '" rx="2" fill="#ee5f73" opacity=".75"/>';
      const labelCount = railStage.classList.contains("expanded") ? 18 : 9;
      const interval = Math.max(Math.ceil(railDomain.length / labelCount), 1);
      if (index % interval === 0) svg += '<text x="' + currentX.toFixed(1) + '" y="162" fill="#c1cde0" font-size="12" font-weight="600" text-anchor="middle">' + priceFormat(strike) + "</text>";
    });
    const spotX = x(Math.min(Math.max(spot, railDomain[0]), railDomain[railDomain.length - 1]));
    svg += '<line x1="' + spotX.toFixed(1) + '" x2="' + spotX.toFixed(1) + '" y1="7" y2="141" stroke="#69b4ff" stroke-width="1.4" stroke-dasharray="4 4"/>';
    state.legs.forEach((leg, index) => {
      const currentX = x(leg.strike);
      const cy = leg.type === "call" ? 34 + (index % 2) * 15 : 120 - (index % 2) * 15;
      const fill = leg.type === "call" ? "#20d49d" : "#ff6b7e";
      svg += '<g data-leg="' + index + '" class="strike-marker"><circle cx="' + currentX.toFixed(1) + '" cy="' + cy + '" r="26" fill="transparent"/><circle class="marker-core" cx="' + currentX.toFixed(1) + '" cy="' + cy + '" r="16" fill="' + fill + '" stroke="#f2f6fb" stroke-width="2.2"/><text x="' + currentX.toFixed(1) + '" y="' + (cy + 5) + '" text-anchor="middle" fill="#0e1621" font-size="13" font-weight="750">' + (leg.action === "COMPRAR" ? "+" : "−") + "</text></g>";
    });
    railSvg.innerHTML = svg;
  };

  let dragged = null;
  railStage.onpointerenter = (event) => {
    setStrikeZoom(true, event.clientX);
    renderRail();
  };
  railStage.onpointerleave = () => {
    strikeTooltip.classList.add("hidden");
    if (dragged === null && !state.strikeZoomPinned) {
      setStrikeZoom(false);
      renderRail();
    }
  };
  zoomButton.onclick = () => {
    state.strikeZoomPinned = !state.strikeZoomPinned;
    setStrikeZoom(state.strikeZoomPinned);
    renderRail();
    commit();
  };
  railSvg.onpointerdown = (event) => {
    const marker = event.target.closest("[data-leg]");
    if (!marker) return;
    dragged = Number(marker.getAttribute("data-leg"));
    strikeTooltip.classList.add("hidden");
    railSvg.setPointerCapture(event.pointerId);
    event.preventDefault();
  };
  railSvg.onpointermove = (event) => {
    if (!railDomain.length) return;
    const rect = railSvg.getBoundingClientRect();
    const local = (event.clientX - rect.left) / Math.max(rect.width, 1) * 920;
    const desired = railDomain[0] + (local - 45) / 830 * (railDomain[railDomain.length - 1] - railDomain[0]);
    if (dragged === null) {
      const closestStrike = railDomain.reduce((best, strike) => Math.abs(strike - desired) < Math.abs(best - desired) ? strike : best, railDomain[0]);
      const call = optionFor("call", closestStrike) || {}, put = optionFor("put", closestStrike) || {};
      const viewport = railStage.getBoundingClientRect();
      strikeTooltip.innerHTML = '<b>STRIKE ' + priceFormat(closestStrike) + '</b>CALL ' + money(Number(call.mid || 0) * 100) + '<br>PUT ' + money(Number(put.mid || 0) * 100);
      strikeTooltip.style.left = Math.max(8, Math.min(event.clientX - viewport.left + railStage.scrollLeft + 14, railStage.scrollWidth - 156)) + "px";
      strikeTooltip.classList.remove("hidden");
      return;
    }
    const matching = available.filter((strike) => !!optionFor(state.legs[dragged].type, strike));
    const closest = matching.reduce((best, strike) => Math.abs(strike - desired) < Math.abs(best - desired) ? strike : best, matching[0]);
    if (closest !== state.legs[dragged].strike) {
      refreshLeg(dragged, closest);
      renderAll(false);
    }
  };
  railSvg.onpointerup = (event) => {
    if (dragged === null) return;
    dragged = null;
    if (railSvg.hasPointerCapture(event.pointerId)) railSvg.releasePointerCapture(event.pointerId);
    commit();
  };
  railSvg.onpointerover = (event) => {
    const marker = event.target.closest("[data-leg]");
    if (!marker) return;
    const core = marker.querySelector(".marker-core");
    if (core) core.setAttribute("r", "20");
  };
  railSvg.onpointerout = (event) => {
    const marker = event.target.closest("[data-leg]");
    if (!marker) return;
    const core = marker.querySelector(".marker-core");
    if (core) core.setAttribute("r", "16");
  };

  const renderLegSliders = () => {
    const box = byId("leg-sliders");
    box.replaceChildren();
    state.legs.forEach((leg, index) => {
      const choices = available.filter((strike) => !!optionFor(leg.type, strike));
      const holder = document.createElement("label");
      holder.className = "leg-slider";
      const header = document.createElement("span");
      header.innerHTML = '<strong class="' + leg.type + '">' + (leg.action === "COMPRAR" ? "COMPRA " : "VENTA ") + leg.type.toUpperCase() + "</strong><b>" + priceFormat(leg.strike) + " · " + money(leg.premium * 100) + "</b>";
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = "0";
      slider.max = String(Math.max(choices.length - 1, 0));
      slider.value = String(Math.max(choices.findIndex((strike) => Math.abs(strike - leg.strike) < 0.001), 0));
      slider.oninput = () => {
        refreshLeg(index, choices[Number(slider.value)]);
        header.querySelector("b").textContent = priceFormat(state.legs[index].strike) + " · " + money(state.legs[index].premium * 100);
        renderRail();
        renderStats();
        renderChart();
        renderGreeks();
      };
      slider.onchange = commit;
      holder.append(header, slider);
      box.appendChild(holder);
    });
  };

  const renderStats = () => {
    const result = bounds();
    const chance = profitChance(result.breakevens);
    const entries = [
      [cashflow() >= 0 ? "CRÉDITO NETO" : "DÉBITO NETO", money(Math.abs(cashflow())), "blue"],
      ["PÉRDIDA MÁXIMA", result.minimum === null ? "ILIMITADA" : money(Math.abs(Math.min(result.minimum, 0))), "red"],
      ["GANANCIA MÁXIMA", result.maximum === null ? "ILIMITADA" : money(Math.max(result.maximum, 0)), "green"],
      ["PROB. GANANCIA", chance.toFixed(1) + "%", "green"]
    ];
    byId("live-stats").innerHTML = entries.map(([label, value, tone]) => '<div class="stat-box ' + tone + '"><span>' + label + "</span><strong>" + value + "</strong></div>").join("");
    byId("curve-label").textContent = "Breakeven: " + (result.breakevens.map(priceFormat).join(" · ") || "N/D");
  };

  let graphMapping = null;
  const renderChart = () => {
    const svg = byId("payoff-chart");
    const table = byId("profit-table");
    const showTable = state.mode === "table";
    svg.classList.toggle("hidden", showTable);
    table.classList.toggle("hidden", !showTable);
    byId("graph-mode").classList.toggle("selected", !showTable);
    byId("table-mode").classList.toggle("selected", showTable);
    if (showTable) {
      renderTable();
      return;
    }
    const lower = Math.max(spot * (1 - state.rangePercent / 100), 0.01);
    const upper = spot * (1 + state.rangePercent / 100);
    const years = Math.max(totalDays - state.elapsed, 0) / 365;
    const samples = Array.from({ length: 181 }, (_, index) => lower + (upper - lower) * index / 180);
    const terminal = samples.map((price) => payoff(price));
    const current = samples.map((price) => payoff(price, years, true));
    const extremes = [...terminal, ...current, 0];
    let low = Math.min(...extremes), high = Math.max(...extremes);
    const padding = Math.max((high - low) * 0.16, 50);
    low -= padding;
    high += padding;
    const plot = { left: 79, top: 19, width: 798, height: 333 };
    const x = (price) => plot.left + (price - lower) / (upper - lower) * plot.width;
    const y = (value) => plot.top + (high - value) / Math.max(high - low, 0.001) * plot.height;
    const zero = y(0);
    graphMapping = { lower, upper, low, high, plot, x, y, years };
    const pathFor = (values) => values.map((value, index) => (index ? "L" : "M") + x(samples[index]).toFixed(2) + "," + y(value).toFixed(2)).join(" ");
    const expiryPath = pathFor(terminal);
    const scenarioPath = pathFor(current);
    const areaPath = expiryPath + " L" + x(upper).toFixed(2) + "," + zero.toFixed(2) + " L" + x(lower).toFixed(2) + "," + zero.toFixed(2) + " Z";
    const positiveHeight = Math.max(Math.min(zero, plot.top + plot.height) - plot.top, 0);
    const negativeStart = Math.max(Math.min(zero, plot.top + plot.height), plot.top);
    const negativeHeight = Math.max(plot.top + plot.height - negativeStart, 0);
    let content = '<defs><linearGradient id="profitFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#23dda4" stop-opacity=".63"/><stop offset="100%" stop-color="#23dda4" stop-opacity=".13"/></linearGradient><linearGradient id="lossFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#fb6978" stop-opacity=".10"/><stop offset="100%" stop-color="#fb6978" stop-opacity=".48"/></linearGradient><clipPath id="positiveClip"><rect x="' + plot.left + '" y="' + plot.top + '" width="' + plot.width + '" height="' + positiveHeight + '"/></clipPath><clipPath id="negativeClip"><rect x="' + plot.left + '" y="' + negativeStart + '" width="' + plot.width + '" height="' + negativeHeight + '"/></clipPath></defs>';
    for (let index = 0; index <= 6; index++) {
      const amount = low + (high - low) * index / 6;
      const yy = y(amount);
      content += '<line x1="' + plot.left + '" y1="' + yy.toFixed(1) + '" x2="' + (plot.left + plot.width) + '" y2="' + yy.toFixed(1) + '" stroke="#283344" stroke-width="1"/>';
      content += '<text x="70" y="' + (yy + 4).toFixed(1) + '" fill="#a2b0c5" font-size="11" text-anchor="end">' + money(amount) + "</text>";
    }
    for (let index = 0; index <= 7; index++) {
      const price = lower + (upper - lower) * index / 7;
      const xx = x(price);
      content += '<line x1="' + xx.toFixed(1) + '" y1="' + plot.top + '" x2="' + xx.toFixed(1) + '" y2="' + (plot.top + plot.height) + '" stroke="#202b3a" stroke-width="1"/>';
      content += '<text x="' + xx.toFixed(1) + '" y="375" fill="#a2b0c5" font-size="11" text-anchor="middle">' + priceFormat(price) + "</text>";
    }
    const bellYears = Math.max(years, 0.8 / 365);
    const deviation = spot * Math.max(atmIv + state.ivShift / 100, 0.01) * Math.sqrt(bellYears);
    const bell = samples.map((price) => Math.exp(-0.5 * ((price - spot) / Math.max(deviation, 0.001)) ** 2));
    const bellPath = bell.map((value, index) => (index ? "L" : "M") + x(samples[index]).toFixed(1) + "," + (plot.top + plot.height - value * 60).toFixed(1)).join(" ") + " L" + x(upper).toFixed(1) + "," + (plot.top + plot.height) + " L" + x(lower).toFixed(1) + "," + (plot.top + plot.height) + " Z";
    content += '<path d="' + bellPath + '" fill="#487dcc" opacity=".13"/>';
    content += '<path d="' + areaPath + '" fill="url(#profitFill)" clip-path="url(#positiveClip)"/><path d="' + areaPath + '" fill="url(#lossFill)" clip-path="url(#negativeClip)"/>';
    content += '<line x1="' + plot.left + '" x2="' + (plot.left + plot.width) + '" y1="' + zero.toFixed(1) + '" y2="' + zero.toFixed(1) + '" stroke="#9aaac0" stroke-width="1.15"/>';
    state.legs.forEach((leg) => {
      if (leg.strike >= lower && leg.strike <= upper) content += '<line x1="' + x(leg.strike).toFixed(1) + '" x2="' + x(leg.strike).toFixed(1) + '" y1="' + plot.top + '" y2="' + (plot.top + plot.height) + '" stroke="' + (leg.type === "call" ? "#29d6a2" : "#ff6f80") + '" opacity=".34" stroke-dasharray="3 5"/>';
    });
    if (data.expected_lower >= lower && data.expected_lower <= upper) content += '<line x1="' + x(data.expected_lower).toFixed(1) + '" x2="' + x(data.expected_lower).toFixed(1) + '" y1="' + plot.top + '" y2="' + (plot.top + plot.height) + '" stroke="#78a2ed" stroke-dasharray="7 6" opacity=".55"/>';
    if (data.expected_upper >= lower && data.expected_upper <= upper) content += '<line x1="' + x(data.expected_upper).toFixed(1) + '" x2="' + x(data.expected_upper).toFixed(1) + '" y1="' + plot.top + '" y2="' + (plot.top + plot.height) + '" stroke="#78a2ed" stroke-dasharray="7 6" opacity=".55"/>';
    content += '<line x1="' + x(spot).toFixed(1) + '" x2="' + x(spot).toFixed(1) + '" y1="' + plot.top + '" y2="' + (plot.top + plot.height) + '" stroke="#6ebcff" stroke-width="1.5" stroke-dasharray="5 5"/>';
    content += '<path d="' + expiryPath + '" fill="none" stroke="#eef3fb" stroke-width="2.5"/><path d="' + scenarioPath + '" fill="none" stroke="#63aeff" stroke-width="2.35"/>';
    const targetX = x(Math.min(Math.max(state.target, lower), upper));
    const targetValue = payoff(state.target, years, true);
    content += '<line x1="' + targetX.toFixed(1) + '" x2="' + targetX.toFixed(1) + '" y1="' + plot.top + '" y2="' + (plot.top + plot.height) + '" stroke="#efc76d" opacity=".77"/>';
    content += '<circle cx="' + targetX.toFixed(1) + '" cy="' + y(targetValue).toFixed(1) + '" r="5" fill="#f5ce78" stroke="#141b26" stroke-width="2"/>';
    content += '<text x="79" y="396" fill="#a9b6c8" font-size="11">— Blanco: vencimiento</text><text x="272" y="396" fill="#71b4ff" font-size="11">— Azul: día seleccionado</text><text x="506" y="396" fill="#e8c26f" font-size="11">Objetivo: ' + priceFormat(state.target) + " · " + money(targetValue) + "</text>";
    svg.innerHTML = content;
  };

  const renderTable = () => {
    const box = byId("profit-table");
    const columns = [...new Set(Array.from({ length: 8 }, (_, index) => Math.round(totalDays * index / 7)))];
    const lower = Math.max(spot * (1 - state.rangePercent / 100), 0.01);
    const upper = spot * (1 + state.rangePercent / 100);
    const prices = Array.from({ length: 15 }, (_, index) => upper - (upper - lower) * index / 14);
    const grid = document.createElement("div");
    grid.className = "heat-grid";
    grid.style.gridTemplateColumns = "80px repeat(" + columns.length + ", minmax(68px, 1fr))";
    const values = [];
    prices.forEach((price) => columns.forEach((elapsed) => values.push(payoff(price, Math.max(totalDays - elapsed, 0) / 365, true))));
    const limit = Math.max(...values.map((value) => Math.abs(value)), 1);
    const cell = (className, text) => {
      const node = document.createElement("div");
      node.className = className;
      node.textContent = text;
      return node;
    };
    grid.appendChild(cell("heat-header", symbol));
    columns.forEach((elapsed) => grid.appendChild(cell("heat-header", elapsed === totalDays ? "VENCE" : "+" + elapsed + " D")));
    prices.forEach((price) => {
      grid.appendChild(cell("heat-price", priceFormat(price)));
      columns.forEach((elapsed) => {
        const value = payoff(price, Math.max(totalDays - elapsed, 0) / 365, true);
        const box = cell("heat-cell", (value >= 0 ? "+" : "") + Math.round(value).toLocaleString("en-US"));
        const intensity = 0.26 + Math.min(Math.abs(value) / limit, 1) * 0.72;
        box.style.background = value >= 0 ? "rgba(16, 170, 119," + intensity + ")" : "rgba(224, 70, 90," + intensity + ")";
        grid.appendChild(box);
      });
    });
    box.replaceChildren(grid);
  };

  const renderGreeks = () => {
    const totals = { delta: 0, gamma: 0, theta: 0, vega: 0 };
    state.legs.forEach((leg) => {
      const option = optionFor(leg.type, leg.strike) || {};
      Object.keys(totals).forEach((name) => totals[name] += signFor(leg) * Number(option[name] || 0) * leg.contracts * 100);
    });
    const expected = spot * atmIv * Math.sqrt(Math.max(totalDays, 0.15) / 365);
    byId("live-greeks").innerHTML = '<span>DELTA <strong>' + totals.delta.toFixed(2) + '</strong></span><span>GAMMA <strong>' + totals.gamma.toFixed(3) + '</strong></span><span>THETA <strong>' + totals.theta.toFixed(2) + '</strong></span><span>VEGA <strong>' + totals.vega.toFixed(2) + '</strong></span><span>MOV. ESPERADO <strong>±' + priceFormat(expected) + "</strong></span>";
  };

  const syncControls = () => {
    byId("target-slider").value = String(Math.round((state.target / spot - (1 - state.rangePercent / 100)) / (2 * state.rangePercent / 100) * 1000));
    byId("days-slider").max = String(Math.max(totalDays, 1));
    byId("days-slider").value = String(state.elapsed);
    byId("iv-slider").value = String(state.ivShift);
    byId("range-slider").value = String(Math.round(state.rangePercent));
    byId("target-label").textContent = priceFormat(state.target);
    byId("days-label").textContent = state.elapsed + " / " + totalDays;
    byId("iv-label").textContent = (atmIv * 100 + state.ivShift).toFixed(1) + "%";
    byId("range-label").textContent = "±" + state.rangePercent.toFixed(0) + "%";
  };
  function renderAll(rebuildSliders = true) {
    renderRail();
    if (rebuildSliders) renderLegSliders();
    renderStats();
    renderChart();
    renderGreeks();
    syncControls();
  }

  byId("target-slider").oninput = (event) => {
    state.target = spot * (1 - state.rangePercent / 100 + Number(event.target.value) / 1000 * 2 * state.rangePercent / 100);
    renderChart();
    syncControls();
  };
  byId("target-slider").onchange = commit;
  byId("days-slider").oninput = (event) => { state.elapsed = Number(event.target.value); renderChart(); syncControls(); };
  byId("days-slider").onchange = commit;
  byId("iv-slider").oninput = (event) => { state.ivShift = Number(event.target.value); renderChart(); syncControls(); };
  byId("iv-slider").onchange = commit;
  byId("range-slider").oninput = (event) => { state.rangePercent = Number(event.target.value); renderAll(); };
  byId("range-slider").onchange = commit;
  byId("graph-mode").onclick = () => { state.mode = "graph"; renderChart(); commit(); };
  byId("table-mode").onclick = () => { state.mode = "table"; renderChart(); commit(); };
  byId("payoff-chart").onpointermove = (event) => {
    if (!graphMapping) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const localX = (event.clientX - rect.left) / Math.max(rect.width, 1) * 920;
    if (localX < graphMapping.plot.left || localX > graphMapping.plot.left + graphMapping.plot.width) return;
    const price = graphMapping.lower + (localX - graphMapping.plot.left) / graphMapping.plot.width * (graphMapping.upper - graphMapping.lower);
    const result = payoff(price, graphMapping.years, true);
    const tooltip = byId("chart-tooltip");
    tooltip.innerHTML = symbol + " " + priceFormat(price) + "<br><b>" + money(result) + "</b>";
    tooltip.style.left = Math.min(Math.max(event.clientX - rect.left + 12, 8), rect.width - 118) + "px";
    tooltip.style.top = Math.max(event.clientY - rect.top - 48, 8) + "px";
    tooltip.classList.remove("hidden");
  };
  byId("payoff-chart").onpointerleave = () => byId("chart-tooltip").classList.add("hidden");
  renderDates();
  setStrikeZoom(state.strikeZoomPinned);
  renderAll();
}
"""


def component_state_value(component_key, field, default=None):
    state = st.session_state.get(component_key)
    if state is None:
        return default
    if isinstance(state, dict):
        return state.get(field, default)
    try:
        return state.get(field, default)
    except (AttributeError, TypeError):
        return getattr(state, field, default)


def apply_visual_selection(frame, index, selection, expiration):
    if not isinstance(selection, dict) or selection.get("expiration") != expiration:
        return frame
    selected_legs = selection.get("legs")
    if not isinstance(selected_legs, list) or not selected_legs:
        return frame
    rows = []
    for leg in selected_legs:
        action = str(leg.get("action") or "").upper()
        option_type = str(leg.get("type") or "").lower()
        strike = defender.number(leg.get("strike"))
        if action not in {"COMPRAR", "VENDER"} or option_type not in {"put", "call"}:
            return frame
        option = defender.get_option(index, option_type, strike)
        if option is None:
            return frame
        rows.append(
            {
                "Acción": action,
                "Tipo": option_type.upper(),
                "Strike": float(strike),
                "Prima": round(defender.number(leg.get("premium"), defender.option_midpoint(option)), 2),
                "Contratos": max(defender.integer(leg.get("contracts")), 1),
            }
        )
    return pd.DataFrame(rows)


def create_visual_payload(symbol, spot, strategy, expiration, expirations, options, legs, expected, graph_range, selection):
    limited = []
    radius = max(float(graph_range) * 1.8, float(spot) * 0.22, 10)
    selected_strikes = {float(leg["strike"]) for leg in legs}
    for option in options:
        strike = defender.number(option.get("strike"))
        option_type = str(option.get("option_type") or "").lower()
        if option_type not in {"put", "call"} or (abs(strike - spot) > radius and strike not in selected_strikes):
            continue
        greeks = option.get("greeks") or {}
        limited.append(
            {
                "type": option_type,
                "strike": strike,
                "mid": defender.option_midpoint(option),
                "bid": defender.number(option.get("bid")),
                "ask": defender.number(option.get("ask")),
                "iv": option_implied_volatility(option) or expected.get("atm_iv") or 0.20,
                "oi": defender.integer(option.get("open_interest")),
                "volume": defender.integer(option.get("volume")),
                "delta": defender.number(greeks.get("delta")),
                "gamma": defender.number(greeks.get("gamma")),
                "theta": defender.number(greeks.get("theta")),
                "vega": defender.number(greeks.get("vega")),
            }
        )
    return {
        "symbol": symbol,
        "spot": float(spot),
        "strategy": strategy,
        "expiration": expiration,
        "expirations": list(expirations),
        "days": defender.calculate_days_remaining(expiration) or 0,
        "options": limited,
        "legs": [
            {
                "action": leg["action"],
                "type": leg["type"],
                "strike": leg["strike"],
                "premium": leg["premium"],
                "contracts": leg["contracts"],
                "iv": leg["iv"],
            }
            for leg in legs
        ],
        "selection": selection if isinstance(selection, dict) else {},
        "atm_iv": expected.get("atm_iv") or 0.20,
        "expected_lower": expected.get("expiry_lower"),
        "expected_upper": expected.get("expiry_upper"),
        "range_percent": min(max(float(graph_range) / max(float(spot), 0.01) * 100, 2), 40),
        "rate": 0.04,
    }


def render_interactive_builder(payload, component_key):
    components = getattr(st, "components", None)
    version_two = getattr(components, "v2", None)
    register = getattr(version_two, "component", None)
    if callable(register):
        component = register(
            "options_defender_live_builder",
            html=LIVE_BUILDER_HTML,
            css=LIVE_BUILDER_CSS,
            js=LIVE_BUILDER_JS,
        )
        return component(
            data=payload,
            default={"selection": payload.get("selection") or {}, "expiration": payload["expiration"]},
            on_selection_change=lambda: None,
            on_expiration_change=lambda: None,
            key=component_key,
        )

    import streamlit.components.v1 as legacy_components

    javascript = LIVE_BUILDER_JS.replace(
        "export default function(component)", "function initializeDefenderBuilder(component)", 1
    )
    encoded = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    document = (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        + LIVE_BUILDER_CSS
        + "</style></head><body style='margin:0;background:#0a0f18'>"
        + LIVE_BUILDER_HTML
        + "<script>"
        + javascript
        + "\ninitializeDefenderBuilder({parentElement:document,data:"
        + encoded
        + ",setStateValue:null});</script></body></html>"
    )
    legacy_components.html(document, height=1060, scrolling=True)
    st.caption(
        "Si quieres guardar automáticamente los strikes arrastrados y cambiar vencimientos desde el gráfico, "
        "actualiza Streamlit con: python -m pip install --upgrade streamlit"
    )
    return None


def simulator_strike_ladder(frame, legs, spx, graph_range):
    radius = min(max(graph_range / 2, 45), 130)
    selected = frame[(frame["Strike"] >= spx - radius) & (frame["Strike"] <= spx + radius)].copy()
    if selected.empty:
        return

    selected["Interés"] = selected.apply(
        lambda row: row["Open interest"] if row["Tipo"] == "CALL" else -row["Open interest"], axis=1
    )
    bars = alt.Chart(selected).mark_bar(opacity=0.76, cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X(
            "Strike:O",
            title=None,
            axis=alt.Axis(labelAngle=-35, labelOverlap=True, labelColor="#b4c2d6", labelFontSize=11),
        ),
        y=alt.Y("Interés:Q", title=None, axis=None),
        color=alt.Color(
            "Tipo:N", scale=alt.Scale(domain=["CALL", "PUT"], range=["#24d6a0", "#ff6477"]), legend=None
        ),
        tooltip=["Strike:O", "Tipo:N", "Open interest:Q"],
    )
    maximum_interest = max(selected["Interés"].abs().max(), 1)
    markers = pd.DataFrame(
        [
            {
                "Strike": leg["strike"],
                "Interés": maximum_interest * (0.84 if leg["type"] == "call" else -0.84),
                "Acción": leg["action"],
                "Detalle": f'{leg["action"]} {leg["type"].upper()} {leg["strike"]:.0f}',
            }
            for leg in legs
            if spx - radius <= leg["strike"] <= spx + radius
        ]
    )
    chart = bars
    if not markers.empty:
        dots = alt.Chart(markers).mark_point(size=210, filled=True, stroke="#0b1019", strokeWidth=1.6).encode(
            x="Strike:O",
            y="Interés:Q",
            shape=alt.Shape(
                "Acción:N", scale=alt.Scale(domain=["COMPRAR", "VENDER"], range=["triangle-up", "triangle-down"]), legend=None
            ),
            color=alt.Color(
                "Acción:N", scale=alt.Scale(domain=["COMPRAR", "VENDER"], range=["#76b6ff", "#f7d275"]), legend=None
            ),
            tooltip=["Detalle:N"],
        )
        chart += dots
    st.altair_chart(
        chart.properties(height=185).configure_view(strokeWidth=0).configure_axis(gridColor="#263142"),
        use_container_width=True,
    )


def simulator_chart(legs, spx, years, iv_change, rate, graph_range, expected, summary):
    lower = max(spx - graph_range, 0)
    upper = spx + graph_range
    steps = 150
    prices = [lower + (upper - lower) * number / steps for number in range(steps + 1)]
    rows = []
    for price in prices:
        rows.append({"SPX": price, "Resultado": simulator_expiration_pnl(legs, price), "Curva": "Al vencimiento"})
        rows.append(
            {
                "SPX": price,
                "Resultado": simulator_scenario_pnl(legs, price, years, iv_change, rate),
                "Curva": "Escenario seleccionado",
            }
        )
    frame = pd.DataFrame(rows)
    expiration_frame = frame[frame["Curva"] == "Al vencimiento"]
    area = payoff_color_layers(
        expiration_frame,
        "SPX",
        alt.X("SPX:Q", title=f"Precio de {selected_symbol()}", scale=alt.Scale(zero=False)),
        opacity=0.27,
    )
    lines = alt.Chart(frame).mark_line(strokeWidth=3).encode(
        x=alt.X("SPX:Q", title=f"Precio de {selected_symbol()}", scale=alt.Scale(zero=False)),
        y=alt.Y("Resultado:Q", title="Ganancia / pérdida ($)"),
        color=alt.Color(
            "Curva:N",
            scale=alt.Scale(
                domain=["Al vencimiento", "Escenario seleccionado"],
                range=["#eaf0fa", "#63b4ff"],
            ),
        ),
        tooltip=[
            alt.Tooltip("SPX:Q", format=",.2f"),
            alt.Tooltip("Resultado:Q", format=",.2f"),
            "Curva:N",
        ],
    )
    zero = alt.Chart(pd.DataFrame({"Resultado": [0]})).mark_rule(color="#90a0b8", opacity=0.8).encode(y="Resultado:Q")
    level_rows = [{"SPX": spx, "Nombre": f"{selected_symbol()} actual", "Color": "#38bdf8"}]
    for value, name, color in (
        (summary.get("put_wall"), "Put wall", "#22c55e"),
        (summary.get("call_wall"), "Call wall", "#ef4444"),
        (summary.get("mvs"), "MVS · Most Valuable Strike", "#fb923c"),
        (expected.get("expiry_lower"), "Rango esperado inferior", "#86efac"),
        (expected.get("expiry_upper"), "Rango esperado superior", "#fca5a5"),
        (expected.get("gamma_magnet"), "Imán gamma", "#facc15"),
    ):
        if value is not None and lower <= value <= upper:
            level_rows.append({"SPX": value, "Nombre": name, "Color": color})

    levels = alt.Chart(pd.DataFrame(level_rows)).mark_rule(strokeDash=[6, 5], strokeWidth=1.5).encode(
        x="SPX:Q",
        color=alt.Color("Color:N", scale=None),
        tooltip=["Nombre:N", alt.Tooltip("SPX:Q", format=",.2f")],
    )
    breakevens = simulator_bounds(legs, spx)["breakevens"]
    crossing_rows = pd.DataFrame(
        [{"SPX": point, "Nombre": f"Breakeven {point:,.2f}"} for point in breakevens if lower <= point <= upper]
    )
    chart = area + lines + zero + levels
    if not crossing_rows.empty:
        crossings = alt.Chart(crossing_rows).mark_rule(color="#78b7ff", strokeDash=[3, 3], opacity=0.74).encode(
            x="SPX:Q", tooltip=["Nombre:N"]
        )
        chart += crossings
    chart = (
        chart.properties(height=455)
        .interactive()
        .configure_view(strokeWidth=0)
        .configure_axis(gridColor="#253042", domainColor="#344155", tickColor="#344155", labelColor="#a2b0c4", titleColor="#b7c3d4")
        .configure_legend(labelColor="#d7dfeb", titleColor="#d7dfeb")
    )
    st.altair_chart(chart, use_container_width=True)


def simulator_heatmap(legs, spx, total_days, iv_change, rate, graph_range, expiration=None, mode="Ganancia $", risk_basis=None):
    prices = [spx - graph_range + 2 * graph_range * number / 16 for number in range(17)]
    elapsed_points = sorted({int(round(total_days * number / 7)) for number in range(8)})
    start_day = date.today()
    if expiration:
        try:
            start_day = date.fromisoformat(expiration) - timedelta(days=total_days)
        except (TypeError, ValueError):
            pass
    cash_basis = abs(simulator_entry_cashflow(legs))
    risk_basis = abs(float(risk_basis or 0))
    rows = []
    for elapsed in elapsed_points:
        years = max(total_days - elapsed, 0) / 365
        target_day = start_day + timedelta(days=elapsed)
        date_label = "VENCE" if elapsed == total_days else target_day.strftime("%d %b").upper()
        for price in prices:
            value = simulator_scenario_pnl(legs, price, years, iv_change, rate)
            if mode == "% Retorno":
                shown_value = value / max(cash_basis, 1) * 100
                label = f"{shown_value:+.0f}%"
            elif mode == "% Riesgo":
                shown_value = value / max(risk_basis or cash_basis, 1) * 100
                label = f"{shown_value:+.0f}%"
            else:
                shown_value = value
                label = f"{value:+,.0f}"
            is_current = abs(price - spx) < graph_range / 20
            rows.append(
                {
                    "Precio": round(price, 1),
                    "SPX": ("● " if is_current else "") + f"{price:,.0f}",
                    "Fecha": date_label,
                    "Días": elapsed,
                    "P&L $": value,
                    "Valor": shown_value,
                    "Celda": label,
                    "Movimiento": (price / spx - 1) * 100,
                }
            )
    frame = pd.DataFrame(rows)
    limit = max(float(frame["Valor"].abs().quantile(0.86)), 1)
    date_order = [
        "VENCE" if elapsed == total_days else (start_day + timedelta(days=elapsed)).strftime("%d %b").upper()
        for elapsed in elapsed_points
    ]
    chart = alt.Chart(frame).mark_rect(cornerRadius=3, stroke="#101722", strokeWidth=1.7).encode(
        x=alt.X(
            "Fecha:O",
            sort=date_order,
            title=None,
            axis=alt.Axis(orient="top", labelAngle=0, labelColor="#b0bdd0", labelPadding=9, ticks=False, domain=False),
        ),
        y=alt.Y(
            "SPX:O",
            sort=alt.SortField(field="Precio", order="descending"),
            title=f"PRECIO {selected_symbol()}",
            axis=alt.Axis(labelColor="#a6b5c8", labelPadding=7, titleColor="#90a0b8", ticks=False, domain=False),
        ),
        color=alt.Color(
            "Valor:Q",
            scale=alt.Scale(domain=[-limit, 0, limit], range=["#bd364a", "#26313f", "#078964"], clamp=True),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("Precio:Q", title=selected_symbol(), format=",.1f"),
            "Fecha:N",
            alt.Tooltip("Movimiento:Q", title="Movimiento %", format="+.2f"),
            alt.Tooltip("P&L $:Q", title="Ganancia / pérdida", format="+,.2f"),
        ],
    )
    labels = chart.mark_text(fontSize=10, fontWeight=600).encode(text="Celda:N", color=alt.value("#f4f7fc"))
    st.altair_chart(
        (chart + labels).properties(height=455).configure_view(strokeWidth=0),
        use_container_width=True,
    )


def save_simulated_spreads(legs, expiration, market_context=None):
    saved = []
    for option_type, strategy in (("put", "PCS"), ("call", "CCS")):
        sold = [leg for leg in legs if leg["type"] == option_type and leg["action"] == "VENDER"]
        bought = [leg for leg in legs if leg["type"] == option_type and leg["action"] == "COMPRAR"]
        if len(sold) != 1 or len(bought) != 1:
            continue
        if sold[0]["contracts"] != bought[0]["contracts"]:
            continue
        credit = sold[0]["premium"] - bought[0]["premium"]
        if credit <= 0:
            continue
        position = validate_position(
            strategy, sold[0]["strike"], bought[0]["strike"], credit, sold[0]["contracts"]
        )
        saved.append(save_trade(position, expiration, source="simulador", market_context=market_context))
    if not saved:
        raise RuntimeError("Solo pueden guardarse PCS, CCS o iron condors con crédito positivo y cantidades iguales.")
    return saved


def render_defenses(position, expiration, expirations, spx, analysis, index, gamma_levels):
    if analysis["pnl"] >= 0:
        st.success("POSICIÓN EN GANANCIA. NO HACER NADA.")
        return
    trigger = defender.DEFENSE_TRIGGER_PERCENT
    if analysis["loss_percent"] < trigger:
        st.warning("PÉRDIDA CONTROLADA. NO DEFENDER TODAVÍA.")
        remaining = analysis["trigger_loss"] - abs(analysis["pnl"])
        if remaining > 0:
            st.write(f"La defensa se activaría si pierdes aproximadamente {money(remaining)} adicionales.")
        return

    st.error(f"PÉRDIDA SUPERIOR AL {trigger:.0f} %. BUSCANDO DEFENSAS.")
    try:
        defenses, alternatives = defender.find_defenses(
            SymbolTradierClient(position.get("symbol") or selected_symbol()),
            position,
            analysis,
            index,
            expiration,
            expirations,
            spx,
            gamma_levels,
        )
    except Exception as error:
        st.error(f"No se pudieron buscar defensas: {error}")
        return
    if not defenses:
        st.warning("No se encontró una defensa adecuada.")
        return
    if alternatives:
        st.warning("Algunas defensas utilizan un vencimiento diferente y pueden aumentar el riesgo.")

    st.subheader("Defensas recomendadas")
    for number, defense in enumerate(defenses[: defender.MAX_RECOMMENDATIONS], start=1):
        st.markdown(f"**Defensa {number}: {defense['strategy']} {defense['short_strike']:.0f}/{defense['long_strike']:.0f}**")
        first, second = st.columns(2)
        first.metric("Crédito adicional", money(defense["total_credit"]))
        second.metric(f"Distancia desde {position.get('symbol') or selected_symbol()}", f"{defense['distance']:.1f} puntos")
        if defense["same_expiration"]:
            st.write(f"Riesgo antes: **{money(analysis['max_loss'])}** · Riesgo después: **{money(defense['maximum_combined_loss'])}**")
        else:
            st.warning(f"Vencimiento distinto: {defense['expiration']}.")


st.session_state.setdefault("active_symbol", "SPX")
with st.sidebar:
    st.title("🛡️ OPTIONS DEFENDER")
    active_symbol = selected_symbol()
    symbol_query = st.text_input(
        "🔎 Acción, ETF o índice",
        value=active_symbol,
        placeholder="SPY, QQQ, AAPL, NVDA, TSLA…",
        key="universal_symbol_search",
    ).strip()
    candidate_symbol = symbol_query.upper() or active_symbol
    if symbol_query and symbol_query.upper() != active_symbol:
        try:
            matches = search_symbols(symbol_query)
            if matches:
                labels = [f"{item['symbol']} · {item['description']}" for item in matches]
                choice = st.selectbox("Resultados encontrados", labels, key=f"symbol_matches_{symbol_query}")
                candidate_symbol = matches[labels.index(choice)]["symbol"]
        except Exception:
            st.caption("Puedes escribir directamente el símbolo y cargarlo.")
    if st.button("CARGAR SÍMBOLO", use_container_width=True):
        if not re.fullmatch(r"[A-Z0-9./^_-]{1,16}", candidate_symbol):
            st.error("Escribe un símbolo válido.")
        else:
            st.session_state["active_symbol"] = candidate_symbol
            clear_data()
            st.rerun()
    st.caption("Ejemplos: SPX · SPY · QQQ · IWM · AAPL · NVDA · TSLA")
    st.divider()
    sandbox_connection = "sandbox" in str(getattr(defender, "BASE_URL", "")).lower()
    with st.expander("⚡ Conexión de datos", expanded=sandbox_connection):
        if sandbox_connection:
            st.warning("Sandbox entrega precios con aproximadamente 15 minutos de atraso.")
            st.caption("Conecta el API token de tu cuenta real para recibir datos disponibles en tiempo real.")
            st.markdown("[Abrir configuración API de Tradier](https://web.tradier.com/user/api)")
            brokerage_token = st.text_input(
                "API token de cuenta real",
                type="password",
                key="tradier_brokerage_token_input",
                help="Pega aquí el token de la cuenta real, no el de Paper Trading o Sandbox.",
            )
            if st.button("ACTIVAR DATOS REALES", use_container_width=True):
                try:
                    change_tradier_connection(TRADIER_BROKERAGE_URL, brokerage_token)
                except RuntimeError as error:
                    st.error(str(error))
        else:
            st.success("Tradier Brokerage conectado.")
            st.caption("Las acciones y ETF pueden recibir datos en tiempo real; algunos índices pueden tener restricciones.")
            if st.button("VOLVER A SANDBOX", use_container_width=True):
                try:
                    change_tradier_connection(TRADIER_SANDBOX_URL)
                except RuntimeError as error:
                    st.error(str(error))
    st.divider()
    page = st.radio(
        "Selecciona una sección",
        ["📈 Mercado", "💡 Ideas de trades", "📊 Simulador de opciones", "📋 Mis operaciones"],
        label_visibility="collapsed",
    )

try:
    with st.spinner(f"Cargando {selected_symbol()} desde Tradier..."):
        current_spx = load_spx(selected_symbol())
        expirations = load_expirations(selected_symbol())
except Exception as error:
    st.error(f"No se pudo cargar {selected_symbol()}: {error}")
    st.info("Prueba otro símbolo en el buscador lateral y verifica que tenga opciones disponibles.")
    st.stop()


with st.sidebar:
    st.divider()
    st.metric(f"{selected_symbol()} actual", f"{current_spx:,.2f}")
    if st.button("🔄 Actualizar datos", use_container_width=True):
        clear_data()
        st.rerun()
    if "sandbox" in str(getattr(defender, "BASE_URL", "")).lower():
        st.caption("Conexión: Tradier Sandbox · Datos atrasados aproximadamente 15 minutos.")
    else:
        st.caption("Conexión: Tradier Brokerage · Datos disponibles en tiempo real.")
    try:
        opened_count = sum(trade.get("status") == "OPEN" for trade in read_trades())
        st.caption(f"Operaciones abiertas guardadas: {opened_count}")
    except RuntimeError as error:
        st.error(str(error))


if page == "📈 Mercado":
    st.title(f"📈 Mercado {selected_symbol()}")
    first_setting, second_setting, third_setting = st.columns(3)
    market_expiration = first_setting.selectbox("Vencimiento", expirations, format_func=expiration_name)
    interval = second_setting.selectbox(
        "Velas",
        list(CANDLE_INTERVAL_LABELS),
        index=1,
        format_func=lambda value: CANDLE_INTERVAL_LABELS[value],
    )
    strike_range = third_setting.select_slider("Rango de strikes", options=[50, 75, 100, 150, 200, 300, 400], value=100)
    with st.expander("🎛️ Configurar gráfico profesional", expanded=False):
        first_option, second_option, third_option, fourth_option, fifth_option, sixth_option = st.columns(6)
        chart_settings = {
            "ema9": first_option.checkbox("EMA 9", value=True),
            "ema21": second_option.checkbox("EMA 21", value=True),
            "vwap": third_option.checkbox("VWAP", value=True),
            "volume": fourth_option.checkbox("Volumen", value=True),
            "levels": fifth_option.checkbox("Niveles", value=True),
            "expected_range": sixth_option.checkbox("Rango esperado", value=True),
        }
        chart_settings["visible_candles"] = st.select_slider(
            "🔍 Zoom del gráfico · velas visibles",
            options=[30, 45, 60, 80, 100, 120, 150, 180],
            value=80,
            help="Menos velas las muestra más grandes; más velas permite ver un período más amplio.",
        )

    def market_panel():
        try:
            spx = load_spx(selected_symbol())
            options = load_chain(market_expiration, selected_symbol())
            summary = summarize_chain(options, spx, strike_range)
            expected = calculate_expected_levels(
                options, spx, market_expiration, summary["frame"], strike_range
            )
        except Exception as error:
            st.error(f"No se pudo cargar el mercado: {error}")
            return

        first, second, third, fourth, fifth, sixth = st.columns(6)
        first.metric(f"{selected_symbol()} actual", f"{spx:,.2f}")
        second.metric("Put wall", f"{summary['put_wall']:,.0f}" if summary["put_wall"] is not None else "N/D")
        third.metric("Call wall", f"{summary['call_wall']:,.0f}" if summary["call_wall"] is not None else "N/D")
        fourth.metric(
            "MVS · strike clave",
            f"{summary['mvs']:,.0f}" if summary["mvs"] is not None else "N/D",
            help="Most Valuable Strike estimado: strike con mayor valor combinado en primas abiertas CALL y PUT.",
        )
        fifth.metric("Gamma neta", compact(summary["gamma_levels"]["net_gamma"]) if summary["has_greeks"] else "N/D")
        ratio = summary["put_oi"] / summary["call_oi"] if summary["call_oi"] else None
        sixth.metric("Put/Call OI", f"{ratio:.2f}" if ratio is not None else "N/D")

        st.subheader("🎯 Movimiento esperado y estructura gamma")
        first, second, third, fourth, fifth = st.columns(5)
        first.metric(
            "Movimiento esperado hoy",
            f"±{expected['daily_move']:,.1f} puntos" if expected["daily_move"] is not None else "N/D",
        )
        second.metric(
            "Límite esperado inferior",
            f"{expected['daily_lower']:,.1f}" if expected["daily_lower"] is not None else "N/D",
        )
        third.metric(
            "Límite esperado superior",
            f"{expected['daily_upper']:,.1f}" if expected["daily_upper"] is not None else "N/D",
        )
        fourth.metric(
            "Imán gamma",
            f"{expected['gamma_magnet']:,.0f}" if expected["gamma_magnet"] is not None else "N/D",
        )
        fifth.metric(
            "Gamma flip estimado",
            f"{expected['gamma_flip']:,.1f}" if expected["gamma_flip"] is not None else "N/D",
        )

        if expected["expiry_move"] is not None:
            dte = defender.calculate_days_remaining(market_expiration)
            st.info(
                f"Rango esperado hasta {market_expiration} ({dte} DTE): "
                f"{expected['expiry_lower']:,.1f} — {expected['expiry_upper']:,.1f} "
                f"(±{expected['expiry_move']:,.1f} puntos)."
            )

        if expected["gamma_flip"] is not None:
            if spx >= expected["gamma_flip"]:
                st.success(f"Régimen gamma: {selected_symbol()} por encima del gamma flip estimado; posible mayor estabilidad.")
            else:
                st.warning(f"Régimen gamma: {selected_symbol()} por debajo del gamma flip estimado; posible mayor volatilidad.")
        elif summary["has_greeks"]:
            st.caption("No se identificó un cruce de gamma dentro del rango analizado.")

        chart_column, level_column = st.columns([2.8, 1])
        with chart_column:
            st.subheader("📊 Gráfico profesional del mercado")
            try:
                candles = load_candles(interval, selected_symbol())
                try:
                    latest_quote = load_spx_quote(candles["symbol"])
                    candles = update_live_candles(candles, latest_quote)
                except Exception:
                    candles = {**candles, "is_live": False}
                if candles["symbol"] != selected_symbol():
                    st.warning(
                        "SPY se muestra como referencia porque Tradier no entregó velas de SPX. "
                        "Los niveles del SPX no se dibujan sobre un gráfico con precios distintos."
                    )
                show_candles(
                    candles,
                    summary["put_wall"],
                    summary["call_wall"],
                    expected=expected,
                    spx=spx,
                    mvs=summary["mvs"],
                    settings=chart_settings,
                )
                if candles.get("quote_delayed"):
                    age = int(candles.get("quote_age_seconds", 0))
                    elapsed = f"{age // 60} min {age % 60} s" if age >= 60 else f"{age} s"
                    if "sandbox" in str(getattr(defender, "BASE_URL", "")).lower():
                        st.warning(
                            f"🟠 Tradier Sandbox retrasa los precios aproximadamente 15 minutos. "
                            f"Último dato: {candles['quote_updated_at']} ({elapsed} de atraso). "
                            "El gráfico incluye sesiones anteriores para mostrar todas las velas disponibles. "
                            "Activa los datos reales desde la barra lateral para quitar el atraso en acciones y ETF."
                        )
                    else:
                        st.warning(
                            f"🟠 Tradier está entregando este símbolo con retraso. "
                            f"Último dato: {candles['quote_updated_at']} ({elapsed} de atraso). "
                            f"El gráfico se revisa cada {LIVE_MARKET_REFRESH_SECONDS} segundos. "
                            "Algunos índices pueden tener restricciones de datos en tiempo real."
                        )
                elif candles.get("is_live"):
                    source_update = (
                        f" · Dato de Tradier: {candles['quote_updated_at']}"
                        if candles.get("quote_updated_at")
                        else ""
                    )
                    st.caption(
                        f"🟢 Vela en formación · Último precio: {candles['live_price']:,.2f} · "
                        f"Actualizado: {candles['updated_at']}{source_update} · "
                        f"Actualización automática cada {LIVE_MARKET_REFRESH_SECONDS} segundos."
                    )
                else:
                    st.caption(
                        "⚪ Las velas se actualizarán automáticamente cuando el mercado esté abierto "
                        "y Tradier entregue una cotización disponible."
                    )
            except Exception as error:
                st.warning(f"No se pudo mostrar el gráfico: {error}")

        with level_column:
            st.subheader("Niveles")
            support = summary["gamma_levels"]["support"] if summary["has_greeks"] else None
            resistance = summary["gamma_levels"]["resistance"] if summary["has_greeks"] else None
            st.metric(
                "🟠 MVS · Most Valuable Strike",
                f"{summary['mvs']:,.0f}" if summary["mvs"] is not None else "N/D",
                delta=f"{summary['mvs'] - spx:+,.1f} puntos del precio" if summary["mvs"] is not None else None,
                delta_color="off",
            )
            if summary["mvs_method"] == "prima_abierta" and summary["mvs_notional"] is not None:
                st.metric("Prima abierta en MVS", f"${compact(summary['mvs_notional'])}")
                if summary["mvs_share"] is not None:
                    st.caption(
                        f"Concentra {summary['mvs_share'] * 100:.1f}% del valor abierto analizado · "
                        f"{summary['mvs_oi']:,} contratos CALL + PUT."
                    )
            elif summary["mvs_method"] == "open_interest":
                st.caption("MVS aproximado por open interest: Tradier no entregó primas válidas.")
            st.metric("Soporte gamma", f"{support:,.0f}" if support is not None else "N/D")
            st.metric("Resistencia gamma", f"{resistance:,.0f}" if resistance is not None else "N/D")
            st.metric("Open interest puts", compact(summary["put_oi"]))
            st.metric("Open interest calls", compact(summary["call_oi"]))
            st.metric(
                "Volatilidad implícita ATM",
                f"{expected['atm_iv'] * 100:.1f}%" if expected["atm_iv"] else "N/D",
            )
            st.metric(
                "Straddle ATM",
                f"{expected['straddle_price']:,.2f}" if expected["straddle_price"] else "N/D",
            )

        with st.expander("Mapa de posiciones y cadena de opciones"):
            show_oi_chart(summary["frame"], mvs=summary["mvs"])
            st.dataframe(summary["frame"].sort_values(["Strike", "Tipo"]), use_container_width=True, hide_index=True)
            st.caption(
                "MVS estimado = strike con mayor suma de (prima media × open interest × multiplicador) "
                "para CALL y PUT del vencimiento y rango seleccionados."
            )
        st.caption(
            f"Actualizado: {datetime.now().strftime('%I:%M:%S %p')} · {expected['method']}. "
            "MVS y gamma flip son niveles estimados; no representan una predicción garantizada."
        )

    use_fragment(market_panel, LIVE_MARKET_REFRESH_SECONDS)
    st.divider()
    st.subheader("Analizar una operación")
    reference = nearest_strike(current_spx)
    market_settings = adaptive_strategy_settings(current_spx)
    default_short = max(reference - market_settings["default_distance"], market_settings["step"] * 2)
    default_long = max(default_short - market_settings["default_width"], market_settings["step"])
    with st.form("analyze_position_form"):
        first, second, third = st.columns(3)
        strategy = first.selectbox("Estrategia", ["PCS", "CCS"])
        expiration = second.selectbox("Vencimiento de la operación", expirations, format_func=expiration_name)
        contracts = third.number_input("Contratos", min_value=1, value=1)
        fourth, fifth, sixth = st.columns(3)
        short_strike = fourth.number_input(
            "Strike vendido", min_value=0.0, value=float(default_short), step=float(market_settings["step"])
        )
        long_strike = fifth.number_input(
            "Strike comprado", min_value=0.0, value=float(default_long), step=float(market_settings["step"])
        )
        credit = sixth.number_input("Crédito recibido", min_value=0.01, value=1.50, step=0.05)
        analyze = st.form_submit_button("ANALIZAR OPERACIÓN", use_container_width=True)

    if analyze:
        try:
            position = validate_position(strategy, short_strike, long_strike, credit, contracts)
            spx = load_spx(selected_symbol())
            options = load_chain(expiration, selected_symbol())
            index = defender.build_option_index(options)
            analysis = defender.analyze_position(position, index, spx)
            levels = defender.calculate_gamma_levels(options, spx)
            first, second, third, fourth = st.columns(4)
            first.metric("Resultado actual", money(analysis["pnl"]))
            second.metric("Riesgo máximo", money(analysis["max_loss"]))
            third.metric("Pérdida sobre riesgo", f"{analysis['loss_percent']:.1f}%")
            fourth.metric("Delta", f"{analysis['short_delta']:+.3f}")
            render_defenses(position, expiration, expirations, spx, analysis, index, levels)
        except Exception as error:
            st.error(f"No se pudo analizar la operación: {error}")


elif page == "💡 Ideas de trades":
    st.title(f"💡 Ideas automáticas de {selected_symbol()}")
    st.caption("Las ideas se recalculan cada 10 minutos solamente mientras esta sección está abierta.")
    closest_30 = min(range(len(expirations)), key=lambda index: abs((defender.calculate_days_remaining(expirations[index]) or 0) - 30))

    with st.expander("Configuración de las ideas", expanded=True):
        first, second, third = st.columns(3)
        idea_expiration = first.selectbox("Vencimiento", expirations, index=closest_30, format_func=expiration_name, key="idea_exp")
        idea_settings = adaptive_strategy_settings(current_spx)
        idea_width = second.selectbox(
            "Ancho del spread",
            idea_settings["widths"],
            index=idea_settings["widths"].index(idea_settings["default_width"]),
            key=f"idea_width_{selected_symbol()}",
        )
        idea_contracts = third.number_input("Contratos por idea", min_value=1, value=1, key="idea_contracts")
        fourth, fifth, sixth = st.columns(3)
        target_delta = fourth.slider("Delta objetivo", 0.05, 0.30, 0.12, 0.01)
        minimum_credit = fifth.number_input("Crédito mínimo por spread", min_value=0.05, value=0.75, step=0.05)
        maximum_risk = sixth.number_input("Riesgo máximo total ($)", min_value=100, value=1000, step=100)
        seventh, eighth = st.columns(2)
        require_outside_expected = seventh.checkbox(
            "Exigir strike fuera del rango esperado al vencimiento", value=False
        )
        require_behind_wall = eighth.checkbox(
            "Exigir strike protegido por put wall/call wall", value=False
        )

    if st.button("🔎 Buscar ideas ahora", use_container_width=True):
        load_spx.clear()
        load_chain.clear()
        st.rerun()

    def ideas_panel():
        try:
            ideas, summary, expected, spx = generate_ideas(
                idea_expiration,
                idea_width,
                minimum_credit,
                maximum_risk,
                target_delta,
                idea_contracts,
                require_outside_expected,
                require_behind_wall,
            )
        except Exception as error:
            st.error(f"No se pudieron generar ideas: {error}")
            return

        first, second, third = st.columns(3)
        first.metric(f"{selected_symbol()} actual", f"{spx:,.2f}")
        second.metric("Put wall", f"{summary['put_wall']:,.0f}" if summary["put_wall"] is not None else "N/D")
        third.metric("Call wall", f"{summary['call_wall']:,.0f}" if summary["call_wall"] is not None else "N/D")

        if expected["expiry_lower"] is not None:
            st.info(
                f"Rango esperado hasta {idea_expiration}: "
                f"{expected['expiry_lower']:,.1f} — {expected['expiry_upper']:,.1f}. "
                "Las ideas fuera de este rango reciben mayor puntuación."
            )

        put_column, call_column = st.columns(2)
        for strategy, column in (("PCS", put_column), ("CCS", call_column)):
            with column:
                st.subheader("🟢 Ideas PCS" if strategy == "PCS" else "🔴 Ideas CCS")
                if not ideas[strategy]:
                    st.info("No hay ideas que cumplan los filtros actuales.")
                for number, idea in enumerate(ideas[strategy], start=1):
                    with st.container(border=True):
                        st.markdown(f"**{selected_symbol()} · {strategy} {idea['short_strike']:.2f}/{idea['long_strike']:.2f}**")
                        one, two, three = st.columns(3)
                        one.metric("Crédito mid", money(idea["max_profit"]))
                        two.metric("Riesgo máx.", money(idea["max_loss"]))
                        three.metric("Delta", f"{idea['delta']:.3f}")
                        st.write(f"Vence: **{idea['expiration']}** · {idea['dte']} DTE · Distancia: **{idea['distance']:.0f} puntos**")
                        st.write(f"Crédito estimado: **{idea['credit']:.2f}** · Bid/ask conservador: **{idea['bid_credit']:.2f}**")
                        if idea["behind_wall"]:
                            st.success(f"Strike ubicado detrás del {'put wall' if strategy == 'PCS' else 'call wall'} ({idea['wall']:.0f}).")
                        else:
                            st.caption("El strike no está protegido por el wall identificado.")
                        if idea["outside_expected"]:
                            st.success("El strike vendido está fuera del movimiento esperado al vencimiento.")
                        elif idea["expected_boundary"] is not None:
                            st.warning(
                                "El strike vendido está dentro del movimiento esperado; "
                                f"nivel de referencia: {idea['expected_boundary']:,.1f}."
                            )

                        key = f"save_{selected_symbol()}_{strategy}_{idea['expiration']}_{idea['short_strike']}_{number}"
                        actual_credit = st.number_input(
                            "Crédito realmente recibido",
                            min_value=0.01,
                            value=float(idea["credit"]),
                            step=0.05,
                            format="%.2f",
                            key=f"credit_{key}",
                        )
                        if st.button("💾 Guardar y hacer seguimiento", key=key, use_container_width=True):
                            try:
                                position = validate_position(
                                    strategy, idea["short_strike"], idea["long_strike"], actual_credit, idea["contracts"]
                                )
                                save_trade(position, idea["expiration"], source="idea")
                                st.success("Operación guardada. Puedes verla en Mis operaciones.")
                                st.rerun()
                            except Exception as error:
                                st.error(f"No se pudo guardar la operación: {error}")

        st.caption(
            f"Último análisis: {datetime.now().strftime('%I:%M:%S %p')} · "
            "Los créditos mid son orientativos y no garantizan ejecución."
        )

    use_fragment(ideas_panel, 600)


elif page == "📊 Simulador de opciones":
    st.markdown(
        '<div class="builder-heading"><div>'
        '<div class="builder-kicker">OPTIONS DEFENDER · STRATEGY BUILDER</div>'
        '<h1>Constructor de estrategias</h1>'
        '<div class="builder-subtitle">Diseña, visualiza y sigue tu operación desde una sola pantalla.</div>'
        f'</div><div class="market-pill">{escape(selected_symbol())} <strong>{current_spx:,.2f}</strong> · TRADIER</div></div>',
        unsafe_allow_html=True,
    )

    closest_30 = min(
        range(len(expirations)),
        key=lambda number: abs((defender.calculate_days_remaining(expirations[number]) or 0) - 30),
    )
    instrument_settings = adaptive_strategy_settings(current_spx)
    builder_column, analysis_column = st.columns([1.08, 2.12], gap="large")

    with builder_column:
        with st.container(border=True):
            st.markdown('<div class="sim-section-label">CONSTRUIR ESTRATEGIA</div>', unsafe_allow_html=True)
            simulated_strategy = st.selectbox(
                "Estrategia",
                [
                    "PCS",
                    "CCS",
                    "Iron Condor",
                    "Iron Butterfly",
                    "Call comprada",
                    "Put comprada",
                    "Call vendida",
                    "Put vendida",
                    "Bull Call Spread",
                    "Bear Put Spread",
                    "Long Straddle",
                    "Long Strangle",
                    "Short Straddle",
                    "Short Strangle",
                    "Call Butterfly",
                    "Put Butterfly",
                    "Personalizada",
                ],
                key="sim_strategy_visual",
            )
            strategy_key = re.sub(r"[^A-Za-z0-9_]", "_", simulated_strategy)
            component_key = f"live_builder_{selected_symbol()}_{strategy_key}"
            expiration_widget_key = f"builder_expiration_{selected_symbol()}_{strategy_key}"
            processed_expiration_key = f"{component_key}_processed_expiration"
            component_expiration = component_state_value(component_key, "expiration")
            if (
                component_expiration in expirations
                and component_expiration != st.session_state.get(processed_expiration_key)
            ):
                st.session_state[expiration_widget_key] = component_expiration
                st.session_state[processed_expiration_key] = component_expiration
            simulated_expiration = st.selectbox(
                "Vencimiento",
                expirations,
                index=closest_30,
                format_func=expiration_name,
                key=expiration_widget_key,
            )
            first, second = st.columns(2)
            simulated_contracts = first.number_input(
                "Contratos", min_value=1, value=1, step=1, key="sim_contracts_visual"
            )
            simulated_width = second.selectbox(
                "Ancho",
                instrument_settings["widths"],
                index=instrument_settings["widths"].index(instrument_settings["default_width"]),
                key=f"sim_width_visual_{selected_symbol()}",
            )
            simulated_distance = st.select_slider(
                f"Distancia desde {selected_symbol()}",
                options=instrument_settings["distances"],
                value=instrument_settings["default_distance"],
                key=f"sim_distance_visual_{selected_symbol()}",
            )
            graph_range = st.select_slider(
                "Rango de visualización",
                options=instrument_settings["ranges"],
                value=instrument_settings["default_range"],
                key=f"sim_graph_range_visual_{selected_symbol()}",
            )

            try:
                simulation_spx = load_spx(selected_symbol())
                simulation_options = load_chain(simulated_expiration, selected_symbol())
                simulation_index = defender.build_option_index(simulation_options)
                simulation_summary = summarize_chain(
                    simulation_options, simulation_spx, min(max(graph_range, 100), 400)
                )
                simulation_expected = calculate_expected_levels(
                    simulation_options,
                    simulation_spx,
                    simulated_expiration,
                    simulation_summary["frame"],
                    min(max(graph_range, 100), 400),
                )
                initial_legs = build_strategy_template(
                    simulated_strategy,
                    simulation_index,
                    simulation_spx,
                    simulated_distance,
                    simulated_width,
                    simulated_contracts,
                )
                previous_visual_selection = component_state_value(component_key, "selection", {})
                initial_legs = apply_visual_selection(
                    initial_legs, simulation_index, previous_visual_selection, simulated_expiration
                )
            except Exception as error:
                st.error(f"No se pudo preparar el simulador: {error}")
                st.stop()

            st.markdown('<div class="sim-section-label">PATAS DE LA OPERACIÓN</div>', unsafe_allow_html=True)
            st.caption("Edita el strike, la prima o los contratos. También puedes agregar o quitar patas.")
            editor_key = (
                f"sim_visual_editor_{selected_symbol()}_{simulated_strategy}_{simulated_expiration}_"
                f"{simulated_distance}_{simulated_width}_{simulated_contracts}_"
                + "_".join(str(float(value)) for value in initial_legs["Strike"].tolist())
            )
            edited_legs = st.data_editor(
                initial_legs,
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key=editor_key,
                column_config={
                    "Acción": st.column_config.SelectboxColumn(
                        "Acción", options=["COMPRAR", "VENDER"], required=True
                    ),
                    "Tipo": st.column_config.SelectboxColumn("Tipo", options=["CALL", "PUT"], required=True),
                    "Strike": st.column_config.NumberColumn(
                        "Strike",
                        min_value=0.0,
                        step=float(instrument_settings["step"]),
                        format="%.2f",
                        required=True,
                    ),
                    "Prima": st.column_config.NumberColumn(
                        "Prima", min_value=0.0, step=0.05, format="%.2f", required=True
                    ),
                    "Contratos": st.column_config.NumberColumn(
                        "Contratos", min_value=1, step=1, required=True
                    ),
                },
            )

            try:
                simulation_legs = normalize_simulator_legs(
                    edited_legs, simulation_index, simulation_expected.get("atm_iv")
                )
            except Exception as error:
                st.warning(f"Revisa la estrategia: {error}")
                st.stop()

            render_strategy_leg_cards(simulation_legs)
            st.markdown('<div class="sim-section-label">MAPA DE STRIKES</div>', unsafe_allow_html=True)
            simulator_strike_ladder(simulation_summary["frame"], simulation_legs, simulation_spx, graph_range)
            st.caption("Calls en verde · puts en rojo · triángulos: patas de tu estrategia.")

    cashflow = simulator_entry_cashflow(simulation_legs)
    bounds = simulator_bounds(simulation_legs, simulation_spx)
    combined_greeks = simulator_greeks(simulation_legs)
    current_pnl = cashflow + sum(
        leg["sign"] * leg["mid"] * leg["contracts"] * 100 for leg in simulation_legs
    )
    dte = defender.calculate_days_remaining(simulated_expiration) or 0
    initial_rate = float(st.session_state.get("sim_interest_rate_visual", 4.0)) / 100
    probability_of_profit = simulator_probability_of_profit(
        simulation_legs,
        simulation_spx,
        years_to_expiration(simulated_expiration),
        simulation_expected.get("atm_iv"),
        initial_rate,
        bounds["breakevens"],
    )
    maximum_loss = abs(min(bounds["max_loss"], 0)) if bounds["max_loss"] is not None else None
    maximum_profit = max(bounds["max_profit"], 0) if bounds["max_profit"] is not None else None
    breakeven_text = (
        " · ".join(f"{point:,.2f}" for point in bounds["breakevens"])
        if bounds["breakevens"]
        else "Sin cruce identificado"
    )

    with analysis_column:
        first, second, third, fourth = st.columns(4)
        with first:
            render_strategy_stat(
                "CRÉDITO NETO" if cashflow >= 0 else "DÉBITO NETO",
                money(abs(cashflow)),
                f"{len(simulation_legs)} pata(s)",
                "blue",
            )
        with second:
            render_strategy_stat(
                "PÉRDIDA MÁXIMA",
                "Ilimitada" if maximum_loss is None else money(maximum_loss),
                "al vencimiento",
                "red",
            )
        with third:
            render_strategy_stat(
                "GANANCIA MÁXIMA",
                "Ilimitada" if maximum_profit is None else money(maximum_profit),
                "al vencimiento",
                "green",
            )
        with fourth:
            render_strategy_stat(
                "PROB. GANANCIA",
                f"{probability_of_profit:.1f}%" if probability_of_profit is not None else "N/D",
                "modelo estimado",
                "green" if probability_of_profit is not None and probability_of_profit >= 50 else "neutral",
            )

        st.markdown('<div class="sim-section-label">CONSTRUCTOR INTERACTIVO EN TIEMPO REAL</div>', unsafe_allow_html=True)
        visual_payload = create_visual_payload(
            selected_symbol(),
            simulation_spx,
            simulated_strategy,
            simulated_expiration,
            expirations,
            simulation_options,
            simulation_legs,
            simulation_expected,
            graph_range,
            previous_visual_selection,
        )
        try:
            render_interactive_builder(visual_payload, component_key)
        except Exception as error:
            st.warning(f"No se pudo iniciar el gráfico interactivo avanzado: {error}")
            st.caption("Puedes seguir utilizando el simulador y los gráficos adicionales de abajo.")

        st.markdown('<div class="sim-section-label">ESCENARIO Y PROYECCIÓN</div>', unsafe_allow_html=True)
        price_column, time_column, volatility_column = st.columns([1, 1, 1])
        scenario_price = price_column.number_input(
            f"Precio {selected_symbol()}",
            min_value=0.01,
            value=float(round(simulation_spx, 2)),
            step=float(instrument_settings["step"]),
            key=f"sim_scenario_price_visual_{selected_symbol()}",
        )
        if dte > 0:
            elapsed_days = time_column.slider(
                "Días transcurridos", min_value=0, max_value=dte, value=0, key="sim_elapsed_visual"
            )
        else:
            time_column.metric("Vencimiento", "0 DTE")
            elapsed_days = 0
        iv_points = volatility_column.slider(
            "Cambio IV (%)", min_value=-20, max_value=30, value=0, key="sim_iv_change_visual"
        )

        with st.expander("⚙️ Ajustes del modelo", expanded=False):
            interest_rate = st.slider(
                "Tasa anual estimada (%)",
                min_value=0.0,
                max_value=10.0,
                value=4.0,
                step=0.25,
                key="sim_interest_rate_visual",
            )

        if dte == 0 and elapsed_days == 0:
            scenario_years = years_to_expiration(simulated_expiration)
        else:
            scenario_years = max(dte - elapsed_days, 0) / 365
        scenario_pnl = simulator_scenario_pnl(
            simulation_legs, scenario_price, scenario_years, iv_points / 100, interest_rate / 100
        )
        expiration_pnl = simulator_expiration_pnl(simulation_legs, scenario_price)

        table_tab, chart_tab = st.tabs(["▦  TABLA DE GANANCIAS", "⌁  GRÁFICO DE RIESGO"])
        with table_tab:
            display_mode = st.radio(
                "Mostrar resultados como",
                ["Ganancia $", "% Retorno", "% Riesgo"],
                horizontal=True,
                label_visibility="collapsed",
                key="sim_heatmap_mode_visual",
            )
            simulator_heatmap(
                simulation_legs,
                simulation_spx,
                max(dte, 1),
                iv_points / 100,
                interest_rate / 100,
                graph_range,
                expiration=simulated_expiration,
                mode=display_mode,
                risk_basis=maximum_loss,
            )
            st.caption(f"Las filas muestran precios potenciales de {selected_symbol()}; las columnas representan fechas futuras.")

        with chart_tab:
            simulator_chart(
                simulation_legs,
                simulation_spx,
                scenario_years,
                iv_points / 100,
                interest_rate / 100,
                graph_range,
                simulation_expected,
                simulation_summary,
            )
            st.caption("Zona verde: beneficio estimado. Zona roja: pérdida estimada. Azul: escenario seleccionado.")

        first, second, third = st.columns(3)
        first.metric("Escenario seleccionado", money(scenario_pnl))
        second.metric("Resultado al vencimiento", money(expiration_pnl))
        third.metric("P&L actual estimado", money(current_pnl))

        st.markdown(
            f'<div class="sim-section-label">BREAKEVEN · {escape(breakeven_text)}</div>',
            unsafe_allow_html=True,
        )
        if simulation_expected.get("expiry_lower") is not None:
            st.caption(
                f"Movimiento esperado: {simulation_expected['expiry_lower']:,.1f} — "
                f"{simulation_expected['expiry_upper']:,.1f} · "
                f"Put wall: {simulation_summary['put_wall'] if simulation_summary['put_wall'] is not None else 'N/D'} · "
                f"Call wall: {simulation_summary['call_wall'] if simulation_summary['call_wall'] is not None else 'N/D'}"
            )

        greek_first, greek_second, greek_third, greek_fourth = st.columns(4)
        greek_first.metric("Delta", f"{combined_greeks['delta']:+.2f}")
        greek_second.metric("Gamma", f"{combined_greeks['gamma']:+.4f}")
        greek_third.metric("Theta", f"{combined_greeks['theta']:+.2f}")
        greek_fourth.metric("Vega", f"{combined_greeks['vega']:+.2f}")

    with builder_column:
        if st.button("💾 GUARDAR OPERACIÓN", use_container_width=True, key="save_visual_strategy"):
            try:
                saved_trades = save_simulated_spreads(
                    simulation_legs,
                    simulated_expiration,
                    market_context={
                        "spot": simulation_spx,
                        "options": simulation_options,
                        "graph_range": graph_range,
                        "atm_iv": simulation_expected.get("atm_iv"),
                        "elapsed_days": elapsed_days,
                        "iv_change": iv_points / 100,
                        "rate": interest_rate / 100,
                        "target_price": scenario_price,
                    },
                )
                if len(saved_trades) == 2:
                    st.success("Estrategia guardada como un PCS y un CCS en Mis operaciones.")
                else:
                    st.success("Operación guardada en Mis operaciones.")
                st.rerun()
            except Exception as error:
                st.warning(str(error))

    st.caption(
        "Probabilidades, curvas y resultados son estimaciones teóricas basadas en volatilidad implícita, "
        "tiempo y tasa configurada. No garantizan precios de ejecución ni beneficios."
    )


else:
    st.title("📋 Mis operaciones")
    st.caption("Las operaciones se guardan en tu computadora y se conservan aunque cierres la aplicación.")
    reference = nearest_strike(current_spx)
    manual_settings = adaptive_strategy_settings(current_spx)
    manual_default_short = max(reference - manual_settings["default_distance"], manual_settings["step"] * 2)
    manual_default_long = max(manual_default_short - manual_settings["default_width"], manual_settings["step"])

    with st.expander("➕ Agregar operación manualmente", expanded=False):
        with st.form("save_manual_trade"):
            first, second, third = st.columns(3)
            manual_strategy = first.selectbox("Tipo de operación", ["PCS", "CCS"], key="manual_strategy")
            manual_expiration = second.selectbox("Vencimiento", expirations, format_func=expiration_name, key="manual_exp")
            manual_contracts = third.number_input("Contratos", min_value=1, value=1, key="manual_contracts")
            fourth, fifth, sixth = st.columns(3)
            manual_short = fourth.number_input(
                "Strike vendido",
                min_value=0.0,
                value=float(manual_default_short),
                step=float(manual_settings["step"]),
                key=f"manual_short_{selected_symbol()}",
            )
            manual_long = fifth.number_input(
                "Strike comprado",
                min_value=0.0,
                value=float(manual_default_long),
                step=float(manual_settings["step"]),
                key=f"manual_long_{selected_symbol()}",
            )
            manual_credit = sixth.number_input("Crédito recibido", min_value=0.01, value=1.50, step=0.05, key="manual_credit")
            save_manual = st.form_submit_button("GUARDAR OPERACIÓN", use_container_width=True)

        if save_manual:
            try:
                position = validate_position(manual_strategy, manual_short, manual_long, manual_credit, manual_contracts)
                save_trade(position, manual_expiration)
                st.success("Operación guardada correctamente.")
                st.rerun()
            except Exception as error:
                st.error(f"No se pudo guardar la operación: {error}")

    def trades_panel():
        try:
            trades = read_trades()
        except Exception as error:
            st.error(str(error))
            return

        opened = [trade for trade in trades if trade.get("status") == "OPEN"]
        closed = [trade for trade in trades if trade.get("status") == "CLOSED"]
        analyzed = []
        for trade in opened:
            try:
                trade_symbol = str(trade.get("symbol") or "SPX").upper()
                trade_spot = load_spx(trade_symbol)
                options = load_chain(trade["expiration"], trade_symbol)
                index = defender.build_option_index(options)
                analysis = defender.analyze_position(trade, index, trade_spot)
                analyzed.append((trade, analysis, options, index, trade_spot))
            except Exception as error:
                analyzed.append((trade, None, str(error), None, None))

        open_pnl = sum(item[1]["pnl"] for item in analyzed if item[1] is not None)
        closed_pnl = sum(float(trade.get("realized_pnl", 0)) for trade in closed)
        first, second, third, fourth = st.columns(4)
        first.metric("Operaciones abiertas", len(opened))
        second.metric("P&L abierto", money(open_pnl))
        third.metric("Operaciones cerradas", len(closed))
        fourth.metric("P&L realizado", money(closed_pnl))

        if not opened:
            st.info("Todavía no tienes operaciones abiertas guardadas.")

        for trade, analysis, options, index, trade_spot in analyzed:
            with st.container(border=True):
                heading_column, remove_column = st.columns([12, 1])
                heading_column.markdown(
                    f"### {trade.get('symbol', 'SPX')} · {trade['strategy']} "
                    f"{trade['short_strike']:.2f}/{trade['long_strike']:.2f} "
                    f"· {trade['expiration']}"
                )
                trade_id = str(trade.get("id") or "")
                if trade_id and remove_column.button(
                    "✕",
                    key=f"remove_trade_open_{trade_id}",
                    help="Eliminar esta operación de la lista",
                    use_container_width=True,
                ):
                    request_trade_removal(trade_id, "open")
                render_trade_removal_confirmation(trade, "open")
                initial_snapshot = trade.get("initial_snapshot")
                if analysis is None:
                    st.warning(f"No se pudo actualizar esta operación: {options}")
                    if isinstance(initial_snapshot, dict) and initial_snapshot.get("curve"):
                        with st.expander("📸 Ver gráfica guardada al abrir la operación", expanded=False):
                            render_saved_trade_graph(trade, initial_snapshot)
                    continue

                first, second, third, fourth, fifth = st.columns(5)
                first.metric("P&L actual", money(analysis["pnl"]))
                second.metric("Crédito inicial", money(trade["credit"] * trade["contracts"] * 100))
                third.metric("Costo de cierre", money(analysis["current_spread_value"] * trade["contracts"] * 100))
                fourth.metric("Riesgo máximo", money(analysis["max_loss"]))
                fifth.metric("Delta", f"{analysis['short_delta']:+.3f}")
                st.caption(
                    f"{trade['contracts']} contrato(s) · {defender.calculate_days_remaining(trade['expiration'])} DTE "
                    f"· Guardado: {trade['opened_at'].replace('T', ' ')}"
                )

                if analysis["loss_percent"] >= defender.DEFENSE_TRIGGER_PERCENT:
                    st.error(f"🚨 Requiere revisar defensa: pérdida del {analysis['loss_percent']:.1f}% sobre el riesgo.")
                    with st.expander("Ver defensas disponibles"):
                        levels = defender.calculate_gamma_levels(options, trade_spot)
                        trade_expirations = load_expirations(str(trade.get("symbol") or "SPX").upper())
                        render_defenses(trade, trade["expiration"], trade_expirations, trade_spot, analysis, index, levels)
                elif analysis["pnl"] >= 0:
                    st.success("Operación en ganancia.")
                else:
                    st.warning(f"Pérdida controlada: {analysis['loss_percent']:.1f}% del riesgo máximo.")

                initial_tab, tracking_tab = st.tabs(["📸 GRÁFICO INICIAL", "📡 SEGUIMIENTO EN VIVO"])
                with initial_tab:
                    if isinstance(initial_snapshot, dict) and initial_snapshot.get("curve"):
                        first, second, third, fourth = st.columns(4)
                        first.metric(
                            f"{trade.get('symbol', 'SPX')} al guardar",
                            f"{float(initial_snapshot.get('spot') or 0):,.2f}",
                        )
                        second.metric("Días iniciales", int(initial_snapshot.get("days") or 0))
                        third.metric("IV inicial", f"{float(initial_snapshot.get('atm_iv') or 0) * 100:.1f}%")
                        fourth.metric("P&L inicial", money(initial_snapshot.get("pnl", 0)))
                        render_saved_trade_graph(trade, initial_snapshot)
                        st.caption(
                            "Esta gráfica queda congelada tal como se guardó el "
                            f"{str(initial_snapshot.get('captured_at') or trade.get('opened_at', '')).replace('T', ' ')}."
                        )
                    else:
                        st.info(
                            "Esta operación se guardó antes de activar las fotografías iniciales. "
                            "Las operaciones nuevas conservarán automáticamente su gráfica original."
                        )

                with tracking_tab:
                    reference_snapshot = initial_snapshot if isinstance(initial_snapshot, dict) else {}
                    live_snapshot = build_trade_snapshot(
                        trade,
                        {
                            "spot": trade_spot,
                            "options": options,
                            "graph_range": reference_snapshot.get("graph_range"),
                            "atm_iv": reference_snapshot.get("atm_iv"),
                            "rate": reference_snapshot.get("rate", 0.04),
                            "target_pnl": analysis["pnl"],
                        },
                    )
                    initial_spot = float(reference_snapshot.get("spot") or 0.0)
                    first, second, third, fourth = st.columns(4)
                    first.metric(
                        f"{trade.get('symbol', 'SPX')} actual",
                        f"{trade_spot:,.2f}",
                        f"{trade_spot - initial_spot:+,.2f}" if initial_spot else None,
                    )
                    second.metric("P&L en vivo", money(analysis["pnl"]))
                    third.metric("IV actual", f"{live_snapshot['atm_iv'] * 100:.1f}%")
                    fourth.metric(
                        "Distancia al strike",
                        f"{abs(trade_spot - float(trade['short_strike'])):,.2f}",
                    )
                    render_saved_trade_graph(
                        trade,
                        live_snapshot,
                        live=True,
                        original_snapshot=reference_snapshot,
                    )
                    st.caption(
                        "La línea amarilla indica el precio al guardar la operación; "
                        "la azul muestra el precio actual. Actualización automática cada 30 segundos."
                    )

                with st.expander("✅ Registrar cierre de la operación"):
                    actual_close = st.number_input(
                        "Débito real pagado para cerrar",
                        min_value=0.0,
                        value=float(round(analysis["current_spread_value"], 2)),
                        step=0.05,
                        format="%.2f",
                        key=f"close_value_{trade['id']}",
                    )
                    if st.button("Confirmar cierre", key=f"close_{trade['id']}"):
                        try:
                            close_trade(trade["id"], actual_close)
                            st.rerun()
                        except Exception as error:
                            st.error(str(error))

        if closed:
            with st.expander("📚 Historial de operaciones cerradas"):
                for trade in reversed(closed):
                    with st.container(border=True):
                        operation_column, result_column, date_column, remove_column = st.columns([4, 1.4, 2.2, 0.55])
                        operation_column.markdown(
                            f"**{trade.get('symbol', 'SPX')} · {trade['strategy']} "
                            f"{trade['short_strike']:.2f}/{trade['long_strike']:.2f}**"
                        )
                        operation_column.caption(
                            f"{trade['contracts']} contrato(s) · Vence {trade['expiration']}"
                        )
                        realized_pnl = float(trade.get("realized_pnl", 0))
                        result_column.metric("Resultado", money(realized_pnl))
                        date_column.caption("Cerrada")
                        date_column.markdown(
                            str(trade.get("closed_at", "")).replace("T", " ") or "Sin fecha"
                        )
                        trade_id = str(trade.get("id") or "")
                        if trade_id and remove_column.button(
                            "✕",
                            key=f"remove_trade_closed_{trade_id}",
                            help="Eliminar esta operación del historial",
                            use_container_width=True,
                        ):
                            request_trade_removal(trade_id, "closed")
                        render_trade_removal_confirmation(trade, "closed")

        st.caption(f"Seguimiento actualizado: {datetime.now().strftime('%I:%M:%S %p')}")

    use_fragment(trades_panel, 30)


st.caption("SPX Defender analiza y registra operaciones. No envía órdenes al bróker.")
