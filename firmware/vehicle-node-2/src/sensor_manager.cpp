/**
 * @file sensor_manager.cpp
 * @brief Perception & Sensor Management Subsystem Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "sensor_manager.h"

SensorManager::SensorManager()
    : window_idx(0),
      current_distance_m(50.0f),
      previous_distance_m(50.0f),
      last_ping_time_ms(0),
      last_calc_time_ms(0),
      estimated_speed_mps(0.0f),
      brake_pressed(false),
      sensor_fault(false) {
    for (int i = 0; i < 3; i++) {
        distance_window[i] = 50.0f;
    }
}

void SensorManager::begin() {
    pinMode(PIN_ULTRASONIC_TRIG, OUTPUT);
    pinMode(PIN_ULTRASONIC_ECHO, INPUT);
    pinMode(PIN_BRAKE_SWITCH, INPUT_PULLUP);

    digitalWrite(PIN_ULTRASONIC_TRIG, LOW);
}

float SensorManager::readUltrasonicRaw() {
    /* Trigger 10 microsecond ultrasonic ping */
    digitalWrite(PIN_ULTRASONIC_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_ULTRASONIC_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_ULTRASONIC_TRIG, LOW);

    /* Read return echo pulse with 30ms timeout (~5m max range) */
    unsigned long duration_us = pulseIn(PIN_ULTRASONIC_ECHO, HIGH, 30000);
    if (duration_us == 0) {
        /* No obstacle in 5m range or echo timeout */
        return 50.0f; /* Sentinel value representing open space */
    }

    /* Speed of sound in ambient air = 343 m/s = 0.0343 cm/us */
    float distance_cm = (duration_us * 0.0343f) / 2.0f;
    return distance_cm / 100.0f; /* Convert to meters */
}

float SensorManager::applyMedianFilter(float raw_m) {
    distance_window[window_idx] = raw_m;
    window_idx = (window_idx + 1) % 3;

    /* Sort temporary copy of window to find median */
    float sorted[3] = {distance_window[0], distance_window[1], distance_window[2]};
    for (int i = 0; i < 2; i++) {
        for (int j = i + 1; j < 3; j++) {
            if (sorted[i] > sorted[j]) {
                float tmp = sorted[i];
                sorted[i] = sorted[j];
                sorted[j] = tmp;
            }
        }
    }
    return sorted[1]; /* Middle value */
}

void SensorManager::update(uint32_t current_time_ms) {
    /* Read Brake Switch (Active LOW with internal pullup) */
    brake_pressed = (digitalRead(PIN_BRAKE_SWITCH) == LOW);

    /* Poll Ultrasonic Sensor at defined interval */
    if (current_time_ms - last_ping_time_ms >= SENSOR_POLL_INTERVAL_MS) {
        float raw = readUltrasonicRaw();
        current_distance_m = applyMedianFilter(raw);

        /* Velocity estimation from delta distance */
        if (last_calc_time_ms > 0) {
            float dt_sec = (current_time_ms - last_calc_time_ms) / 1000.0f;
            if (dt_sec > 0.01f && current_distance_m < 30.0f && previous_distance_m < 30.0f) {
                float delta_d = previous_distance_m - current_distance_m;
                estimated_speed_mps = delta_d / dt_sec;
                if (estimated_speed_mps < 0.0f) estimated_speed_mps = 0.0f;
            }
        }
        previous_distance_m = current_distance_m;
        last_calc_time_ms = current_time_ms;
        last_ping_time_ms = current_time_ms;
    }
}
