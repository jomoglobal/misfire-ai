"""
Eval: Urgency Calibration
--------------------------
Verifies the agent assigns urgency levels matching clinical expectations.
Ported from obd2-vehicle-health-advisor/evals/urgency_calibration.py
Updated to use Claude via Anthropic SDK.
"""

import json
import os
import re
import pytest
import anthropic
from dotenv import load_dotenv

load_dotenv()

URGENCY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"]

URGENCY_CASES = [
    {
        "id": "healthy_idle",
        "vehicle_id": "tundra-2007",
        "snapshot": {
            "RPM": 750, "ECT": 195,
            "STFT_B1": 0.8, "LTFT_B1": 1.2,
            "STFT_B2": -0.4, "LTFT_B2": 0.9,
        },
        "expected_tier": ["NORMAL", "LOW"],
        "description": "All values within healthy range",
    },
    {
        "id": "mild_lean_drift",
        "vehicle_id": "tundra-2007",
        "snapshot": {
            "RPM": 780, "ECT": 192,
            "STFT_B1": 3.0, "LTFT_B1": 7.5,
            "STFT_B2": 2.1, "LTFT_B2": 6.8,
        },
        "expected_tier": ["MEDIUM", "HIGH"],
        "description": "Both banks drifting lean — moderate concern",
    },
    {
        "id": "severe_overheating",
        "vehicle_id": "bmw-335i-2009",
        "snapshot": {
            "RPM": 900, "ECT": 265,
            "STFT_B1": 0.0, "LTFT_B1": 0.0,
        },
        "expected_tier": ["CRITICAL", "HIGH"],
        "description": "ECT at 265°F — near boiling",
    },
    {
        "id": "ltft_saturation",
        "vehicle_id": "honda-fit-2015",
        "snapshot": {
            "RPM": 820, "ECT": 197,
            "STFT_B1": 10.9, "LTFT_B1": 22.7,
        },
        "expected_tier": ["CRITICAL", "HIGH"],
        "description": "LTFT near max — ECU at limit of fuel correction",
    },
]

SYSTEM_PROMPT = (
    "You are an OBD2 diagnostic assistant. "
    "Analyze the snapshot and output an urgency level as one of: "
    "CRITICAL, HIGH, MEDIUM, LOW, or NORMAL. "
    "Start your response with the urgency level on its own line."
)


def extract_urgency(text: str) -> str | None:
    for level in URGENCY_LEVELS:
        if re.search(rf"\b{level}\b", text, re.IGNORECASE):
            return level.upper()
    return None


def call_agent(snapshot: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Snapshot:\n```json\n{json.dumps(snapshot, indent=2)}\n```",
            }
        ],
    )
    return message.content[0].text if message.content else ""


@pytest.mark.parametrize("case", URGENCY_CASES, ids=[c["id"] for c in URGENCY_CASES])
def test_urgency_tier(case):
    response = call_agent(case["snapshot"])
    urgency = extract_urgency(response)
    assert urgency is not None, (
        f"Case '{case['id']}': could not extract urgency.\nResponse:\n{response}"
    )
    assert urgency in case["expected_tier"], (
        f"Case '{case['id']}': got '{urgency}', expected one of {case['expected_tier']}.\n"
        f"Response:\n{response}"
    )
