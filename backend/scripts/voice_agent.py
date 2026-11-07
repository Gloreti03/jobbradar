"""Configures the ElevenLabs voice-interview agent from our code (owner: Matilde).

Sets name, system prompt, first message, language, test values of the variables and authentication
(signed URLs only) on the agent ELEVENLABS_AGENT_ID, keeping the voice chosen on elevenlabs.io.
The texts live in prompts.py (INTERVIEW_VOICE_*): change them there and run this again.

Usage (from backend/, with ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID in .env):
    uv run python scripts/voice_agent.py          # update the agent
    uv run python scripts/voice_agent.py --show   # only print the current settings
The API key needs the ElevenAgents (Conversational AI) permission with write access.
"""

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ELEVENLABS_AGENT_ID, ELEVENLABS_API_KEY  # noqa: E402
from prompts import (  # noqa: E402
    INTERVIEW_VOICE_FIRST_MESSAGE,
    INTERVIEW_VOICE_PLACEHOLDERS,
    INTERVIEW_VOICE_SYSTEM,
)

API = "https://api.elevenlabs.io/v1/convai/agents"
AGENT_NAME = "JobbRadar Interviewer"
TURN_TIMEOUT_S = 30  # silence before the agent speaks again (default 7 s)
MAX_CALL_S = 900  # 6 answers with thinking time


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the ElevenLabs interview agent.")
    parser.add_argument("--show", action="store_true", help="Only print the current agent settings")
    args = parser.parse_args()

    if not ELEVENLABS_API_KEY or not ELEVENLABS_AGENT_ID:
        sys.exit("Put ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID in backend/.env first.")
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    url = f"{API}/{ELEVENLABS_AGENT_ID}"

    if not args.show:
        body = {
            "name": AGENT_NAME,
            "conversation_config": {
                "agent": {
                    "first_message": INTERVIEW_VOICE_FIRST_MESSAGE,
                    "language": "en",
                    "prompt": {"prompt": INTERVIEW_VOICE_SYSTEM},
                    "dynamic_variables": {"dynamic_variable_placeholders": INTERVIEW_VOICE_PLACEHOLDERS},
                },
                # push-to-talk in the frontend: the mic stays muted until the candidate presses
                # "Start answer", so the agent must wait in silence instead of re-prompting after 7 s,
                # and must not cut the candidate off during short pauses
                "turn": {"turn_timeout": TURN_TIMEOUT_S, "turn_eagerness": "patient"},
                "conversation": {"max_duration_seconds": MAX_CALL_S},
            },
            "platform_settings": {"auth": {"enable_auth": True}},
        }
        resp = httpx.patch(url, headers=headers, json=body, timeout=30)
        if resp.status_code != 200:
            sys.exit(f"ElevenLabs error {resp.status_code}: {resp.text[:500]}")
        print("Agent updated.")

    resp = httpx.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        sys.exit(f"ElevenLabs error {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    agent = data.get("conversation_config", {}).get("agent", {})
    print("Name:          ", data.get("name"))
    print("Language:      ", agent.get("language"))
    print("First message: ", agent.get("first_message"))
    print("Variables:     ", list((agent.get("dynamic_variables") or {}).get("dynamic_variable_placeholders", {})))
    print("Auth enabled:  ", data.get("platform_settings", {}).get("auth", {}).get("enable_auth"))
    turn = data.get("conversation_config", {}).get("turn", {})
    print("Turn:          ", f"timeout {turn.get('turn_timeout')} s, eagerness {turn.get('turn_eagerness')}")
    print("Max duration:  ", data.get("conversation_config", {}).get("conversation", {}).get("max_duration_seconds"), "s")
    print("Prompt start:  ", (agent.get("prompt") or {}).get("prompt", "")[:80].replace("\n", " "), "...")


if __name__ == "__main__":
    main()
