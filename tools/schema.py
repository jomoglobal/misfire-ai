"""
MisfireAI canonical signal schema.

Defines signal families, canonical names, units, source availability,
column mappings for all 5 data sources, unit conversion functions,
and reference dictionaries for data quality and health scoring.
"""

from __future__ import annotations
import re
from typing import Callable

# ---------------------------------------------------------------------------
# Signal family definitions
# Each entry: (family, unit, description, source_availability)
# ---------------------------------------------------------------------------

SIGNAL_SCHEMA: dict[str, dict] = {
    # ── FUELING ──────────────────────────────────────────────────────────────
    "STFT_B1": {
        "family": "fueling",
        "unit": "%",
        "description": "Short term fuel trim bank 1",
        "source_availability": {
            "mhd": "STFT 1 (%)",
            "car_scanner": "Short term fuel % trim - Bank 1 (%)",
            "carobd": "SHORT_TERM_FUEL_TRIM_BANK_1",
            "cephasax": "SHORT TERM FUEL TRIM BANK 1",
            "isay_gerard": "Ajuste de combustible a corto plazo (Banco 1)",
        },
    },
    "STFT_B2": {
        "family": "fueling",
        "unit": "%",
        "description": "Short term fuel trim bank 2",
        "source_availability": {
            "mhd": "STFT 2 (%)",
            "car_scanner": "Short term fuel % trim - Bank 2 (%)",
            "carobd": "SHORT_TERM_FUEL_TRIM_BANK_2",
            "cephasax": "SHORT TERM FUEL TRIM BANK 2",
            "isay_gerard": "absent",
        },
    },
    "LTFT_B1": {
        "family": "fueling",
        "unit": "%",
        "description": "Long term fuel trim bank 1",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "Long term fuel % trim - Bank 1 (%)",
            "carobd": "LONG_TERM_FUEL_TRIM_BANK_1",
            "cephasax": "absent",
            "isay_gerard": "Ajuste de combustible a largo plazo (Banco 1)",
        },
    },
    "LTFT_B2": {
        "family": "fueling",
        "unit": "%",
        "description": "Long term fuel trim bank 2",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "Long term fuel % trim - Bank 2 (%)",
            "carobd": "LONG_TERM_FUEL_TRIM_BANK_2",
            "cephasax": "LONG TERM FUEL TRIM BANK 2",
            "isay_gerard": "absent",
        },
    },
    "AFR_B1": {
        "family": "fueling",
        "unit": "AFR",
        "description": "Air/fuel ratio wideband lambda bank 1 (MHD)",
        "source_availability": {
            "mhd": "Lambda bank 1 (AFR)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "AFR_B2": {
        "family": "fueling",
        "unit": "AFR",
        "description": "Air/fuel ratio wideband lambda bank 2 (MHD)",
        "source_availability": {
            "mhd": "Lambda bank 2 (AFR)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "O2_VOLT_B1S2": {
        "family": "fueling",
        "unit": "V",
        "description": "Narrowband downstream O2 voltage bank 1 sensor 2",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "Voltaje del sensor de labda (Banco 1 - Sensor 2)",
        },
    },
    "O2_LAMBDA_B1S1": {
        "family": "fueling",
        "unit": "lambda",
        "description": "Wideband equivalence ratio upstream bank 1 sensor 1",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "EQUIV_RATIO",
            "isay_gerard": "Relación de equivalencia del sensor de O2 (Banco 1 - Sensor 1)",
        },
    },
    "O2_CURRENT_B1S1": {
        "family": "fueling",
        "unit": "mA",
        "description": "Wideband O2 current upstream bank 1 sensor 1 (Isay Gerard)",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "Corriente del sensor de O2 (Banco 1 - Sensor 1)",
        },
    },
    "EQUIV_RATIO": {
        "family": "fueling",
        "unit": "lambda",
        "description": "Commanded equivalence ratio",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "EQUIV_RATIO",
            "isay_gerard": "absent",
        },
    },
    "FUEL_PRESSURE": {
        "family": "fueling",
        "unit": "PSI",
        "description": "Fuel rail pressure low side",
        "source_availability": {
            "mhd": "Fuel low pressure sensor (PSI)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "FUEL_PRESSURE",
            "isay_gerard": "absent",
        },
    },
    "FUEL_RAIL_PSI": {
        "family": "fueling",
        "unit": "PSI",
        "description": "High side rail pressure (MHD)",
        "source_availability": {
            "mhd": "Rail pressure (PSI)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── IGNITION ──────────────────────────────────────────────────────────────
    "TIMING_ADV": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Generic timing advance (OBD2 Mode 01)",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "Timing advance (°)",
            "carobd": "TIMING_ADVANCE",
            "cephasax": "TIMING_ADVANCE",
            "isay_gerard": "Avance de tiempo de encendido",
        },
    },
    "TIMING_CYL1": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Per-cylinder timing correction cylinder 1 (MHD)",
        "source_availability": {
            "mhd": "Timing Cyl. 1 (*CRK)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "TIMING_CYL2": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Per-cylinder timing correction cylinder 2 (MHD)",
        "source_availability": {
            "mhd": "Cyl2 Timing Cor (*)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "TIMING_CYL3": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Per-cylinder timing correction cylinder 3 (MHD)",
        "source_availability": {
            "mhd": "Cyl3 Timing Cor (*)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "TIMING_CYL4": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Per-cylinder timing correction cylinder 4 (MHD)",
        "source_availability": {
            "mhd": "Cyl4 Timing Cor (*)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "TIMING_CYL5": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Per-cylinder timing correction cylinder 5 (MHD)",
        "source_availability": {
            "mhd": "Cyl5 Timing Cor (*)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "TIMING_CYL6": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Per-cylinder timing correction cylinder 6 (MHD)",
        "source_availability": {
            "mhd": "Cyl6 Timing Cor (*)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "KNOCK_RETARD": {
        "family": "ignition",
        "unit": "degrees",
        "description": "Derived: most negative per-cylinder timing correction in session",
        "source_availability": {
            "mhd": "derived from Cyl1-6 Timing Cor",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── THERMAL ──────────────────────────────────────────────────────────────
    "ECT": {
        "family": "thermal",
        "unit": "°C",
        "description": "Engine coolant temperature",
        "source_availability": {
            "mhd": "Coolant (*F) — converted",
            "car_scanner": "Engine coolant temperature (℉) — converted",
            "carobd": "COOLANT_TEMPERATURE",
            "cephasax": "ENGINE_COOLANT_TEMP",
            "isay_gerard": "Temperatura del líquido de enfriamiento del motor",
        },
    },
    "IAT": {
        "family": "thermal",
        "unit": "°C",
        "description": "Intake air temperature",
        "source_availability": {
            "mhd": "IAT (*F) — converted",
            "car_scanner": "Intake air temperature (℉) — converted",
            "carobd": "INTAKE_AIR_TEMP",
            "cephasax": "AIR_INTAKE_TEMP",
            "isay_gerard": "Temperatura del aire del colector de admisión",
        },
    },
    "OIL_TEMP": {
        "family": "thermal",
        "unit": "°C",
        "description": "Oil temperature",
        "source_availability": {
            "mhd": "Oil temp (*F) — converted",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "EGT": {
        "family": "thermal",
        "unit": "°C",
        "description": "Exhaust gas temperature pre-turbo",
        "source_availability": {
            "mhd": "EGT Pre-turbo (*F) — converted",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "TRANS_TEMP": {
        "family": "thermal",
        "unit": "°C",
        "description": "Transmission temperature",
        "source_availability": {
            "mhd": "Transmission temp (*F) — converted",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "AMB_TEMP": {
        "family": "thermal",
        "unit": "°C",
        "description": "Ambient air temperature",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "AMBIENT_AIR_TEMP",
            "isay_gerard": "Temperatura ambiente",
        },
    },
    # ── BOOST ────────────────────────────────────────────────────────────────
    "BOOST_ACTUAL": {
        "family": "boost",
        "unit": "PSI",
        "description": "Measured boost pressure",
        "source_availability": {
            "mhd": "Boost (PSI)",
            "car_scanner": "Calculated boost (psi)",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "BOOST_TARGET": {
        "family": "boost",
        "unit": "PSI",
        "description": "Boost target pressure",
        "source_availability": {
            "mhd": "Boost target (PSI)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "WGDC_B1": {
        "family": "boost",
        "unit": "%",
        "description": "Wastegate duty cycle bank 1",
        "source_availability": {
            "mhd": "WGDC Bank 1 (%)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "WGDC_B2": {
        "family": "boost",
        "unit": "%",
        "description": "Wastegate duty cycle bank 2",
        "source_availability": {
            "mhd": "WGDC Bank 2 (%)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "WGDC_BASE": {
        "family": "boost",
        "unit": "%",
        "description": "Wastegate base value",
        "source_availability": {
            "mhd": "WGDC Base Value (%)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "WGDC_AFTER_PID": {
        "family": "boost",
        "unit": "%",
        "description": "Wastegate after PID correction",
        "source_availability": {
            "mhd": "WGDC After PID (%)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── CATALYST ─────────────────────────────────────────────────────────────
    "CAT_TEMP_B1S1": {
        "family": "catalyst",
        "unit": "°C",
        "description": "Catalyst temperature bank 1 sensor 1",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "CATALYST_TEMPERATURE_BANK1_SENSOR1",
            "cephasax": "absent",
            "isay_gerard": "Temperatura del catalizador (Banco 1 - Sensor 1)",
        },
    },
    "CAT_TEMP_B1S2": {
        "family": "catalyst",
        "unit": "°C",
        "description": "Catalyst temperature bank 1 sensor 2",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "CATALYST_TEMPERATURE_BANK1_SENSOR2",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── FUEL_SUPPLY ──────────────────────────────────────────────────────────
    "MAF": {
        "family": "fuel_supply",
        "unit": "g/s",
        "description": "Mass airflow",
        "source_availability": {
            "mhd": "MAF (g/s)",
            "car_scanner": "absent",
            "carobd": "MAF",
            "cephasax": "MAF",
            "isay_gerard": "absent",
        },
    },
    "MAF_REQ": {
        "family": "fuel_supply",
        "unit": "g/s",
        "description": "Requested MAF",
        "source_availability": {
            "mhd": "MAF Req (g/s)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "MAP": {
        "family": "fuel_supply",
        "unit": "kPa",
        "description": "Manifold absolute pressure",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "Intake manifold absolute pressure (psi) — converted",
            "carobd": "INTAKE_MANIFOLD_PRESSURE",
            "cephasax": "INTAKE_MANIFOLD_PRESSURE",
            "isay_gerard": "Presión absoluta del colector de admisión",
        },
    },
    "LOAD": {
        "family": "fuel_supply",
        "unit": "%",
        "description": "Calculated engine load",
        "source_availability": {
            "mhd": "Load actual",
            "car_scanner": "Calculated engine load value (%)",
            "carobd": "ENGINE_LOAD",
            "cephasax": "ENGINE_LOAD",
            "isay_gerard": "Carga calculada del motor",
        },
    },
    "THROTTLE": {
        "family": "fuel_supply",
        "unit": "%",
        "description": "Throttle position",
        "source_availability": {
            "mhd": "Throttle Position",
            "car_scanner": "absent",
            "carobd": "THROTTLE",
            "cephasax": "THROTTLE_POS",
            "isay_gerard": "absent",
        },
    },
    "ACCEL_PED": {
        "family": "fuel_supply",
        "unit": "%",
        "description": "Accelerator pedal position",
        "source_availability": {
            "mhd": "Accel Ped. Pos. (%)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── COMPOSITION ──────────────────────────────────────────────────────────
    "ETHANOL_PCT": {
        "family": "composition",
        "unit": "%",
        "description": "Ethanol content active",
        "source_availability": {
            "mhd": "Ethanol Content (Active) (%)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "FUEL_INTERP": {
        "family": "composition",
        "unit": "%",
        "description": "Fuel interpolation FF %",
        "source_availability": {
            "mhd": "Fuel Interpolation (FF) (%)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "FUEL_MODE": {
        "family": "composition",
        "unit": "raw",
        "description": "Fuel mode flag (MHD)",
        "source_availability": {
            "mhd": "Fuel mode (-)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── EXHAUST ──────────────────────────────────────────────────────────────
    "AMB_PRESSURE": {
        "family": "exhaust",
        "unit": "PSI",
        "description": "Ambient/barometric pressure",
        "source_availability": {
            "mhd": "Amb pressure (PSI)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "OIL_PRESSURE_NXM": {
        "family": "exhaust",
        "unit": "PSI",
        "description": "Oil pressure (NXM aftermarket kit, MHD)",
        "source_availability": {
            "mhd": "Oil Pressure (NXM kit) (PSI)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── DRIVETRAIN ───────────────────────────────────────────────────────────
    "RPM": {
        "family": "drivetrain",
        "unit": "rpm",
        "description": "Engine RPM",
        "source_availability": {
            "mhd": "RPM (RPM)",
            "car_scanner": "Engine RPM (rpm)",
            "carobd": "ENGINE_RPM",
            "cephasax": "ENGINE_RPM",
            "isay_gerard": "RPM del motor",
        },
    },
    "VSS": {
        "family": "drivetrain",
        "unit": "km/h",
        "description": "Vehicle speed",
        "source_availability": {
            "mhd": "Speed (mph) — converted",
            "car_scanner": "Vehicle speed (mph) — converted",
            "carobd": "VEHICLE_SPEED",
            "cephasax": "SPEED",
            "isay_gerard": "Velocidad",
        },
    },
    "GEAR": {
        "family": "drivetrain",
        "unit": "raw",
        "description": "Gear position",
        "source_availability": {
            "mhd": "Gear (-)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "TORQUE_ACTUAL": {
        "family": "drivetrain",
        "unit": "Nm",
        "description": "Actual torque",
        "source_availability": {
            "mhd": "Torque actual value (Nm)",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    "RUN_TIME": {
        "family": "drivetrain",
        "unit": "seconds",
        "description": "Engine run time",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "ENGINE_RUN_TINE",
            "cephasax": "absent",
            "isay_gerard": "absent",
        },
    },
    # ── META ─────────────────────────────────────────────────────────────────
    "DTCs": {
        "family": "meta",
        "unit": "string",
        "description": "Fault codes list",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "TROUBLE_CODES",
            "isay_gerard": "absent",
        },
    },
    "DTC_COUNT": {
        "family": "meta",
        "unit": "count",
        "description": "Number of active DTCs",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "DTC_NUMBER",
            "isay_gerard": "absent",
        },
    },
    "VEHICLE_MARK": {
        "family": "meta",
        "unit": "string",
        "description": "Vehicle make string (cephasax)",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "MARK",
            "isay_gerard": "absent",
        },
    },
    "VEHICLE_MODEL": {
        "family": "meta",
        "unit": "string",
        "description": "Vehicle model string (cephasax)",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "MODEL",
            "isay_gerard": "absent",
        },
    },
    "VEHICLE_YEAR": {
        "family": "meta",
        "unit": "string",
        "description": "Vehicle year string (cephasax)",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "CAR_YEAR",
            "isay_gerard": "absent",
        },
    },
    "MIL_DISTANCE": {
        "family": "meta",
        "unit": "km",
        "description": "Distance driven with MIL on",
        "source_availability": {
            "mhd": "absent",
            "car_scanner": "absent",
            "carobd": "absent",
            "cephasax": "absent",
            "isay_gerard": "Distancia recorrida con la luz indicadora de falla (MIL) encendida",
        },
    },
}

# ---------------------------------------------------------------------------
# SOURCE_COLUMN_MAP — (source_name, raw_column_header) → canonical_name
# ---------------------------------------------------------------------------

SOURCE_COLUMN_MAP: dict[tuple[str, str], str] = {
    # ── MHD ──────────────────────────────────────────────────────────────────
    ("mhd", "RPM"):                         "RPM",
    ("mhd", "RPM (RPM)"):                   "RPM",
    ("mhd", "Speed"):                        "VSS",
    ("mhd", "Speed (mph)"):                  "VSS",
    ("mhd", "Boost"):                        "BOOST_ACTUAL",
    ("mhd", "Boost (PSI)"):                  "BOOST_ACTUAL",
    ("mhd", "Boost target"):                 "BOOST_TARGET",
    ("mhd", "Boost target (PSI)"):           "BOOST_TARGET",
    ("mhd", "Coolant"):                      "ECT",
    ("mhd", "Coolant (*F)"):                 "ECT",
    ("mhd", "IAT"):                          "IAT",
    ("mhd", "IAT (*F)"):                     "IAT",
    ("mhd", "Oil temp"):                     "OIL_TEMP",
    ("mhd", "Oil temp (*F)"):                "OIL_TEMP",
    ("mhd", "EGT Pre-turbo"):                "EGT",
    ("mhd", "EGT Pre-turbo (*F)"):           "EGT",
    ("mhd", "Transmission temp"):            "TRANS_TEMP",
    ("mhd", "Transmission temp (*F)"):       "TRANS_TEMP",
    ("mhd", "STFT 1"):                       "STFT_B1",
    ("mhd", "STFT 1 (%)"):                   "STFT_B1",
    ("mhd", "STFT 2"):                       "STFT_B2",
    ("mhd", "STFT 2 (%)"):                   "STFT_B2",
    ("mhd", "Lambda bank 1"):                "AFR_B1",
    ("mhd", "Lambda bank 1 (AFR)"):          "AFR_B1",
    ("mhd", "Lambda bank 2"):                "AFR_B2",
    ("mhd", "Lambda bank 2 (AFR)"):          "AFR_B2",
    ("mhd", "MAF"):                          "MAF",
    ("mhd", "MAF (g/s)"):                    "MAF",
    ("mhd", "MAF Req"):                      "MAF_REQ",
    ("mhd", "MAF Req (g/s)"):               "MAF_REQ",
    ("mhd", "MAF Req (wgdc)"):              "MAF_REQ",
    ("mhd", "MAF Req (wgdc) (g/s)"):        "MAF_REQ",
    ("mhd", "Load actual"):                  "LOAD",
    ("mhd", "Load req."):                    "LOAD",
    ("mhd", "Throttle Position"):            "THROTTLE",
    ("mhd", "Accel Ped. Pos."):             "ACCEL_PED",
    ("mhd", "Accel Ped. Pos. (%)"):         "ACCEL_PED",
    ("mhd", "Gear"):                         "GEAR",
    ("mhd", "Gear (-)"):                     "GEAR",
    ("mhd", "Torque actual value"):          "TORQUE_ACTUAL",
    ("mhd", "Torque actual value (Nm)"):     "TORQUE_ACTUAL",
    ("mhd", "Cyl1 Timing Cor"):              "TIMING_CYL1",
    ("mhd", "Cyl1 Timing Cor (*)"):          "TIMING_CYL1",
    ("mhd", "Cyl2 Timing Cor"):              "TIMING_CYL2",
    ("mhd", "Cyl2 Timing Cor (*)"):          "TIMING_CYL2",
    ("mhd", "Cyl3 Timing Cor"):              "TIMING_CYL3",
    ("mhd", "Cyl3 Timing Cor (*)"):          "TIMING_CYL3",
    ("mhd", "Cyl4 Timing Cor"):              "TIMING_CYL4",
    ("mhd", "Cyl4 Timing Cor (*)"):          "TIMING_CYL4",
    ("mhd", "Cyl5 Timing Cor"):              "TIMING_CYL5",
    ("mhd", "Cyl5 Timing Cor (*)"):          "TIMING_CYL5",
    ("mhd", "Cyl6 Timing Cor"):              "TIMING_CYL6",
    ("mhd", "Cyl6 Timing Cor (*)"):          "TIMING_CYL6",
    ("mhd", "Timing Cyl. 1"):                "TIMING_CYL1",
    ("mhd", "Timing Cyl. 1 (*CRK)"):        "TIMING_CYL1",
    ("mhd", "WGDC Bank 1"):                  "WGDC_B1",
    ("mhd", "WGDC Bank 1 (%)"):              "WGDC_B1",
    ("mhd", "WGDC Bank 2"):                  "WGDC_B2",
    ("mhd", "WGDC Bank 2 (%)"):              "WGDC_B2",
    ("mhd", "WGDC Base Value"):              "WGDC_BASE",
    ("mhd", "WGDC Base Value (%)"):          "WGDC_BASE",
    ("mhd", "WGDC After PID"):               "WGDC_AFTER_PID",
    ("mhd", "WGDC After PID (%)"):           "WGDC_AFTER_PID",
    ("mhd", "Ethanol Content (Active)"):     "ETHANOL_PCT",
    ("mhd", "Ethanol Content (Active) (%)"):  "ETHANOL_PCT",
    ("mhd", "Fuel Interpolation (FF)"):      "FUEL_INTERP",
    ("mhd", "Fuel Interpolation (FF) (%)"):  "FUEL_INTERP",
    ("mhd", "Fuel mode"):                    "FUEL_MODE",
    ("mhd", "Fuel mode (-)"):                "FUEL_MODE",
    ("mhd", "Fuel low pressure sensor"):     "FUEL_PRESSURE",
    ("mhd", "Fuel low pressure sensor (PSI)"): "FUEL_PRESSURE",
    ("mhd", "Rail pressure"):                "FUEL_RAIL_PSI",
    ("mhd", "Rail pressure (PSI)"):          "FUEL_RAIL_PSI",
    ("mhd", "Amb pressure"):                 "AMB_PRESSURE",
    ("mhd", "Amb pressure (PSI)"):           "AMB_PRESSURE",
    ("mhd", "Oil Pressure (NXM kit)"):       "OIL_PRESSURE_NXM",
    ("mhd", "Oil Pressure (NXM kit) (PSI)"): "OIL_PRESSURE_NXM",
    # ── CAR SCANNER ──────────────────────────────────────────────────────────
    ("car_scanner", "Engine RPM (rpm)"):                           "RPM",
    ("car_scanner", "Engine RPM x1000 (rpm)"):                     None,  # skip duplicate
    ("car_scanner", "Calculated engine load value (%)"):           "LOAD",
    ("car_scanner", "Engine coolant temperature (℉)"):             "ECT",
    ("car_scanner", "Short term fuel % trim - Bank 1 (%)"):        "STFT_B1",
    ("car_scanner", "Long term fuel % trim - Bank 1 (%)"):         "LTFT_B1",
    ("car_scanner", "Short term fuel % trim - Bank 2 (%)"):        "STFT_B2",
    ("car_scanner", "Long term fuel % trim - Bank 2 (%)"):         "LTFT_B2",
    ("car_scanner", "Intake air temperature (℉)"):                 "IAT",
    ("car_scanner", "Intake manifold absolute pressure (psi)"):    "MAP",
    ("car_scanner", "Vehicle speed (mph)"):                        "VSS",
    ("car_scanner", "Timing advance (°)"):                         "TIMING_ADV",
    ("car_scanner", "Calculated boost (psi)"):                     "BOOST_ACTUAL",
    # ── CAROBD ───────────────────────────────────────────────────────────────
    ("carobd", "ENGINE_RPM"):                              "RPM",
    ("carobd", "ENGINE_LOAD"):                             "LOAD",
    ("carobd", "COOLANT_TEMPERATURE"):                     "ECT",
    ("carobd", "SHORT_TERM_FUEL_TRIM_BANK_1"):             "STFT_B1",
    ("carobd", "LONG_TERM_FUEL_TRIM_BANK_1"):              "LTFT_B1",
    ("carobd", "SHORT_TERM_FUEL_TRIM_BANK_2"):             "STFT_B2",
    ("carobd", "LONG_TERM_FUEL_TRIM_BANK_2"):              "LTFT_B2",
    ("carobd", "INTAKE_MANIFOLD_PRESSURE"):                "MAP",
    ("carobd", "MAF"):                                     "MAF",
    ("carobd", "INTAKE_AIR_TEMP"):                         "IAT",
    ("carobd", "VEHICLE_SPEED"):                           "VSS",
    ("carobd", "THROTTLE"):                                "THROTTLE",
    ("carobd", "TIMING_ADVANCE"):                          "TIMING_ADV",
    ("carobd", "CATALYST_TEMPERATURE_BANK1_SENSOR1"):      "CAT_TEMP_B1S1",
    ("carobd", "CATALYST_TEMPERATURE_BANK1_SENSOR2"):      "CAT_TEMP_B1S2",
    ("carobd", "ENGINE_RUN_TINE"):                         "RUN_TIME",  # source typo preserved
    # ── CEPHASAX ─────────────────────────────────────────────────────────────
    ("cephasax", "SHORT TERM FUEL TRIM BANK 1"):           "STFT_B1",
    ("cephasax", "SHORT TERM FUEL TRIM BANK 2"):           "STFT_B2",
    ("cephasax", "LONG TERM FUEL TRIM BANK 2"):            "LTFT_B2",
    ("cephasax", "ENGINE_COOLANT_TEMP"):                   "ECT",
    ("cephasax", "ENGINE_RPM"):                            "RPM",
    ("cephasax", "ENGINE_LOAD"):                           "LOAD",
    ("cephasax", "MAF"):                                   "MAF",
    ("cephasax", "INTAKE_MANIFOLD_PRESSURE"):              "MAP",
    ("cephasax", "AIR_INTAKE_TEMP"):                       "IAT",
    ("cephasax", "AMBIENT_AIR_TEMP"):                      "AMB_TEMP",
    ("cephasax", "SPEED"):                                 "VSS",
    ("cephasax", "THROTTLE_POS"):                          "THROTTLE",
    ("cephasax", "TIMING_ADVANCE"):                        "TIMING_ADV",
    ("cephasax", "FUEL_PRESSURE"):                         "FUEL_PRESSURE",
    ("cephasax", "TROUBLE_CODES"):                         "DTCs",
    ("cephasax", "DTC_NUMBER"):                            "DTC_COUNT",
    ("cephasax", "EQUIV_RATIO"):                           "O2_LAMBDA_B1S1",
    ("cephasax", "MARK"):                                  "VEHICLE_MARK",
    ("cephasax", "MODEL"):                                 "VEHICLE_MODEL",
    ("cephasax", "CAR_YEAR"):                              "VEHICLE_YEAR",
    # ── ISAY GERARD ──────────────────────────────────────────────────────────
    # Full headers with unit brackets (exact)
    ("isay_gerard", "RPM del motor [rpm]"):                                                    "RPM",
    ("isay_gerard", "Carga calculada del motor [%]"):                                          "LOAD",
    ("isay_gerard", "Temperatura del líquido de enfriamiento del motor [°C]"):                 "ECT",
    ("isay_gerard", "Ajuste de combustible a corto plazo (Banco 1) [%]"):                      "STFT_B1",
    ("isay_gerard", "Ajuste de combustible a largo plazo (Banco 1) [%]"):                      "LTFT_B1",
    ("isay_gerard", "Presión absoluta del colector de admisión [kPa]"):                        "MAP",
    ("isay_gerard", "Velocidad [km/h]"):                                                       "VSS",
    ("isay_gerard", "Avance de tiempo de encendido [°]"):                                      "TIMING_ADV",
    ("isay_gerard", "Temperatura del aire del colector de admisión [°C]"):                     "IAT",
    ("isay_gerard", "Voltaje del sensor de labda (Banco 1 - Sensor 2) [V]"):                   "O2_VOLT_B1S2",
    ("isay_gerard", "Temperatura del catalizador (Banco 1 - Sensor 1) [°C]"):                  "CAT_TEMP_B1S1",
    ("isay_gerard", "Relación de equivalencia del sensor de O₂ (Banco 1 - Sensor 1)"):        "O2_LAMBDA_B1S1",
    ("isay_gerard", "Corriente del sensor de O₂ (Banco 1 - Sensor 1) [mA]"):                  "O2_CURRENT_B1S1",
    ("isay_gerard", "Temperatura ambiente [°C]"):                                              "AMB_TEMP",
    ("isay_gerard", "Distancia recorrida con la luz indicadora de falla (MIL) encendida [km]"): "MIL_DISTANCE",
    # Stripped variants (no unit brackets) — used after unit stripping
    ("isay_gerard", "RPM del motor"):                                                          "RPM",
    ("isay_gerard", "Carga calculada del motor"):                                              "LOAD",
    ("isay_gerard", "Temperatura del líquido de enfriamiento del motor"):                      "ECT",
    ("isay_gerard", "Ajuste de combustible a corto plazo (Banco 1)"):                          "STFT_B1",
    ("isay_gerard", "Ajuste de combustible a largo plazo (Banco 1)"):                          "LTFT_B1",
    ("isay_gerard", "Presión absoluta del colector de admisión"):                              "MAP",
    ("isay_gerard", "Velocidad"):                                                              "VSS",
    ("isay_gerard", "Avance de tiempo de encendido"):                                          "TIMING_ADV",
    ("isay_gerard", "Temperatura del aire del colector de admisión"):                          "IAT",
    ("isay_gerard", "Voltaje del sensor de labda (Banco 1 - Sensor 2)"):                       "O2_VOLT_B1S2",
    ("isay_gerard", "Temperatura del catalizador (Banco 1 - Sensor 1)"):                       "CAT_TEMP_B1S1",
    ("isay_gerard", "Relación de equivalencia del sensor de O₂ (Banco 1 - Sensor 1)"):        "O2_LAMBDA_B1S1",
    ("isay_gerard", "Corriente del sensor de O₂ (Banco 1 - Sensor 1)"):                       "O2_CURRENT_B1S1",
    ("isay_gerard", "Temperatura ambiente"):                                                   "AMB_TEMP",
    ("isay_gerard", "Distancia recorrida con la luz indicadora de falla (MIL) encendida"):     "MIL_DISTANCE",
}

# ---------------------------------------------------------------------------
# Unit conversion functions
# All temperatures stored in °C; speeds in km/h.
# Boost/rail pressure kept in PSI (BMW-native).
# MAP kept in kPa (OBD2 standard).
# ---------------------------------------------------------------------------

def F_to_C(v: float) -> float:
    return (v - 32.0) * 5.0 / 9.0

def PSI_to_kPa(v: float) -> float:
    return v * 6.89476

def kPa_to_PSI(v: float) -> float:
    return v / 6.89476

def mph_to_kmh(v: float) -> float:
    return v * 1.60934

# UNIT_CONVERSIONS: canonical_name → conversion function to apply on ingest
# Applied when the source column implies a unit different from the canonical unit.
# Keys are (source, canonical_name) pairs.
UNIT_CONVERSIONS: dict[tuple[str, str], Callable[[float], float]] = {
    # MHD temperatures are in °F
    ("mhd", "ECT"):        F_to_C,
    ("mhd", "IAT"):        F_to_C,
    ("mhd", "OIL_TEMP"):   F_to_C,
    ("mhd", "EGT"):        F_to_C,
    ("mhd", "TRANS_TEMP"): F_to_C,
    # Car Scanner temperatures are in °F
    ("car_scanner", "ECT"): F_to_C,
    ("car_scanner", "IAT"): F_to_C,
    # Car Scanner MAP is in PSI → convert to kPa
    ("car_scanner", "MAP"): PSI_to_kPa,
    # Car Scanner speed is in mph → convert to km/h
    ("car_scanner", "VSS"): mph_to_kmh,
    # Car Scanner boost is PSI — keep as PSI (no conversion)
    # MHD speed is in mph → convert to km/h
    ("mhd", "VSS"): mph_to_kmh,
}

# ---------------------------------------------------------------------------
# ROLLOVER_SENTINELS — ELM327 artifacts
# ---------------------------------------------------------------------------

ROLLOVER_SENTINELS: dict[str, list[float]] = {
    "ECT":     [255.0],
    "MAP":     [255.0],
    "STFT_B1": [-96.0, -100.0],
    "STFT_B2": [-96.0, -100.0],
    "LTFT_B1": [-96.0, -100.0],
    "LTFT_B2": [-96.0, -100.0],
}

# ---------------------------------------------------------------------------
# HEALTHY_RANGES — expected operating ranges for health scoring (inclusive)
# ---------------------------------------------------------------------------

HEALTHY_RANGES: dict[str, tuple[float, float]] = {
    "STFT_B1":       (-5.0,   5.0),
    "STFT_B2":       (-5.0,   5.0),
    "LTFT_B1":       (-5.0,   5.0),
    "LTFT_B2":       (-5.0,   5.0),
    "ECT":           (75.0,  110.0),
    "TIMING_ADV":    (-5.0,  45.0),
    "CAT_TEMP_B1S1": (300.0, 850.0),
    "CAT_TEMP_B1S2": (300.0, 850.0),
    "AFR_B1":        (13.5,  15.5),
    "AFR_B2":        (13.5,  15.5),
    "OIL_TEMP":      (80.0,  130.0),
    "IAT":           (-20.0,  60.0),
    "AMB_TEMP":      (-40.0,  60.0),
    "BOOST_ACTUAL":  (-5.0,  30.0),
}

# ---------------------------------------------------------------------------
# SATURATION_LIMITS — for fuel trim scoring
# ---------------------------------------------------------------------------

SATURATION_LIMITS: dict[str, float] = {
    "STFT_B1": 25.0,
    "STFT_B2": 25.0,
    "LTFT_B1": 25.0,
    "LTFT_B2": 25.0,
}

# ---------------------------------------------------------------------------
# detect_source — identify source from column headers
# ---------------------------------------------------------------------------

def _strip_units_detect(header: str) -> str:
    """Strip trailing unit bracket/paren for source detection."""
    import re
    return re.sub(r'\s*[\[\(][^\]\)]*[\]\)]\s*$', '', header).strip()


def detect_source(columns: list[str]) -> str:
    """Return the source name based on distinctive column patterns."""
    col_set = set(columns)
    bare_set = set(_strip_units_detect(c) for c in columns)
    # MHD: unique headers with (*F) style or MHD version string
    if any(c.startswith("MHD") for c in col_set):
        return "mhd"
    if any("*F" in c or "*CRK" in c or "WGDC" in c for c in col_set):
        return "mhd"
    if any("STFT 1" in c or "Lambda bank 1" in c for c in col_set):
        return "mhd"
    # Car Scanner: verbose English with ℉ or mph units in header
    if any("℉" in c for c in col_set):
        return "car_scanner"
    if any("Engine RPM" in c or "Calculated boost" in c for c in col_set):
        return "car_scanner"
    # Isay Gerard: Spanish headers
    if any("Ajuste" in c or "RPM del motor" in c or "líquido" in c for c in col_set):
        return "isay_gerard"
    # cephasax: has TROUBLE_CODES or MARK or space-delimited fuel trim names
    if "SHORT TERM FUEL TRIM BANK 1" in col_set or "TROUBLE_CODES" in col_set or "MARK" in col_set:
        return "cephasax"
    # carOBD: uppercase OBD2 names — check bare (unit-stripped) set since columns are "ENGINE_RPM ()"
    if "ENGINE_RPM" in bare_set or "COOLANT_TEMPERATURE" in bare_set or "ENGINE_RUN_TINE" in bare_set:
        return "carobd"
    return "unknown"
