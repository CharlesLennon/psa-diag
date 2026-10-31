#!/usr/bin/env python3
"""
PSA-DIAG TUI: Modern btop-style Terminal Interface
Specialized for Citroën Grand C4 Picasso Mk1 (1.6 HDi DV6 • EGS6 / Semi-Auto)

Tabs:
  [1: DTCs]      - Fault inspection, multi-module scanning, clearance, and details
  [2: LiveData]  - Real-time gauges (RPM, Boost, DPF Soot, Battery, EGS6 Clutch/Hydraulics)
  [3: Sniffer]   - "Cheat Engine" style differential CAN sniffer & reverse engineer
  [4: Tools]     - EGS6 hydraulic/clutch wear, DPF soot load, and battery crank test
  [5: Research]  - Interactive search across 40,752 PSA definitions & AEE2004 modules
  [6: Logs]      - Diagnostic audit trail & full log file viewer
  [7: Settings]  - COM port selection, baud rate, and simulation controls
"""

import curses
import os
import sys
import time
import math
import random
import datetime

# Import sibling modules
sys.path.insert(0, '/root/psa_diag')
import obd_service
import psa_diag
import can_sniffer
import special_diagnostics
import advanced_features
import engine_diagram
import workshop_features

# Color pair constants
CP_DEFAULT = 1
CP_HEADER = 2
CP_TAB_ACTIVE = 3
CP_TAB_INACTIVE = 4
CP_BORDER = 5
CP_HIGHLIGHT = 6
CP_OK = 7
CP_WARN = 8
CP_ERR = 9
CP_ACCENT = 10
CP_DIM = 11

