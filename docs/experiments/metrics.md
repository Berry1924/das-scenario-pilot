# Evaluation Metrics & Quantitative Formulations

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Safety System  
**Document Type:** Metric Definitions & Experimental Mathematics  

---

## 1. Network Performance Metrics

### 1.1 Packet Delivery Ratio (PDR)
The percentage of successfully received wire packets relative to total packets transmitted by the sender:

$$\text{PDR} = \left( \frac{N_{received}}{N_{transmitted}} \right) \times 100\%$$

In congested VANET simulations, Baseline B exhibits PDR $\approx 52.4\%$, whereas the DAAS adaptive rate controller maintains PDR $> 89.6\%$.

### 1.2 Channel Busy Ratio (CBR)
The fraction of time during which the wireless channel is sensed as busy (signal above carrier-sense threshold $-85\text{ dBm}$):

$$\text{CBR} = \frac{T_{busy}}{T_{observation}}$$

Target operational CBR is kept below $0.65$ to prevent exponential CSMA/CA back-off collapse.

---

## 2. Safety & Timing Metrics

### 2.1 Emergency Alert Latency ($T_{alert}$)
The elapsed time from the mechanical closure of the lead vehicle's emergency brake switch until the following vehicle's cockpit HMI buzzer activates:

$$T_{alert} = t_{sensor} + t_{arbitration} + t_{phy\_tx} + t_{propagation} + t_{phy\_rx} + t_{validation} + t_{actuation}$$

Bench test measurements confirm $T_{alert} \le 6.0\text{ ms}$.

### 2.2 Time-to-Collision (TTC)
The projected time remaining before geometric contact occurs at closing speed $v_{rel}$:

$$\text{TTC} = \frac{d}{v_{rel}} = \frac{d_{front} - d_{rear}}{v_{follower} - v_{leader}}$$

### 2.3 Hazard Latch Holding Duration
The time interval $\Delta T_{hold} = 1500\text{ ms}$ over which an active emergency alert is held in RAM after the physical trigger event ceases, preventing visual warning flicker during RF packet dropouts.
