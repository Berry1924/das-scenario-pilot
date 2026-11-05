# Packet Sequence Validation & Loss Tracking

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Document Type:** Network Protocol Engineering Specification  

---

## 1. Sequence Validation Architecture

In ad-hoc RF environments like open-cast mining pits, packets are subject to reflection from iron ore walls, multipath fading, and antenna polarization shifts. These effects cause intermittent frame drops or out-of-order delivery.

To ensure that the edge node can assess RF link health and detect packet losses without transport-layer handshakes (TCP ACK overhead), the protocol implements **sender-monotonic sequence validation**:

```
Transmitter (Node 1)                  Receiver (Node 2)
====================                  =================

Seq = 1 --------------------------->  Rx Seq = 1 [VALID, Loss = 0]
Seq = 2 --------------------------->  Rx Seq = 2 [VALID, Loss = 0]
Seq = 3 ------ (LOST IN DUST) ----->  (Not Received)
Seq = 4 --------------------------->  Rx Seq = 4 [VALID, Loss = 4 - 2 - 1 = 1]
Seq = 4 ------ (REPLAY ATTACK) ---->  Rx Seq = 4 [REJECTED: DUPLICATE]
Seq = 2 ------ (DELAYED MULTIPATH)->  Rx Seq = 2 [REJECTED: OUT-OF-ORDER]
```

---

## 2. Mathematical Definition

Let $S_{rx}$ be the sequence number of the incoming packet from sender $i$, and $S_{last}$ be the highest sequence number previously validated from sender $i$:

$$\Delta S = S_{rx} - S_{last}$$

- **Case 1: Contiguous Arrival ($\Delta S = 1$)**  
  Packet is valid and in-order. $S_{last} \leftarrow S_{rx}$.
- **Case 2: Forward Skip ($\Delta S > 1$)**  
  Packet is valid. Number of dropped frames added to loss counter:  
  $$N_{dropped} = \Delta S - 1$$  
  $S_{last} \leftarrow S_{rx}$.
- **Case 3: Duplicate or Replay ($\Delta S \le 0$)**  
  Packet is invalid. Discarded immediately to prevent replay attacks or processing outdated states.

---

## 3. Telemetry Integration

The calculated packet drop statistics (`packets_dropped`, `packets_received`) are streamed directly in the serial telemetry payload to the host DAAS-V2V machine learning model. The ML model utilizes this Packet Delivery Ratio (PDR) to accurately estimate channel congestion and calculate optimal transmission rates.
