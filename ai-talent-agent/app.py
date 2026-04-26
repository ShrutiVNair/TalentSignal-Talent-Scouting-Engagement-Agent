from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src.agents.ranking_agent import get_match
from src.config import get_settings
from src.database.db import fetch_all, resolve_db_path
from src.database.models import ensure_database
from src.database.seed import seed_all
from src.integrations.communication.email_adapter import get_status as email_status
from src.jd_extractor import extract_text
from src.jd_parser import parse_jd
from src.llm_client import LLMClient
from src.services.audit_service import list_audit_logs
from src.services.batch_scoring_service import get_top_matches, score_candidates_for_role
from src.services.candidate_service import get_candidate, list_candidates, upsert_candidate
from src.services.compliance_service import evaluate_compliance, get_compliance_record
from src.services.contact_validation_service import contact_readiness
from src.services.deduplication_service import check_duplicate
from src.services.email_outreach_service import approve_email, generate_email_draft, get_email_status, send_test_email
from src.services.engagement_service import (
    build_hr_decision_summary,
    capture_candidate_reply,
    latest_simulation_for_candidate,
    list_reply_timeline,
    simulate_outreach_for_role,
)
from src.services.role_service import create_role, get_role, list_roles
from src.services.scheduling_service import create_mock_meeting_recommendation, suggested_recruiter_screen_slots


load_dotenv()
ensure_database()
seed_all()

st.set_page_config(page_title="TalentSignal AI", page_icon=":material/groups:", layout="wide")


DEMO_JD = """Senior Frontend Engineer
Requires 5+ years building polished React, TypeScript, GraphQL, and SaaS product experiences.
The role partners closely with design, product, and backend teams to ship reliable customer-facing workflows.
Remote-friendly with strong ownership, accessibility, and performance expectations.
"""

DEMO_CANDIDATE = {
    "id": "DEMO-SHRUTI-001",
    "name": "Shruti Nair",
    "email": "shrutinair.ai31@gmail.com",
    "phone": "",
    "linkedin_url": "",
    "github_url": "",
    "portfolio_url": "",
    "location": "Remote",
    "current_company": "TalentSignal Demo",
    "current_title": "Senior Frontend Engineer",
    "years_experience": 6,
    "skills": ["React", "TypeScript", "GraphQL", "SaaS", "Accessibility"],
    "summary": "Demo candidate with a real email path for end-to-end TalentSignal outreach.",
    "resume_text": "Senior Frontend Engineer with React, TypeScript, GraphQL, SaaS platforms, accessibility, and product engineering experience.",
    "compensation_expectation": "$150k",
    "availability": "Available this week",
    "work_mode_preference": "remote",
    "domain_experience": "SaaS product engineering",
    "engagement_persona": "Curious evaluator",
    "contact_source": "demo",
    "contact_consent_status": "demo_assumed",
    "contact_readiness_status": "Ready for email draft",
    "contact_readiness_reason": "Valid email available for test-mode outreach.",
    "preferred_channel": "email",
    "email_confidence": 1,
    "phone_confidence": 0,
    "linkedin_confidence": 0,
    "profile_parse_confidence": 0.9,
}


