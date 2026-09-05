import random
import math

class PhysicsEngine:
    """
    Tier 1 Physics Engine Simulator.
    Calculates the spatial and RF physics for IoMT devices to simulate 
    real-world Hospital signal degradation and packet drops.
    """
    def __init__(self):
        """
        Initializes the physical location space and RF baseline.
        """
        self.edge_pos = (0, 0)
        self.device_positions = {
            "DEV-1": [5.0, 0.0],
            "DEV-2": [10.0, 0.0],
            "DEV-3": [15.0, 0.0]
        }
        self.tx_power = -30
        self.path_loss_exponent = 2.5
    
    def move_device(self, dev_id: str, dx: float, dy: float):
        """
        Simulates a patient physically walking around, changing their spatial coordinates.
        
        Args:
            dev_id (str): The unique identifier of the IoMT device.
            dx (float): The change in X coordinate (meters).
            dy (float): The change in Y coordinate (meters).
        """
        if dev_id in self.device_positions:
            self.device_positions[dev_id][0] += dx
            self.device_positions[dev_id][1] += dy

    def get_signal_stats(self, dev_id: str) -> tuple:
        """
        Calculates exact RSSI and physics-based packet drop probability based on the Friis transmission equation.
        
        Args:
            dev_id (str): The unique identifier of the IoMT device.
            
        Returns:
            tuple: A tuple containing (distance in meters, RSSI in dBm, drop_prob as float).
        """
        pos = self.device_positions.get(dev_id, [1, 0])
        distance = ((pos[0])**2 + (pos[1])**2)**0.5
        if distance < 1: distance = 1.0
        
        rssi = self.tx_power - (10 * self.path_loss_exponent * math.log10(distance))
        
        if rssi < -100:
            drop_prob = 0.90
        elif rssi < -85:
            drop_prob = 0.40
        elif rssi < -70:
            drop_prob = 0.05
        else:
            drop_prob = 0.01
            
        return distance, rssi, drop_prob
