"""
Diagnostic agent — core reasoning layer.
Uses GPT-4o with Phoenix/OTel tracing.
"""

import json
import os
from dataclasses import dataclass, field

from openai import OpenAI
from opentelemetry import trace

from pipeline.vehicles import VehicleConfig, get_vehicle_by_id, build_vehicle_from_meta
from pipeline.preprocessor import preprocess_snapshot

tracer = trace.get_tracer("misfire-ai")


@dataclass
class AgentInput:
    vehicle_id: str
    snapshot: dict
    scenario: str = ""
    vehicle_override: VehicleConfig | None = None


@dataclass
class AgentOutput:
    assessment: str
    warnings: list[str]
    vehicle_id: str
    scenario: str
    urgency: str = "UNKNOWN"


def _build_system_prompt(vehicle: VehicleConfig) -> str:
    bank_info = (
        "dual-bank (B1 and B2 fuel trims available)"
        if vehicle.bank_count == 2
        else "single-bank (B1 fuel trims only)"
    )
    turbo_info = (
        "turbocharged — boost pressure and charge pipe integrity are relevant"
        if vehicle.turbocharged
        else "naturally aspirated"
    )
    fuel_info = (
        "flex-fuel — ethanol content varies per fill-up; fuel trims, AFR targets, and timing "
        "all shift with ethanol %; always consider ethanol content when interpreting trim data"
        if vehicle.fuel_type == "flex-fuel"
        else "gasoline"
    )

    quirks_block = ""
    if vehicle.known_quirks:
        quirks_block = "\n\nKnown quirks and caveats for this vehicle:\n" + "\n".join(
            f"- {q}" for q in vehicle.known_quirks
        )

    inaccessible_block = ""
    if vehicle.inaccessible_pids:
        inaccessible_block = (
            "\n\nPIDs known to be inaccessible via generic OBD2 on this vehicle "
            "(absence is expected, not a fault):\n"
            + "\n".join(f"- {p}" for p in vehicle.inaccessible_pids)
        )

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt_v2.txt")
    try:
        with open(prompt_path) as f:
            base_prompt = f.read().strip()
    except FileNotFoundError:
        base_prompt = "You are an expert OBD2 vehicle health advisor with deep knowledge of automotive diagnostics."

    vehicle_context = f"""
Vehicle under analysis:
- {vehicle.year} {vehicle.make} {vehicle.model}
- Engine: {vehicle.engine}
- Drivetrain: {turbo_info}
- Bank configuration: {bank_info}
- Fuel metering: {vehicle.fuel_system}-based
- Fuel type: {fuel_info}
- EGR system present: {vehicle.has_egr}{quirks_block}{inaccessible_block}
"""

    return base_prompt + "\n\n" + vehicle_context


def run_diagnostic_agent(input: AgentInput) -> AgentOutput:
    vehicle = input.vehicle_override or get_vehicle_by_id(input.vehicle_id)
    if not vehicle:
        raise ValueError(f"Unknown vehicle_id: '{input.vehicle_id}'")

    preprocessed = preprocess_snapshot(input.snapshot)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    with tracer.start_as_current_span("misfire.diagnostic") as span:
        span.set_attribute("vehicle.id", input.vehicle_id)
        span.set_attribute("vehicle.make", vehicle.make)
        span.set_attribute("vehicle.model", vehicle.model)
        span.set_attribute("vehicle.year", vehicle.year)
        span.set_attribute("scenario", input.scenario)

        system_prompt = _build_system_prompt(vehicle)

        warnings_block = ""
        if preprocessed.warnings:
            warnings_block = "\n\nPreprocessor warnings:\n" + "\n".join(
                f"- {w}" for w in preprocessed.warnings
            )

        user_message = (
            f"OBD2 Snapshot:\n```json\n"
            f"{json.dumps(preprocessed.normalized, indent=2)}\n```"
            f"{warnings_block}"
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        )

        assessment = response.choices[0].message.content or "(no response)"

        urgency = "UNKNOWN"
        for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"]:
            if tier in assessment.upper():
                urgency = tier
                break

        span.set_attribute("urgency", urgency)
        span.set_attribute("preprocessor.warning_count", len(preprocessed.warnings))

        return AgentOutput(
            assessment=assessment,
            warnings=preprocessed.warnings,
            vehicle_id=input.vehicle_id,
            scenario=input.scenario,
            urgency=urgency,
        )
