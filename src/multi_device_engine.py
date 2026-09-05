import time
import json
import os
import wfdb

class IoMTDevice:
    """
    Tier 1: Clinical Data Ingestion Engine.
    Streams real patient physiological data from the PhysioNet databases to simulate an active medical wearable.
    """
    def __init__(self, device_id: str, patient_id: str, db_dir: str, device_type: str):
        """
        Initializes the IoMT Device and pre-loads clinical telemetry.
        
        Args:
            device_id (str): The logical network ID of the device.
            patient_id (str): The PhysioNet patient record ID (e.g., '100').
            db_dir (str): The PhysioNet database directory (e.g., 'mitdb').
            device_type (str): Human-readable device classification (e.g., 'Pacemaker').
        """
        self.device_id = device_id
        self.patient_id = patient_id
        self.db_dir = db_dir
        self.device_type = device_type
        self.sequence_num = 0
        self.current_index = 0
        
        os.makedirs('data', exist_ok=True)
        local_path = os.path.join('data', self.patient_id)
        
        if not os.path.exists(local_path + '.dat'):
            print(f"Downloading {self.patient_id} from {self.db_dir}...")
            wfdb.dl_database(self.db_dir, 'data', records=[self.patient_id])
            
        try:
            self.signals, self.fields = wfdb.rdsamp(local_path)
            self.sig_names = self.fields.get('sig_name', [])
        except Exception:
            self.signals = None
            self.sig_names = []

    def get_next_tick(self) -> bytes:
        """
        Retrieves the next chronological slice of telemetry from the medical dataset.
        
        Returns:
            bytes: UTF-8 encoded JSON string containing the raw physiological payload.
        """
        self.sequence_num += 1
        payload = {
            "device_id": self.device_id,
            "patient_id": self.patient_id,
            "device_type": self.device_type,
            "seq_num": self.sequence_num,
            "timestamp": time.time(),
            "data": {}
        }
        
        if self.signals is not None:
            for i in range(min(2, len(self.sig_names))):
                val = float(self.signals[self.current_index, i])
                payload["data"][self.sig_names[i]] = round(val, 3)
            
            self.current_index += 1
            if self.current_index >= len(self.signals):
                self.current_index = 0
        else:
            payload["data"]["fallback"] = 0.5
            
        return json.dumps(payload).encode('utf-8')
