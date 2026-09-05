import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import time
import json
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box

from pqc_nodes import WearableNode, EdgeNode
from datacenter_node import DatacenterNode
from qkd_key_manager import QKDKeyPool
from physics_engine import PhysicsEngine
from multi_device_engine import IoMTDevice

class Dashboard:
    def __init__(self):
        # 1. Initialization & Threading
        self.qkd_pool = QKDKeyPool(max_pool_size=50)
        self.qkd_pool.start()
        
        self.physics = PhysicsEngine()
        
        self.edge_ip = "127.0.0.1"
        self.edge_port = 5020
        self.edge_node = EdgeNode(self.edge_ip, self.edge_port, kem_algorithm="ML-KEM-512", qkd_pool=self.qkd_pool)
        self.wearable_node = WearableNode("Dev-1", self.edge_ip, self.edge_port, kem_algorithm="ML-KEM-512")
        self.datacenter_node = DatacenterNode(qkd_pool=self.qkd_pool)
        
        self.pacemaker = IoMTDevice("Dev-1", "100", "mitdb", "Pacemaker")

        # 2. UI Layout (3-Pane Grid)
        self.layout = Layout()
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main")
        )
        self.layout["main"].split_row(
            Layout(name="tier1"),
            Layout(name="tier2"),
            Layout(name="tier3")
        )
        
        # State variables for UI tracking
        self.seq_num = 0
        self.ecg_mv = 0.0
        self.tier1_encap_ms = 0.0
        self.tier2_decap_ms = 0.0
        self.tier2_trans_ms = 0.0
        self.tier3_decrypt_ms = 0.0
        self.verify_status = "[blue]IDLE[/blue]"
        
    def generate_header(self) -> Panel:
        """Header Pane: Display project title and live QBER."""
        qber = getattr(self.qkd_pool, 'last_qber', 0.0)
        qber_str = f"{qber * 100:.2f}%"
        qber_style = "green" if qber <= 0.11 else "red bold"
        
        title_text = Text()
        title_text.append("Hybrid PQC-QKD Edge Computing Framework ", style="bold cyan")
        title_text.append("| ", style="white")
        title_text.append(f"Live QBER: ", style="bold white")
        title_text.append(qber_str, style=qber_style)
        
        return Panel(Align.center(title_text, vertical="middle"), style="bold blue", box=box.ROUNDED)

    def generate_tier1(self) -> Panel:
        """Pane 1 (Tier 1: Wearable)"""
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold white")
        table.add_row("Raw ECG (mV)", f"{self.ecg_mv:.3f}")
        table.add_row("Sequence #", str(self.seq_num))
        table.add_row("ML-KEM Encap", f"{self.tier1_encap_ms:.2f} ms")
        return Panel(table, title="[bold green]Tier 1: Wearable[/bold green]", border_style="green")

    def generate_tier2(self) -> Panel:
        """Pane 2 (Tier 2: Edge Gateway)"""
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold white")
        
        # Thread-safe read of queue size
        pool_size = self.qkd_pool.key_queue.qsize()
        
        table.add_row("ML-KEM Decap", f"{self.tier2_decap_ms:.2f} ms")
        table.add_row("QKD Keys Avail", f"{pool_size} / {self.qkd_pool.max_pool_size}")
        table.add_row("Re-encryption", f"{self.tier2_trans_ms:.2f} ms")
        return Panel(table, title="[bold yellow]Tier 2: Edge Gateway[/bold yellow]", border_style="yellow")

    def generate_tier3(self) -> Panel:
        """Pane 3 (Tier 3: Datacenter)"""
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold white")
        table.add_row("QKD Decrypt", f"{self.tier3_decrypt_ms:.2f} ms")
        table.add_row("Payload Status", self.verify_status)
        return Panel(table, title="[bold red]Tier 3: Datacenter[/bold red]", border_style="red")

    def update_ui(self):
        """Re-render the panels with the latest state."""
        self.layout["header"].update(self.generate_header())
        self.layout["tier1"].update(self.generate_tier1())
        self.layout["tier2"].update(self.generate_tier2())
        self.layout["tier3"].update(self.generate_tier3())

    def run_pipeline(self):
        """Main Loop: Streams data through the End-to-End Pipeline."""
        with Live(self.layout, refresh_per_second=10, screen=True) as live:
            # Let the QKD pool spool up initially
            time.sleep(2)
            
            while True:
                # 1. Fetch live data (PhysioNet ingestion)
                raw_payload = self.pacemaker.get_next_tick()
                payload_dict = json.loads(raw_payload.decode('utf-8'))
                
                self.seq_num = payload_dict["seq_num"]
                
                # Dynamically fetch the first available ECG reading
                if "MLII" in payload_dict["data"]:
                    self.ecg_mv = payload_dict["data"]["MLII"]
                else:
                    keys = list(payload_dict["data"].keys())
                    self.ecg_mv = payload_dict["data"][keys[0]] if keys else 0.0
                
                self.verify_status = "[yellow]TRANSMITTING...[/yellow]"
                self.update_ui()
                
                # 2. Tier 1: Wearable Encapsulate & Transmit
                success, dist, rssi, p_ms = self.wearable_node.encapsulate_and_transmit(
                    self.edge_node.public_key,
                    raw_payload,
                    self.physics
                )
                self.tier1_encap_ms = p_ms
                self.update_ui()
                
                if not success:
                    self.verify_status = "[bold red]DROPPED (Physics)[/bold red]"
                    self.update_ui()
                    time.sleep(0.5)
                    continue
                
                # 3. Tier 2: Receive & Decapsulate
                packet, _ = self.edge_node.receive_packet()
                if not packet:
                    self.verify_status = "[bold red]DROPPED (Network)[/bold red]"
                    self.update_ui()
                    time.sleep(0.5)
                    continue
                    
                decrypted_data, edge_ms = self.edge_node.process_packet(packet)
                self.tier2_decap_ms = edge_ms
                self.update_ui()
                
                if decrypted_data == b"ERROR":
                    self.verify_status = "[bold red]CORRUPTED (InvalidTag)[/bold red]"
                    self.update_ui()
                    time.sleep(0.5)
                    continue

                # 4. Tier 2: Translate & Forward
                start_trans = time.perf_counter()
                try:
                    enc_data, nonce, qkd_key = self.edge_node.translate_and_forward(decrypted_data)
                    self.tier2_trans_ms = (time.perf_counter() - start_trans) * 1000
                except Exception:
                    self.verify_status = "[bold red]QKD POOL EMPTY[/bold red]"
                    self.update_ui()
                    time.sleep(0.5)
                    continue
                
                self.update_ui()

                # 5. Tier 3: Datacenter Receive & Verify
                start_dec = time.perf_counter()
                final_payload = self.datacenter_node.receive_and_decrypt(enc_data, nonce, qkd_key)
                self.tier3_decrypt_ms = (time.perf_counter() - start_dec) * 1000
                
                if final_payload:
                    self.verify_status = "[bold green]VERIFIED[/bold green]"
                else:
                    self.verify_status = "[bold red]FAILED[/bold red]"
                
                self.update_ui()
                
                # Rhythmic refresh (roughly 1-2 packets per second for visual readability)
                time.sleep(0.5)

if __name__ == "__main__":
    try:
        dashboard = Dashboard()
        dashboard.run_pipeline()
    except KeyboardInterrupt:
        pass
