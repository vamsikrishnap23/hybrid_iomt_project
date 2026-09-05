from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

class DatacenterNode:
    """
    Tier 3: The Healthcare Datacenter Node.
    Receives QKD-encrypted payloads from the Edge Node and decrypts them.
    In this simulation, it accepts a reference to the QKDKeyPool to simulate 
    possessing the synchronized quantum keys via the BB84 fiber link.
    """
    def __init__(self, qkd_pool):
        """
        Initializes the Datacenter Node.
        
        Args:
            qkd_pool (QKDKeyPool): Reference to the quantum key pool to simulate the shared synchronized state.
        """
        self.qkd_pool = qkd_pool

    def receive_and_decrypt(self, enc_data, nonce, qkd_key):
        """
        Receives the encrypted payload from the Edge Gateway and decrypts it
        using the synchronized QKD AES-256 key.
        
        Args:
            enc_data (bytes): The AES-GCM encrypted payload.
            nonce (bytes): The unique 12-byte nonce used for encryption.
            qkd_key (bytes): The symmetric key originally generated via the QKD BB84 protocol.
            
        Returns:
            bytes: The decrypted raw clinical JSON, or None if integrity verification fails.
        """
        aesgcm = AESGCM(qkd_key)
        try:
            # Decrypts the data and automatically verifies the Authentication Tag (AEAD)
            raw_payload = aesgcm.decrypt(nonce, enc_data, None)
            return raw_payload
        except InvalidTag:
            print("DATACENTER ALERT: Payload integrity check failed (InvalidTag).")
            return None