def inject_theme_styles(theme: str) -> None:
    dark = theme == "Dark"
    if dark:
        bg = (
            "radial-gradient(circle at 18% 12%, rgba(44, 95, 255, .32), transparent 30%),"
            "radial-gradient(circle at 82% 8%, rgba(236, 72, 153, .30), transparent 32%),"
            "linear-gradient(135deg, #050814 0%, #101827 48%, #1b1033 100%)"
        )
    else:
        bg = (
            "radial-gradient(circle at 18% 14%, rgba(78, 205, 196, .75), transparent 35%),"
            "radial-gradient(circle at 82% 10%, rgba(255, 150, 96, .72), transparent 34%),"
            "linear-gradient(135deg, #a7f3ee 0%, #c9befa 48%, #ffc29a 100%)"
        )
    text = "#f8fbff" if dark else "#101828"
    muted = "#b8c7dc" if dark else "#475467"
    card = "rgba(15, 23, 42, .70)" if dark else "rgba(255, 255, 255, .72)"
    field = "rgba(15, 23, 42, .42)" if dark else "rgba(255, 255, 255, .46)"
    field_hover = "rgba(30, 41, 59, .58)" if dark else "rgba(255, 255, 255, .64)"
    border = "rgba(255,255,255,.16)" if dark else "rgba(255,255,255,.58)"
    primary = "#38bdf8" if dark else "#2563eb"
    success = "#22c55e" if dark else "#047857"
    warning = "#f59e0b" if dark else "#b45309"
    danger = "#ef4444" if dark else "#b91c1c"
    glow = "rgba(56, 189, 248, .35)" if dark else "rgba(59, 130, 246, .30)"
    sidebar = "rgba(8, 13, 30, .72)" if dark else "rgba(255, 255, 255, .20)"
    chip_text = "#f8fbff" if dark else "#102033"
    dropdown_bg = "#111827" if dark else "#f8fafc"
    dropdown_hover = "#1f2937" if dark else "#e0f2fe"
    dropdown_selected = "#0f766e" if dark else "#bfdbfe"
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        .stApp {{
            --bg: {bg};
            --card-bg: {card};
            --text: {text};
            --muted: {muted};
            --border: {border};
            --primary: {primary};
            --success: {success};
            --warning: {warning};
            --danger: {danger};
            --ts-text: {text};
            --ts-muted: {muted};
            --ts-card: {card};
            --ts-field: {field};
            --ts-field-hover: {field_hover};
            --ts-border: {border};
            --ts-glow: {glow};
            background: {bg};
            color: {text};
            font-family: Inter, system-ui, sans-serif;
        }}
        header[data-testid="stHeader"],
        [data-testid="stHeader"],
        [data-testid="stDecoration"] {{
            background: transparent !important;
            display: none !important;
            height: 0 !important;
        }}
        [data-testid="stToolbar"], [data-testid="stStatusWidget"], #MainMenu, footer {{
            display: none !important;
            visibility: hidden !important;
        }}
        [data-testid="stAppViewContainer"] {{
            background: {bg};
        }}
        .block-container {{
            padding: .85rem 2rem 2.4rem;
            max-width: 1240px;
        }}
        h1, h2, h3, p, label, span, div {{
            font-family: Inter, system-ui, sans-serif;
            letter-spacing: 0;
            color: {text};
        }}
        [data-testid="stSidebar"] {{
            width: 220px !important;
            min-width: 220px !important;
            background: {sidebar} !important;
            backdrop-filter: blur(18px);
            border-right: 1px solid {border};
        }}
        [data-testid="stSidebar"] * {{
            color: {text} !important;
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] > div {{
            background: {field} !important;
            border-color: {border} !important;
            min-height: 2.35rem !important;
            overflow: hidden !important;
        }}
        .ts-topbar {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1rem; padding:.2rem .1rem; }}
        .brand {{ font-size:1.18rem; font-weight:900; color:{text}; }}
        .brand-mark {{ font-size:2rem; font-weight:900; margin-right:.55rem; }}
        .demo-grid {{ display:grid; grid-template-columns: 1.05fr 1.05fr 1fr; gap:1rem; align-items:stretch; }}
        .glass-card {{
            background: {card};
            border: 1px solid {border};
            border-radius: 20px;
            padding: 1rem;
            min-height: 100%;
            color: {text};
            box-shadow: inset 0 1px 0 rgba(255,255,255,.22), 0 18px 42px rgba(15, 23, 42, .16);
            backdrop-filter: blur(18px);
        }}
        .section-title {{
            font-size: 1.15rem;
            font-weight: 900;
            margin: .2rem 0 .35rem;
            color: {text};
        }}
        .section-subtitle {{
            color: {muted};
            margin: 0 0 1rem;
        }}
        .score-grid {{
            display:grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap:.6rem;
            margin:.7rem 0;
        }}
        .score-tile {{
            border: 1px solid {border};
            border-radius: 14px;
            padding:.65rem;
            background: rgba(255,255,255,.12);
        }}
        .outreach-page-title {{
            margin: .2rem 0 1.05rem;
        }}
        .outreach-page-title h1 {{
            font-size: 2rem;
            line-height: 1.08;
            margin: 0 0 .25rem;
            color: {text};
        }}
        .outreach-page-title p {{
            margin: 0;
            color: {muted};
            font-size: 1rem;
        }}
        .recipient-box {{
            border: 1px solid {border};
            border-radius: 15px;
            padding: .85rem;
            margin-top: .9rem;
            background: rgba(59, 130, 246, .12);
        }}
        .recipient-box div {{
            margin: .22rem 0;
            color: {text};
        }}
        .safety-note {{
            border-radius: 12px;
            padding: .65rem .75rem;
            margin-top: .6rem;
            background: rgba(34, 197, 94, .13);
            color: {text};
            font-weight: 700;
        }}
        .summary-callout {{
            border-radius: 14px;
            padding: .75rem .85rem;
            margin: .75rem 0;
            background: rgba(34, 197, 94, .15);
            border: 1px solid rgba(34, 197, 94, .30);
            color: {text};
            font-weight: 800;
        }}
        .compact-list {{
            margin: .35rem 0 .75rem 1rem;
            padding: 0;
        }}
        .compact-list li {{
            margin: .22rem 0;
            color: {text};
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: {card};
            border: 1px solid {border};
            border-radius: 20px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.20), 0 16px 36px rgba(15, 23, 42, .12);
            backdrop-filter: blur(18px);
        }}
        .mini-card {{
            border: 1px solid {border};
            border-radius: 16px;
            padding: .85rem;
            background: rgba(255,255,255,.16);
            margin: .72rem 0;
        }}
        .card-title {{ color:{text}; font-weight:800; font-size:.9rem; text-transform:uppercase; margin-bottom:.8rem; opacity:.92; }}
        .hero-role {{ font-size:1.45rem; line-height:1.08; font-weight:800; color:{text}; margin-bottom:1rem; }}
        .muted {{ color:{muted}; font-size:.9rem; }}
        .progress-track {{ height:.55rem; border-radius:999px; background:rgba(255,255,255,.25); overflow:hidden; }}
        .progress-fill {{ height:100%; border-radius:999px; background:linear-gradient(90deg,#2f80ed,#5eead4); box-shadow:0 0 22px {glow}; }}
        .pipeline-step {{ display:flex; gap:.8rem; align-items:center; }}
        .step-icon {{ width:2.35rem; height:2.35rem; border-radius:12px; display:grid; place-items:center; background:rgba(255,255,255,.20); border:1px solid {border}; }}
        .chip {{ display:inline-flex; align-items:center; justify-content:center; min-width:5.2rem; border-radius:999px; padding:.28rem .65rem; font-size:.74rem; line-height:1; font-weight:800; border:1px solid {border}; white-space:nowrap; color:{chip_text}; }}
        .chip.green {{ background:rgba(34,197,94,.22); color:{'#dcfce7' if dark else '#047857'}; }}
        .chip.blue {{ background:rgba(59,130,246,.22); color:{'#dbeafe' if dark else '#1d4ed8'}; }}
        .chip.amber {{ background:rgba(245,158,11,.22); color:{'#fef3c7' if dark else '#92400e'}; }}
        .chip.red {{ background:rgba(239,68,68,.20); color:{'#fee2e2' if dark else '#b91c1c'}; }}
        .score-badge {{ width:5.6rem; height:5.6rem; border-radius:999px; display:grid; place-items:center; margin:.5rem 0; font-size:1.45rem; font-weight:900; color:{text}; background: conic-gradient(#22c55e var(--score), rgba(255,255,255,.22) 0); }}
        .score-badge span {{ width:4.25rem; height:4.25rem; border-radius:999px; background:{card}; display:grid; place-items:center; }}
        .metric-row {{ display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:.8rem; margin-top:1rem; }}
        .timeline-item {{ border-left:3px solid #38bdf8; padding-left:.75rem; margin:.8rem 0; }}
        .chat-bubble {{
            border: 1px solid {border};
            border-radius: 16px;
            padding: .85rem;
            margin: .65rem 0;
            background: rgba(255,255,255,.14);
        }}
        .chat-bubble.candidate {{
            background: rgba(34,197,94,.13);
        }}
        .chat-bubble.analysis {{
            background: rgba(59,130,246,.13);
        }}
        .shortlist-card {{
            border: 1px solid {border};
            border-radius: 16px;
            padding: .72rem .82rem;
            background: rgba(255,255,255,.14);
            margin: .55rem 0;
        }}
        .button-row {{ display:flex; gap:.65rem; margin-top:.75rem; }}
        textarea,
        input,
        [data-baseweb="base-input"],
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-testid="stTextArea"] textarea,
        [data-testid="stTextInput"] input,
        [data-testid="stFileUploader"] section,
        [data-testid="stFileUploaderDropzone"] {{
            background: {field} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }}
        [data-baseweb="base-input"] > div,
        [data-testid="stTextArea"] div,
        [data-testid="stTextInput"] div {{
            background: transparent !important;
        }}
        textarea:focus,
        input:focus,
        [data-baseweb="base-input"]:focus-within,
        [data-baseweb="select"] > div:hover,
        [data-testid="stFileUploader"] section:hover {{
            background: {field_hover} !important;
            border-color: rgba(56, 189, 248, .58) !important;
        }}
        textarea::placeholder,
        input::placeholder {{
            color: {muted} !important;
        }}
        textarea:disabled,
        input:disabled,
        textarea[disabled],
        input[disabled],
        [aria-disabled="true"] textarea,
        [aria-disabled="true"] input {{
            color: {text} !important;
            -webkit-text-fill-color: {text} !important;
            opacity: 1 !important;
            background: {field} !important;
        }}
        [data-testid="stTextArea"] textarea:disabled,
        [data-testid="stTextInput"] input:disabled {{
            color: {text} !important;
            -webkit-text-fill-color: {text} !important;
            opacity: 1 !important;
        }}
        [data-testid="stFileUploader"] button {{
            background: rgba(56, 189, 248, .18) !important;
            color: {text} !important;
            border: 1px solid {border} !important;
            border-radius: 10px !important;
        }}
        [data-testid="stFileUploader"] small,
        [data-testid="stFileUploader"] span,
        [data-testid="stFileUploader"] p {{
            color: {muted} !important;
        }}
        [data-baseweb="popover"],
        [data-baseweb="menu"],
        [role="listbox"] {{
            background: {dropdown_bg} !important;
            border: 1px solid {border} !important;
            color: {text} !important;
            box-shadow: 0 18px 45px rgba(15,23,42,.22) !important;
        }}
        [role="option"],
        [data-baseweb="menu"] li,
        [data-baseweb="menu"] div {{
            background: {dropdown_bg} !important;
            color: {text} !important;
        }}
        [role="option"]:hover,
        [data-baseweb="menu"] li:hover,
        [aria-selected="true"] {{
            background: {dropdown_hover} !important;
            color: {text} !important;
        }}
        [role="option"][aria-selected="true"] {{
            background: {dropdown_selected} !important;
            color: {text} !important;
        }}
        [data-testid="stExpander"],
        [data-testid="stExpander"] details {{
            background: {card} !important;
            border: 1px solid {border} !important;
            border-radius: 16px !important;
            overflow: hidden;
        }}
        [data-testid="stExpander"] summary {{
            background: {field} !important;
            color: {text} !important;
            border-radius: 14px !important;
            padding: .75rem .9rem !important;
        }}
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] div,
        [data-testid="stExpander"] label {{
            color: {text} !important;
        }}
        div[role="radiogroup"] label {{
            background: transparent !important;
        }}
        div.stButton > button {{
            border-radius: 999px;
            border: 1px solid {border};
            background: linear-gradient(135deg, #38bdf8, #2563eb);
            color: white;
            font-weight: 800;
            box-shadow: 0 12px 28px {glow};
        }}
        div.stButton > button * {{
            color: inherit !important;
        }}
        div.stButton > button[kind="secondary"] {{ background: rgba(255,255,255,.16); color:{text}; box-shadow:none; }}
        @media (max-width: 980px) {{
            .block-container {{ padding: 1rem; }}
            .demo-grid, .metric-row, .score-grid {{ grid-template-columns: 1fr; }}
            .ts-topbar {{ align-items:flex-start; flex-direction:column; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_glass_card(title: str, body: str = "") -> None:
    st.markdown(f"<div class='glass-card'><div class='card-title'>{title}</div>{body}</div>", unsafe_allow_html=True)


def render_status_chip(label: str, tone: str = "blue") -> str:
    return f"<span class='chip {tone}'>{label}</span>"


def render_metric_card(label: str, value: Any, helper: str = "") -> str:
    return f"<div class='mini-card'><div class='muted'>{label}</div><div style='font-size:1.55rem;font-weight:900'>{value}</div><div class='muted'>{helper}</div></div>"


def render_pipeline_step(label: str, detail: str, done: bool = False, active: bool = False) -> str:
    tone = "green" if done else "blue" if active else "amber"
    status = "Complete" if done else "In progress" if active else "Queued"
    return (
        "<div class='mini-card pipeline-step'>"
        f"<div class='step-icon'>{'✓' if done else '•'}</div>"
        f"<div><b>{label}: {status}</b><div class='muted'>{detail}</div></div>"
        f"<div style='margin-left:auto'>{render_status_chip(status, tone)}</div>"
        "</div>"
    )


def render_score_badge(score: float) -> str:
    value = max(0, min(100, int(score or 0)))
    return f"<div class='score-badge' style='--score:{value}%;'><span>{value}%</span></div>"


def candidate_status(candidate: dict[str, Any], match: dict[str, Any]) -> tuple[str, str]:
    readiness = contact_readiness(candidate, match.get("compliance_status") or {"outreach_allowed": True})
    compliance = match.get("compliance_status") or {}
    match_score = float(match.get("match_score", 0))
    if compliance.get("outreach_allowed") is False:
        return "Blocked", "red"
    if not candidate.get("email_valid"):
        return "Needs contact info", "amber"
    if readiness.get("preferred_channel") != "email":
        return "Missing contact", "amber"
    if match_score >= 70:
        return "Shortlisted", "green"
    if match_score >= 50:
        return "Needs review", "amber"
    return "Filtered out", "red"


def ranked_candidate_rows(role_id: int | None, limit: int = 10) -> list[dict[str, Any]]:
    if not role_id:
        return []
    rows = []
    for match in get_top_matches(role_id, limit=50):
        candidate = get_candidate(match["candidate_id"])
        if not candidate:
            continue
        status, tone = candidate_status(candidate, match)
        scorecard = match.get("scorecard") or {}
        reason = (scorecard.get("strengths") or [scorecard.get("explanation") or "Scored against the active role."])[0]
        compliance_clear = (match.get("compliance_status") or {}).get("outreach_allowed", True) is not False
        email_ready = bool(candidate.get("email_valid"))
        rows.append(
            {
                "candidate": candidate,
                "match": match,
                "status": status,
                "tone": tone,
                "reason": reason,
                "email_ready": email_ready,
                "rank_score": (
                    1 if compliance_clear else 0,
                    1 if email_ready else 0,
                    combined_score(match),
                    float(match.get("match_score", 0)),
                    float(match.get("interest_score", 0)),
                ),
            }
        )
    rows.sort(key=lambda item: item["rank_score"], reverse=True)
    return rows[:limit]


def top_match_for_role(role_id: int | None) -> dict[str, Any] | None:
    rows = ranked_candidate_rows(role_id, limit=1)
    return rows[0]["match"] if rows else None


def evaluated_candidates(role_id: int | None, limit: int = 10) -> list[dict[str, Any]]:
    return ranked_candidate_rows(role_id, limit=limit)


def combined_score(match: dict[str, Any]) -> float:
    return round(float(match.get("match_score", 0)) * 0.65 + float(match.get("interest_score", 0)) * 0.35, 1)


def recommendation_for_scores(match: dict[str, Any], status: str) -> str:
    match_score = float(match.get("match_score", 0))
    interest_score = float(match.get("interest_score", 0))
    if status == "Blocked":
        return "Do not contact"
    if match_score >= 80 and interest_score >= 70:
        return "Schedule recruiter screen"
    if match_score >= 70 and interest_score >= 40:
        return "Send role details"
    if match_score >= 50 and interest_score >= 70:
        return "Recruiter review"
    if interest_score < 40:
        return "Keep warm"
    return "Recruiter review"


def match_explanation(candidate: dict[str, Any], match: dict[str, Any]) -> str:
    scorecard = match.get("scorecard") or {}
    strengths = scorecard.get("strengths") or []
    gaps = scorecard.get("gaps") or []
    skills = ", ".join((candidate.get("skills") or [])[:4])
    reason = strengths[0] if strengths else f"Relevant experience across {skills or 'the target skill set'}."
    gap_text = f" Missing/unclear: {', '.join(gaps[:2])}." if gaps else ""
    return f"{reason}{gap_text} Location/work mode and compliance are considered before outreach."


def render_candidate_explanation(candidate: dict[str, Any], role: dict[str, Any], match: dict[str, Any], status: str) -> None:
    scorecard = match.get("scorecard") or {}
    candidate_skills = {str(skill).lower(): str(skill) for skill in candidate.get("skills", [])}
    required_skills = [str(skill) for skill in role.get("required_skills", [])]
    matched = [skill for skill in required_skills if skill.lower() in candidate_skills]
    missing = [skill for skill in required_skills if skill.lower() not in candidate_skills]
    experience = candidate.get("years_experience") or 0
    role_min = role.get("experience_min") or 0
    experience_fit = scorecard.get("experience_score", 0)
    location_fit = scorecard.get("location_score", scorecard.get("work_mode_score", 0))
    simulation = latest_simulation_for_candidate(candidate["id"], role["id"])
    interest_reason = (simulation or {}).get("hr_summary") or latest_interest_evidence(candidate["id"], role["id"])["detail"]
    recommendation = recommendation_for_scores(match, status)
    combined = combined_score(match)
    st.markdown(
        f"""
        <div class='shortlist-card' style='background:rgba(56,189,248,.10)'>
          <div style='font-weight:900;margin-bottom:.45rem'>Explanation for {escape(candidate['name'])}</div>
          <div class='score-grid'>
            <div class='score-tile'><div class='muted'>Matched required skills</div><b>{escape(', '.join(matched) if matched else 'None confirmed')}</b></div>
            <div class='score-tile'><div class='muted'>Missing skills</div><b>{escape(', '.join(missing[:4]) if missing else 'No major required-skill gap')}</b></div>
            <div class='score-tile'><div class='muted'>Experience fit</div><b>{escape(str(experience))} yrs vs {escape(str(role_min))}+ required · {int(experience_fit)}%</b></div>
          </div>
          <p class='muted'><b>Location/work mode fit:</b> {int(location_fit)}% based on candidate preference and role setup.</p>
          <p class='muted'><b>Interest evidence:</b> {escape(interest_reason)}</p>
          <p class='muted'><b>Recommendation reason:</b> {escape(recommendation)} because match is {int(match.get('match_score', 0))}% and simulated interest is {int(match.get('interest_score', 0))}%.</p>
          <p class='muted'><b>Combined score:</b> 0.65 × {int(match.get('match_score', 0))} + 0.35 × {int(match.get('interest_score', 0))} = {combined}%.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def latest_interest_evidence(candidate_id: str | None, role_id: int | None) -> dict[str, Any]:
    if not candidate_id or not role_id:
        return {"label": "No replies yet", "detail": "Interest starts from profile and availability signals."}
    replies = list_reply_timeline(candidate_id, role_id)
    if not replies:
        return {"label": "No replies yet", "detail": "Interest starts from profile and availability signals."}
    analysis = replies[-1].get("analysis", {})
    delta = float(analysis.get("interest_delta", 0))
    direction = "↑" if delta > 0 else "↓" if delta < 0 else "→"
    return {
        "label": f"{direction} {delta:+.0f} from latest reply",
        "detail": analysis.get("hr_summary", "Latest reply analyzed."),
        "analysis": analysis,
    }


def render_candidate_shortlist_card(candidate: dict[str, Any] | None, match: dict[str, Any] | None) -> None:
    if not candidate:
        render_glass_card("Ranked Shortlist", "<p class='muted'>Add a candidate and run Talent Scan to see the top match.</p>")
        return
    match_score = float((match or {}).get("match_score", 0))
    interest = float((match or {}).get("interest_score", 50))
    level = "HIGH" if interest >= 70 else "MEDIUM" if interest >= 45 else "LOW"
    tone = "green" if level == "HIGH" else "amber" if level == "MEDIUM" else "red"
    scorecard = (match or {}).get("scorecard") or {}
    explanation = (scorecard.get("strengths") or [scorecard.get("explanation") or "Selected because the profile aligns with the active role."])[0]
    evidence = latest_interest_evidence(candidate.get("id"), match.get("role_id") if match else None)
    bullets = scorecard.get("strengths") or [explanation]
    bullets_html = "".join(f"<li>{escape(str(item))}</li>" for item in bullets[:3])
    st.markdown(
        f"""
        <div class='glass-card'>
          <div class='card-title'>Top Recommendation</div>
          <div class='mini-card'>
            <div style='font-size:1.08rem;font-weight:900'>{escape(candidate['name'])}</div>
            <div class='muted'>{escape(candidate.get('current_title') or 'Candidate')} at {escape(candidate.get('current_company') or 'Unknown company')}</div>
            {render_score_badge(match_score)}
            <div style='display:flex;gap:.55rem;flex-wrap:wrap'>
              {render_status_chip(f"Match {int(match_score)}%", "blue")}
              {render_status_chip(f"Interest {level}", tone)}
            </div>
            <p class='muted'><b>Interest evidence:</b> {escape(evidence['label'])}</p>
            <ul class='muted' style='padding-left:1rem;margin:.45rem 0 0'>{bullets_html}</ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_primary_action_button(label: str, key: str) -> bool:
    return st.button(label, key=key, use_container_width=True)


def init_state() -> None:
    defaults = {
        "theme": "Light",
        "page": "Home",
        "pending_page": None,
        "selected_role_id": None,
        "selected_candidate_id": "DEMO-SHRUTI-001",
        "current_jd": DEMO_JD,
        "parsed_jd_summary": None,
        "last_scan": None,
        "last_email_result": None,
        "draft_approved": False,
        "explanation_candidate_id": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def apply_pending_navigation() -> None:
    pending_page = st.session_state.get("pending_page")
    if pending_page:
        st.session_state.page = pending_page
        st.session_state.pending_page = None


def navigate(page: str) -> None:
    st.session_state.pending_page = page
    st.rerun()


def toggle_explanation(candidate_id: str) -> None:
    current = st.session_state.get("explanation_candidate_id")
    st.session_state.explanation_candidate_id = None if current == candidate_id else candidate_id


def selected_role() -> dict[str, Any] | None:
    roles = list_roles()
    if not roles:
        return None
    if not st.session_state.selected_role_id:
        st.session_state.selected_role_id = roles[0]["id"]
    return get_role(st.session_state.selected_role_id)


def selected_candidate() -> dict[str, Any] | None:
    candidate_id = st.session_state.get("selected_candidate_id")
    if candidate_id:
        candidate = get_candidate(candidate_id)
        if candidate:
            return candidate
    candidates = list_candidates()
    if candidates:
        st.session_state.selected_candidate_id = candidates[0]["id"]
        return candidates[0]
    return None


def create_demo_role() -> int:
    return create_role_from_jd(DEMO_JD)


def create_role_from_jd(jd_text: str) -> int:
    parsed = parse_jd(jd_text, LLMClient())
    title = parsed.get("role_title") or "Senior Frontend Engineer"
    required = parsed.get("required_skills") or ["React", "TypeScript", "GraphQL"]
    nice_to_have = parsed.get("nice_to_have_skills") or ["SaaS", "Accessibility"]
    experience = int(parsed.get("years_experience") or 5)
    role_id = create_role(
        {
            "title": title,
            "department": "Product Engineering",
            "hiring_manager": "Hiring Team",
            "location": parsed.get("location_preference") or "Remote",
            "work_mode": parsed.get("work_mode") or "remote",
            "salary_min": 140000,
            "salary_max": 185000,
            "required_skills": required,
            "nice_to_have_skills": nice_to_have,
            "experience_min": experience,
            "experience_max": max(experience + 4, 9),
            "jd_text": jd_text,
            "interview_process": "Recruiter screen, technical screen, final team conversation",
        },
        calibration={"must_have_skills": required, "nice_to_have_skills": nice_to_have},
    )
    st.session_state.selected_role_id = role_id
    st.session_state.current_jd = jd_text
    st.session_state.parsed_jd_summary = parsed
    return role_id


def extract_jd_from_inputs(uploaded_file: Any | None, pasted_jd: str) -> tuple[str, str | None]:
    if uploaded_file is not None:
        try:
            return extract_text(uploaded_file), None
        except Exception as exc:
            return "", f"Could not read the uploaded JD: {exc}"
    jd_text = pasted_jd.strip()
    if jd_text:
        return jd_text, None
    return st.session_state.get("current_jd", DEMO_JD), None


def save_demo_candidate(payload: dict[str, Any] | None = None) -> str:
    candidate_id = upsert_candidate(payload or DEMO_CANDIDATE, source="demo")
    st.session_state.selected_candidate_id = candidate_id
    return candidate_id


def ensure_demo_records() -> None:
    roles = list_roles()
    demo_role = next(
        (
            role
            for role in roles
            if role.get("title") == "Senior Frontend Engineer"
            and "React" in (role.get("jd_text") or "")
            and "TypeScript" in (role.get("jd_text") or "")
        ),
        None,
    )
    if demo_role is None:
        create_demo_role()
    elif not st.session_state.get("selected_role_id"):
        st.session_state.selected_role_id = demo_role["id"]
        st.session_state.current_jd = demo_role.get("jd_text") or DEMO_JD
    if not get_candidate("DEMO-SHRUTI-001"):
        save_demo_candidate()


def score_selected(role_id: int, candidate_id: str) -> dict[str, Any]:
    result = score_candidates_for_role(role_id, candidate_ids=[candidate_id])
    st.session_state.last_scan = {**result, "role_id": role_id}
    return result


def run_talent_scan(role_id: int) -> dict[str, Any]:
    progress = st.progress(0, text="Analyzing candidate pool...")

    def on_progress(value: float, scored: int, total: int) -> None:
        progress.progress(value, text=f"Analyzed {scored} of {total} candidates")

    result = score_candidates_for_role(role_id, limit=50, progress_callback=on_progress)
    progress.progress(1.0, text=f"Talent Scan complete: analyzed {result['processed_count']} candidates")
    st.session_state.last_scan = {**result, "role_id": role_id}
    top = top_match_for_role(role_id)
    if top:
        st.session_state.selected_candidate_id = top["candidate_id"]
    return result


def run_outreach_simulation(role_id: int) -> dict[str, Any]:
    result = simulate_outreach_for_role(role_id, limit=5)
    st.session_state.last_simulation = {**result, "role_id": role_id}
    top = top_match_for_role(role_id)
    if top:
        st.session_state.selected_candidate_id = top["candidate_id"]
    return result


def current_match(role: dict[str, Any] | None, candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not role or not candidate:
        return None
    return get_match(candidate["id"], role["id"])


def pipeline_state(role: dict[str, Any] | None, candidate: dict[str, Any] | None, match: dict[str, Any] | None) -> tuple[int, list[tuple[str, str, bool, bool]]]:
    top_matches = get_top_matches(role["id"], limit=10) if role else []
    last_scan = st.session_state.get("last_scan") or {}
    last_simulation = st.session_state.get("last_simulation") or {}
    simulations = 0
    if role:
        simulations = sum(1 for row in top_matches if latest_simulation_for_candidate(row["candidate_id"], role["id"]))
    analyzed_count = int(last_scan.get("processed_count") or len(top_matches) or 0)
    shortlisted_count = sum(1 for item in top_matches if float(item.get("match_score", 0)) >= 70)
    candidate_done = bool(top_matches)
    shortlist_detail = "Waiting for scan results."
    if top_matches:
        top = top_matches[0]
        shortlist_detail = f"Top candidate: {top.get('full_name', top.get('candidate_id'))} at {int(top.get('match_score', 0))}% match."
    avg_interest = last_simulation.get("average_interest_score")
    interest_detail = f"Average simulated interest: {int(avg_interest)}%." if avg_interest else "Waiting for outreach simulation."
    steps = [
        ("Parsed JD", f"Extracted {(role or {}).get('title', 'role')}, skills, and experience.", bool(role), not role),
        ("Scanned candidate pool", f"Analyzed {analyzed_count} candidates · {shortlisted_count} shortlisted.", candidate_done, bool(role and not candidate_done)),
        ("Matches scored", f"Match scores available for {len(top_matches)} candidates.", bool(top_matches), False),
        ("Outreach simulated", f"Simulated conversations for {simulations} candidates.", simulations > 0, bool(top_matches and simulations == 0)),
        ("Interest scored", interest_detail, simulations > 0, False),
        ("Ranked shortlist ready", shortlist_detail, bool(top_matches and simulations > 0), False),
    ]
    progress = int(sum(1 for _, _, done, _ in steps if done) / len(steps) * 100)
    return progress, steps


def get_email_history(candidate_id: str, role_id: int) -> list[dict[str, Any]]:
    from src.services.outreach_service import list_messages

    return [
        item
        for item in list_messages(candidate_id, role_id)
        if item["channel"] in {"email", "email_reply", "simulated_outreach", "simulated_reply"}
    ]


def render_topbar() -> None:
    left, right = st.columns([1.3, 1])
    with left:
        st.markdown(
            "<div class='ts-topbar'><div><div class='brand'><span class='brand-mark'>A⌕</span> TalentSignal AI</div><div class='muted'>Recruiter Dashboard</div></div></div>",
            unsafe_allow_html=True,
        )
    with right:
        status = email_status()
        st.markdown(
            f"<div class='ts-topbar' style='justify-content:flex-end'><span class='chip blue'>{escape(st.session_state.get('theme', 'Light'))}</span><span class='chip green'>Email {escape(status.mode.replace('_', ' '))}</span></div>",
            unsafe_allow_html=True,
        )


def render_sidebar() -> None:
    with st.sidebar:
        st.radio("Theme", ["Light", "Dark"], key="theme", horizontal=True)
        st.divider()
        page = st.radio("Pages", ["Home", "Candidates", "Outreach Demo", "Settings"], key="page")
        st.divider()
        roles = list_roles()
        if roles:
            options = {f"{role['title']} #{role['id']}": role["id"] for role in roles}
            current = next((label for label, role_id in options.items() if role_id == st.session_state.selected_role_id), next(iter(options)))
            st.session_state.selected_role_id = options[st.selectbox("Selected role", list(options), index=list(options).index(current))]
        candidates = list_candidates()
        if candidates:
            options = {f"{candidate['name']} · {candidate.get('email') or 'no email'}": candidate["id"] for candidate in candidates}
            current = next((label for label, cid in options.items() if cid == st.session_state.selected_candidate_id), next(iter(options)))
            st.session_state.selected_candidate_id = options[st.selectbox("Selected candidate", list(options), index=list(options).index(current))]


def format_timestamp(value: str | None) -> str:
    if not value:
        return "just now"
    try:
        return datetime.fromisoformat(value).strftime("%b %d, %I:%M %p")
    except ValueError:
        return value


def demo_footer(candidate_email: str | None) -> str:
    return f"This is a TalentSignal demo email. Intended candidate email: {candidate_email or 'Unavailable'}."


def render_candidate_pool(role: dict[str, Any] | None) -> None:
    with st.container(border=True):
        st.markdown("<div class='section-title'>Candidate Discovery</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-subtitle'>Who was scanned and why the shortlist is credible.</div>", unsafe_allow_html=True)
        if not role:
            st.info("Upload or paste a JD, then run Talent Scan.")
            return
        rows = evaluated_candidates(role["id"], limit=5)
        if not rows:
            st.info("Run Talent Scan to evaluate candidates for this role.")
            return
        matched_skills: dict[str, int] = {}
        for row in rows:
            for skill in (row["candidate"].get("skills") or [])[:6]:
                matched_skills[skill] = matched_skills.get(skill, 0) + 1
        st.markdown(
            f"""
            <div class='score-grid'>
              <div class='score-tile'><div class='muted'>Candidates scanned</div><b>{len(list_candidates())}</b></div>
              <div class='score-tile'><div class='muted'>Shortlisted</div><b>{sum(1 for r in rows if r['status'] == 'Shortlisted')}</b></div>
              <div class='score-tile'><div class='muted'>Top skills</div><b>{escape(', '.join(list(matched_skills)[:3]) or 'Pending')}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Filters used: compliance clear, valid email where available, role skills, experience, location/work mode.")
        for index, row in enumerate(rows, start=1):
            candidate = row["candidate"]
            match = row["match"]
            st.markdown(
                f"""
                <div style='display:flex;justify-content:space-between;gap:.75rem;align-items:center;border-top:1px solid var(--border);padding:.55rem 0'>
                  <div><b>#{index} {escape(candidate['name'])}</b><br><span class='muted'>{escape(candidate.get('current_title') or 'Candidate')} · {escape(candidate.get('current_company') or 'Unknown company')}</span></div>
                  <div style='display:flex;gap:.4rem;flex-wrap:wrap;justify-content:flex-end'>
                    {render_status_chip(f"{int(match.get('match_score', 0))}% match", "blue")}
                    {render_status_chip(row['status'], row['tone'])}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_ranked_shortlist(role: dict[str, Any] | None) -> None:
    with st.container(border=True):
        if not role:
            st.info("Parse a JD and run Talent Scan to build the shortlist.")
            return
        rows = evaluated_candidates(role["id"], limit=5)
        if not rows:
            st.info("No ranked candidates yet. Run Talent Scan first.")
            return
        for index, row in enumerate(rows, start=1):
            candidate = row["candidate"]
            match = row["match"]
            simulation = latest_simulation_for_candidate(candidate["id"], role["id"])
            recommendation = recommendation_for_scores(match, row["status"])
            short_reason = match_explanation(candidate, match)
            conversation = (simulation or {}).get("hr_summary", "Outreach simulation has not run yet.")
            st.markdown(
                f"""
                <div class='shortlist-card'>
                  <div style='display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap'>
                    <div>
                      <div class='muted'>Rank #{index}</div>
                      <div style='font-size:1rem;font-weight:900'>{escape(candidate['name'])}</div>
                      <div class='muted'>{escape(candidate.get('current_title') or 'Candidate')} · {escape(candidate.get('current_company') or 'Unknown company')}</div>
                    </div>
                    <div style='display:flex;gap:.45rem;flex-wrap:wrap'>
                      {render_status_chip(f"Match {int(match.get('match_score', 0))}%", "blue")}
                      {render_status_chip(f"Interest {int(match.get('interest_score', 0))}%", "green" if float(match.get('interest_score', 0)) >= 70 else "amber")}
                      {render_status_chip(f"Combined {int(combined_score(match))}%", "green" if combined_score(match) >= 75 else "amber")}
                    </div>
                  </div>
                  <p class='muted' style='margin:.5rem 0 .25rem'><b>Reason:</b> {escape(short_reason[:170])}</p>
                  <p class='muted' style='margin:.25rem 0'><b>Conversation:</b> {escape(conversation[:170])}</p>
                  <div><b>Recommendation:</b> {escape(recommendation)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("View Explanation", key=f"shortlist_view_{candidate['id']}_{role['id']}", use_container_width=True):
                st.session_state.selected_candidate_id = candidate["id"]
                toggle_explanation(candidate["id"])
            if st.session_state.get("explanation_candidate_id") == candidate["id"]:
                render_candidate_explanation(candidate, role, match, row["status"])


def render_conversation_timeline(candidate_id: str, role_id: int, compact: bool = False) -> None:
    with st.container(border=True):
        st.markdown("<div class='section-title'>Conversation Timeline</div>", unsafe_allow_html=True)
        history = sorted(get_email_history(candidate_id, role_id), key=lambda item: item.get("created_at") or "")
        if not history:
            st.info("Outreach simulation has not run yet. Click Simulate Outreach Conversations to estimate candidate interest.")
            return
        if compact:
            history = history[-5:]
        for item in history:
            metadata = item.get("metadata", {})
            subject = metadata.get("subject")
            analysis = metadata.get("analysis", {})
            when = format_timestamp(item.get("created_at"))
            if item["channel"] in {"email_reply", "simulated_reply"}:
                source = "Candidate → TalentSignal" if item["channel"] == "email_reply" else "Candidate → TalentSignal (simulated)"
                st.markdown(
                    f"""
                    <div class='chat-bubble candidate'>
                      <div class='muted'>{when} · {source}</div>
                      <div>{escape(item.get('message_body') or '')}</div>
                    </div>
                    <div class='chat-bubble analysis'>
                      <div class='muted'>TalentSignal Analysis</div>
                      <div><b>{escape(analysis.get('sentiment', 'neutral').title())}</b> · Interest Score {int(analysis.get('new_interest_score') or analysis.get('interest_score') or 0)}%</div>
                      <div class='muted'>{escape(analysis.get('hr_summary', 'Reply analyzed.'))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                body = item.get("message_body") or ""
                recipient = (item.get("metadata") or {}).get("actual_recipient") or get_settings().test_email_recipient or "Mock mode"
                is_simulation = item["channel"] == "simulated_outreach"
                if item.get("status") in {"test_sent", "mock_sent", "sent"}:
                    candidate = get_candidate(candidate_id)
                    footer = demo_footer(candidate.get("email") if candidate else None)
                    if footer not in body:
                        body = f"{body}\n\n{footer}"
                st.markdown(
                    f"""
                    <div class='chat-bubble'>
                      <div class='muted'>{when} · TalentSignal → Candidate{' (simulated)' if is_simulation else f' · Actual recipient: {escape(str(recipient))}'}</div>
                      <div><b>{escape(subject or 'Recruiter Outreach')}</b></div>
                      <div>{escape(body[:520])}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_home() -> None:
    role = selected_role()
    selected = selected_candidate()
    top_match = top_match_for_role(role["id"] if role else None)
    selected_match = current_match(role, selected) if role and selected else None
    match = selected_match or top_match
    active_candidate = selected if selected_match else get_candidate(top_match["candidate_id"]) if top_match else selected
    progress, steps = pipeline_state(role, active_candidate, match)
    summary = build_hr_decision_summary(active_candidate["id"], role["id"]) if role and active_candidate else {"summary": "Create/select a role and candidate to begin."}

    render_topbar()
    st.markdown("<div class='section-title'>1. JD Intake</div>", unsafe_allow_html=True)
    with st.container(border=True):
        parsed = st.session_state.get("parsed_jd_summary") or {}
        required_skills = parsed.get("required_skills") or (role or {}).get("required_skills", [])
        nice_skills = parsed.get("nice_to_have_skills") or (role or {}).get("nice_to_have_skills", [])
        experience = parsed.get("years_experience") or (role or {}).get("experience_min", 5)
        intake_left, intake_right = st.columns([1.05, .95])
        with intake_left:
            uploaded_file = st.file_uploader("Upload Job Description", type=["txt", "pdf", "docx"], key="home_jd_upload")
            pasted_jd = st.text_area("Paste JD", value=st.session_state.get("current_jd", DEMO_JD), height=170, key="home_jd_text")
            if st.button("Parse JD", key="home_use_jd", use_container_width=True, type="primary"):
                jd_text, error = extract_jd_from_inputs(uploaded_file, pasted_jd)
                if error:
                    st.error(error)
                elif not jd_text.strip():
                    st.warning("Add or upload a job description first.")
                else:
                    role_id = create_role_from_jd(jd_text)
                    st.success("JD parsed and role saved.")
                    st.session_state.selected_role_id = role_id
                    st.rerun()
        with intake_right:
            st.markdown(f"<div class='hero-role'>{escape((role or {}).get('title', 'No role selected'))}</div>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class='mini-card'>
                  <div class='muted'>Parsed role summary</div>
                  <div><b>Required:</b> {escape(', '.join(required_skills[:6]) if required_skills else 'React, TypeScript, GraphQL')}</div>
                  <div><b>Nice-to-have:</b> {escape(', '.join(nice_skills[:5]) if nice_skills else 'SaaS, Accessibility')}</div>
                  <div><b>Experience:</b> {escape(str(experience))}+ years</div>
                  <div><b>Location/work mode:</b> {escape((role or {}).get('location') or 'Flexible')} · {escape((role or {}).get('work_mode') or 'Flexible')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div class='section-title'>2. Talent Scan</div>", unsafe_allow_html=True)
    scan_left, scan_right = st.columns([.78, 1.22])
    with scan_left:
        with st.container(border=True):
            st.markdown("**Run agent workflow**")
            scan_clicked = st.button("Run Talent Scan", key="home_scan", use_container_width=True, type="primary")
            simulate_clicked = st.button("Simulate Outreach Conversations", key="home_simulate", use_container_width=True, disabled=not bool(top_match))
            if scan_clicked:
                jd_text, error = extract_jd_from_inputs(uploaded_file, pasted_jd)
                if error:
                    st.error(error)
                    return
                if not role or jd_text.strip() != (role.get("jd_text") or "").strip():
                    role_id = create_role_from_jd(jd_text or DEMO_JD)
                    role = get_role(role_id)
                if not selected:
                    save_demo_candidate()
                result = run_talent_scan(role["id"])
                st.success(f"Talent Scan complete: analyzed {result['processed_count']} candidates.")
                st.rerun()
            if simulate_clicked and role:
                result = run_outreach_simulation(role["id"])
                st.success(f"Simulated {result['engaged_count']} outreach conversations. Average interest: {int(result['average_interest_score'])}%.")
                st.rerun()
            st.progress(progress / 100, text=f"{progress}% complete")
            for label, detail, done, active in steps:
                icon = "✓" if done else "•"
                st.markdown(
                    f"<div class='pipeline-step'><div class='step-icon'>{icon}</div><div><b>{escape(label)}</b><div class='muted'>{escape(detail)}</div></div></div>",
                    unsafe_allow_html=True,
                )
    with scan_right:
        render_candidate_pool(role)

    st.markdown("<div class='section-title'>3. Ranked Shortlist</div>", unsafe_allow_html=True)
    render_ranked_shortlist(role)

    workspace_left, workspace_right = st.columns([1, 1])
    with workspace_left:
        if role and active_candidate:
            render_conversation_timeline(active_candidate["id"], role["id"], compact=False)
        else:
            st.info("Run Talent Scan and outreach simulation to see the conversation timeline.")
    with workspace_right:
        render_hr_summary_card(summary, role, active_candidate)


def render_candidate_page() -> None:
    role = selected_role()
    candidate = selected_candidate()
    render_topbar()
    left, right = st.columns([1, 1])
    with left:
        with st.container(border=True):
            st.markdown("**Candidate**")
            with st.form("candidate_form"):
                name = st.text_input("Candidate name", value=(candidate or DEMO_CANDIDATE).get("name", ""))
                email = st.text_input("Email", value=(candidate or DEMO_CANDIDATE).get("email", "shrutinair.ai31@gmail.com"))
                title = st.text_input("Title", value=(candidate or DEMO_CANDIDATE).get("current_title", "Senior Frontend Engineer"))
                company = st.text_input("Company", value=(candidate or DEMO_CANDIDATE).get("current_company", "TalentSignal Demo"))
                location = st.text_input("Location", value=(candidate or DEMO_CANDIDATE).get("location", "Remote"))
                skills_raw = st.text_area("Skills", value=", ".join((candidate or DEMO_CANDIDATE).get("skills", [])))
                submitted = st.form_submit_button("Save Candidate")
        if submitted:
            payload = {**DEMO_CANDIDATE, "id": (candidate or DEMO_CANDIDATE)["id"], "name": name, "email": email, "current_title": title, "current_company": company, "location": location, "skills": [item.strip() for item in skills_raw.split(",") if item.strip()]}
            save_demo_candidate(payload)
            st.success("Candidate saved.")
            st.rerun()
    with right:
        with st.container(border=True):
            st.markdown("**Score Candidate**")
            if not role:
                if st.button("Create Demo Role", use_container_width=True):
                    create_demo_role()
                    st.rerun()
            if candidate and role and st.button("Score Candidate", use_container_width=True):
                score_selected(role["id"], candidate["id"])
                st.success("Candidate scored.")
                st.rerun()
            match = current_match(role, candidate)
            if match:
                scorecard = match.get("scorecard", {})
                st.markdown(render_metric_card("Final Score", f"{int(match['final_score'])}%", match.get("recommendation") or "Ready for recruiter review"), unsafe_allow_html=True)
                st.write(scorecard.get("explanation", "Match explanation is available after scoring."))
                for strength in scorecard.get("strengths", [])[:5]:
                    st.markdown(f"- {strength}")
            else:
                st.info("Save a candidate and score them against the selected role.")


def render_email_page() -> None:
    role = selected_role()
    candidate = selected_candidate()
    match = current_match(role, candidate)
    render_topbar()
    st.markdown(
        """
        <div class='outreach-page-title'>
          <h1>Outreach Demo</h1>
          <p>Generate a safe test email, simulate engagement, and show HR what to do next.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not role or not candidate:
        st.info("Create or select a role and candidate first.")
        return
    readiness = contact_readiness(candidate, {"outreach_allowed": True})
    compliance = evaluate_compliance(candidate, role, check_duplicate(candidate))
    status = get_email_status(candidate["id"], role["id"])
    summary = build_hr_decision_summary(candidate["id"], role["id"])
    email_cfg = email_status()
    settings = get_settings()
    approval_key = f"draft_approved_{candidate['id']}_{role['id']}"
    simulation = latest_simulation_for_candidate(candidate["id"], role["id"])

    left, right = st.columns([.95, 1.05], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("<div class='section-title'>Email Workflow</div>", unsafe_allow_html=True)
            st.write(f"**Role:** {role['title']}")
            st.write(f"**Candidate:** {candidate['name']}")
            st.markdown(
                f"{render_status_chip('Ready for email draft' if readiness['preferred_channel'] == 'email' else 'Needs email review', 'green' if readiness['preferred_channel'] == 'email' else 'amber')} "
                f"{render_status_chip('Compliance clear' if compliance['outreach_allowed'] else 'Compliance blocked', 'green' if compliance['outreach_allowed'] else 'red')} "
                f"{render_status_chip('Test recipient configured' if email_cfg.test_recipient_configured else 'Mock fallback active', 'green' if email_cfg.test_recipient_configured else 'amber')}",
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:.45rem'></div>", unsafe_allow_html=True)
            if st.button("Generate Email Draft", use_container_width=True, key="email_generate_draft"):
                if not match:
                    score_selected(role["id"], candidate["id"])
                draft = generate_email_draft(candidate["id"], role["id"])
                st.session_state.last_generated_email = draft
                st.session_state[approval_key] = False
                st.success("Email draft saved.")
            draft = st.session_state.get("last_generated_email") or status
            subject = draft.get("subject") or draft.get("metadata", {}).get("subject") or f"{role['title']} opportunity"
            body = draft.get("body") or draft.get("message_body") or "Generate a draft to preview the outreach email."
            display_body = f"{body}\n\n{demo_footer(candidate.get('email'))}"
            st.text_input("Subject", value=subject, disabled=True)
            st.text_area("Body", value=display_body, height=220, disabled=True)
            if st.button("Approve Draft", use_container_width=True, disabled=draft.get("status") == "none", key="email_approve_draft"):
                approve_email(candidate["id"], role["id"], "Demo Recruiter")
                st.session_state[approval_key] = True
                st.success("Draft approved.")
            approved = bool(st.session_state.get(approval_key))
            if st.button("Send Test Email", use_container_width=True, disabled=not approved, key="email_send_test"):
                result = send_test_email(candidate["id"], role["id"], "Demo Recruiter")
                st.session_state.last_email_result = result
                if result["status"] in {"test_sent", "mock_sent"}:
                    if result["status"] == "mock_sent":
                        st.success(f"Mock email saved successfully. Actual recipient: {result.get('actual_recipient')}")
                    else:
                        st.success(f"Email sent successfully to TEST_EMAIL_RECIPIENT. Actual recipient: {result.get('actual_recipient')}")
                else:
                    st.error(result.get("error") or f"Send status: {result['status']}")
            result = st.session_state.get("last_email_result") or {}
            actual_recipient = result.get("actual_recipient") or settings.test_email_recipient or "No external recipient (mock mode)"
            st.markdown(
                f"""
                <div class='recipient-box'>
                  <div><b>Actual recipient:</b> {escape(str(actual_recipient))}</div>
                  <div><b>Candidate email on file:</b> {escape(candidate.get('email') or 'Missing')}</div>
                  <div class='safety-note'>Demo email never sends to candidate directly.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(email_cfg.detail)

        with st.expander("Advanced: paste a real candidate reply"):
            st.caption("Optional override for a live demo. The main workflow uses simulated outreach.")
            with st.form("reply_form"):
                reply = st.text_area("Candidate reply", height=120, placeholder="Example: Sounds good, I am available tomorrow. Please send details.")
                saved = st.form_submit_button("Analyze Reply")
            if saved:
                captured = capture_candidate_reply(candidate["id"], role["id"], reply)
                if captured["status"] == "saved":
                    st.success(captured["analysis"]["hr_summary"])
                    summary = build_hr_decision_summary(candidate["id"], role["id"])
                else:
                    st.error(captured["error"])
    with right:
        with st.container(border=True):
            st.markdown("<div class='section-title'>HR Decision Summary</div>", unsafe_allow_html=True)
            if summary.get("status") == "ready":
                combined = combined_score(match or {}) if match else 0
                st.markdown(
                    f"<div class='summary-callout'>What HR should do next: {escape(summary['recommended_next_step'])}</div>",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("Match", f"{int(summary['match_score'])}%")
                c2.metric("Interest", f"{int(summary['interest_score'])}%")
                c3.metric("Combined", f"{int(combined)}%")
                st.write(f"**Candidate:** {candidate['name']}")
                st.write(f"**Role:** {role['title']}")
                st.write(f"**Engagement status:** {summary['engagement_status']}")
                if simulation:
                    st.write(f"**What they said:** {simulation['candidate_reply']}")
                st.markdown("**Key fit reasons**")
                st.markdown(
                    "<ul class='compact-list'>"
                    + "".join(f"<li>{escape(reason)}</li>" for reason in summary["key_fit_reasons"][:3])
                    + "</ul>",
                    unsafe_allow_html=True,
                )
                st.markdown("**Concerns / objections**")
                st.markdown(
                    "<ul class='compact-list'>"
                    + "".join(f"<li>{escape(concern)}</li>" for concern in summary["candidate_concerns"][:2])
                    + "</ul>",
                    unsafe_allow_html=True,
                )
                can_schedule = summary["match_score"] >= 80 and summary["interest_score"] >= 70 and summary["recommended_next_step"] == "Schedule recruiter screen"
                if can_schedule:
                    slots = suggested_recruiter_screen_slots()
                    selected = st.selectbox("Suggested time slots", slots, key=f"slot_{candidate['id']}_{role['id']}")
                    if st.button("Create Meeting Recommendation", key=f"meeting_{candidate['id']}_{role['id']}", use_container_width=True):
                        result = create_mock_meeting_recommendation(candidate["id"], role["id"], selected)
                        st.success(f"Recruiter screen recommendation created for {result['slot_time']}.")
            else:
                st.info(summary.get("summary", "Run simulated outreach to prepare an HR decision summary."))
        render_conversation_timeline(candidate["id"], role["id"], compact=True)


def render_hr_summary_card(summary: dict[str, Any], role: dict[str, Any] | None, candidate: dict[str, Any] | None) -> None:
    with st.container(border=True):
        st.markdown("<div class='section-title'>HR Decision Summary</div>", unsafe_allow_html=True)
        if summary.get("status") == "ready":
            match = current_match(role, candidate) if role and candidate else None
            combined = combined_score(match or {}) if match else 0
            simulation = latest_simulation_for_candidate(candidate["id"], role["id"]) if role and candidate else None
            st.success(f"What HR should do next: {summary['recommended_next_step']}")
            st.write(summary.get("summary", "No summary yet."))
            c1, c2, c3 = st.columns(3)
            c1.metric("Match Score", f"{int(summary['match_score'])}%")
            c2.metric("Interest Score", f"{int(summary['interest_score'])}%")
            c3.metric("Combined Score", f"{int(combined)}%")
            if candidate and role:
                st.write(f"**Candidate:** {candidate['name']}")
                st.write(f"**Role:** {role['title']}")
            st.write(f"**Engagement Status:** {summary['engagement_status']}")
            st.write(f"**Recommended Next Step:** {summary['recommended_next_step']}")
            if simulation:
                st.write(f"**What they said:** {simulation['candidate_reply']}")
            st.write("**Key Fit Reasons**")
            for reason in summary["key_fit_reasons"]:
                st.markdown(f"- {reason}")
            st.write("**Candidate Concerns / Objections**")
            for concern in summary["candidate_concerns"]:
                st.markdown(f"- {concern}")
            if summary["recommended_next_step"] == "Schedule recruiter screen":
                st.success("Recommended: Schedule recruiter screen")
            can_schedule = summary["match_score"] >= 80 and summary["interest_score"] >= 70 and summary["recommended_next_step"] == "Schedule recruiter screen"
            if role and candidate and can_schedule:
                slots = suggested_recruiter_screen_slots()
                selected = st.selectbox("Suggested time slots", slots, key=f"slot_{candidate['id']}_{role['id']}")
                if st.button("Create Meeting Recommendation", key=f"meeting_{candidate['id']}_{role['id']}", use_container_width=True):
                    result = create_mock_meeting_recommendation(candidate["id"], role["id"], selected)
                    st.success(f"Recruiter screen recommendation created for {result['slot_time']}.")
            elif role and candidate:
                st.caption("Meeting recommendation appears once match and interest are both high.")
        else:
            st.write(summary.get("summary", "No summary yet."))


def render_settings() -> None:
    settings = get_settings()
    status = email_status()
    render_topbar()
    with st.container(border=True):
        st.markdown("**Settings**")
        st.info("Simulated outreach and email test mode are enabled for this demo build. SMS, LinkedIn, calls, Slack, Teams, and production send are disabled in the main workflow.")
        st.write(f"Email provider: **{status.provider}**")
        st.write(f"SMTP configured: **{status.configured}**")
        st.write(f"Test recipient: **{settings.test_email_recipient or 'Not configured'}**")
        st.write(f"Production outreach enabled: **{settings.production_outreach_enabled}**")
        st.caption("Email is optional demo support. The primary engagement flow runs through deterministic in-app simulation.")


def main() -> None:
    init_state()
    apply_pending_navigation()
    inject_theme_styles(st.session_state.theme)
    ensure_demo_records()
    render_sidebar()

    page = st.session_state.page
    if page == "Home":
        render_home()
    elif page == "Candidates":
        render_candidate_page()
    elif page == "Outreach Demo":
        render_email_page()
    else:
        render_settings()


if __name__ == "__main__":
    main()
