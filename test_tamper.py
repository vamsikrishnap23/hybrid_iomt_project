import time
import json
from multi_device_engine import IoMTDevice
from pqc_nodes import WearableNode, EdgeNode
from network_channel import SimulatedNetwork

dev = IoMTDevice("DEV-1", "100", "mitdb", "Wearable ECG")
w_node = WearableNode()
edge = EdgeNode()

for _ in range(5):
    raw_payload = dev.get_next_tick()
    cipher, enc_data, nonce, lat_w = w_node.encapsulate_and_encrypt(edge.public_key, raw_payload)
    decrypted_data, lat_e = edge.receive_and_decrypt(cipher, enc_data, nonce)
    print("Decrypted:", decrypted_data == raw_payload)
