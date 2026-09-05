import queue
import threading
import time
import logging
from qkd_engine import QKDEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QKDKeyPool")

class QKDKeyPool:
    """
    Background thread manager that pre-generates QKD derived symmetric keys.
    Maintains a thread-safe pool of keys so the Edge Gateway avoids blocking
    (and causing fatal network latency) while waiting for quantum circuit simulations.
    """
    def __init__(self, max_pool_size: int = 50, num_qubits_per_key: int = 512, qber_threshold: float = 0.11):
        """
        Initializes the Key Pool.
        
        Args:
            max_pool_size (int): Maximum number of pre-generated 256-bit keys to hold in memory.
            num_qubits_per_key (int): Number of qubits to simulate per BB84 batch.
            qber_threshold (float): The maximum allowed QBER (e.g. 11%). Keys exceeding this are discarded.
        """
        self.max_pool_size = max_pool_size
        self.num_qubits = num_qubits_per_key
        self.qber_threshold = qber_threshold
        
        self.key_queue = queue.Queue(maxsize=max_pool_size)
        self._stop_event = threading.Event()
        self._generator_thread = threading.Thread(target=self._generate_keys_worker, daemon=True)
        self.engine = QKDEngine(num_qubits=num_qubits_per_key)

    def start(self):
        """Starts the background key generation thread."""
        logger.info("Starting QKD Key Pool background generator...")
        self._stop_event.clear()
        if not self._generator_thread.is_alive():
            self._generator_thread.start()

    def stop(self):
        """Signals the background thread to stop gracefully."""
        logger.info("Stopping QKD Key Pool background generator...")
        self._stop_event.set()
        # To avoid hanging on join if the thread is blocking on queue.put
        # we can unblock it by popping an item if it's full, but daemon thread 
        # naturally dies when main program exits.

    def _generate_keys_worker(self):
        """Worker loop that continuously runs the BB84 protocol and queues valid keys."""
        while not self._stop_event.is_set():
            if not self.key_queue.full():
                try:
                    # Run the expensive quantum simulation
                    result = self.engine.run_protocol()
                    qber = result["qber"]
                    
                    if qber <= self.qber_threshold:
                        # Pool the generated AES-256 key
                        self.key_queue.put(result["final_key"], timeout=1)
                        logger.debug(f"Pooled new quantum key. Pool size: {self.key_queue.qsize()}/{self.max_pool_size}")
                    else:
                        logger.warning(f"Discarding key due to high QBER ({qber:.4f} > {self.qber_threshold}). Interception likely.")
                except queue.Full:
                    pass
                except Exception as e:
                    logger.error(f"Error during QKD key generation: {e}")
            else:
                # Pool is full, throttle to save CPU cycles
                time.sleep(0.5)

    def get_key(self, timeout: float = 5.0) -> bytes:
        """
        Retrieves a pre-generated AES-256 key from the pool instantly.
        Blocks up to 'timeout' seconds if the pool is temporarily empty.
        
        Returns:
            bytes: A 256-bit symmetric key.
            
        Raises:
            queue.Empty: If no key is available within the timeout period.
        """
        try:
            key = self.key_queue.get(timeout=timeout)
            logger.debug(f"Key pulled from pool. Remaining pool size: {self.key_queue.qsize()}/{self.max_pool_size}")
            return key
        except queue.Empty:
            logger.error("CRITICAL: QKD Key pool exhausted! Network latency spike imminent.")
            raise

if __name__ == "__main__":
    print("--- Testing QKD Key Pool Manager ---")
    # Small pool size for quick testing
    pool = QKDKeyPool(max_pool_size=5)
    pool.start()
    
    # Wait for the simulator thread to generate some keys
    print("Waiting for keys to be generated in the background...")
    time.sleep(5) 
    
    try:
        key1 = pool.get_key()
        print(f"Retrieved Key 1 (hex): {key1.hex()}")
        
        key2 = pool.get_key()
        print(f"Retrieved Key 2 (hex): {key2.hex()}")
    except queue.Empty:
        print("Failed to get key.")
        
    pool.stop()
