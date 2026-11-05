# Baseline A: Autonomous Local Sensing Only (No V2V)

**Configuration:** Isolated Vehicle System (No Wireless Interconnect)  
**Evaluation Role:** Lower Control Baseline  

---

## 1. Description of Baseline A

Baseline A represents the current standard deployed in most surface mining fleets:
- Each vehicle relies strictly on its own on-board sensors (short-range proximity sensors, ultrasonic transducers, reversing radars, or optical mirrors/cameras).
- There is **no communication** between vehicles.
- A vehicle has zero awareness of obstacles or preceding trucks until they enter physical optical or sensor line-of-sight.

---

## 2. Failure Modes in Open-Cast Iron Ore Mines

1. **Optical Extinction in Thick Fog & Airborne Dust:**  
   In radiation fog or dense hematite dust clouds, optical range collapses to under 5 meters. A 100T haul truck moving at 30 km/h needs 40+ meters to stop, making rear-end collisions physically inevitable.
2. **Blind Haul Road Switchbacks:**  
   When descending a steep haul road with 15-meter vertical rock benches, oncoming uphill trucks are hidden behind the rock face. Local sensors cannot "see through" rock benches.
3. **No Cooperative Braking Lead Time:**  
   If a lead vehicle hits a sudden fault or slams its brakes in dense dust, the follower vehicle gets zero warning until its own local sensor detects the obstacle at short range.
