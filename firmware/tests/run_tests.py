#!/usr/bin/env python3
"""
Master Embedded Host Test Runner & CI Verification Script
Compiles and executes all native C++ firmware algorithm tests using g++ or clang++.
"""

import os
import sys
import subprocess
import shutil

TESTS = [
    ("Wire Protocol & CRC16", "firmware/tests/test_wire_protocol.cpp", "firmware/tests/test_wire_protocol.exe"),
    ("Sequence & Freshness", "firmware/tests/test_sequence_freshness.cpp", "firmware/tests/test_sequence_freshness.exe"),
    ("Risk Engine & TTC", "firmware/tests/test_risk_engine.cpp", "firmware/tests/test_risk_engine.exe"),
    ("Hazard Memory Decay", "firmware/tests/test_hazard_decay.cpp", "firmware/tests/test_hazard_decay.exe"),
    ("Safety-Path Isolation", "firmware/tests/test_safety_isolation.cpp", "firmware/tests/test_safety_isolation.exe"),
]

def main():
    print("=" * 65)
    print("  DAAS-V2V / SIH26007 FIRMWARE ALGORITHMIC TEST RUNNER")
    print("=" * 65)

    compiler = "g++" if shutil.which("g++") else "clang++"
    if not shutil.which(compiler):
        print(f"Error: Neither g++ nor clang++ was found in PATH.")
        sys.exit(1)

    print(f"Using C++ Compiler: {compiler}\n")
    all_passed = True
    results = []

    for name, src, exe in TESTS:
        print(f"[*] Building and running suite: {name} ({src})...")
        compile_cmd = [compiler, "-O2", "-Wall", "-std=c++11", src, "-o", exe]
        c_proc = subprocess.run(compile_cmd, capture_output=True, text=True)
        if c_proc.returncode != 0:
            print(f"[-] Compilation error for {src}:\n{c_proc.stderr}")
            results.append((name, "COMPILATION FAILED"))
            all_passed = False
            continue

        r_proc = subprocess.run([exe], capture_output=True, text=True)
        if r_proc.returncode == 0:
            print(r_proc.stdout.strip())
            results.append((name, "PASSED"))
        else:
            print(f"[-] Test execution failed with code {r_proc.returncode}:\n{r_proc.stderr}")
            results.append((name, "FAILED"))
            all_passed = False
        print("-" * 65)

    print("\n" + "=" * 65)
    print("  SUMMARY OF EMBEDDED ALGORITHM VERIFICATION")
    print("=" * 65)
    for name, status in results:
        flag = "[PASS]" if status == "PASSED" else "[FAIL]"
        print(f"  {flag:<8} {name:<35} : {status}")
    print("=" * 65)

    if not all_passed:
        print("[-] One or more firmware test suites failed.")
        sys.exit(1)

    print("[+] All firmware algorithm tests completed successfully!")
    sys.exit(0)

if __name__ == "__main__":
    main()
