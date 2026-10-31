#!/usr/bin/env python3
"""
PSA OBD-II / CAN Communication and DTC Management Service
Dedicated to Citroën Grand C4 Picasso Mk1 (1.6 HDi DV6, EGS6 / Piloted Manual Gearbox)
Supports Live Serial (ELM327 / OBDLink USB/BT) and High-Fidelity Simulation Mode.
"""

import os
import sys
import time
import re
import datetime
import socket
import struct
import serial
import serial.tools.list_ports

LOG_DIR = '/root/psa_diag/logs'
HISTORY_FILE = os.path.join(LOG_DIR, 'diag_history.log')

# Known PSA ECU CAN Identifiers on AEE2004 Platform
KNOWN_PSA_ECUS = {
    '7E8': ('Engine Management ECU (CMM)', 'Bosch EDC16C34 / Continental SID807 (1.6 HDi)'),
    '7E0': ('Engine Management ECU (CMM)', 'Transmit address to Bosch/Continental ECU'),
    '7E9': ('Piloted / Robotized Gearbox (BVMP)', 'Magneti Marelli CFC300P (6-Speed EGS6 / Semi-Auto)'),
    '7E1': ('Piloted / Robotized Gearbox (BVMP)', 'Transmit address to EGS6 Gearbox ECU'),
    '7E2': ('Piloted / Robotized Gearbox (BVMP Alt)', 'Secondary EGS6 CAN identifier'),
    '768': ('ABS / ESP Dynamic Stability Control', 'Bosch ESP 8.1 Module'),
    '760': ('ABS / ESP Transmit Header', 'Transmit address to Bosch ESP 8.1'),
    '79A': ('Electric Parking Brake (FSE / EPB)', 'Motorized Caliper & Cable Unit'),
    '792': ('Electric Parking Brake Transmit Header', 'Transmit address to FSE unit'),
    '7D2': ('Built-in Systems Interface (BSI)', 'Central Body Gateway & Multiplexer'),
    '752': ('BSI Transmit Header', 'Transmit address to BSI'),
    '7DF': ('OBD-II Broadcast Header', 'All Powertrain Nodes (Engine + Gearbox)'),
    'UNKNOWN': ('Unidentified ECU Node', 'Direct CAN frame response')
}

def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)

def find_serial_ports():
    """Finds plausible OBD serial ports on Linux."""
    ports = list(serial.tools.list_ports.comports())
    candidates = []
    for p in ports:
        dev = p.device
        desc = (p.description or '').lower()
        hwid = (p.hwid or '').lower()
        if any(dev.startswith(prefix) for prefix in ['/dev/ttyUSB', '/dev/ttyACM', '/dev/rfcomm']):
            candidates.append(p)
        elif any(k in desc or k in hwid for k in ['usb', 'ftdi', 'ch340', 'cp210', 'obd', 'elm', 'serial']):
            if not dev.startswith('/dev/ttyS') or dev in ['/dev/ttyS0']:
                candidates.append(p)
    return candidates

def find_can_interfaces():
    """Detects Linux kernel SocketCAN network interfaces (e.g. can0, can1, vcan0)."""
    can_ifs = []
    sys_net = '/sys/class/net'
    if os.path.exists(sys_net):
        for iface in os.listdir(sys_net):
            type_file = os.path.join(sys_net, iface, 'type')
            if os.path.exists(type_file):
                try:
                    with open(type_file, 'r') as f:
                        # 280 is ARPHRD_CAN in Linux net devices
                        if f.read().strip() in ('280', '0x118'):
                            can_ifs.append(iface)
                except Exception:
                    pass
            elif iface.startswith(('can', 'vcan', 'slcan')):
                can_ifs.append(iface)
    return sorted(list(set(can_ifs)))

