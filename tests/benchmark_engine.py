import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import time
import os
import matplotlib.pyplot as plt
import numpy as np
from statistics import mean

# Import our custom framework modules
from pqc_nodes import WearableNode, EdgeNode
from datacenter_node import DatacenterNode
from qkd_key_manager import QKDKeyPool
from physics_engine import PhysicsEngine
from qkd_engine import QKDEngine

def test_a_latency():
    print("Starting Test A: End-to-End Latency vs. Payload Size...")
    
    # 6 specific payload sizes spanning small telemetry to large image segments
    payload_sizes = [128, 256, 512, 1024, 2048, 4096]
    avg_latencies = []
    num_iterations = 50
    
    # Initialize the background QKD Pool
    qkd_pool = QKDKeyPool(max_pool_size=60) 
    qkd_pool.start()
    time.sleep(2) # Give the qiskit simulator a head start to spool keys
    
    # Initialize Nodes on a unique port to avoid conflicts
    test_port = 5055
    edge_node = EdgeNode("127.0.0.1", test_port, kem_algorithm="ML-KEM-512", qkd_pool=qkd_pool)
    wearable_node = WearableNode("Dev-Bench", "127.0.0.1", test_port, kem_algorithm="ML-KEM-512")
    datacenter_node = DatacenterNode(qkd_pool=qkd_pool)
    
    physics = PhysicsEngine()
    # Force perfect physics location to prevent unrelated packet drops during timing
    physics.device_positions["Dev-Bench"] = [0.0, 0.0]
    physics.tx_power = -30
    
    for size in payload_sizes:
        raw_payload = os.urandom(size)
        latencies = []
        print(f"  Testing Payload Size: {size:4} bytes... ", end="", flush=True)
        
        valid_samples = 0
        while valid_samples < num_iterations:
            # We measure absolute wall-clock time which includes the physics engine's
            # time.sleep() delay multipliers simulating the ESP32 constraints.
            start_time = time.perf_counter()
            
            # --- TIER 1 ---
            success, _, _, _ = wearable_node.encapsulate_and_transmit(
                edge_node.public_key, raw_payload, physics, force_tamper=False
            )
            
            if not success:
                continue # Retry if random natural loss occurs
                
            # --- TIER 2 ---
            packet, _ = edge_node.receive_packet()
            if not packet:
                continue
                
            decrypted_data, _ = edge_node.process_packet(packet)
            if decrypted_data == b"ERROR":
                continue
                
            try:
                enc_data, nonce, qkd_key = edge_node.translate_and_forward(decrypted_data)
            except Exception:
                time.sleep(0.1) # Wait for QKD pool to generate a key
                continue
                
            # --- TIER 3 ---
            final_payload = datacenter_node.receive_and_decrypt(enc_data, nonce, qkd_key)
            if final_payload:
                end_time = time.perf_counter()
                total_ms = (end_time - start_time) * 1000
                latencies.append(total_ms)
                valid_samples += 1
                
        avg_latency = mean(latencies)
        avg_latencies.append(avg_latency)
        print(f"Average: {avg_latency:6.2f} ms")
        
    qkd_pool.stop()
    
    # Plotting Test A
    plt.figure(figsize=(10, 6), dpi=300)
    plt.plot(payload_sizes, avg_latencies, marker='o', markersize=8, linewidth=2.5, color='#2c3e50', label='Hybrid PQC-QKD Latency')
    plt.axhline(y=250, color='#e74c3c', linestyle='--', linewidth=2, label='AAMI Clinical Limit (250 ms)')
    
    plt.title("End-to-End Latency vs. Medical Payload Size", fontsize=16, fontweight='bold', pad=15)
    plt.xlabel("Payload Size (Bytes)", fontsize=12, fontweight='bold')
    plt.ylabel("Average E2E Latency (ms)", fontsize=12, fontweight='bold')
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.legend(fontsize=12, loc='upper left')
    plt.tight_layout()
    
    plt.savefig("fig1_latency_benchmark.png")
    print("Test A Complete. Saved to fig1_latency_benchmark.png.\n")

def test_b_qber():
    print("Starting Test B: QBER vs. Interception Probability...")
    probabilities = np.arange(0.0, 1.1, 0.1)
    qber_results = []
    
    for prob in probabilities:
        print(f"  Testing Interception Probability: {prob:.1f}... ", end="", flush=True)
        # Using 1024 qubits batch to get slightly smoother statistical lines
        engine = QKDEngine(num_qubits=1024, intercept_prob=prob)
        result = engine.run_protocol()
        qber = result["qber"]
        qber_results.append(qber)
        print(f"QBER: {qber*100:5.2f}%")
        
    # Plotting Test B
    plt.figure(figsize=(10, 6), dpi=300)
    plt.plot(probabilities, qber_results, marker='s', markersize=8, linewidth=2.5, color='#8e44ad', label='Measured QBER (Qiskit)')
    plt.axhline(y=0.11, color='#e74c3c', linestyle='--', linewidth=2, label='Eve Detection Threshold (11%)')
    
    plt.title("Quantum Bit Error Rate (QBER) vs. Interception Probability", fontsize=16, fontweight='bold', pad=15)
    plt.xlabel("Interception Probability", fontsize=12, fontweight='bold')
    plt.ylabel("QBER", fontsize=12, fontweight='bold')
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.legend(fontsize=12, loc='upper left')
    plt.tight_layout()
    
    plt.savefig("fig2_qber_benchmark.png")
    print("Test B Complete. Saved to fig2_qber_benchmark.png.")

if __name__ == "__main__":
    print("=== Phase 4 Benchmarking Engine ===")
    test_a_latency()
    test_b_qber()
    print("All empirical tests complete.")
