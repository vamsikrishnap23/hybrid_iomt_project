import random
import time

class SimulatedNetwork:
    def __init__(self, drop_rate=0.1, tamper_rate=0.1, min_jitter_ms=10, max_jitter_ms=100):
        self.drop_rate = drop_rate
        self.tamper_rate = tamper_rate
        self.min_jitter_ms = min_jitter_ms
        self.max_jitter_ms = max_jitter_ms

    def transmit(self, ciphertext, encrypted_payload, nonce, initial_latency_ms):
        if random.random() < self.drop_rate:
            return None 
            
        tampered = False
        if random.random() < self.tamper_rate:
            payload_array = bytearray(encrypted_payload)
            if len(payload_array) > 0:
                target_idx = random.randint(0, len(payload_array) - 1)
                payload_array[target_idx] ^= 0xFF
                encrypted_payload = bytes(payload_array)
                tampered = True

        jitter = random.uniform(self.min_jitter_ms, self.max_jitter_ms)
        time.sleep(jitter / 1000.0)
        
        return {
            "ciphertext": ciphertext,
            "encrypted_payload": encrypted_payload,
            "nonce": nonce,
            "network_latency": jitter,
            "total_latency": initial_latency_ms + jitter,
            "was_tampered": tampered
        }