class SocketCANInterface:
    """
    Native Linux SocketCAN interface (can0, can1, vcan0).
    Provides zero-latency 500 kbps CAN communication without serial ELM327 bottlenecks.
    Compatible with USB-to-CAN adapters (CANable, Candlelight, Korlan, Waveshare).
    """
    CAN_FRAME_FMT = "=IB3x8s"

    def __init__(self, interface: str = 'can0'):
        self.interface = interface
        self.sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        self.sock.bind((interface,))
        self.sock.settimeout(0.6)
        self.current_header = '7DF'
        self.is_open = True
        print(f"[✓] Initialized native Linux SocketCAN on {interface} (500 kbps).")

    def close(self):
        if self.is_open:
            self.sock.close()
            self.is_open = False

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def write(self, data: bytes):
        pass

    def send_frame(self, can_id: int, data_bytes: bytes):
        payload = data_bytes[:8].ljust(8, b'\x00')
        frame = struct.pack(self.CAN_FRAME_FMT, can_id, len(data_bytes[:8]), payload)
        self.sock.send(frame)

    def recv_frame(self, timeout: float = 0.5) -> tuple[int, bytes] | None:
        self.sock.settimeout(timeout)
        try:
            raw = self.sock.recv(16)
            if len(raw) == 16:
                can_id, dlc, payload = struct.unpack(self.CAN_FRAME_FMT, raw)
                return (can_id & 0x7FF, payload[:dlc])
        except (socket.timeout, BlockingIOError, OSError):
            return None
        return None

    def send_cmd(self, cmd: str) -> list[str]:
        c = cmd.strip().upper()
        if c.startswith('ATSH'):
            parts = c.split()
            if len(parts) > 1:
                self.current_header = parts[1]
            return ['OK']
        elif c.startswith('AT'):
            return ['OK']

        # Parse command hex bytes
        clean = c.replace(' ', '')
        if len(clean) % 2 != 0:
            clean = '0' + clean
        try:
            req_bytes = bytes.fromhex(clean)
        except ValueError:
            return ['ERROR']

        isotp_frame = bytes([len(req_bytes)]) + req_bytes
        try:
            tx_id = int(self.current_header, 16)
        except ValueError:
            tx_id = 0x7DF

        self.send_frame(tx_id, isotp_frame)

        # Collect replies
        replies = []
        start = time.time()
        while time.time() - start < 0.5:
            res = self.recv_frame(timeout=0.15)
            if res:
                rx_id, rx_data = res
                hex_str = ' '.join(f'{b:02X}' for b in rx_data)
                replies.append(f"{rx_id:03X} {hex_str}")
        return replies or ['NO DATA']

    def send_command(self, cmd: str) -> list[str]:
        return self.send_cmd(cmd)

class SimulatedELM327:
    """High-fidelity simulation of an ELM327 connected to a 2010 Grand C4 Picasso 1.6 HDi EGS6."""
    def __init__(self):
        self.current_header = '7DF'
        self.is_open = True
        self.cleared = False
        print("[*] SIMULATION ENGINE: Emulating ELM327 v1.5 on High-Speed CAN (500 kbps)")
        print("[*] VEHICLE PROFILE: Citroën Grand C4 Picasso 1.6 HDi (EGS6 Semi-Auto, Bosch ESP 8.1, FSE)")

    def close(self):
        self.is_open = False

    def write(self, data: bytes):
        pass

    def send_cmd(self, cmd: str) -> list[str]:
        c = cmd.strip().upper()
        time.sleep(0.04) # Simulate CAN bus latency

        if c == 'ATZ':
            return ['ELM327 v1.5']
        elif c in ('ATE0', 'ATL0', 'ATS0'):
            return ['OK']
        elif c == 'ATH1':
            return ['OK']
        elif c.startswith('ATSP'):
            return ['OK']
        elif c.startswith('ATSH'):
            self.current_header = c[4:].strip()
            return ['OK']
        elif c == '0100':
            # Mode 01 PID 00 (Supported PIDs)
            return ['7E8 06 41 00 BE 3F B8 13', '7E9 06 41 00 98 18 80 01']
        elif c == '03':
            # Mode 03 (Confirmed DTCs)
            if self.cleared:
                return ['7E8 02 43 00 00 00 00 00', '7E9 02 43 00 00 00 00 00']
            
            # Realistic Citroën Grand C4 Picasso EGS6 trouble codes:
            # 7E8 (Engine): P0299 (Turbo underboost), P1351 (Glow plug relay)
            # 7E9 (EGS6 Semi-Auto Gearbox): P17A5 (raw 17A5 - Gear 1 mechanical/hydraulic coordination fault!)
            if self.current_header in ('7DF', '7E0'):
                res = ['7E8 06 43 02 02 99 13 51 00']
                if self.current_header == '7DF':
                    res.append('7E9 04 43 01 17 A5 00 00 00')
                return res
            elif self.current_header in ('7E1', '7E2'):
                return ['7E9 04 43 01 17 A5 00 00 00']
            elif self.current_header == '760':
                # ABS/ESP: C1385 (raw 5385)
                return ['768 04 43 01 53 85 00 00 00']
            elif self.current_header == '792':
                # FSE Handbrake: C155A (raw 555A)
                return ['79A 04 43 01 55 5A 00 00 00']
            else:
                return ['NO DATA']

        elif c == '07':
            # Mode 07 (Pending DTCs)
            if self.cleared:
                return ['7E8 02 47 00 00 00 00 00']
            return ['7E8 04 47 01 02 99 00 00 00'] # P0299 pending boost deviation

        elif c in ('1902FF', '19 02 FF'):
            # UDS Service 0x19: Report DTC by status mask
            if self.cleared:
                return ['59 02 FF 00']
            if self.current_header in ('7E1', '7E2'):
                # Gearbox UDS response
                return ['7E9 06 59 02 FF 17 A5 29']
            elif self.current_header == '760':
                return ['768 06 59 02 FF 53 85 1C']
            return ['7E8 08 59 02 FF 02 99 21 13 51']

        elif c == '04':
            # Mode 04: Clear DTCs
            self.cleared = True
            return ['44']

        elif c in ('14FFFFFF', '14 FF FF FF'):
            # UDS Service 0x14: Clear all diagnostic trouble codes
            self.cleared = True
            return ['54']

        return ['OK']

