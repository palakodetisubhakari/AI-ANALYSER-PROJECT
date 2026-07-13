"""
Saathi — Owner Sales Call Quality Companion
Final Streamlit UI: redesigned layout, new color system, friendlier
coaching cards, compact call evidence, safer HTML escaping, and responsive views.

Reads agents_data.json, shows each agent their own dashboard after login, and
sends feedback to a Google Apps Script webhook. A separate manager passcode
opens a simple view linking to the feedback sheet.
"""

import html
import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ── CONFIG ────────────────────────────────────────────────────────────────
DATA_FILE = "agents_data.json"
FEEDBACK_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNyO1zu3uDeIzPqoV0giZZEXT543NhnMUjsDak5vl8R-uT3lIcPcBtR2ujLqCYmJhG/exec"
FEEDBACK_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_mDEbmmEC3FD4CJg-LhRTCtYCNFhWAtzy-nyJLrkxkM/edit?gid=0#gid=0"
MANAGER_PASSCODE = "saathi-admin"  # change this before sharing the app / repo

APP_NAME = "Saathi"
APP_TAGLINE = "Your partner in performance and rewards"

# Friendly premium palette
INK = "#0B1220"          # deep navy text
NAVY = "#111827"         # primary dark block
MUTED = "#667085"        # secondary text
PAPER = "#FFFDF8"        # card surface
CANVAS = "#F6F2EA"       # page bg
LINE = "#E7E2D8"         # warm border
TEAL = "#12B8A6"         # positive brand accent
TEAL_SOFT = "#E8FAF7"
CORAL = "#FF6B5F"        # attention accent
CORAL_SOFT = "#FFF0EE"
AMBER = "#D99000"
AMBER_SOFT = "#FFF6E3"
GREEN = "#16A34A"
GREEN_SOFT = "#EAF8EF"
BLUE = "#2563EB"
BLUE_SOFT = "#ECF4FF"
LILAC = "#7C3AED"
LILAC_SOFT = "#F3EEFF"

