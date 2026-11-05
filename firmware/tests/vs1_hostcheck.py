#!/usr/bin/env python3
"""Host-side syntax/type check for VS1 firmware (no ESP32 core required).

Generates minimal stub headers mimicking the real Arduino/ESP-IDF 5.x API
shapes, maps include paths, and runs g++ -fsyntax-only. This is a BUILD
quality gate, not a behavioural test (behaviour is covered by the Python
simulation and, later, hardware bench runs).
"""

import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STUBS = {
    "Arduino.h": """#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
unsigned long millis();
unsigned long micros();
void pinMode(int, int);
void digitalWrite(int, int);
int digitalRead(int);
void tone(int, unsigned int);
void noTone(int);
void delay(unsigned long);
struct SerialClass {
    void begin(long);
    void print(const char*);
    void println(const char*);
    template<typename... A> void printf(const char*, A...) { }
};
extern SerialClass Serial;
#define INPUT_PULLUP 2
#define HIGH 1
#define LOW 0
#define OUTPUT 1
""",
    "esp_now.h": """#pragma once
#include <stdint.h>
#include <stddef.h>
typedef enum { ESP_NOW_SEND_SUCCESS = 0, ESP_NOW_SEND_FAIL } esp_now_send_status_t;
typedef enum { ESP_OK = 0 } esp_err_t;
typedef struct { uint8_t peer_addr[6]; uint8_t channel; bool encrypt; } esp_now_peer_info_t;
typedef struct { int8_t rssi; } wifi_pkt_rx_ctrl_t;
typedef struct { const wifi_pkt_rx_ctrl_t* rx_ctrl; } esp_now_recv_info_t;
typedef struct { int rssi; } wifi_tx_info_t;
typedef void (*esp_now_send_cb_t)(const wifi_tx_info_t*, esp_now_send_status_t);
typedef void (*esp_now_recv_cb_t)(const esp_now_recv_info_t*, const uint8_t*, int);
esp_err_t esp_now_init(void);
esp_err_t esp_now_register_send_cb(esp_now_send_cb_t);
esp_err_t esp_now_register_recv_cb(esp_now_recv_cb_t);
esp_err_t esp_now_add_peer(const esp_now_peer_info_t*);
esp_err_t esp_now_send(const uint8_t*, const uint8_t*, size_t);
""",
    "WiFi.h": """#pragma once
#include <stdint.h>
class String {
public:
    String(const char* s = "");
    const char* c_str() const;
};
class WiFiClass {
public:
    void mode(int);
    void disconnect();
    String macAddress();
    int channel();
};
extern WiFiClass WiFi;
#define WIFI_STA 1
#define WL_CONNECTED 3
""",
    "esp_wifi.h": """#pragma once
#include <stdint.h>
#define WIFI_SECOND_CHAN_NONE 0
typedef int wifi_second_chan_t;
void esp_wifi_set_promiscuous(bool);
void esp_wifi_set_channel(uint8_t, wifi_second_chan_t);
""",
    "esp_idf_version.h": """#pragma once
#define ESP_IDF_VERSION 5000000
#define ESP_IDF_VERSION_VAL(a,b,c) ((a)*1000000+(b)*1000+(c))
""",
}


def main() -> int:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        print("Error: no C++ compiler in PATH")
        return 1

    src_ino = os.path.join(REPO, "firmware", "vs1_ack_rtt", "vs1_ack_rtt.ino")
    if not os.path.isfile(src_ino):
        print(f"Error: {src_ino} not found")
        return 1

    with tempfile.TemporaryDirectory(prefix="vs1_stubs_") as tmp:
        for name, content in STUBS.items():
            with open(os.path.join(tmp, name), "w") as f:
                f.write(content)
        with open(src_ino) as f:
            text = f.read()
        # Map repo-relative includes to the common/ header dirs.
        text = text.replace(
            '#include "../../common/protocol/v2v_packet.h"',
            '#include "v2v_packet.h"')
        text = text.replace(
            '#include "../../common/validation/packet_validator.h"',
            '#include "packet_validator.h"')
        # Arduino builds auto-include Arduino.h before the sketch.
        text = "#include <Arduino.h>\n" + text
        check_cpp = os.path.join(tmp, "vs1_hostcheck.cpp")
        with open(check_cpp, "w") as f:
            f.write(text)

        cmd = [compiler, "-fsyntax-only", "-std=c++11", "-Wall", "-Wextra",
               f"-I{tmp}",
               f"-I{os.path.join(REPO, 'firmware', 'common', 'protocol')}",
               f"-I{os.path.join(REPO, 'firmware', 'common', 'validation')}",
               check_cpp]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print("[-] VS1 firmware host check FAILED:")
            print(proc.stderr)
            return 1
        warnings = [l for l in proc.stderr.splitlines() if "warning" in l]
        print("[+] VS1 firmware host check: PASS "
              f"({len(warnings)} warning(s))")
        for w in warnings:
            print("   ", w.strip())
        return 0


if __name__ == "__main__":
    sys.exit(main())