def require_vehicle_or_demo(is_demo: bool = False, port: str = None, interface: str = None) -> bool:
    """
    Checks if physical vehicle/adapter is connected.
    If not connected and is_demo is False, prints a clear diagnostic error and terminates.
    """
    if is_demo:
        return True

    # Check SocketCAN interface if requested or physical can0 present
    can_ifs = find_can_interfaces()
    if interface and interface in can_ifs:
        return True
    if 'can0' in can_ifs:
        return True

    candidates = find_serial_ports()
    if port:
        candidates = [p for p in candidates if p.device == port]
        if not candidates and os.path.exists(port):
            return True

    if not candidates:
        print("\n" + "=" * 65)
        print("\033[1m\033[31m[!] ERROR: VEHICLE / OBD-II ADAPTER NOT DETECTED!\033[0m")
        print("=" * 65)
        print("  • No active serial adapter found on /dev/ttyUSB*, /dev/ttyACM*, or /dev/rfcomm*.")
        print("  • No active SocketCAN adapter found on can0.")
        print("  • Ensure your ELM327 / OBDLink USB or Bluetooth cable is plugged in.")
        print("  • Ensure the vehicle ignition key is turned to ON (Position 2).")
        print()
        print("  \033[1m\033[33mTo run with Citroën Grand C4 Picasso offline test data, add '--demo':\033[0m")
        print("      \033[36mpsa <command> --demo\033[0m   (or \033[36mpsa --demo\033[0m)")
        print("=" * 65 + "\n")
        sys.exit(1)
    return True

