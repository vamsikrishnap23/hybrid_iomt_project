import time
import json
import threading
import socket
import sys
import select
import tty
import termios
from queue import Queue
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console
from rich.text import Text

from multi_device_engine import IoMTDevice
from pqc_nodes import WearableNode, EdgeNode
from physics_engine import PhysicsEngine

# --- GLOBAL STATE ---
event_log = deque(maxlen=20)
device_stats = {
    "DEV-1": {"status": "ONLINE", "rate": 0, "pkts": 0, "color": "green", "bloat": 0, "rssi": -30},
    "DEV-2": {"status": "ONLINE", "rate": 0, "pkts": 0, "color": "green", "bloat": 0, "rssi": -30},
    "DEV-3": {"status": "ONLINE", "rate": 0, "pkts": 0, "color": "green", "bloat": 0, "rssi": -30}
}
edge_stats = {"processed": 0, "dropped": 0, "errors": 0}
start_time = time.time()
current_scenario = "1 - NORMAL OPERATION"

# Web Dashboard Data
web_data = {
    "DEV-1": {"last_payload": {}, "status": "Waiting"},
    "DEV-2": {"last_payload": {}, "status": "Waiting"},
    "DEV-3": {"last_payload": {}, "status": "Waiting"}
}

# --- WEB SERVER ---
class WebDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        response = json.dumps({
            "scenario": current_scenario,
            "edge_stats": edge_stats,
            "devices": web_data
        }, indent=2)
        self.wfile.write(response.encode('utf-8'))
        
    def log_message(self, format, *args):
        pass # Suppress HTTP logs to avoid corrupting TUI

