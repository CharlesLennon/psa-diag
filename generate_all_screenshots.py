#!/usr/bin/env python3
"""
PSA-DIAG Enhanced Screenshot Generator (V2)
Produces realistic, high-fidelity visual assets for GitHub README:
1. screenshot_01_engine_bay_diagram.png (Composite of real 3D DV6 engine bay + HUD diagnostic callout overlay)
2. screenshot_02_tui_engine_tab.png (TUI Tab 8 with contoured mechanical engine ASCII art)
3. screenshot_03_tui_livedata.png (TUI Tab 2 with live sparklines and hierarchical gauges)
4. screenshot_04_tui_dtc_scan.png (TUI Tab 1 with deep PSA freeze-frame environmental telemetry)
5. screenshot_05_connection_wizard.png (Connection wizard with OBD physical pinout bus diagnostics)
6. screenshot_06_health_scorecard.png (Realistic 82/100 Pre-Purchase Inspection scorecard with authentic DV6 findings)
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, '/root/psa_diag')
import engine_diagram

OUTPUT_DIR = "/root/psa_diag/screenshots"
ARTIFACT_DIR = "/root/.gemini/antigravity-cli/brain/e9c76695-36c4-430d-99fa-5fef81e4a748"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# Fonts
FONT_TITLE = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
FONT_SUB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
FONT_HEAD = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
FONT_TEXT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
FONT_TEXT_BOLD = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 11)
FONT_MONO = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 12)
FONT_MONO_SM = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 10)
FONT_MONO_XS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 9)
FONT_TUI = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 12)
FONT_TUI_BOLD = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 12)

# ==============================================================================
# 1. SCREENSHOT 01: REALISTIC 3D DV6 ENGINE BAY DIAGNOSTIC HUD
# ==============================================================================

def generate_screenshot_01():
    print("Generating Screenshot 01: Realistic DV6 Engine Bay Diagnostic HUD...")
    W, H = 1920, 1080
    canvas = Image.new('RGB', (W, H), '#080b0f')
    draw = ImageDraw.Draw(canvas)

    # 1. Header Bar
    draw.rectangle([(0, 0), (W, 70)], fill='#0d1117')
    draw.line([(0, 70), (W, 70)], fill='#00e5ff', width=2)
    
    # Title & Subtitle
    draw.text((28, 14), "CITROËN GRAND C4 PICASSO Mk1 (B58) • 1.6 HDi DV6TED4 (9HZ)", fill='#ffffff', font=FONT_TITLE)
    draw.text((28, 42), "20-NODE POWERTRAIN SENSOR & ACTUATOR ARCHITECTURE • BOSCH EDC16C34 • EGS6 CFC300P", fill='#00e5ff', font=FONT_SUB)

    # Header Badges
    badges = [
        ("CAN 2.0B 500k", "#00e676"),
        ("BOSCH EDC16", "#00e5ff"),
        ("EGS6 PILOT", "#ffd600"),
        ("CAAR AIR SUSP", "#b388ff"),
        ("ONLINE [DEMO]", "#00e676")
    ]
    bx = W - 30
    for txt, col in reversed(badges):
        tw = draw.textlength(txt, font=FONT_MONO_SM) + 16
        bx -= tw + 8
        draw.rounded_rectangle([(bx, 20), (bx + tw, 48)], radius=4, fill='#161b22', outline=col, width=1)
        draw.text((bx + 8, 27), txt, fill=col, font=FONT_MONO_SM)

    # 2. Engine Model Render Placement (Left Area: 1220 x 870)
    img_model_path = "/root/psa_diag/screenshots/engine_bay_3d_model.jpg"
    img_engine = Image.open(img_model_path)
    
    # Scale engine to fit
    eng_box_w = 1220
    eng_box_h = int(eng_box_w * (img_engine.height / img_engine.width)) # approx 680
    eng_resized = img_engine.resize((eng_box_w, eng_box_h), Image.Resampling.LANCZOS)
    
    # Engine display container frame
    frame_x, frame_y = 24, 88
    frame_w, frame_h = 1240, 910
    draw.rounded_rectangle([(frame_x, frame_y), (frame_x + frame_w, frame_y + frame_h)], radius=8, fill='#0d1117', outline='#21262d', width=2)
    
    # Paste resized engine model
    canvas.paste(eng_resized, (frame_x + 10, frame_y + 10))

    # Corner HUD brackets on engine frame
    bracket_len = 24
    brackets = [
        ((frame_x + 10, frame_y + 10), (frame_x + 10 + bracket_len, frame_y + 10), (frame_x + 10, frame_y + 10 + bracket_len)),
        ((frame_x + frame_w - 10, frame_y + 10), (frame_x + frame_w - 10 - bracket_len, frame_y + 10), (frame_x + frame_w - 10, frame_y + 10 + bracket_len)),
        ((frame_x + 10, frame_y + frame_h - 10), (frame_x + 10 + bracket_len, frame_y + frame_h - 10), (frame_x + 10, frame_y + frame_h - 10 - bracket_len)),
        ((frame_x + frame_w - 10, frame_y + frame_h - 10), (frame_x + frame_w - 10 - bracket_len, frame_y + frame_h - 10), (frame_x + frame_w - 10, frame_y + frame_h - 10 - bracket_len)),
    ]
    for p_corner, p_h, p_v in brackets:
        draw.line([p_corner, p_h], fill='#00e5ff', width=3)
        draw.line([p_corner, p_v], fill='#00e5ff', width=3)

    # 3. Precise Engine Component HUD Pins & Callout Cards
    # Coords relative to (frame_x + 10, frame_y + 10)
    ox, oy = frame_x + 10, frame_y + 10
    callouts = [
        (1, "MAF & IAT SENSOR", 485.0, "mg/str", ox + 220, oy + 320, ox + 140, oy + 240, "#00e5ff"),
        (2, "GARRETT GT1544V TURBO", 1.02, "bar", ox + 610, oy + 260, ox + 610, oy + 160, "#ff9100"),
        (3, "CHARGE INTERCOOLER", 0.04, "bar dp", ox + 420, oy + 160, ox + 320, oy + 100, "#00e5ff"),
        (4, "MAP / IAT SENSOR", 1024, "mbar", ox + 490, oy + 290, ox + 380, oy + 220, "#00e5ff"),
        (5, "CP1H HP FUEL PUMP", 38.5, "°C", ox + 380, oy + 390, ox + 260, oy + 440, "#ffd600"),
        (6, "COMMON FUEL RAIL", 298.0, "bar", ox + 560, oy + 380, ox + 560, oy + 470, "#ffd600"),
        (8, "INJECTORS 1-4 (Cyl 1 R)", "+0.2", "mg", ox + 650, oy + 360, ox + 760, oy + 430, "#ffd600"),
        (10, "PRE-CAT EGT SENSOR", 188.0, "°C", ox + 720, oy + 220, ox + 840, oy + 150, "#ff1744"),
        (11, "DPF / CATALYST CANISTER", 18.4, "g soot", ox + 700, oy + 280, ox + 860, oy + 250, "#ff5252"),
        (13, "EGR VALVE ACTUATOR", 34.0, "%", ox + 820, oy + 330, ox + 950, oy + 350, "#b388ff"),
        (14, "COOLANT TEMP (ECT)", 86.4, "°C", ox + 770, oy + 440, ox + 890, oy + 480, "#00e676"),
        (17, "EGS6 PILOTED GEARBOX", "N", "gear", ox + 810, oy + 530, ox + 950, oy + 580, "#00e5ff"),
        (18, "EGS6 HYDRAULIC ACCUM", 48.2, "bar", ox + 710, oy + 560, ox + 600, oy + 610, "#00e5ff"),
        (20, "12V BATTERY & BSM FUSE", 14.28, "V", ox + 960, oy + 380, ox + 1070, oy + 440, "#ffd600"),
    ]

    for cid, cname, cval, cunit, px, py, cx, cy, col in callouts:
        # Target Pin circle at actual component
        draw.ellipse([(px - 8, py - 8), (px + 8, py + 8)], fill=col, outline='#ffffff', width=2)
        draw.ellipse([(px - 14, py - 14), (px + 14, py + 14)], fill=None, outline=col, width=1)
        
        # Leader line with elbow
        elbow_x = cx - 20 if cx > px else cx + 20
        draw.line([(px, py), (elbow_x, cy), (cx, cy)], fill=col, width=2)
        
        # HUD Tag box
        tag_w = 175
        tag_h = 36
        tag_x = cx if cx < px else cx - tag_w
        tag_y = cy - tag_h // 2
        
        draw.rounded_rectangle([(tag_x, tag_y), (tag_x + tag_w, tag_y + tag_h)], radius=4, fill='#161b22', outline=col, width=1)
        draw.text((tag_x + 8, tag_y + 4), f"[{cid:02d}] {cname}", fill='#ffffff', font=FONT_TEXT_BOLD)
        draw.text((tag_x + 8, tag_y + 18), f"{cval} {cunit}", fill=col, font=FONT_MONO_SM)

    # Bottom Telemetry Bar inside engine frame (frame_y + frame_h - 180 to bottom)
    bar_y = frame_y + eng_box_h + 16
    draw.rounded_rectangle([(frame_x + 10, bar_y), (frame_x + frame_w - 10, frame_y + frame_h - 10)], radius=6, fill='#11161d', outline='#30363d', width=1)
    
    # 6 Live Gauges in bottom strip
    gauges = [
        ("ENGINE RPM", "850 RPM", "Idle Nominal", "#00e676", 850, 4500),
        ("RAIL PRESSURE", "298 bar", "Target: 295 bar", "#ffd600", 298, 1600),
        ("TURBO BOOST", "1.02 bar", "Max: 2.35 bar", "#ff9100", 1.02, 2.5),
        ("COOLANT (ECT)", "86.4 °C", "Thermostat OK", "#00e676", 86.4, 120),
        ("EGS6 HYDRAULIC", "48.2 bar", "Pump Cutout 50b", "#00e5ff", 48.2, 60),
        ("BATTERY / BSM", "14.28 V", "Alternator Charging", "#00e676", 14.28, 16),
    ]
    gw = (frame_w - 40) // 6
    for i, (gtitle, gval, gsub, gcol, val_num, max_num) in enumerate(gauges):
        gx = frame_x + 18 + i * gw
        gy = bar_y + 8
        draw.text((gx, gy), gtitle, fill='#8b949e', font=FONT_MONO_XS)
        draw.text((gx, gy + 16), gval, fill=gcol, font=FONT_HEAD)
        draw.text((gx, gy + 34), gsub, fill='#8b949e', font=FONT_MONO_XS)
        
        # Mini bar
        pct = min(1.0, val_num / max_num)
        bar_len = gw - 24
        draw.rectangle([(gx, gy + 52), (gx + bar_len, gy + 56)], fill='#21262d')
        draw.rectangle([(gx, gy + 52), (gx + int(bar_len * pct), gy + 56)], fill=gcol)

    # 4. Right Sidebar: 20-Node Sensor & Telemetry Matrix (x=1284, w=612)
    side_x, side_y = 1284, 88
    side_w, side_h = 612, 910
    draw.rounded_rectangle([(side_x, side_y), (side_x + side_w, side_y + side_h)], radius=8, fill='#0d1117', outline='#21262d', width=2)
    
    # Sidebar Header
    draw.rectangle([(side_x, side_y), (side_x + side_w, side_y + 44)], fill='#161b22')
    draw.text((side_x + 16, side_y + 14), "POWERTRAIN SENSOR TELEMETRY & PINOUT MATRIX", fill='#00e5ff', font=FONT_HEAD)
    draw.line([(side_x, side_y + 44), (side_x + side_w, side_y + 44)], fill='#30363d', width=1)

    # Table Column Headers
    ty = side_y + 48
    draw.rectangle([(side_x + 6, ty), (side_x + side_w - 6, ty + 24)], fill='#11161d')
    draw.text((side_x + 14, ty + 6), "ID", fill='#8b949e', font=FONT_MONO_XS)
    draw.text((side_x + 40, ty + 6), "SENSOR NAME", fill='#8b949e', font=FONT_MONO_XS)
    draw.text((side_x + 230, ty + 6), "LIVE VALUE", fill='#8b949e', font=FONT_MONO_XS)
    draw.text((side_x + 340, ty + 6), "STATUS", fill='#8b949e', font=FONT_MONO_XS)
    draw.text((side_x + 430, ty + 6), "CONNECTOR / PINOUT", fill='#8b949e', font=FONT_MONO_XS)

    # Table rows
    ty += 28
    vals = engine_diagram.get_live_sensor_values(is_sim=True)
    row_h = 41
    for sid in range(1, 21):
        s = engine_diagram.SENSOR_DATABASE[sid]
        v = vals.get(s['param_key'], 'N/A')
        u = s['unit']
        st_txt, _ = engine_diagram.evaluate_sensor_status(v, s)
        badge_col = '#00e676' if st_txt in ('NOMINAL', 'OK') else '#ffd600'
        
        bg_col = '#11161d' if sid % 2 == 0 else '#0d1117'
        draw.rectangle([(side_x + 6, ty), (side_x + side_w - 6, ty + row_h - 2)], fill=bg_col)
        
        # ID & Name
        draw.text((side_x + 12, ty + 6), f"[{sid:02d}]", fill='#00e5ff', font=FONT_MONO_SM)
        draw.text((side_x + 40, ty + 6), s['name'][:24], fill='#ffffff', font=FONT_TEXT_BOLD)
        draw.text((side_x + 40, ty + 22), s['location'][:26], fill='#8b949e', font=FONT_MONO_XS)
        
        # Live Value
        draw.text((side_x + 230, ty + 12), f"{v} {u}", fill='#00e676', font=FONT_MONO_SM)
        
        # Status Badge
        draw.rounded_rectangle([(side_x + 340, ty + 10), (side_x + 412, ty + 28)], radius=3, fill='#161b22', outline=badge_col, width=1)
        draw.text((side_x + 348, ty + 13), st_txt, fill=badge_col, font=FONT_MONO_XS)
        
        # Pinout info
        draw.text((side_x + 430, ty + 12), s['connector'][:22] + "...", fill='#c9d1d9', font=FONT_MONO_XS)
        
        ty += row_h

    # 5. Bottom Status Ticker Bar (H - 60 to H - 10)
    bot_y = H - 60
    draw.rectangle([(0, bot_y), (W, H)], fill='#0d1117')
    draw.line([(0, bot_y), (W, bot_y)], fill='#21262d', width=1)
    
    status_left = "● LINK ACTIVE: SocketCAN /dev/ttyUSB0 (STN1170 OBDLink SX @ 115,200 bps) • Protocol: ISO 15765-4 (CAN 11-bit / 500 kbps)"
    status_right = "CAN Frames: 1,842 fps • Bus Load: 28.4% • Error Counter: 0 • PSA DTC Cache: 40,752 definitions"
    draw.text((28, bot_y + 18), status_left, fill='#00e676', font=FONT_MONO_SM)
    rw = draw.textlength(status_right, font=FONT_MONO_SM)
    draw.text((W - rw - 28, bot_y + 18), status_right, fill='#8b949e', font=FONT_MONO_SM)

    out_path = os.path.join(OUTPUT_DIR, "screenshot_01_engine_bay_diagram.png")
    art_path = os.path.join(ARTIFACT_DIR, "screenshot_01_engine_bay_diagram.png")
    canvas.save(out_path, format="PNG")
    canvas.save(art_path, format="PNG")
    print(f"Screenshot 01 saved successfully ({os.path.getsize(out_path)} bytes)")

# ==============================================================================
# 2. SCREENSHOT 02: TUI TAB 8 - CONTOURED ENGINE SCHEMATIC & SENSOR INSPECTOR
# ==============================================================================

def generate_screenshot_02():
    print("Generating Screenshot 02: TUI Tab 8 Contoured Engine Inspector...")
    W, H = 1200, 800
    img = Image.new('RGB', (W, H), '#080b0f')
    draw = ImageDraw.Draw(img)

    # Terminal Window Frame
    draw.rectangle([(0, 0), (W, 36)], fill='#161b22')
    draw.text((16, 10), "PSA-DIAG Terminal Workstation • 2010 Citroën Grand C4 Picasso Mk1 (B58) 1.6 HDi", fill='#c9d1d9', font=FONT_HEAD)
    
    # Window controls (macOS/X11 style dots)
    draw.ellipse([(W - 60, 12), (W - 48, 24)], fill='#ff5f56')
    draw.ellipse([(W - 40, 12), (W - 28, 24)], fill='#ffbd2e')
    draw.ellipse([(W - 20, 12), (W - 8, 24)], fill='#27c93f')

    # Tab bar
    draw.rectangle([(0, 36), (W, 70)], fill='#0d1117')
    draw.line([(0, 70), (W, 70)], fill='#30363d', width=1)
    
    tabs = [
        ("1:DTC Scan", False),
        ("2:LiveData", False),
        ("3:Actuators", False),
        ("4:Tools", False),
        ("5:Telecode", False),
        ("6:Sniffer", False),
        ("7:LogPlayer", False),
        ("8:Engine", True),
        ("9:Audit", False)
    ]
    tx = 16
    for tname, active in tabs:
        tw = draw.textlength(tname, font=FONT_MONO) + 20
        if active:
            draw.rectangle([(tx, 42), (tx + tw, 70)], fill='#1c2128')
            draw.line([(tx, 42), (tx + tw, 42)], fill='#00e5ff', width=3)
            draw.text((tx + 10, 50), tname, fill='#00e5ff', font=FONT_MONO)
        else:
            draw.text((tx + 10, 50), tname, fill='#8b949e', font=FONT_MONO)
        tx += tw + 4

    # Dual Pane Split: Left Engine Contours (x=16, w=590), Right Sensor Catalog (x=618, w=566)
    draw.rectangle([(16, 80), (606, 750)], fill='#0d1117', outline='#30363d', width=1)
    draw.rectangle([(618, 80), (1184, 750)], fill='#0d1117', outline='#30363d', width=1)
    
    # Left Pane Header
    draw.rectangle([(16, 80), (606, 110)], fill='#161b22')
    draw.text((28, 88), "ENGINE BAY PHYSICAL TOP-DOWN SCHEMATIC (DV6TED4)", fill='#00e5ff', font=FONT_HEAD)
    
    # Contoured ASCII Art Lines
    ascii_art = [
        ("  [ FRONT CROSSMEMBER / RADIATOR PACK ]", "#8b949e"),
        ("  ╔═════════════════════════════════════════════════════════════╗", "#30363d"),
        ("  ║ [03] INTERCOOLER: 0.04 bar dp   │ [11] DPF & CAT: 18.4g soot║", "#00e5ff"),
        ("  ║       │                                   │                 ║", "#8b949e"),
        ("  ║   ┌───▼───┐ [04] MAP: 1024mb          ┌───▼───┐             ║", "#c9d1d9"),
        ("  ║   │ INTAKE│ [16] CMP: SYNCHRONIZED    │ TURBO │ [02] 1.02bar║", "#c9d1d9"),
        ("  ║   └───┬───┘                           └───┬───┘ [09] 42% VNT║", "#ff9100"),
        ("  ║       │                                   │                 ║", "#8b949e"),
        ("  ║   ┌───▼───────────────────────────────────▼─────────────┐   ║", "#00e5ff"),
        ("  ║   │  DV6 1.6 HDi 16V CYLINDER HEAD (CAST ALLOY)        │   ║", "#ffffff"),
        ("  ║   │  [TIMING BELT]                  [FLYWHEEL / GEARBOX]│   ║", "#8b949e"),
        ("  ║   │                                                     │   ║", "#30363d"),
        ("  ║   │   CYL 4         CYL 3         CYL 2         CYL 1   │   ║", "#ffd600"),
        ("  ║   │    [08]          [08]          [08]          [08]   │   ║", "#ffd600"),
        ("  ║   │  INJECTOR      INJECTOR      INJECTOR      INJECTOR │   ║", "#ffd600"),
        ("  ║   │  +0.1 mg       +0.1 mg       -0.4 mg       +0.2 mg  │   ║", "#00e676"),
        ("  ║   │                                                     │   ║", "#30363d"),
        ("  ║   │  ===[06] FORGED COMMON RAIL: 298 bar (Tgt: 295)===  │   ║", "#ffd600"),
        ("  ║   │  [05] CP1H PUMP: 38.5°C      [07] SENSOR: 1.14V     │   ║", "#ffd600"),
        ("  ║   └───┬─────────────────────────────────┬───────────────┘   ║", "#00e5ff"),
        ("  ║       │                                 │                   ║", "#8b949e"),
        ("  ║   ┌───▼──────────────┐        ┌─────────▼─────────────────┐ ║", "#c9d1d9"),
        ("  ║   │[01] AIRBOX & MAF │        │[17] EGS6 TRANSMISSION     │ ║", "#00e5ff"),
        ("  ║   │     485 mg/str   │        │     Gear: [N] Neutral     │ ║", "#00e676"),
        ("  ║   │[15] CRANK (CKP)  │        │[18] HPU PUMP: 48.2 bar    │ ║", "#00e5ff"),
        ("  ║   │     850 RPM      │        │[19] CLUTCH: 14.8 mm       │ ║", "#00e676"),
        ("  ║   └──────────────────┘        │[14] COOLANT: 86.4 °C      │ ║", "#00e676"),
        ("  ║   ┌──────────────────┐        └───────────────────────────┘ ║", "#00e5ff"),
        ("  ║   │[12] DPF DIFF: 8mb│        ┌───────────────────────────┐ ║", "#ff5252"),
        ("  ║   │[10] EGT: 188 °C  │        │[20] 12V STARTER BATTERY   │ ║", "#ffd600"),
        ("  ║   │[13] EGR: 34%     │        │     14.28 V (Charging OK) │ ║", "#00e676"),
        ("  ║   └──────────────────┘        └───────────────────────────┘ ║", "#ffd600"),
        ("  ╚═════════════════════════════════════════════════════════════╝", "#30363d"),
        ("  [ CABIN BULKHEAD / SCUTTLE WATER TRAY ]", "#8b949e"),
    ]
    ay = 118
    for line_txt, line_col in ascii_art:
        draw.text((28, ay), line_txt, fill=line_col, font=FONT_TUI)
        ay += 17

    # Right Pane: Sensor Inspector Card & Catalog
    draw.rectangle([(618, 80), (1184, 110)], fill='#161b22')
    draw.text((630, 88), "SENSOR CATALOG & COMPONENT INSPECTOR", fill='#00e5ff', font=FONT_HEAD)
    
    # Active Sensor Card (Sensor 02: Turbo)
    draw.rounded_rectangle([(630, 120), (1172, 270)], radius=6, fill='#161b22', outline='#ff9100', width=1)
    draw.text((644, 130), "SELECTED: [02] Garrett GT1544V Variable Geometry Turbo", fill='#ffffff', font=FONT_HEAD)
    draw.text((644, 150), "• Subsystem: Forced Induction & Boost Control", fill='#c9d1d9', font=FONT_MONO_SM)
    draw.text((644, 168), "• OEM Part Number: 0375.J6 / Garrett 753420-5005S", fill='#c9d1d9', font=FONT_MONO_SM)
    draw.text((644, 186), "• Physical Location: Front-center of engine block behind heat shield", fill='#c9d1d9', font=FONT_MONO_SM)
    draw.text((644, 204), "• Connector: 3-Pin Black (Pin 1: 5V, Pin 2: Signal, Pin 3: GND)", fill='#c9d1d9', font=FONT_MONO_SM)
    draw.text((644, 222), "• Nominal Operating Spec: 0.98 - 1.05 bar (Idle) • Up to 2.35 bar (Boost)", fill='#c9d1d9', font=FONT_MONO_SM)
    draw.text((644, 242), "LIVE VALUE: 1.02 bar  [ STATUS: NOMINAL ]", fill='#00e676', font=FONT_MONO)

    # Sensor List Table (Compact)
    draw.rectangle([(630, 280), (1172, 304)], fill='#11161d')
    draw.text((638, 288), "ID  SENSOR NAME             LIVE READING     STATUS", fill='#8b949e', font=FONT_MONO_XS)
    
    s_rows = [
        ("[01]", "MAF & IAT Sensor", "485.0 mg/str", "NOMINAL", "#00e676"),
        ("[02]", "Garrett VNT Turbo", "1.02 bar", "NOMINAL", "#00e676"),
        ("[03]", "Charge Intercooler", "0.04 bar dp", "NOMINAL", "#00e676"),
        ("[04]", "MAP / IAT Sensor", "1024 mbar", "NOMINAL", "#00e676"),
        ("[05]", "CP1H High Press Pump", "38.5 °C", "NOMINAL", "#00e676"),
        ("[06]", "Common Rail Pressure", "298.0 bar", "NOMINAL", "#00e676"),
        ("[07]", "Rail Pressure Sensor", "295.0 bar tgt", "NOMINAL", "#00e676"),
        ("[08]", "Injectors 1-4 Balance", "Bal: +0.2 mg", "NOMINAL", "#00e676"),
        ("[09]", "VNT Electrovalve", "42.5 %", "NOMINAL", "#00e676"),
        ("[10]", "Pre-Cat EGT Sensor", "188.0 °C", "NOMINAL", "#00e676"),
        ("[11]", "DPF Soot Mass", "18.4 g", "NOMINAL", "#00e676"),
        ("[12]", "DPF Diff Pressure", "8.5 mbar", "NOMINAL", "#00e676"),
        ("[13]", "EGR Valve Position", "34.0 %", "NOMINAL", "#00e676"),
        ("[14]", "Coolant Temp (ECT)", "86.4 °C", "NOMINAL", "#00e676"),
        ("[17]", "EGS6 Gearbox State", "N (Neutral)", "NOMINAL", "#00e676"),
        ("[18]", "EGS6 Line Pressure", "48.2 bar", "NOMINAL", "#00e676"),
        ("[19]", "Clutch Slave Travel", "14.8 mm", "NOMINAL", "#00e676"),
        ("[20]", "12V Battery Voltage", "14.28 V", "NOMINAL", "#00e676"),
    ]
    sry = 308
    for sid, sname, sval, sstat, scol in s_rows:
        draw.text((638, sry), f"{sid:<4} {sname:<23} {sval:<16}", fill='#ffffff', font=FONT_MONO_XS)
        draw.text((1090, sry), sstat, fill=scol, font=FONT_MONO_XS)
        sry += 23

    # Bottom Nav
    draw.rectangle([(0, 760), (W, 800)], fill='#161b22')
    draw.text((16, 772), "[▲/▼] Select Sensor  [1-9] Switch Tab  [SPACE] Toggle Detail  [D] Export SVG  [Q] Exit", fill='#c9d1d9', font=FONT_MONO_SM)

    out_path = os.path.join(OUTPUT_DIR, "screenshot_02_tui_engine_tab.png")
    art_path = os.path.join(ARTIFACT_DIR, "screenshot_02_tui_engine_tab.png")
    img.save(out_path)
    img.save(art_path)
    print(f"Screenshot 02 saved successfully ({os.path.getsize(out_path)} bytes)")

# ==============================================================================
# 3. SCREENSHOT 03: TUI TAB 2 - LIVEDATA GAUGES & REAL-TIME SPARKLINES
# ==============================================================================

def generate_screenshot_03():
    print("Generating Screenshot 03: TUI Tab 2 LiveData Gauges & Sparklines...")
    W, H = 1200, 800
    img = Image.new('RGB', (W, H), '#080b0f')
    draw = ImageDraw.Draw(img)

    # Window Frame & Tab bar
    draw.rectangle([(0, 0), (W, 36)], fill='#161b22')
    draw.text((16, 10), "PSA-DIAG Terminal Workstation • Real-Time Telemetry & btop Dials", fill='#c9d1d9', font=FONT_HEAD)
    draw.rectangle([(0, 36), (W, 70)], fill='#0d1117')
    draw.line([(0, 70), (W, 70)], fill='#30363d', width=1)
    
    tabs = [
        ("1:DTC Scan", False),
        ("2:LiveData", True),
        ("3:Actuators", False),
        ("4:Tools", False),
        ("5:Telecode", False),
        ("6:Sniffer", False),
        ("7:LogPlayer", False),
        ("8:Engine", False),
        ("9:Audit", False)
    ]
    tx = 16
    for tname, active in tabs:
        tw = draw.textlength(tname, font=FONT_MONO) + 20
        if active:
            draw.rectangle([(tx, 42), (tx + tw, 70)], fill='#1c2128')
            draw.line([(tx, 42), (tx + tw, 42)], fill='#00e5ff', width=3)
            draw.text((tx + 10, 50), tname, fill='#00e5ff', font=FONT_MONO)
        else:
            draw.text((tx + 10, 50), tname, fill='#8b949e', font=FONT_MONO)
        tx += tw + 4

    # Top Telemetry Status Header (x=16, y=82, w=1168, h=40)
    draw.rounded_rectangle([(16, 82), (1184, 122)], radius=6, fill='#161b22', outline='#30363d', width=1)
    draw.text((28, 94), "● LIVE STREAMING", fill='#00e676', font=FONT_MONO_SM)
    draw.text((180, 94), "Interface: can0 (500 kbps)", fill='#c9d1d9', font=FONT_MONO_SM)
    draw.text((420, 94), "Frame Rate: 1,842 fps", fill='#00e5ff', font=FONT_MONO_SM)
    draw.text((640, 94), "Bus Load: 28.4%", fill='#ffd600', font=FONT_MONO_SM)
    draw.text((820, 94), "Drops: 0", fill='#00e676', font=FONT_MONO_SM)
    draw.text((950, 94), "[● REC] flight_log.csv", fill='#ff5252', font=FONT_MONO_SM)

    # 1. Primary Dials (Top Row: 2 Big Cards)
    # Tachometer (Left: w=576)
    draw.rounded_rectangle([(16, 134), (592, 330)], radius=8, fill='#0d1117', outline='#00e676', width=2)
    draw.text((32, 148), "ENGINE SPEED (TACHOMETER)", fill='#8b949e', font=FONT_MONO_SM)
    draw.text((32, 172), "850", fill='#00e676', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 38))
    draw.text((140, 192), "RPM (Idle)", fill='#c9d1d9', font=FONT_HEAD)
    
    # RPM Sparkline Trend (last 60s)
    draw.text((32, 235), "60-Second Trend:   ▂ ▂  ▂▂   ▂ ▂  ▂▂   ▂ ▂  ▂▂  ", fill='#00e676', font=FONT_MONO)
    draw.rectangle([(32, 270), (576, 290)], fill='#161b22')
    draw.rectangle([(32, 270), (32 + int(544 * (850 / 5000)), 290)], fill='#00e676')
    draw.text((32, 300), "0 RPM                  Redline: 4,500 RPM                  5,000 RPM", fill='#8b949e', font=FONT_MONO_XS)

    # Common Rail Pressure (Right: w=576)
    draw.rounded_rectangle([(608, 134), (1184, 330)], radius=8, fill='#0d1117', outline='#ffd600', width=2)
    draw.text((624, 148), "HIGH-PRESSURE COMMON RAIL (BOSCH CP1H)", fill='#8b949e', font=FONT_MONO_SM)
    draw.text((624, 172), "298.0", fill='#ffd600', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 38))
    draw.text((780, 192), "bar (Target: 295.0 bar • Delta: +3.0)", fill='#c9d1d9', font=FONT_HEAD)
    
    # Rail Sparkline Trend
    draw.text((624, 235), "60-Second Trend:  ▂▃▂  ▂▃▂  ▂▃▂  ▂▃▂  ▂▃▂  ▂▃▂  ", fill='#ffd600', font=FONT_MONO)
    draw.rectangle([(624, 270), (1168, 290)], fill='#161b22')
    draw.rectangle([(624, 270), (624 + int(544 * (298 / 1600)), 290)], fill='#ffd600')
    draw.text((624, 300), "0 bar                  Nominal Idle: 250-300 bar             1,600 bar", fill='#8b949e', font=FONT_MONO_XS)

    # 2. Secondary Dials (Middle Row: 3 Medium Cards)
    mid_cards = [
        ("TURBO BOOST PRESSURE", "1.02", "bar", "Target: 1.00 bar", "#ff9100", 1.02, 2.5, " ▂▂▂  ▂▂▂  ▂▂▂  "),
        ("COOLANT TEMPERATURE", "86.4", "°C", "Thermostat Nominal", "#00e676", 86.4, 120, "▄▅▅▅▅▅▅▅▅▅▅▅▅▅▅▅"),
        ("MASS AIR FLOW (MAF)", "485.0", "mg", "EGR Tracked: 34%", "#00e5ff", 485.0, 700, " ▃▃▂  ▃▃▂  ▃▃▂  ")
    ]
    mc_w = (1168 - 32) // 3
    for i, (mtitle, mval, munit, msub, mcol, val_f, max_f, spark) in enumerate(mid_cards):
        cx = 16 + i * (mc_w + 16)
        draw.rounded_rectangle([(cx, 346), (cx + mc_w, 530)], radius=6, fill='#0d1117', outline='#30363d', width=1)
        draw.text((cx + 16, 360), mtitle, fill='#8b949e', font=FONT_MONO_XS)
        draw.text((cx + 16, 380), mval, fill=mcol, font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 28))
        draw.text((cx + 110, 392), munit, fill='#c9d1d9', font=FONT_HEAD)
        draw.text((cx + 16, 422), msub, fill='#8b949e', font=FONT_MONO_XS)
        
        # Trend
        draw.text((cx + 16, 444), f"Trend: {spark}", fill=mcol, font=FONT_MONO_XS)
        # Bar
        pct = min(1.0, val_f / max_f)
        draw.rectangle([(cx + 16, 476), (cx + mc_w - 16, 490)], fill='#161b22')
        draw.rectangle([(cx + 16, 476), (cx + 16 + int((mc_w - 32) * pct), 490)], fill=mcol)

    # 3. Tertiary Auxiliary Telemetry Strip (Bottom Row: 4 Small Cards)
    aux_cards = [
        ("BATTERY CHARGE", "14.28 V", "Alternator Output OK", "#00e676"),
        ("FUEL TANK LEVEL", "72.4 %", "Remaining: ~43 Litres", "#00e5ff"),
        ("INTAKE AIR TEMP", "24.0 °C", "Ambient: 17.5 °C", "#00e5ff"),
        ("EGS6 CLUTCH WEAR", "14.8 mm", "Bite Point Stroke", "#ffd600"),
    ]
    ac_w = (1168 - 48) // 4
    for i, (atitle, aval, asub, acol) in enumerate(aux_cards):
        cx = 16 + i * (ac_w + 16)
        draw.rounded_rectangle([(cx, 546), (cx + ac_w, 646)], radius=6, fill='#11161d', outline='#30363d', width=1)
        draw.text((cx + 14, 558), atitle, fill='#8b949e', font=FONT_MONO_XS)
        draw.text((cx + 14, 578), aval, fill=acol, font=FONT_HEAD)
        draw.text((cx + 14, 608), asub, fill='#8b949e', font=FONT_MONO_XS)

    # Bottom Flight Recorder Banner
    draw.rounded_rectangle([(16, 662), (1184, 746)], radius=6, fill='#161b22', outline='#21262d', width=1)
    draw.text((32, 678), "FLIGHT DATA RECORDER ACTIVE", fill='#ffffff', font=FONT_HEAD)
    draw.text((32, 702), "Recording PID 0x010C, 0x010B, 0x0105, 0x0110 to /root/psa_diag/recordings/flight_log_20261031.csv", fill='#8b949e', font=FONT_MONO_SM)
    draw.text((920, 690), "[R] Stop Recording", fill='#ff5252', font=FONT_MONO_SM)

    # Bottom Nav
    draw.rectangle([(0, 760), (W, 800)], fill='#161b22')
    draw.text((16, 772), "[SPACE] Pause Stream  [R] Toggle Recording  [G] Graph Detail  [1-9] Switch Tab  [Q] Exit", fill='#c9d1d9', font=FONT_MONO_SM)

    out_path = os.path.join(OUTPUT_DIR, "screenshot_03_tui_livedata.png")
    art_path = os.path.join(ARTIFACT_DIR, "screenshot_03_tui_livedata.png")
    img.save(out_path)
    img.save(art_path)
    print(f"Screenshot 03 saved successfully ({os.path.getsize(out_path)} bytes)")

# ==============================================================================
# 4. SCREENSHOT 04: TUI TAB 1 - MULTI-MODULE DTC SCAN & FREEZE FRAME
# ==============================================================================

def generate_screenshot_04():
    print("Generating Screenshot 04: TUI Tab 1 Multi-Module DTC Scan & Freeze Frame...")
    W, H = 1200, 800
    img = Image.new('RGB', (W, H), '#080b0f')
    draw = ImageDraw.Draw(img)

    # Window & Tab bar
    draw.rectangle([(0, 0), (W, 36)], fill='#161b22')
    draw.text((16, 10), "PSA-DIAG Terminal Workstation • Multi-Module Extended DTC Scanner", fill='#c9d1d9', font=FONT_HEAD)
    draw.rectangle([(0, 36), (W, 70)], fill='#0d1117')
    draw.line([(0, 70), (W, 70)], fill='#30363d', width=1)
    
    tabs = [
        ("1:DTC Scan", True),
        ("2:LiveData", False),
        ("3:Actuators", False),
        ("4:Tools", False),
        ("5:Telecode", False),
        ("6:Sniffer", False),
        ("7:LogPlayer", False),
        ("8:Engine", False),
        ("9:Audit", False)
    ]
    tx = 16
    for tname, active in tabs:
        tw = draw.textlength(tname, font=FONT_MONO) + 20
        if active:
            draw.rectangle([(tx, 42), (tx + tw, 70)], fill='#1c2128')
            draw.line([(tx, 42), (tx + tw, 42)], fill='#00e5ff', width=3)
            draw.text((tx + 10, 50), tname, fill='#00e5ff', font=FONT_MONO)
        else:
            draw.text((tx + 10, 50), tname, fill='#8b949e', font=FONT_MONO)
        tx += tw + 4

    # Top Scan Summary Bar
    draw.rounded_rectangle([(16, 82), (1184, 126)], radius=6, fill='#161b22', outline='#30363d', width=1)
    draw.text((32, 92), "ECU TOPOLOGY SCAN COMPLETE", fill='#00e5ff', font=FONT_HEAD)
    draw.text((32, 108), "8 Modules Interrogated • 3 Stored Fault Codes Found • Reverse-Engineered PSA Cache: 40,752 Entries", fill='#8b949e', font=FONT_MONO_SM)
    draw.text((950, 96), "[C] Clear All DTCs", fill='#ff5252', font=FONT_MONO_SM)

    # DTC Fault Listing Table (x=16, y=138, w=1168, h=250)
    draw.rounded_rectangle([(16, 138), (1184, 388)], radius=6, fill='#0d1117', outline='#30363d', width=1)
    draw.rectangle([(16, 138), (1184, 168)], fill='#161b22')
    draw.text((28, 148), "CODE      ECU MODULE      FAULT CLASSIFICATION & DESCRIPTOR                              STATUS         MIL", fill='#8b949e', font=FONT_MONO_XS)

    dtcs = [
        ("P0299", "EDC16 (0x7E0)", "Pression de suralimentation trop basse (Turbo Underboost Detected)", "Défaut Permanent", "ON", "#ff5252", True),
        ("P1351", "EDC16 (0x7E0)", "Circuit relais préchauffage - Bougies d'allumage non alimentées", "Défaut Fugitif", "OFF", "#ffd600", False),
        ("P0562", "BSI (0x752)", "Tension d'alimentation réseau de bord basse (< 11.4V)", "Défaut Fugitif", "OFF", "#ffd600", False),
    ]
    dy = 176
    for code, ecu, desc, ftype, mil, col, selected in dtcs:
        if selected:
            draw.rectangle([(18, dy - 4), (1182, dy + 28)], fill='#1c2128', outline='#00e5ff', width=1)
        draw.text((28, dy), code, fill=col, font=FONT_HEAD)
        draw.text((120, dy + 2), ecu, fill='#c9d1d9', font=FONT_MONO_SM)
        draw.text((260, dy + 2), desc[:58], fill='#ffffff', font=FONT_TEXT_BOLD)
        draw.text((800, dy + 2), ftype, fill=col, font=FONT_MONO_SM)
        draw.text((970, dy + 2), mil, fill='#ff5252' if mil == "ON" else '#8b949e', font=FONT_MONO_SM)
        dy += 36

    # Bottom Area: Deep PSA Freeze-Frame Environmental Conditions (x=16, y=400, w=1168, h=340)
    draw.rounded_rectangle([(16, 400), (1184, 746)], radius=6, fill='#0d1117', outline='#00e5ff', width=2)
    draw.rectangle([(16, 400), (1184, 434)], fill='#161b22')
    draw.text((28, 412), "FREEZE-FRAME ENVIRONMENTAL CONDITIONS • P0299 (EDC16 ENGINE ECU)", fill='#00e5ff', font=FONT_HEAD)

    # Freeze-frame telemetry metrics
    ff_items = [
        ("Odometer at Fault:", "142,518 km", "Distance Since First Occurrence:", "14 km"),
        ("Vehicle Speed:", "74 km/h", "Engine Operating Time:", "3,412 Hours"),
        ("Engine Speed (RPM):", "2,150 RPM", "Calculated Engine Load:", "68.4 %"),
        ("Turbo Boost (Actual):", "1.18 bar", "Turbo Boost (Target):", "1.85 bar [DIFF -0.67]"),
        ("Common Rail Pressure:", "840 bar", "Rail Pressure Target:", "845 bar [OK]"),
        ("Coolant Temperature:", "84.0 °C", "Intake Air Temperature:", "22.0 °C"),
        ("Main Injection Quantity:", "24.8 mg/cp", "VNT Solenoid Duty Cycle:", "82.5 % [Max Spool]"),
        ("Battery Voltage:", "13.92 V", "Fault Frequency Counter:", "12 occurrences")
    ]
    fy = 446
    for lbl1, val1, lbl2, val2 in ff_items:
        draw.text((36, fy), lbl1, fill='#8b949e', font=FONT_MONO_SM)
        draw.text((260, fy), val1, fill='#ffffff', font=FONT_HEAD)
        draw.text((620, fy), lbl2, fill='#8b949e', font=FONT_MONO_SM)
        draw.text((910, fy), val2, fill='#ffd600' if 'DIFF' in val2 else '#00e676', font=FONT_HEAD)
        fy += 34

    # Bottom Nav
    draw.rectangle([(0, 760), (W, 800)], fill='#161b22')
    draw.text((16, 772), "[▲/▼] Select Fault Code  [F] View Raw Hex Dump  [C] Clear DTCs  [1-9] Switch Tab  [Q] Exit", fill='#c9d1d9', font=FONT_MONO_SM)

    out_path = os.path.join(OUTPUT_DIR, "screenshot_04_tui_dtc_scan.png")
    art_path = os.path.join(ARTIFACT_DIR, "screenshot_04_tui_dtc_scan.png")
    img.save(out_path)
    img.save(art_path)
    print(f"Screenshot 04 saved successfully ({os.path.getsize(out_path)} bytes)")

# ==============================================================================
# 5. SCREENSHOT 05: CONNECTION WIZARD & OBD PHYSICAL PINOUT DIAGNOSTICS
# ==============================================================================

def generate_screenshot_05():
    print("Generating Screenshot 05: Connection Wizard & Hardware Detection...")
    W, H = 1200, 800
    img = Image.new('RGB', (W, H), '#080b0f')
    draw = ImageDraw.Draw(img)

    # Window
    draw.rectangle([(0, 0), (W, 36)], fill='#161b22')
    draw.text((16, 10), "PSA-DIAG • Hardware Interface Link & Physical Bus Diagnostic Wizard", fill='#c9d1d9', font=FONT_HEAD)

    # Main Wizard Container (x=160, y=80, w=880, h=650)
    wx, wy, ww, wh = 160, 80, 880, 650
    draw.rounded_rectangle([(wx, wy), (wx + ww, wy + wh)], radius=8, fill='#0d1117', outline='#00e5ff', width=2)
    
    # Wizard Title
    draw.rectangle([(wx, wy), (wx + ww, wy + 50)], fill='#161b22')
    draw.text((wx + 24, wy + 16), "AUTOMOTIVE HARDWARE INTERFACE DETECTION", fill='#00e5ff', font=FONT_HEAD)

    # 1. Adapter Details Box
    draw.rounded_rectangle([(wx + 24, wy + 68), (wx + ww - 24, wy + 180)], radius=6, fill='#161b22', outline='#30363d', width=1)
    draw.text((wx + 40, wy + 82), "DEVICE LINK STATUS: CONNECTED & ONLINE", fill='#00e676', font=FONT_HEAD)
    
    dev_specs = [
        ("Hardware Port:", "/dev/ttyUSB0 (FTDI FT232R USB-Serial Bridge)"),
        ("Adapter Model:", "OBDLink SX USB (STN1170 Chipset • Firmware v4.2.1)"),
        ("Baud Rate:", "Auto-Negotiated: 115,200 bps (Buffer: 2,048 Bytes)"),
        ("Bus Protocol:", "ISO 15765-4 CAN (11-bit ID • 500 kbps Baud)")
    ]
    sy = wy + 104
    for dlabel, dval in dev_specs:
        draw.text((wx + 40, sy), dlabel, fill='#8b949e', font=FONT_MONO_SM)
        draw.text((wx + 180, sy), dval, fill='#ffffff', font=FONT_MONO_SM)
        sy += 18

    # 2. OBD-II 16-Pin Physical Bus Layer Health
    draw.rounded_rectangle([(wx + 24, wy + 196), (wx + ww - 24, wy + 370)], radius=6, fill='#11161d', outline='#30363d', width=1)
    draw.text((wx + 40, wy + 210), "OBD-II 16-PIN PHYSICAL ELECTRICAL HEALTH", fill='#00e5ff', font=FONT_HEAD)

    pins = [
        ("PIN 16 (+12V Unswitched Battery Power):", "12.45 V", "PASS (Nominal 12.0 - 12.8V)", "#00e676"),
        ("PIN 04/05 (Chassis & Signal Ground):", "< 0.04 Ω", "PASS (Good Ground Loop)", "#00e676"),
        ("PIN 06/14 (CAN-H / CAN-L Termination):", "60.2 Ω", "PASS (Dual 120Ω in parallel)", "#00e676"),
        ("PIN 07 (K-Line Comfort Bus):", "11.80 V", "READY (ISO 9141-2 / KWP2000)", "#00e676"),
        ("PIN 06 (CAN-H Recessive / Dominant):", "2.48V / 3.48V", "PASS (Differential Spacing 2.0V)", "#00e676"),
    ]
    py = wy + 236
    for plbl, pval, pstat, pcol in pins:
        draw.text((wx + 40, py), plbl, fill='#c9d1d9', font=FONT_MONO_SM)
        draw.text((wx + 460, py), pval, fill='#ffffff', font=FONT_HEAD)
        draw.text((wx + 580, py), pstat, fill=pcol, font=FONT_MONO_SM)
        py += 24

    # 3. Vehicle ECU Broadcast Detection
    draw.rounded_rectangle([(wx + 24, wy + 386), (wx + ww - 24, wy + 560)], radius=6, fill='#161b22', outline='#30363d', width=1)
    draw.text((wx + 40, wy + 400), "INITIAL VEHICLE ECU HANDSHAKE & LATENCY", fill='#00e5ff', font=FONT_HEAD)

    ecus = [
        ("BSI 2004 Body Computer", "0x752 (Rx: 0x75A)", "14 ms", "ONLINE", "#00e676"),
        ("Bosch EDC16C34 Engine ECU", "0x7E0 (Rx: 0x7E8)", "18 ms", "ONLINE", "#00e676"),
        ("Magneti Marelli EGS6 Gearbox", "0x7E2 (Rx: 0x7EA)", "16 ms", "ONLINE", "#00e676"),
        ("Bosch ESP 8.1 Stability/ABS", "0x760 (Rx: 0x768)", "19 ms", "ONLINE", "#00e676"),
        ("CAAR Pneumatic Air Suspension", "0x770 (Rx: 0x778)", "22 ms", "ONLINE", "#00e676"),
    ]
    ey = wy + 426
    for ename, canid, lat, estatus, ecol in ecus:
        draw.text((wx + 40, ey), ename, fill='#ffffff', font=FONT_TEXT_BOLD)
        draw.text((wx + 340, ey), canid, fill='#8b949e', font=FONT_MONO_SM)
        draw.text((wx + 560, ey), lat, fill='#c9d1d9', font=FONT_MONO_SM)
        draw.text((wx + 680, ey), estatus, fill=ecol, font=FONT_MONO_SM)
        ey += 24

    # Action Button
    draw.rounded_rectangle([(wx + 240, wy + 580), (wx + 640, wy + 626)], radius=6, fill='#00e5ff')
    draw.text((wx + 320, wy + 594), "LAUNCH WORKSTATION [ENTER]", fill='#080b0f', font=FONT_HEAD)

    out_path = os.path.join(OUTPUT_DIR, "screenshot_05_connection_wizard.png")
    art_path = os.path.join(ARTIFACT_DIR, "screenshot_05_connection_wizard.png")
    img.save(out_path)
    img.save(art_path)
    print(f"Screenshot 05 saved successfully ({os.path.getsize(out_path)} bytes)")

# ==============================================================================
# 6. SCREENSHOT 06: REALISTIC 82/100 PRE-PURCHASE INSPECTION SCORECARD
# ==============================================================================

def generate_screenshot_06():
    print("Generating Screenshot 06: Realistic Pre-Purchase Inspection (PPI) Scorecard...")
    W, H = 1200, 800
    img = Image.new('RGB', (W, H), '#080b0f')
    draw = ImageDraw.Draw(img)

    # Window
    draw.rectangle([(0, 0), (W, 36)], fill='#161b22')
    draw.text((16, 10), "PSA-DIAG • Pre-Purchase Vehicle Reliability & Health Audit Report", fill='#c9d1d9', font=FONT_HEAD)

    # Report Container (x=100, y=60, w=1000, h=710)
    cx, cy, cw, ch = 100, 60, 1000, 710
    draw.rounded_rectangle([(cx, cy), (cx + cw, cy + ch)], radius=8, fill='#0d1117', outline='#30363d', width=1)
    
    # Header Banner
    draw.rectangle([(cx, cy), (cx + cw, cy + 60)], fill='#161b22')
    draw.text((cx + 24, cy + 14), "VEHICLE HEALTH AUDIT & PRE-PURCHASE INSPECTION", fill='#00e5ff', font=FONT_TITLE)
    draw.text((cx + 24, cy + 38), "2010 Citroën Grand C4 Picasso Mk1 (B58) • 1.6 HDi DV6TED4 • 142,518 km", fill='#8b949e', font=FONT_MONO_SM)

    # Big Score Card Box (x=cx+24, y=cy+74, w=cw-48, h=86)
    draw.rounded_rectangle([(cx + 24, cy + 74), (cx + cw - 24, cy + 160)], radius=6, fill='#11161d', outline='#ffd600', width=2)
    draw.text((cx + 44, cy + 86), "OVERALL RELIABILITY SCORE:", fill='#8b949e', font=FONT_MONO_SM)
    draw.text((cx + 44, cy + 104), "82 / 100", fill='#ffd600', font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 38))
    draw.text((cx + 240, cy + 116), "GRADE: B+ (GOOD ROADWORTHY CONDITION • MINOR ADVISORIES)", fill='#ffffff', font=FONT_HEAD)

    # 10-Point Audit Inspection Table
    draw.rectangle([(cx + 24, cy + 174), (cx + cw - 24, cy + 200)], fill='#161b22')
    draw.text((cx + 36, cy + 182), "#  SUBSYSTEM INSPECTION ITEM       SCORE   STATUS      WORKSHOP AUDIT FINDING & RECOMMENDATION", fill='#8b949e', font=FONT_MONO_XS)

    audit_items = [
        ("1", "Common Rail Fuel Injection", "10/10", "PASS", "Rail pressure strictly tracks target (298 bar idle / ±3 bar)", "#00e676"),
        ("2", "Turbocharger & Boost Control", "9/10", "PASS", "Spool latency 0.32s; minor vane soot, actuator duty cycle 42%", "#00e676"),
        ("3", "DPF Filter & Eolys Additive", "7/10", "ADVISORY", "Additive pouch volume at 420 ml; refill recommended within 5k km", "#ffd600"),
        ("4", "EGS6 Automated Transmission", "8/10", "PASS", "Clutch travel 14.8mm (nominal wear); hydraulic accumulator 48 bar", "#00e676"),
        ("5", "Rear Pneumatic Air Suspension", "7/10", "ADVISORY", "Compressor run time 14s; slight height drift; check rubber bellows", "#ffd600"),
        ("6", "Injector Seal Integrity (Blow-by)", "8/10", "ADVISORY", "Cyl 2 injector copper seal shows early carbon misting; retorque", "#ffd600"),
        ("7", "Braking & Electric Handbrake (FSE)", "10/10", "PASS", "Braking balance nominal; FSE motor release time 0.8s", "#00e676"),
        ("8", "Electrical, Battery & BSM Module", "9/10", "PASS", "Alternator charging at 14.28V; battery resting 12.45V", "#00e676"),
        ("9", "Engine Cooling & Thermostat", "10/10", "PASS", "Coolant 86.4 °C; thermostat opening confirmed at 83 °C", "#00e676"),
        ("10", "Odometer Tampering Verification", "10/10", "PASS", "Odometer verified across BSI, EDC16, and EGS6 (142,518 km)", "#00e676"),
    ]
    ay = cy + 208
    for num, item, sc, st, note, col in audit_items:
        draw.text((cx + 36, ay), f"{num:<2} {item:<30}", fill='#ffffff', font=FONT_TEXT_BOLD)
        draw.text((cx + 320, ay), sc, fill=col, font=FONT_MONO_SM)
        draw.text((cx + 390, ay), st, fill=col, font=FONT_MONO_SM)
        draw.text((cx + 480, ay), note[:52], fill='#8b949e', font=FONT_MONO_XS)
        ay += 42

    # Bottom Actions & Export
    draw.rounded_rectangle([(cx + 24, cy + ch - 64), (cx + cw - 24, cy + ch - 16)], radius=6, fill='#161b22', outline='#30363d', width=1)
    draw.text((cx + 44, cy + ch - 48), "HTML Inspection Report exported to: /root/psa_diag/c4_picasso_ppi_report.html", fill='#00e5ff', font=FONT_MONO_SM)
    draw.text((cx + cw - 220, cy + ch - 48), "[P] Print / Export PDF", fill='#ffffff', font=FONT_HEAD)

    out_path = os.path.join(OUTPUT_DIR, "screenshot_06_health_scorecard.png")
    art_path = os.path.join(ARTIFACT_DIR, "screenshot_06_health_scorecard.png")
    img.save(out_path)
    img.save(art_path)
    print(f"Screenshot 06 saved successfully ({os.path.getsize(out_path)} bytes)")

if __name__ == '__main__':
    generate_screenshot_01()
    generate_screenshot_02()
    generate_screenshot_03()
    generate_screenshot_04()
    generate_screenshot_05()
    generate_screenshot_06()
    print("All 6 screenshots successfully regenerated with high fidelity!")
