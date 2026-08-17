import time
import json
import threading
from queue import Queue
from collections import deque
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console
from rich.text import Text
from rich.align import Align

from multi_device_engine import IoMTDevice
from pqc_nodes import WearableNode, EdgeNode
from network_channel import SimulatedNetwork

# Global event log
event_log = deque(maxlen=15)
# Store latest stats for animation/metrics
device_stats = {}

def log_event(msg, style="white"):
    timestamp = time.strftime("%H:%M:%S")
    event_log.append(f"[[cyan]{timestamp}[/cyan]] [{style}]{msg}[/{style}]")

def data_generator_worker(dev: IoMTDevice, q: Queue, hz: int):
    sleep_time = 1.0 / hz
    while True:
        raw_payload = dev.get_next_tick()
        q.put((time.time(), raw_payload))
        time.sleep(sleep_time)

def pqc_network_worker(dev_id: str, q: Queue, w_node: WearableNode, edge: EdgeNode, network: SimulatedNetwork):
    while True:
        if not q.empty():
            gen_time, raw_payload = q.get()
            payload_dict = json.loads(raw_payload.decode('utf-8'))
            
            cipher, enc_data, nonce, lat_w = w_node.encapsulate_and_encrypt(
                edge.public_key, raw_payload
            )
            
            buffer_delay_ms = (time.time() - gen_time) * 1000.0
            packet = network.transmit(cipher, enc_data, nonce, lat_w)
            
            status_color = "green"
            msg = f"Sent {dev_id} Seq {payload_dict['seq_num']}"
            
            if not packet:
                status_color = "dim red"
                msg = f"Dropped {dev_id} Seq {payload_dict['seq_num']}"
                log_event(msg, status_color)
            else:
                decrypted_data, lat_e = edge.receive_and_decrypt(
                    packet["ciphertext"], packet["encrypted_payload"], packet["nonce"]
                )
                
                total_e2e_latency = buffer_delay_ms + packet['network_latency'] + lat_e
                
                if decrypted_data == b"ERROR":
                    status_color = "bold red"
                    log_event(f"TAMPER DETECTED: {dev_id} Seq {payload_dict['seq_num']}", status_color)
                elif decrypted_data == raw_payload:
                    log_event(f"Verified {dev_id} (Lat: {total_e2e_latency:.0f}ms)", status_color)
                else:
                    status_color = "red"
            
            device_stats[dev_id] = {
                "qsize": q.qsize(),
                "bloat": buffer_delay_ms,
                "status": status_color,
                "active": True
            }
        else:
            if dev_id in device_stats:
                device_stats[dev_id]["active"] = False
            time.sleep(0.01)

def build_network_map(frame: int) -> Panel:
    # Animation frames for transmission lines
    patterns = [
        "· - · - · - · - · -",
        "- · - · - · - · - ·",
        "· - · - · - · - · -",
        "- · - · - · - · - ·"
    ]
    p = patterns[frame % len(patterns)]
    
    map_text = Text()
    map_text.append("\n\n")
    
    # DEV 1
    c1 = device_stats.get("DEV-1", {}).get("status", "white")
    map_text.append("       (●) DEV-1 ".ljust(20), style="cyan")
    map_text.append(f"{p} ↘\n", style=c1)
    
    # EDGE
    map_text.append("                             (●) EDGE NODE\n", style="bold blue")
    
    # DEV 2
    c2 = device_stats.get("DEV-2", {}).get("status", "white")
    map_text.append("       (●) DEV-2 ".ljust(20), style="cyan")
    map_text.append(f"{p} ↗\n", style=c2)
    
    map_text.append("\n")
    
    # DEV 3
    c3 = device_stats.get("DEV-3", {}).get("status", "white")
    map_text.append("       (●) DEV-3 ".ljust(20), style="cyan")
    map_text.append(f"{p} ↗\n", style=c3)
    
    return Panel(Align.center(map_text, vertical="middle"), title="[bold cyan]Network Topology[/bold cyan]", border_style="cyan")

def build_metrics_table() -> Panel:
    table = Table(expand=True)
    table.add_column("Device", style="cyan")
    table.add_column("Q-Size", justify="right", style="magenta")
    table.add_column("Bloat (ms)", justify="right", style="yellow")
    table.add_column("State", justify="center")
    
    for dev_id in ["DEV-1", "DEV-2", "DEV-3"]:
        stats = device_stats.get(dev_id, {})
        qsize = str(stats.get("qsize", 0))
        bloat = f"{stats.get('bloat', 0):.0f}"
        color = stats.get("status", "white")
        active = "TRANSMITTING" if stats.get("active") else "IDLE"
        table.add_row(dev_id, qsize, bloat, f"[{color}]{active}[/{color}]")
        
    return Panel(table, title="[bold magenta]Real-time Metrics[/bold magenta]", border_style="magenta")

def build_logs() -> Panel:
    log_text = Text.from_markup("\n".join(event_log))
    return Panel(log_text, title="[bold yellow]Event Logs[/bold yellow]", border_style="yellow")

def main():
    console = Console()
    
    devices = [
        IoMTDevice("DEV-1", "100", "mitdb", "Wearable ECG"),
        IoMTDevice("DEV-2", "a01", "apnea-ecg", "Apnea Monitor"),
        IoMTDevice("DEV-3", "slp01a", "slpdb", "Sleep Tracker")
    ]
    
    wearables = {dev.device_id: WearableNode() for dev in devices}
    edge = EdgeNode()
    network = SimulatedNetwork(drop_rate=0.05, tamper_rate=0.05, min_jitter_ms=5, max_jitter_ms=20)
    
    queues = {dev.device_id: Queue() for dev in devices}
    
    # 50 Hz (Tachycardia) for DEV-1, 20 Hz for others
    threading.Thread(target=data_generator_worker, args=(devices[0], queues["DEV-1"], 50), daemon=True).start()
    threading.Thread(target=data_generator_worker, args=(devices[1], queues["DEV-2"], 20), daemon=True).start()
    threading.Thread(target=data_generator_worker, args=(devices[2], queues["DEV-3"], 20), daemon=True).start()
    
    for dev in devices:
        threading.Thread(target=pqc_network_worker, 
                         args=(dev.device_id, queues[dev.device_id], wearables[dev.device_id], edge, network), 
                         daemon=True).start()

    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main")
    )
    layout["main"].split_row(
        Layout(name="left_pane", ratio=2),
        Layout(name="right_pane", ratio=1)
    )
    layout["left_pane"].split_column(
        Layout(name="map", ratio=3),
        Layout(name="metrics", ratio=2)
    )
    layout["header"].update(Panel("[bold cyan]HYBRID PQC-QKD IoMT: PHASE 1 VISUAL DASHBOARD[/bold cyan]"))

    frame = 0
    with Live(layout, refresh_per_second=8, screen=True) as live:
        try:
            while True:
                layout["map"].update(build_network_map(frame))
                layout["metrics"].update(build_metrics_table())
                layout["right_pane"].update(build_logs())
                
                frame += 1
                time.sleep(0.125)
                
        except KeyboardInterrupt:
            pass
            
    console.print("[bold green]Visual TUI Terminated.[/bold green]")

if __name__ == "__main__":
    main()
