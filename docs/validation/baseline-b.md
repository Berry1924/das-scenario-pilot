# Baseline B: Fixed-Rate Uncoordinated V2V Broadcast

**Configuration:** Standard 10 Hz Periodic V2V Broadcast  
**Evaluation Role:** Intermediate Benchmark Baseline  

---

## 1. Description of Baseline B

Baseline B represents conventional vehicular communication architectures (such as basic IEEE 802.11p or basic ESP-NOW without dynamic rate adaptation):
- Every active vehicle in the fleet broadcasts its kinematic state at a fixed, unvarying frequency (typically 10 Hz, or every 100 ms).
- No channel congestion monitoring is performed.
- Emergency braking packets are treated identically to routine position beacons, sharing the same software FIFO queue and transmission priority.

---

## 2. Bottlenecks & Hazards under High Fleet Density

1. **CSMA/CA Channel Saturation & Collisions:**  
   When 20 to 50 mining vehicles congregate at an excavation pit shovel, stockyard, or crusher queue, simultaneous 10 Hz transmissions saturate the wireless medium. The Channel Busy Ratio (CBR) climbs above 80%, causing packet collisions and random exponential back-offs.
2. **Packet Delivery Ratio (PDR) Collapse:**  
   In dense environments, fixed-rate beaconing causes PDR to drop to ~50–60%. Crucial emergency packets are dropped in the air.
3. **Queue Inversion Delays:**  
   Because emergency messages share the same FIFO queue as routine beacons, an emergency brake packet may wait behind 2 or 3 scheduled beacons, introducing 30–150 ms of queuing delay.
