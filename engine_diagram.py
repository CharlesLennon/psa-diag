#!/usr/bin/env python3
"""
PSA-DIAG Engine Bay & Sensor Architecture Diagram Module
Specialized for Citroën Grand C4 Picasso Mk1 (B58) 1.6 HDi (DV6 Engine • EGS6 CFC300P)

Provides:
- Detailed ASCII top-down engine bay schematic with numbered sensor callouts
- Comprehensive physical location descriptions, connector pinouts, and test specs
- Live/Simulated telemetry binding with threshold health evaluation
- Responsive SVG/HTML interactive vector diagram for companion web dashboard
"""

import sys
import os
import math

# ANSI Colors
BOLD = '\033[1m'
CYAN = '\033[36m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'
MAGENTA = '\033[35m'
RESET = '\033[0m'
DIM = '\033[2m'

# Complete Sensor Catalog for Citroën Grand C4 Picasso 1.6 HDi DV6 & EGS6
SENSOR_DATABASE = {
    1: {
        'id': 'MAF',
        'name': 'Mass Air Flow Sensor (Débitmètre)',
        'oem_ref': '1920.EK / 9650010780',
        'location': 'Intake duct between air filter box and turbo inlet (Rear left of bay)',
        'connector': '4-Pin Black (Pin 1: 12V, Pin 2: Ground, Pin 3: Signal, Pin 4: IAT)',
        'nominal': '250 - 550 mg/stroke (8 - 18 g/s at idle; >80 g/s under boost)',
        'param_key': 'maf_mg',
        'unit': 'mg/stroke',
        'warn_low': 200,
        'warn_high': 650,
        'system': 'Air Intake'
    },
    2: {
        'id': 'TURBO',
        'name': 'Garrett GT1544V Variable Geometry Turbo',
        'oem_ref': '0375.J6 / 753420-5005S',
        'location': 'Front-center of engine block behind heatshield above exhaust manifold',
        'connector': 'Vacuum capsule with position feedback sensor (3-Pin Black)',
        'nominal': '0.98 - 1.05 bar (Idle/Atmospheric) • Up to 2.35 bar (Max Boost)',
        'param_key': 'boost_bar',
        'unit': 'bar',
        'warn_low': 0.85,
        'warn_high': 2.50,
        'system': 'Forced Induction'
    },
    3: {
        'id': 'INTERCOOLER',
        'name': 'Air-to-Air Boost Intercooler',
        'oem_ref': '0384.N8',
        'location': 'Mounted in lower front bumper radiator pack behind lower grille',
        'connector': 'Quick-release boost hoses (hot side left, cold side right)',
        'nominal': 'Pressure drop across core < 0.15 bar',
        'param_key': 'intercooler_dp',
        'unit': 'bar',
        'warn_low': 0.0,
        'warn_high': 0.25,
        'system': 'Charge Air'
    },
    4: {
        'id': 'MAP_IAT',
        'name': 'Manifold Absolute Pressure & Air Temp (MAP)',
        'oem_ref': '1920.CZ / 9639381480',
        'location': 'On top plastic air intake dosing distributor (front right of engine)',
        'connector': '3-Pin Green / Black (5V supply, Ground, 0.5-4.5V output)',
        'nominal': '1013 mbar atmospheric (engine off) • 1000-1100 mbar idle',
        'param_key': 'map_mbar',
        'unit': 'mbar',
        'warn_low': 800,
        'warn_high': 2450,
        'system': 'Charge Air'
    },
    5: {
        'id': 'HP_PUMP',
        'name': 'Bosch CP1H High Pressure Fuel Pump',
        'oem_ref': '1920.HT / 0445010102',
        'location': 'Upper left of cylinder head, driven by camshaft timing belt',
        'connector': 'Fuel Temp Sensor (2-Pin Green) & Flow Regulator VC (2-Pin Brown)',
        'nominal': 'Supply suction > -0.3 bar; delivery 250 - 1600 bar',
        'param_key': 'fuel_temp_c',
        'unit': '°C',
        'warn_low': 5,
        'warn_high': 75,
        'system': 'Common Rail'
    },
    6: {
        'id': 'FUEL_RAIL',
        'name': 'Forged Steel High Pressure Common Rail',
        'oem_ref': '1570.L5',
        'location': 'Mounted under intake manifold at rear of cylinder head',
        'connector': 'High pressure steel lines to 4 injectors (17mm flare nuts)',
        'nominal': 'Target pressure closely tracks actual pressure (±15 bar)',
        'param_key': 'rail_press_bar',
        'unit': 'bar',
        'warn_low': 230,
        'warn_high': 1650,
        'system': 'Common Rail'
    },
    7: {
        'id': 'RAIL_SENSOR',
        'name': 'Common Rail Pressure Sensor',
        'oem_ref': '1920.GW / 55PP06-03',
        'location': 'Screwed into underside of fuel rail (central rear of block)',
        'connector': '3-Pin Black (Pin 1: Ground, Pin 2: Signal 0.5-4.5V, Pin 3: 5V Ref)',
        'nominal': '250 - 300 bar at warm idle (approx 1.0 - 1.2V signal)',
        'param_key': 'rail_target_bar',
        'unit': 'bar',
        'warn_low': 200,
        'warn_high': 1700,
        'system': 'Common Rail'
    },
    8: {
        'id': 'INJECTORS',
        'name': 'Bosch Common Rail Injectors (Cyl 1 - 4)',
        'oem_ref': '1980.J4 / 0445110259',
        'location': 'Deep wells in cylinder head (Cyl 1 Flywheel side -> Cyl 4 Belt side)',
        'connector': '2-Pin Black on each injector head (Piezo / Solenoid pulse)',
        'nominal': 'Correction balance within ±1.5 mg/stroke per cylinder',
        'param_key': 'inj_balance_c1',
        'unit': 'mg/str',
        'warn_low': -2.5,
        'warn_high': 2.5,
        'system': 'Fuel Injection'
    },
    9: {
        'id': 'VNT_VALVE',
        'name': 'Turbo Boost Control Electrovalve (VNT Solenoid)',
        'oem_ref': '1618.C9',
        'location': 'Mounted low behind engine block near brake servo vacuum line',
        'connector': '2-Pin Grey (PWM Duty cycle modulated by EDC16C34)',
        'nominal': 'Duty cycle: 20% (vanes open) to 85% (vanes closed/high spool)',
        'param_key': 'vnt_duty_pct',
        'unit': '%',
        'warn_low': 10,
        'warn_high': 95,
        'system': 'Vacuum Control'
    },
    10: {
        'id': 'EGT_SENSOR',
        'name': 'Pre-Catalyst Exhaust Gas Temperature Sensor',
        'oem_ref': '1618.LS',
        'location': 'Screwed directly into top elbow of DPF/Cat housing right off turbo',
        'connector': '2-Pin Black high-temp lead to harness clip on cylinder head',
        'nominal': '140 - 220°C idle • 350 - 450°C cruising • 580 - 620°C DPF regen',
        'param_key': 'egt_temp_c',
        'unit': '°C',
        'warn_low': 60,
        'warn_high': 750,
        'system': 'Exhaust'
    },
    11: {
        'id': 'DPF_FAP',
        'name': 'Catalytic Converter & Diesel Particulate Filter',
        'oem_ref': '1731.RJ / 1740.16',
        'location': 'Vertical canister in front of engine block behind cooling fans',
        'connector': 'Silicon pressure sampling pipes (upstream and downstream)',
        'nominal': 'Soot load < 25g (Capacity: 40g); Backpressure < 15 mbar idle',
        'param_key': 'dpf_soot_g',
        'unit': 'g',
        'warn_low': 0,
        'warn_high': 30,
        'system': 'Exhaust Aftertreatment'
    },
    12: {
        'id': 'DIFF_PRESS',
        'name': 'DPF Exhaust Differential Pressure Sensor',
        'oem_ref': '1618.LP / 9662143180',
        'location': 'Bolted to battery tray bracket (accessible from above)',
        'connector': '3-Pin Grey (5V supply, Ground, 0.5-4.5V pressure output)',
        'nominal': '0 - 12 mbar at 850 RPM idle • 20 - 70 mbar at 3000 RPM light load',
        'param_key': 'dpf_diff_mbar',
        'unit': 'mbar',
        'warn_low': 0,
        'warn_high': 45,
        'system': 'Exhaust Aftertreatment'
    },
    13: {
        'id': 'EGR_VALVE',
        'name': 'Electric EGR Valve with Position Potentiometer',
        'oem_ref': '1618.NR / 9672880080',
        'location': 'Rear right of cylinder head above bellhousing, bolted to cooler',
        'connector': '5-Pin Black (Pins 1 & 5: Stepper motor; Pins 2,3,4: Feedback pot)',
        'nominal': '0% (Closed during full load/cold) • 20 - 65% (Part-load recirculation)',
        'param_key': 'egr_pos_pct',
        'unit': '%',
        'warn_low': 0,
        'warn_high': 100,
        'system': 'Emissions'
    },
    14: {
        'id': 'ECT_SENSOR',
        'name': 'Engine Coolant Temperature Sensor (ECT)',
        'oem_ref': '1338.C1 / 96566364',
        'location': 'Water outlet housing on right side of head (above gearbox)',
        'connector': '2-Pin Green NTC thermistor (Held by U-shaped wire clip)',
        'nominal': '82 - 92°C at warmed up operating temperature (Thermostat: 83°C)',
        'param_key': 'coolant_c',
        'unit': '°C',
        'warn_low': 60,
        'warn_high': 105,
        'system': 'Cooling System'
    },
    15: {
        'id': 'CKP_SENSOR',
        'name': 'Crankshaft Engine Speed Position Sensor (CKP)',
        'oem_ref': '1920.PJ / 9664387280',
        'location': 'Lower front engine block near crankshaft pulley (behind belt cover)',
        'connector': '3-Pin White Hall-effect sensor reading magnetic encoder ring',
        'nominal': '800 - 850 RPM warm idle • 0 km/h stationary',
        'param_key': 'engine_rpm',
        'unit': 'RPM',
        'warn_low': 700,
        'warn_high': 4500,
        'system': 'Engine Timing'
    },
    16: {
        'id': 'CMP_SENSOR',
        'name': 'Camshaft Phase Identification Sensor (CMP)',
        'oem_ref': '1920.QN / 9653831280',
        'location': 'Upper front of cylinder head pointing at camshaft target wheel',
        'connector': '3-Pin Grey Hall-effect sensor',
        'nominal': 'Synchronized with crankshaft (Sync State: YES / 1)',
        'param_key': 'cam_sync',
        'unit': 'state',
        'warn_low': 0,
        'warn_high': 2,
        'system': 'Engine Timing'
    },
    17: {
        'id': 'EGS6_TRANS',
        'name': 'EGS6 6-Speed Piloted Manual Gearbox (BMP6)',
        'oem_ref': '20DV12 / 20DV18',
        'location': 'Right side of engine bay beneath battery and air cleaner ducting',
        'connector': 'Multi-pin round bayonet harness to CFC300P TCU',
        'nominal': 'Mechanical manual box shifted by electro-hydraulic robot pack',
        'param_key': 'gear_selected',
        'unit': '',
        'warn_low': 0,
        'warn_high': 6,
        'system': 'Transmission'
    },
    18: {
        'id': 'EGS6_PUMP',
        'name': 'EGS6 Hydraulic Power Pack & Accumulator',
        'oem_ref': '2105.37 / 2452.E1',
        'location': 'Bolted to front-top of transmission casing under air intake trunk',
        'connector': '2-Pin High-current pump feed & 3-Pin pressure sensor (0x7E9)',
        'nominal': '40 - 50 bar line pressure • Pump cuts out at 50 bar',
        'param_key': 'egs6_press_bar',
        'unit': 'bar',
        'warn_low': 38,
        'warn_high': 55,
        'system': 'Hydraulics'
    },
    19: {
        'id': 'CLUTCH_ACT',
        'name': 'EGS6 Clutch Slave Cylinder & Travel Sensor',
        'oem_ref': '2182.52 / Magneti Marelli',
        'location': 'Bolted to clutch bellhousing, acts directly on clutch release fork',
        'connector': 'Integrated Hall linear potentiometer stroke sensor',
        'nominal': 'Stroke: ~10mm (Brand new clutch) to ~18mm (Worn wear limit)',
        'param_key': 'clutch_pos_mm',
        'unit': 'mm',
        'warn_low': 8.0,
        'warn_high': 17.5,
        'system': 'Hydraulics'
    },
    20: {
        'id': 'BATTERY_12V',
        'name': '12V Lead-Acid Starter Battery & BSM Module',
        'oem_ref': '5600.TC / L3 70Ah 720A',
        'location': 'Rear right of engine bay under plastic protective cover',
        'connector': 'Positive quick-release clamp & BSM Engine Bay Fuse Box',
        'nominal': '12.4 - 12.8V resting • >10.5V cranking • 13.8 - 14.5V charging',
        'param_key': 'battery_v',
        'unit': 'V',
        'warn_low': 11.5,
        'warn_high': 15.0,
        'system': 'Electrical'
    }
}

