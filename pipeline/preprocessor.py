"""
Preprocessor — validates and normalizes raw OBD2 snapshot data
before passing to the agent.
Ported from obd2-vehicle-health-advisor/lib/preprocessor.ts.
"""

from dataclasses import dataclass, field

SENSOR_RANGES: dict[str, tuple[float, float]] = {
    "RPM":      (0, 8000),
    "ECT":      (-40, 300),
    "IAT":      (-40, 250),
    "MAP":      (0, 255),
    "MAF":      (0, 655),
    "THROTTLE": (0, 100),
    "LOAD":     (0, 100),
    "STFT_B1":  (-25, 25),
    "LTFT_B1":  (-25, 25),
    "STFT_B2":  (-25, 25),
    "LTFT_B2":  (-25, 25),
    "O2_B1S1":  (0, 1.275),
    "O2_B1S2":  (0, 1.275),
    "O2_B2S1":  (0, 1.275),
    "O2_B2S2":  (0, 1.275),
    "VSS":      (0, 200),
    "BOOST":    (-5, 40),
}

# Known ELM327 rollover artifacts
ROLLOVER_SENTINELS: dict[str, list[float]] = {
    "ECT": [255.0],
    "MAP": [255.0],
    "STFT_B1": [-96.0, -100.0],
    "STFT_B2": [-96.0, -100.0],
}


@dataclass
class PreprocessorResult:
    normalized: dict
    warnings: list[str] = field(default_factory=list)


def preprocess_snapshot(raw: dict) -> PreprocessorResult:
    normalized = {}
    warnings = []

    for key, value in raw.items():
        if key == "DTCs":
            if isinstance(value, list):
                normalized["DTCs"] = [str(v) for v in value]
            else:
                warnings.append(f"DTCs field is not a list — skipped")
            continue

        # Handle stat dicts from synthetic dataset {last, min, max, mean, std}
        if isinstance(value, dict):
            normalized[key] = value
            # Check for rollover artifacts in stat dicts
            last_val = value.get("last")
            std_val = value.get("std", 1)
            if last_val is not None and std_val == 0:
                sentinels = ROLLOVER_SENTINELS.get(key, [])
                if last_val in sentinels or last_val in [0, 255, 65535]:
                    warnings.append(
                        f"Sensor '{key}' has std=0 and value {last_val} — "
                        f"likely ELM327 rollover artifact, not a real reading"
                    )
            continue

        try:
            num_val = float(value)
        except (TypeError, ValueError):
            warnings.append(f"Sensor '{key}' has non-numeric value '{value}' — skipped")
            continue

        # Check rollover sentinels
        sentinels = ROLLOVER_SENTINELS.get(key, [])
        if num_val in sentinels:
            warnings.append(
                f"Sensor '{key}' value {num_val} matches known ELM327 rollover artifact — "
                f"flagged as unreliable"
            )

        # Range check
        if key in SENSOR_RANGES:
            lo, hi = SENSOR_RANGES[key]
            if not (lo <= num_val <= hi):
                warnings.append(
                    f"Sensor '{key}' value {num_val} is outside expected range "
                    f"[{lo}, {hi}] — included but flagged"
                )

        normalized[key] = num_val

    return PreprocessorResult(normalized=normalized, warnings=warnings)
