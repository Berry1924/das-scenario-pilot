/**
 * @file hmi.h
 * @brief Cockpit Human-Machine Interface (OLED, Audio Buzzer, Warning LEDs)
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef HMI_H
#define HMI_H

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "../include/node_config.h"
#include "../../common/protocol/v2v_packet.h"

class CockpitHMI {
public:
    CockpitHMI();
    void begin();
    void update(uint32_t current_time_ms,
                v2v_risk_level_t risk_level,
                float distance_m,
                float ttc_sec,
                float speed_mps,
                bool is_fallback,
                bool hazard_latched,
                uint32_t rx_packet_count);

private:
    void updateDisplay(v2v_risk_level_t risk_level,
                       float distance_m,
                       float ttc_sec,
                       float speed_mps,
                       bool is_fallback,
                       bool hazard_latched,
                       uint32_t rx_packet_count);
    void updateAudioVisuals(uint32_t current_time_ms, v2v_risk_level_t risk_level, bool is_fallback);

    Adafruit_SSD1306 display;
    bool display_initialized;
    uint32_t last_display_update_ms;
    uint32_t last_buzzer_toggle_ms;
    bool buzzer_state;
};

#endif /* HMI_H */