class OBDInterface:
    """Manages physical serial ELM327, native SocketCAN (can0/vcan0), or simulation."""
    def __init__(self, port: str = None, baudrate: int = 38400, force_sim: bool = False, interface: str = None, raise_on_fail: bool = False):
        self.port_name = port
        self.baudrate = baudrate
        self.force_sim = force_sim
        self.interface = interface
        self.raise_on_fail = raise_on_fail
        self.ser = None
        self.is_simulated = False
        self.is_socketcan = False
        self.connect()

    def connect(self):
        if self.force_sim:
            self.ser = SimulatedELM327()
            self.is_simulated = True
            return

        if self.interface:
            try:
                self.ser = SocketCANInterface(interface=self.interface)
                self.is_socketcan = True
                return
            except Exception as e:
                if self.raise_on_fail:
                    raise ConnectionError(f"Failed to bind SocketCAN on {self.interface}: {e}")
                print(f"[!] SocketCAN {self.interface} error: {e}. Falling back to serial...")

        target_port = self.port_name
        if not target_port:
            candidates = find_serial_ports()
            if candidates:
                target_port = candidates[0].device
                print(f"[*] Auto-detected OBD-II serial interface: {target_port} ({candidates[0].description})")
            else:
                if self.raise_on_fail:
                    raise ConnectionError("No active serial adapter found.")
                require_vehicle_or_demo(is_demo=False)
                return

        # Attempt connection to real serial port
        baud_list = [self.baudrate, 38400, 115200, 9600]
        baud_list = list(dict.fromkeys(baud_list)) # unique

        for b in baud_list:
            try:
                print(f"[*] Connecting to {target_port} at {b} baud...")
                s = serial.Serial(target_port, baudrate=b, timeout=1.5)
                s.write(b'\r\nATZ\r\n')
                time.sleep(0.5)
                resp = s.read_all().decode('ascii', errors='ignore')
                if 'ELM' in resp.upper() or 'OBD' in resp.upper() or 'OK' in resp.upper() or '>' in resp:
                    print(f"[✓] Connected successfully to ELM327 adapter on {target_port} @ {b} baud.")
                    self.ser = s
                    self.baudrate = b
                    self.port_name = target_port
                    self.init_elm()
                    return
                s.close()
            except Exception as e:
                pass

        if self.raise_on_fail:
            raise ConnectionError(f"Could not communicate with adapter on {target_port} (failed handshake).")

        print("\n" + "=" * 65)
        print(f"\033[1m\033[31m[!] ERROR: COULD NOT COMMUNICATE WITH ADAPTER ON {target_port}!\033[0m")
        print("=" * 65)
        print("  • Adapter detected but failed ATZ handshake at 38400, 115200, and 9600 baud.")
        print("  • Check port permissions: sudo usermod -aG dialout $USER")
        print("  • To run with offline test data instead, add '--demo':")
        print(f"      psa <command> --demo")
        print("=" * 65 + "\n")
        sys.exit(1)

    def init_elm(self):
        if self.is_simulated:
            return
        commands = ['ATE0', 'ATL0', 'ATS0', 'ATH1', 'ATSP6']
        for cmd in commands:
            self.send_command(cmd)

    def send_command(self, cmd: str) -> list[str]:
        if self.is_simulated:
            return self.ser.send_cmd(cmd)
        if isinstance(self.ser, SocketCANInterface):
            return self.ser.send_command(cmd)

        clean_cmd = cmd.strip() + '\r'
        self.ser.reset_input_buffer()
        self.ser.write(clean_cmd.encode('ascii'))
        
        lines = []
        raw_buffer = ""
        start_time = time.time()
        
        while time.time() - start_time < 2.5:
            if self.ser.in_waiting > 0:
                chunk = self.ser.read(self.ser.in_waiting).decode('ascii', errors='ignore')
                raw_buffer += chunk
                if '>' in chunk:
                    break
            else:
                time.sleep(0.02)

        for l in raw_buffer.split('\r'):
            l_clean = l.strip().replace('\n', '')
            if l_clean and l_clean != '>' and l_clean != cmd.strip():
                lines.append(l_clean)
        return lines

    def close(self):
        if self.ser:
            self.ser.close()

