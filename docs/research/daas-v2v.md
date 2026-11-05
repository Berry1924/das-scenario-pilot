# DAAS-V2V: Density-Aware Adaptive Secure Machine Learning Engine

**Project:** DAAS-V2V (Core ML Research Subsystem)  
**Authors:** Team IGRIS07, SKP Engineering College  
**Target Venue:** IEEE International Conference on Smart Computing, Electrical and Power Technologies (IConSCEPT 2026)  
**Document Type:** Machine Learning & Network Research Architecture  

---

## 1. Research Motivation & Problem Formulation

In high-density vehicular ad-hoc networks (VANETs), standard periodic beaconing (typically fixed at 10 Hz) induces severe radio channel congestion as vehicle count scales. Under dense traffic conditions:
- **Packet Collision Storms:** Uncoordinated Carrier-Sense Multiple Access (CSMA/CA) transmissions collide frequently.
- **Packet Delivery Ratio (PDR) Collapse:** PDR degrades sharply below 60%, causing life-critical emergency braking alerts to be dropped or excessively delayed.
- **Channel Busy Ratio (CBR) Saturation:** Transceivers spend excessive time backing off rather than transmitting critical safety telemetry.

**The DAAS-V2V Solution:**  
An intelligent, supervisory machine learning engine that monitors local RF telemetry (received signal strength indicator RSSI, signal-to-noise ratio SNR, instantaneous packet drop rate, and vehicle kinematics) to predict channel congestion state and vehicular density in real time, dynamically adapting routine beacon rates between **2 Hz (congested)** and **20 Hz (sparse)** to optimize channel capacity while preserving safety-path isolation.

---

## 2. Synthetic Dataset & Experimental Methodology

### 2.1 Dataset Composition (`synthetic_vanet.csv`)
Because physical mine haul fleets cannot be subjected to simulated catastrophic communication crashes during active production, the research team generated a mathematically rigorous synthetic VANET benchmark dataset:
- **Total Records:** **85,248** labeled vehicular network frames.
- **Data Generator:** `ml/scripts/generate_synthetic_dataset.py`.
- **Primary Features:**
  1. `speed_mps`: Vehicle instantaneous velocity (0 to 35 m/s).
  2. `accel_mps2`: Longitudinal acceleration (-8 to +4 $\text{m/s}^2$).
  3. `distance_m`: Forward distance to preceding vehicle (1 to 200 m).
  4. `rssi_dbm`: Received Signal Strength Indicator (-110 to -30 dBm).
  5. `snr_db`: Signal-to-Noise Ratio (0 to 40 dB).
  6. `packet_drop_rate`: Exponentially weighted moving average of dropped packets (0.0 to 1.0).
  7. `channel_busy_ratio`: Estimated percentage of time channel is occupied (0.0 to 1.0).
- **Target Labels:**
  1. `density_level`: Multi-class category (`LOW`, `MEDIUM`, `HIGH`).
  2. `channel_congestion`: Binary classification (`UNCONGESTED = 0`, `CONGESTED = 1`).

---

## 3. Machine Learning Models & Evaluated Benchmarks

### 3.1 Model Architectures
- **Algorithm:** Extreme Gradient Boosting (`XGBoost`) Classifier.
- **Implementation:** Python 3.11 with scikit-learn and XGBoost native C-library bindings.
- **Training Pipeline:** Stratified 80/20 train-test split (`ml/src/daas/training/splitter.py`) with 5-fold cross-validation.

### 3.2 Numerical Evaluation Results
The empirical evaluation results achieved on the 85,248-record test suite (fully documented in `ml/evaluation/DAAS_FINAL_ML_VALIDATION.md`) are summarized below:

| Metric | Evaluated Value | Evaluation Context & Scope |
| :--- | :---: | :--- |
| **Density Classification Accuracy** | **99.72%** | Test set accuracy across Low, Medium, and High traffic density classes. |
| **Congestion ROC-AUC Score** | **0.9301** | Binary classification area under Receiver Operating Characteristic curve. |
| **Precision (Congested Class)** | **0.9415** | Precision in identifying saturated RF channels. |
| **Recall (Congested Class)** | **0.9180** | Recall in identifying saturated RF channels. |
| **Average Host Inference Latency** | **9.93 ms** | Measured on host workstation CPU (Intel i7 / AMD Ryzen). |

> [!IMPORTANT]
> These performance metrics apply strictly to the **DAAS-V2V synthetic VANET dataset**. They must never be conflated with physical open-cast mine field trial data.

---

## 4. Policy Execution & Closed-Loop Rate Adaptation

The policy engine (`ml/src/daas/policy/adaptive.py`) translates model predictions into closed-loop rate recommendations sent back to vehicle nodes:

```python
if is_safety_critical:
    # Hard invariant: Emergency packets bypass adaptation entirely
    target_rate_hz = 20.0  # Maximum burst rate
elif predicted_congestion == CONGESTED and predicted_density == HIGH:
    target_rate_hz = 2.0   # Scale back routine beacons to relieve channel
elif predicted_congestion == UNCONGESTED and predicted_density == LOW:
    target_rate_hz = 15.0  # High-rate precision tracking when medium is clear
else:
    target_rate_hz = 10.0  # Nominal 10 Hz beaconing
```
