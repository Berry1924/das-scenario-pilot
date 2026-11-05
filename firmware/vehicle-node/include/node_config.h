/**
 * @file node_config.h
 * @brief Vehicle Node 1 Hardware & Operational Configuration
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef NODE_CONFIG_H
#define NODE_CONFIG_H

#include <stdint.h>
#include "../../common/protocol/v2v_packet.h"

/* Node Identification */
#define LOCAL_NODE_ID            1
#define LOCAL_VEHICLE_TYPE       VEHICLE_TYPE_HAUL_DUMPER_100T
#define PEER_NODE_ID             2

/* ESP-NOW Wireless Configuration */
#define ESPNOW_WIFI_CHANNEL      1
/* Replace with actual MAC address of peer Node 2 */
static const uint8_t PEER_MAC_ADDRESS[6] = {0xC8, 0x2E, 0x18, 0xF4, 0x47, 0x78};

/* Hardware Pinout Assignments (per ADR-005) */
#define PIN_ULTRASONIC_TRIG      5
#define PIN_ULTRASONIC_ECHO      18
#define PIN_BRAKE_SWITCH         19  /* Active-low push button (Internal Pull-Up) */
#define PIN_LED_DANGER           4   /* Red Danger LED */
#define PIN_LED_SAFE             2   /* Green Safe LED (also ESP32 on-board LED) */
#define PIN_BUZZER               13  /* Active Piezo Buzzer */
#define PIN_OLED_SDA             21  /* I2C Data */
#define PIN_OLED_SCL             22  /* I2C Clock */

/* Display Configuration */
#define SCREEN_WIDTH             128
#define SCREEN_HEIGHT            64
#define OLED_RESET_PIN           -1
#define SCREEN_I2C_ADDRESS       0x3C

/* Timing & Safety Thresholds */
#define FALLBACK_TIMEOUT_MS          2500  /* Peer silence threshold to enter fallback */
#define HAZARD_LATCH_DURATION_MS     1500  /* Anti-flicker temporal holding duration */
#define SENSOR_POLL_INTERVAL_MS      50    /* Ultrasonic ping interval (20 Hz) */
#define TELEMETRY_STREAM_INTERVAL_MS 100   /* Serial telemetry streaming interval (10 Hz) */

/* Adaptive Beacon Transmission Bounds */
#define DEFAULT_TX_INTERVAL_MS       100   /* 10 Hz nominal */
#define MIN_TX_INTERVAL_MS           50    /* 20 Hz maximum rate */
#define MAX_TX_INTERVAL_MS           500   /* 2 Hz minimum rate under extreme congestion */

/* Risk Engine Thresholds (Meters and Seconds) */
#define THRESHOLD_DIST_CRITICAL_M    4.0f
#define THRESHOLD_DIST_WARNING_M     8.0f
#define THRESHOLD_DIST_CAUTION_M     15.0f

#define THRESHOLD_TTC_CRITICAL_S     1.5f
#define THRESHOLD_TTC_WARNING_S      3.0f
#define THRESHOLD_TTC_CAUTION_S      5.0f

#endif /* NODE_CONFIG_H */
