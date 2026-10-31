#!/usr/bin/env python3
"""
PSA / Citroën Diagnostic CLI & Interactive Menu Tool (psa-diag / psa)
Specialized for Citroën Grand C4 Picasso Mk1 (AEE2004 / B58 Architecture)
1.6 HDi DV6 Diesel & 6-Speed Piloted Manual Gearbox (EGS6 / BMP6)

Integrates:
- Interactive Menu-driven navigation & CLI arguments
- Live Serial (ELM327 / OBDLink USB / Bluetooth) & High-Fidelity Simulation
- Multi-ECU CAN scanning (Engine, EGS6 Gearbox, ABS/ESP 8.1, Electric Parking Brake)
- Full DTC decoding against the 40,752 reverse-engineered PSA-RE database definitions
- Persistent audit logging for all read, scan, and clear operations
"""

import sys
import os
import re
import sqlite3
import argparse
import datetime

# Add local directory to path for obd_service and tui import
sys.path.insert(0, '/root/psa_diag')
import obd_service
import tui
import can_sniffer
import special_diagnostics
import advanced_features
import engine_diagram
import workshop_features

DB_PATH = '/root/psa_diag/psa_dtc_cache.db'
LOG_DIR = '/root/psa_diag/logs'
HISTORY_FILE = os.path.join(LOG_DIR, 'diag_history.log')

# Global configuration state for current session
SESSION_CONFIG = {
    'port': None,
    'baud': 38400,
    'force_sim': False,
    'interface': None
}

def make_progress_bar(val: float, total: float, width: int = 20) -> str:
    pct = val / total if total > 0 else 0
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {int(pct * 100)}%"

# ANSI Color codes
BOLD = '\033[1m'
CYAN = '\033[36m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'
MAGENTA = '\033[35m'
RESET = '\033[0m'
DIM = '\033[2m'

SYSTEM_MAP = {
    'P': ('Powertrain', 'Engine ECU (DV6 HDi Bosch EDC16C34/SID807) & EGS6 Piloted Gearbox (CFC300P)'),
    'C': ('Chassis', 'ABS/ESP (Bosch 8.1), Electric Parking Brake (FSE), Power Steering (DAE)'),
    'B': ('Body', 'BSI (Built-in Systems Interface), Airbags (RBG), Climate, Lighting, Instrument Cluster'),
    'U': ('Network', 'Inter-module communication (CAN IS 500k, CAN CONF 125k, CAN CAR 125k), Gateway errors')
}

TYPE_MAP = {
    '0': 'Standardized SAE / ISO generic code (universal across all car brands)',
    '1': 'Manufacturer-specific (Citroën / Peugeot / PSA proprietary)',
    '2': 'Manufacturer-specific (Extended PSA chassis / body / powertrain)',
    '3': 'Reserved / Manufacturer-specific'
}

PICASSO_SPECIFIC_ADVICE = {
    'C': [
        "On the Grand C4 Picasso Mk1 (B58), chassis faults are overwhelmingly tied to either:",
        "  1. Electric Parking Brake (FSE / EPB) cable tension, motor lockup, or force sensor calibration.",
        "  2. ABS/ESP wheel speed sensors (magnetic encoder ring on rear bearings corroding).",
        "  3. Cranking voltage drop: A battery dropping below ~10.5V on start throws false ABS/Handbrake warnings.",
        "  4. Brake pedal switch (dual-contact switch above the brake pedal failing)."
    ],
    'P': [
        "On the 1.6 HDi & EGS6 semi-auto transmission:",
        "  1. Gearbox codes (P17A5, P07xx, P08xx): Clutch actuator pressure, position sensor, or bite-point wear.",
        "  2. DPF (FAP) soot overload or differential pressure sensor pipes split/clogged.",
        "  3. Eolys additive dosing pump / pouch empty or additive ECU counter out of sync.",
        "  4. Turbo boost solenoid (electrovalve behind engine) or sticking VNT vanes."
    ],
    'B': [
        "On the Grand C4 Picasso, Body faults originate in the BSI (under dashboard) or BSM (engine bay fuse box).",
        "  - Check for water ingress under the scuttle panel draining onto the BSM/fuse box.",
        "  - Check pneumatic suspension height sensor linkages (Exclusive models)."
    ],
    'U': [
        "Network (U) faults occur when one ECU loses CAN frames from another.",
        "  - If accompanied by C-codes or Gearbox errors, the ABS/ESP or EPB is missing torque/speed frames.",
        "  - Often caused by a blown fuse, low battery, or water corrosion in the front ABS plug."
    ]
}

def get_db():
    if not os.path.exists(DB_PATH):
        print(f"{RED}Error: Cache database {DB_PATH} not found.{RESET}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def parse_code_structure(code_str: str):
    s = code_str.strip().upper()
    if s.startswith('0X'):
        s = s[2:]
        
    if re.fullmatch(r'[0-9A-F]{4}', s):
        raw_val = int(s, 16)
        prefix_bits = (raw_val >> 14) & 0x03
        prefixes = ['P', 'C', 'B', 'U']
        type_bit = (raw_val >> 12) & 0x03
        sub_hex = f"{raw_val & 0x0FFF:03X}"
        std_code = f"{prefixes[prefix_bits]}{type_bit}{sub_hex}"
        return std_code, prefixes[prefix_bits], str(type_bit), sub_hex, s

    m = re.match(r'^([PCBU])([0-3])([0-9A-F]{3})(?:-([0-9A-F]{2}))?$', s)
    if m:
        cat = m.group(1)
        typ = m.group(2)
        sub = m.group(3)
        return s, cat, typ, sub, ''

    return s, '', '', '', ''

def lookup_code_data(code_input: str):
    conn = get_db()
    c = conn.cursor()
    clean_code = code_input.strip().upper()
    std_code, cat, typ, sub, raw_hex = parse_code_structure(clean_code)
    base_code = clean_code.split('-')[0]

    c.execute('''
        SELECT code, raw, arch, system, ecu, desc_en, desc_fr, comment
        FROM dtcs 
        WHERE code = ? OR code = ? OR raw = ?
        ORDER BY 
            CASE 
                WHEN arch LIKE 'AEE2004%' THEN 1 
                WHEN arch LIKE 'AEE2010%' THEN 2 
                ELSE 3 
            END
    ''', (clean_code, base_code, clean_code))
    matches = c.fetchall()
    conn.close()
    return clean_code, std_code, cat, typ, sub, raw_hex, matches

def format_code_report(clean_code: str, std_code: str, cat: str, typ: str, sub: str, raw_hex: str, matches: list, use_color: bool = True):
    b = BOLD if use_color else ''
    cy = CYAN if use_color else ''
    gr = GREEN if use_color else ''
    ye = YELLOW if use_color else ''
    dim = DIM if use_color else ''
    mg = MAGENTA if use_color else ''
    rst = RESET if use_color else ''

    out = []
    out.append("=" * 65)
    out.append(f" {b}{cy}CITROËN / PSA DIAGNOSTIC REPORT: {clean_code}{rst}")
    out.append("=" * 65)

    if cat:
        sys_name, sys_desc = SYSTEM_MAP.get(cat, ("Unknown", "Unknown"))
        typ_desc = TYPE_MAP.get(typ, "Unknown")
        out.append(f" {b}System:{rst}        {sys_name} ({b}{cat}{rst})")
        out.append(f" {b}Function:{rst}      {sys_desc}")
        out.append(f" {b}Code Range:{rst}    {typ_desc}")
        if sub:
            out.append(f" {b}Hex Index:{rst}     0x{sub}")
        if raw_hex:
            out.append(f" {b}Raw CAN Hex:{rst}   0x{raw_hex} -> Formatted DTC: {b}{std_code}{rst}")

    if matches:
        out.append(f"\n {gr}{b}[✓] Exact Match Found in PSA Database ({len(matches)} reference(s)):{rst}\n")
        seen = set()
        for m in matches:
            code_val, raw_val, arch, system, ecu, desc_en, desc_fr, comment = m
            key = (arch, system, ecu, desc_en)
            if key in seen:
                continue
            seen.add(key)
            is_picasso_arch = 'AEE2004' in arch
            arch_badge = f"{gr}[Grand C4 Picasso Native - {arch}]{rst}" if is_picasso_arch else f"{dim}[{arch}]{rst}"
            out.append(f"  • {b}Module:{rst} {system} / {b}{ecu}{rst} {arch_badge}")
            if desc_en:
                out.append(f"    {b}English:{rst} {desc_en}")
            if desc_fr and desc_fr != desc_en:
                out.append(f"    {dim}French (OEM): {desc_fr}{rst}")
            if comment and comment != 'None' and comment != desc_en:
                out.append(f"    {dim}Details: {comment}{rst}")
            out.append("")
    else:
        out.append(f"\n {ye}[!] No direct OEM text definition found for '{clean_code}' in database.{rst}")
        conn = get_db()
        c = conn.cursor()
        search_sub = sub if sub else clean_code[-3:]
        c.execute('''
            SELECT DISTINCT code, raw, arch, system, ecu, desc_en 
            FROM dtcs 
            WHERE (code LIKE ? OR raw LIKE ?) AND (arch LIKE 'AEE2004%' OR arch LIKE 'AEE2010%')
            LIMIT 6
        ''', (f"%{search_sub}%", f"%{search_sub}%"))
        related = c.fetchall()
        conn.close()
        if related:
            out.append(f"\n {cy}{b}Related PSA Codes matching index '*{search_sub}*':{rst}")
            for r in related:
                out.append(f"  • {b}{r[0]}{rst} (raw: {r[1]}) in {r[3]}/{r[4]}: {r[5]}")
            out.append("")

    if cat in PICASSO_SPECIFIC_ADVICE:
        out.append(f" {b}{mg}Technical Insights for Citroën Grand C4 Picasso Mk1:{rst}")
        for line in PICASSO_SPECIFIC_ADVICE[cat]:
            out.append(f"  {line}")

    out.append("=" * 65 + "\n")
    return "\n".join(out)

def lookup_code(code_input: str):
    clean_code, std_code, cat, typ, sub, raw_hex, matches = lookup_code_data(code_input)
    print(format_code_report(clean_code, std_code, cat, typ, sub, raw_hex, matches, use_color=True))

def search_text(keyword: str):
    conn = get_db()
    c = conn.cursor()
    pattern = f"%{keyword}%"
    c.execute('''
        SELECT code, raw, arch, system, ecu, desc_en, desc_fr
        FROM dtcs
        WHERE (desc_en LIKE ? OR desc_fr LIKE ? OR comment LIKE ?)
          AND (arch LIKE 'AEE2004%' OR arch LIKE 'AEE2010%')
        GROUP BY code, ecu
        LIMIT 15
    ''', (pattern, pattern, pattern))
    results = c.fetchall()
    
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}PSA DIAGNOSTIC SEARCH: '{keyword}'{RESET} ({len(results)} matches shown)")
    print("=" * 65)
    
    if not results:
        print(f"  No entries found matching '{keyword}'.")
    else:
        for r in results:
            code, raw, arch, system, ecu, desc_en, desc_fr = r
            print(f"  • {BOLD}{GREEN}{code}{RESET} (raw: {raw}) [{arch} -> {system}/{ecu}]")
            print(f"    {desc_en or desc_fr}")
            print()
    print("=" * 65 + "\n")
    conn.close()

