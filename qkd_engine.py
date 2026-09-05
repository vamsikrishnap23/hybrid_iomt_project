import numpy as np
import hashlib
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator

class QKDEngine:
    """
    Quantum Key Distribution (QKD) Engine simulating the BB84 protocol.
    Provides quantum state preparation, measurement, sifting, QBER calculation,
    and final AES-256 key derivation.
    """
    def __init__(self, num_qubits: int = 512, intercept_prob: float = 0.0):
        """
        Initializes the QKD engine.
        
        Args:
            num_qubits (int): The number of qubits to transmit in a single BB84 batch.
            intercept_prob (float): The probability (0.0 to 1.0) that Eve intercepts a qubit.
        """
        self.num_qubits = num_qubits
        self.intercept_prob = intercept_prob
        self.simulator = AerSimulator()

    def generate_random_bits_and_bases(self):
        """Generates random bits and bases (0 for Rectilinear, 1 for Diagonal)."""
        bits = np.random.randint(2, size=self.num_qubits)
        bases = np.random.randint(2, size=self.num_qubits)
        return bits, bases

    def prepare_states(self, alice_bits, alice_bases) -> list[QuantumCircuit]:
        """
        Alice prepares the quantum states based on her random bits and bases.
        """
        circuits = []
        for i in range(self.num_qubits):
            qr = QuantumRegister(1, 'q')
            cr = ClassicalRegister(1, 'bob_c')
            qc = QuantumCircuit(qr, cr)
            
            # Encode the bit
            if alice_bits[i] == 1:
                qc.x(0)
                
            # Encode the basis (apply Hadamard for Diagonal basis)
            if alice_bases[i] == 1:
                qc.h(0)
                
            circuits.append(qc)
        return circuits

    def intercept_and_resend(self, circuits: list[QuantumCircuit]) -> list[QuantumCircuit]:
        """
        Simulates an eavesdropper (Eve) intercepting and resending the qubits.
        Eve randomly selects bases and measures the qubits, inherently collapsing the states.
        """
        eve_bases = np.random.randint(2, size=self.num_qubits)
        for i in range(self.num_qubits):
            if np.random.rand() < self.intercept_prob:
                eve_cr = ClassicalRegister(1, 'eve_c')
                circuits[i].add_register(eve_cr)
                
                # Eve rotates to her chosen basis
                if eve_bases[i] == 1:
                    circuits[i].h(0)
                    
                # Eve measures, causing the quantum state to collapse
                circuits[i].measure(0, eve_cr)
                
                # Eve resends the state. To simulate Bob receiving this collapsed state 
                # in the standard basis channel, we rotate back if Eve measured in diagonal.
                if eve_bases[i] == 1:
                    circuits[i].h(0)
        return circuits

    def measure_states(self, circuits: list[QuantumCircuit], bob_bases) -> list[int]:
        """
        Bob measures the received quantum states according to his random bases.
        """
        for i in range(self.num_qubits):
            # Bob rotates to his chosen basis
            if bob_bases[i] == 1:
                circuits[i].h(0)
            # Bob measures into his classical register (index 0 corresponds to 'bob_c')
            circuits[i].measure(0, 0)
            
        # Run all circuits in a single batch for maximum simulator performance
        result = self.simulator.run(circuits, shots=1).result()
        
        bob_bits = []
        for i in range(self.num_qubits):
            counts = result.get_counts(i)
            # Qiskit outputs classical registers as space-separated strings.
            # The rightmost substring belongs to the first added register ('bob_c').
            measured_str = list(counts.keys())[0]
            bit = int(measured_str.split()[-1]) 
            bob_bits.append(bit)
            
        return bob_bits

    def sift_keys(self, alice_bits, bob_bits, alice_bases, bob_bases):
        """
        Alice and Bob compare their bases over a classical public channel.
        They discard bits where their bases did not match.
        """
        sifted_alice = []
        sifted_bob = []
        for i in range(self.num_qubits):
            if alice_bases[i] == bob_bases[i]:
                sifted_alice.append(alice_bits[i])
                sifted_bob.append(bob_bits[i])
        return sifted_alice, sifted_bob

    def calculate_qber(self, sifted_alice, sifted_bob) -> float:
        """
        Calculates the Quantum Bit Error Rate (QBER) from a subset of the sifted key.
        (For simplicity, we compare the entire sifted key in this simulation).
        """
        if not sifted_alice:
            return 0.0
        errors = sum(1 for a, b in zip(sifted_alice, sifted_bob) if a != b)
        return errors / len(sifted_alice)

    def derive_key(self, sifted_key: list[int]) -> bytes:
        """
        Hashes the sifted key using SHA-256 to produce a final, uniformly distributed 
        256-bit symmetric key suitable for AES-GCM.
        """
        bit_string = "".join(str(b) for b in sifted_key)
        return hashlib.sha256(bit_string.encode()).digest()

    def run_protocol(self) -> dict:
        """
        Executes the full BB84 protocol workflow.
        Returns a dictionary containing the sifted key length, QBER, and derived final AES key.
        """
        alice_bits, alice_bases = self.generate_random_bits_and_bases()
        circuits = self.prepare_states(alice_bits, alice_bases)
        
        if self.intercept_prob > 0.0:
            circuits = self.intercept_and_resend(circuits)
            
        _, bob_bases = self.generate_random_bits_and_bases()
        bob_bits = self.measure_states(circuits, bob_bases)
        
        sifted_alice, sifted_bob = self.sift_keys(alice_bits, bob_bits, alice_bases, bob_bases)
        qber = self.calculate_qber(sifted_alice, sifted_bob)
        final_key = self.derive_key(sifted_bob)
        
        return {
            "sifted_key_length": len(sifted_bob),
            "qber": qber,
            "final_key": final_key
        }

if __name__ == "__main__":
    print("--- Running BB84 Simulation (No Eve) ---")
    engine = QKDEngine(num_qubits=512, intercept_prob=0.0)
    result = engine.run_protocol()
    print(f"Sifted Key Length: {result['sifted_key_length']} bits")
    print(f"QBER: {result['qber']:.4f}")
    print(f"Derived AES-256 Key (hex): {result['final_key'].hex()}")

    print("\n--- Running BB84 Simulation (Eve Intercept Prob: 1.0) ---")
    engine_eve = QKDEngine(num_qubits=512, intercept_prob=1.0)
    result_eve = engine_eve.run_protocol()
    print(f"Sifted Key Length: {result_eve['sifted_key_length']} bits")
    print(f"QBER: {result_eve['qber']:.4f}")
    if result_eve['qber'] > 0.11:
        print("ALERT: High QBER detected! Eavesdropper presence highly likely.")