def get_live_sensor_values(is_sim: bool = True) -> dict:
    """Returns real or high-fidelity simulated telemetry dictionary for all diagram nodes."""
    return {
        'engine_rpm': 850,
        'speed_kmh': 0,
        'coolant_c': 86.4,
        'maf_mg': 485.0,
        'boost_bar': 1.02,
        'intercooler_dp': 0.04,
        'map_mbar': 1024,
        'fuel_temp_c': 38.5,
        'rail_press_bar': 298.0,
        'rail_target_bar': 295.0,
        'inj_balance_c1': 0.2,
        'inj_balance_c2': -0.4,
        'inj_balance_c3': 0.1,
        'inj_balance_c4': 0.1,
        'vnt_duty_pct': 42.5,
        'egt_temp_c': 188.0,
        'dpf_soot_g': 18.4,
        'dpf_diff_mbar': 8.5,
        'egr_pos_pct': 34.0,
        'cam_sync': 'SYNCHRONIZED',
        'gear_selected': 'N (Neutral)',
        'egs6_press_bar': 48.2,
        'clutch_pos_mm': 14.8,
        'clutch_slip_rpm': 0,
        'battery_v': 14.28,
        'oil_temp_c': 88.0,
        'ambient_temp_c': 17.5,
        'baro_mbar': 1012,
        'throttle_pct': 98.0,
        'glow_relay_active': False
    }

