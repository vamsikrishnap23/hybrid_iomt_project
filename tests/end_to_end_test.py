import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import time
import json
import socket
from pqc_nodes import WearableNode, EdgeNode
from datacenter_node import DatacenterNode
from qkd_key_manager import QKDKeyPool
from physics_engine import PhysicsEngine

def main():
    print("=== Hybrid PQC-QKD Edge Computing Framework ===")
    print("Starting Phase 3: End-to-End Cryptographic Translation Test\n")

    # 1. Initialize the QKD Key Pool (Simulating the active fiber link)
    print("[1] Initializing QKD Key Pool (BB84 Simulation)...")
    qkd_pool = QKDKeyPool(max_pool_size=5)
    qkd_pool.start()
    
    # Allow some time for the Qiskit simulator to spool up a few AES-256 keys
    print("Waiting for quantum simulator to pool AES-256 keys in the background...")
    time.sleep(4) 
    
    # 2. Initialize the Hardware Nodes
    print("\n[2] Initializing Tiers 1, 2, and 3 Nodes...")
    edge_ip = "127.0.0.1"
    edge_port = 5005
    
    edge_node = EdgeNode(edge_ip, edge_port, kem_algorithm="ML-KEM-512", qkd_pool=qkd_pool)
    wearable_node = WearableNode("Dev-100", edge_ip, edge_port, kem_algorithm="ML-KEM-512")
    datacenter_node = DatacenterNode(qkd_pool=qkd_pool)
    
    physics = PhysicsEngine()
    
    # 3. Generate Mock Clinical Data
    payload_dict = {"patient_id": "100", "ecg_mV": -0.19, "heart_rate": 72, "alert": "Normal"}
    raw_payload = json.dumps(payload_dict).encode('utf-8')
    print(f"\n[3] Wearable Data Generated: {payload_dict}")
    
    # ==========================================
    # STEP 1: Wearable (PQC Encapsulation)
    # ==========================================
    print("\n--- TIER 1 (Wearable -> Edge) ---")
    print("Wearable executing ML-KEM-512 Encapsulation and AES-GCM Encryption...")
    
    success, dist, rssi, p_ms = wearable_node.encapsulate_and_transmit(
        edge_node.public_key, 
        raw_payload, 
        physics
    )
    
    if not success:
        print("Packet dropped due to simulated physics (RSSI loss). Run script again.")
        qkd_pool.stop()
        return

    print("Packet transmitted over UDP socket.")
    
    # ==========================================
    # STEP 2: Edge (PQC Decapsulation)
    # ==========================================
    print("\n--- TIER 2 (Edge Gateway: Decryption) ---")
    packet, _ = edge_node.receive_packet()
    if not packet:
        print("Edge failed to receive packet (Timeout).")
        qkd_pool.stop()
        return
        
    print("Edge executing ML-KEM-512 Decapsulation and AES-GCM Decryption...")
    decrypted_data, edge_ms = edge_node.process_packet(packet)
    
    if decrypted_data == b"ERROR":
        print("Edge failed to decrypt data (InvalidTag). Integrity compromised.")
        qkd_pool.stop()
        return
        
    print(f"Edge successfully recovered raw clinical data: {decrypted_data.decode('utf-8')}")
    
    # ==========================================
    # STEP 3: Edge (Cryptographic Translation)
    # ==========================================
    print("\n--- TIER 2 -> TIER 3 (Edge Gateway: Translation) ---")
    print("Edge fetching synchronized quantum key from QKD pool...")
    
    try:
        enc_data, nonce, qkd_key = edge_node.translate_and_forward(decrypted_data)
        print(f"Edge re-encrypted data with unique nonce and QKD-derived key: {qkd_key.hex()[:16]}...")
        print("Forwarding to Datacenter...")
    except Exception as e:
        print(f"Translation failed: {e}")
        qkd_pool.stop()
        return
        
    # ==========================================
    # STEP 4: Datacenter (QKD Decryption)
    # ==========================================
    print("\n--- TIER 3 (Datacenter: Reception) ---")
    print(f"Datacenter utilizing shared QKD key: {qkd_key.hex()[:16]}... to verify AEAD tag and decrypt.")
    
    final_payload = datacenter_node.receive_and_decrypt(enc_data, nonce, qkd_key)
    
    if final_payload:
        print(f"\n[SUCCESS] End-to-End Cryptographic Chain Complete!")
        print(f"Final Verified Payload: {json.loads(final_payload.decode('utf-8'))}")
    else:
        print("\n[FAILURE] Datacenter failed to verify payload.")
        
    qkd_pool.stop()
    print("\nShutting down QKD pool.")

if __name__ == "__main__":
    main()
