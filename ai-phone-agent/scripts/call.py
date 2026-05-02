#!/usr/bin/env python3
"""
AI Phone Agent — Call Script

Usage:
    # Start a real outbound call (your phone will ring)
    python scripts/call.py

    # Simulate a conversation locally (no phone call)
    python scripts/call.py --simulate

    # Call a different number
    python scripts/call.py --to +919876543210

    # Add a number to the demo whitelist for this session
    python scripts/call.py --to +919876543210 --whitelist

Environment:
    VOBIZ_AUTH_ID      (default: MA_B1SVPHLK)
    VOBIZ_AUTH_TOKEN
    VOBIZ_DID          (default: +918065481227)
    BACKEND_URL        (default: http://localhost:8000)
    NGROK_URL          (used for live mode webhooks)
    DEMO_MODE          (default: true)
    DEMO_WHITELIST_NUMBERS  (comma-separated, required in demo mode)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# Load env vars from backend/.env so credentials work out of the box
_dotenv_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
if _dotenv_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_dotenv_path)
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VOBIZ_AUTH_ID = os.getenv("VOBIZ_AUTH_ID", "MA_B1SVPHLK")
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN", "")
VOBIZ_DID = os.getenv("VOBIZ_DID", "+918065481227")
VOBIZ_BASE_URL = os.getenv("VOBIZ_BASE_URL", "https://api.vobiz.ai/api/v1")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
NGROK_URL = os.getenv("NGROK_URL", "")

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
DEMO_WHITELIST = set(
    n.strip() for n in os.getenv("DEMO_WHITELIST_NUMBERS", "").split(",") if n.strip()
)

DEFAULT_TO_NUMBER = "+918301877184"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xml_to_text(xml_string: str) -> tuple[Optional[str], Optional[str], bool]:
    """Parse Vobiz XML response.

    Returns:
        (audio_url, speak_text, hangup)
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError:
        return None, xml_string[:200], False

    audio_url = None
    speak_text = None
    hangup = False

    for child in root:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "Play":
            audio_url = child.text
        elif tag == "Speak":
            speak_text = child.text
        elif tag == "Hangup":
            hangup = True

    return audio_url, speak_text, hangup