st.set_page_config(
    page_title=f"{APP_NAME} — {APP_TAGLINE}",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ── DATA ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_agents(data_file: str, file_mtime: float) -> Dict[str, Dict[str, Any]]:
    # file_mtime is intentionally an argument so Streamlit reloads data when
    # agents_data.json changes after deployment.
    with open(data_file, encoding="utf-8") as f:
        return json.load(f)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def score_int(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def num(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def call_score_value(agent: Dict[str, Any]) -> int:
    """Display only call_score from agents_data.json.

    Intentionally does not fall back to overall_score, conversation_quality,
    conversion_score, or any other score-like field.
    """
    return score_int(agent.get("call_score", 0))


def short_id(value: Any) -> str:
    text = "" if value is None else str(value)
    if len(text) <= 22:
        return text
    return f"{text[:8]}…{text[-6:]}"


def build_directory(agents: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Exact full name and employee ID work. Unique first names also work."""
    directory: Dict[str, str] = {}
    first_counts: Dict[str, int] = {}

    for agent in agents.values():
        name = str(agent.get("name", "")).strip()
        first = name.split()[0].lower() if name else ""
        if first:
            first_counts[first] = first_counts.get(first, 0) + 1

    for eid, agent in agents.items():
        name = str(agent.get("name", "")).strip()
        if name:
            directory[name.lower()] = eid
        directory[str(eid).lower()] = eid
        first = name.split()[0].lower() if name else ""
        if first and first_counts.get(first) == 1:
            directory[first] = eid
    return directory


def resolve_agent(query: str, agents: Dict[str, Dict[str, Any]], directory: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    q = query.strip().lower()
    if not q:
        return None, "Enter your name or employee ID."

    if q in directory:
        return directory[q], None

    partial = [eid for eid, a in agents.items() if q in str(a.get("name", "")).lower()]
    if len(partial) == 1:
        return partial[0], None
    if len(partial) > 1:
        names = ", ".join(str(agents[eid].get("name", eid)) for eid in partial[:4])
        return None, f"Found multiple matches: {names}. Use full name or employee ID."
    return None, "Could not find that name or ID. Check spelling, or ask your manager if you are not set up yet."


# ── CSS ──────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --ink: {INK};
            --navy: {NAVY};
            --muted: {MUTED};
            --paper: {PAPER};
            --canvas: {CANVAS};
            --line: {LINE};
            --teal: {TEAL};
            --teal-soft: {TEAL_SOFT};
            --coral: {CORAL};
            --coral-soft: {CORAL_SOFT};
            --amber: {AMBER};
            --amber-soft: {AMBER_SOFT};
            --green: {GREEN};
            --green-soft: {GREEN_SOFT};
            --blue: {BLUE};
            --blue-soft: {BLUE_SOFT};
            --lilac: {LILAC};
            --lilac-soft: {LILAC_SOFT};
        }}

        html, body, .stApp {{
            background:
                radial-gradient(circle at 8% -5%, rgba(18,184,166,.20), transparent 28%),
                radial-gradient(circle at 95% 4%, rgba(255,107,95,.16), transparent 26%),
                linear-gradient(180deg, #FFFDF8 0%, var(--canvas) 52%, #F3EEE5 100%);
            color: var(--ink);
        }}

        header[data-testid="stHeader"] {{ background: transparent; height: 0rem; }}
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
        #MainMenu, footer, [data-testid="collapsedControl"], [data-testid="stHeaderActionElements"] {{
            display: none !important;
            visibility: hidden !important;
        }}

        div.block-container {{
            max-width: 1180px;
            padding: 1.25rem 1.35rem 3.5rem;
        }}

        .topbar {{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap: 16px;
            margin: 4px 0 16px;
        }}
        .brand {{
            display:flex;
            align-items:center;
            gap: 12px;
        }}
        .brand-logo {{
            width: 42px;
            height: 42px;
            border-radius: 16px;
            display:flex;
            align-items:center;
            justify-content:center;
            color: #071014;
            background: linear-gradient(135deg, #9AF7EA 0%, #FFD2C8 100%);
            box-shadow: 0 16px 36px rgba(17,24,39,.13);
            font-weight: 950;
            letter-spacing: -.04em;
        }}
        .brand-name {{
            font-size: 14px;
            font-weight: 900;
            color: var(--ink);
            letter-spacing: -.02em;
        }}
        .brand-sub {{
            font-size: 12px;
            color: var(--muted);
            margin-top: 1px;
        }}

        .hero {{
            position: relative;
            overflow: hidden;
            border-radius: 32px;
            padding: 28px;
            color: white;
            background:
                radial-gradient(circle at 84% 10%, rgba(18,184,166,.55), transparent 30%),
                radial-gradient(circle at 35% 0%, rgba(255,107,95,.34), transparent 26%),
                linear-gradient(135deg, #0B1220 0%, #172033 56%, #24334C 100%);
            box-shadow: 0 28px 70px rgba(15,23,42,.22);
            margin-bottom: 18px;
        }}
        .hero::after {{
            content:"";
            position:absolute;
            right:-80px;
            bottom:-110px;
            width: 280px;
            height: 280px;
            border-radius: 50%;
            background: rgba(255,255,255,.065);
        }}
        .hero-grid {{
            position:relative;
            z-index:1;
            display:grid;
            grid-template-columns: minmax(0, 1fr) 310px;
            gap: 24px;
            align-items:center;
        }}
        .eyebrow-top {{
            display:inline-flex;
            align-items:center;
            gap: 8px;
            border: 1px solid rgba(255,255,255,.16);
            background: rgba(255,255,255,.08);
            color: #D5FAF5;
            border-radius: 999px;
            padding: 7px 11px;
            font-size: 12px;
            font-weight: 850;
            margin-bottom: 16px;
        }}
        .hero-title {{
            font-size: 38px;
            line-height: 1.04;
            font-weight: 950;
            letter-spacing: -.055em;
            margin-bottom: 10px;
        }}
        .hero-copy {{
            max-width: 650px;
            color: rgba(255,255,255,.72);
            font-size: 14px;
            line-height: 1.58;
        }}
        .hero-pills {{
            display:flex;
            flex-wrap:wrap;
            gap: 8px;
            margin-top: 17px;
        }}
        .hero-pill {{
            display:inline-flex;
            align-items:center;
            gap: 7px;
            padding: 8px 11px;
            border-radius: 999px;
            background: rgba(255,255,255,.11);
            border: 1px solid rgba(255,255,255,.14);
            color: rgba(255,255,255,.88);
            font-size: 12px;
            font-weight: 800;
        }}
        .score-tile {{
            justify-self:end;
            width: 100%;
            background: rgba(255,255,255,.12);
            border: 1px solid rgba(255,255,255,.18);
            border-radius: 28px;
            padding: 18px;
            backdrop-filter: blur(10px);
        }}
        .score-ring {{
            width: 172px;
            height: 172px;
            border-radius: 50%;
            display:flex;
            align-items:center;
            justify-content:center;
            margin: 0 auto 13px;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,.20);
        }}
        .score-core {{
            width: 124px;
            height: 124px;
            border-radius: 50%;
            display:flex;
            flex-direction:column;
            align-items:center;
            justify-content:center;
            background: rgba(8,13,24,.92);
            box-shadow: 0 10px 30px rgba(0,0,0,.18);
        }}
        .score-number {{
            font-size: 40px;
            line-height:1;
            font-weight: 950;
            letter-spacing: -.06em;
        }}
        .score-label {{
            font-size: 11px;
            color: rgba(255,255,255,.60);
            font-weight: 800;
            margin-top: 5px;
        }}
        .score-caption {{
            text-align:center;
            color: rgba(255,255,255,.76);
            font-size: 13px;
            font-weight: 750;
        }}

        .quick-grid {{
            display:grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
            margin: 12px 0 18px;
        }}
        .quick-card, .soft-card, .focus-card, .login-card {{
            background: rgba(255,253,248,.92);
            border: 1px solid rgba(231,226,216,.92);
            border-radius: 24px;
            box-shadow: 0 18px 46px rgba(74,61,39,.08);
        }}
        .quick-card {{
            padding: 17px 18px;
            min-height: 112px;
        }}
        .quick-label {{
            color: var(--muted);
            font-size: 12px;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: .08em;
            margin-bottom: 8px;
        }}
        .quick-value {{
            color: var(--ink);
            font-size: 34px;
            line-height: 1;
            font-weight: 950;
            letter-spacing: -.05em;
        }}
        .quick-help {{
            color: var(--muted);
            font-size: 12.5px;
            line-height: 1.45;
            margin-top: 11px;
        }}
        .quick-accent {{
            width: 38px;
            height: 5px;
            border-radius: 999px;
            margin-bottom: 12px;
        }}
        .accent-teal {{ background: var(--teal); }}
        .accent-coral {{ background: var(--coral); }}
        .accent-amber {{ background: var(--amber); }}

        .soft-card {{
            padding: 20px;
            min-height: 100%;
        }}
        .card-title {{
            color: var(--ink);
            font-size: 18px;
            font-weight: 950;
            letter-spacing: -.035em;
            margin-bottom: 5px;
        }}
        .card-subtitle {{
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 14px;
        }}
        .strength-item {{
            display:flex;
            gap: 11px;
            align-items:flex-start;
            padding: 11px 0;
            border-bottom: 1px solid rgba(231,226,216,.78);
            color: #263244;
            font-size: 14px;
            line-height: 1.48;
        }}
        .strength-item:last-child {{ border-bottom: none; }}
        .tick {{
            width: 23px;
            height: 23px;
            border-radius: 9px;
            background: var(--teal-soft);
            color: var(--teal);
            display:inline-flex;
            align-items:center;
            justify-content:center;
            flex: 0 0 23px;
            font-size: 12px;
            font-weight: 950;
        }}

        .section-title {{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap: 12px;
            margin: 26px 0 12px;
        }}
        .section-title-main {{
            color: var(--ink);
            font-size: 22px;
            font-weight: 950;
            letter-spacing: -.045em;
        }}
        .section-title-sub {{
            color: var(--muted);
            font-size: 13px;
            margin-top: 3px;
        }}
        .section-badge {{
            border-radius: 999px;
            padding: 8px 11px;
            background: #FFFFFF;
            border: 1px solid var(--line);
            color: var(--muted);
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
        }}

        .focus-card {{
            overflow:hidden;
            margin-bottom: 12px;
        }}
        .focus-top {{
            display:grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 14px;
            align-items:start;
            padding: 19px 20px 16px;
            background: linear-gradient(180deg, #FFFEFB 0%, #FBF6EE 100%);
            border-bottom: 1px solid rgba(231,226,216,.9);
        }}
        .focus-kicker {{
            color: var(--coral);
            font-size: 11px;
            font-weight: 950;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .focus-title {{
            color: var(--ink);
            font-size: 18px;
            line-height: 1.25;
            font-weight: 950;
            letter-spacing: -.035em;
        }}
        .focus-advice {{
            color: var(--muted);
            font-size: 13px;
            line-height: 1.48;
            margin-top: 8px;
        }}
        .count-pill {{
            min-width: 74px;
            padding: 11px 12px;
            text-align:center;
            border-radius: 20px;
            color: var(--coral);
            background: var(--coral-soft);
            border: 1px solid #FFD7D2;
            font-size: 24px;
            font-weight: 950;
            line-height: 1;
        }}
        .count-pill span {{
            display:block;
            color: rgba(255,107,95,.78);
            font-size: 10px;
            font-weight: 850;
            margin-top: 5px;
        }}
        .moments {{
            padding: 12px;
        }}
        .moment {{
            display:grid;
            grid-template-columns: 34px minmax(0, 1fr) auto;
            gap: 11px;
            align-items:start;
            padding: 13px;
            border-radius: 18px;
            background: #FFFFFF;
            border: 1px solid rgba(231,226,216,.92);
            margin-bottom: 10px;
        }}
        .moment:last-child {{ margin-bottom: 0; }}
        .moment-icon {{
            width: 34px;
            height: 34px;
            border-radius: 13px;
            display:flex;
            align-items:center;
            justify-content:center;
            background: var(--amber-soft);
            color: var(--amber);
            font-weight: 950;
            font-size: 15px;
        }}
        .moment-quote {{
            color: var(--ink);
            font-size: 13.8px;
            line-height: 1.45;
            font-weight: 750;
            overflow-wrap:anywhere;
        }}
        .moment-meta {{
            color: var(--muted);
            font-size: 12px;
            line-height: 1.45;
            margin-top: 4px;
        }}
        .moment-miss {{
            color: var(--coral);
            font-size: 12.3px;
            line-height: 1.45;
            margin-top: 7px;
            font-weight: 850;
        }}
        .call-chip {{
            border-radius: 999px;
            padding: 7px 9px;
            max-width: 130px;
            overflow:hidden;
            text-overflow:ellipsis;
            white-space:nowrap;
            background: #F7F2EA;
            border: 1px solid var(--line);
            color: #685B49;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 10.5px;
            font-weight: 850;
        }}
        .focus-note {{
            margin: 0 12px 13px;
            padding: 11px 13px;
            border-radius: 16px;
            background: var(--blue-soft);
            border: 1px solid #D8E8FF;
            color: #31527B;
            font-size: 12.6px;
            line-height: 1.5;
        }}
        .empty-good {{
            background: var(--green-soft);
            border-color: #CDEED8;
        }}
        .empty-good .moment-icon {{ background: #FFFFFF; color: var(--green); }}
        .empty-good .moment-miss {{ color: var(--green); }}

        .coach-note {{
            padding: 16px;
            border-radius: 20px;
            background: linear-gradient(135deg, var(--teal-soft), #FFFFFF 70%);
            border: 1px solid #CFF1EC;
            color: #23534D;
            font-size: 13.4px;
            line-height: 1.55;
        }}

        .profile-avatar {{
            width: 86px;
            height: 86px;
            border-radius: 28px;
            display:flex;
            align-items:center;
            justify-content:center;
            color: #061316;
            background: linear-gradient(135deg, #9AF7EA, #FFD2C8);
            font-size: 30px;
            font-weight: 950;
            margin-bottom: 14px;
            box-shadow: 0 16px 32px rgba(17,24,39,.12);
        }}
        .profile-name {{
            color: var(--ink);
            font-size: 23px;
            font-weight: 950;
            letter-spacing: -.045em;
        }}
        .profile-meta {{
            color: var(--muted);
            font-size: 13px;
            margin-top: 4px;
        }}

        .login-shell {{
            max-width: 980px;
            margin: 54px auto 0;
            display:grid;
            grid-template-columns: 1.05fr .95fr;
            gap: 18px;
            align-items:stretch;
        }}
        .login-hero {{
            position:relative;
            overflow:hidden;
            border-radius: 34px;
            padding: 34px;
            color: white;
            background:
                radial-gradient(circle at 78% 10%, rgba(18,184,166,.52), transparent 32%),
                radial-gradient(circle at 20% 0%, rgba(255,107,95,.36), transparent 25%),
                linear-gradient(135deg, #0B1220 0%, #172033 100%);
            box-shadow: 0 30px 80px rgba(15,23,42,.24);
        }}
        .login-big {{
            font-size: 42px;
            line-height: 1.02;
            font-weight: 950;
            letter-spacing: -.065em;
            margin: 20px 0 12px;
        }}
        .login-copy {{
            color: rgba(255,255,255,.72);
            font-size: 14.5px;
            line-height: 1.62;
            max-width: 420px;
        }}
        .login-card {{
            padding: 30px;
            display:flex;
            flex-direction:column;
            justify-content:center;
        }}
        .login-card-title {{
            color: var(--ink);
            font-size: 26px;
            line-height:1.1;
            font-weight: 950;
            letter-spacing: -.055em;
            margin-bottom: 8px;
        }}
        .login-card-copy {{
            color: var(--muted);
            font-size: 13.5px;
            line-height: 1.55;
            margin-bottom: 18px;
        }}

        /* Native Streamlit controls styled to match the new UI */
        div[data-testid="stForm"] {{
            border: 0 !important;
            background: transparent !important;
            padding: 0 !important;
        }}
        div[data-baseweb="input"], textarea {{
            border-radius: 16px !important;
            border: 1px solid var(--line) !important;
            background: #FFFFFF !important;
            min-height: 49px;
            box-shadow: none !important;
        }}
        div[data-baseweb="input"]:focus-within, textarea:focus {{
            border-color: rgba(18,184,166,.72) !important;
            box-shadow: 0 0 0 4px rgba(18,184,166,.13) !important;
        }}
        .stButton > button, .stFormSubmitButton > button {{
            border-radius: 16px !important;
            min-height: 44px;
            border: 1px solid var(--line) !important;
            background: #FFFFFF !important;
            color: var(--ink) !important;
            font-weight: 900 !important;
            box-shadow: 0 8px 20px rgba(74,61,39,.06) !important;
            transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease;
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            transform: translateY(-1px);
            border-color: rgba(18,184,166,.65) !important;
            color: #0D766D !important;
            box-shadow: 0 14px 28px rgba(18,184,166,.12) !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            margin: 8px 0 18px;
            border-bottom: 0;
        }}
        .stTabs [data-baseweb="tab"] {{
            height: 42px;
            padding: 0 18px;
            border-radius: 999px;
            font-weight: 900;
            color: var(--muted);
            background: rgba(255,253,248,.76);
            border: 1px solid var(--line);
        }}
        .stTabs [aria-selected="true"] {{
            background: var(--navy) !important;
            color: white !important;
            border-color: var(--navy) !important;
        }}
        .stTabs [data-baseweb="tab-highlight"] {{ display:none; }}
        .stCaption, [data-testid="stCaptionContainer"] {{ color: var(--muted) !important; }}
        hr {{ margin: .75rem 0 !important; }}

        @media (max-width: 980px) {{
            div.block-container {{ padding-left: 1rem; padding-right: 1rem; }}
            .hero-grid, .login-shell {{ grid-template-columns: 1fr; }}
            .score-tile {{ justify-self:stretch; max-width: 360px; }}
            .quick-grid {{ grid-template-columns: 1fr; }}
            .hero-title {{ font-size: 31px; }}
            .login-big {{ font-size: 34px; }}
        }}
        @media (max-width: 640px) {{
            .hero {{ padding: 22px; border-radius: 26px; }}
            .hero-title {{ font-size: 28px; }}
            .focus-top, .moment {{ grid-template-columns: 1fr; }}
            .count-pill {{ width: fit-content; }}
            .call-chip {{ width: fit-content; max-width: 100%; }}
            .section-title {{ align-items:flex-start; flex-direction:column; }}
            .login-hero, .login-card {{ padding: 24px; border-radius: 26px; }}
            .stTabs [data-baseweb="tab"] {{ padding: 0 12px; font-size: 12.5px; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── HTML HELPERS ─────────────────────────────────────────────────────────
def render_html(body: str) -> None:
    """render_html(..., unsafe_allow_html=True) but strips leading whitespace
    from every line first. Streamlit's markdown parser treats any line that
    starts with 4+ spaces as a literal code block (standard Markdown rule),
    so indented HTML f-strings render as visible '</div>' text instead of
    being parsed as markup. Stripping indentation is safe here since
    whitespace between HTML tags has no visual effect."""
    cleaned = "\n".join(line.strip() for line in str(body).strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


def score_colour(score: int) -> str:
    if score >= 65:
        return TEAL
    if score >= 35:
        return AMBER
    return CORAL


def performance_label(score: int) -> str:
    if score >= 65:
        return "Strong momentum"
    if score >= 35:
        return "Coachable"
    return "Needs urgent support"


def topbar() -> None:
    render_html(
        f"""
        <div class="topbar">
          <div class="brand">
            <div class="brand-logo">🤝</div>
            <div>
              <div class="brand-name">{esc(APP_NAME)}</div>
              <div class="brand-sub">{esc(APP_TAGLINE)}</div>
            </div>
          </div>
        </div>
        """,
    )


def render_hero(agent: Dict[str, Any]) -> None:
    score = call_score_value(agent)
    deg = score * 3.6
    colour = score_colour(score)
    name = esc(agent.get("name", "Agent"))
    employee_id = esc(agent.get("employee_id", ""))
    calls = esc(agent.get("n_live_calls", "—"))
    rpl_rank = esc(agent.get("rpl_rank", "—"))

    render_html(
        f"""
        <div class="hero">
          <div class="hero-grid">
            <div>
              <div class="eyebrow-top">This week's coaching snapshot</div>
              <div class="hero-title">Hi {name}, here is where your calls are winning — and where to tighten.</div>
              <div class="hero-copy">
                Built from live call evidence. The page focuses on actions the agent can control, with each coaching point traceable to a call ID.
              </div>
              <div class="hero-pills">
                <span class="hero-pill">{employee_id} · Owner Sales</span>
                <span class="hero-pill">{calls} calls reviewed</span>
                <span class="hero-pill">RPL rank #{rpl_rank} of 34</span>
              </div>
            </div>
            <div class="score-tile">
              <div class="score-ring" style="background: conic-gradient({colour} {deg:.1f}deg, rgba(255,255,255,.18) 0deg);">
                <div class="score-core">
                  <div class="score-number">{score}</div>
                  <div class="score-label">call score</div>
                </div>
              </div>
              <div class="score-caption">{performance_label(score)}</div>
            </div>
          </div>
        </div>
        """,
    )


def quick_card(label: str, value: Any, help_text: str, accent_class: str) -> str:
    return f"""
    <div class="quick-card">
      <div class="quick-accent {accent_class}"></div>
      <div class="quick-label">{esc(label)}</div>
      <div class="quick-value">{esc(value)}</div>
      <div class="quick-help">{esc(help_text)}</div>
    </div>
    """


def render_quick_grid(agent: Dict[str, Any]) -> None:
    call_score = call_score_value(agent)

    render_html(
        f"""
        <div class="quick-grid" style="grid-template-columns: 1fr;">
          {quick_card('Call score', call_score, 'Pulled only from call_score in agents_data.json.', 'accent-amber')}
        </div>
        """,
    )


def render_strengths_card(agent: Dict[str, Any]) -> None:
    strengths = agent.get("strengths", []) or []
    items = "".join(
        f'<div class="strength-item"><span class="tick">✓</span><span>{esc(item)}</span></div>'
        for item in strengths[:5]
    )
    if not items:
        items = '<div class="card-subtitle">No strengths listed for this cycle yet.</div>'

    render_html(
        f"""
        <div class="soft-card">
          <div class="card-title">What is already working</div>
          <div class="card-subtitle">Start the 1:1 here. Reinforce these behaviours before moving to corrections.</div>
          {items}
        </div>
        """,
    )

def section_title(title: str, subtitle: str, badge: str = "") -> None:
    badge_html = f'<div class="section-badge">{esc(badge)}</div>' if badge else ""
    render_html(
        f"""
        <div class="section-title">
          <div>
            <div class="section-title-main">{esc(title)}</div>
            <div class="section-title-sub">{esc(subtitle)}</div>
          </div>
          {badge_html}
        </div>
        """,
    )


def issue_row_a(item: Dict[str, Any]) -> str:
    sop = str(item.get("sop", "") or "").split(":")[0]
    return f"""
    <div class="moment">
      <div class="moment-icon">!</div>
      <div>
        <div class="moment-quote">{esc(item.get('objection', ''))}</div>
        <div class="moment-meta">Expected SOP: {esc(sop)}</div>
        <div class="moment-miss">Rebuttal did not match the specific objection.</div>
      </div>
      <div class="call-chip" title="{esc(item.get('cdr_id', ''))}">Call · {esc(short_id(item.get('cdr_id', '')))}</div>
    </div>
    """


def issue_row_b(item: Dict[str, Any]) -> str:
    return f"""
    <div class="moment">
      <div class="moment-icon">→</div>
      <div>
        <div class="moment-quote">{esc(item.get('reason', ''))}</div>
        <div class="moment-miss">Owner showed buying intent, but no plan was offered.</div>
      </div>
      <div class="call-chip" title="{esc(item.get('cdr_id', ''))}">Call · {esc(short_id(item.get('cdr_id', '')))}</div>
    </div>
    """


def empty_focus_row(message: str) -> str:
    return f"""
    <div class="moment empty-good">
      <div class="moment-icon">✓</div>
      <div>
        <div class="moment-quote">{esc(message)}</div>
        <div class="moment-miss">Good sign for this review cycle.</div>
      </div>
    </div>
    """


def focus_card(area_number: int, title: str, advice: str, total: int, rows_html: str, note: str = "") -> None:
    count = max(0, int(total or 0))
    note_html = f'<div class="focus-note">{esc(note)}</div>' if note else ""
    render_html(
        f"""
        <div class="focus-card">
          <div class="focus-top">
            <div>
              <div class="focus-kicker">Priority {area_number}</div>
              <div class="focus-title">{esc(title)}</div>
              <div class="focus-advice">{esc(advice)}</div>
            </div>
            <div class="count-pill">{count}<span>this cycle</span></div>
          </div>
          <div class="moments">
            {rows_html}
          </div>
          {note_html}
        </div>
        """,
    )


# ── CHARTS ───────────────────────────────────────────────────────────────
def trend_chart(points: Iterable[Dict[str, Any]]) -> None:
    points = list(points or [])
    if len(points) < 2:
        render_html(
            '<div class="coach-note">Not enough day-to-day spread in this cycle to show a reliable trend yet. Future cycles will make this chart more useful.</div>',
        )
        return

    df = pd.DataFrame(points)
    if "date" not in df.columns or "score" not in df.columns:
        render_html('<div class="coach-note">Trend data is missing date or score fields.</div>')
        return

    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["date", "score"])
    if len(df) < 2:
        render_html('<div class="coach-note">Trend data exists, but there are not enough valid points to chart.</div>')
        return

    fig = go.Figure(
        go.Scatter(
            x=df["date"],
            y=df["score"],
            mode="lines+markers+text",
            text=df["score"].round(0).astype(int),
            textposition="top center",
            line=dict(color=TEAL, width=4),
            marker=dict(size=10, color=TEAL, line=dict(width=2, color="#FFFFFF")),
            hovertemplate="%{x}<br>Score: %{y}<extra></extra>",
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(l=8, r=8, t=32, b=8),
        yaxis=dict(range=[0, 100], gridcolor="#E8E0D3", zeroline=False, title=None),
        xaxis=dict(gridcolor="#F0E8DB", title=None),
        plot_bgcolor="#FFFDF8",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    diff = df["score"].iloc[-1] - df["score"].iloc[0]
    if diff > 0:
        st.success(f"Up {int(diff)} points from first day to last.")
    elif diff < 0:
        st.warning(f"Down {int(abs(diff))} points from first day to last.")
    else:
        st.info("Flat — no change from first day to last.")


def good_example_html(example: Optional[Dict[str, Any]]) -> str:
    if not example:
        return '<div class="coach-note">No successful rebuttal example selected for this cycle yet.</div>'
    sop = str(example.get("sop", "") or "").split(":")[0]
    return f"""
    <div class="moment empty-good">
      <div class="moment-icon">✓</div>
      <div>
        <div class="moment-quote"><b>{esc(sop)}</b></div>
        <div class="moment-meta">Owner: {esc(example.get('objection', ''))}</div>
        <div class="moment-miss">Reply: {esc(example.get('rebuttal', ''))}</div>
      </div>
      <div class="call-chip" title="{esc(example.get('cdr_id', ''))}">Call · {esc(short_id(example.get('cdr_id', '')))}</div>
    </div>
    """


# ── FEEDBACK ─────────────────────────────────────────────────────────────
def send_feedback(agent_id: str, area: str, reaction: str, comment: str) -> bool:
    payload = {
        "agent": agent_id,
        "area": area,
        "reaction": reaction,
        "comment": comment,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        resp = requests.post(FEEDBACK_WEBHOOK_URL, json=payload, timeout=8, allow_redirects=True)
    except Exception as exc:
        st.warning(f"Could not reach the feedback sheet right now ({exc}). Try again shortly.")
        return False

    if resp.status_code != 200:
        st.error(f"Feedback sheet returned status {resp.status_code}. Feedback was not saved.")
        return False

    try:
        body = resp.json()
    except ValueError:
        st.error(
            "Got an unexpected non-JSON response from the feedback sheet. Check Apps Script deployment access and redeploy if needed."
        )
        return False

    if body.get("status") == "ok":
        return True

    st.error(f"Sheet responded but did not confirm success: {body}")
    return False


def feedback_widget(key: str, agent_id: str, area_title: str) -> None:
    reaction_key = f"{key}_reaction"
    st.caption("Was this coaching point fair?")
    c1, c2 = st.columns(2)
    if c1.button("Fair point", key=f"{key}_fair", use_container_width=True):
        st.session_state[reaction_key] = "like"
    if c2.button("Needs review", key=f"{key}_review", use_container_width=True):
        st.session_state[reaction_key] = "dislike"

    reaction = st.session_state.get(reaction_key)
    if reaction:
        label = "Optional context" if reaction == "like" else "What should the manager review?"
        comment = st.text_area(label, key=f"{key}_comment", height=84)
        if st.button("Submit feedback", key=f"{key}_submit", use_container_width=True):
            if send_feedback(agent_id, area_title, reaction, comment):
                st.success("Thanks — noted for review.")
                del st.session_state[reaction_key]


# ── PAGES ────────────────────────────────────────────────────────────────
def render_home(agent: Dict[str, Any]) -> None:
    render_quick_grid(agent)

    col1, col2 = st.columns([1.05, .95], gap="medium")
    with col1:
        render_strengths_card(agent)
    with col2:
        render_coach_note(agent)

    section_title(
        "Priority coaching moments",
        "Each card shows what happened, why it matters, and the call evidence to review.",
        "2 focus areas",
    )

    area_a = agent.get("area_a", []) or []
    area_a_total = int(agent.get("area_a_total", len(area_a)) or 0)
    area_a_rows = "".join(issue_row_a(item) for item in area_a[:3]) or empty_focus_row("No SOP-mapped rebuttal misses found.")
    area_a_note = f"Showing {min(len(area_a), 3)} of {area_a_total}. Review remaining examples in the call log / Trends view." if area_a_total > 3 else ""

    area_b = agent.get("area_b", []) or []
    area_b_total = int(agent.get("area_b_total", len(area_b)) or 0)
    area_b_rows = "".join(issue_row_b(item) for item in area_b[:3]) or empty_focus_row("No confirmed missed high-intent pitches found.")
    excluded = int(agent.get("area_b_excluded_deferred", 0) or 0)
    area_b_note_parts: List[str] = []
    if area_b_total > 3:
        area_b_note_parts.append(f"Showing {min(len(area_b), 3)} of {area_b_total}. Review remaining examples in the call log / Trends view.")
    if excluded:
        area_b_note_parts.append(f"{excluded} calls were excluded because the owner asked for a callback, so those are not counted as fair misses.")
    area_b_note = " ".join(area_b_note_parts)

    focus_col1, focus_col2 = st.columns(2, gap="medium")
    with focus_col1:
        focus_card(
            1,
            "Match the rebuttal to the exact objection",
            "Coach the agent to name the objection first, then use the right SOP response, then ask a simple next question.",
            area_a_total,
            area_a_rows,
            area_a_note,
        )
        feedback_widget("fb_area_a", str(agent.get("employee_id", "")), "Area 1 — rebuttal match")

    with focus_col2:
        focus_card(
            2,
            "Offer the plan when the owner asks directly",
            "When intent is explicit, the agent should move from explanation to a concrete plan and next step.",
            area_b_total,
            area_b_rows,
            area_b_note,
        )
        feedback_widget("fb_area_b", str(agent.get("employee_id", "")), "Area 2 — offer the plan")


def render_trends(agent: Dict[str, Any]) -> None:
    section_title("Trend and examples", "Use this view for the manager review, not just the agent summary.")
    col1, col2 = st.columns([1.25, 1], gap="medium")
    with col1:
        render_html(
            '<div class="soft-card"><div class="card-title">Performance over this cycle</div><div class="card-subtitle">Daily score combines rebuttal compliance and pitch-completion rate for this agent only.</div>',
        )
        trend_chart(agent.get("daily_trend", []))
        render_html('</div>')

    with col2:
        render_html(
            f'<div class="soft-card"><div class="card-title">A rebuttal that worked</div><div class="card-subtitle">Use this as the positive coaching anchor.</div>{good_example_html(agent.get("good_example"))}</div>',
        )

    section_title("Data note", "What was scored and what was intentionally excluded.")
    render_html(
        """
        <div class="soft-card">
          <div class="coach-note">
            <b>This cycle's focus areas were auto-detected, not manually transcript-reviewed.</b><br><br>
            Use the feedback buttons on the Overview tab to flag anything that looks wrong. Customer intent / language match is not scored because it is the AI analyser's read of the call, not something the agent controls.
          </div>
        </div>
        """,
    )


def render_profile(agent: Dict[str, Any]) -> None:
    initials = "".join(w[0] for w in str(agent.get("name", "A")).split()[:2]).upper() or "A"
    section_title("Agent profile", "Quick reference for manager 1:1 preparation.")

    col1, col2 = st.columns([.85, 1.65], gap="medium")
    with col1:
        render_html(
            f"""
            <div class="soft-card">
              <div class="profile-avatar">{esc(initials)}</div>
              <div class="profile-name">{esc(agent.get('name', 'Agent'))}</div>
              <div class="profile-meta">{esc(agent.get('employee_id', ''))} · Owner Sales</div>
            </div>
            """,
        )
    with col2:
        render_html(
            f"""
            <div class="quick-grid" style="margin:0; grid-template-columns: repeat(2, minmax(0, 1fr));">
              {quick_card('Calls this cycle', agent.get('n_live_calls', '—'), 'Live calls included in the current review cycle.', 'accent-teal')}
              {quick_card('Call score', call_score_value(agent), 'Pulled only from call_score in your JSON.', 'accent-coral')}
              {quick_card('RPL', f"₹{num(agent.get('rpl', 0)):.0f}", 'Revenue per lead for this agent.', 'accent-amber')}
              {quick_card('RPL rank', f"#{esc(agent.get('rpl_rank', '—'))} of 34", 'Relative performance inside the team.', 'accent-teal')}
            </div>
            """,
        )

    section_title("Manager note", "Keep the review clear, specific, and fair.")
    render_html(
        f"""
        <div class="soft-card">
          <div class="coach-note">
            Two areas were flagged this cycle by automated analysis of <b>{esc(agent.get('n_live_calls', '—'))}</b> live calls.
            Start with one strength, then choose one priority behaviour for the next cycle. Each issue is traceable to a call ID.
          </div>
        </div>
        """,
    )


def render_login(agents: Dict[str, Dict[str, Any]], directory: Dict[str, str]) -> None:
    st.markdown('<div style="max-width:980px; margin: 54px auto 0;">', unsafe_allow_html=True)
    hero_col, form_col = st.columns([1.05, 0.95], gap="medium")

    with hero_col:
        render_html(
            f"""
            <div class="login-hero" style="height:100%;">
              <div class="brand-logo">🤝</div>
              <div class="login-big">{esc(APP_NAME)} — {esc(APP_TAGLINE)}.</div>
              <div class="login-copy">
                Private agent view. Focuses on clear strengths, priority coaching moments, and call evidence — without overwhelming you.
              </div>
              <div class="hero-pills">
                <span class="hero-pill">Call-quality review</span>
                <span class="hero-pill">Feedback-ready</span>
                <span class="hero-pill">Manager 1:1 friendly</span>
              </div>
            </div>
            """,
        )

    with form_col:
        with st.container(border=True):
            st.markdown(
                '<div class="login-card-title">View your dashboard</div>'
                '<div class="login-card-copy">Enter your name or employee ID below. '
                'Use your full name if your first name is shared with another agent.</div>',
                unsafe_allow_html=True,
            )
            with st.form("login_form", border=False):
                query = st.text_input(
                    "Name or employee ID",
                    placeholder="Example: Noor Fathima or OS1234",
                    label_visibility="collapsed",
                )
                submitted = st.form_submit_button("Open dashboard →", use_container_width=True, type="primary")

    st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        key = query.strip().lower()
        if key == MANAGER_PASSCODE:
            st.session_state["is_manager"] = True
            st.rerun()
        agent_id, error = resolve_agent(query, agents, directory)
        if agent_id:
            st.session_state["agent_id"] = agent_id
            st.rerun()
        else:
            st.error(error)


def render_manager_view() -> None:
    render_html(
        f"""
        <div class="login-shell" style="grid-template-columns: 1fr;">
          <div class="login-hero">
            <div class="brand-logo">🤝</div>
            <div class="login-big">Manager view</div>
            <div class="login-copy">
              Every agent's 👍 / 👎 feedback and comments land in your sheet in real time, tagged by agent and coaching area.
            </div>
          </div>
        </div>
        """,
    )
    st.write("")
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.link_button("Open feedback sheet →", FEEDBACK_SHEET_URL, use_container_width=True)
        st.write("")
        if st.button("← Back to login", use_container_width=True):
            del st.session_state["is_manager"]
            st.rerun()


# ── MAIN ─────────────────────────────────────────────────────────────────
def main() -> None:
    inject_css()

    try:
        agents = load_agents(DATA_FILE, os.path.getmtime(DATA_FILE))
    except FileNotFoundError:
        st.error(f"Could not find {DATA_FILE}. Place it in the same folder as this app.")
        return
    except json.JSONDecodeError as exc:
        st.error(f"{DATA_FILE} is not valid JSON: {exc}")
        return

    directory = build_directory(agents)

    if st.session_state.get("is_manager"):
        render_manager_view()
        return

    if "agent_id" not in st.session_state:
        render_login(agents, directory)
        return

    agent_id = st.session_state["agent_id"]
    agent = agents.get(agent_id)
    if not agent:
        del st.session_state["agent_id"]
        st.error("This agent is no longer available in the data file. Please log in again.")
        st.rerun()

    top_l, top_r = st.columns([7, 1])
    with top_l:
        topbar()
    with top_r:
        if st.button("Log out", use_container_width=True):
            del st.session_state["agent_id"]
            st.rerun()

    render_hero(agent)

    tab_home, tab_trends, tab_profile = st.tabs(["Overview", "Trends", "Profile"])
    with tab_home:
        render_home(agent)
    with tab_trends:
        render_trends(agent)
    with tab_profile:
        render_profile(agent)


if __name__ == "__main__":
    main()
