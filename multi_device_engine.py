import time
import json
import os
import wfdb

class IoMTDevice:
    def __init__(self, device_id, patient_id, db_dir, device_type):
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
        except Exception as e:
            self.signals = None
            self.sig_names = []

    def get_next_tick(self):
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