def _get_latest_ai_text(call_sid: str) -> Optional[str]:
    """Fetch the latest assistant turn from the backend session."""
    try:
        r = httpx.get(f"{BACKEND_URL}/api/calls/{call_sid}", timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        turns = data.get("turns", [])
        for turn in reversed(turns):
            if turn.get("role") == "assistant":
                return turn.get("content")
        return None
    except Exception:
        return None


def _play_audio(url: str) -> None:
    """Try to play audio URL using system player."""
    import platform
    import subprocess

    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            tmp_path = "/tmp/phone_agent_last_response.wav"
            httpx.get(url).raise_for_status()
            with open(tmp_path, "wb") as f:
                f.write(httpx.get(url).content)
            subprocess.Popen(["afplay", tmp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("  🔊  Playing audio...")
        elif system == "Linux":
            subprocess.Popen(["mpg123", "-q", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("  🔊  Playing audio...")
        else:
            print(f"  🔊  Audio: {url}")
    except Exception as exc:
        print(f"  🔊  Audio: {url} (could not play: {exc})")


def _check_backend() -> dict:
    """Ping the backend health endpoint and return status info."""
    try:
        r = httpx.get(f"{BACKEND_URL}/health", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _show_demo_banner() -> None:
    """Print demo-mode banner if active."""
    if DEMO_MODE:
        print(
            """
╔══════════════════════════════════════════════════════════════╗
║  [DEMO MODE]  Test calls only — whitelisted numbers only     ║
║  Whitelist: {count} number(s)                                  ║
╚══════════════════════════════════════════════════════════════╝
""".format(count=len(DEMO_WHITELIST))
        )


def _is_whitelisted(phone: str) -> bool:
    """Check if a number is in the demo whitelist."""
    if not DEMO_MODE:
        return True
    clean = phone.strip().replace(" ", "").replace("-", "")
    return clean in DEMO_WHITELIST


# ---------------------------------------------------------------------------
# Live Mode — Real outbound call via Vobiz
# ---------------------------------------------------------------------------

def _get_ngrok_url() -> Optional[str]:
    """Auto-detect public ngrok URL from the local ngrok API."""
    try:
        r = httpx.get("http://localhost:4040/api/tunnels", timeout=5)
        r.raise_for_status()
        tunnels = r.json().get("tunnels", [])
        for tunnel in tunnels:
            url = tunnel.get("public_url", "")
            if url.startswith("https://"):
                return url
    except Exception:
        pass
    return None


def start_live_call(to_number: str, auto_whitelist: bool = False) -> Optional[str]:
    """Initiate an outbound call via Vobiz. Returns call_sid or None."""
    _show_demo_banner()

    # Demo-mode whitelist check
    if DEMO_MODE and not _is_whitelisted(to_number):
        if auto_whitelist:
            DEMO_WHITELIST.add(to_number.strip().replace(" ", "").replace("-", ""))
            print(f"✅  Added {to_number} to demo whitelist for this session.")
        else:
            print(f"❌  DEMO_MODE: {to_number} is NOT in the whitelist.")
            print(f"   Whitelisted: {', '.join(DEMO_WHITELIST) or '(none)'}")
            print("   Run with --whitelist to auto-add, or set DEMO_WHITELIST_NUMBERS in .env")
            return None

    if not VOBIZ_AUTH_TOKEN:
        print("❌  VOBIZ_AUTH_TOKEN not set. Export it and try again.")
        return None

    public_url = NGROK_URL or _get_ngrok_url()
    if not public_url:
        print("❌  No public URL found for webhooks.")
        print("   Start ngrok:  ngrok http 8000")
        print("   Or set NGROK_URL env var.")
        return None

    answer_url = f"{public_url}/webhook/vobiz/answer"
    hangup_url = f"{public_url}/webhook/vobiz/hangup"
    recording_url = f"{public_url}/webhook/vobiz/recording"

    payload = {
        "from": VOBIZ_DID,
        "to": to_number,
        "answer_url": answer_url,
        "hangup_url": hangup_url,
        "recording_url": recording_url,
        "answer_method": "POST",
        "hangup_method": "POST",
    }

    url = f"{VOBIZ_BASE_URL}/Account/{VOBIZ_AUTH_ID}/Call/"

    print(f"📞  Calling {to_number} from {VOBIZ_DID}...")
    print(f"   Answer URL: {answer_url}")
    print(f"   Hangup URL: {hangup_url}")

    try:
        r = httpx.post(
            url,
            json=payload,
            auth=(VOBIZ_AUTH_ID, VOBIZ_AUTH_TOKEN),
            timeout=30,
        )
        print(f"   Vobiz response: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
        data = r.json()
        call_sid = data.get("call_sid") or data.get("CallSid") or data.get("request_uuid")
        print(f"✅  Call queued. SID: {call_sid or 'N/A'}")
        return call_sid
    except httpx.HTTPStatusError as exc:
        print(f"❌  Vobiz API error: {exc.response.status_code} {exc.response.text}")
        return None
    except Exception as exc:
        print(f"❌  Failed to start call: {exc}")
        return None


def monitor_live_call(call_sid: Optional[str]) -> None:
    """Poll backend for call status until it ends."""
    if not call_sid:
        call_sid = input("Enter call SID to monitor (or press Enter to skip): ").strip() or None
        if not call_sid:
            return

    print(f"\n👀  Monitoring call {call_sid}...")
    print("   Press Ctrl+C to stop monitoring.\n")

    last_turn_count = 0
    try:
        while True:
            time.sleep(3)
            try:
                r = httpx.get(f"{BACKEND_URL}/api/calls/{call_sid}", timeout=10)
                if r.status_code == 404:
                    print("📴  Call session not found yet (call may still be connecting)...")
                    continue
                r.raise_for_status()
                data = r.json()

                turns = data.get("turns", [])
                state = data.get("state", "unknown")
                ended = data.get("ended_at")

                # Print new turns
                if len(turns) > last_turn_count:
                    for turn in turns[last_turn_count:]:
                        role = turn.get("role", "?")
                        content = turn.get("content", "")
                        prefix = "🤖 AI" if role == "assistant" else "👤 You"
                        print(f"   {prefix}: {content}")
                    last_turn_count = len(turns)

                if ended:
                    duration = data.get("metadata", {}).get("duration_seconds", "?")
                    print(f"\n📴  Call ended. State: {state} | Duration: {duration}s")
                    break

            except Exception as exc:
                print(f"   ⚠️  Poll error: {exc}")

    except KeyboardInterrupt:
        print("\n🛑  Stopped monitoring.")
        try:
            httpx.post(
                f"{BACKEND_URL}/webhook/vobiz/hangup",
                json={"call_sid": call_sid, "duration_seconds": 0},
                timeout=10,
            )
            print("   Cleaned up session.")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Simulate Mode — Local text conversation with the backend
# ---------------------------------------------------------------------------

def run_simulation() -> None:
    """Run a fully local conversation loop against the backend webhooks."""
    call_sid = f"sim-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    _show_demo_banner()

    # Check backend health
    health = _check_backend()
    if health:
        print(f"   Backend: {health.get('status', 'unknown')} | Mode: {health.get('mode', 'unknown')}")
    else:
        print("   ⚠️  Backend not reachable. Start it with: cd backend && python run.py")

    print("=" * 60)
    print("🧪  SIMULATION MODE — No real phone call")
    print(f"   Call SID: {call_sid}")
    print(f"   Backend:  {BACKEND_URL}")
    print("=" * 60)

    # 1. Trigger answer webhook (get greeting)
    print("\n📞  Triggering answer webhook...")
    try:
        r = httpx.post(
            f"{BACKEND_URL}/webhook/vobiz/answer",
            json={"call_sid": call_sid, "from": "+919999999999"},
            timeout=60,
        )
        r.raise_for_status()
        audio_url, speak_text, _ = _xml_to_text(r.text)

        if audio_url:
            print(f"\n🤖  [AI greeting — audio generated]")
            ai_text = _get_latest_ai_text(call_sid)
            if ai_text:
                print(f"    {ai_text}")
            _play_audio(audio_url)
        elif speak_text:
            print(f"\n🤖  {speak_text}")
        else:
            print(f"\n⚠️  Unexpected response:\n{r.text}")
    except Exception as exc:
        print(f"❌  Answer webhook failed: {exc}")
        return

    # 2. Conversation loop
    print("\n💬  Type your message and press Enter. Type 'quit' or 'bye' to end.\n")

    while True:
        try:
            user_input = input("👤  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye", "hangup"):
            break

        # Send recording webhook
        try:
            r = httpx.post(
                f"{BACKEND_URL}/webhook/vobiz/recording",
                json={"call_sid": call_sid, "user_text": user_input},
                timeout=60,
            )
            r.raise_for_status()
            audio_url, speak_text, hangup = _xml_to_text(r.text)

            if audio_url:
                ai_text = _get_latest_ai_text(call_sid)
                if ai_text:
                    print(f"🤖  {ai_text}")
                else:
                    print("🤖  [AI responded — see audio below]")
                _play_audio(audio_url)
            elif speak_text:
                print(f"🤖  {speak_text}")
            else:
                print(f"⚠️  Unexpected response:\n{r.text}")

            if hangup:
                print("\n📴  AI hung up.")
                break

        except Exception as exc:
            print(f"❌  Recording webhook failed: {exc}")

    # 3. Hangup
    print("\n📞  Sending hangup webhook...")
    try:
        httpx.post(
            f"{BACKEND_URL}/webhook/vobiz/hangup",
            json={"call_sid": call_sid, "duration_seconds": 0},
            timeout=10,
        )
    except Exception:
        pass

    # 4. Summary
    print("\n" + "=" * 60)
    print("📊  CALL SUMMARY")
    print("=" * 60)
    try:
        r = httpx.get(f"{BACKEND_URL}/api/calls/{call_sid}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            turns = data.get("turns", [])
            for turn in turns:
                role = turn.get("role", "?")
                content = turn.get("content", "")
                prefix = "🤖" if role == "assistant" else "👤"
                print(f"   {prefix}  {content}")
            print(f"\n   State: {data.get('state', '?')}")
            print(f"   LLM:   {data.get('llm_model', '?')}")
            print(f"   Calls: {data.get('total_llm_calls', 0)}")
            print(f"   Tokens:{data.get('total_tokens_used', 0)}")
        else:
            print("   Session already cleaned up.")
    except Exception as exc:
        print(f"   Could not fetch summary: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Phone Agent — Call Script")
    parser.add_argument(
        "--simulate", "-s",
        action="store_true",
        help="Run in simulation mode (no real phone call)",
    )
    parser.add_argument(
        "--to", "-t",
        default=DEFAULT_TO_NUMBER,
        help=f"Phone number to call (default: {DEFAULT_TO_NUMBER})",
    )
    parser.add_argument(
        "--monitor", "-m",
        action="store_true",
        help="Monitor the call after initiating (live mode only)",
    )
    parser.add_argument(
        "--whitelist", "-w",
        action="store_true",
        help="Auto-add --to number to demo whitelist for this session",
    )
    args = parser.parse_args()

    if args.simulate:
        run_simulation()
    else:
        call_sid = start_live_call(args.to, auto_whitelist=args.whitelist)
        if call_sid and args.monitor:
            monitor_live_call(call_sid)
        elif call_sid:
            print("\n📱  Your phone should ring shortly. Pick up and talk to the AI!")
            print("   Run with --monitor to see live transcript in this terminal.")


if __name__ == "__main__":
    main()
