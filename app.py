"""
Owner Sales — Call Quality Performance Portal
Streamlit app. Reads agents_data.json, shows each agent their own dashboard
after they enter their name/employee ID, and sends 👍/👎 feedback to a
Google Apps Script webhook (same one used by the previous HTML version).
"""

import json
import re
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ── CONFIG ────────────────────────────────────────────────────────────────
DATA_FILE = "agents_data.json"
FEEDBACK_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw2_97ldaS5GAu-OsKrIFHflhE2d7pZrw63DBWOtx2I05uO4l7VmPQE_y7NtouA65Db8Q/exec"

VIOLET = "#7C3AED"
VIOLET_DK = "#5B21B6"
NAVY = "#16233F"
SLATE = "#6B7280"
GREEN = "#0F9D58"
AMBER = "#B9700A"
RED = "#D64545"

st.set_page_config(page_title="Owner Sales Performance", page_icon="📞", layout="wide")


# ── DATA ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_agents():
    with open(DATA_FILE) as f:
        return json.load(f)


def build_directory(agents):
    directory = {}
    for eid, a in agents.items():
        name = a["name"]
        directory[str(name).split()[0].lower()] = eid
        directory[str(name).lower()] = eid
        directory[eid.lower()] = eid
    return directory


# ── STYLES ───────────────────────────────────────────────────────────────
def inject_css():
    st.markdown(
        f"""
        <style>
        .stApp {{ background: #F7F7FB; }}
        div.block-container {{ max-width: 1180px; padding-top: 1.5rem; padding-left: 2.5rem; padding-right: 2.5rem; }}
        .greet {{ font-size: 14px; color: {SLATE}; }}
        .greet b {{ color: {NAVY}; font-size: 26px; display:block; margin-top:2px; }}
        .pill {{ background: #F3EEFE; color: {VIOLET_DK}; font-size: 12px; font-weight: 700;
                 padding: 5px 13px; border-radius: 20px; display:inline-block; margin-top: 10px; }}
        .card {{ background: #fff; border-radius: 16px; padding: 22px 26px; margin-bottom: 18px;
                 box-shadow: 0 1px 4px rgba(20,20,50,0.06); height: 100%; }}
        .card h3 {{ margin: 0 0 12px; font-size: 16px; }}
        .strength-item {{ display:flex; gap:10px; padding:10px 0; border-top:1px solid #EAEAF2; font-size:14px; line-height:1.5; }}
        .strength-item:first-of-type {{ border-top:none; }}
        .moment {{ background:#F7F7FB; border-radius:10px; padding:14px 16px; margin-bottom:10px; font-size:13.5px; }}
        .moment .owner {{ font-style:italic; color:{NAVY}; }}
        .moment .miss {{ color:{RED}; margin-top:5px; }}
        .cdr-tag {{ font-family:monospace; font-size:10px; background:#EEF0F6; color:{SLATE};
                    padding:2px 7px; border-radius:20px; }}
        .sec-label {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:{SLATE};
                      font-weight:700; margin:24px 2px 10px; }}
        .footnote {{ font-size:12px; color:{SLATE}; line-height:1.6; margin-top:12px; padding-top:12px;
                     border-top:1px dashed #EAEAF2; }}
        [data-testid="stMetric"] {{ background:#fff; border-radius:14px; padding:14px 18px;
                     box-shadow: 0 1px 4px rgba(20,20,50,0.06); }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
        .stTabs [data-baseweb="tab"] {{ height: 42px; padding: 0 20px; border-radius: 10px 10px 0 0; }}
        div[data-testid="stExpander"] {{ background:#fff; border-radius:16px; box-shadow: 0 1px 4px rgba(20,20,50,0.06);
                     border: none; margin-bottom: 16px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── COMPONENTS ───────────────────────────────────────────────────────────
def score_ring(score: int, conv_q: int, conv_s: int):
    color = GREEN if score >= 65 else (AMBER if score >= 35 else RED)
    fig = go.Figure(
        go.Pie(
            values=[score, 100 - score],
            hole=0.78,
            marker_colors=[color, "#EFEFF4"],
            textinfo="none",
            sort=False,
            direction="clockwise",
            rotation=90,
        )
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=170,
        width=170,
        annotations=[dict(text=f"<b>{score}</b><br><span style='font-size:11px;color=#6B7280'>out of 100</span>",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=28, color=NAVY))],
    )
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3>Overall performance</h3>", unsafe_allow_html=True)
    ring_col, metrics_col = st.columns([1, 1.2])
    with ring_col:
        st.plotly_chart(fig, use_container_width=False, config={"displayModeBar": False})
    with metrics_col:
        st.metric("Conversation quality", conv_q)
        st.metric("Conversion", conv_s)
    st.caption("Based only on what they said or did on calls — not the AI's read of the customer")
    st.markdown("</div>", unsafe_allow_html=True)


def trend_chart(points):
    if len(points) < 2:
        st.markdown(
            '<div class="footnote">Not enough day-to-day spread in this cycle\'s data to chart a '
            "reliable daily trend yet — will build out once more cycles run.</div>",
            unsafe_allow_html=True,
        )
        return
    df = pd.DataFrame(points)
    fig = go.Figure(
        go.Scatter(
            x=df["date"], y=df["score"], mode="lines+markers+text",
            text=df["score"], textposition="top center",
            line=dict(color=AMBER, width=3), marker=dict(size=8, color=AMBER),
        )
    )
    fig.update_layout(
        height=200, margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(range=[0, 100], gridcolor="#EAEAF2"),
        xaxis=dict(gridcolor="#EAEAF2"),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    diff = df["score"].iloc[-1] - df["score"].iloc[0]
    if diff > 0:
        st.markdown(f"<span style='color:{GREEN};font-weight:700;'>↑ {int(diff)} points</span> from first day to last", unsafe_allow_html=True)
    elif diff < 0:
        st.markdown(f"<span style='color:{RED};font-weight:700;'>↓ {int(abs(diff))} points</span> from first day to last", unsafe_allow_html=True)
    else:
        st.markdown("Flat — no change from first day to last")


def cdr_chip(cdr_id: str):
    short = cdr_id[:8]
    key = f"cdr_{cdr_id}"
    shown = st.session_state.get(key, False)
    label = cdr_id if shown else short
    if st.button(label, key=key + "_btn"):
        st.session_state[key] = not shown
        st.rerun()


def moment_card_a(item):
    st.markdown(
        f"""<div class="moment">
        <div class="owner">👤 {item['objection'] or ''} <span style="color:{SLATE};">({(item['sop'] or '').split(':')[0]})</span></div>
        <div class="miss">✕ Rebuttal did not follow the required SOP for this objection</div>
        </div>""",
        unsafe_allow_html=True,
    )
    cdr_chip(item["cdr_id"])


def moment_card_b(item):
    st.markdown(
        f"""<div class="moment">
        <div class="owner">👤 {item['reason'] or ''}</div>
        <div class="miss">✕ No plan offered on this call</div>
        </div>""",
        unsafe_allow_html=True,
    )
    cdr_chip(item["cdr_id"])


def send_feedback(agent_id, area, reaction, comment):
    payload = {"agent": agent_id, "area": area, "reaction": reaction, "comment": comment,
               "timestamp": datetime.utcnow().isoformat()}
    try:
        requests.post(FEEDBACK_WEBHOOK_URL, json=payload, timeout=5)
        return True
    except Exception as e:
        st.warning(f"Couldn't reach the feedback sheet right now ({e}). Try again shortly.")
        return False


def feedback_widget(key, agent_id, area_title):
    st.markdown("---")
    st.caption("Does this feel fair and accurate?")
    c1, c2 = st.columns(2)
    reaction_key = f"{key}_reaction"
    if c1.button("👍 Like", key=f"{key}_like"):
        st.session_state[reaction_key] = "like"
    if c2.button("👎 Dislike", key=f"{key}_dislike"):
        st.session_state[reaction_key] = "dislike"
    if st.session_state.get(reaction_key):
        comment = st.text_area("Anything you'd add — context we might be missing, a call you'd push back on, etc.",
                                key=f"{key}_comment")
        if st.button("Submit", key=f"{key}_submit"):
            ok = send_feedback(agent_id, area_title, st.session_state[reaction_key], comment)
            if ok:
                st.success("✓ Thanks — noted for review")
                del st.session_state[reaction_key]


# ── PAGES ────────────────────────────────────────────────────────────────
def render_home(agent):
    left, right = st.columns([1, 1.3], gap="large")

    with left:
        score_ring(agent["overall_score"], agent["conversation_quality"], agent["conversion_score"])

    with right:
        st.markdown('<div class="card"><h3>👍 What\'s genuinely working</h3>', unsafe_allow_html=True)
        for s in agent["strengths"]:
            st.markdown(f'<div class="strength-item">✅ {s}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="sec-label">2 areas to focus on</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        with st.expander(f"1️⃣ Match the rebuttal to the specific objection — {agent['area_a_total']} this cycle", expanded=True):
            if agent["area_a"]:
                for item in agent["area_a"][:4]:
                    moment_card_a(item)
                if agent["area_a_total"] > 4:
                    st.caption(f"+{agent['area_a_total']-4} more this cycle — see Trends tab")
            else:
                st.caption("No SOP-mapped rebuttal misses found this cycle — good sign.")
            feedback_widget("fb1", agent["employee_id"], "Area 1 — rebuttal match")

    with col_b:
        with st.expander(f"2️⃣ Offer the plan when the owner asks directly — {agent['area_b_total']} this cycle", expanded=True):
            if agent["area_b"]:
                for item in agent["area_b"][:4]:
                    moment_card_b(item)
                if agent["area_b_total"] > 4:
                    st.caption(f"+{agent['area_b_total']-4} more this cycle — see Trends tab")
            else:
                st.caption("No confirmed missed high-intent pitches this cycle — good sign.")
            if agent["area_b_excluded_deferred"]:
                st.caption(f"{agent['area_b_excluded_deferred']} more excluded — owner asked for a callback, not a fair miss.")
            feedback_widget("fb2", agent["employee_id"], "Area 2 — offer the plan")


def render_trends(agent):
    col1, col2 = st.columns([1.4, 1], gap="large")

    with col1:
        st.markdown('<div class="sec-label">Performance over this cycle</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        trend_chart(agent["daily_trend"])
        st.markdown(
            '<div class="footnote">Score = 50% rebuttal compliance + 50% pitch-completion rate that day, '
            "for this agent only. Days with fewer than 5 relevant calls are skipped. This chart covers one "
            "review cycle — each future cycle adds another point, building toward a real trend.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        if agent["good_example"]:
            g = agent["good_example"]
            st.markdown('<div class="sec-label">A rebuttal that worked</div>', unsafe_allow_html=True)
            st.markdown(
                f"""<div class="card">
                <b>{(g['sop'] or '').split(':')[0]}</b><br><br>
                <span style="color:{SLATE};">Owner:</span> {g['objection'] or ''}<br><br>
                <span style="color:{GREEN};font-weight:600;">Reply:</span> {g['rebuttal'] or ''}
                </div>""",
                unsafe_allow_html=True,
            )
            cdr_chip(g["cdr_id"])

    st.markdown(
        '<div class="footnote"><b>This cycle\'s areas were auto-detected</b>, not manually transcript-reviewed. '
        "Use the 👍/👎 feedback on Home to flag anything that looks wrong.<br><br>"
        "<b>Customer intent / language match not scored</b> — that\'s the AI analyser\'s read of the call, "
        "not something the agent controls.</div>",
        unsafe_allow_html=True,
    )


def render_profile(agent):
    header_col, stats_col = st.columns([1, 1.6], gap="large")

    with header_col:
        st.markdown(
            f"""<div style="text-align:center; padding: 10px 0 20px;">
            <div style="width:74px;height:74px;border-radius:50%;background:{VIOLET};color:#fff;
                        font-size:26px;font-weight:700;display:flex;align-items:center;justify-content:center;
                        margin:0 auto 10px;">{''.join(w[0] for w in agent['name'].split()[:2]).upper()}</div>
            <h2 style="margin:0;">{agent['name']}</h2>
            <div style="color:{SLATE};font-size:12.5px;">{agent['employee_id']} · Owner Sales</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with stats_col:
        c1, c2 = st.columns(2)
        c1.metric("Calls this cycle", agent["n_live_calls"])
        c2.metric("Overall score", agent["overall_score"])
        c1.metric("RPL", f"₹{agent['rpl']:.0f}")
        c2.metric("RPL rank", f"#{agent['rpl_rank']} of 34")

    st.markdown(
        f"""<div class="card" style="margin-top:16px;">
        <h3>Manager note</h3>
        <p style="font-size:14px;color:{SLATE};">Two areas flagged this cycle by automated analysis of
        {agent['n_live_calls']} live calls — review the 👍/👎 feedback before the next 1:1.</p>
        <div class="footnote">The call analyser tags things like customer intent by reading the call —
        that's not something the agent controls, so it's excluded from the score. Everything else is
        their own words and actions, each traceable to a call ID.</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ── LOGIN ────────────────────────────────────────────────────────────────
def render_login(agents, directory):
    spacer_l, mid, spacer_r = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(
            f"""<div style="text-align:center; padding: 60px 0 20px;">
            <div style="width:52px;height:52px;border-radius:16px;background:{VIOLET};color:#fff;
                        display:flex;align-items:center;justify-content:center;font-weight:700;font-size:20px;
                        margin:0 auto 20px;">OS</div>
            <h1 style="font-size:24px;margin:0 0 8px;">Owner Sales Performance</h1>
            <p style="color:{SLATE};font-size:14px;">Enter your name or employee ID to see your own
            call quality dashboard for this cycle.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        query = st.text_input("Your name or employee ID", label_visibility="collapsed",
                               placeholder="Your name or employee ID")
        if st.button("View my dashboard", use_container_width=True):
            key = query.strip().lower()
            agent_id = directory.get(key)
            if agent_id:
                st.session_state["agent_id"] = agent_id
                st.rerun()
            else:
                st.error("Couldn't find that name or ID — check spelling, or ask your manager if you're not set up yet.")


# ── MAIN ─────────────────────────────────────────────────────────────────
def main():
    inject_css()
    agents = load_agents()
    directory = build_directory(agents)

    if "agent_id" not in st.session_state:
        render_login(agents, directory)
        return

    agent = agents[st.session_state["agent_id"]]

    top_l, top_r = st.columns([6, 1])
    with top_l:
        st.markdown(
            f'<div class="greet">Good morning<b>{agent["name"]}</b>'
            f'<span class="pill">⚡ 2 focus areas this week</span></div>',
            unsafe_allow_html=True,
        )
    with top_r:
        if st.button("← Log out"):
            del st.session_state["agent_id"]
            st.rerun()

    tab_home, tab_trends, tab_profile = st.tabs(["🏠 Home", "📊 Trends", "👤 Profile"])
    with tab_home:
        render_home(agent)
    with tab_trends:
        render_trends(agent)
    with tab_profile:
        render_profile(agent)


if __name__ == "__main__":
    main()
