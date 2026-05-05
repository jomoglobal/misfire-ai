"""
Eval: Sensor Validity
---------------------
Verifies the agent correctly identifies out-of-range or implausible
sensor readings and includes them in its assessment.
Ported from obd2-vehicle-health-advisor/evals/sensor_validity.py
Updated to use Claude via Anthropic SDK.
"""

import json
import os
import pytest
import anthropic
from dotenv import load_dotenv

load_dotenv()

SENSOR_VALIDITY_CASES = [
    {
        "id": "ect_overcool",
        "vehicle_id": "tundra-2007",
        "snapshot": {"RPM": 800, "ECT": 110, "STFT_B1": 0.0, "LTFT_B1": 0.0},
        "expect_flag": "ECT",
        "description": "Engine coolant temp too low (thermostat stuck open)",
    },
    {
        "id": "maf_zero",
        "vehicle_id": "tundra-2007",
        "snapshot": {"RPM": 750, "ECT": 195, "MAF": 0.0, "STFT_B1": 0.0},
        "expect_flag": "MAF",
        "description": "MAF reads zero at idle — sensor failure or unplugged",
    },
    {
        "id": "ltft_extreme_lean",
        "vehicle_id": "bmw-335i-2009",
        "snapshot": {"RPM": 800, "ECT": 200, "LTFT_B1": 24.5, "STFT_B1": 9.0},
        "expect_flag": "LTFT",
        "description": "LTFT B1 near saturation — severe lean condition",
    },
    {
        "id": "rpm_unrealistic",
        "vehicle_id": "honda-fit-2015",
        "snapshot": {"RPM": 9999, "ECT": 190, "STFT_B1": 0.0, "LTFT_B1": 0.0},
        "expect_flag": "RPM",
        "description": "RPM above redline — likely sensor error",
    },
]

SYSTEM_PROMPT = (
    "You are an OBD2 diagnostic assistant. "
    "Analyze the snapshot and list any sensors with implausible or out-of-range values."
)


def call_agent(snapshot: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Snapshot:\n```json\n{json.dumps(snapshot, indent=2)}\n```",
            }
        ],
    )
    return message.content[0].text if message.content else ""


@pytest.mark.parametrize("case", SENSOR_VALIDITY_CASES, ids=[c["id"] for c in SENSOR_VALIDITY_CASES])
def test_sensor_flagged(case):
    response = call_agent(case["snapshot"])
    assert case["expect_flag"] in response, (
        f"Case '{case['id']}': expected '{case['expect_flag']}' to be flagged.\n"
        f"Agent response:\n{response}"
    )
