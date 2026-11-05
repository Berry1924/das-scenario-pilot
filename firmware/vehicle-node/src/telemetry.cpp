/**
 * @file telemetry.cpp
 * @brief Host Serial Telemetry Streamer & Rate Adaptation Command Parser Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "telemetry.h"

TelemetryStreamer::TelemetryStreamer()
    : last_stream_time_ms(0) {
}

void TelemetryStreamer::begin(unsigned long baud_rate) {
    Serial.begin(baud_rate);
}

void TelemetryStreamer::streamState(uint32_t current_time_ms,
                                   const node_telemetry_state_t& state) {
    if (current_time_ms - last_stream_time_ms < TELEMETRY_STREAM_INTERVAL_MS) {
        return;
    }
    last_stream_time_ms = current_time_ms;

    /* Emit structured JSON telemetry line for host ML / gateway */
    Serial.print(F("{\"uptime\":"));
    Serial.print(state.uptime_ms);
    Serial.print(F(",\"node\":"));
    Serial.print(state.node_id);
    Serial.print(F(",\"type\":"));
    Serial.print(state.vehicle_type);
    Serial.print(F(",\"dist\":"));
    Serial.print(state.local_distance_m, 2);
    Serial.print(F(",\"spd\":"));
    Serial.print(state.estimated_speed_mps, 2);
    Serial.print(F(",\"brake\":"));
    Serial.print(state.brake_switch_active ? 1 : 0);
    Serial.print(F(",\"risk\":"));
    Serial.print((int)state.active_risk_level);
    Serial.print(F(",\"ttc\":"));
    Serial.print(state.calculated_ttc_sec, 2);
    Serial.print(F(",\"latch\":"));
    Serial.print(state.hazard_latch_active ? 1 : 0);
    Serial.print(F(",\"fallback\":"));
    Serial.print(state.fallback_mode_active ? 1 : 0);
    Serial.print(F(",\"tx_cnt\":"));
    Serial.print(state.packets_sent);
    Serial.print(F(",\"rx_cnt\":"));
    Serial.print(state.packets_received);
    Serial.print(F(",\"drop_cnt\":"));
    Serial.print(state.packets_dropped);
    Serial.print(F(",\"crc_err\":"));
    Serial.print(state.crc_errors);
    Serial.print(F(",\"rssi\":"));
    Serial.print(state.last_peer_rssi);
    Serial.print(F(",\"tx_rate_hz\":"));
    Serial.print(state.target_tx_rate_hz, 1);
    Serial.println(F("}"));
}

bool TelemetryStreamer::checkRateAdaptationCommand(float* new_rate_hz) {
    if (!Serial.available()) return false;

    String line = Serial.readStringUntil('\n');
    line.trim();

    /* Look for simple rate adaptation command: {"rate": 15.0} or RATE=15.0 */
    int idx = line.indexOf("rate");
    if (idx != -1) {
        int colon = line.indexOf(':', idx);
        if (colon != -1) {
            float val = line.substring(colon + 1).toFloat();
            if (val >= 2.0f && val <= 20.0f) {
                if (new_rate_hz) *new_rate_hz = val;
                return true;
            }
        }
    }
    return false;
}
