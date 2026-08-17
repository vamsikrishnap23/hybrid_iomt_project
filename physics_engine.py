import random
import math

class PhysicsEngine:
    def __init__(self):
        self.edge_pos = (0, 0)
        self.device_positions = {
            "DEV-1": [5.0, 0.0],   # Close
            "DEV-2": [10.0, 0.0],  # Medium
            "DEV-3": [15.0, 0.0]   # Far
        }
        self.tx_power = -30 # Base transmission power in dBm
        self.path_loss_exponent = 2.5 # Urban/Indoor environment
    
    def move_device(self, dev_id, dx, dy):
        """Simulates a patient physically walking around."""
        if dev_id in self.device_positions:
            self.device_positions[dev_id][0] += dx
            self.device_positions[dev_id][1] += dy

    def get_signal_stats(self, dev_id):
        """Calculates exact RSSI and physics-based packet drop probability."""
        pos = self.device_positions.get(dev_id, [1, 0])
        distance = ((pos[0])**2 + (pos[1])**2)**0.5
        if distance < 1: distance = 1.0
        
        # Simplified Friis transmission / Path Loss equation (logarithmic)
        rssi = self.tx_power - (10 * self.path_loss_exponent * math.log10(distance))
        
        # Calculate signal degradation and drop probability based on RSSI
        if rssi < -100:
            drop_prob = 0.90 # Almost total loss
        elif rssi < -85:
            drop_prob = 0.40 # Heavy interference
        elif rssi < -70:
            drop_prob = 0.05 # Light interference
        else:
            drop_prob = 0.01 # Baseline environmental noise
            
        return distance, rssi, drop_prob