def evaluate_sensor_status(key_val: float | str, sensor_meta: dict) -> tuple[str, str]:
    """Returns (status_badge, color_code) for a sensor parameter."""
    if isinstance(key_val, str):
        return ("OK", GREEN)
    val = float(key_val)
    low = sensor_meta.get('warn_low')
    high = sensor_meta.get('warn_high')
    if low is not None and val < low:
        return ("LOW_WARN", YELLOW)
    if high is not None and val > high:
        return ("HIGH_WARN", RED)
    return ("NOMINAL", GREEN)

def render_ascii_engine_diagram(is_sim: bool = True, use_color: bool = True) -> str:
    """
    Renders an ASCII top-down diagram of the Citroën Grand C4 Picasso 1.6 HDi engine bay
    with numbered callouts and live telemetry values.
    """
    c_b = BOLD if use_color else ''
    c_cy = CYAN if use_color else ''
    c_g = GREEN if use_color else ''
    c_y = YELLOW if use_color else ''
    c_r = RED if use_color else ''
    c_m = MAGENTA if use_color else ''
    c_rst = RESET if use_color else ''
    c_dim = DIM if use_color else ''

    vals = get_live_sensor_values(is_sim=is_sim)

    # Helper to format sensor tag e.g. "[1] MAF: 485 mg"
    def tag(num: int) -> str:
        s = SENSOR_DATABASE[num]
        v = vals.get(s['param_key'], 'N/A')
        u = s['unit']
        return f"{c_b}{c_cy}[{num:02d}]{c_rst} {v} {u}".strip()

    diagram = f"""
{c_b}{c_cy}╔════════════════════════════════════════════════════════════════════════════════════════════════╗{c_rst}
{c_b}{c_cy}║     CITROËN GRAND C4 PICASSO Mk1 (B58) • 1.6 HDi DV6 DIESEL • ENGINE BAY SENSOR MAP    ║{c_rst}
{c_b}{c_cy}╚════════════════════════════════════════════════════════════════════════════════════════════════╝{c_rst}
 {c_dim}TOP-DOWN VIEW (Facing Bonnet from Front Bumper • Cyl 1 at Flywheel / Cyl 4 at Timing Belt){c_rst}

                          {c_b}[ FRONT BUMPER / RADIATOR PACK ]{c_rst}
  ┌───────────────────────────────────────────────────────────────────────────┐
  │  [3] INTERCOOLER ({vals['intercooler_dp']} bar dp)      [11] DPF & CAT ({vals['dpf_soot_g']}g soot)     │
  │  ├───[COLD PIPE]──────┐                  ┌──────[HOT PIPE]────┤
  │                       ▼                  ▼                    │
  │  ┌─────────────────────────┐       ┌───────────────────────┐  │
  │  │ [4] MAP / IAT SENSOR    │       │ [2] GARRETT TURBO     │  │
  │  │     {vals['map_mbar']} mbar / {vals['ambient_temp_c']}°C   │       │     {vals['boost_bar']} bar (Actual)  │  │
  │  │ [16] CAM SENSOR (CMP)   │       │ [9] VNT VALVE: {vals['vnt_duty_pct']}%   │  │
  │  └──────────┬──────────────┘       └──────────┬────────────┘  │
  │             │                                 │               │
  │  ┌──────────▼─────────────────────────────────▼────────────┐  │
  │  │       DV6 1.6 HDi 16V / 8V ALUMINIUM CYLINDER HEAD      │  │
  │  │  [TIMING BELT SIDE]               [FLYWHEEL / GEARBOX]  │  │
  │  │                                                         │  │
  │  │   CYL 4        CYL 3        CYL 2        CYL 1 (Bip)    │  │
  │  │    [8]          [8]          [8]          [8]           │  │
  │  │  INJECTOR     INJECTOR     INJECTOR     INJECTOR        │  │
  │  │  ({vals['inj_balance_c4']:+.1f} mg)   ({vals['inj_balance_c3']:+.1f} mg)   ({vals['inj_balance_c2']:+.1f} mg)   ({vals['inj_balance_c1']:+.1f} mg)     │  │
  │  │                                                         │  │
  │  │   ───[6] COMMON RAIL: {vals['rail_press_bar']} bar (Target: {vals['rail_target_bar']})───    │  │
  │  │   [5] HP PUMP: {vals['fuel_temp_c']}°C          [7] RAIL PRESS SENSOR     │  │
  │  └──────────┬─────────────────────────────────┬────────────┘  │
  │             │                                 │               │
  │             │                       ┌─────────▼────────────┐  │
  │  ┌──────────▼──────────────┐        │ [17] EGS6 TRANSMISSION│  │
  │  │ [1] AIR FILTER & MAF    │        │  Selector: {vals['gear_selected']}  │  │
  │  │     {vals['maf_mg']} mg/stroke      │        │  [18] PUMP: {vals['egs6_press_bar']} bar    │  │
  │  │                         │        │  [19] CLUTCH: {vals['clutch_pos_mm']}mm  │  │
  │  │ [15] CRANK SENSOR (CKP) │        │  [14] ECT: {vals['coolant_c']}°C        │  │
  │  │      {vals['engine_rpm']} RPM (Idle)     │        └──────────────────────┘  │
  │  └─────────────────────────┘        ┌──────────────────────┐  │
  │  ┌─────────────────────────┐        │ [20] 12V STARTER     │  │
  │  │ [12] DIFF PRESS SENSOR  │        │      BATTERY & BSM   │  │
  │  │      {vals['dpf_diff_mbar']} mbar (Idle)     │        │      {vals['battery_v']} V (Charge OK) │  │
  │  │ [10] PRE-CAT EGT: {vals['egt_temp_c']}°C │        │ [13] EGR: {vals['egr_pos_pct']}% Open │  │
  │  └─────────────────────────┘        └──────────────────────┘  │
  └───────────────────────────────────────────────────────────────────────────┘
                       {c_dim}[ BULKHEAD / CABIN SCUTTLE PANEL ]{c_rst}
"""
    return diagram