def parse_raw_dtc_lines(lines: list[str]) -> dict:
    """
    Parses ELM327 response lines with headers (ATH1) into structured DTC tuples per ECU.
    Returns: { '7E8': [('P0299', '0299'), ...], '7E9': [('P17A5', '17A5')], ... }
    """
    ecu_frames = {}
    for line in lines:
        cleaned = line.strip().replace(' ', '').upper()
        if not cleaned or any(k in cleaned for k in ['NODATA', 'SEARCHING', 'OK', 'STOPPED', 'ERROR', '?']):
            continue

        # Extract ECU CAN ID (3 hex chars)
        m = re.match(r'^([0-9A-F]{3})(.*)', cleaned)
        if m:
            ecu_id = m.group(1)
            payload = m.group(2)
            ecu_frames.setdefault(ecu_id, []).append(payload)
        else:
            ecu_frames.setdefault('UNKNOWN', []).append(cleaned)

    results = {}
    for ecu_id, frames in ecu_frames.items():
        combined_payload = ''
        for f in frames:
            # Handle ISO-TP framing
            if re.match(r'^0[0-9A-F]', f): # Single Frame (0x0L)
                combined_payload += f[2:]
            elif re.match(r'^1[0-9A-F]{3}', f): # First Frame (0x1LLL)
                combined_payload += f[4:]
            elif re.match(r'^2[0-9A-F]', f): # Consecutive Frame (0x2S)
                combined_payload += f[2:]
            else:
                combined_payload += f

        dtcs = []
        # Find Mode 43 (response to 03) or 47 (response to 07)
        m_mode = re.search(r'(43|47)([0-9A-F]{2})([0-9A-F]+)', combined_payload)
        if m_mode:
            count = int(m_mode.group(2), 16)
            dtc_bytes = m_mode.group(3)
            for i in range(0, min(count * 4, len(dtc_bytes)), 4):
                chunk = dtc_bytes[i:i+4]
                if len(chunk) == 4 and chunk != '0000':
                    raw_val = int(chunk, 16)
                    p_idx = (raw_val >> 14) & 0x03
                    p_char = ['P', 'C', 'B', 'U'][p_idx]
                    t_char = (raw_val >> 12) & 0x03
                    sub_hex = f'{raw_val & 0x0FFF:03X}'
                    std_code = f'{p_char}{t_char}{sub_hex}'
                    dtcs.append((std_code, chunk))

        # Check UDS Service 0x59 response (response to 19 02 FF)
        m_uds = re.search(r'5902FF([0-9A-F]+)', combined_payload)
        if m_uds:
            uds_bytes = m_uds.group(1)
            # UDS DTC format: 3 bytes DTC (4 hex) + 1 byte status (2 hex)
            for i in range(0, len(uds_bytes), 6):
                chunk = uds_bytes[i:i+4]
                if len(chunk) == 4 and chunk != '0000':
                    raw_val = int(chunk, 16)
                    p_idx = (raw_val >> 14) & 0x03
                    p_char = ['P', 'C', 'B', 'U'][p_idx]
                    t_char = (raw_val >> 12) & 0x03
                    sub_hex = f'{raw_val & 0x0FFF:03X}'
                    std_code = f'{p_char}{t_char}{sub_hex}'
                    if (std_code, chunk) not in dtcs:
                        dtcs.append((std_code, chunk))

        if dtcs:
            results[ecu_id] = dtcs

    return results

def log_dtc_action(action: str, raw_data: dict, decoded_report: str, port_name: str, is_sim: bool):
    """Logs the DTC action with timestamp and detailed reports."""
    ensure_log_dir()
    now = datetime.datetime.now()
    timestamp_str = now.strftime('%Y%m%d_%H%M%S')
    date_display = now.strftime('%Y-%m-%d %H:%M:%S')

    session_filename = f"dtc_{action}_{timestamp_str}.log"
    session_filepath = os.path.join(LOG_DIR, session_filename)

    with open(session_filepath, 'w', encoding='utf-8') as f:
        f.write("=================================================================\n")
        f.write(f" CITROËN GRAND C4 PICASSO (1.6 HDi / EGS6) - DIAGNOSTIC LOG\n")
        f.write("=================================================================\n")
        f.write(f"Action:         {action.upper()}\n")
        f.write(f"Timestamp:      {date_display}\n")
        f.write(f"Connection:     {'SIMULATED TEST DATA' if is_sim else f'LIVE HARDWARE ({port_name})'}\n")
        f.write(f"Vehicle:        Citroën Grand C4 Picasso Mk1 (B58) - 1.6 HDi DV6\n")
        f.write(f"Transmission:   6-Speed Piloted Manual Gearbox (EGS6 / BMP6 - CFC300P)\n")
        f.write("-----------------------------------------------------------------\n\n")
        f.write("RAW CAN / OBD-II RESPONSE FRAMES:\n")
        for ecu, dtcs in raw_data.items():
            f.write(f"  [{ecu}] -> {dtcs}\n")
        f.write("\n-----------------------------------------------------------------\n")
        f.write("DECODED DIAGNOSTIC REPORT:\n\n")
        f.write(decoded_report)
        f.write("\n=================================================================\n")

    # Append to cumulative history log
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        codes_found = []
        for dtcs in raw_data.values():
            codes_found.extend([c[0] for c in dtcs])
        code_summary = ", ".join(codes_found) if codes_found else "NO FAULTS DETECTED"
        mode_badge = "[SIM]" if is_sim else "[LIVE]"
        f.write(f"[{date_display}] {mode_badge} ACTION={action.upper()} | CODES=[{code_summary}] | LOG={session_filename}\n")

    return session_filepath
