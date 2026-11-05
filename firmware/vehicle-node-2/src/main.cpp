/**
 * @file main.cpp
 * @brief Vehicle Node 1 Main Entry Point & Subsystem Orchestration
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include <Arduino.h>
#include "../include/node_config.h"
#include "../../common/protocol/v2v_packet.h"
#include "../../common/safety/safety_isolation.h"
#include "../../common/telemetry/telemetry_types.h"
#include "sensor_manager.h"
#include "hazard_state.h"
#include "risk_engine.h"
#include "priority_engine.h"
#include "fallback_manager.h"
#include "hmi.h"
#include "v2v_protocol.h"
#include "telemetry.h"

/* Subsystem Instances */
static SensorManager     sensorMgr;
static HazardStateManager hazardMgr;
static RiskEngine        riskEng;
static PriorityEngine    priorityEng;
static FallbackManager   fallbackMgr;
static CockpitHMI        hmi;
static V2VProtocol       v2v;
static TelemetryStreamer telemetry;

/* Peer State Cache */
static uint16_t cached_peer_hazards = HAZARD_FLAG_NONE;
static float    cached_peer_distance = 50.0f;
static float    cached_peer_speed    = 0.0f;

void setup() {
    telemetry.begin(115200);
    hmi.begin();
    sensorMgr.begin();

    if (!v2v.begin()) {
        /* Failed to init ESP-NOW: fallback active */
    }
}

void loop() {
    uint32_t now = millis();

    /* 1. Update Sensors (Ultrasonic & Brake Switch) */
    sensorMgr.update(now);
    bool brake_active = sensorMgr.isBrakePressed();
    float local_dist  = sensorMgr.getDistanceMeters();
    float local_speed = sensorMgr.getSpeedMps();

    /* 2. Process Incoming Over-the-Air V2V Packets */
    if (v2v.hasNewPacket()) {
        v2v_packet_t rx = v2v.getLatestPacket();
        fallbackMgr.recordPeerHeartbeat(now);

        cached_peer_hazards  = rx.hazard_flags;
        cached_peer_distance = rx.distance_m;
        cached_peer_speed    = rx.speed_mps;

        if ((rx.hazard_flags & HAZARD_FLAG_BRAKE_ACTIVE) != 0) {
            hazardMgr.triggerHazard(HAZARD_FLAG_BRAKE_ACTIVE, now);
        }
    }

    /* 3. Update Fallback Watchdog & Hazard Temporal Decay */
    fallbackMgr.update(now);
    hazardMgr.update(now);

    /* 4. Evaluate Collision Risk Engine */
    /* If peer data is fresh, incorporate peer hazard flags */
    uint16_t combined_hazards = cached_peer_hazards | hazardMgr.getLatchedFlags();
    if (brake_active) {
        combined_hazards |= HAZARD_FLAG_BRAKE_ACTIVE;
    }

    /* Effective distance is local ultrasonic or peer cooperative distance */
    float effective_dist = local_dist;
    if (fallbackMgr.isFallbackActive() && effective_dist > 40.0f) {
        /* In fallback mode without direct obstacle, maintain autonomous caution */
    }

    riskEng.evaluate(effective_dist, local_speed, combined_hazards, brake_active);
    v2v_risk_level_t current_risk = riskEng.getRiskLevel();

    /* 5. Safety-Path Priority Dispatch & Transmission */
    bool is_emergency = (brake_active || riskEng.isImminentCollision() || hazardMgr.isHazardActive());
    if (priorityEng.shouldTransmit(now, is_emergency)) {
        v2v_priority_t prio = priorityEng.determinePacketPriority(brake_active, riskEng.isImminentCollision());
        
        uint16_t tx_flags = HAZARD_FLAG_NONE;
        if (brake_active) tx_flags |= HAZARD_FLAG_BRAKE_ACTIVE;
        if (riskEng.isImminentCollision()) tx_flags |= HAZARD_FLAG_IMMINENT_COLLISION;
        if (sensorMgr.isSensorFault()) tx_flags |= HAZARD_FLAG_SENSOR_FAULT;

        v2v.sendPacket(prio, tx_flags, local_dist, local_speed, 0.0f, now);
        priorityEng.recordTransmission(now);
    }

    /* 6. Update Cockpit HMI (OLED, Audio Buzzer, Warning LEDs) */
    hmi.update(now,
               current_risk,
               effective_dist,
               riskEng.getTTC(),
               local_speed,
               fallbackMgr.isFallbackActive(),
               hazardMgr.isHazardActive(),
               v2v.getPacketsReceived());

    /* 7. Check for Host Rate Adaptation Commands */
    float adapted_rate = 0.0f;
    if (telemetry.checkRateAdaptationCommand(&adapted_rate)) {
        priorityEng.adaptBeaconRate(adapted_rate);
    }

    /* 8. Stream Structured JSON Telemetry to Host Gateway */
    node_telemetry_state_t state;
    state.uptime_ms = now;
    state.node_id = LOCAL_NODE_ID;
    state.vehicle_type = LOCAL_VEHICLE_TYPE;
    state.brake_switch_active = brake_active;
    state.local_distance_m = local_dist;
    state.estimated_speed_mps = local_speed;
    state.packets_sent = v2v.getPacketsSent();
    state.packets_received = v2v.getPacketsReceived();
    state.packets_dropped = v2v.getPacketsDropped();
    state.crc_errors = v2v.getCrcErrors();
    state.last_peer_rssi = v2v.getLastRssi();
    state.last_peer_rx_timestamp = now - fallbackMgr.getSilenceDurationMs(now);
    state.active_risk_level = current_risk;
    state.calculated_ttc_sec = riskEng.getTTC();
    state.hazard_latch_active = hazardMgr.isHazardActive();
    state.fallback_mode_active = fallbackMgr.isFallbackActive();
    state.target_tx_rate_hz = 1000.0f / (float)priorityEng.getTxIntervalMs();
    state.current_tx_interval_ms = priorityEng.getTxIntervalMs();

    telemetry.streamState(now, state);

    delay(5); /* Yield to FreeRTOS scheduler */
}