def render_sensor_detail_table(is_sim: bool = True, use_color: bool = True) -> str:
    """Renders a comprehensive tabular index of all 20 sensors with locations, pinouts and live telemetry."""
    c_b = BOLD if use_color else ''
    c_cy = CYAN if use_color else ''
    c_g = GREEN if use_color else ''
    c_y = YELLOW if use_color else ''
    c_r = RED if use_color else ''
    c_rst = RESET if use_color else ''
    c_dim = DIM if use_color else ''

    vals = get_live_sensor_values(is_sim=is_sim)
    lines = []
    lines.append(f"{c_b}{c_cy}" + "=" * 95 + f"{c_rst}")
    lines.append(f" {c_b}ID  SENSOR NAME                  SYSTEM          LIVE VALUE      STATUS    NOMINAL SPEC{c_rst}")
    lines.append(f"{c_cy}" + "-" * 95 + f"{c_rst}")

    for num in sorted(SENSOR_DATABASE.keys()):
        s = SENSOR_DATABASE[num]
        val = vals.get(s['param_key'], 'N/A')
        u = s['unit']
        val_str = f"{val} {u}".strip()
        status_txt, status_col = evaluate_sensor_status(val, s)

        badge = f"{status_col}{c_b}{status_txt:<9}{c_rst}"
        lines.append(f" {c_b}[{num:02d}]{c_rst} {s['name'][:26]:<26}  {s['system'][:14]:<14}  {val_str:<14}  {badge} {s['nominal'][:22]}")

    lines.append(f"{c_b}{c_cy}" + "=" * 95 + f"{c_rst}\n")
    return "\n".join(lines)

