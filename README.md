# MindEase_BothPackect

Reads EEG data over Bluetooth Low Energy (BLE) from two channels (Left/Right ear) and writes synchronized microvolt values to a CSV-like text file.

- **Language:** Python 3.9  
- **Output:** `eeg_data.txt` (appends) with header `Left Ear,Right Ear`  
- **Contact:** hesamdc7613@gmail.com  
- **GitHub:** Hesamdc

---

## Features

- Connects to a BLE EEG device using `bleak`
- Parses short (raw EEG) and long (meditation/attention) packets
- Shows per-channel sampling rate and running totals
- Retries BLE connection on failure
- Streams synchronized Left/Right microvolt values to file

---

## Requirements

- Python **3.9**
- Bluetooth Low Energy hardware support
- OS BLE permissions (see Notes)

Install dependencies:

```bash
pip install -r requirements.txt
