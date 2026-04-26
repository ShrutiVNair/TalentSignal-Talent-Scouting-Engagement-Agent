from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


PERSONA_BEHAVIOR = {
    "actively_looking": {
        "reply_1": "Thanks for reaching out. This sounds aligned with what I'm exploring right now, especially if the role has strong backend ownership.",
        "follow_up": "What does the interview process and near-term roadmap look like?",
        "enthusiasm": 0.95,
        "openness": 0.95,
    },
    "passive_but_open": {
        "reply_1": "I'm not actively interviewing, but the scope sounds interesting enough to learn more.",
        "follow_up": "Could you share why this team is hiring now and how much influence the role has?",
        "enthusiasm": 0.72,
        "openness": 0.74,
    },
    "compensation_driven": {
        "reply_1": "Potentially interested. Before I spend much time, I'd want to understand compensation range and leveling.",
        "follow_up": "If the band is competitive and remote flexibility is strong, I'd be open to a next step.",
        "enthusiasm": 0.68,
        "openness": 0.7,
    },
    "mission_driven": {
        "reply_1": "The role sounds interesting if the product mission and engineering culture are meaningful.",
        "follow_up": "I'd want to hear how this team measures customer impact and technical quality.",
        "enthusiasm": 0.78,
        "openness": 0.76,
    },
    "remote_only": {
        "reply_1": "I'm open as long as the role is fully remote and the team is set up to work that way long term.",
        "follow_up": "If there's any expectation to relocate or go hybrid later, it probably won't be a fit.",
        "enthusiasm": 0.75,
        "openness": 0.8,
    },
    "not_interested": {
        "reply_1": "I appreciate the note, but I'm not looking to make a move right now.",
        "follow_up": "Please feel free to stay in touch for something materially different down the road.",
        "enthusiasm": 0.18,
        "openness": 0.15,
    },
    "skeptical": {
        "reply_1": "Maybe, though I'd need a clearer picture of team stability, expectations, and technical depth.",
        "follow_up": "I've been contacted about vague roles before, so specifics would help.",
        "enthusiasm": 0.46,
        "openness": 0.45,
    },
    "fast_responder": {
        "reply_1": "This caught my eye. Happy to chat if the role is moving quickly.",
        "follow_up": "I could likely make time this week if we're aligned on scope and level.",
        "enthusiasm": 0.88,
        "openness": 0.87,
    },
    "slow_responder": {
        "reply_1": "Thanks for the outreach. I'm open to hearing more, though my schedule is a bit packed at the moment.",
        "follow_up": "Please send details in writing and I can get back once I have a clearer window.",
        "enthusiasm": 0.58,
        "openness": 0.62,
    },
}


def simulate_conversation(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    outreach_packet: dict[str, Any],
) -> dict[str, Any]:
    persona = candidate.get("engagement_persona", "passive_but_open")
    behavior = PERSONA_BEHAVIOR.get(persona, PERSONA_BEHAVIOR["passive_but_open"])
    sent_at = datetime.now(UTC).replace(microsecond=0)
    reply_at = sent_at + timedelta(hours=4 if persona in {"fast_responder", "actively_looking"} else 30 if persona == "slow_responder" else 12)
    follow_up_at = reply_at + timedelta(hours=2)
    second_reply_at = follow_up_at + timedelta(hours=8)

    follow_up_question = (
        f"Thanks, {candidate['name'].split()[0]}. "
        f"Would a role centered on {jd['role_title']} work, remote setup, and backend architecture ownership be worth a 20-minute call?"
    )

    second_reply = behavior["follow_up"]
    evidence = [
        f"Delivery state: {outreach_packet['delivery_status']}.",
        f"Persona: {persona}",
        f"Initial reply tone suggests openness score around {int(behavior['openness'] * 100)}.",
        f"Follow-up response suggests enthusiasm score around {int(behavior['enthusiasm'] * 100)}.",
        f"Simulated response timeline: first reply at {reply_at.isoformat()}, second reply at {second_reply_at.isoformat()}.",
    ]
    communication_log = outreach_packet["communication_log"] + [
        {
            "step": "candidate_reply_simulated",
            "timestamp": reply_at.isoformat(),
            "channel": "simulated_in_app_email",
            "status": "simulated_reply",
            "detail": behavior["reply_1"],
        },
        {
            "step": "follow_up_simulated",
            "timestamp": follow_up_at.isoformat(),
            "channel": "simulated_in_app_email",
            "status": "simulated_follow_up",
            "detail": follow_up_question,
        },
        {
            "step": "candidate_second_reply_simulated",
            "timestamp": second_reply_at.isoformat(),
            "channel": "simulated_in_app_email",
            "status": "simulated_reply",
            "detail": behavior["follow_up"],
        },
    ]

    summary = (
        f"{candidate['name']} responded with a {persona.replace('_', ' ')} posture. "
        f"They signaled {'clear interest' if behavior['openness'] >= 0.75 else 'guarded interest' if behavior['openness'] >= 0.45 else 'low current interest'} "
        f"and highlighted {infer_priority(persona)} as the main decision factor."
    )

    return {
        "persona": persona,
        "initial_outreach": outreach_packet["message"],
        "candidate_reply": behavior["reply_1"],
        "follow_up_question": follow_up_question,
        "second_reply": second_reply,
        "conversation_evidence": evidence,
        "conversation_summary": summary,
        "communication_log": communication_log,
    }


def infer_priority(persona: str) -> str:
    priorities = {
        "actively_looking": "timing and scope",
        "passive_but_open": "career upside",
        "compensation_driven": "compensation and level",
        "mission_driven": "mission and product impact",
        "remote_only": "remote flexibility",
        "not_interested": "current stability",
        "skeptical": "clarity and trust",
        "fast_responder": "speed and momentum",
        "slow_responder": "asynchronous detail",
    }
    return priorities.get(persona, "fit and role clarity")
