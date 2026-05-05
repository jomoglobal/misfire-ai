"""
Eval: Diagnosis Accuracy
------------------------
Verifies the agent surfaces the correct probable root cause for
known diagnostic patterns.
Ported from obd2-vehicle-health-advisor/evals/diagnosis_accuracy.py
Updated to use Claude via Anthropic SDK.
"""

import json
import os
import pytest
import anthropic
from dotenv import load_dotenv

load_dotenv()

DIAGNOSIS_CASES = [
    {
        "id": "vacuum_leak_tundra",
        "vehicle_id": "tundra-2007",
        "snapshot": {
            "RPM": 900, "ECT": 196,
            "STFT_B1": 9.4, "LTFT_B1": 12.3,
            "STFT_B2": 8.7, "LTFT_B2": 11.8,
            "MAF": 3.1,
        },
        "expected_keywords": ["vacuum", "leak", "intake"],
        "description": "Both banks lean with low MAF — classic vacuum leak pattern",
    },
    {
        "id": "o2_sensor_heater_honda",
        "vehicle_id": "honda-fit-2015",
        "snapshot": {
            "RPM": 780, "ECT": 190,
            "STFT_B1": 14.0, "LTFT_B1": 18.5,
            "O2_B1S1": 0.1,
        },
        "expected_keywords": ["oxygen", "O2", "sensor", "fuel trim"],
        "description": "Fixed lean O2 voltage + maxed fuel trim — lazy/failed upstream O2",
    },
    {
        "id": "hpfp_bmw",
        "vehicle_id": "bmw-335i-2009",
        "snapshot": {
            "RPM": 1200, "ECT": 200,
            "STFT_B1": 12.0, "LTFT_B1": 18.0,
            "STFT_B2": 11.5, "LTFT_B2": 17.3,
        },
        "expected_keywords": ["fuel pump", "HPFP", "pressure", "fuel"],
        "description": "N54 with dual-bank lean at light load — HPFP common failure mode",
    },
    {
        "id": "bank2_injector_tundra",
        "vehicle_id": "tundra-2007",
        "snapshot": {
            "RPM": 800, "ECT": 194,
            "STFT_B1": 0.5, "LTFT_B1": 1.2,
            "STFT_B2": 8.9, "LTFT_B2": 14.1,
        },
        "expected_keywords": ["injector", "Bank 2", "B2", "fuel injector", "misfire"],
        "description": "Bank 2 lean imbalance — possible injector fault",
    },
]

SYSTEM_PROMPT = (
    "You are an expert OBD2 vehicle health advisor. "
    "Analyze the snapshot and identify the most likely root cause(s) of any abnormal readings. "
    "Be specific about probable components or systems responsible."
)


def call_agent(vehicle_id: str, snapshot: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Vehicle: {vehicle_id}\n"
                    f"Snapshot:\n```json\n{json.dumps(snapshot, indent=2)}\n```"
                ),
            }
        ],
    )
    return message.content[0].text if message.content else ""


@pytest.mark.parametrize("case", DIAGNOSIS_CASES, ids=[c["id"] for c in DIAGNOSIS_CASES])
def test_diagnosis_mentions_root_cause(case):
    response = call_agent(case["vehicle_id"], case["snapshot"])
    response_lower = response.lower()
    matched = [kw for kw in case["expected_keywords"] if kw.lower() in response_lower]
    assert matched, (
        f"Case '{case['id']}': none of {case['expected_keywords']} found.\n"
        f"Response:\n{response}"
    )
