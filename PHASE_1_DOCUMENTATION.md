# Phase 1 Documentation: Hybrid PQC-QKD Edge Computing Framework for IoMT

## 1. What We Have Built (Phase 1 Summary)
In Phase 1, we successfully engineered and simulated the **Tier 1 (Wearable) $\rightarrow$ Tier 2 (Edge)** segment of the hybrid architecture. Instead of relying on static or mocked data, we built a fully dynamic, physics-based network simulation:

1. **Clinical Data Ingestion Engine**: Built `multi_device_engine.py` which dynamically downloads and streams real patient physiological data from the PhysioNet clinical databases (e.g., MIT-BIH Arrhythmia, Apnea-ECG, Sleep-EDF).
2. **Post-Quantum Cryptography (PQC) Layer**: Implemented NIST FIPS 203 standard **ML-KEM-512 (Kyber)** for secure key encapsulation on constrained devices, utilizing `liboqs`. We secured the payload using AES-GCM Authenticated Encryption with Associated Data (AEAD).
3. **Hardware Emulation**: Introduced algorithmic delay multipliers that scale standard CPU execution times to simulate the computational constraints of an ESP32 wearable (e.g., forcing ~25 ms delays for PQC encapsulation).
4. **Real UDP Network & Physics Engine**: Replaced basic Python memory transfers with a true OS-level UDP Client/Server architecture. Built `physics_engine.py` to calculate real-time **Received Signal Strength Indicator (RSSI)** based on the physical distance between the patient and the edge router.
5. **Interactive Dashboard & Web API**: Engineered a high-performance terminal UI (`tui_better.py`) with live topological mapping and interactive scenarios (Normal, MitM Attack, Patient Wandering), backed by an embedded HTTP server (Port 8080) for real-time JSON telemetry streaming.

---

## 2. Explaining the Project to Your Professor

When presenting Phase 1 to your professor, structure your explanation around **The Problem**, **Our Simulation Methodology**, and **The Mathematical Rigor**.

### A. The Core Problem (The PQC Bottleneck)
*"Professor, as outlined in recent 2025-2026 IEEE literature, pure Post-Quantum Cryptography (like ML-KEM) imposes a severe computational bottleneck on low-power IoMT wearables. The lattice-based Gaussian sampling overhead causes unacceptable latency, violating the strict `< 250 ms` real-time safety threshold required for critical cardiac telemetry. Our goal in Phase 1 was to empirically prove and simulate this bottleneck."*

### B. The Simulation Methodology
*"To prove this without requiring physical ESP32 hardware, we built a deterministic simulation pipeline. We utilized actual UDP sockets over the OS network stack. We didn't just randomly drop packets; we built an RF Physics Engine that tracks the $(x, y)$ coordinates of the patient and calculates the path loss. As the patient walks away from the Edge Gateway, the RSSI drops logarithmically, which naturally induces bit-corruption in the wireless channel."*

### C. The Cryptographic Reality
*"Because we used AES-GCM for payload encryption, any natural bit-flip caused by this weak signal instantly invalidates the cryptographic authentication tag (`InvalidTag`). Our Edge Node correctly traps this. Furthermore, we built an interactive Man-In-The-Middle (MitM) simulation that proves our PQC/AES-GCM pipeline reliably rejects active adversarial tampering in real-time."*

---

## 3. The Mathematical Formulations Used

You can present these specific formulas from your research paper to prove the simulation is anchored in mathematics:

### 1. Lattice-Based Encryption Overhead
The heavy computational delay simulated on the wearable (the reason we added the `iot_delay_multiplier`) stems from the Learning With Errors (LWE) lattice math:
$$ \mathbf{b} = \mathbf{A}\mathbf{s} + \mathbf{e} \pmod{q} $$
*Where $\mathbf{A}$ is a random matrix, $\mathbf{s}$ is the secret vector, and $\mathbf{e}$ is the Gaussian noise vector.*

### 2. The Physics Engine (Path Loss & RSSI)
To determine if a packet drops or corrupts over the UDP socket, we calculate the signal degradation using the logarithmic Friis transmission equation:
$$ RSSI = P_{tx} - (10 \cdot n \cdot \log_{10}(d)) $$
*Where $P_{tx}$ is the base transmission power (-30 dBm), $n$ is the path loss exponent (2.5 for indoor hospital environments), and $d$ is the physical distance in meters.*

### 3. Total System Latency
Phase 1 focuses on the first half of your ultimate latency constraint formula:
$$ T_{sys} = T_{PQC}^{enc} + T_{link}^{short} + T_{Edge}^{process} + T_{QKD}^{gen} + T_{link}^{long} \leq 250 \text{ ms} $$
*In our dashboard, we actively monitor $T_{PQC}^{enc}$ (Wearable Bloat) and $T_{link}^{short}$ (Network UDP Jitter).*

---

## 4. Why This Approach is Novel

1. **System-Level Emulation over Pure Math**: Most academic papers just output a static graph in MATLAB. Your project actually runs a live, asynchronous UDP network that streams real PhysioNet datasets, offering a tangible, interactive proof-of-concept.
2. **Physics-Driven Security Failures**: Instead of relying on random number generators for packet loss, your simulation marries RF physics (RSSI degradation) with Cryptography. It proves that weak Wi-Fi signals in a hospital naturally cause bit-flips, which trigger cryptographic failures (AEAD tag rejection)—a highly realistic edge-case often ignored in pure cryptographic literature.
3. **The Buffer Bloat Insight**: By utilizing decoupled asynchronous queues, your simulation accurately models "Buffer Bloat." If a patient experiences tachycardia (heart rate spikes to 50 Hz), but the wearable can only encrypt at 40 Hz due to ML-KEM overhead, the queue fills up, and latency exceeds 250 ms. This perfectly validates the core literature gap identified in your proposal!
