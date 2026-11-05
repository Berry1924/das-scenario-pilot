/**
 * @file sensor_manager.h
 * @brief Perception & Sensor Management Subsystem
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

#include <Arduino.h>
#include "../include/node_config.h"

class SensorManager {
public:
    SensorManager();
    void begin();
    void update(uint32_t current_time_ms);

    float getDistanceMeters() const { return current_distance_m; }
    float getSpeedMps() const { return estimated_speed_mps; }
    bool isBrakePressed() const { return brake_pressed; }
    bool isSensorFault() const { return sensor_fault; }

private:
    float readUltrasonicRaw();
    float applyMedianFilter(float raw_m);

    float distance_window[3];
    uint8_t window_idx;
    float current_distance_m;
    float previous_distance_m;
    uint32_t last_ping_time_ms;
    uint32_t last_calc_time_ms;
    float estimated_speed_mps;
    bool brake_pressed;
    bool sensor_fault;
};

#endif /* SENSOR_MANAGER_H */