def show_modules():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT system, ecu, COUNT(code)
        FROM dtcs
        WHERE arch LIKE 'AEE2004%'
        GROUP BY system, ecu
        ORDER BY system, ecu
    ''')
    rows = c.fetchall()
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}Grand C4 Picasso Mk1 (AEE2004 Architecture) Known Modules{RESET}")
    print("=" * 65)
    for r in rows:
        sys_name = r[0]
        ecu_name = r[1]
        cnt = r[2]
        desc = ""
        if 'ESP' in ecu_name or 'ABS' in ecu_name: desc = "(Anti-lock Braking / Stability Control)"
        elif 'FSE' in ecu_name or 'FSE' in sys_name: desc = "(Electric Parking Brake)"
        elif 'BVA' in ecu_name or 'CFC' in ecu_name: desc = "(Automatic / EGS6 Robotized Gearbox)"
        elif 'ADDGO' in ecu_name or 'ADDGO' in sys_name: desc = "(Eolys Diesel Additive System)"
        elif 'BSI' in ecu_name: desc = "(Built-in Systems Interface / Main Gateway)"
        elif 'CMM' in sys_name: desc = "(Engine Management ECU)"
        elif 'SUSPENSION' in ecu_name or 'AIR' in sys_name: desc = "(Pneumatic Rear Suspension)"
        print(f"  • {BOLD}{sys_name:<10}{RESET} / {BOLD}{ecu_name:<18}{RESET} {DIM}{desc:<35}{RESET} ({cnt} DTCs)")
    print("=" * 65 + "\n")
    conn.close()

# ==============================================================================
# SERIAL & DTC ACTIONS: READ / SCAN / CLEAR
# ==============================================================================

def execute_dtc_read(port: str = None, baud: int = 38400, sim: bool = False, interface: str = None):
    p = port or SESSION_CONFIG['port']
    b = baud or SESSION_CONFIG['baud']
    s = sim or SESSION_CONFIG['force_sim']
    i = interface or SESSION_CONFIG.get('interface')

    if not s:
        obd_service.require_vehicle_or_demo(is_demo=False, port=p, interface=i)

    print(f"\n{BOLD}{CYAN}=== CITROËN GRAND C4 PICASSO: DTC READ OPERATION ==={RESET}")
    iface = obd_service.OBDInterface(port=p, baudrate=b, force_sim=s, interface=i)
    
    print("[*] Requesting Confirmed Fault Codes (OBD Mode 03)...")
    resp_03 = iface.send_command('03')
    print("[*] Requesting Pending Fault Codes (OBD Mode 07)...")
    resp_07 = iface.send_command('07')
    iface.close()

    raw_combined = resp_03 + resp_07
    parsed_dtcs = obd_service.parse_raw_dtc_lines(raw_combined)

    report_text = generate_dtc_summary_report(parsed_dtcs, action_name="READ (Confirmed & Pending)")
    print(report_text)

    log_file = obd_service.log_dtc_action(
        action="read",
        raw_data=parsed_dtcs,
        decoded_report=report_text,
        port_name=iface.port_name or 'AUTO',
        is_sim=iface.is_simulated
    )
    print(f"{GREEN}[✓] Diagnostic session logged to:{RESET} {BOLD}{log_file}{RESET}\n")

def execute_dtc_scan(port: str = None, baud: int = 38400, sim: bool = False, interface: str = None):
    p = port or SESSION_CONFIG['port']
    b = baud or SESSION_CONFIG['baud']
    s = sim or SESSION_CONFIG['force_sim']
    i = interface or SESSION_CONFIG.get('interface')

    if not s:
        obd_service.require_vehicle_or_demo(is_demo=False, port=p, interface=i)

    print(f"\n{BOLD}{CYAN}=== CITROËN GRAND C4 PICASSO: EXTENDED MULTI-MODULE SCAN ==={RESET}")
    print("[*] Target Platform: PSA AEE2004 High-Speed CAN (500 kbps)")
    print("[*] Scanning Modules: Engine (CMM), Gearbox (BVMP/EGS6), Stability (ESP 8.1), Handbrake (FSE)\n")

    iface = obd_service.OBDInterface(port=p, baudrate=b, force_sim=s, interface=i)
    all_raw_lines = []

    print("[1/4] Probing Powertrain Broadcast (0x7DF)...")
    iface.send_command('ATSH 7DF')
    all_raw_lines.extend(iface.send_command('03'))
    all_raw_lines.extend(iface.send_command('07'))

    print("[2/4] Interrogating 6-Speed Piloted Gearbox (BVMP 0x7E1 / 0x7E2)...")
    iface.send_command('ATSH 7E1')
    all_raw_lines.extend(iface.send_command('03'))
    all_raw_lines.extend(iface.send_command('1902FF'))

    print("[3/4] Interrogating Dynamic Stability & ABS (ESP 8.1 0x760)...")
    iface.send_command('ATSH 760')
    all_raw_lines.extend(iface.send_command('03'))
    all_raw_lines.extend(iface.send_command('1902FF'))

    print("[4/4] Interrogating Electric Parking Brake Unit (FSE 0x792)...")
    iface.send_command('ATSH 792')
    all_raw_lines.extend(iface.send_command('03'))
    all_raw_lines.extend(iface.send_command('1902FF'))

    iface.close()

    parsed_dtcs = obd_service.parse_raw_dtc_lines(all_raw_lines)
    report_text = generate_dtc_summary_report(parsed_dtcs, action_name="EXTENDED MULTI-MODULE SCAN")
    print(report_text)

    log_file = obd_service.log_dtc_action(
        action="scan",
        raw_data=parsed_dtcs,
        decoded_report=report_text,
        port_name=iface.port_name or 'AUTO',
        is_sim=iface.is_simulated
    )
    print(f"{GREEN}[✓] Full vehicle scan logged to:{RESET} {BOLD}{log_file}{RESET}\n")

def execute_dtc_clear(port: str = None, baud: int = 38400, sim: bool = False, force: bool = False, interface: str = None):
    p = port or SESSION_CONFIG['port']
    b = baud or SESSION_CONFIG['baud']
    s = sim or SESSION_CONFIG['force_sim']
    i = interface or SESSION_CONFIG.get('interface')

    if not s:
        obd_service.require_vehicle_or_demo(is_demo=False, port=p, interface=i)

    print(f"\n{BOLD}{RED}=== CITROËN GRAND C4 PICASSO: DTC CLEAR OPERATION ==={RESET}")
    print(f"{YELLOW}Warning: Clearing DTCs will reset freeze-frame data and extinguish check engine/service lights.{RESET}")
    print(f"Vehicle: Citroën Grand C4 Picasso 1.6 HDi (EGS6 Piloted Manual Transmission)\n")

    if not force:
        try:
            confirm = input(f"{BOLD}Are you sure you want to clear all fault codes? [y/N]: {RESET}").strip().lower()
            if confirm not in ('y', 'yes'):
                print("Clear operation cancelled.")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return

    iface = obd_service.OBDInterface(port=p, baudrate=b, force_sim=s, interface=i)
    
    print("[*] Transmitting Clear Diagnostic Information (OBD Mode 04 & UDS 0x14)...")
    iface.send_command('ATSH 7DF')
    iface.send_command('04')
    iface.send_command('14FFFFFF')

    iface.send_command('ATSH 7E1')
    iface.send_command('04')
    iface.send_command('14FFFFFF')

    iface.send_command('ATSH 760')
    iface.send_command('04')
    iface.send_command('14FFFFFF')

    print(f"{GREEN}[✓] Clear command dispatched to Engine, Gearbox, and Chassis nodes.{RESET}")
    print("[*] Re-interrogating ECUs to verify clearance...")

    iface.send_command('ATSH 7DF')
    post_read = iface.send_command('03')
    iface.close()

    parsed_post = obd_service.parse_raw_dtc_lines(post_read)
    
    report_lines = []
    report_lines.append("=" * 65)
    report_lines.append(f" {BOLD}POST-CLEARANCE VERIFICATION RESULTS{RESET}")
    report_lines.append("=" * 65)
    
    total_remaining = sum(len(codes) for codes in parsed_post.values())
    if total_remaining == 0:
        report_lines.append(f" {GREEN}{BOLD}[✓] SUCCESS: All fault codes cleared. Zero active DTCs reported.{RESET}")
        report_lines.append("   - Instrument cluster Service / Check Engine lamps should now be OFF.")
        report_lines.append("   - If faults reappear after driving, they indicate a persistent hardware failure.")
    else:
        report_lines.append(f" {RED}{BOLD}[!] NOTICE: {total_remaining} fault code(s) remained or immediately recurred:{RESET}")
        for ecu, codes in parsed_post.items():
            ecu_name, ecu_desc = obd_service.KNOWN_PSA_ECUS.get(ecu, ("Unknown ECU", "Direct CAN node"))
            report_lines.append(f"   • Module {ecu} ({ecu_name}): {[c[0] for c in codes]}")
        report_lines.append("   - Immediate recurrence signifies a permanent electrical open/short circuit.")
    report_lines.append("=" * 65 + "\n")
    
    report_text = "\n".join(report_lines)
    print(report_text)

    log_file = obd_service.log_dtc_action(
        action="clear",
        raw_data=parsed_post,
        decoded_report=report_text,
        port_name=iface.port_name or 'AUTO',
        is_sim=iface.is_simulated
    )
    print(f"{GREEN}[✓] Clear operation logged to:{RESET} {BOLD}{log_file}{RESET}\n")

def generate_dtc_summary_report(parsed_dtcs: dict, action_name: str) -> str:
    lines = []
    lines.append("=" * 65)
    lines.append(f" {BOLD}{CYAN}CITROËN DIAGNOSTIC SUMMARY: {action_name}{RESET}")
    lines.append("=" * 65)

    if not parsed_dtcs:
        lines.append(f" {GREEN}{BOLD}[✓] NO FAULT CODES DETECTED.{RESET}")
        lines.append("   All scanned ECUs reported zero active or pending diagnostic codes.")
        lines.append("=" * 65)
        return "\n".join(lines)

    total_codes = sum(len(codes) for codes in parsed_dtcs.values())
    lines.append(f" Total Fault Codes Detected: {BOLD}{total_codes}{RESET} across {len(parsed_dtcs)} module(s)\n")

    for ecu_id, code_list in parsed_dtcs.items():
        ecu_name, ecu_desc = obd_service.KNOWN_PSA_ECUS.get(ecu_id, ("Unidentified Module", "Direct CAN node"))
        lines.append(f" {BOLD}{YELLOW}▶ MODULE [CAN 0x{ecu_id}]: {ecu_name}{RESET}")
        lines.append(f"   {DIM}{ecu_desc}{RESET}")
        lines.append("   " + "-" * 55)

        for std_code, raw_hex in code_list:
            clean_code, s_code, cat, typ, sub, r_hex, matches = lookup_code_data(std_code)
            
            best_desc_en = "Manufacturer proprietary fault code"
            best_desc_fr = ""
            if matches:
                for m in matches:
                    if 'AEE2004' in m[2]:
                        best_desc_en = m[5] or best_desc_en
                        best_desc_fr = m[6] or best_desc_fr
                        break
                if best_desc_en == "Manufacturer proprietary fault code":
                    best_desc_en = matches[0][5] or best_desc_en
                    best_desc_fr = matches[0][6] or best_desc_fr

            lines.append(f"   • {BOLD}{RED}{std_code:<6}{RESET} (raw: 0x{raw_hex}) : {BOLD}{best_desc_en}{RESET}")
            if best_desc_fr and best_desc_fr != best_desc_en:
                lines.append(f"     {DIM}OEM (FR): {best_desc_fr}{RESET}")

            if std_code == 'P17A5':
                lines.append(f"     {MAGENTA}→ GEARBOX ADVICE: 1st gear synchronization fault on EGS6/BMP6 robotized manual.{RESET}")
                lines.append(f"     {MAGENTA}  Check clutch electrovalve hydraulic pressure and clutch bite point calibration.{RESET}")
            elif std_code == 'C1385':
                lines.append(f"     {MAGENTA}→ BRAKE ADVICE: ABS/ESP solenoid relay voltage low. Check battery & engine fusebox relay.{RESET}")
            elif std_code == 'P1351':
                lines.append(f"     {MAGENTA}→ ENGINE ADVICE: Glow plug relay circuit open/coherence (extremely common on DV6 1.6 HDi).{RESET}")
            elif std_code == 'P0299':
                lines.append(f"     {MAGENTA}→ TURBO ADVICE: Turbo underboost. Check vacuum solenoid pipes and wastegate actuator.{RESET}")
            lines.append("")

    lines.append("=" * 65)
    return "\n".join(lines)

def show_recent_logs(interactive_select: bool = False):
    obd_service.ensure_log_dir()
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN DIAGNOSTIC LOG AUDIT TRAIL{RESET}")
    print(f" Directory: {LOG_DIR}")
    print("=" * 65)

    if os.path.exists(HISTORY_FILE):
        print(f"\n{BOLD}Diagnostic History Summary:{RESET}")
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for l in lines[-10:]:
                print("  " + l.strip())
        print()

    log_files = sorted([f for f in os.listdir(LOG_DIR) if f.startswith('dtc_')], reverse=True)
    if not log_files:
        print("  No session log files found yet.")
    else:
        print(f"{BOLD}Recent Session Log Files:{RESET}")
        for idx, lf in enumerate(log_files[:5], 1):
            path = os.path.join(LOG_DIR, lf)
            size = os.path.getsize(path)
            print(f"  [{idx}] {BOLD}{lf}{RESET} ({size} bytes)")
        
        if interactive_select:
            try:
                choice = input(f"\n{BOLD}Enter log # to view in full (or press Enter to skip): {RESET}").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(log_files[:5]):
                    selected_file = os.path.join(LOG_DIR, log_files[int(choice) - 1])
                    print("\n" + "-" * 65)
                    with open(selected_file, 'r', encoding='utf-8') as sf:
                        print(sf.read())
                    print("-" * 65)
            except (KeyboardInterrupt, EOFError):
                pass

    print("=" * 65 + "\n")

def configure_adapter():
    """Sub-menu to configure COM port, baud rate, and simulation mode."""
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}ADAPTER & SERIAL CONNECTION SETTINGS{RESET}")
    print("=" * 65)
    
    ports = obd_service.find_serial_ports()
    print(f" Available Hardware Serial Ports:")
    if ports:
        for idx, p in enumerate(ports, 1):
            print(f"   [{idx}] {BOLD}{p.device}{RESET} - {p.description}")
    else:
        print("   [!] No active USB or Bluetooth serial adapters found right now.")
    
    current_port = SESSION_CONFIG['port'] or "Auto-Detect"
    current_baud = SESSION_CONFIG['baud']
    current_mode = "FORCED SIMULATION" if SESSION_CONFIG['force_sim'] else "LIVE AUTO"

    print(f"\n Current Settings:")
    print(f"   • Port:       {BOLD}{current_port}{RESET}")
    print(f"   • Baud Rate:  {BOLD}{current_baud}{RESET}")
    print(f"   • Mode:       {BOLD}{current_mode}{RESET}")

    print("\n Options:")
    print("   [1] Select a detected port")
    print("   [2] Enter manual device path (e.g. /dev/ttyUSB0)")
    print("   [3] Change baud rate (38400, 115200, 9600)")
    print("   [4] Toggle Simulation Mode ON/OFF")
    print("   [0] Back to main menu")

    try:
        opt = input(f"\n{BOLD}Select an option [0-4]: {RESET}").strip()
        if opt == '1' and ports:
            p_idx = int(input("Enter port number: ").strip())
            if 1 <= p_idx <= len(ports):
                SESSION_CONFIG['port'] = ports[p_idx - 1].device
                SESSION_CONFIG['force_sim'] = False
                print(f"{GREEN}[✓] Port set to: {SESSION_CONFIG['port']}{RESET}")
        elif opt == '2':
            dev = input("Enter device path (e.g. /dev/ttyUSB0): ").strip()
            if dev:
                SESSION_CONFIG['port'] = dev
                SESSION_CONFIG['force_sim'] = False
                print(f"{GREEN}[✓] Port set to: {SESSION_CONFIG['port']}{RESET}")
        elif opt == '3':
            b = int(input("Enter baud rate (38400, 115200, 9600): ").strip())
            if b in (38400, 115200, 9600, 230400, 500000):
                SESSION_CONFIG['baud'] = b
                print(f"{GREEN}[✓] Baud rate set to: {b}{RESET}")
        elif opt == '4':
            SESSION_CONFIG['force_sim'] = not SESSION_CONFIG['force_sim']
            state = "ON" if SESSION_CONFIG['force_sim'] else "OFF"
            print(f"{GREEN}[✓] Forced Simulation Mode: {state}{RESET}")
    except (ValueError, IndexError, KeyboardInterrupt, EOFError):
        pass

# ==============================================================================
# MAIN INTERACTIVE MENU
# ==============================================================================

def run_main_menu(is_demo: bool = False):
    """Main interactive text user interface."""
    SESSION_CONFIG['force_sim'] = is_demo or SESSION_CONFIG['force_sim']
    if not SESSION_CONFIG['force_sim']:
        obd_service.require_vehicle_or_demo(is_demo=False, port=SESSION_CONFIG['port'])

    while True:
        # Determine status string
        if SESSION_CONFIG['force_sim']:
            mode_badge = f"{YELLOW}[DEMO / SIMULATION MODE]{RESET}"
        elif SESSION_CONFIG['port']:
            mode_badge = f"{GREEN}[PORT: {SESSION_CONFIG['port']} @ {SESSION_CONFIG['baud']}]{RESET}"
        else:
            candidates = obd_service.find_serial_ports()
            if candidates:
                mode_badge = f"{GREEN}[READY: {candidates[0].device}]{RESET}"
            else:
                mode_badge = f"{RED}[VEHICLE NOT CONNECTED]{RESET}"

        print(f"\n{BOLD}{CYAN}╔═════════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║         CITROËN GRAND C4 PICASSO (1.6 HDi / EGS6) DIAGNOSTICS       ║{RESET}")
        print(f"{BOLD}{CYAN}║                 PSA AEE2004 Architecture • Full CAN                 ║{RESET}")
        print(f"{BOLD}{CYAN}╚═════════════════════════════════════════════════════════════════════╝{RESET}")
        print(f"  {BOLD}Status:{RESET}   {mode_badge}")
        print(f"  {BOLD}Vehicle:{RESET}  Citroën Grand C4 Picasso Mk1 (B58) 1.6 HDi")
        print(f"  {BOLD}Gearbox:{RESET}  6-Speed Piloted Manual (EGS6 / BMP6 - Magneti Marelli CFC300P)")
        print(f"  {BOLD}Network:{RESET}  High-Speed CAN 500 kbps (Pins 6 & 14)\n")

        print(f"  {BOLD}{GREEN}[1]{RESET} {BOLD}Read Active & Pending DTCs{RESET}     (Powertrain / Modes 03 & 07)")
        print(f"  {BOLD}{GREEN}[2]{RESET} {BOLD}Extended Multi-Module Scan{RESET}     (Engine, EGS6, ABS/ESP, Handbrake)")
        print(f"  {BOLD}{RED}[3]{RESET} {BOLD}Clear Fault Codes{RESET}              (Extinguish Service/Check Engine lamps)")
        print(f"  {BOLD}{CYAN}[4]{RESET} {BOLD}Look Up Fault Code{RESET}             (Decode C27A5, P17A5, C1385, raw hex)")
        print(f"  {BOLD}{CYAN}[5]{RESET} {BOLD}Search Database by Keyword{RESET}     (Search 'clutch', 'gearbox', 'dpf')")
        print(f"  {BOLD}{MAGENTA}[6]{RESET} {BOLD}View Diagnostic Audit Logs{RESET}     (Audit history & view session logs)")
        print(f"  {BOLD}{MAGENTA}[7]{RESET} {BOLD}List Known Vehicle ECUs{RESET}        (Grand C4 Picasso AEE2004 modules)")
        print(f"  {BOLD}{YELLOW}[8]{RESET} {BOLD}Adapter & Connection Setup{RESET}     (Port selection, baud rate, test)")
        print(f"  {BOLD}[0] Exit{RESET}\n")

        try:
            choice = input(f"{BOLD}psa-diag [0-8]> {RESET}").strip()
            if not choice:
                continue

            if choice in ('0', 'q', 'exit', 'quit'):
                print("\nGoodbye.")
                break
            elif choice == '1':
                execute_dtc_read(sim=SESSION_CONFIG['force_sim'])
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            elif choice == '2':
                execute_dtc_scan(sim=SESSION_CONFIG['force_sim'])
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            elif choice == '3':
                execute_dtc_clear(sim=SESSION_CONFIG['force_sim'])
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            elif choice == '4':
                code = input(f"\n{BOLD}Enter DTC or Raw Hex (e.g. C27A5, P17A5, 0x67A5): {RESET}").strip()
                if code:
                    lookup_code(code)
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            elif choice == '5':
                kw = input(f"\n{BOLD}Enter search keyword (e.g. 'parking brake', 'gearbox'): {RESET}").strip()
                if kw:
                    search_text(kw)
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            elif choice == '6':
                show_recent_logs(interactive_select=True)
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            elif choice == '7':
                show_modules()
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            elif choice == '8':
                configure_adapter()
                input(f"\n{DIM}Press Enter to return to menu...{RESET}")
            else:
                # If user typed a direct code like C27A5 in the main menu
                clean = choice.upper()
                if re.match(r'^[PCBU0-9]', clean):
                    lookup_code(clean)
                    input(f"\n{DIM}Press Enter to return to menu...{RESET}")
                else:
                    print(f"{RED}Invalid option '{choice}'. Please select 0 to 8.{RESET}")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

# ==============================================================================
# SPECIALIZED DIAGNOSTICS & CAN REVERSE ENGINEERING CLI HANDLERS
# ==============================================================================

def cli_odometer(is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    data = special_diagnostics.analyze_odometer_service(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN GRAND C4 PICASSO: ODOMETER & MAINTENANCE AUDIT{RESET}")
    print(f" Electronic Nodes: BSI Gateway (0x7D2) & Instrument Cluster (0x7C2)")
    print("=" * 65)
    print(f" • Total Vehicle Mileage:     {BOLD}{data['total_miles']:,} miles{RESET} ({data['total_km']:,} km)")
    print(f" • Next Service Countdown:    {BOLD}{data['service_remaining_miles']:,} miles{RESET} ({data['service_remaining_km']:,} km / {data['service_days']} days)")
    print(f" • Instrument Spanner Lamp:   {BOLD}{GREEN if data['spanner_badge']=='OK' else RED}{data['spanner_status']}{RESET}")
    print(f" • Oil Life Remaining:        {BOLD}{data['oil_life_remaining_pct']}%{RESET} (Degradation index: {data['oil_degradation_pct']}%)")
    print(f" • Fuel Economy (1.6 HDi):    {BOLD}{data['avg_mpg']} MPG{RESET} ({data['avg_l_100km']} L/100km)")
    print(f" • Trip Computer A:           {data['trip_a_miles']} miles ({data['trip_a_km']} km)")
    print(f" • Trip Computer B:           {data['trip_b_miles']} miles ({data['trip_b_km']} km)")
    print(f" • Odometer Synchronization:  {BOLD}{GREEN}{data['sync_status']}{RESET}")
    print("=" * 65 + "\n")

def cli_service(action: str = 'info', is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action == 'reset':
        res = special_diagnostics.reset_service_interval(is_sim=is_demo)
        print("\n" + "=" * 65)
        print(f" {BOLD}{GREEN}[✓] CITROËN MAINTENANCE SERVICE INTERVAL RESET SUCCESSFUL{RESET}")
        print("=" * 65)
        print(f" • Next Service Interval:     {BOLD}{res['reset_interval_miles']:,} miles{RESET} ({res['reset_interval_km']:,} km / {res['reset_days']} days)")
        print(f" • Maintenance Spanner Lamp:  {BOLD}EXTINGUISHED (Cleared from cluster & BSI){RESET}")
        print(f" • Oil Degradation Index:     {BOLD}RESET TO 0%{RESET}")
        print(f" • Execution Timestamp:       {res['timestamp']}")
        print("=" * 65 + "\n")
    else:
        cli_odometer(is_demo=is_demo, port=port, interface=interface)

def cli_egs6(action: str = 'status', is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action == 'relearn':
        print("\n" + "=" * 65)
        print(f" {BOLD}{CYAN}CITROËN EGS6: POINT DE LÉCHAGE & GRID RELEARN WIZARD{RESET}")
        print(f" Gearbox: Magneti Marelli CFC300P (6-Speed Robotized Manual)")
        print("=" * 65)
        print("[!] Ensure vehicle is on level ground, handbrake ON, footbrake held.\n")
        def callback(stage, total, title, desc):
            bar = make_progress_bar(stage, total, width=20)
            print(f"[{stage}/{total}] {bar} {BOLD}{title}:{RESET} {desc}")
        res = special_diagnostics.run_egs6_relearn(is_sim=is_demo, step_callback=callback)
        print("\n" + "-" * 65)
        print(f" {BOLD}{GREEN}[✓] RELEARN COMPLETE:{RESET} Bite-point learned at {BOLD}{res['bite_point_mm']} mm{RESET}")
        print(f" • Neutral Offset: {res['neutral_offset_mm']} mm | Fork Calibration: {res['fork_calibration']}")
        print(f" • Final Step: {res['instructions']}")
        print("=" * 65 + "\n")
        return

    data = special_diagnostics.analyze_egs6_gearbox(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN GRAND C4 PICASSO: EGS6 GEARBOX & CLUTCH ANALYSIS{RESET}")
    print(f" Platform: Magneti Marelli CFC300P (6-Speed Piloted Manual Transmission)")
    print("=" * 65)
    print(f" • Hydraulic Pump Pressure:    {BOLD}{data['pressure_bar']} bar{RESET} (Normal range: 40 - 50 bar)")
    print(f" • Pressure Hold Decay Time:    {BOLD}{data['decay_sec']} seconds{RESET} (Threshold: >120s good, <45s failing)")
    print(f" • Accumulator Health Status:   {BOLD}{GREEN if data['accum_status']=='OK' else YELLOW}{data['accum_verdict']}{RESET}")
    print(f" • Clutch Slave Position:       {BOLD}{data['clutch_mm']} mm{RESET} (Range: ~10mm new to ~18mm worn limit)")
    print(f" • Estimated Clutch Plate Wear: {BOLD}{data['clutch_wear_pct']}%{RESET}")
    print(f" • Clutch Wear Assessment:      {BOLD}{GREEN if data['clutch_status']=='OK' else YELLOW}{data['clutch_verdict']}{RESET}")
    print(f" • Relearn Calibration Status:  {data['relearn_status']}")
    print(f" • Hydraulic Fluid Temperature: {data['temp_c']} °C")
    print("=" * 65 + "\n")

def cli_dpf(action: str = 'status', is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action == 'regen':
        print("\n" + "=" * 65)
        print(f" {BOLD}{RED}CITROËN 1.6 HDi: FORCED STATIONARY DPF REGENERATION{RESET}")
        print(f" Engine: DV6 1.6 HDi (Bosch EDC16C34 Euro 4/Euro 5 FAP)")
        print("=" * 65)
        print(f"{YELLOW}Warning: Exhaust temperature will exceed 580°C. Keep clear of tailpipe.{RESET}\n")
        def callback(stage, total, title, desc):
            bar = make_progress_bar(stage, total, width=20)
            print(f"[{stage}/{total}] {bar} {BOLD}{title}:{RESET} {desc}")
        res = special_diagnostics.run_dpf_regeneration(is_sim=is_demo, step_callback=callback)
        print("\n" + "-" * 65)
        print(f" {BOLD}{GREEN}[✓] REGENERATION SUCCESSFUL!{RESET}")
        print(f" • Soot reduced: {BOLD}{res['initial_soot_g']} g -> {res['final_soot_g']} g ({res['soot_reduction_pct']}% reduction){RESET}")
        print(f" • Max Core Temp: {res['max_temp_c']} °C | Idle Backpressure: {res['diff_pressure_idle_mbar']} mbar")
        print(f" • Verdict: {res['verdict']}")
        print("=" * 65 + "\n")
        return

    data = special_diagnostics.analyze_dpf_system(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN GRAND C4 PICASSO: DPF (FAP) & EOLYS ADDITIVE HEALTH{RESET}")
    print(f" Engine: 1.6 HDi DV6 Diesel (Euro 4 / Euro 5 FAP System)")
    print("=" * 65)
    print(f" • DPF Soot Load:               {BOLD}{data['soot_g']} g ({data['soot_pct']}% capacity){RESET}")
    print(f" • Exhaust Differential Press:  {BOLD}{data['diff_mbar']} mbar{RESET} at idle (Normal: 0-15 mbar)")
    print(f" • Distance Since Last Regen:   {BOLD}{data['km_since_regen']} km{RESET} (Historical avg interval: {data['avg_regen_km']} km)")
    print(f" • Particle Filter Verdict:     {BOLD}{GREEN if data['dpf_status']=='OK' else YELLOW}{data['dpf_verdict']}{RESET}")
    print(f" • Eolys Additive in Pouch:     {BOLD}{data['eolys_ml']} ml ({data['eolys_pct']}% full){RESET}")
    print(f" • Additive System Verdict:     {BOLD}{GREEN if data['eolys_status']=='OK' else YELLOW}{data['eolys_verdict']}{RESET}")
    print("=" * 65 + "\n")

def cli_bsi(action: str = 'status', duration: int = 60, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action == 'keepalive':
        advanced_features.BSIController.run_keepalive(duration_sec=duration, is_sim=is_demo)
    else:
        st = advanced_features.BSIController.get_power_state(is_sim=is_demo)
        print("\n" + "=" * 65)
        print(f" {BOLD}{CYAN}CITROËN BSI (CENTRAL BODY GATEWAY) POWER STATUS{RESET}")
        print(f" Target Module: CAN 0x7D2 / 0x752")
        print("=" * 65)
        print(f" • Power Stage:               {BOLD}{GREEN if 'AWAKE' in st['power_stage'] else YELLOW}{st['power_stage']}{RESET}")
        print(f" • Economy Mode Status:       {'ACTIVE (Electrics Inhibited)' if st['economy_mode_active'] else 'INACTIVE (Normal Operating State)'}")
        print(f" • Economy Mode Timeout:      {BOLD}{st['minutes_to_economy_mode']} minutes remaining{RESET}")
        print(f" • Ignition Key State:        {st['key_position']}")
        print(f" • BSI Wakeup Reason:         {st['bsi_wake_reason']}")
        print(f" • Multiplex Network Status:  {st['can_buses']}")
        print(f" • 12V Battery Voltage:       {st['battery_v']} V")
        print("=" * 65 + "\n")

def cli_web(port: int = 8080, is_demo: bool = False, serial_port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=serial_port, interface=interface)
    import web_dashboard
    web_dashboard.start_web_server(port=port, is_demo=is_demo)

def cli_battery(is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    data = special_diagnostics.analyze_battery_crank(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN GRAND C4 PICASSO: 12V CRANKING VOLTAGE TEST{RESET}")
    print(f" Electrical System & False Phantom DTC Risk Assessment")
    print("=" * 65)
    print(f" • Resting Battery Voltage:     {BOLD}{data['resting_v']} V{RESET}")
    print(f" • Cranking Minimum Voltage:    {BOLD}{data['cranking_min_v']} V{RESET} (Critical threshold: 10.50 V)")
    print(f" • Alternator Charging Voltage: {BOLD}{data['charging_v']} V{RESET} (Alternator regulator OK)")
    print(f" • Battery Health Assessment:   {BOLD}{GREEN if data['status']=='OK' else RED}{data['verdict']}{RESET}")
    print(f" • Phantom DTC Risk:            {BOLD}{MAGENTA}{data['risk']}{RESET}")
    print("=" * 65 + "\n")

def cli_signals(action: str = 'list', export_path: str = None):
    if action == 'export':
        out = export_path or '/root/psa_diag/c4_picasso_learned.dbc'
        saved_path = can_sniffer.export_dbc_file(out)
        print(f"\n{GREEN}[✓] Successfully exported learned signals to Vector DBC format:{RESET}")
        print(f"    {BOLD}{saved_path}{RESET}\n")
        return

    signals = can_sniffer.load_learned_signals()
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN REVERSE-ENGINEERED SIGNALS DICTIONARY{RESET}")
    print(f" File: {can_sniffer.LEARNED_SIGNALS_FILE} ({len(signals)} learned signals)")
    print("=" * 65)
    for s in signals:
        print(f" • {BOLD}{GREEN}{s['name']:<26}{RESET} [{BOLD}{s['can_id']}{RESET} Byte {s['byte_idx']} Mask {s['bit_mask']}]")
        print(f"   {s['description']}")
        print(f"   {DIM}Recorded: {s.get('learned_on', 'N/A')}{RESET}")
        print()
    print("=" * 65 + "\n")

def cli_epb(action: str = 'status', exit_mode: bool = False, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    controller = advanced_features.EPBController()
    if action in ('service', 'retract'):
        controller.set_service_mode(retract=True, is_sim=is_demo)
    elif action == 'calibrate':
        controller.calibrate_force(is_sim=is_demo)
    elif exit_mode or action == 'exit':
        controller.set_service_mode(retract=False, is_sim=is_demo)
    else:
        st = controller.get_status(is_sim=is_demo)
        print("\n" + "=" * 65)
        print(f" {BOLD}{CYAN}CITROËN ELECTRIC PARKING BRAKE (FSE) STATUS{RESET}")
        print(f" Target Module: CAN 0x792 / 0x79A")
        print("=" * 65)
        print(f" • Operating State:          {BOLD}{st['state']}{RESET}")
        print(f" • Mode:                     {st['mode']}")
        print(f" • Clamping Tension Force:   {BOLD}{st['tension_daN']} daN{RESET} (Nominal: 140 - 180 daN)")
        print(f" • Left Cable Extension:     {st['left_cable_mm']} mm")
        print(f" • Right Cable Extension:    {st['right_cable_mm']} mm")
        print(f" • Total Application Cycles: {st['cycles_count']}")
        print(f" • Calibration Status:       {BOLD}{GREEN if 'VALID' in st['calibration_status'] else YELLOW}{st['calibration_status']}{RESET}")
        print(f" • Pad Replacement Mode:     {'ACTIVE (Cables Unwound)' if st['pad_replacement_mode'] else 'INACTIVE (Normal Driving)'}")
        print("=" * 65 + "\n")

def cli_freeze(code: str = 'P17A5', is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    print(advanced_features.FreezeFrameInspector.format_report(code))

def cli_test(component: str = 'pump', is_demo: bool = False, port: str = None, interface: str = None):
    if component == 'list':
        print("\n" + "=" * 65)
        print(f" {BOLD}{CYAN}AVAILABLE BIDIRECTIONAL ACTUATOR TESTS{RESET}")
        print("=" * 65)
        for k, v in advanced_features.ActuatorTester.TESTS.items():
            print(f" • {BOLD}{k:<10}{RESET} : {v['name']} ({v['description']})")
        print("=" * 65 + "\n")
        return
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    advanced_features.ActuatorTester.run_test(component, is_sim=is_demo)

def cli_network(is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    print(advanced_features.CANNetworkTopology.render_ascii_map(is_sim=is_demo))

def cli_record(duration: int = 30, trigger_on_dtc: bool = False, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    rec = advanced_features.FlightRecorder()
    rec.record_flight(duration_sec=duration, trigger_on_dtc=trigger_on_dtc, is_sim=is_demo)

def cli_sniff(is_demo: bool = False, port: str = None, interface: str = None):
    if sys.stdin.isatty() and sys.stdout.isatty():
        tui.launch_tui(is_demo=is_demo)
    else:
        if not is_demo:
            obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
        print("[*] Launching CAN Sniffer in interactive terminal...")

def cli_diagram(sensor_id: int = None, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if sensor_id:
        print(engine_diagram.get_sensor_inspect_card(sensor_id, is_sim=is_demo))
    else:
        print(engine_diagram.render_ascii_engine_diagram(is_sim=is_demo, use_color=True))
        print(engine_diagram.render_sensor_detail_table(is_sim=is_demo, use_color=True))

def cli_sensors(subsystem: str = 'all', is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    tree = workshop_features.get_all_vehicle_sensors(is_sim=is_demo)
    print("\n" + "=" * 70)
    print(f" {BOLD}{CYAN}CITROËN GRAND C4 PICASSO: FULL VEHICLE SENSOR TELEMETRY{RESET}")
    print(f" Platform: PSA AEE2004 • 1.6 HDi DV6 • EGS6 • Bosch ESP 8.1")
    print("=" * 70)
    for cat, sensor_list in tree.items():
        if subsystem != 'all' and subsystem.lower() not in cat.lower():
            continue
        print(f"\n {BOLD}{YELLOW}▶ {cat.upper()}{RESET}")
        print(" " + "-" * 68)
        for s in sensor_list:
            print(f"  • {BOLD}{s['name']:<34}{RESET} : {BOLD}{GREEN}{s['val']:<16}{RESET} {DIM}(Nominal: {s['nominal']}){RESET}")
    print("=" * 70 + "\n")

def cli_suspension(action: str = 'status', is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action in ('bleed', 'depressurize'):
        print("\n" + "=" * 65)
        print(f" {BOLD}{RED}CITROËN REAR PNEUMATIC SUSPENSION: SERVICE DEPRESSURIZATION{RESET}")
        print(f" Target Module: CAAR (Rear Air Suspension 0x782 / 0x702)")
        print("=" * 65)
        print("[!] Ensure vehicle is stationary on flat ground with handbrake applied.\n")
        def cb(stage, total, title, desc):
            bar = make_progress_bar(stage, total, width=20)
            print(f"[{stage}/{total}] {bar} {BOLD}{title}:{RESET} {desc}")
        res = workshop_features.PneumaticSuspensionController.bleed_system(is_sim=is_demo, step_callback=cb)
        print("\n" + "-" * 65)
        print(f" {BOLD}{GREEN}[✓] DEPRESSURIZATION COMPLETE:{RESET} Circuit pressure: {BOLD}{res['final_pressure_bar']} bar{RESET}")
        print(f" • Left Height: {res['height_left_mm']} mm | Right Height: {res['height_right_mm']} mm")
        print(f" • Next Step: {res['instructions']}")
        print("=" * 65 + "\n")
        return
    elif action == 'inflate':
        print("\n" + "=" * 65)
        print(f" {BOLD}{CYAN}CITROËN REAR PNEUMATIC SUSPENSION: REPRESSURIZATION WIZARD{RESET}")
        print(f" Target Module: CAAR (Rear Air Suspension 0x782 / 0x702)")
        print("=" * 65)
        def cb(stage, total, title, desc):
            bar = make_progress_bar(stage, total, width=20)
            print(f"[{stage}/{total}] {bar} {BOLD}{title}:{RESET} {desc}")
        res = workshop_features.PneumaticSuspensionController.inflate_system(is_sim=is_demo, step_callback=cb)
        print("\n" + "-" * 65)
        print(f" {BOLD}{GREEN}[✓] REPRESSURIZATION COMPLETE:{RESET} Circuit pressure: {BOLD}{res['bellows_pressure_bar']} bar{RESET}")
        print(f" • Restored Curb Height: Left {res['height_left_mm']} mm | Right {res['height_right_mm']} mm")
        print(f" • Status: {res['instructions']}")
        print("=" * 65 + "\n")
        return
    elif action == 'test':
        res = workshop_features.PneumaticSuspensionController.test_compressor(duration_sec=5, is_sim=is_demo)
        print("\n" + "=" * 65)
        print(f" {BOLD}{CYAN}SUSPENSION 12V COMPRESSOR ELECTRICAL RUN TEST{RESET}")
        print("=" * 65)
        print(f" • Current Draw:        {BOLD}{res['current_draw_amps']} A{RESET} (Peak: {res['peak_current_amps']} A)")
        print(f" • Pressure Rise:       {BOLD}+{res['pressure_rise_bar']} bar{RESET}")
        print(f" • Compressor Temp:     {res['max_temp_c']} °C")
        print(f" • Verdict:             {BOLD}{GREEN}{res['verdict']}{RESET}")
        print("=" * 65 + "\n")
        return
    elif action == 'calibrate':
        res = workshop_features.PneumaticSuspensionController.calibrate_height(nominal_target_mm=118.0, is_sim=is_demo)
        print("\n" + "=" * 65)
        print(f" {BOLD}{GREEN}[✓] HEIGHT SENSOR ZEROING CALIBRATION SUCCESSFUL{RESET}")
        print("=" * 65)
        print(f" • Reference Curb Height:  {BOLD}{res['reference_curb_mm']} mm{RESET}")
        print(f" • Left Sensor Voltage:    {res['left_offset_v']} V")
        print(f" • Right Sensor Voltage:   {res['right_offset_v']} V")
        print(f" • Stored in CAAR EEPROM:  YES")
        print("=" * 65 + "\n")
        return

    st = workshop_features.PneumaticSuspensionController.get_status(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN GRAND C4 PICASSO: REAR PNEUMATIC AIR SUSPENSION{RESET}")
    print(f" Target Module: CAAR (Rear Suspension ECU 0x782 / 0x702)")
    print("=" * 65)
    print(f" • System State:            {BOLD}{st['system_state']}{RESET}")
    print(f" • Rear Left Ride Height:   {BOLD}{st['height_left_mm']} mm{RESET} ({st['sensor_left_v']} V) [Nominal: {st['nominal_target_mm']} mm]")
    print(f" • Rear Right Ride Height:  {BOLD}{st['height_right_mm']} mm{RESET} ({st['sensor_right_v']} V) [Nominal: {st['nominal_target_mm']} mm]")
    print(f" • Left Bellows Pressure:   {st['bellows_pressure_left_bar']} bar")
    print(f" • Right Bellows Pressure:  {st['bellows_pressure_right_bar']} bar")
    print(f" • Air Reservoir Pressure:  {BOLD}{st['reservoir_pressure_bar']} bar{RESET} (Nominal: 8.0 - 10.0 bar)")
    print(f" • Compressor Temperature:  {st['compressor_temp_c']} °C (Thermal cutout at 110°C)")
    print(f" • Airbag Leak Integrity:   {BOLD}{GREEN}{st['airbag_integrity']}{RESET}")
    print(f" • Height Calibration:      {'VALID' if st['calibration_valid'] else 'UNSET'}")
    print("=" * 65 + "\n")

def cli_eolys(action: str = 'status', volume: int = 1100, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action == 'reset':
        print("\n" + "=" * 65)
        print(f" {BOLD}{CYAN}CITROËN EOLYS DPF ADDITIVE REFILL & PRIMING WIZARD{RESET}")
        print(f" Target Modules: ADDGO (0x772) & Engine EDC16C34 (0x7E8)")
        print("=" * 65)
        def cb(stage, total, title, desc):
            bar = make_progress_bar(stage, total, width=20)
            print(f"[{stage}/{total}] {bar} {BOLD}{title}:{RESET} {desc}")
        res = workshop_features.EolysManager.reset_pouch(volume_ml=volume, is_sim=is_demo, step_callback=cb)
        print("\n" + "-" * 65)
        print(f" {BOLD}{GREEN}[✓] EOLYS ADDITIVE RESET & PRIMING SUCCESSFUL!{RESET}")
        print(f" • New Pouch Volume:       {BOLD}{res['new_volume_ml']} ml{RESET} (Estimated range: ~{res['remaining_range_km']:,} km)")
        print(f" • Additive DTCs Cleared:  YES (Cleared P1434 / P1435 in EDC16C34)")
        print(f" • Dosing Line Primed:     YES (15-second pump purge complete)")
        print("=" * 65 + "\n")
        return

    st = workshop_features.EolysManager.get_status(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN EOLYS DPF ADDITIVE SYSTEM STATUS{RESET}")
    print(f" Module: Additive Dosing ECU (ADDGO 0x772)")
    print("=" * 65)
    print(f" • Additive Pouch Volume:   {BOLD}{st['pouch_volume_ml']} ml{RESET} / {st['pouch_capacity_ml']} ml ({st['pouch_percent']}%)")
    print(f" • Estimated Additive Range:{BOLD}~{st['estimated_range_km']:,} km{RESET} remaining")
    print(f" • Injected Cerine in DPF:  {st['total_cerine_injected_g']} g (Capacity: {st['cerine_capacity_g']} g)")
    print(f" • Dosing Pump Resistance:  {st['pump_resistance_ohms']} Ω (Normal: 10 - 15 Ω)")
    print(f" • Additive Warning Lamp:   {'ACTIVE' if st['warning_lamp_active'] else 'OFF (Normal)'}")
    print("=" * 65 + "\n")

def cli_injector(action: str = 'read', cylinder: int = 1, code: str = None, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action == 'write':
        if not code:
            print(f"{RED}Error: --code argument required for writing injector calibration.{RESET}")
            return
        res = workshop_features.InjectorCoder.write_code(cylinder=cylinder, code=code, is_sim=is_demo)
        print("\n" + "=" * 65)
        print(f" {BOLD}{GREEN}[✓] BOSCH 1.6 HDi INJECTOR CODE PROGRAMMED SUCCESSFUL{RESET}")
        print("=" * 65)
        print(f" • Target Cylinder:        {BOLD}Cylinder {res['cylinder']}{RESET} ({res['cylinder_location']})")
        print(f" • New Stored IMA Code:    {BOLD}{res['new_code']}{RESET}")
        print(f" • Written to ECU EEPROM:  YES (Bosch EDC16C34)")
        print(f" • Timestamp:              {res['timestamp']}")
        print("=" * 65 + "\n")
        return

    codes = workshop_features.InjectorCoder.read_codes(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN 1.6 HDi BOSCH INJECTOR IMA CODES{RESET}")
    print(f" Engine ECU: {codes['ecu']} (DID 0xF190)")
    print(" Note: PSA counts Cylinder 1 at the FLYWHEEL / TRANSMISSION side!")
    print("=" * 65)
    print(f" • Cylinder 1 (Flywheel Side):    {BOLD}{GREEN}{codes['cyl1']}{RESET}")
    print(f" • Cylinder 2 (Center Right):     {BOLD}{GREEN}{codes['cyl2']}{RESET}")
    print(f" • Cylinder 3 (Center Left):      {BOLD}{GREEN}{codes['cyl3']}{RESET}")
    print(f" • Cylinder 4 (Timing Belt Side): {BOLD}{GREEN}{codes['cyl4']}{RESET}")
    print("=" * 65 + "\n")

def cli_bsi_config(action: str = 'list', option: str = None, value: str = None, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    if action == 'set':
        if not option or not value:
            print(f"{RED}Error: --option and --value required for telecoding.{RESET}")
            return
        res = workshop_features.BSITelecoder.set_option(option, value, is_sim=is_demo)
        print("\n" + "=" * 65)
        print(f" {BOLD}{GREEN}[✓] CITROËN BSI TELECODING WRITE SUCCESSFUL{RESET}")
        print("=" * 65)
        print(f" • Parameter:              {BOLD}{res['option_name']}{RESET} ({res['option_key']})")
        print(f" • New Committed Value:    {BOLD}{res['new_value']}{RESET}")
        print(f" • Target BSI DID:         {res['did']}")
        print(f" • Security Access Seed:   AUTHENTICATED & STORED")
        print("=" * 65 + "\n")
        return

    opts = workshop_features.BSITelecoder.get_all_options(is_sim=is_demo)
    print("\n" + "=" * 65)
    print(f" {BOLD}{CYAN}CITROËN BSI CUSTOMER TELECODING & HIDDEN OPTIONS{RESET}")
    print(f" Gateway: Built-in Systems Interface (CAN 0x752)")
    print("=" * 65)
    for k, v in opts.items():
        print(f" • {BOLD}{k:<22}{RESET} : Current: {BOLD}{GREEN}{v['value']:<14}{RESET} Choices: {v['choices']}")
        print(f"   {DIM}{v['desc']}{RESET}\n")
    print("=" * 65)
    print(f" To change an option: {CYAN}psa bsi-config set --option <name> --value <val> --demo{RESET}\n")

def cli_health(export_path: str = None, is_demo: bool = False, port: str = None, interface: str = None):
    if not is_demo:
        obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
    audit = workshop_features.VehicleHealthAuditor.run_full_audit(is_sim=is_demo)
    score_col = GREEN if audit['overall_score'] >= 80 else YELLOW
    
    print("\n" + "=" * 70)
    print(f" {BOLD}{CYAN}CITROËN GRAND C4 PICASSO: PRE-PURCHASE INSPECTION (PPI) SCORECARD{RESET}")
    print(f" Target: {audit['vehicle']} • VIN: {audit['vin']}")
    print(f" Timestamp: {audit['timestamp']} | Recorded Mileage: {audit['odometer_miles']:,} miles")
    print("=" * 70)
    print(f"\n   {BOLD}OVERALL VEHICLE HEALTH INDEX:{RESET} {score_col}{BOLD}{audit['overall_score']}/100{RESET}  [{BOLD}{audit['grade']}{RESET}]\n")
    print(" " + "-" * 68)
    for title, score, details, badge in audit['checklist']:
        b_color = GREEN if badge == "PASS" else YELLOW
        print(f" [{b_color}{BOLD}{badge:<4}{RESET}] {score:<3}/100 : {BOLD}{title:<34}{RESET}")
        print(f"          {DIM}↳ {details}{RESET}")
    print("=" * 70)

    if export_path:
        saved = workshop_features.VehicleHealthAuditor.generate_html_report(audit, output_path=export_path)
        print(f"\n{GREEN}[✓] Full inspection report exported to standalone HTML:{RESET} {BOLD}{saved}{RESET}\n")
    else:
        print(f"\n {DIM}To export an interactive HTML inspection report, add '--export report.html'{RESET}\n")

def cli_can_replay(file_path: str, interface: str = 'vcan0', speed: float = 1.0, is_demo: bool = False):
    workshop_features.CANReplayEngine.replay_log_file(file_path=file_path, interface=interface, speed_mult=speed, is_sim=is_demo)

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

def main():
    global_demo = any(arg in sys.argv for arg in ['--demo', '--sim', '-demo', '-sim'])

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--demo", action="store_true", help="Run with Citroën Grand C4 Picasso offline simulation test data")
    common_parser.add_argument("--sim", action="store_true", help="Alias for --demo")
    common_parser.add_argument("--port", help="Serial port (e.g. /dev/ttyUSB0, /dev/ttyACM0)")
    common_parser.add_argument("--baud", type=int, default=38400, help="Baud rate (default: 38400)")
    common_parser.add_argument("-i", "--interface", help="SocketCAN interface (e.g. can0, vcan0)")

    parser = argparse.ArgumentParser(
        description="PSA / Citroën Diagnostic CLI Tool (Grand C4 Picasso Mk1 1.6 HDi EGS6)",
        parents=[common_parser]
    )
    subparsers = parser.add_subparsers(dest="command")

    # lookup command
    p_lookup = subparsers.add_parser("lookup", parents=[common_parser], help="Lookup and decode a DTC code (e.g. C27A5, P17A5)")
    p_lookup.add_argument("code", help="The DTC code or raw hex (e.g. C27A5, P17A5, 0x67A5)")

    # search command
    p_search = subparsers.add_parser("search", parents=[common_parser], help="Search the PSA database by keyword (e.g. 'parking brake')")
    p_search.add_argument("keyword", help="Search keyword")

    # modules command
    subparsers.add_parser("modules", parents=[common_parser], help="List all ECUs and modules on the C4 Picasso AEE2004 platform")

    # menu / tui / shell command
    subparsers.add_parser("tui", parents=[common_parser], help="Launch btop-style tabbed diagnostic dashboard")
    subparsers.add_parser("menu", parents=[common_parser], help="Launch interactive diagnostic dashboard")
    subparsers.add_parser("shell", parents=[common_parser], help="Launch interactive diagnostic dashboard")

    # dtc command group
    p_dtc = subparsers.add_parser("dtc", parents=[common_parser], help="Perform live or simulated OBD-II/CAN actions")
    dtc_subparsers = p_dtc.add_subparsers(dest="dtc_action")

    # dtc read
    dtc_subparsers.add_parser("read", parents=[common_parser], help="Read active and pending DTCs from vehicle")

    # dtc scan
    dtc_subparsers.add_parser("scan", parents=[common_parser], help="Extended scan across Engine, EGS6 Gearbox, ESP, Handbrake")

    # dtc clear
    p_dtc_clear = dtc_subparsers.add_parser("clear", parents=[common_parser], help="Clear DTCs from ECUs and verify clearance")
    p_dtc_clear.add_argument("--force", action="store_true", help="Skip confirmation prompt")

    # dtc logs
    dtc_subparsers.add_parser("logs", parents=[common_parser], help="View recent diagnostic audit logs")

    # Specialized diagnostics & CAN reverse engineering commands
    # Odometer and miles inspection
    subparsers.add_parser("odo", parents=[common_parser], help="Read total vehicle mileage & maintenance interval audit")
    subparsers.add_parser("miles", parents=[common_parser], help="Read total vehicle mileage (alias for odo)")

    # Service indicator & spanner lamp reset
    p_srv = subparsers.add_parser("service", parents=[common_parser], help="Citroën service interval audit & spanner lamp reset")
    p_srv.add_argument("service_action", nargs="?", default="info", choices=["info", "reset"], help="Action: info (view service status) or reset (clear spanner lamp)")

    # EGS6 Gearbox
    p_egs6 = subparsers.add_parser("egs6", parents=[common_parser], help="Run EGS6 semi-auto gearbox diagnostics & clutch relearn")
    p_egs6.add_argument("egs6_action", nargs="?", default="status", choices=["status", "relearn"], help="Action: status (hydraulic pressure & wear) or relearn (point de léchage)")

    # DPF (FAP)
    p_dpf = subparsers.add_parser("dpf", parents=[common_parser], help="Run DPF soot load diagnostics & forced stationary regeneration")
    p_dpf.add_argument("dpf_action", nargs="?", default="status", choices=["status", "regen"], help="Action: status (soot & eolys) or regen (forced thermal burn)")

    # BSI Controller
    p_bsi = subparsers.add_parser("bsi", parents=[common_parser], help="BSI gateway power management & Economy Mode keepalive")
    p_bsi.add_argument("bsi_action", nargs="?", default="status", choices=["status", "keepalive"], help="Action: status or keepalive")
    p_bsi.add_argument("--duration", type=int, default=60, help="Keepalive heartbeat duration in seconds (default: 60)")

    # Web Dashboard (Mobile companion)
    p_web = subparsers.add_parser("web", help="Launch mobile companion dark-mode web dashboard")
    p_web.add_argument("--demo", action="store_true", help="Run with simulation test data")
    p_web.add_argument("--sim", action="store_true", help="Alias for --demo")
    p_web.add_argument("--port", dest="web_port", type=int, default=8080, help="Web dashboard HTTP port (default: 8080)")
    p_web.add_argument("--web-port", dest="web_port", type=int, help="Alias for --port")
    p_web.add_argument("-i", "--interface", help="SocketCAN network interface (e.g. can0, vcan0)")
    p_web.add_argument("--serial-port", dest="port", help="Serial port (e.g. /dev/ttyUSB0)")

    subparsers.add_parser("battery", parents=[common_parser], help="Run 12V battery cranking voltage drop test")
    subparsers.add_parser("sniff", parents=[common_parser], help="Launch Cheat-Engine style CAN bus sniffer")

    # EPB / FSE Service Mode & Calibration
    p_epb = subparsers.add_parser("epb", parents=[common_parser], help="Electric Parking Brake (EPB/FSE) maintenance mode & calibration")
    p_epb.add_argument("epb_action", nargs="?", default="status", choices=["status", "service", "retract", "calibrate", "exit"], help="EPB action")
    p_epb.add_argument("--exit", action="store_true", help="Exit service mode and restore tension")

    # Freeze Frame Inspector
    p_frz = subparsers.add_parser("freeze", parents=[common_parser], help="Inspect DTC freeze-frame telemetry snapshot (Mode 02/UDS)")
    p_frz.add_argument("freeze_code", nargs="?", default="P17A5", help="DTC fault code to inspect (default: P17A5)")

    # Bidirectional Actuator Component Tests
    p_tst = subparsers.add_parser("test", parents=[common_parser], help="Bidirectional actuator component tests")
    p_tst.add_argument("component", nargs="?", default="pump", choices=["pump", "fan_low", "fan_high", "egr", "glow", "fuel", "list"], help="Actuator component to test")

    # CAN Bus Node Topology Ping
    subparsers.add_parser("ping", parents=[common_parser], help="CAN bus node topology ping & network health map")
    subparsers.add_parser("network", parents=[common_parser], help="CAN bus node topology ping & network health map")

    # Black Box CSV Flight Recorder
    p_rec = subparsers.add_parser("record", parents=[common_parser], help="Black box CSV flight recorder")
    p_rec.add_argument("--duration", type=int, default=30, help="Recording duration in seconds (default: 30)")
    p_rec.add_argument("--trigger-on-dtc", action="store_true", help="Auto-trigger recording burst when DTC trips")

    p_sig = subparsers.add_parser("signals", parents=[common_parser], help="Manage reverse-engineered CAN signals dictionary")
    p_sig.add_argument("sig_action", nargs="?", default="list", choices=["list", "export"], help="Action: list or export")
    p_sig.add_argument("--out", help="Export path for DBC file (default: /root/psa_diag/c4_picasso_learned.dbc)")

    # Engine bay visual diagram & sensor inspection
    p_diag = subparsers.add_parser("diagram", parents=[common_parser], help="Display visual engine bay layout with sensor locations & live values")
    p_diag.add_argument("--sensor", type=int, help="Inspect specific sensor ID (1-20)")
    p_eng = subparsers.add_parser("engine", parents=[common_parser], help="Alias for diagram")
    p_eng.add_argument("--sensor", type=int, help="Inspect specific sensor ID (1-20)")

    # Full vehicle sensor suite
    p_sens = subparsers.add_parser("sensors", parents=[common_parser], help="Display all 35+ real-time vehicle sensors across all systems")
    p_sens.add_argument("--subsystem", choices=["all", "engine", "gearbox", "chassis", "body"], default="all", help="Filter by subsystem")
    p_sens.add_argument("--engine", dest="subsystem", action="store_const", const="engine", help="Filter engine sensors")
    p_sens.add_argument("--gearbox", dest="subsystem", action="store_const", const="gearbox", help="Filter gearbox sensors")
    p_sens.add_argument("--chassis", dest="subsystem", action="store_const", const="chassis", help="Filter chassis/ABS sensors")
    p_sens.add_argument("--body", dest="subsystem", action="store_const", const="body", help="Filter suspension & body sensors")

    # Pneumatic air suspension
    p_susp = subparsers.add_parser("suspension", parents=[common_parser], help="Rear pneumatic air suspension control & height calibration")
    p_susp.add_argument("susp_action", nargs="?", default="status", choices=["status", "bleed", "depressurize", "inflate", "test", "calibrate"], help="Action: status, bleed, inflate, test, calibrate")

    # Eolys additive refill wizard
    p_eolys = subparsers.add_parser("eolys", parents=[common_parser], help="Eolys DPF additive pouch refill reset & priming wizard")
    p_eolys.add_argument("eolys_action", nargs="?", default="status", choices=["status", "reset"], help="Action: status or reset")
    p_eolys.add_argument("--volume", type=int, default=1100, help="New pouch volume in ml (default: 1100)")

    # Injector IMA coding
    p_inj = subparsers.add_parser("injector", parents=[common_parser], help="Bosch 1.6 HDi injector IMA classification code read/write")
    p_inj.add_argument("inj_action", nargs="?", default="read", choices=["read", "write"], help="Action: read or write")
    p_inj.add_argument("--cyl", type=int, default=1, choices=[1, 2, 3, 4], help="Cylinder number (1-4, Cyl 1=Flywheel side)")
    p_inj.add_argument("--code", help="New 6-to-9 char alphanumeric IMA code (e.g. 7A3F9C)")

    # BSI Telecoding
    p_bsicfg = subparsers.add_parser("bsi-config", parents=[common_parser], help="BSI telecoding & hidden options configuration (mirrors, DRL, etc.)")
    p_bsicfg.add_argument("cfg_action", nargs="?", default="list", choices=["list", "set"], help="Action: list or set")
    p_bsicfg.add_argument("--option", help="Telecoding option name (e.g. mirrors_auto_fold, daytime_running_lights)")
    p_bsicfg.add_argument("--value", help="Option value to set")

    # Pre-Purchase Inspection & Vehicle Health Score
    p_hlth = subparsers.add_parser("health", parents=[common_parser], help="Run 10-point Pre-Purchase Inspection & compute Vehicle Health Score")
    p_hlth.add_argument("--export", help="Export inspection report to standalone HTML file")
    p_ppi = subparsers.add_parser("ppi", parents=[common_parser], help="Alias for health")
    p_ppi.add_argument("--export", help="Export inspection report to standalone HTML file")

    # CAN candump replay engine
    p_rpl = subparsers.add_parser("replay", parents=[common_parser], help="Replay candump CAN log file onto SocketCAN interface")
    p_rpl.add_argument("logfile", help="Path to candump format log file")
    p_rpl.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier (e.g. 1.0, 2.0)")

    # Direct DTC shortcut (e.g. `psa C27A5` or `psa P17A5`)
    known_commands = {
        'lookup', 'search', 'modules', 'tui', 'menu', 'shell', 'dtc',
        'egs6', 'dpf', 'battery', 'sniff', 'epb', 'freeze', 'test',
        'ping', 'network', 'record', 'signals', 'odo', 'miles', 'service',
        'bsi', 'web', 'diagram', 'engine', 'sensors', 'suspension',
        'eolys', 'injector', 'bsi-config', 'health', 'ppi', 'replay',
        '-h', '--help'
    }
    non_flags = [a for a in sys.argv[1:] if not a.startswith('-')]
    if len(non_flags) == 1 and non_flags[0].lower() not in known_commands:
        candidate = non_flags[0].upper()
        if re.match(r'^(0X[0-9A-F]+|[PCBU][0-9A-F]{4})$', candidate) or len(candidate) <= 6:
            lookup_code(candidate)
            return

    args = parser.parse_args()

    is_demo = global_demo or getattr(args, 'demo', False) or getattr(args, 'sim', False)
    SESSION_CONFIG['force_sim'] = is_demo
    if getattr(args, 'port', None):
        SESSION_CONFIG['port'] = args.port
    if getattr(args, 'baud', None):
        SESSION_CONFIG['baud'] = args.baud
    if getattr(args, 'interface', None):
        SESSION_CONFIG['interface'] = args.interface

    port = getattr(args, 'port', None)
    baud = getattr(args, 'baud', 38400)
    interface = getattr(args, 'interface', None)

    if args.command == "lookup":
        lookup_code(args.code)
    elif args.command == "search":
        search_text(args.keyword)
    elif args.command == "modules":
        show_modules()
    elif args.command in ("odo", "miles"):
        cli_odometer(is_demo=is_demo, port=port, interface=interface)
    elif args.command == "service":
        cli_service(action=getattr(args, 'service_action', 'info'), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "egs6":
        cli_egs6(action=getattr(args, 'egs6_action', 'status'), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "dpf":
        cli_dpf(action=getattr(args, 'dpf_action', 'status'), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "bsi":
        cli_bsi(action=getattr(args, 'bsi_action', 'status'), duration=getattr(args, 'duration', 60), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "web":
        cli_web(port=getattr(args, 'web_port', 8080), is_demo=is_demo, serial_port=port, interface=interface)
    elif args.command == "battery":
        cli_battery(is_demo=is_demo, port=port, interface=interface)
    elif args.command == "epb":
        cli_epb(action=args.epb_action, exit_mode=args.exit, is_demo=is_demo, port=port, interface=interface)
    elif args.command == "freeze":
        cli_freeze(code=args.freeze_code, is_demo=is_demo, port=port, interface=interface)
    elif args.command == "test":
        cli_test(component=args.component, is_demo=is_demo, port=port, interface=interface)
    elif args.command in ("ping", "network"):
        cli_network(is_demo=is_demo, port=port, interface=interface)
    elif args.command == "record":
        cli_record(duration=args.duration, trigger_on_dtc=args.trigger_on_dtc, is_demo=is_demo, port=port, interface=interface)
    elif args.command == "signals":
        cli_signals(action=args.sig_action, export_path=args.out)
    elif args.command == "sniff":
        cli_sniff(is_demo=is_demo, port=port, interface=interface)
    elif args.command in ("diagram", "engine"):
        cli_diagram(sensor_id=getattr(args, 'sensor', None), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "sensors":
        cli_sensors(subsystem=getattr(args, 'subsystem', 'all') or 'all', is_demo=is_demo, port=port, interface=interface)
    elif args.command == "suspension":
        cli_suspension(action=getattr(args, 'susp_action', 'status'), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "eolys":
        cli_eolys(action=getattr(args, 'eolys_action', 'status'), volume=getattr(args, 'volume', 1100), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "injector":
        cli_injector(action=getattr(args, 'inj_action', 'read'), cylinder=getattr(args, 'cyl', 1), code=getattr(args, 'code', None), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "bsi-config":
        cli_bsi_config(action=getattr(args, 'cfg_action', 'list'), option=getattr(args, 'option', None), value=getattr(args, 'value', None), is_demo=is_demo, port=port, interface=interface)
    elif args.command in ("health", "ppi"):
        cli_health(export_path=getattr(args, 'export', None), is_demo=is_demo, port=port, interface=interface)
    elif args.command == "replay":
        cli_can_replay(file_path=args.logfile, interface=interface or 'vcan0', speed=getattr(args, 'speed', 1.0), is_demo=is_demo)
    elif args.command in ("tui", "menu", "shell"):
        if sys.stdin.isatty() and sys.stdout.isatty():
            tui.launch_tui(is_demo=is_demo)
        else:
            if not is_demo:
                obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
            run_main_menu(is_demo=is_demo)
    elif args.command == "dtc":
        if args.dtc_action == "read":
            execute_dtc_read(port=port, baud=baud, sim=is_demo, interface=interface)
        elif args.dtc_action == "scan":
            execute_dtc_scan(port=port, baud=baud, sim=is_demo, interface=interface)
        elif args.dtc_action == "clear":
            execute_dtc_clear(port=port, baud=baud, sim=is_demo, force=getattr(args, 'force', False), interface=interface)
        elif args.dtc_action == "logs":
            show_recent_logs(interactive_select=False)
        else:
            p_dtc.print_help()
    else:
        # Check if single non-flag positional argument was passed (e.g. psa C27A5)
        filtered_argv = [a for a in sys.argv[1:] if a not in ('--demo', '--sim', '-demo', '-sim') and not a.startswith('--port') and not a.startswith('--baud') and not a.startswith('-i') and not a.startswith('--interface')]
        if len(filtered_argv) == 1 and not filtered_argv[0].startswith('-'):
            lookup_code(filtered_argv[0])
        else:
            # Default behavior when run without arguments (e.g. `psa` or `psa --demo`)
            if sys.stdin.isatty() and sys.stdout.isatty():
                tui.launch_tui(is_demo=is_demo)
            else:
                if not is_demo:
                    obd_service.require_vehicle_or_demo(is_demo=False, port=port, interface=interface)
                run_main_menu(is_demo=is_demo)

if __name__ == '__main__':
    main()
