/**
 * @file hmi.cpp
 * @brief Cockpit Human-Machine Interface Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "hmi.h"

CockpitHMI::CockpitHMI()
    : display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET_PIN),
      display_initialized(false),
      last_display_update_ms(0),
      last_buzzer_toggle_ms(0),
      buzzer_state(false) {
}

void CockpitHMI::begin() {
    pinMode(PIN_LED_DANGER, OUTPUT);
    pinMode(PIN_LED_SAFE, OUTPUT);
    pinMode(PIN_BUZZER, OUTPUT);

    digitalWrite(PIN_LED_DANGER, LOW);
    digitalWrite(PIN_LED_SAFE, HIGH); /* Initial OK state */
    digitalWrite(PIN_BUZZER, LOW);

    Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);
    if (display.begin(SSD1306_SWITCHCAPVCC, SCREEN_I2C_ADDRESS)) {
        display_initialized = true;
        display.clearDisplay();
        display.setTextColor(SSD1306_WHITE);
        display.setTextSize(1);
        display.setCursor(0, 10);
        display.println(F("  DAAS-V2V MINE"));
        display.setCursor(0, 25);
        display.println(F("  SYSTEM BOOT OK"));
        display.display();
        delay(500);
    }
}

void CockpitHMI::updateAudioVisuals(uint32_t current_time_ms, v2v_risk_level_t risk_level, bool is_fallback) {
    switch (risk_level) {
        case RISK_LEVEL_CRITICAL:
            /* Solid Danger LED, continuous high-priority audio buzzer */
            digitalWrite(PIN_LED_DANGER, HIGH);
            digitalWrite(PIN_LED_SAFE, LOW);
            digitalWrite(PIN_BUZZER, HIGH);
            break;

        case RISK_LEVEL_WARNING:
            /* Rapid flashing Danger LED (4 Hz) and pulsating buzzer */
            digitalWrite(PIN_LED_SAFE, LOW);
            if (current_time_ms - last_buzzer_toggle_ms >= 125) {
                buzzer_state = !buzzer_state;
                digitalWrite(PIN_BUZZER, buzzer_state ? HIGH : LOW);
                digitalWrite(PIN_LED_DANGER, buzzer_state ? HIGH : LOW);
                last_buzzer_toggle_ms = current_time_ms;
            }
            break;

        case RISK_LEVEL_CAUTION:
            /* Solid Green LED, brief warning chirp every 1 second */
            digitalWrite(PIN_LED_SAFE, HIGH);
            digitalWrite(PIN_LED_DANGER, LOW);
            if (current_time_ms - last_buzzer_toggle_ms >= 1000) {
                digitalWrite(PIN_BUZZER, HIGH);
                delayMicroseconds(30000); /* 30 ms audible chirp */
                digitalWrite(PIN_BUZZER, LOW);
                last_buzzer_toggle_ms = current_time_ms;
            }
            break;

        case RISK_LEVEL_SAFE:
        default:
            digitalWrite(PIN_LED_SAFE, HIGH);
            digitalWrite(PIN_LED_DANGER, LOW);
            digitalWrite(PIN_BUZZER, LOW);
            break;
    }

    if (is_fallback && risk_level < RISK_LEVEL_WARNING) {
        /* In fallback mode without immediate obstacle: slow amber/safe blink */
        if ((current_time_ms / 500) % 2 == 0) {
            digitalWrite(PIN_LED_SAFE, HIGH);
        } else {
            digitalWrite(PIN_LED_SAFE, LOW);
        }
    }
}

void CockpitHMI::updateDisplay(v2v_risk_level_t risk_level,
                              float distance_m,
                              float ttc_sec,
                              float speed_mps,
                              bool is_fallback,
                              bool hazard_latched,
                              uint32_t rx_packet_count) {
    if (!display_initialized) return;

    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);

    /* Header Bar */
    display.print(F("DAAS-V2V [ID:"));
    display.print(LOCAL_NODE_ID);
    display.println(F("]"));

    display.drawLine(0, 9, 127, 9, SSD1306_WHITE);

    /* Status Bar */
    display.setCursor(0, 13);
    display.print(F("STATUS: "));
    if (hazard_latched) {
        display.println(F("!EMERGENCY!"));
    } else {
        switch (risk_level) {
            case RISK_LEVEL_CRITICAL: display.println(F("!! CRITICAL !!")); break;
            case RISK_LEVEL_WARNING:  display.println(F("WARNING")); break;
            case RISK_LEVEL_CAUTION:  display.println(F("CAUTION")); break;
            case RISK_LEVEL_SAFE:     display.println(F("SAFE")); break;
        }
    }

    /* Kinematics Readout */
    display.setCursor(0, 26);
    display.print(F("DIST: "));
    if (distance_m >= 45.0f) {
        display.println(F("CLEAR (>40m)"));
    } else {
        display.print(distance_m, 1);
        display.println(F(" m"));
    }

    display.setCursor(0, 39);
    display.print(F("TTC:  "));
    if (ttc_sec >= 90.0f) {
        display.print(F("INF"));
    } else {
        display.print(ttc_sec, 1);
        display.print(F(" s"));
    }
    display.print(F(" SPD:"));
    display.print(speed_mps, 1);

    /* Link & Mode Footer */
    display.setCursor(0, 52);
    if (is_fallback) {
        display.print(F("MODE: AUTONOMOUS"));
    } else {
        display.print(F("V2V: OK (RX:"));
        display.print(rx_packet_count);
        display.print(F(")"));
    }

    display.display();
}

void CockpitHMI::update(uint32_t current_time_ms,
                       v2v_risk_level_t risk_level,
                       float distance_m,
                       float ttc_sec,
                       float speed_mps,
                       bool is_fallback,
                       bool hazard_latched,
                       uint32_t rx_packet_count) {
    updateAudioVisuals(current_time_ms, risk_level, is_fallback);

    if (current_time_ms - last_display_update_ms >= 100) {
        updateDisplay(risk_level, distance_m, ttc_sec, speed_mps, is_fallback, hazard_latched, rx_packet_count);
        last_display_update_ms = current_time_ms;
    }
}
