"""
Vehicle configuration registry.
Ported and expanded from obd2-vehicle-health-advisor/lib/vehicles.ts.
"""

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class VehicleConfig:
    id: str
    make: str
    model: str
    year: int
    engine: str
    turbocharged: bool
    bank_count: int          # 1 or 2
    fuel_system: str         # "MAF" or "MAP"
    fuel_type: str           # "gasoline" or "flex-fuel"
    has_egr: bool
    known_quirks: list[str]
    expected_pids: list[str]
    inaccessible_pids: list[str] = field(default_factory=list)


VEHICLES: list[VehicleConfig] = [
    VehicleConfig(
        id="bmw-335i-2009",
        make="BMW",
        model="335i",
        year=2009,
        engine="3.0L N54 Twin-Turbo I6",
        turbocharged=True,
        bank_count=2,
        fuel_system="MAF",
        fuel_type="flex-fuel",
        has_egr=False,
        known_quirks=[
            "HPFP (high-pressure fuel pump) failure is one of the most common N54 faults — "
            "symptoms are lean codes (P0087, P2177, P2179), stalling under boost, and rough "
            "running at high load; rail pressure drop under WOT is the key diagnostic signal",
            "HPFP low-pressure feed must be 65–75 PSI at idle and hold under boost; if "
            "low-pressure drops below 55 PSI under load, HPFP cannot build adequate rail pressure",
            "Runs flex fuel — ethanol content changes every fill-up; AFR targets, fuel trims, "
            "and timing advance all shift with ethanol %; always note ethanol % when interpreting "
            "fuel trim data",
            "At high ethanol blends (E50+), STFT/LTFT will read persistently negative on a "
            "non-ethanol-compensating tune — this is expected, not a fault",
            "STFT/LTFT values on generic OBD2 are scaled differently than native BMW protocol — "
            "add ~2% correction factor when comparing to MHD or NCS logs",
            "Wastegate rattle at cold start is a known benign N54 characteristic — not a fault",
            "Charge pipe blowout under boost causes sudden lean spike followed by boost loss; "
            "look for STFT max spike >20% with simultaneous boost pressure drop",
            "Injector carbon buildup on GDI system — no port wash; intake valves accumulate "
            "carbon over time; symptoms are lean idle trims that normalize under load; "
            "requires walnut blasting every 40–60k miles",
            "Per-cylinder timing knock retard (visible via MHD) is more diagnostic than "
            "aggregate STFT — a single cylinder pulling timing while others are normal points "
            "to an injector or compression issue on that cylinder",
        ],
        expected_pids=[
            "0104", "0105", "010A", "010B", "010C", "010D", "010F",
            "0110", "0111", "0114", "0115", "011B", "011C",
            "0106", "0107", "0108", "0109", "0133",
        ],
    ),
    VehicleConfig(
        id="tundra-2007",
        make="Toyota",
        model="Tundra",
        year=2007,
        engine="4.0L V6 (1GR-FE)",
        turbocharged=False,
        bank_count=2,
        fuel_system="MAF",
        fuel_type="gasoline",
        has_egr=False,
        known_quirks=[
            "Secondary air injection pump common failure after 100k miles",
            "Bank 2 O2 sensor wiring prone to heat damage near exhaust manifold",
            "EVAP system leak codes triggered by aftermarket gas caps",
            "Generic OBD2 scanners (ELM327) often fail to log MAF, upstream O2, and STFT B2 "
            "on this vehicle — missing PIDs are a tool limitation, not necessarily a sensor fault",
        ],
        inaccessible_pids=[
            "0110",  # MAF — frequently unreported by ELM327 on 1GR-FE
            "0108",  # STFT B2 — often missing from generic OBD2 captures
            "0114",  # O2 B1S1 — upstream O2 not reliably reported via generic OBD2
            "011B",  # O2 B2S1 — same
        ],
        expected_pids=[
            "0104", "0105", "010B", "010C", "010D", "010F",
            "0110", "0111", "0114", "0115", "011B", "011C",
            "0106", "0107", "0108", "0109",
        ],
    ),
    VehicleConfig(
        id="honda-fit-2015",
        make="Honda",
        model="Fit",
        year=2015,
        engine="1.5L L15B7 VTEC i4",
        turbocharged=False,
        bank_count=1,
        fuel_system="MAP",
        fuel_type="gasoline",
        has_egr=True,
        inaccessible_pids=[
            "010D",  # Vehicle speed — Honda Fit does not expose via generic OBD2; returns 0
        ],
        known_quirks=[
            "Honda uses a proprietary OBD2 profile; some generic scanners misread MAP sensor values",
            "EGR valve sticky at low mileage intervals — monitor P0400 family codes",
            "CVT heat sensitivity above 230°F; worth logging ATF temp if available",
            "Port injection allows O2 sensor fuel trim feedback on B1 only",
            "Limit to 8 PIDs to maintain adequate MAF polling rate at WOT",
        ],
        expected_pids=[
            "0104", "0105", "010B", "010C", "010D", "010F",
            "0111", "0114", "0115", "0106", "0107", "012C", "012D",
        ],
    ),
]


def get_vehicle_by_id(vehicle_id: str) -> Optional[VehicleConfig]:
    return next((v for v in VEHICLES if v.id == vehicle_id), None)


def list_vehicle_ids() -> list[str]:
    return [v.id for v in VEHICLES]
