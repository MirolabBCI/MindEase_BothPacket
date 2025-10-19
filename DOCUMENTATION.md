# MindEase_BothPackect — Detailed Code Documentation

**Author:** hesamdc7613@gmail.com  
**Language:** Python 3.9  

---

## Overview

`MindEase_BothPackect.py` is a Python script that connects to a Bluetooth Low Energy (BLE) EEG device, reads EEG packets from both ears, processes them, and logs synchronized microvolt values to a file (`eeg_data.txt`).

It uses the **`bleak`** library for BLE communication and **asyncio** for parallel asynchronous data streaming and saving.

---

## ⚙️ System Architecture

The program is composed of four main parts:

1. **BLEDevice Class**  
   Handles BLE connection, packet reception, decoding, and signal quality estimation.

2. **Notification Handler**  
   Receives continuous byte streams from the BLE device and splits them into valid EEG packets.

3. **Data Saver**  
   Collects samples from asynchronous queues and writes them into a synchronized text file.

4. **Main Event Loop**  
   Runs two asynchronous tasks concurrently:
   - `ble_device.read_data_from_device()`
   - `save_data_to_file()`

---

## 📡 Bluetooth Data Flow

BLE EEG Device → BleakClient → Notification Handler → Data Queue → File Writer

The data packets are sent by the device as **short** and **long** frames:

| Type         | Bytes    | Content                          | Purpose                             |
|--------------|----------|----------------------------------|-------------------------------------|
| Short Packet | 8 bytes  | Raw EEG                          | Continuous EEG signal data          |
| Long Packet  | 36 bytes | Meditation / Attention + Quality | Periodic signal quality and metrics |

---

## Code Components

### 1. `BLEDevice` Class

**Purpose:** Manage BLE connection, data parsing, and performance metrics.

**Attributes:**
- `address`: Device MAC address
- `uuids`: BLE service UUIDs for Left/Right ear
- `buffers`: Temporary bytearrays to store incoming partial packets
- `data_queues`: Queues to store parsed EEG samples
- `packet_counts`: Track per-second packets
- `total_packets`: Track total packets since start

**Key Methods:**
- `process_short_packet()`: Converts 8-byte EEG data into microvolts  
- `process_long_packet()`: Extracts signal quality, meditation, and attention values  
- `calculate_signal_quality()`: Monitors real-time packet rate per channel  
- `notification_handler()`: Manages incoming BLE data stream, detects and splits packets  
- `read_data_from_device()`: Manages BLE connection lifecycle, including retries

---

### 2. `process_short_packet(uuid, packet)`

**Input:** 8-byte EEG packet  
**Output:** Raw EEG microvolt value  

**Steps:**
1. Converts bytes to hex string  
2. Extracts high and low bytes  
3. Combines into signed 16-bit integer  
4. Converts to microvolts using hardware gain constants  
5. Pushes timestamped EEG value into the data queue  

---

### 3. `process_long_packet(uuid, packet)`

**Input:** 36-byte packet  
**Output:** Signal quality + meditation + attention metrics  

This function prints signal quality information and can be expanded to log meditation/attention data if desired.

---

### 4. `notification_handler(uuid, sender, data)`

Handles live BLE stream data:
- Buffers raw bytes
- Detects packet boundaries (`0xAA 0xAA`)
- Distinguishes short (0x04) and long (0x20) packets
- Dispatches to corresponding handlers
- Resets buffer after processing

---

### 5. `save_data_to_file(data_queues, file_handle)`

**Purpose:** Writes synchronized Left/Right microvolt values to disk.

**Mechanism:**
- Continuously pulls values from both Left and Right ear queues
- Writes pairs into `eeg_data.txt` as:
Left Ear,Right Ear
12.345678,11.234567
- Flushes every 512 samples or 1 second

---

### 6. `main()`

Sets up the entire system:
1. Creates queues for both channels  
2. Instantiates a `BLEDevice`  
3. Starts both coroutines concurrently via `asyncio.gather()`  
4. Gracefully handles shutdown and flushes remaining data

---

## Data Conversion Details

**Raw ADC → Microvolts conversion formula:**
µV = raw × (1.8 / 4096) × (1 / 2000) × 1000

- 1.8 V reference voltage  
- 12-bit ADC (4096 levels)  
- 2000 amplifier gain  
- Conversion to microvolts for readability

---

## Logging & Monitoring

- Sampling rate per channel is displayed every second  
- Connection events and errors logged via `logging`  
- File writes confirmed via line count messages  

Example console output:
Connected to D4:F5:33:9A:E0:F6
Left Ear 512.00 Hz (Total: 1024)
Right Ear 510.00 Hz (Total: 1020)
Written 300 lines

---

## Error Handling & Recovery

- Up to **5 retry attempts** if BLE connection fails  
- Waits 5 seconds between reconnect attempts  
- Uses `asyncio.WindowsSelectorEventLoopPolicy()` for Windows BLE compatibility  
- `KeyboardInterrupt` gracefully flushes data and stops safely

---

## 🪄 Flow Summary

┌─────────────────────────────┐
│ Start Program│
├─────────────────────────────┤
│ Initialize Queues│
│ Create BLEDevice instance│ 
├─────────────────────────────┤
│ Connect via BleakClient│
│ Subscribe to Notifications│
├─────────────────────────────┤
│ Receive EEG Packets│
│ Parse → Convert → Queue│
├─────────────────────────────┤
│ Async Task 1: BLE Receiver│
│ Async Task 2: File Writer│
├─────────────────────────────┤
│ Sync Left & Right Channels│
│ Write to eeg_data.txt│
├─────────────────────────────┤
│ KeyboardInterrupt → Flush│
│ Close File & Exit│
└─────────────────────────────┘

---

## Troubleshooting

| Problem            | Possible Cause              | Fix                            |
|--------------------|-----------------------------|--------------------------------|
| `Connection error` | Device out of range or busy | Move closer or restart device  |
| No packets         | Wrong UUID or address       | Update `DEVICE_ADDRESS`        |
| Permission denied  | BLE access blocked          | Run with admin/sudo            |
| Slow rate          | Interference or weak signal | Retry connection               |
| File empty         | Both queues empty           | Verify both channels connected |

---

## Summary

This script provides a robust base for:
- EEG BLE data capture  
- Live signal processing  
- Synchronized multi-channel logging  

It’s modular, extensible, and ready for research or integration with machine learning pipelines.

---

**Author Contact:**  
hesamdc7613@gmail.com  
GitHub: `Hesamdc`