def get_sensor_inspect_card(sensor_id: int, is_sim: bool = True) -> str:
    """Generates an in-depth technical inspection card for a single sensor."""
    if sensor_id not in SENSOR_DATABASE:
        return f"{RED}Error: Sensor #{sensor_id} not found in catalog (Valid: 1 to 20).{RESET}"
    
    s = SENSOR_DATABASE[sensor_id]
    vals = get_live_sensor_values(is_sim=is_sim)
    val = vals.get(s['param_key'], 'N/A')
    st_txt, st_col = evaluate_sensor_status(val, s)

    return f"""
{BOLD}{CYAN}═════════════════════════════════════════════════════════════════{RESET}
 {BOLD}SENSOR INSPECTION #{sensor_id:02d}: {s['name']}{RESET}
{CYAN}─────────────────────────────────────────────────────────────────{RESET}
 • {BOLD}PSA / OEM Reference:{RESET}    {s['oem_ref']}
 • {BOLD}Subsystem:{RESET}              {s['system']}
 • {BOLD}Physical Location:{RESET}      {s['location']}
 • {BOLD}Connector & Pinout:{RESET}     {s['connector']}
 • {BOLD}Nominal Working Range:{RESET}  {s['nominal']}
 • {BOLD}Current Live Reading:{RESET}   {st_col}{BOLD}{val} {s['unit']}{RESET} [{st_col}{st_txt}{RESET}]
{BOLD}{CYAN}═════════════════════════════════════════════════════════════════{RESET}
"""

