import oqs
import time
import socket
import pickle
import random
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from physics_engine import PhysicsEngine

class WearableNode:
    def __init__(self, dev_id, edge_ip, edge_port, kem_algorithm="ML-KEM-512"):
        self.dev_id = dev_id
        self.edge_ip = edge_ip
        self.edge_port = edge_port
        self.kem_alg = kem_algorithm
        self.kem = oqs.KeyEncapsulation(self.kem_alg)
        self.iot_delay_multiplier = 250 
        
        # REAL UDP SOCKET
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def encapsulate_and_transmit(self, edge_public_key, raw_payload, physics: PhysicsEngine, force_tamper=False):
        start_time = time.perf_counter()
        ciphertext, shared_secret = self.kem.encap_secret(edge_public_key)
        aesgcm = AESGCM(shared_secret[:32])
        nonce = b'123456789012' 
        encrypted_payload = aesgcm.encrypt(nonce, raw_payload, None)
        end_time = time.perf_counter()
        
        actual_pc_ms = (end_time - start_time) * 1000
        simulated_iot_ms = actual_pc_ms * self.iot_delay_multiplier
        time.sleep(simulated_iot_ms / 1000.0) 
        
        # Calculate physical constraints
        distance, rssi, drop_prob = physics.get_signal_stats(self.dev_id)
        
        if random.random() >= drop_prob:
            packet = {
                "dev_id": self.dev_id,
                "ciphertext": ciphertext,
                "encrypted_payload": encrypted_payload,
                "nonce": nonce,
                "gen_time": time.time(),
                "rssi": rssi,
                "distance": distance
            }
            
            # Real physics: weaker signal causes bit corruption OR an active MitM attacker
            tamper_chance = max(0, (drop_prob / 2.0)) 
            if force_tamper or random.random() < tamper_chance:
                payload_array = bytearray(encrypted_payload)
                if len(payload_array) > 0:
                    payload_array[random.randint(0, len(payload_array)-1)] ^= 0xFF
                    packet["encrypted_payload"] = bytes(payload_array)
                    packet["was_tampered"] = force_tamper

            data = pickle.dumps(packet)
            # Send data over actual OS network stack
            self.sock.sendto(data, (self.edge_ip, self.edge_port))
            return True, distance, rssi, simulated_iot_ms
        else:
            return False, distance, rssi, simulated_iot_ms

class EdgeNode:
    def __init__(self, bind_ip, bind_port, kem_algorithm="ML-KEM-512"):
        self.kem_alg = kem_algorithm
        self.kem = oqs.KeyEncapsulation(self.kem_alg)
        self.public_key = self.kem.generate_keypair()
        self.edge_delay_multiplier = 15 
        
        # REAL UDP SERVER
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, bind_port))
        self.sock.settimeout(0.1)

    def receive_packet(self):
        try:
            data, addr = self.sock.recvfrom(65535)
            packet = pickle.loads(data)
            return packet, addr
        except socket.timeout:
            return None, None
        except Exception:
            return None, None

    def process_packet(self, packet):
        start_time = time.perf_counter()
        shared_secret = self.kem.decap_secret(packet["ciphertext"])
        aesgcm = AESGCM(shared_secret[:32])
        try:
            decrypted_data = aesgcm.decrypt(packet["nonce"], packet["encrypted_payload"], None)
            end_time = time.perf_counter()
            actual_pc_ms = (end_time - start_time) * 1000
            simulated_edge_ms = actual_pc_ms * self.edge_delay_multiplier
            time.sleep(simulated_edge_ms / 1000.0)
            return decrypted_data, simulated_edge_ms
        except InvalidTag:
            return b"ERROR", 0.0