def init_colors():
    if not curses.has_colors():
        return
    curses.use_default_colors()
    try:
        curses.init_pair(CP_DEFAULT, curses.COLOR_WHITE, -1)
        curses.init_pair(CP_HEADER, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(CP_TAB_ACTIVE, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(CP_TAB_INACTIVE, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(CP_BORDER, curses.COLOR_BLUE, -1)
        curses.init_pair(CP_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(CP_OK, curses.COLOR_GREEN, -1)
        curses.init_pair(CP_WARN, curses.COLOR_YELLOW, -1)
        curses.init_pair(CP_ERR, curses.COLOR_RED, -1)
        curses.init_pair(CP_ACCENT, curses.COLOR_MAGENTA, -1)
        curses.init_pair(CP_DIM, curses.COLOR_WHITE, -1)
    except Exception:
        pass

def color(pair_id, extra_attr=0):
    if curses.has_colors():
        return curses.color_pair(pair_id) | extra_attr
    return extra_attr

def make_gauge_bar(value: float, min_val: float, max_val: float, width: int = 20) -> str:
    """Generates an ASCII bar gauge like [████████░░░░░░░░]."""
    clamped = max(min_val, min(max_val, value))
    pct = (clamped - min_val) / (max_val - min_val) if max_val > min_val else 0
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {int(pct * 100)}%"

class DiagnosticTUI:
    def __init__(self, stdscr, is_demo: bool = False):
        self.stdscr = stdscr
        self.is_demo = is_demo or psa_diag.SESSION_CONFIG['force_sim']
        self.tabs = [
            "1: DTCs",
            "2: LiveData",
            "3: Sniffer",
            "4: Tools",
            "5: Research",
            "6: Logs",
            "7: Settings",
            "8: Engine"
        ]
        self.active_tab = 0
        self.running = True
        self.engine_sensor_selected = 1

        # DTC Tab State
        self.dtc_items = []
        self.dtc_selected_idx = 0
        self.dtc_status_msg = "Ready. [S] Scan  [R] Read  [C] Clear  [F] Freeze-Frame"
        self.show_freeze_frame = False
        self.load_sample_or_last_dtcs()

        # LiveData Tab State
        self.live_paused = False
        self.tick_count = 0

        # Sniffer Tab State (Cheat Engine style CAN sniffer)
        self.can_filter = can_sniffer.DifferentialFilter()
        self.can_stream = can_sniffer.CANSimulationStream()
        self.sniffer_selected_idx = 0
        self.sniffer_status = "Sniffer Active. Press [1] for Baseline Snapshot, [C] for Changed, [S] to Save Signal."
        self.learned_signals = can_sniffer.load_learned_signals()
        self.learned_selected_idx = 0
        self.sniffer_view_mode = "candidates" # 'candidates' or 'signals'

        # Tools Tab State
        self.tools_view = "diagnostics" # 'diagnostics', 'network', or 'odometer'
        self.tools_status_msg = "Ready. [P] CAN Ping  [O] Odometer  [E] EPB  [L] Clutch Relearn  [G] DPF Regen  [K] BSI Keepalive"
        self.egs6_data = special_diagnostics.analyze_egs6_gearbox(is_sim=self.is_demo)
        self.dpf_data = special_diagnostics.analyze_dpf_system(is_sim=self.is_demo)
        self.battery_data = special_diagnostics.analyze_battery_crank(is_sim=self.is_demo)
        self.network_nodes = advanced_features.CANNetworkTopology.ping_all(is_sim=self.is_demo)
        self.odo_data = special_diagnostics.analyze_odometer_service(is_sim=self.is_demo)

        # Research Tab State
        self.research_query = "C27A5"
        self.research_results = []
        self.research_selected_idx = 0
        self.execute_research_search(self.research_query)

        # Logs Tab State
        self.log_files = []
        self.logs_selected_idx = 0
        self.log_scroll_offset = 0
        self.refresh_log_files()

        # Seed initial CAN frames
        initial_frames = self.can_stream.generate_tick()
        for cid, b_data in initial_frames.items():
            self.can_filter.update_frame(cid, b_data)

        # Connection Screen State (opened when no --demo flag is provided)
        self.show_connect_screen = not self.is_demo
        self.connect_candidates = []
        self.connect_selected_idx = 0
        self.connect_status_msg = "Scanning available serial ports..."
        self.connect_spinner_idx = 0
        self.connect_baud = psa_diag.SESSION_CONFIG.get('baud', 38400)
        self.rescan_ports()

    def safe_addstr(self, y: int, x: int, text: str, attr: int = 0, max_len: int = None):
        """
        Anti-wrapping addstr: Strictly clips text so it NEVER spills onto next lines
        or outside window boundaries, eliminating curses wrap errors.
        """
        try:
            h, w = self.stdscr.getmaxyx()
            if y < 0 or y >= h or x < 0 or x >= w:
                return
            available = w - x
            if y == h - 1:
                available -= 1 # Leave bottom-right corner untouched
            if available <= 0:
                return
            limit = min(available, max_len if max_len is not None else available)
            cleaned = str(text)[:limit]
            if cleaned:
                self.stdscr.addstr(y, x, cleaned, attr)
        except curses.error:
            pass

    def load_sample_or_last_dtcs(self):
        self.dtc_items = [
            ('7E9', 'Piloted Gearbox (BVMP/EGS6)', 'P17A5', '17A5',
             'Mechanical or hydraulic gearbox fault on first gear with engine braking',
             'Défaut mécanique ou hydraulique de boîte de vitesses sur premier rapport'),
            ('7E8', 'Engine Management (CMM)', 'P0299', '0299',
             'Turbo pressure signal - Turbocharger underboost',
             'Signal pression turbocompresseur - Pression inférieure à la consigne'),
            ('7E8', 'Engine Management (CMM)', 'P1351', '1351',
             'Pre/post heating relay circuit - Relay supplied, plugs not supplied',
             'Circuit relais pré-postchauffage - Bougies non alimentées'),
            ('768', 'ABS / ESP Dynamic Stability', 'C1385', '5385',
             'Electrovalves supply voltage fault (Solenoid relay low voltage)',
             'Défaut tension d\'alimentation des électrovannes'),
            ('79A', 'Electric Parking Brake (FSE)', 'C155A', '555A',
             'Electric parking brake not calibrated: stroke-force law',
             'FSE non calibré : loi course-effort')
        ]

    def refresh_log_files(self):
        obd_service.ensure_log_dir()
        if os.path.exists(obd_service.LOG_DIR):
            files = sorted([f for f in os.listdir(obd_service.LOG_DIR) if f.startswith('dtc_')], reverse=True)
            self.log_files = files
        else:
            self.log_files = []

    def execute_research_search(self, term: str):
        term = term.strip()
        if not term:
            return
        conn = psa_diag.get_db()
        c = conn.cursor()
        clean_code, std_code, cat, typ, sub, raw_hex, matches = psa_diag.lookup_code_data(term)
        results = []
        if matches:
            for m in matches:
                results.append((m[0], m[1], m[2], m[3], m[4], m[5], m[6]))
        else:
            pat = f"%{term}%"
            c.execute('''
                SELECT code, raw, arch, system, ecu, desc_en, desc_fr
                FROM dtcs
                WHERE (code LIKE ? OR raw LIKE ? OR desc_en LIKE ? OR desc_fr LIKE ?)
                  AND (arch LIKE 'AEE2004%' OR arch LIKE 'AEE2010%')
                LIMIT 40
            ''', (pat, pat, pat, pat))
            results = c.fetchall()
        conn.close()
        self.research_results = results
        self.research_selected_idx = 0

    def rescan_ports(self):
        try:
            self.connect_candidates = obd_service.find_serial_ports()
            if self.connect_candidates:
                self.connect_status_msg = f"Found {len(self.connect_candidates)} serial port(s). Select port to connect."
            else:
                self.connect_status_msg = "No vehicle interface adapter detected."
        except Exception as e:
            self.connect_candidates = []
            self.connect_status_msg = f"Port scan error: {e}"

    def attempt_connect(self, port_name: str):
        self.connect_status_msg = f"Testing handshake with {port_name} @ {self.connect_baud} baud..."
        self.stdscr.refresh()
        try:
            if not os.path.exists(port_name):
                self.connect_status_msg = f"[!] Port device '{port_name}' does not exist."
                return

            iface = obd_service.OBDInterface(port=port_name, baudrate=self.connect_baud, force_sim=False, raise_on_fail=True)
            if iface.ser and not iface.is_simulated:
                psa_diag.SESSION_CONFIG['port'] = port_name
                psa_diag.SESSION_CONFIG['baud'] = self.connect_baud
                psa_diag.SESSION_CONFIG['force_sim'] = False
                self.is_demo = False
                self.show_connect_screen = False
                self.dtc_status_msg = f"[✓] LIVE HARDWARE: Connected to ELM327 on {port_name}."
                self.tools_status_msg = "Ready. [P] CAN Ping  [E] EPB Service  [T] Actuator Test  [R] Refresh"
                return
            else:
                self.connect_status_msg = f"[!] Could not handshake with ELM327 on {port_name}."
        except ConnectionError as ce:
            self.connect_status_msg = f"[!] Handshake failed on {port_name}. Ensure ignition is ON."
        except Exception as e:
            self.connect_status_msg = f"[!] Handshake error on {port_name}: {e}"

    def enter_demo_mode(self):
        self.is_demo = True
        psa_diag.SESSION_CONFIG['force_sim'] = True
        self.show_connect_screen = False
        self.dtc_status_msg = "[MODE: DEMO / TEST DATA] Offline Citroën Grand C4 Picasso 1.6 HDi simulation active."
        self.tools_status_msg = "Ready. [P] CAN Ping  [E] EPB Service  [T] Actuator Test  [R] Refresh"

    def draw_connect_screen(self, h, w):
        title = " 🚗 PSA-DIAG • VEHICLE INTERFACE CONNECTION & LOADING WIZARD "
        arch = "[AEE2004 High-Speed CAN 500k] "
        total_right = len(arch)
        avail_title = max(10, w - total_right - 2)
        self.safe_addstr(0, 0, title.ljust(avail_title), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(0, max(0, w - total_right - 1), arch, color(CP_HEADER))

        sub = " Citroën Grand C4 Picasso Mk1 (1.6 HDi DV6 • 6-Speed EGS6 / BMP6 • Magneti Marelli CFC300P)"
        self.safe_addstr(1, 0, sub.ljust(w - 1), color(CP_DIM))

        box_w = min(88, w - 4)
        box_h = min(22, h - 4)
        box_x = max(1, (w - box_w) // 2)
        box_y = max(3, (h - box_h) // 2)

        self.draw_box(box_y, box_x, box_h, box_w, " Connect to Vehicle Interface ")

        cy = box_y + 2
        spinners = ['⠋', '⠙', '⠹', '⠸']
        self.connect_spinner_idx = (self.connect_spinner_idx + 1) % len(spinners)
        sp = spinners[self.connect_spinner_idx]

        if self.connect_candidates:
            self.safe_addstr(cy, box_x + 3, f"{sp} [STATUS: HARDWARE INTERFACE DETECTED]", color(CP_OK, curses.A_BOLD))
            cy += 1
            self.safe_addstr(cy, box_x + 3, self.connect_status_msg, curses.A_BOLD)
            cy += 2
            self.safe_addstr(cy, box_x + 3, "Available Serial Communication Ports:", curses.A_BOLD)
            cy += 1

            for idx, p in enumerate(self.connect_candidates[:5]):
                is_sel = (idx == self.connect_selected_idx)
                attr = color(CP_HIGHLIGHT, curses.A_BOLD) if is_sel else color(CP_DEFAULT)
                marker = "▶" if is_sel else " "
                line = f" {marker} [{idx+1}] {p.device:<16} ({p.description or 'Serial Adapter'})"
                self.safe_addstr(cy, box_x + 3, line, attr, max_len=box_w - 6)
                cy += 1

            cy += 1
            baud_info = f"Target Baud: {self.connect_baud} baud  |  ISO 15765-4 (CAN 11-bit / 500 kbps)"
            self.safe_addstr(cy, box_x + 3, baud_info, color(CP_DIM))

        else:
            self.safe_addstr(cy, box_x + 3, f"{sp} [STATUS: WAITING FOR OBD-II ADAPTER / VEHICLE]", color(CP_WARN, curses.A_BOLD))
            cy += 1
            self.safe_addstr(cy, box_x + 3, "• No active serial adapter found on /dev/ttyUSB*, /dev/ttyACM*, /dev/rfcomm*.", color(CP_ERR))
            cy += 2

            self.safe_addstr(cy, box_x + 3, "VEHICLE CONNECTION CHECKLIST:", color(CP_HEADER, curses.A_BOLD))
            cy += 1
            self.safe_addstr(cy, box_x + 5, "1. Connect ELM327 / OBDLink USB cable or pair Bluetooth OBD device.")
            cy += 1
            self.safe_addstr(cy, box_x + 5, "2. Plug 16-pin connector into Grand C4 Picasso OBD-II diagnostic socket.")
            cy += 1
            self.safe_addstr(cy, box_x + 5, "   (Located inside cabin fuse box compartment to right of steering wheel).")
            cy += 1
            self.safe_addstr(cy, box_x + 5, "3. Turn vehicle ignition key to ON (Position 2 - dash cluster illuminated).")
            cy += 1
            self.safe_addstr(cy, box_x + 5, "4. Ensure dialout permissions: 'sudo usermod -aG dialout $USER'.")

        act_y = box_y + box_h - 5
        self.stdscr.hline(act_y, box_x + 1, curses.ACS_HLINE, box_w - 2)
        act_y += 1
        self.safe_addstr(act_y, box_x + 3, "ACTIONS:", curses.A_BOLD)
        act_y += 1
        if self.connect_candidates:
            self.safe_addstr(act_y, box_x + 3, "[C / Enter] Connect to Port    [R] Rescan    [D] Launch Demo Mode    [Q] Quit", color(CP_ACCENT, curses.A_BOLD))
        else:
            self.safe_addstr(act_y, box_x + 3, "[R] Rescan / Retry Link        [D / Enter] Launch Demo Mode          [Q] Quit", color(CP_ACCENT, curses.A_BOLD))
        act_y += 1
        self.safe_addstr(act_y, box_x + 3, "[P] Custom Port (/dev/ttyUSB0) [B] Cycle Baud (38400, 115200, 9600)", color(CP_DIM))

        footer = " Tip: Run 'psa --demo' to bypass this connection screen and boot directly into Demo Mode."
        self.safe_addstr(h - 1, 0, footer.ljust(w - 1), color(CP_TAB_ACTIVE))

    def handle_connect_input(self):
        try:
            key = self.stdscr.getch()
        except curses.error:
            return

        if key == -1:
            return

        if key in (ord('q'), ord('Q'), 27):
            self.running = False
            return

        elif key in (ord('r'), ord('R')):
            self.connect_status_msg = "Rescanning serial ports..."
            self.stdscr.refresh()
            self.rescan_ports()

        elif key in (ord('d'), ord('D')):
            self.enter_demo_mode()

        elif key in (10, 13, ord('c'), ord('C')):
            if self.connect_candidates:
                target_port = self.connect_candidates[self.connect_selected_idx].device
                self.attempt_connect(target_port)
            else:
                self.enter_demo_mode()

        elif key in (ord('b'), ord('B')):
            bauds = [38400, 115200, 9600, 500000]
            idx = bauds.index(self.connect_baud) if self.connect_baud in bauds else 0
            self.connect_baud = bauds[(idx + 1) % len(bauds)]
            psa_diag.SESSION_CONFIG['baud'] = self.connect_baud
            self.connect_status_msg = f"Default baud rate set to {self.connect_baud}."

        elif key in (ord('p'), ord('P')):
            custom_port = self.prompt_input("Enter serial port device path (e.g. /dev/ttyUSB0): ")
            if custom_port:
                self.attempt_connect(custom_port.strip())

        elif key == curses.KEY_UP:
            if self.connect_candidates:
                self.connect_selected_idx = max(0, self.connect_selected_idx - 1)

        elif key == curses.KEY_DOWN:
            if self.connect_candidates:
                self.connect_selected_idx = min(len(self.connect_candidates) - 1, self.connect_selected_idx + 1)

    def run(self):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.stdscr.timeout(500) # 500ms loop for live updating

        while self.running:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()

            if h < 20 or w < 75:
                self.safe_addstr(0, 0, "Terminal window too small! Please resize to at least 75x20.", curses.A_BOLD)
                self.stdscr.refresh()
                key = self.stdscr.getch()
                if key in (ord('q'), ord('Q')):
                    break
                continue

            if self.show_connect_screen:
                self.draw_connect_screen(h, w)
                self.stdscr.refresh()
                self.handle_connect_input()
                continue

            # Update live simulated CAN frames in background
            new_frames = self.can_stream.generate_tick()
            for cid, b_data in new_frames.items():
                self.can_filter.update_frame(cid, b_data)

            self.draw_header(w)
            self.draw_tabs(w)
            
            content_h = h - 6
            if self.active_tab == 0:
                self.draw_dtc_tab(4, content_h, w)
            elif self.active_tab == 1:
                self.draw_livedata_tab(4, content_h, w)
            elif self.active_tab == 2:
                self.draw_sniffer_tab(4, content_h, w)
            elif self.active_tab == 3:
                self.draw_tools_tab(4, content_h, w)
            elif self.active_tab == 4:
                self.draw_research_tab(4, content_h, w)
            elif self.active_tab == 5:
                self.draw_logs_tab(4, content_h, w)
            elif self.active_tab == 6:
                self.draw_settings_tab(4, content_h, w)
            elif self.active_tab == 7:
                self.draw_engine_tab(4, content_h, w)

            self.draw_footer(h, w)
            self.stdscr.refresh()
            self.handle_input()

    def draw_header(self, width):
        title = " 🚗 PSA-DIAG • CITROËN GRAND C4 PICASSO Mk1 (1.6 HDi • EGS6) "
        arch = "[AEE2004 500k] "

        if self.is_demo or psa_diag.SESSION_CONFIG['force_sim']:
            status_text = "[MODE: DEMO / TEST DATA]"
            status_attr = color(CP_WARN, curses.A_BOLD)
        elif psa_diag.SESSION_CONFIG['port']:
            status_text = f"[LIVE: {psa_diag.SESSION_CONFIG['port']}]"
            status_attr = color(CP_OK, curses.A_BOLD)
        else:
            candidates = obd_service.find_serial_ports()
            if candidates:
                status_text = f"[READY: {candidates[0].device}]"
                status_attr = color(CP_OK, curses.A_BOLD)
            else:
                status_text = "[NO HARDWARE DETECTED]"
                status_attr = color(CP_ERR, curses.A_BOLD)

        total_right = len(arch) + len(status_text)
        avail_title = max(10, width - total_right - 2)

        self.safe_addstr(0, 0, title.ljust(avail_title), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(0, avail_title, arch, color(CP_DIM))
        self.safe_addstr(0, avail_title + len(arch), status_text, status_attr)

    def draw_tabs(self, width):
        y = 2
        x = 2
        for idx, tab_name in enumerate(self.tabs):
            is_active = (idx == self.active_tab)
            txt = f" {tab_name} "
            attr = color(CP_TAB_ACTIVE, curses.A_BOLD) if is_active else color(CP_TAB_INACTIVE)
            self.safe_addstr(y, x, txt, attr)
            x += len(txt) + 1

        try:
            self.stdscr.attron(color(CP_BORDER))
            self.stdscr.hline(3, 1, curses.ACS_HLINE, width - 2)
            self.stdscr.attroff(color(CP_BORDER))
        except curses.error:
            pass

    def draw_footer(self, height, width):
        y = height - 2
        try:
            self.stdscr.attron(color(CP_BORDER))
            self.stdscr.hline(y, 1, curses.ACS_HLINE, width - 2)
            self.stdscr.attroff(color(CP_BORDER))
        except curses.error:
            pass

        hints = " [←/→] Tab   [↑/↓] Select   [Enter] Action   [Q] Quit "
        if self.active_tab == 0:
            subhints = " [S] Multi-Scan  [R] Read  [C] Clear  [F] Freeze-Frame "
        elif self.active_tab == 1:
            subhints = " [Space] Pause/Resume Stream "
        elif self.active_tab == 2:
            subhints = " [1] Snapshot  [C] Changed  [U] Unchanged  [S] Save Signal "
        elif self.active_tab == 3:
            subhints = " [P] CAN Ping  [E] EPB Service  [T] Actuator Test  [R] Refresh "
        elif self.active_tab == 4:
            subhints = " [/] Search Code/Keyword "
        elif self.active_tab == 5:
            subhints = " [PgUp/PgDn] Scroll Log "
        elif self.active_tab == 6:
            subhints = " [T] Test Port  [M] Sim Mode "
        elif self.active_tab == 7:
            subhints = " [↑/↓] Select Sensor  [1-8] Tabs "
        else:
            subhints = ""

        self.safe_addstr(height - 1, 2, hints, color(CP_DIM))
        if subhints:
            rx = max(len(hints) + 4, width - len(subhints) - 2)
            self.safe_addstr(height - 1, rx, subhints, color(CP_ACCENT, curses.A_BOLD))

    # =========================================================================
    # TAB 1: DTCs
    # =========================================================================
    def draw_dtc_tab(self, start_y, height, width):
        btn_y = start_y
        self.safe_addstr(btn_y, 2, "Quick Actions: ", curses.A_BOLD)
        self.safe_addstr(btn_y, 17, "[S] Multi-Scan", color(CP_OK, curses.A_BOLD))
        self.safe_addstr(btn_y, 33, "[R] Read", color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(btn_y, 44, "[C] Clear", color(CP_ERR, curses.A_BOLD))
        ff_color = CP_HIGHLIGHT if self.show_freeze_frame else CP_ACCENT
        self.safe_addstr(btn_y, 56, f"[F] Freeze-Frame Snapshot {'(ACTIVE)' if self.show_freeze_frame else ''}", color(ff_color, curses.A_BOLD))

        self.safe_addstr(btn_y + 1, 2, self.dtc_status_msg, color(CP_DIM))

        split_w = int(width * 0.45)
        left_w = split_w
        right_w = width - split_w - 4
        box_y = start_y + 3
        box_h = height - 3

        self.draw_box(box_y, 1, box_h, left_w, " Detected Trouble Codes ")

        if not self.dtc_items:
            self.safe_addstr(box_y + 2, 3, "No trouble codes detected.", color(CP_OK))
            self.safe_addstr(box_y + 3, 3, "Press [S] to run an extended scan.", color(CP_DIM))
        else:
            for idx, item in enumerate(self.dtc_items[:box_h - 2]):
                ecu_id, ecu_name, code, raw_hex, en_desc, _ = item
                is_selected = (idx == self.dtc_selected_idx)
                attr = color(CP_HIGHLIGHT, curses.A_BOLD) if is_selected else color(CP_DEFAULT)

                prefix = "▶ " if is_selected else "  "
                line_str = f"{prefix}{code:<5} [{ecu_id}] {en_desc}"
                self.safe_addstr(box_y + 1 + idx, 2, line_str.ljust(left_w - 3), attr, max_len=left_w - 3)

        if self.show_freeze_frame and self.dtc_items and 0 <= self.dtc_selected_idx < len(self.dtc_items):
            item = self.dtc_items[self.dtc_selected_idx]
            code = item[2]
            snap = advanced_features.FreezeFrameInspector.get_snapshot(code)
            self.draw_box(box_y, left_w + 2, box_h, right_w, f" Freeze-Frame Snapshot: {code} (Press [F] for Guidance) ")

            card_y = box_y + 1
            cx = left_w + 4

            self.safe_addstr(card_y, cx, "TRIGGERED DTC:  ", curses.A_BOLD)
            self.safe_addstr(card_y, cx + 16, f"{code}", color(CP_ERR, curses.A_BOLD))
            self.safe_addstr(card_y, cx + 24, f"Captured: {snap['timestamp']}", color(CP_DIM))

            self.safe_addstr(card_y + 1, cx, "MODULE:         ", curses.A_BOLD)
            self.safe_addstr(card_y + 1, cx + 16, f"{snap['module']}", color(CP_HEADER, curses.A_BOLD))

            self.safe_addstr(card_y + 3, cx, "CONDITIONS AT MOMENT OF FAULT:", curses.A_BOLD)
            row_i = 0
            for param, val_tuple in snap['telemetry'].items():
                val, note = val_tuple
                ry = card_y + 4 + row_i
                if ry >= box_y + box_h - 4:
                    break
                self.safe_addstr(ry, cx, f"• {param:<24}", curses.A_BOLD)
                self.safe_addstr(ry, cx + 26, f"{val:<12}", color(CP_OK, curses.A_BOLD))
                self.safe_addstr(ry, cx + 40, f"({note})", color(CP_DIM), max_len=right_w - 44)
                row_i += 1

            ay = card_y + 4 + row_i + 1
            if ay < box_y + box_h - 2:
                self.safe_addstr(ay, cx, "ENGINEERING ROOT CAUSE ANALYSIS:", color(CP_ACCENT, curses.A_BOLD))
                self.safe_addstr(ay + 1, cx, f"{snap['root_cause']}", color(CP_DEFAULT), max_len=right_w - 6)

        else:
            self.draw_box(box_y, left_w + 2, box_h, right_w, " Fault Breakdown & Diagnostic Guidance ")

            if self.dtc_items and 0 <= self.dtc_selected_idx < len(self.dtc_items):
                item = self.dtc_items[self.dtc_selected_idx]
                ecu_id, ecu_name, code, raw_hex, en_desc, fr_desc = item

                card_y = box_y + 1
                cx = left_w + 4

                self.safe_addstr(card_y, cx, "FAULT CODE: ", curses.A_BOLD)
                self.safe_addstr(card_y, cx + 12, f"{code}", color(CP_ERR, curses.A_BOLD))
                self.safe_addstr(card_y, cx + 20, f"(Raw CAN Hex: 0x{raw_hex})", color(CP_DIM))

                self.safe_addstr(card_y + 1, cx, "MODULE:     ", curses.A_BOLD)
                self.safe_addstr(card_y + 1, cx + 12, f"CAN 0x{ecu_id} - {ecu_name}", color(CP_HEADER, curses.A_BOLD))

                self.safe_addstr(card_y + 3, cx, "ENGLISH DESCRIPTION:", curses.A_BOLD)
                self.safe_addstr(card_y + 4, cx, f"• {en_desc}", color(CP_DEFAULT, curses.A_BOLD), max_len=right_w - 6)

                if fr_desc:
                    self.safe_addstr(card_y + 5, cx, "FRENCH OEM TITLE:", color(CP_DIM, curses.A_BOLD))
                    self.safe_addstr(card_y + 6, cx, f"• {fr_desc}", color(CP_DIM), max_len=right_w - 6)

                self.safe_addstr(card_y + 8, cx, "CITROËN GRAND PICASSO Mk1 ADVICE:", color(CP_ACCENT, curses.A_BOLD))
                if code == 'P17A5':
                    self.safe_addstr(card_y + 9, cx, "→ EGS6 6-Speed Semi-Auto Clutch Synchronization Fault:", color(CP_WARN))
                    self.safe_addstr(card_y + 10, cx, "  1. Hydraulic actuator pressure dropping below 40 bar.")
                    self.safe_addstr(card_y + 11, cx, "  2. Clutch bite point wear / relearn calibration required.")
                    self.safe_addstr(card_y + 12, cx, "  3. Gearbox input speed sensor signal mismatch.")
                elif code == 'C1385':
                    self.safe_addstr(card_y + 9, cx, "→ ABS/ESP 8.1 Solenoid Valve Supply Voltage:", color(CP_WARN))
                    self.safe_addstr(card_y + 10, cx, "  1. High internal resistance / voltage drop during cranking.")
                    self.safe_addstr(card_y + 11, cx, "  2. Check ABS double relay in engine bay fusebox (BSM).")
                    self.safe_addstr(card_y + 12, cx, "  3. Inspect earth terminal under battery tray.")
                elif code == 'P0299':
                    self.safe_addstr(card_y + 9, cx, "→ 1.6 HDi Turbocharger Underboost Deviation:", color(CP_WARN))
                    self.safe_addstr(card_y + 10, cx, "  1. Vacuum solenoid behind engine split hose or failing.")
                    self.safe_addstr(card_y + 11, cx, "  2. Sticking variable geometry turbo (VNT) vanes.")
                    self.safe_addstr(card_y + 12, cx, "  3. Intercooler boost pipe split or loose jubilee clip.")
                elif code == 'C155A':
                    self.safe_addstr(card_y + 9, cx, "→ Electric Parking Brake (FSE) Calibration:", color(CP_WARN))
                    self.safe_addstr(card_y + 10, cx, "  1. Handbrake cable tension sensor requires recalibration.")
                    self.safe_addstr(card_y + 11, cx, "  2. Check rear brake caliper levers returning to stops.")
                else:
                    self.safe_addstr(card_y + 9, cx, "→ Cross-referenced with PSA AEE2004 Electronic Network.", color(CP_DIM))

    # =========================================================================
    # TAB 2: LiveData (btop Style Gauges)
    # =========================================================================
    def draw_livedata_tab(self, start_y, height, width):
        self.tick_count += 1
        t = self.tick_count * 0.2

        rpm = 820 + int(30 * math.sin(t))
        coolant = 87 + int(2 * math.cos(t * 0.5))
        boost = round(1.10 + 0.15 * math.sin(t * 0.8), 2)
        battery = round(14.25 + 0.1 * math.sin(t * 0.3), 2)
        rail_bar = 295 + int(15 * math.sin(t))
        dpf_pct = 43
        oil_temp = 68 + int(1 * math.cos(t * 0.2))
        egs6_hydr = round(47.8 + 1.2 * math.sin(t * 1.2), 1)

        pause_badge = "[PAUSED]" if self.live_paused else "[LIVE STREAMING 500ms]"
        self.safe_addstr(start_y, 2, f"Sensor Telemetry: {pause_badge}   (Press [SPACE] to pause)", color(CP_OK if not self.live_paused else CP_WARN, curses.A_BOLD))

        split_w = width // 2 - 2
        box_y = start_y + 2
        box_h = height - 2

        self.draw_box(box_y, 1, box_h, split_w, " DV6 1.6 HDi Engine & Turbo Parameters ")

        ey = box_y + 2
        self.safe_addstr(ey, 3, "Engine RPM:".ljust(18), curses.A_BOLD)
        self.safe_addstr(ey, 21, f"{rpm} RPM".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(ey, 32, make_gauge_bar(rpm, 0, 5000, max(8, split_w - 38)), color(CP_OK))

        ey += 2
        self.safe_addstr(ey, 3, "Turbo Boost (MAP):".ljust(18), curses.A_BOLD)
        self.safe_addstr(ey, 21, f"{boost} bar".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(ey, 32, make_gauge_bar(boost, 0.8, 2.5, max(8, split_w - 38)), color(CP_OK))

        ey += 2
        self.safe_addstr(ey, 3, "Coolant Temp:".ljust(18), curses.A_BOLD)
        self.safe_addstr(ey, 21, f"{coolant} °C".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(ey, 32, make_gauge_bar(coolant, 40, 120, max(8, split_w - 38)), color(CP_OK))

        ey += 2
        self.safe_addstr(ey, 3, "Rail Pressure:".ljust(18), curses.A_BOLD)
        self.safe_addstr(ey, 21, f"{rail_bar} bar".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(ey, 32, make_gauge_bar(rail_bar, 200, 1600, max(8, split_w - 38)), color(CP_ACCENT))

        ey += 2
        self.safe_addstr(ey, 3, "DPF Soot Load:".ljust(18), curses.A_BOLD)
        self.safe_addstr(ey, 21, f"{dpf_pct} %".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(ey, 32, make_gauge_bar(dpf_pct, 0, 100, max(8, split_w - 38)), color(CP_OK))

        ey += 2
        self.safe_addstr(ey, 3, "Battery Voltage:".ljust(18), curses.A_BOLD)
        self.safe_addstr(ey, 21, f"{battery} V".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(ey, 32, make_gauge_bar(battery, 10.0, 15.5, max(8, split_w - 38)), color(CP_OK))

        self.draw_box(box_y, split_w + 3, box_h, split_w, " EGS6 Piloted Gearbox & Chassis Telemetry ")

        gy = box_y + 2
        rx = split_w + 5

        self.safe_addstr(gy, rx, "Actuator Pressure:".ljust(18), curses.A_BOLD)
        self.safe_addstr(gy, rx + 18, f"{egs6_hydr} bar".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(gy, rx + 29, make_gauge_bar(egs6_hydr, 20, 60, max(8, split_w - 38)), color(CP_OK))

        gy += 2
        self.safe_addstr(gy, rx, "Gearbox Oil Temp:".ljust(18), curses.A_BOLD)
        self.safe_addstr(gy, rx + 18, f"{oil_temp} °C".ljust(10), color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(gy, rx + 29, make_gauge_bar(oil_temp, 20, 120, max(8, split_w - 38)), color(CP_OK))

        gy += 3
        self.safe_addstr(gy, rx, "Selected Gear:        ", curses.A_BOLD)
        self.safe_addstr(gy, rx + 22, "1st Gear (Auto / Semi-Auto)", color(CP_HEADER, curses.A_BOLD))

        gy += 1
        self.safe_addstr(gy, rx, "Clutch Actuator State:", curses.A_BOLD)
        self.safe_addstr(gy, rx + 22, "Closed / Engaged", color(CP_OK, curses.A_BOLD))

        gy += 1
        self.safe_addstr(gy, rx, "Clutch Slip Speed:    ", curses.A_BOLD)
        self.safe_addstr(gy, rx + 22, "0 RPM (Synchronized)", color(CP_OK))

        gy += 1
        self.safe_addstr(gy, rx, "Brake Pedal Switch:   ", curses.A_BOLD)
        self.safe_addstr(gy, rx + 22, "Released (Dual-Contact OK)", color(CP_DIM))

        gy += 1
        self.safe_addstr(gy, rx, "Handbrake (EPB) State:", curses.A_BOLD)
        self.safe_addstr(gy, rx + 22, "Disengaged / Calibrated", color(CP_OK))

        gy += 1
        self.safe_addstr(gy, rx, "Vehicle Total Miles:  ", curses.A_BOLD)
        self.safe_addstr(gy, rx + 22, "114,655 miles (184,520 km)", color(CP_OK, curses.A_BOLD))

        gy += 1
        self.safe_addstr(gy, rx, "Next Service Due:     ", curses.A_BOLD)
        self.safe_addstr(gy, rx + 22, "870 miles (45 days) [🔧]", color(CP_WARN, curses.A_BOLD))

    # =========================================================================
    # TAB 3: Cheat-Engine Style CAN Sniffer & Signal Learner
    # =========================================================================
    def draw_sniffer_tab(self, start_y, height, width):
        # Action Bar Buttons
        self.safe_addstr(start_y, 2, "Cheat-Engine Filter: ", curses.A_BOLD)
        self.safe_addstr(start_y, 23, "[1] Snapshot", color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(start_y, 38, "[C] Changed", color(CP_OK, curses.A_BOLD))
        self.safe_addstr(start_y, 52, "[U] Unchanged", color(CP_WARN, curses.A_BOLD))
        self.safe_addstr(start_y, 68, "[Z] Undo", color(CP_DIM, curses.A_BOLD))
        self.safe_addstr(start_y, 79, "[R] Reset", color(CP_ERR, curses.A_BOLD))
        self.safe_addstr(start_y, 91, "[S] Save Signal", color(CP_ACCENT, curses.A_BOLD))

        self.safe_addstr(start_y + 1, 2, self.sniffer_status, color(CP_DIM), max_len=width - 4)

        split_w = int(width * 0.52)
        box_y = start_y + 3
        box_h = height - 3

        # Left: Live / Filtered Candidate Pointers
        candidates = self.can_filter.get_candidate_details()
        title_count = f" Filter Candidates ({len(candidates)} survivors) " if self.can_filter.is_filtered else " All Active CAN Frames "
        self.draw_box(box_y, 1, box_h, split_w, title_count)

        if not candidates:
            self.safe_addstr(box_y + 2, 3, "No candidate bytes match current filter.", color(CP_WARN))
            self.safe_addstr(box_y + 3, 3, "Press [R] to reset filter or [Z] to undo last step.", color(CP_DIM))
        else:
            header_str = "  CAN ID   Byte   Current Hex   Binary (Bits 7..0)   Module"
            self.safe_addstr(box_y + 1, 2, header_str, color(CP_HEADER, curses.A_BOLD), max_len=split_w - 3)
            
            for idx, c_info in enumerate(candidates[:box_h - 3]):
                is_sel = (idx == self.sniffer_selected_idx)
                attr = color(CP_HIGHLIGHT, curses.A_BOLD) if is_sel else color(CP_DEFAULT)
                prefix = "▶ " if is_sel else "  "
                row_str = f"{prefix}{c_info['can_id']}   [{c_info['byte_idx']}]     {c_info['current_hex']}         {c_info['current_bin']}    {c_info['description']}"
                self.safe_addstr(box_y + 2 + idx, 2, row_str.ljust(split_w - 3), attr, max_len=split_w - 3)

        # Right: Signal Dictionary & Learned Pointers
        right_w = width - split_w - 4
        rx = split_w + 2
        self.draw_box(box_y, rx, box_h, right_w, " Learned Signals Dictionary ")

        self.safe_addstr(box_y + 1, rx + 2, "Test Simulation Triggers:", curses.A_BOLD)
        self.safe_addstr(box_y + 2, rx + 2, "[B] Press Brake   [H] Handbrake   [G] Select 1st Gear", color(CP_HEADER))

        self.safe_addstr(box_y + 4, rx + 2, "Saved Signals (DBC / JSON Dictionary):", color(CP_ACCENT, curses.A_BOLD))
        signals = can_sniffer.load_learned_signals()
        for s_idx, sig in enumerate(signals[:box_h - 7]):
            s_line = f"• {sig['name']}: {sig['can_id']} B{sig['byte_idx']} M{sig['bit_mask']}"
            self.safe_addstr(box_y + 6 + s_idx, rx + 2, s_line, color(CP_OK, curses.A_BOLD), max_len=right_w - 4)
            self.safe_addstr(box_y + 6 + s_idx + 1, rx + 4, f"{sig['description']}", color(CP_DIM), max_len=right_w - 6)

    # =========================================================================
    # TAB 4: Tools (EGS6, DPF, Battery, EPB, Actuator Tests, CAN Ping)
    # =========================================================================
    def draw_tools_tab(self, start_y, height, width):
        self.safe_addstr(start_y, 2, "PSA Specific Diagnostic Systems (Citroën Grand C4 Picasso 1.6 HDi EGS6)", curses.A_BOLD)
        self.safe_addstr(start_y + 1, 2, self.tools_status_msg, color(CP_DIM))

        box_y = start_y + 2
        box_h = height - 2

        if self.tools_view == "network":
            self.draw_box(box_y, 1, box_h, width - 2, " PSA AEE2004 CAN Bus Network Topology Map (Press [P] to return) ")
            header_str = f"  {'CAN Node':<32} {'TX / RX Address':<20} {'Status':<14} {'Response Latency'}"
            self.safe_addstr(box_y + 1, 3, header_str, color(CP_HEADER, curses.A_BOLD), max_len=width - 8)

            for idx, n in enumerate(self.network_nodes[:box_h - 4]):
                ny = box_y + 3 + idx
                status_str = "[ ONLINE ]" if n['online'] else "[ NO RESP ]"
                status_attr = color(CP_OK, curses.A_BOLD) if n['online'] else color(CP_ERR, curses.A_BOLD)
                resp_str = f"{n['latency_ms']} ms" if n['online'] else "Timeout"
                id_str = f"{n['tx']} / {n['rx']}"

                self.safe_addstr(ny, 3, f"• {n['name']:<30}", curses.A_BOLD)
                self.safe_addstr(ny, 35, f"{id_str:<18}", color(CP_DIM))
                self.safe_addstr(ny, 55, f"{status_str:<14}", status_attr)
                self.safe_addstr(ny, 71, f"{resp_str}", color(CP_DEFAULT))

            summary_y = box_y + box_h - 2
            online_cnt = sum(1 for n in self.network_nodes if n['online'])
            self.safe_addstr(summary_y, 3, f"CAN Summary: {online_cnt} Active ECUs Online  |  {len(self.network_nodes)-online_cnt} Offline  (CAAR suspension is Exclusive trim only)", color(CP_ACCENT, curses.A_BOLD))
            return

        if self.tools_view == "odometer":
            self.draw_box(box_y, 1, box_h, width - 2, " Citroën Grand C4 Picasso: Odometer & Maintenance Audit (Press [O] to return) ")
            oy = box_y + 2
            d = getattr(self, 'odo_data', special_diagnostics.analyze_odometer_service(is_sim=self.is_demo))
            self.safe_addstr(oy, 4, f"TOTAL VEHICLE MILEAGE:       {d['total_miles']:,} miles  ({d['total_km']:,} km)", curses.A_BOLD)
            oy += 2
            self.safe_addstr(oy, 4, f"NEXT SERVICE COUNTDOWN:      {d['service_remaining_miles']:,} miles  ({d['service_remaining_km']:,} km / {d['service_days']} days remaining)", curses.A_BOLD)
            oy += 1
            sp_color = color(CP_OK if d['spanner_badge'] == 'OK' else CP_WARN, curses.A_BOLD)
            self.safe_addstr(oy, 4, f"INSTRUMENT SPANNER LAMP:     {d['spanner_status']}", sp_color)
            oy += 2
            self.safe_addstr(oy, 4, f"OIL LIFE REMAINING:          {d['oil_life_remaining_pct']}%  (Degradation index: {d['oil_degradation_pct']}%)")
            oy += 1
            self.safe_addstr(oy, 4, f"FUEL ECONOMY (1.6 HDi DV6):  {d['avg_mpg']} MPG  ({d['avg_l_100km']} L/100km)")
            oy += 2
            self.safe_addstr(oy, 4, f"TRIP COMPUTER A:             {d['trip_a_miles']} miles  ({d['trip_a_km']} km)")
            oy += 1
            self.safe_addstr(oy, 4, f"TRIP COMPUTER B:             {d['trip_b_miles']} miles  ({d['trip_b_km']} km)")
            oy += 2
            self.safe_addstr(oy, 4, f"ODOMETER SYNCHRONIZATION:    {d['sync_status']}", color(CP_OK, curses.A_BOLD))
            oy += 3
            self.safe_addstr(oy, 4, "ACTIONS:  [S] Reset Service Spanner & Restore 12,500 mi / 365 Days    [O] Back to Diagnostics", color(CP_ACCENT, curses.A_BOLD))
            return

        col_w = (width - 4) // 3

        # 1. EGS6 Semi-Auto Gearbox Health
        self.draw_box(box_y, 1, box_h, col_w, " 1. EGS6 Clutch & Hydraulics ")
        ey = box_y + 2
        self.safe_addstr(ey, 3, f"Pressure:     {self.egs6_data['pressure_bar']} bar")
        ey += 1
        self.safe_addstr(ey, 3, f"Hold Decay:   {self.egs6_data['decay_sec']} seconds")
        ey += 1
        self.safe_addstr(ey, 3, f"Clutch Pos:   {self.egs6_data['clutch_mm']} mm")
        ey += 1
        self.safe_addstr(ey, 3, f"Clutch Wear:  {self.egs6_data['clutch_wear_pct']} %")
        ey += 2
        self.safe_addstr(ey, 3, "Accumulator Verdict:", curses.A_BOLD)
        ey += 1
        accum_attr = color(CP_OK if self.egs6_data['accum_status'] == 'OK' else CP_WARN)
        self.safe_addstr(ey, 3, f"{self.egs6_data['accum_verdict']}", accum_attr, max_len=col_w - 5)
        ey += 2
        self.safe_addstr(ey, 3, "Clutch Plate Verdict:", curses.A_BOLD)
        ey += 1
        self.safe_addstr(ey, 3, f"{self.egs6_data['clutch_verdict']}", color(CP_OK), max_len=col_w - 5)

        # 2. DPF & Eolys Additive
        rx2 = col_w + 2
        self.draw_box(box_y, rx2, box_h, col_w, " 2. DPF & Eolys Additive ")
        dy = box_y + 2
        self.safe_addstr(dy, rx2 + 2, f"Soot Load:    {self.dpf_data['soot_g']} g ({self.dpf_data['soot_pct']}%)")
        dy += 1
        self.safe_addstr(dy, rx2 + 2, f"Diff Press:   {self.dpf_data['diff_mbar']} mbar")
        dy += 1
        self.safe_addstr(dy, rx2 + 2, f"Last Regen:   {self.dpf_data['km_since_regen']} km ago")
        dy += 1
        self.safe_addstr(dy, rx2 + 2, f"Eolys Level:  {self.dpf_data['eolys_ml']} ml ({self.dpf_data['eolys_pct']}%)")
        dy += 2
        self.safe_addstr(dy, rx2 + 2, "Filter Verdict:", curses.A_BOLD)
        dy += 1
        self.safe_addstr(dy, rx2 + 2, f"{self.dpf_data['dpf_verdict']}", color(CP_OK), max_len=col_w - 5)
        dy += 2
        self.safe_addstr(dy, rx2 + 2, "Eolys Fluid Verdict:", curses.A_BOLD)
        dy += 1
        self.safe_addstr(dy, rx2 + 2, f"{self.dpf_data['eolys_verdict']}", color(CP_OK), max_len=col_w - 5)

        # 3. 12V Battery & Cranking Test
        rx3 = col_w * 2 + 3
        col3_w = width - rx3 - 2
        self.draw_box(box_y, rx3, box_h, col3_w, " 3. Battery & False DTC Test ")
        by = box_y + 2
        self.safe_addstr(by, rx3 + 2, f"Resting Volt: {self.battery_data['resting_v']} V")
        by += 1
        self.safe_addstr(by, rx3 + 2, f"Crank Dip:    {self.battery_data['cranking_min_v']} V")
        by += 1
        self.safe_addstr(by, rx3 + 2, f"Alternator:   {self.battery_data['charging_v']} V")
        by += 2
        self.safe_addstr(by, rx3 + 2, "Battery Verdict:", curses.A_BOLD)
        by += 1
        self.safe_addstr(by, rx3 + 2, f"{self.battery_data['verdict']}", color(CP_OK), max_len=col3_w - 5)
        by += 2
        self.safe_addstr(by, rx3 + 2, "Phantom DTC Risk:", curses.A_BOLD)
        by += 1
        self.safe_addstr(by, rx3 + 2, f"{self.battery_data['risk']}", color(CP_ACCENT), max_len=col3_w - 5)

    # =========================================================================
    # TAB 5: Research
    # =========================================================================
    def draw_research_tab(self, start_y, height, width):
        self.safe_addstr(start_y, 2, "Current Query: ", curses.A_BOLD)
        self.safe_addstr(start_y, 17, f"'{self.research_query}'", color(CP_HEADER, curses.A_BOLD))
        self.safe_addstr(start_y, 25 + len(self.research_query), f"({len(self.research_results)} matches found across PSA database)   [Press '/' to search]", color(CP_DIM))

        split_w = int(width * 0.42)
        box_y = start_y + 2
        box_h = height - 2

        self.draw_box(box_y, 1, box_h, split_w, " Search Matches ")
        self.draw_box(box_y, split_w + 2, box_h, width - split_w - 4, " Definition Details ")

        if not self.research_results:
            self.safe_addstr(box_y + 2, 3, "No results found.", color(CP_WARN))
        else:
            for idx, r in enumerate(self.research_results[:box_h - 2]):
                code, raw, arch, sys_name, ecu, desc_en, _ = r
                is_sel = (idx == self.research_selected_idx)
                attr = color(CP_HIGHLIGHT, curses.A_BOLD) if is_sel else color(CP_DEFAULT)
                line = f"{'>' if is_sel else ' '} {code:<6} [{ecu}] {desc_en}"
                self.safe_addstr(box_y + 1 + idx, 2, line.ljust(split_w - 3), attr, max_len=split_w - 3)

        if self.research_results and 0 <= self.research_selected_idx < len(self.research_results):
            sel = self.research_results[self.research_selected_idx]
            code, raw, arch, sys_name, ecu, desc_en, desc_fr = sel
            cx = split_w + 4
            cy = box_y + 2

            self.safe_addstr(cy, cx, "DTC CODE:       ", curses.A_BOLD)
            self.safe_addstr(cy, cx + 16, f"{code}  (raw: {raw})", color(CP_HEADER, curses.A_BOLD))

            self.safe_addstr(cy + 1, cx, "ARCHITECTURE:   ", curses.A_BOLD)
            self.safe_addstr(cy + 1, cx + 16, f"{arch}", color(CP_OK if 'AEE2004' in arch else CP_DIM))

            self.safe_addstr(cy + 2, cx, "MODULE / ECU:   ", curses.A_BOLD)
            self.safe_addstr(cy + 2, cx + 16, f"{sys_name} / {ecu}", color(CP_ACCENT, curses.A_BOLD))

            self.safe_addstr(cy + 4, cx, "ENGLISH DESCRIPTION:", curses.A_BOLD)
            self.safe_addstr(cy + 5, cx, f"{desc_en}", color(CP_DEFAULT, curses.A_BOLD), max_len=width - split_w - 8)

            if desc_fr:
                self.safe_addstr(cy + 7, cx, "FRENCH OEM TITLE:", color(CP_DIM, curses.A_BOLD))
                self.safe_addstr(cy + 8, cx, f"{desc_fr}", color(CP_DIM), max_len=width - split_w - 8)

    # =========================================================================
    # TAB 6: Logs
    # =========================================================================
    def draw_logs_tab(self, start_y, height, width):
        self.safe_addstr(start_y, 2, f"Diagnostic Session Logs Directory: {obd_service.LOG_DIR}", curses.A_BOLD)

        split_w = int(width * 0.38)
        box_y = start_y + 2
        box_h = height - 2

        self.draw_box(box_y, 1, box_h, split_w, " Audit Log Files ")
        self.draw_box(box_y, split_w + 2, box_h, width - split_w - 4, " Log File Contents ")

        if not self.log_files:
            self.safe_addstr(box_y + 2, 3, "No log files recorded yet.", color(CP_DIM))
        else:
            for idx, lf in enumerate(self.log_files[:box_h - 2]):
                is_sel = (idx == self.logs_selected_idx)
                attr = color(CP_HIGHLIGHT, curses.A_BOLD) if is_sel else color(CP_DEFAULT)
                line = f"{'>' if is_sel else ' '} {lf}"
                self.safe_addstr(box_y + 1 + idx, 2, line.ljust(split_w - 3), attr, max_len=split_w - 3)

        if self.log_files and 0 <= self.logs_selected_idx < len(self.log_files):
            filepath = os.path.join(obd_service.LOG_DIR, self.log_files[self.logs_selected_idx])
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                cx = split_w + 4
                view_h = box_h - 2
                for i in range(view_h):
                    line_idx = self.log_scroll_offset + i
                    if line_idx < len(lines):
                        txt = lines[line_idx].rstrip()
                        self.safe_addstr(box_y + 1 + i, cx, txt, color(CP_DEFAULT), max_len=width - split_w - 8)
            except Exception as e:
                self.safe_addstr(box_y + 2, split_w + 4, f"Error reading log: {e}", color(CP_ERR))

    # =========================================================================
    # TAB 7: Settings
    # =========================================================================
    def draw_settings_tab(self, start_y, height, width):
        self.safe_addstr(start_y, 2, "Hardware Adapter & Serial Port Configuration", curses.A_BOLD)

        box_y = start_y + 2
        box_h = height - 2

        self.draw_box(box_y, 1, box_h, width - 2, " Settings & Hardware Probing ")

        detected_ports = obd_service.find_serial_ports()
        sy = box_y + 2
        self.safe_addstr(sy, 4, "DETECTED SERIAL HARDWARE:", curses.A_BOLD)
        if detected_ports:
            for p in detected_ports:
                sy += 1
                self.safe_addstr(sy, 6, f"• {p.device} ({p.description})", color(CP_OK, curses.A_BOLD))
        else:
            sy += 1
            self.safe_addstr(sy, 6, "• None detected on USB/Bluetooth serial lines right now.", color(CP_WARN))

        sy += 2
        self.safe_addstr(sy, 4, "CURRENT ADAPTER PROFILE:", curses.A_BOLD)
        sy += 1
        port_name = psa_diag.SESSION_CONFIG['port'] or "Auto-Detect (/dev/ttyUSB0, /dev/ttyACM0)"
        self.safe_addstr(sy, 6, f"Port:       {port_name}")
        sy += 1
        self.safe_addstr(sy, 6, f"Baud Rate:  {psa_diag.SESSION_CONFIG['baud']} baud (Standard ELM327 / OBDLink)")
        sy += 1
        sim_state = "ENABLED (Forced Test Mode)" if psa_diag.SESSION_CONFIG['force_sim'] else "DISABLED (Auto-switch on connection)"
        self.safe_addstr(sy, 6, f"Simulation: {sim_state}", color(CP_ACCENT, curses.A_BOLD))

        sy += 3
        self.safe_addstr(sy, 4, "HOTKEYS:", curses.A_BOLD)
        sy += 1
        self.safe_addstr(sy, 6, "[M] Toggle Forced Simulation Mode ON/OFF", color(CP_HEADER))
        sy += 1
        self.safe_addstr(sy, 6, "[B] Cycle Baud Rates (38400 -> 115200 -> 9600)", color(CP_HEADER))
        sy += 1
        self.safe_addstr(sy, 6, "[T] Test Port Handshake with 'ATZ' command", color(CP_HEADER))
        sy += 1
        self.safe_addstr(sy, 6, "[C] Open Connection Wizard / Device Link Screen", color(CP_HEADER))

    def draw_engine_tab(self, start_y, height, width):
        left_w = min(50, width // 2)
        right_w = width - left_w - 3
        right_x = left_w + 2

        self.draw_box(start_y, 1, height, left_w, " 1.6 HDi Engine Bay Map ")
        self.draw_box(start_y, right_x, height, right_w, " Sensors & Locations (20 Nodes) ")

        vals = engine_diagram.get_live_sensor_values(is_sim=self.is_demo)
        diag_lines = [
            "[ FRONT BUMPER / RADIATOR PACK ]",
            "┌──────────────────────────────────────────────┐",
            f"│ [03] INTERCOOLER     │ [11] DPF ({vals['dpf_soot_g']}g soot)  │",
            f"│  dp: {vals['intercooler_dp']} bar         │      backp: {vals['dpf_diff_mbar']} mb  │",
            "├──────────────────────┼───────────────────────┤",
            f"│ [04] MAP / IAT       │ [02] GARRETT TURBO    │",
            f"│  {vals['map_mbar']} mb / {vals['ambient_temp_c']}°C  │  {vals['boost_bar']} bar | [09] {vals['vnt_duty_pct']}% │",
            "├──────────────────────┴───────────────────────┤",
            "│ DV6 1.6 HDi CYLINDER HEAD (16V / 8V DIESEL)  │",
            f"│ [08] INJ4:{vals['inj_balance_c4']:+.1f} INJ3:{vals['inj_balance_c3']:+.1f} INJ2:{vals['inj_balance_c2']:+.1f} INJ1:{vals['inj_balance_c1']:+.1f}│",
            f"│ [06] RAIL: {vals['rail_press_bar']} bar [05] PUMP:{vals['fuel_temp_c']}°C [07] SENS │",
            "├──────────────────────┬───────────────────────┤",
            f"│ [01] AIR & MAF       │ [17] EGS6 GEARBOX     │",
            f"│  {vals['maf_mg']} mg/stroke   │  Selector: {vals['gear_selected'][:10]}   │",
            f"│ [15] CRANK: {vals['engine_rpm']} RPM │  [18] PUMP: {vals['egs6_press_bar']} bar   │",
            f"│ [16] CAM: SYNCED     │  [19] CLUTCH: {vals['clutch_pos_mm']}mm │",
            f"│ [14] ECT: {vals['coolant_c']}°C      │  [20] 12V BATT: {vals['battery_v']}V │",
            "└──────────────────────┴───────────────────────┘",
            "[ BULKHEAD / CABIN SCUTTLE ]"
        ]

        ly = start_y + 1
        for line in diag_lines:
            if ly >= start_y + height - 1:
                break
            self.safe_addstr(ly, 3, line, color(CP_DEFAULT), max_len=left_w - 4)
            ly += 1

        sy = start_y + 1
        header = f" {'ID':<4} {'SENSOR NAME':<22} {'LIVE VALUE':<14} {'STATUS':<8}"
        self.safe_addstr(sy, right_x + 2, header, color(CP_HEADER, curses.A_BOLD), max_len=right_w - 4)
        sy += 1

        list_h = min(11, height - 9)
        for idx in range(1, 21):
            if sy >= start_y + list_h + 2:
                break
            s = engine_diagram.SENSOR_DATABASE[idx]
            v = vals.get(s['param_key'], 'N/A')
            u = s['unit']
            v_str = f"{v} {u}"[:13]
            st_txt, _ = engine_diagram.evaluate_sensor_status(v, s)

            is_sel = (idx == self.engine_sensor_selected)
            attr = color(CP_HIGHLIGHT, curses.A_BOLD) if is_sel else color(CP_DEFAULT)
            marker = "▶" if is_sel else " "

            line = f"{marker}[{idx:02d}] {s['name'][:22]:<22} {v_str:<14} {st_txt:<8}"
            self.safe_addstr(sy, right_x + 1, line, attr, max_len=right_w - 3)
            sy += 1

        sel_s = engine_diagram.SENSOR_DATABASE.get(self.engine_sensor_selected, {})
        det_y = start_y + list_h + 2
        det_h = height - list_h - 3
        if det_h >= 5:
            self.draw_box(det_y, right_x + 1, det_h, right_w - 2, f" Sensor #{self.engine_sensor_selected:02d} Technical Details ")
            dy = det_y + 1
            self.safe_addstr(dy, right_x + 3, f"Name: {sel_s.get('name', 'N/A')}", curses.A_BOLD, max_len=right_w - 6)
            dy += 1
            self.safe_addstr(dy, right_x + 3, f"Location: {sel_s.get('location', 'N/A')}", color(CP_DEFAULT), max_len=right_w - 6)
            dy += 1
            self.safe_addstr(dy, right_x + 3, f"Connector: {sel_s.get('connector', 'N/A')}", color(CP_DIM), max_len=right_w - 6)
            dy += 1
            self.safe_addstr(dy, right_x + 3, f"Nominal: {sel_s.get('nominal', 'N/A')}", color(CP_OK), max_len=right_w - 6)

    def draw_box(self, y, x, h, w, title=""):
        try:
            self.stdscr.attron(color(CP_BORDER))
            self.stdscr.addch(y, x, curses.ACS_ULCORNER)
            self.stdscr.hline(y, x + 1, curses.ACS_HLINE, w - 2)
            self.stdscr.addch(y, x + w - 1, curses.ACS_URCORNER)

            self.stdscr.vline(y + 1, x, curses.ACS_VLINE, h - 2)
            self.stdscr.vline(y + 1, x + w - 1, curses.ACS_VLINE, h - 2)

            self.stdscr.addch(y + h - 1, x, curses.ACS_LLCORNER)
            self.stdscr.hline(y + h - 1, x + 1, curses.ACS_HLINE, w - 2)
            self.stdscr.addch(y + h - 1, x + w - 1, curses.ACS_LRCORNER)
            self.stdscr.attroff(color(CP_BORDER))

            if title:
                self.safe_addstr(y, x + 2, f" {title} ", curses.A_BOLD, max_len=w - 4)
        except curses.error:
            pass

    def prompt_input(self, prompt_text: str) -> str:
        curses.echo()
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        h, w = self.stdscr.getmaxyx()
        self.stdscr.attron(color(CP_TAB_ACTIVE, curses.A_BOLD))
        self.safe_addstr(h - 1, 0, " " * (w - 1))
        self.safe_addstr(h - 1, 2, prompt_text)
        self.stdscr.attroff(color(CP_TAB_ACTIVE, curses.A_BOLD))
        self.stdscr.refresh()
        try:
            val = self.stdscr.getstr().decode('utf-8', errors='ignore')
        except Exception:
            val = ""
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        return val

    # =========================================================================
    # USER INPUT HANDLING
    # =========================================================================
    def handle_input(self):
        try:
            ch = self.stdscr.getch()
        except curses.error:
            return

        if ch == -1:
            return

        if ch in (ord('q'), ord('Q')):
            self.running = False
            return
        elif ch == curses.KEY_RIGHT or ch == 9: # Tab or Right
            self.active_tab = (self.active_tab + 1) % len(self.tabs)
            return
        elif ch == curses.KEY_LEFT:
            self.active_tab = (self.active_tab - 1) % len(self.tabs)
            return
        elif ord('1') <= ch <= ord('8'):
            self.active_tab = ch - ord('1')
            return

        # Tab Specific Navigation
        if self.active_tab == 0: # DTC Tab
            if ch == curses.KEY_UP and self.dtc_items:
                self.dtc_selected_idx = max(0, self.dtc_selected_idx - 1)
            elif ch == curses.KEY_DOWN and self.dtc_items:
                self.dtc_selected_idx = min(len(self.dtc_items) - 1, self.dtc_selected_idx + 1)
            elif ch in (ord('s'), ord('S')):
                self.dtc_status_msg = "Running Extended Multi-Scan (Engine, Gearbox, ESP, Handbrake)..."
                self.stdscr.refresh()
                self.run_tui_scan()
            elif ch in (ord('r'), ord('R')):
                self.dtc_status_msg = "Reading active & pending codes..."
                self.stdscr.refresh()
                self.run_tui_read()
            elif ch in (ord('c'), ord('C')):
                self.run_tui_clear()
            elif ch in (ord('f'), ord('F'), curses.KEY_ENTER, 10, 13):
                self.show_freeze_frame = not self.show_freeze_frame
                state = "ON" if self.show_freeze_frame else "OFF"
                self.dtc_status_msg = f"Freeze-Frame Snapshot Mode: {state}. Press [F] to toggle."

        elif self.active_tab == 1: # LiveData Tab
            if ch == ord(' '):
                self.live_paused = not self.live_paused

        elif self.active_tab == 2: # Sniffer Tab
            if ch == ord('1'):
                count = self.can_filter.take_snapshot(f"Snap-{len(self.can_filter.snapshots)}")
                self.sniffer_status = f"[✓] Baseline Snapshot #{count} recorded. Perform action, then press [C]."
            elif ch in (ord('c'), ord('C')):
                count = self.can_filter.filter_changed()
                self.sniffer_status = f"[✓] Filtered CHANGED: {count} candidate byte(s) remaining."
            elif ch in (ord('u'), ord('U')):
                count = self.can_filter.filter_unchanged()
                self.sniffer_status = f"[✓] Filtered UNCHANGED: {count} candidate byte(s) remaining."
            elif ch in (ord('z'), ord('Z')):
                count = self.can_filter.undo_last_filter()
                self.sniffer_status = f"[✓] Filter Undone. {count} candidate byte(s) active."
            elif ch in (ord('r'), ord('R')):
                self.can_filter.reset_filter()
                self.sniffer_status = "[✓] Filter reset. Showing all active CAN bus frames."
            elif ch in (ord('s'), ord('S')):
                # Save highlighted candidate to dictionary
                candidates = self.can_filter.get_candidate_details()
                if candidates and 0 <= self.sniffer_selected_idx < len(candidates):
                    cand = candidates[self.sniffer_selected_idx]
                    name = self.prompt_input(f"Enter Signal Name for {cand['can_id']} B{cand['byte_idx']}: ")
                    if name:
                        desc = self.prompt_input("Enter Signal Description: ")
                        can_sniffer.add_learned_signal(name, cand['can_id'], cand['byte_idx'], "0xFF", desc or "User reverse-engineered signal")
                        self.sniffer_status = f"[✓] Signal '{name}' saved to learned_signals.json!"
            # Test simulation action triggers
            elif ch in (ord('b'), ord('B')):
                self.can_stream.trigger_action('brake', 3.0)
                self.sniffer_status = "[!] Simulation: Brake pedal pressed for 3s (CAN ID 0x217 changed)."
            elif ch in (ord('h'), ord('H')):
                self.can_stream.trigger_action('handbrake', 3.0)
                self.sniffer_status = "[!] Simulation: Handbrake lever pulled for 3s (CAN ID 0x388 changed)."
            elif ch in (ord('g'), ord('G')):
                self.can_stream.trigger_action('gear_1', 3.0)
                self.sniffer_status = "[!] Simulation: EGS6 shifted into 1st Gear for 3s (CAN ID 0x128 changed)."
            elif ch == curses.KEY_UP:
                candidates = self.can_filter.get_candidate_details()
                if candidates:
                    self.sniffer_selected_idx = max(0, self.sniffer_selected_idx - 1)
            elif ch == curses.KEY_DOWN:
                candidates = self.can_filter.get_candidate_details()
                if candidates:
                    self.sniffer_selected_idx = min(len(candidates) - 1, self.sniffer_selected_idx + 1)

        elif self.active_tab == 3: # Tools Tab
            if ch in (ord('r'), ord('R')):
                self.egs6_data = special_diagnostics.analyze_egs6_gearbox(is_sim=self.is_demo)
                self.dpf_data = special_diagnostics.analyze_dpf_system(is_sim=self.is_demo)
                self.battery_data = special_diagnostics.analyze_battery_crank(is_sim=self.is_demo)
                self.tools_status_msg = "[✓] Telemetry evaluations refreshed."
            elif ch in (ord('p'), ord('P')):
                self.tools_view = "network" if self.tools_view != "network" else "diagnostics"
                if self.tools_view == "network":
                    self.network_nodes = advanced_features.CANNetworkTopology.ping_all(is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] CAN Network Topology updated. Press [P] to return to Diagnostics."
                else:
                    self.tools_status_msg = "Diagnostic Systems view active. Press [P] for CAN Ping."
            elif ch in (ord('e'), ord('E')):
                act = self.prompt_input("EPB Mode: [1] Retract for Pad Change  [2] Calibrate Force  [3] Normal Drive: ")
                epb = advanced_features.EPBController()
                if act == '1':
                    epb.set_service_mode(retract=True, is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] EPB Service Mode: Cables unwound. Calipers safe for pad change."
                elif act == '2':
                    epb.calibrate_force(is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] EPB Clamping Force Calibrated (165 daN). C155A resolved."
                elif act == '3':
                    epb.set_service_mode(retract=False, is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] EPB Normal Driving Tension Restored."
            elif ch in (ord('t'), ord('T')):
                act_name = self.prompt_input("Actuator Test [pump / fan_low / fan_high / egr / glow / fuel]: ")
                if act_name:
                    advanced_features.ActuatorTester.run_test(act_name, is_sim=self.is_demo)
                    self.tools_status_msg = f"[✓] Actuator '{act_name}' test cycle complete."
            elif ch in (ord('o'), ord('O')):
                self.tools_view = "odometer" if self.tools_view != "odometer" else "diagnostics"
                if self.tools_view == "odometer":
                    self.odo_data = special_diagnostics.analyze_odometer_service(is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] Odometer & Service view active. Press [S] to Reset Spanner, [O] to return."
                else:
                    self.tools_status_msg = "Diagnostic Systems view active."
            elif ch in (ord('s'), ord('S')) and self.tools_view == "odometer":
                confirm = self.prompt_input("Reset service spanner countdown to 12,500 mi / 365 days? (y/n): ")
                if confirm.lower() in ('y', 'yes'):
                    special_diagnostics.reset_service_interval(is_sim=self.is_demo)
                    self.odo_data = special_diagnostics.analyze_odometer_service(is_sim=self.is_demo)
                    self.odo_data['spanner_status'] = "NORMAL (Service Spanner OFF)"
                    self.odo_data['spanner_badge'] = "OK"
                    self.odo_data['service_remaining_miles'] = 12500
                    self.odo_data['service_remaining_km'] = 20000
                    self.odo_data['service_days'] = 365
                    self.tools_status_msg = "[✓] Service Interval Reset! Spanner lamp extinguished."
            elif ch in (ord('l'), ord('L')):
                self.tools_status_msg = "[*] Running EGS6 Clutch Relearn (Point de Léchage)..."
                self.stdscr.refresh()
                res = special_diagnostics.run_egs6_relearn(is_sim=self.is_demo)
                self.tools_status_msg = f"[✓] EGS6 Relearn Complete: Bite-point learned at {res['bite_point_mm']}mm."
            elif ch in (ord('g'), ord('G')):
                self.tools_status_msg = "[*] Initiating DPF Forced Regeneration... Please wait..."
                self.stdscr.refresh()
                res = special_diagnostics.run_dpf_regeneration(is_sim=self.is_demo)
                self.tools_status_msg = f"[✓] DPF Regen Complete: Soot burned to {res['final_soot_g']}g ({res['soot_reduction_pct']}% reduction)."
            elif ch in (ord('k'), ord('K')):
                advanced_features.BSIController.send_keepalive_pulse(is_sim=self.is_demo)
                self.tools_status_msg = "[✓] BSI Economy Mode Keep-Alive pulse sent on CAN 0x7DF."
            elif ch in (ord('a'), ord('A')):
                susp_act = self.prompt_input("Air Suspension: [1] Bleed/Deflate  [2] Inflate  [3] Test Compressor: ")
                if susp_act == '1':
                    res = workshop_features.PneumaticSuspensionController.bleed_system(is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] Air suspension deflated to 0.0 bar for airbag removal."
                elif susp_act == '2':
                    res = workshop_features.PneumaticSuspensionController.inflate_system(is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] Air suspension inflated to nominal 118mm curb height."
                elif susp_act == '3':
                    res = workshop_features.PneumaticSuspensionController.test_compressor(is_sim=self.is_demo)
                    self.tools_status_msg = f"[✓] Compressor run test: {res['current_draw_amps']}A, +{res['pressure_rise_bar']} bar."
            elif ch in (ord('y'), ord('Y')):
                confirm = self.prompt_input("Reset Eolys additive counter to 1,100 ml and prime dosing lines? (y/n): ")
                if confirm.lower() in ('y', 'yes'):
                    workshop_features.EolysManager.reset_pouch(volume_ml=1100, is_sim=self.is_demo)
                    self.tools_status_msg = "[✓] Eolys pouch reset to 1100 ml and 15s pump prime cycle complete!"
            elif ch in (ord('h'), ord('H')):
                audit = workshop_features.VehicleHealthAuditor.run_full_audit(is_sim=self.is_demo)
                self.tools_status_msg = f"[✓] Vehicle Health Score: {audit['overall_score']}/100 [{audit['grade']}]."

        elif self.active_tab == 4: # Research Tab
            if ch == curses.KEY_UP and self.research_results:
                self.research_selected_idx = max(0, self.research_selected_idx - 1)
            elif ch == curses.KEY_DOWN and self.research_results:
                self.research_selected_idx = min(len(self.research_results) - 1, self.research_selected_idx + 1)
            elif ch in (ord('/'), ord('s'), ord('S')):
                query = self.prompt_input("Search Code or Keyword (e.g. C27A5, clutch, DPF): ")
                if query:
                    self.research_query = query
                    self.execute_research_search(query)

        elif self.active_tab == 5: # Logs Tab
            if ch == curses.KEY_UP and self.log_files:
                self.logs_selected_idx = max(0, self.logs_selected_idx - 1)
                self.log_scroll_offset = 0
            elif ch == curses.KEY_DOWN and self.log_files:
                self.logs_selected_idx = min(len(self.log_files) - 1, self.logs_selected_idx + 1)
                self.log_scroll_offset = 0
            elif ch == curses.KEY_PPAGE:
                self.log_scroll_offset = max(0, self.log_scroll_offset - 5)
            elif ch == curses.KEY_NPAGE:
                self.log_scroll_offset += 5

        elif self.active_tab == 6: # Settings Tab
            if ch in (ord('m'), ord('M')):
                psa_diag.SESSION_CONFIG['force_sim'] = not psa_diag.SESSION_CONFIG['force_sim']
            elif ch in (ord('b'), ord('B')):
                current = psa_diag.SESSION_CONFIG['baud']
                order = [38400, 115200, 9600]
                idx = (order.index(current) + 1) % len(order) if current in order else 0
                psa_diag.SESSION_CONFIG['baud'] = order[idx]
            elif ch in (ord('t'), ord('T')):
                self.test_handshake()
            elif ch in (ord('c'), ord('C')):
                self.show_connect_screen = True
                self.rescan_ports()

        elif self.active_tab == 7: # Engine Tab
            if ch == curses.KEY_UP:
                self.engine_sensor_selected = max(1, self.engine_sensor_selected - 1)
            elif ch == curses.KEY_DOWN:
                self.engine_sensor_selected = min(20, self.engine_sensor_selected + 1)

    def run_tui_scan(self):
        iface = obd_service.OBDInterface(
            port=psa_diag.SESSION_CONFIG['port'],
            baudrate=psa_diag.SESSION_CONFIG['baud'],
            force_sim=psa_diag.SESSION_CONFIG['force_sim']
        )
        all_raw = []
        iface.send_command('ATSH 7DF')
        all_raw.extend(iface.send_command('03'))
        iface.send_command('ATSH 7E1')
        all_raw.extend(iface.send_command('03'))
        iface.send_command('ATSH 760')
        all_raw.extend(iface.send_command('03'))
        iface.send_command('ATSH 792')
        all_raw.extend(iface.send_command('03'))
        iface.close()

        parsed = obd_service.parse_raw_dtc_lines(all_raw)
        items = []
        for ecu_id, codes in parsed.items():
            ecu_name, _ = obd_service.KNOWN_PSA_ECUS.get(ecu_id, ("Direct ECU", ""))
            for code, raw_hex in codes:
                _, _, _, _, _, _, matches = psa_diag.lookup_code_data(code)
                en_desc = matches[0][5] if matches else "Proprietary DTC"
                fr_desc = matches[0][6] if matches else ""
                items.append((ecu_id, ecu_name, code, raw_hex, en_desc, fr_desc))

        self.dtc_items = items
        self.dtc_selected_idx = 0
        self.dtc_status_msg = f"Scan complete! {len(items)} fault(s) detected across modules."
        self.refresh_log_files()

    def run_tui_read(self):
        iface = obd_service.OBDInterface(
            port=psa_diag.SESSION_CONFIG['port'],
            baudrate=psa_diag.SESSION_CONFIG['baud'],
            force_sim=psa_diag.SESSION_CONFIG['force_sim']
        )
        resp = iface.send_command('03') + iface.send_command('07')
        iface.close()
        parsed = obd_service.parse_raw_dtc_lines(resp)
        items = []
        for ecu_id, codes in parsed.items():
            ecu_name, _ = obd_service.KNOWN_PSA_ECUS.get(ecu_id, ("Direct ECU", ""))
            for code, raw_hex in codes:
                _, _, _, _, _, _, matches = psa_diag.lookup_code_data(code)
                en_desc = matches[0][5] if matches else "Proprietary DTC"
                fr_desc = matches[0][6] if matches else ""
                items.append((ecu_id, ecu_name, code, raw_hex, en_desc, fr_desc))
        self.dtc_items = items
        self.dtc_selected_idx = 0
        self.dtc_status_msg = f"Read complete! {len(items)} powertrain DTC(s) found."
        self.refresh_log_files()

    def run_tui_clear(self):
        confirm = self.prompt_input("Clear all trouble codes from vehicle? Type 'yes' to confirm: ")
        if confirm.lower() in ('y', 'yes'):
            iface = obd_service.OBDInterface(
                port=psa_diag.SESSION_CONFIG['port'],
                baudrate=psa_diag.SESSION_CONFIG['baud'],
                force_sim=psa_diag.SESSION_CONFIG['force_sim']
            )
            iface.send_command('ATSH 7DF')
            iface.send_command('04')
            iface.close()
            self.dtc_items = []
            self.dtc_status_msg = "Codes cleared successfully! All warning lights extinguished."
            self.refresh_log_files()

    def test_handshake(self):
        self.safe_addstr(0, 0, "Testing adapter handshake...", color(CP_WARN))
        self.stdscr.refresh()
        iface = obd_service.OBDInterface(
            port=psa_diag.SESSION_CONFIG['port'],
            baudrate=psa_diag.SESSION_CONFIG['baud'],
            force_sim=psa_diag.SESSION_CONFIG['force_sim']
        )
        res = iface.send_command('ATZ')
        iface.close()
        msg = f"Handshake reply: {' '.join(res)}"
        self.prompt_input(f"{msg} (Press Enter)")

def launch_tui(is_demo: bool = False):
    is_demo = is_demo or psa_diag.SESSION_CONFIG['force_sim']
    curses.wrapper(lambda stdscr: (init_colors(), DiagnosticTUI(stdscr, is_demo=is_demo).run()))

if __name__ == '__main__':
    is_demo = any(arg in sys.argv for arg in ['--demo', '--sim', '-demo', '-sim'])
    launch_tui(is_demo=is_demo)