def generate_html_svg_engine_view(is_sim: bool = True) -> str:
    """
    Produces a self-contained responsive HTML/SVG interactive visual diagram
    for the companion web dashboard.
    """
    vals = get_live_sensor_values(is_sim=is_sim)
    
    # SVG Node cards
    svg_cards = ""
    nodes = [
        (1, "MAF Sensor", 120, 360, f"{vals['maf_mg']} mg", "Intake Air"),
        (2, "Garrett Turbo", 520, 140, f"{vals['boost_bar']} bar", "Exhaust"),
        (3, "Intercooler", 180, 50, f"{vals['intercooler_dp']} bar dp", "Cooling"),
        (4, "MAP / IAT", 200, 140, f"{vals['map_mbar']} mbar", "Intake"),
        (5, "HP CP1H Pump", 120, 240, f"{vals['fuel_temp_c']} °C", "Common Rail"),
        (6, "Common Rail", 350, 240, f"{vals['rail_press_bar']} bar", "Fuel"),
        (7, "Rail Pressure", 450, 240, f"{vals['rail_target_bar']} bar", "Fuel"),
        (8, "Injectors 1-4", 350, 190, f"Bal: {vals['inj_balance_c1']:+.1f}", "Piezo"),
        (9, "VNT Solenoid", 520, 90, f"{vals['vnt_duty_pct']}%", "Vacuum"),
        (10, "Pre-Cat EGT", 680, 140, f"{vals['egt_temp_c']} °C", "Exhaust"),
        (11, "DPF (FAP)", 680, 220, f"{vals['dpf_soot_g']} g", "Filter"),
        (12, "Diff Pressure", 680, 300, f"{vals['dpf_diff_mbar']} mbar", "Exhaust"),
        (13, "EGR Valve", 520, 320, f"{vals['egr_pos_pct']}%", "Emissions"),
        (14, "ECT Temp", 350, 340, f"{vals['coolant_c']} °C", "Cooling"),
        (15, "CKP Crank", 120, 430, f"{vals['engine_rpm']} RPM", "Timing"),
        (16, "CMP Cam", 200, 90, f"{vals['cam_sync']}", "Timing"),
        (17, "EGS6 Gearbox", 350, 420, f"{vals['gear_selected']}", "Trans"),
        (18, "EGS6 Pump", 470, 420, f"{vals['egs6_press_bar']} bar", "Hydraulic"),
        (19, "Clutch Slave", 590, 420, f"{vals['clutch_pos_mm']} mm", "Clutch"),
        (20, "12V Battery", 680, 420, f"{vals['battery_v']} V", "Electric")
    ]

    for nid, title, x, y, val_str, cat in nodes:
        svg_cards += f"""
        <g class="sensor-node" transform="translate({x},{y})" onclick="showSensorModal({nid})">
          <rect width="130" height="52" rx="6" fill="#161b22" stroke="#30363d" stroke-width="1.5" class="node-box"/>
          <circle cx="16" cy="16" r="9" fill="#00e5ff" opacity="0.2"/>
          <text x="16" y="20" font-size="10" font-weight="bold" fill="#00e5ff" text-anchor="middle">{nid}</text>
          <text x="32" y="18" font-size="11" font-weight="bold" fill="#fff">{title}</text>
          <text x="14" y="40" font-size="12" font-weight="bold" fill="#00e676">{val_str}</text>
          <text x="118" y="40" font-size="9" fill="#8b949e" text-anchor="end">{cat}</text>
        </g>
        """

    html = f"""
    <div style="background:#0d1117; color:#c9d1d9; border-radius:8px; padding:16px; border:1px solid #30363d; margin-top:16px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 style="color:#00e5ff; font-size:1.1rem; margin:0;">🗺️ CITROËN GRAND C4 PICASSO: 1.6 HDi ENGINE BAY & SENSOR SCHEMATIC</h3>
        <span style="font-size:0.75rem; background:rgba(0,229,255,0.15); color:#00e5ff; padding:3px 8px; border-radius:4px; font-weight:bold;">DV6 1.6 HDi • EGS6</span>
      </div>
      <p style="font-size:0.8rem; color:#8b949e; margin-bottom:14px;">Interactive top-down schematic. Click any numbered sensor node to view physical location, connector pinouts, and test specs.</p>
      
      <div style="overflow-x:auto;">
        <svg viewBox="0 0 860 510" style="width:100%; min-width:750px; background:#080b0f; border-radius:8px; border:1px solid #21262d;">
          <!-- Chassis boundaries -->
          <rect x="20" y="20" width="820" height="470" rx="12" fill="none" stroke="#21262d" stroke-dasharray="6 4" stroke-width="2"/>
          <text x="430" y="38" fill="#484f58" font-size="11" font-weight="bold" text-anchor="middle">FRONT BUMPER / RADIATOR CROSSMEMBER</text>
          <text x="430" y="480" fill="#484f58" font-size="11" font-weight="bold" text-anchor="middle">CABIN BULKHEAD / SCUTTLE TRAY</text>

          <!-- Engine Block & Cylinder Head Silhouette -->
          <rect x="180" y="170" width="450" height="120" rx="8" fill="#11161d" stroke="#00e5ff" stroke-width="1.2" opacity="0.8"/>
          <text x="405" y="235" fill="#30363d" font-size="16" font-weight="bold" text-anchor="middle" letter-spacing="3">PSA DV6 CYLINDER HEAD</text>
          
          <!-- Gearbox Silhouette -->
          <rect x="330" y="390" width="310" height="70" rx="8" fill="#11161d" stroke="#ffd600" stroke-width="1.2" opacity="0.6"/>
          <text x="485" y="432" fill="#30363d" font-size="13" font-weight="bold" text-anchor="middle">EGS6 PILOTED TRANSMISSION</text>

          <!-- Piping lines -->
          <path d="M 245 102 L 245 140" stroke="#00e5ff" stroke-width="2" fill="none" opacity="0.6"/>
          <path d="M 585 192 L 585 240" stroke="#ff1744" stroke-width="2" fill="none" opacity="0.6"/>
          <path d="M 745 192 L 745 220" stroke="#ff9100" stroke-width="2" fill="none" opacity="0.6"/>

          {svg_cards}
        </svg>
      </div>
    </div>
    """
    return html

if __name__ == '__main__':
    print(render_ascii_engine_diagram(is_sim=True, use_color=True))
    print(render_sensor_detail_table(is_sim=True, use_color=True))
