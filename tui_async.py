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

from multi_device_engine import IoMTDevice
from pqc_nodes import WearableNode, EdgeNode
from network_channel import SimulatedNetwork

def generate_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1)
    )
    layout["main"].split_row(
        Layout(name="dev1"),
        Layout(name="dev2"),
        Layout(name="dev3"),
        Layout(name="edge")
    )
    return layout

def data_generator_worker(dev: IoMTDevice, q: Queue, hz: int):
    """Continuously generates data at a specific frequency (Hz) and queues it."""
    sleep_time = 1.0 / hz
    while True:
        raw_payload = dev.get_next_tick()
        # Attach the exact generation time to measure total buffer bloat later
        q.put((time.time(), raw_payload))
        time.sleep(sleep_time)

def pqc_network_worker(dev_id: str, q: Queue, w_node: WearableNode, edge: EdgeNode, network: SimulatedNetwork, history: deque, edge_history: deque):
    """Pulls data from queue, runs expensive PQC crypto, and transmits."""
    while True:
        if not q.empty():
            gen_time, raw_payload = q.get()
            payload_dict = json.loads(raw_payload.decode('utf-8'))
            
            # --- B. Wearable PQC Processing (THIS BLOCKS AND SIMULATES HARDWARE DELAY) ---
            cipher, enc_data, nonce, lat_w = w_node.encapsulate_and_encrypt(
                edge.public_key, raw_payload
            )
            
            # Buffer Bloat = Time waiting in queue + time taken to encrypt
            buffer_delay_ms = (time.time() - gen_time) * 1000.0
            
            # --- C. Network Transmission ---
            packet = network.transmit(cipher, enc_data, nonce, lat_w)
            
            history.appendleft({
                "seq": payload_dict["seq_num"],
                "data": str(payload_dict["data"]),
                "buffer": f"{q.qsize()} items",
                "bloat": f"{buffer_delay_ms:.0f} ms",
                "status": "[green]SENT[/green]" if packet else "[red]DROP[/red]"
            })
            
            # --- D. Edge Processing ---
            if packet:
                decrypted_data, lat_e = edge.receive_and_decrypt(
                    packet["ciphertext"], 
                    packet["encrypted_payload"], 
                    packet["nonce"]
                )
                
                if decrypted_data == b"ERROR":
                    status = "[bold red]TAMPERED[/bold red]"
                elif decrypted_data == raw_payload:
                    status = "[green]VERIFIED[/green]"
                else:
                    status = "[red]UNKNOWN[/red]"
                
                total_e2e_latency = buffer_delay_ms + packet['network_latency'] + lat_e
                
                edge_history.appendleft({
                    "dev": dev_id,
                    "seq": payload_dict["seq_num"],
                    "e2e": f"{total_e2e_latency:.0f} ms",
                    "status": status
                })
        else:
            time.sleep(0.01)

def main():
    console = Console()
    console.print("[bold yellow]Initializing Asynchronous Buffer Bloat Simulation...[/bold yellow]")
    
    devices = [
        IoMTDevice("DEV-1", "100", "mitdb", "Wearable ECG Patch"),
        IoMTDevice("DEV-2", "a01", "apnea-ecg", "Apnea Monitor"),
        IoMTDevice("DEV-3", "slp01a", "slpdb", "Sleep EEG Tracker")
    ]
    
    wearables = {dev.device_id: WearableNode(kem_algorithm="ML-KEM-512") for dev in devices}
    edge = EdgeNode(kem_algorithm="ML-KEM-512")
    network = SimulatedNetwork(drop_rate=0.05, tamper_rate=0.05, min_jitter_ms=5, max_jitter_ms=20)
    
    # Queues for each device
    queues = {dev.device_id: Queue() for dev in devices}
    
    # Histories
    history = {dev.device_id: deque(maxlen=8) for dev in devices}
    edge_history = deque(maxlen=10)
    
    # Start Data Generator Threads (Simulating Heartbeats)
    # Let's force DEV-1 to have Tachycardia (50 Hz), others normal (20 Hz)
    # The ESP32 maxes out at ~40 Hz encryption, so DEV-1 will bloat, others won't!
    threading.Thread(target=data_generator_worker, args=(devices[0], queues["DEV-1"], 50), daemon=True).start()
    threading.Thread(target=data_generator_worker, args=(devices[1], queues["DEV-2"], 20), daemon=True).start()
    threading.Thread(target=data_generator_worker, args=(devices[2], queues["DEV-3"], 20), daemon=True).start()
    
    # Start Network/Crypto Workers
    for dev in devices:
        threading.Thread(target=pqc_network_worker, 
                         args=(dev.device_id, queues[dev.device_id], wearables[dev.device_id], edge, network, history[dev.device_id], edge_history), 
                         daemon=True).start()

    layout = generate_layout()
    layout["header"].update(Panel("[bold cyan]PHASE 1: ASYNCHRONOUS BUFFER BLOAT (DEV-1 Tachycardia 50Hz vs ESP32 Crypto Limit)[/bold cyan]"))

    with Live(layout, refresh_per_second=4, screen=True) as live:
        try:
            while True:
                for i, dev in enumerate(devices):
                    t = Table(title=f"{dev.device_type} ({dev.device_id})", expand=True)
                    t.add_column("Seq")
                    t.add_column("Q-Size", style="magenta")
                    t.add_column("Bloat", style="yellow")
                    t.add_column("Status")
                    for row in history[dev.device_id]:
                        t.add_row(str(row["seq"]), row["buffer"], row["bloat"], row["status"])
                    layout[f"dev{i+1}"].update(Panel(t, border_style="cyan"))
                
                e_table = Table(title="Edge Gateway (NUC)", expand=True)
                e_table.add_column("Dev", style="cyan")
                e_table.add_column("Seq")
                e_table.add_column("End-to-End Latency", style="yellow")
                e_table.add_column("Status")
                
                for row in edge_history:
                    e_table.add_row(row["dev"], str(row["seq"]), row["e2e"], row["status"])
                layout["edge"].update(Panel(e_table, border_style="blue"))
                
                time.sleep(0.25)
                
        except KeyboardInterrupt:
            pass
            
    console.print("[bold green]Async Buffer Bloat Simulation Terminated.[/bold green]")

if __name__ == "__main__":
    main()
