# Edge Decision Layer & Risk Classification Engine

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Document Type:** Algorithmic & Mathematical Specification  

---

## 1. Algorithmic Overview

The Edge Decision Layer runs locally on each vehicle's microcontroller to assess collision risks in real time. It fuses local proximity sensing with cooperative V2V hazard telemetry to classify operational safety into four distinct states:
1. `RISK_LEVEL_SAFE` (Green)
2. `RISK_LEVEL_CAUTION` (Yellow)
3. `RISK_LEVEL_WARNING` (Orange)
4. `RISK_LEVEL_CRITICAL` (Red)

```
+-----------------------------------------------------------------------------------+
|                        EDGE COLLISION RISK PIPELINE                               |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Local Sensor Distance d_local ]        [ Peer V2V Distance d_peer ]            |
|  [ Forward Velocity v_rel        ]        [ Peer Hazard Flags (Brake Active) ]    |
|                 \                                      /                          |
|                  \                                    /                           |
|                   v                                  v                            |
|             +----------------------------------------------+                      |
|             |          SENSOR SANITY & FUSION GATE         |                      |
|             |  - Rejects out-of-bounds readings            |                      |
|             |  - Prioritizes closer obstacle measurement   |                      |
|             +----------------------------------------------+                      |
|                                    |                                              |
|                                    v                                              |
|             +----------------------------------------------+                      |
|             |        TIME-TO-COLLISION (TTC) CALCULATOR    |                      |
|             |              TTC = d / v_rel                 |                      |
|             +----------------------------------------------+                      |
|                                    |                                              |
|                                    v                                              |
|             +----------------------------------------------+                      |
|             |         MULTI-CRITERIA RISK ARBITRATOR       |                      |
|             |  Condition 1: Peer Brake Active? -> CRITICAL |                      |
|             |  Condition 2: TTC < 1.5s OR d < 4m -> CRITICAL                      |
|             |  Condition 3: TTC < 3.0s OR d < 8m -> WARNING|                      |
|             |  Condition 4: TTC < 5.0s OR d < 15m ->CAUTION|                      |
|             |  Condition 5: Otherwise -> SAFE              |                      |
|             +----------------------------------------------+                      |
|                                    |                                              |
|                                    v                                              |
|             +----------------------------------------------+                      |
|             |      TEMPORAL HAZARD HOLDING REGISTER        |                      |
|             |  - Latches active hazard for 1500 ms         |                      |
|             |  - Eliminates rapid strobe / warning flicker |                      |
|             +----------------------------------------------+                      |
|                                    |                                              |
|                                    v                                              |
|                    [ COCKPIT HMI WARNING DISPATCH ]                               |
+-----------------------------------------------------------------------------------+
```

---

## 2. Mathematical Formulations

### 2.1 Time-to-Collision (TTC)
Let $d$ be the measured distance to the preceding vehicle in meters, and $v_{rel}$ be the closing relative velocity in meters per second ($v_{rel} > 0$ when distance is decreasing):

$$\text{TTC} = \begin{cases} 
\frac{d}{v_{rel}} & \text{if } v_{rel} > 0.1\text{ m/s} \\ 
99.9\text{ s (Safe/Diverging)} & \text{if } v_{rel} \le 0.1\text{ m/s} 
\end{cases}$$

If $d \le 0$, $\text{TTC} = 0.0\text{ s}$ (physical impact detected).

### 2.2 Proximity Stopping Margin
In heavy mining machinery, safe stopping distance $S_{stop}$ on an unpaved haul road with grade $\theta$ and tire-ground friction coefficient $\mu \approx 0.35$ is given by:

$$S_{stop} = v \cdot t_{reaction} + \frac{v^2}{2g(\mu \pm \sin\theta)}$$

For a 100T dumper moving at $30\text{ km/h}$ ($8.33\text{ m/s}$) downhill on a $1:12$ ($4.76^\circ$) grade with driver reaction time $t_{reaction} = 1.5\text{ s}$:
$$S_{stop} = (8.33 \times 1.5) + \frac{(8.33)^2}{2 \times 9.81 \times (0.35 - 0.083)} \approx 12.5\text{ m} + 13.2\text{ m} \approx 25.7\text{ meters}$$

This physical calculation dictates why proactive cooperative V2V warning (up to 50+ meters) is non-negotiable in open-cast mines: local short-range sensors alone cannot provide adequate reaction margins for ultra-class dumpers.
