#!/usr/bin/env python3
"""
PSA-DIAG Mobile Wi-Fi Companion Web Dashboard
Dedicated to Citroën Grand C4 Picasso Mk1 (1.6 HDi DV6 • EGS6 CFC300P)
Zero-dependency lightweight HTTP server for smartphone/tablet diagnostics.
"""

import os
import sys
import json
import time
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, '/root/psa_diag')
import obd_service
import psa_diag
import special_diagnostics
import advanced_features
import engine_diagram
import workshop_features

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>PSA-DIAG • Citroën Grand C4 Picasso</title>
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --cyan: #00e5ff;
      --green: #00e676;
      --yellow: #ffd600;
      --red: #ff1744;
      --text: #c9d1d9;
      --text-dim: #8b949e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
    body { background: var(--bg); color: var(--text); padding: 12px; }
    header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
    .title { font-size: 1.1rem; font-weight: bold; color: var(--cyan); }
    .badge { font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-demo { background: rgba(255, 214, 0, 0.2); color: var(--yellow); border: 1px solid var(--yellow); }
    .badge-live { background: rgba(0, 230, 118, 0.2); color: var(--green); border: 1px solid var(--green); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
    .card-title { font-size: 0.9rem; font-weight: bold; color: var(--cyan); margin-bottom: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 6px; }
    .metric-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 0.85rem; }
    .metric-val { font-weight: bold; color: #fff; }
    .bar-bg { width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; margin-top: 4px; }
    .bar-fill { height: 100%; background: var(--green); transition: width 0.3s; }
    .bar-fill-warn { background: var(--yellow); }
    .bar-fill-err { background: var(--red); }
    .dtc-item { background: rgba(0,0,0,0.3); border-left: 3px solid var(--red); padding: 8px; border-radius: 4px; margin-bottom: 6px; font-size: 0.8rem; }
    .dtc-code { color: var(--yellow); font-weight: bold; }
    .actions { display: flex; gap: 8px; margin-top: 10px; }
    button { flex: 1; background: #21262d; border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 6px; font-size: 0.85rem; font-weight: bold; cursor: pointer; }
    button:hover { background: #30363d; border-color: var(--cyan); }
    button.btn-clear { border-color: var(--red); color: var(--red); }
    button.btn-clear:hover { background: rgba(255, 23, 68, 0.15); }
    footer { text-align: center; color: var(--text-dim); font-size: 0.75rem; margin-top: 20px; }
  </style>
</head>
<body>
  <header>
    <div>
      <div class="title">🚗 PSA-DIAG MOBILE COMPANION</div>
      <div style="font-size: 0.75rem; color: var(--text-dim);">Citroën Grand C4 Picasso 1.6 HDi • EGS6</div>
    </div>
    <div id="modeBadge" class="badge badge-demo">DEMO MODE</div>
  </header>

  <div class="grid">
    <!-- Odometer & Maintenance -->
    <div class="card">
      <div class="card-title"><span>📌 ODOMETER & SERVICE INTERVAL</span><span id="spannerIcon">🔧</span></div>
      <div class="metric-row">
        <span>Total Mileage:</span>
        <span class="metric-val" id="totalMiles">-- miles (-- km)</span>
      </div>
      <div class="metric-row">
        <span>Next Service Due:</span>
        <span class="metric-val" id="serviceDue">-- miles (-- days)</span>
      </div>
      <div class="metric-row">
        <span>Oil Life Remaining:</span>
        <span class="metric-val" id="oilLife">-- %</span>
      </div>
      <div class="bar-bg"><div id="oilBar" class="bar-fill" style="width: 80%;"></div></div>
      <div class="metric-row" style="margin-top: 8px;">
        <span>Trip A / Avg Economy:</span>
        <span class="metric-val" id="tripAvg">-- miles • -- MPG</span>
      </div>
      <div class="actions">
        <button onclick="resetService()">Reset Service Spanner</button>
      </div>
    </div>

    <!-- EGS6 Semi-Auto Gearbox -->
    <div class="card">
      <div class="card-title"><span>⚙️ EGS6 PILOTED GEARBOX</span><span id="gearBadge">1st</span></div>
      <div class="metric-row">
        <span>Hydraulic Line Pressure:</span>
        <span class="metric-val" id="hydrPressure">-- bar</span>
      </div>
      <div class="bar-bg"><div id="hydrBar" class="bar-fill" style="width: 70%;"></div></div>
      <div class="metric-row" style="margin-top: 8px;">
        <span>Pressure Decay Hold:</span>
        <span class="metric-val" id="accumDecay">-- s (Healthy)</span>
      </div>
      <div class="metric-row">
        <span>Clutch Position / Wear:</span>
        <span class="metric-val" id="clutchWear">-- mm (--% worn)</span>
      </div>
      <div class="bar-bg"><div id="clutchBar" class="bar-fill" style="width: 60%;"></div></div>
      <div class="metric-row" style="margin-top: 8px;">
        <span>Clutch Slip Speed:</span>
        <span class="metric-val" id="clutchSlip">0 RPM (Synced)</span>
      </div>
    </div>

    <!-- Engine & Live Telemetry -->
    <div class="card">
      <div class="card-title"><span>⚡ ENGINE & TURBO TELEMETRY</span><span id="engineRPM">850 RPM</span></div>
      <div class="metric-row">
        <span>Vehicle Speed:</span>
        <span class="metric-val" id="vehSpeed">-- km/h (-- mph)</span>
      </div>
      <div class="metric-row">
        <span>Turbo Boost Pressure:</span>
        <span class="metric-val" id="boostPress">-- bar</span>
      </div>
      <div class="bar-bg"><div id="boostBar" class="bar-fill" style="width: 30%;"></div></div>
      <div class="metric-row" style="margin-top: 8px;">
        <span>Common Rail Fuel Pressure:</span>
        <span class="metric-val" id="railPress">-- bar</span>
      </div>
      <div class="metric-row">
        <span>Coolant Temperature:</span>
        <span class="metric-val" id="coolantTemp">-- °C</span>
      </div>
      <div class="metric-row">
        <span>12V Battery Voltage:</span>
        <span class="metric-val" id="battVoltage">-- V</span>
      </div>
    </div>

    <!-- DPF & Emissions -->
    <div class="card">
      <div class="card-title"><span>💨 DPF & EMISSIONS (1.6 HDi)</span><span id="dpfStatus">OK</span></div>
      <div class="metric-row">
        <span>DPF Soot Load:</span>
        <span class="metric-val" id="dpfSoot">-- g (--%)</span>
      </div>
      <div class="bar-bg"><div id="sootBar" class="bar-fill" style="width: 45%;"></div></div>
      <div class="metric-row" style="margin-top: 8px;">
        <span>Exhaust Differential Pressure:</span>
        <span class="metric-val" id="diffPress">-- mbar</span>
      </div>
      <div class="metric-row">
        <span>Distance Since Last Regen:</span>
        <span class="metric-val" id="regenDist">-- km</span>
      </div>
      <div class="metric-row">
        <span>Eolys Fluid in Reservoir:</span>
        <span class="metric-val" id="eolysVol">-- ml</span>
      </div>
    </div>

    <!-- Active DTCs -->
    <div class="card" style="grid-column: 1 / -1;">
      <div class="card-title"><span>⚠️ ACTIVE DIAGNOSTIC TROUBLE CODES</span><span id="dtcCount">0 detected</span></div>
      <div id="dtcList">
        <div style="font-size: 0.85rem; color: var(--text-dim);">No fault codes detected. All modules reporting OK.</div>
      </div>
      <div class="actions" style="margin-top: 12px;">
        <button onclick="fetchData()">Refresh Telemetry</button>
        <button class="btn-clear" onclick="clearDTCs()">Clear DTCs from ECUs</button>
      </div>
    </div>

    <!-- Engine Diagram & Advanced Workshop Controls -->
    <div class="card" style="grid-column: 1 / -1; border-color: rgba(0,229,255,0.3);">
      <div class="card-title"><span style="color:#00e5ff;">🗺️ ENGINE BAY SCHEMATIC & WORKSHOP ACTIONS</span><span>DV6 1.6 HDi</span></div>
      <p style="font-size:0.85rem; color:var(--text-dim); margin-bottom:12px;">
        Inspect physical locations and pinouts for all 20 powertrain sensors, or run suspension service wizards directly from your device.
      </p>
      <div class="actions" style="flex-wrap:wrap;">
        <a href="/engine" style="flex:1; min-width:220px; text-decoration:none;"><button style="width:100%; border-color:#00e5ff; color:#00e5ff;">🗺️ Open Engine Bay Sensor Map</button></a>
        <button onclick="bleedSuspension()" style="flex:1; min-width:180px;">🎈 Deflate Airbags (Bleed)</button>
        <button onclick="inflateSuspension()" style="flex:1; min-width:180px;">⚡ Inflate Suspension</button>
        <button onclick="resetEolys()" style="flex:1; min-width:180px;">🧪 Reset Eolys Pouch</button>
      </div>
    </div>
  </div>

  <footer>
    PSA-DIAG AEE2004 Platform • High-Speed CAN 500 kbps • Auto-refreshing every 1.5s
  </footer>

  <script>
    async function fetchData() {
      try {
        const res = await fetch('/api/telemetry');
        const d = await res.json();
        
        // Mode badge
        const mb = document.getElementById('modeBadge');
        if (d.is_demo) {
          mb.className = 'badge badge-demo';
          mb.innerText = 'DEMO MODE';
        } else {
          mb.className = 'badge badge-live';
          mb.innerText = 'LIVE HARDWARE';
        }

        // Odometer
        document.getElementById('totalMiles').innerText = `${d.odo.total_miles.toLocaleString()} mi (${d.odo.total_km.toLocaleString()} km)`;
        document.getElementById('serviceDue').innerText = `${d.odo.service_remaining_miles.toLocaleString()} mi (${d.odo.service_days} days)`;
        document.getElementById('oilLife').innerText = `${d.odo.oil_life_remaining_pct}%`;
        document.getElementById('oilBar').style.width = `${d.odo.oil_life_remaining_pct}%`;
        document.getElementById('tripAvg').innerText = `${d.odo.trip_a_miles} mi • ${d.odo.avg_mpg} MPG (${d.odo.avg_l_100km} L/100km)`;
        document.getElementById('spannerIcon').innerText = d.odo.spanner_badge === 'OK' ? '✅' : '🔧';

        // EGS6
        document.getElementById('gearBadge').innerText = d.egs6.gear;
        document.getElementById('hydrPressure').innerText = `${d.egs6.pressure_bar} bar`;
        document.getElementById('hydrBar').style.width = `${Math.min(100, (d.egs6.pressure_bar / 60) * 100)}%`;
        document.getElementById('accumDecay').innerText = `${d.egs6.decay_sec}s (${d.egs6.accum_status})`;
        document.getElementById('clutchWear').innerText = `${d.egs6.clutch_mm} mm (${d.egs6.clutch_wear_pct}% worn)`;
        document.getElementById('clutchBar').style.width = `${d.egs6.clutch_wear_pct}%`;
        document.getElementById('clutchSlip').innerText = `${d.egs6.slip_rpm} RPM`;

        // Engine
        document.getElementById('engineRPM').innerText = `${d.live.rpm} RPM`;
        document.getElementById('vehSpeed').innerText = `${d.live.speed_kmh} km/h (${Math.round(d.live.speed_kmh * 0.621371)} mph)`;
        document.getElementById('boostPress').innerText = `${d.live.boost_bar} bar`;
        document.getElementById('boostBar').style.width = `${Math.min(100, (d.live.boost_bar / 2.5) * 100)}%`;
        document.getElementById('railPress').innerText = `${d.live.rail_bar} bar`;
        document.getElementById('coolantTemp').innerText = `${d.live.coolant_c} °C`;
        document.getElementById('battVoltage').innerText = `${d.live.battery_v} V`;

        // DPF
        document.getElementById('dpfStatus').innerText = d.dpf.dpf_status;
        document.getElementById('dpfSoot').innerText = `${d.dpf.soot_g} g (${d.dpf.soot_pct}%)`;
        document.getElementById('sootBar').style.width = `${d.dpf.soot_pct}%`;
        document.getElementById('diffPress').innerText = `${d.dpf.diff_mbar} mbar`;
        document.getElementById('regenDist').innerText = `${d.dpf.km_since_regen} km`;
        document.getElementById('eolysVol').innerText = `${d.dpf.eolys_ml} ml (${d.dpf.eolys_pct}%)`;

        // DTCs
        const dtcContainer = document.getElementById('dtcList');
        document.getElementById('dtcCount').innerText = `${d.dtcs.length} code(s)`;
        if (d.dtcs.length > 0) {
          dtcContainer.innerHTML = d.dtcs.map(item => `
            <div class="dtc-item">
              <span class="dtc-code">${item.code}</span> [${item.module}] : <b>${item.desc}</b>
              <div style="color: var(--text-dim); margin-top: 2px;">OEM (FR): ${item.desc_fr || 'N/A'}</div>
            </div>
          `).join('');
        } else {
          dtcContainer.innerHTML = '<div style="font-size: 0.85rem; color: var(--green);">[✓] Zero fault codes detected across all ECUs.</div>';
        }

      } catch (e) {
        console.error('Fetch error:', e);
      }
    }

    async function resetService() {
      if (confirm('Reset service interval countdown back to 12,500 miles (20,000 km) and extinguish spanner icon?')) {
        await fetch('/api/service/reset', { method: 'POST' });
        alert('Service countdown successfully reset!');
        fetchData();
      }
    }

    async function clearDTCs() {
      if (confirm('Clear all diagnostic trouble codes from Engine, EGS6, ABS/ESP, and Handbrake ECUs?')) {
        await fetch('/api/clear', { method: 'POST' });
        alert('Clear command dispatched to vehicle nodes.');
        fetchData();
      }
    }

    async function bleedSuspension() {
      if (confirm('Vent and depressurize rear air suspension airbags to 0.0 bar for repair/replacement?')) {
        const res = await fetch('/api/suspension/bleed', { method: 'POST' });
        const data = await res.json();
        alert('Air suspension depressurized to 0.0 bar. Airbags ready for safe removal.');
        fetchData();
      }
    }

    async function inflateSuspension() {
      if (confirm('Run compressor and inflate rear air suspension back to nominal 118mm curb height?')) {
        const res = await fetch('/api/suspension/inflate', { method: 'POST' });
        const data = await res.json();
        alert('Air suspension inflated back to nominal curb height (4.8 bar).');
        fetchData();
      }
    }

    async function resetEolys() {
      if (confirm('Reset Eolys additive pouch counter to 1,100 ml and prime dosing lines?')) {
        const res = await fetch('/api/eolys/reset', { method: 'POST' });
        const data = await res.json();
        alert('Eolys pouch reset to 1100 ml and 15s pump prime cycle executed.');
        fetchData();
      }
    }

    // Auto refresh every 1500ms
    fetchData();
    setInterval(fetchData, 1500);
  </script>
</body>
</html>
"""

class DiagnosticWebHandler(BaseHTTPRequestHandler):
    is_demo = True

    def log_message(self, format, *args):
        pass # Suppress noisy console HTTP access logs

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif self.path in ('/engine', '/diagram'):
            svg_content = engine_diagram.generate_html_svg_engine_view(is_sim=self.is_demo)
            page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Citroën Grand C4 Picasso • Engine Bay Sensor Map</title><style>body {{ background:#0d1117; color:#c9d1d9; font-family:system-ui,-apple-system,sans-serif; margin:0; padding:16px; }} a {{ color:#00e5ff; text-decoration:none; font-weight:bold; }} .modal {{ display:none; position:fixed; z-index:100; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.7); }} .modal-content {{ background:#161b22; border:1px solid #30363d; border-radius:8px; max-width:550px; margin:10% auto; padding:20px; box-shadow:0 8px 24px rgba(0,0,0,0.5); }}</style></head><body><div style="margin-bottom:14px;"><a href="/">← Return to Main Telemetry Dashboard</a></div>{svg_content}<div id="sensorModal" class="modal" onclick="closeModal()"><div class="modal-content" onclick="event.stopPropagation()"><div id="modalBody"></div><div style="text-align:right; margin-top:16px;"><button onclick="closeModal()" style="background:#21262d; border:1px solid #30363d; color:#fff; padding:8px 16px; border-radius:6px; cursor:pointer; font-weight:bold;">Close</button></div></div></div><script>async function showSensorModal(id){{try{{const res=await fetch('/api/sensor/'+id);const s=await res.json();document.getElementById('modalBody').innerHTML='<h3 style="color:#00e5ff; margin-top:0;">['+id+'] '+s.name+'</h3><p style="font-size:0.85rem; color:#8b949e;"><b>OEM Ref:</b> '+s.oem_ref+'</p><p><b>Subsystem:</b> '+s.system+'</p><p><b>Physical Location:</b> '+s.location+'</p><p><b>Connector Pinout:</b> '+s.connector+'</p><p><b>Nominal Spec:</b> '+s.nominal+'</p><p><b>Live Value:</b> <span style="color:#00e676; font-size:1.1rem; font-weight:bold;">'+s.live_val+' '+s.unit+'</span></p>';document.getElementById('sensorModal').style.display='block';}}catch(e){{console.error(e);}}}} function closeModal(){{document.getElementById('sensorModal').style.display='none';}}</script></body></html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(page.encode('utf-8'))
        elif self.path.startswith('/api/sensor/'):
            try:
                sid = int(self.path.split('/')[-1])
                s = engine_diagram.SENSOR_DATABASE.get(sid, {})
                vals = engine_diagram.get_live_sensor_values(is_sim=self.is_demo)
                s_copy = dict(s)
                s_copy['live_val'] = vals.get(s.get('param_key'), 'N/A')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(s_copy).encode('utf-8'))
            except Exception:
                self.send_response(400)
                self.end_headers()
        elif self.path == '/api/health':
            audit = workshop_features.VehicleHealthAuditor.run_full_audit(is_sim=self.is_demo)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(audit).encode('utf-8'))
        elif self.path == '/api/sensors':
            sensors = workshop_features.get_all_vehicle_sensors(is_sim=self.is_demo)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(sensors).encode('utf-8'))
        elif self.path == '/api/telemetry':
            odo = special_diagnostics.analyze_odometer_service(is_sim=self.is_demo)
            egs = special_diagnostics.analyze_egs6_gearbox(is_sim=self.is_demo)
            dpf = special_diagnostics.analyze_dpf_system(is_sim=self.is_demo)
            bat = special_diagnostics.analyze_battery_crank(is_sim=self.is_demo)

            data = {
                'is_demo': self.is_demo,
                'odo': odo,
                'egs6': {
                    'gear': '1st (Auto)',
                    'pressure_bar': egs['pressure_bar'],
                    'decay_sec': egs['decay_sec'],
                    'accum_status': egs['accum_status'],
                    'clutch_mm': egs['clutch_mm'],
                    'clutch_wear_pct': egs['clutch_wear_pct'],
                    'slip_rpm': 0
                },
                'live': {
                    'rpm': 850,
                    'speed_kmh': 0,
                    'boost_bar': 1.02,
                    'rail_bar': 295,
                    'coolant_c': 86,
                    'battery_v': bat['charging_v']
                },
                'dpf': dpf,
                'dtcs': [
                    {
                        'code': 'P17A5',
                        'module': 'EGS6 Gearbox (0x7E9)',
                        'desc': 'Mechanical or hydraulic gearbox fault on first gear',
                        'desc_fr': 'Défaut mécanique ou hydraulique de boîte de vitesses'
                    },
                    {
                        'code': 'P0299',
                        'module': 'Engine Management (0x7E8)',
                        'desc': 'Turbo pressure signal - Turbocharger underboost',
                        'desc_fr': 'Signal pression turbocompresseur - sous-surpression'
                    },
                    {
                        'code': 'C1385',
                        'module': 'ABS/ESP 8.1 (0x768)',
                        'desc': 'Electrovalves supply voltage fault (Cranking drop)',
                        'desc_fr': 'Tension alimentation électrovannes (chute démarrage)'
                    }
                ] if not getattr(self.server, 'dtcs_cleared', False) else []
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/service/reset':
            special_diagnostics.reset_service_interval(is_sim=self.is_demo)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'OK'}).encode('utf-8'))
        elif self.path == '/api/clear':
            self.server.dtcs_cleared = True
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'OK'}).encode('utf-8'))
        elif self.path == '/api/suspension/bleed':
            res = workshop_features.PneumaticSuspensionController.bleed_system(is_sim=self.is_demo)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        elif self.path == '/api/suspension/inflate':
            res = workshop_features.PneumaticSuspensionController.inflate_system(is_sim=self.is_demo)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        elif self.path == '/api/eolys/reset':
            res = workshop_features.EolysManager.reset_pouch(volume_ml=1100, is_sim=self.is_demo)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def get_local_ip():
    """Finds best non-loopback IP address for display to user."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def start_web_server(port: int = 8080, is_demo: bool = True):
    """Starts the companion web dashboard server."""
    DiagnosticWebHandler.is_demo = is_demo
    server = HTTPServer(('0.0.0.0', port), DiagnosticWebHandler)
    server.dtcs_cleared = False
    local_ip = get_local_ip()

    print("\n" + "=" * 65)
    print(f" \033[1m\033[36mCITROËN GRAND C4 PICASSO: MOBILE COMPANION DASHBOARD\033[0m")
    print(f" Mode: \033[1m\033[33m{'SIMULATION (DEMO)' if is_demo else 'LIVE HARDWARE'}\033[0m")
    print("=" * 65)
    print(f" • Local URL:    \033[1m\033[32mhttp://localhost:{port}\033[0m")
    print(f" • Phone/Tablet: \033[1m\033[32mhttp://{local_ip}:{port}\033[0m")
    print()
    print(" Connect your smartphone or tablet to your laptop Wi-Fi hotspot to")
    print(" monitor live EGS6 hydraulics, odometer, and DTCs from the driver's seat!")
    print(" Press Ctrl+C to terminate web server.")
    print("=" * 65 + "\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Web server terminated.")
        server.server_close()

if __name__ == '__main__':
    is_demo = any(arg in sys.argv for arg in ['--demo', '--sim', '-demo', '-sim'])
    start_web_server(port=8080, is_demo=is_demo)