def start_web_server():
    server = HTTPServer(('0.0.0.0', 8080), WebDashboardHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# --- HELPERS ---
def log_event(level, msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    color = "cyan" if level == "INFO" else "red" if level == "ERROR" else "yellow" if level == "WARN" else "magenta"
    event_log.append(f"[[bright_black]{timestamp}[/bright_black]] [[{color}]{level:5}[/{color}]] {msg}")

import os
import signal
import atexit

old_settings = None
def restore_terminal():
    if old_settings:
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        except Exception:
            pass

atexit.register(restore_terminal)

# --- SCENARIO CONTROL ---
def scenario_listener(physics: PhysicsEngine):
    global current_scenario, old_settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    
    while True:
        try:
            char_bytes = os.read(fd, 1)
            if not char_bytes:
                continue
            c = char_bytes.decode('utf-8', errors='ignore')
            
            if c == '1':
                current_scenario = "1 - NORMAL OPERATION"
                physics.device_positions["DEV-3"] = [15.0, 0.0]
                physics.tx_power = -30
                log_event("INFO", "Scenario 1: Normal Operation (Stable)")
            elif c == '2':
                current_scenario = "2 - MAN-IN-THE-MIDDLE ATTACK"
                log_event("WARN", "Scenario 2: Active MitM Tampering Initiated")
            elif c == '3':
                current_scenario = "3 - PATIENT WANDERING (DISTANCE)"
                log_event("WARN", "Scenario 3: Patient DEV-3 wandering out of range")
            elif c == 'q' or c == 'Q':
                os.kill(os.getpid(), signal.SIGINT)
        except Exception:
            pass

def physics_worker(physics: PhysicsEngine):
    while True:
        if "3" in current_scenario:
            physics.move_device("DEV-3", 1.5, 0) # Move fast away
        time.sleep(1.0)

# --- WORKERS ---
def data_generator_worker(dev: IoMTDevice, q: Queue, hz: int):
    sleep_time = 1.0 / hz
    while True:
        raw_payload = dev.get_next_tick()
        q.put((time.time(), raw_payload))
        time.sleep(sleep_time)

def pqc_network_worker(dev_id: str, q: Queue, w_node: WearableNode, edge_pub, physics: PhysicsEngine):
    while True:
        if not q.empty():
            gen_time, raw_payload = q.get()
            
            # Scenario overrides
            is_mitm = ("2" in current_scenario and dev_id == "DEV-2")
            
            success, distance, rssi, lat_w = w_node.encapsulate_and_transmit(edge_pub, raw_payload, physics, force_tamper=is_mitm)
            
            device_stats[dev_id]["pkts"] += 1
            device_stats[dev_id]["bloat"] = (time.time() - gen_time) * 1000.0
            device_stats[dev_id]["rssi"] = rssi
            
            if not success:
                edge_stats["dropped"] += 1
                device_stats[dev_id]["color"] = "yellow"
                web_data[dev_id]["status"] = "DROPPED (Signal Lost)"
                
            device_stats[dev_id]["rate"] = min(99.9, device_stats[dev_id]["pkts"] / max(1, (time.time() - start_time)))
        else:
            time.sleep(0.01)

def edge_server_worker(edge: EdgeNode):
    while True:
        packet, addr = edge.receive_packet()
        if packet:
            dev_id = packet["dev_id"]
            decrypted_data, lat_e = edge.process_packet(packet)
            
            if decrypted_data == b"ERROR":
                edge_stats["errors"] += 1
                device_stats[dev_id]["color"] = "red"
                if packet.get("was_tampered", False):
                    log_event("ERROR", f"ACTIVE ATTACK: MitM Tampering caught on {dev_id}")
                    web_data[dev_id]["status"] = "MALICIOUS TAMPER DETECTED"
                else:
                    log_event("WARN", f"Physics: Bit corruption caught on {dev_id} (RSSI: {packet['rssi']:.1f})")
                    web_data[dev_id]["status"] = "NATURAL CORRUPTION REJECTED"
            else:
                edge_stats["processed"] += 1
                device_stats[dev_id]["color"] = "green"
                
                # Update web JSON feed with successful decryption
                payload_json = json.loads(decrypted_data.decode('utf-8'))
                web_data[dev_id]["last_payload"] = payload_json
                web_data[dev_id]["last_encrypted"] = packet['encrypted_payload'].hex()
                web_data[dev_id]["status"] = "SECURE"
                
                if edge_stats["processed"] % 15 == 0:
                    log_event("INFO", f"Verified packet from {dev_id} ({len(packet['encrypted_payload'])}b)")

# --- UI RENDERING ---
def build_header() -> Panel:
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_text = Text()
    header_text.append(f" IoT Edge Network Monitor   |   Scenario: {current_scenario}", style="bold cyan")
    header_text.append(f"{' '*20}Time: {t}    Status: RUNNING", style="green")
    return Panel(header_text, style="white")

def build_footer() -> Panel:
    total_pkts = sum(d["pkts"] for d in device_stats.values())
    rate = total_pkts / max(1, (time.time() - start_time))
    footer_text = Text()
    footer_text.append("[1] Normal  [2] MitM Attack  [3] Distance Loss", style="bold yellow")
    footer_text.append(f"{' '*20}Web API: http://127.0.0.1:8080", style="cyan")
    footer_text.append(f"{' '*10}Packets/s: {rate:.1f}   Errors: {edge_stats['errors']}   Dropped: {edge_stats['dropped']}", style="green")
    return Panel(footer_text, style="white")

def get_node_lines(name, d_id, color, rssi):
    return [
        f"+---------------+",
        f"| (([green]p[/green])) [green]{name}[/green]{' '*(8-len(name))}|",
        f"|  A            |",
        f"|   RSSI: {rssi:3.0f}   |",
        f"|   Status: [{color}]ON[/{color}] |",
        f"+---------------+"
    ]

def build_topology() -> Panel:
    s1 = device_stats["DEV-1"]
    s2 = device_stats["DEV-2"]
    s3 = device_stats["DEV-3"]
    
    n1 = get_node_lines('Node-01', '001', s1['color'], s1['rssi'])
    n2 = get_node_lines('Node-02', '002', s2['color'], s2['rssi'])
    n3 = get_node_lines('Node-03', '003', s3['color'], s3['rssi'])
    
    lines = [
        f"  {n1[0]}",
        f"  {n1[1]}",
        f"  {n1[2]}      Transmitting...",
        f"  {n1[3]}      {s1['rate']:>5.2f} pkts/s -----------------+",
        f"  {n1[4]}                                    |",
        f"  {n1[5]}                                    v",
        f"                                             +--------------------+           +----------------------+",
        f"  {n2[0]}                          | [cyan]=[/cyan] Edge-Node-01     |           | [magenta]*[/magenta] Datacenter-01      |",
        f"  {n2[1]}      Transmitting...       | Role: EDGE GATEWAY | ===[cyan]QKD[/cyan]==> | Role: QKD RECEIVER   |",
        f"  {n2[2]}      {s2['rate']:>5.2f} pkts/s ------> | Status: [green]ONLINE[/green]     | [cyan] (Fiber) [/cyan] | Status: [yellow]STANDBY[/yellow]      |",
        f"  {n2[3]}                          +--------------------+           +----------------------+",
        f"  {n2[4]}                                    ^",
        f"  {n2[5]}                                    |",
        f"                                                       |",
        f"  {n3[0]}                                    |",
        f"  {n3[1]}      Transmitting...               |",
        f"  {n3[2]}      {s3['rate']:>5.2f} pkts/s -----------------+",
        f"  {n3[3]}",
        f"  {n3[4]}",
        f"  {n3[5]}"
    ]
    
    top = "\n".join(lines)
    return Panel(Text.from_markup(top), title="[bold cyan]NETWORK TOPOLOGY[/bold cyan]", border_style="cyan")

def build_info() -> Panel:
    uptime = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
    total_rate = sum(d["rate"] for d in device_stats.values())
    cpu = "||||||    "
    mem = "||||||||  "
    
    def format_node(dev_id):
        p_dict = dict(web_data[dev_id].get("last_payload", {}))
        
        # Extract only the actual biological data (ECG, Apnea, etc)
        vital_data = p_dict.get("data", {})
        p = str(vital_data)
        e = web_data[dev_id].get("last_encrypted", "")
        
        if len(p) > 42: p = p[:39] + "..."
        if len(e) > 35: e = e[:32] + "..."
        
        return f"[green]{p}[/green]\n         [magenta]Wire Ciphertext: {e}[/magenta]"

    # Grab a live snippet of the actual clinical telemetry (ignoring static IDs)
    pl1 = format_node("DEV-1")
    pl2 = format_node("DEV-2")
    pl3 = format_node("DEV-3")
    
    info = f"""
Edge Node ID    : Edge-Node-01
Uptime          : {uptime}
CPU Usage       : [green]18%[/green] {cpu}
Memory Usage    : [green]42%[/green] {mem}
Incoming Rate   : {total_rate:.2f} pkts/s
Processed Pkts  : {edge_stats['processed']}
Dropped Pkts    : {edge_stats['dropped']}
Tampered Pkts   : {edge_stats['errors']}

[bold cyan]LIVE DECRYPTED & RAW TRANSFERS[/bold cyan]
Node-01: {pl1}
Node-02: {pl2}
Node-03: {pl3}
"""
    return Panel(Text.from_markup(info), title="[bold cyan]EDGE NODE INFO[/bold cyan]", border_style="cyan")

def build_logs() -> Panel:
    log_text = Text.from_markup("\n".join(event_log))
    return Panel(log_text, title="[bold cyan]LOGS[/bold cyan]", border_style="cyan")

def main():
    console = Console()
    
    # Start Web API
    start_web_server()
    log_event("INFO", "Web Dashboard API running at http://127.0.0.1:8080")
    
    physics = PhysicsEngine()
    devices = [
        IoMTDevice("DEV-1", "100", "mitdb", "Wearable ECG"),
        IoMTDevice("DEV-2", "a01", "apnea-ecg", "Apnea Monitor"),
        IoMTDevice("DEV-3", "slp01a", "slpdb", "Sleep Tracker")
    ]
    
    edge = EdgeNode("127.0.0.1", 5005)
    wearables = {dev.device_id: WearableNode(dev.device_id, "127.0.0.1", 5005) for dev in devices}
    queues = {dev.device_id: Queue() for dev in devices}
    
    # Start workers
    threading.Thread(target=scenario_listener, args=(physics,), daemon=True).start()
    threading.Thread(target=edge_server_worker, args=(edge,), daemon=True).start()
    threading.Thread(target=physics_worker, args=(physics,), daemon=True).start()
    
    threading.Thread(target=data_generator_worker, args=(devices[0], queues["DEV-1"], 40), daemon=True).start() # High frequency ECG
    threading.Thread(target=data_generator_worker, args=(devices[1], queues["DEV-2"], 20), daemon=True).start() # Medium frequency Apnea
    threading.Thread(target=data_generator_worker, args=(devices[2], queues["DEV-3"], 10), daemon=True).start() # Low frequency Sleep Tracker
    
    for dev in devices:
        threading.Thread(target=pqc_network_worker, 
                         args=(dev.device_id, queues[dev.device_id], wearables[dev.device_id], edge.public_key, physics), 
                         daemon=True).start()

    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="topology", ratio=2),
        Layout(name="right_pane", ratio=1)
    )
    layout["right_pane"].split_column(
        Layout(name="info", ratio=1),
        Layout(name="logs", ratio=1)
    )

    with Live(layout, refresh_per_second=4, screen=True) as live:
        try:
            while True:
                layout["header"].update(build_header())
                layout["topology"].update(build_topology())
                layout["info"].update(build_info())
                layout["logs"].update(build_logs())
                layout["footer"].update(build_footer())
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
