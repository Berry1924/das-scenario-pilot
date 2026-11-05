/**
 * @file telemetry.h
 * @brief Host Serial Telemetry Streamer & Rate Adaptation Command Parser
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <Arduino.h>
#include "../include/node_config.h"
#include "../../common/telemetry/telemetry_types.h"

class TelemetryStreamer {
public:
    TelemetryStreamer();
    void begin(unsigned long baud_rate = 115200);

    void streamState(uint32_t current_time_ms,
                     const node_telemetry_state_t& state);

    bool checkRateAdaptationCommand(float* new_rate_hz);

private:
    uint32_t last_stream_time_ms;
};

#endif /* TELEMETRY_H */
