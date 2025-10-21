#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MindEase_BothPackect
------------------------------------------------------------
Python 3.9

Description:
    Reads EEG data over BLE (two channels: Left/Right ear) using bleak,
    parses short (raw EEG) and long (meditation/attention) packets, and
    writes synchronized microvolt values to a CSV-like text file.

Usage (recommended):
    1) Create & activate a virtual environment (Python 3.9)
       - Windows (PowerShell):
            py -3.9 -m venv .venv
            .\.venv\Scripts\Activate.ps1
       - macOS/Linux:
            python3.9 -m venv .venv
            source .venv/bin/activate

    2) Install dependencies:
            pip install -r requirements.txt

    3) (Optional) Update DEVICE_ADDRESS below with your device's BLE MAC.

    4) Run:
            python MindEase_BothPackect.py

Output:
    - Appends synchronized lines to "eeg_data.txt" with columns:
        Left Ear,Right Ear
      Values are microvolts (µV), formatted to 6 decimals.

Notes:
    - On Linux, ensure your user has BLE permissions (e.g., use `bluetoothctl`,
      or run with appropriate capabilities).
    - On Windows, BLE requires Bluetooth support enabled and drivers installed.
    - Program retries BLE connection automatically if it drops.

Author Contact:
    Email: hesamdc7613@gmail.com
    GitHub: Hesamdc
"""

import asyncio
import time
import queue
from bleak import BleakClient
import ctypes
from datetime import datetime 
import logging

# --- Minimal logging (info + connection errors) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEVICE_ADDRESS = "D4:F5:33:9A:E0:F6"

UUIDS = {
    "Left Ear": "6e400003-b5b0-f393-e0a9-e50e24dcca9f",
    "Right Ear": "6e400003-b5b1-f393-e0a9-e50e24dcca9f"
}

eeg_data_filename = "eeg_data.txt"


class BLEDevice:
    def __init__(self, address, uuids, data_queues, filename_prefix):
        self.address = address
        self.uuids = uuids
        self.packet_counts = {uuid: 0 for uuid in uuids.values()}
        self.total_packets = {uuid: 0 for uuid in uuids.values()}
        self.start_times = {uuid: time.time() for uuid in uuids.values()}
        self.first_second_skipped = {uuid: False for uuid in uuids.values()}
        self.buffers = {uuid: bytearray() for uuid in uuids.values()}
        self.data_queues = data_queues
        self.filename_prefix = filename_prefix
        self.uuid_to_name = {v: k for k, v in uuids.items()}

        # Store latest long-packet fields for each uuid
        self.med_att_values = {
            uuid: {"med": None, "att": None, "quality": None} for uuid in uuids.values()
        }

        # Meditation history for plotting (all history, per uuid)
        self.med_history = {uuid: {"t": [], "v": []} for uuid in uuids.values()}

    def process_short_packet(self, uuid, packet):
        if len(packet) < 8:
            logger.warning(f"Invalid short packet length: {len(packet)}")
            return
        hex_packet = ' '.join(f'{byte:02X}' for byte in packet)
        self.packet_counts[uuid] += 1
        self.total_packets[uuid] += 1
        # short_signal_quality extracted but not printed (kept intact)
        short_signal_quality = int(hex_packet[15:17], 16)
        high_byte = int(hex_packet[18:20], 16)
        low_byte = int(hex_packet[21:23], 16)
        raw_value = (high_byte << 8) | low_byte
        if raw_value >= 32768:
            raw_value -= 65536
        raw_value_microvolts = raw_value * (1.8 / 4096) / 2000 * 1000
        self.data_queues[uuid].put((time.time(), raw_value_microvolts))

    def process_long_packet(self, uuid, packet):
        """Update meditation/attention/quality; printing is deferred to once-per-second status line."""
        try:
            hex_packet = ' '.join(f'{byte:02X}' for byte in packet)
            meditation_hex = hex_packet[96:98]
            attention_hex = hex_packet[-5:-3]
            long_signal_quality_hex = hex_packet[12:14]

            meditation = int(meditation_hex, 16)
            attention = int(attention_hex, 16)
            long_signal_quality = int(long_signal_quality_hex, 16)

            self.med_att_values[uuid]["med"] = meditation
            self.med_att_values[uuid]["att"] = attention
            self.med_att_values[uuid]["quality"] = long_signal_quality

            # Append meditation to history for plotting
            now = time.time()
            self.med_history[uuid]["t"].append(now)
            self.med_history[uuid]["v"].append(meditation)

        except Exception as e:
            logger.error(f"Error processing long packet: {e}")

    def _format_status_line(self, uuid, sampling_rate):
        name = self.uuid_to_name[uuid]
        med = self.med_att_values[uuid]["med"]
        att = self.med_att_values[uuid]["att"]
        qual = self.med_att_values[uuid]["quality"]
        med_str = str(med) if med is not None else "N/A"
        att_str = str(att) if att is not None else "N/A"
        qual_str = str(qual) if qual is not None else "N/A"
        ts = time.strftime("%H:%M:%S", time.localtime())
        return f"{name:9} | {sampling_rate:.2f} Hz | SQ: {qual_str} | Med: {med_str} | Att: {att_str} | Time: {ts}"

    def calculate_signal_quality(self, uuid):
        """Called whenever notifications arrive; prints one clean line per ear per second."""
        current_time = time.time()
        elapsed_time = current_time - self.start_times[uuid]
        if elapsed_time >= 1.0:
            sampling_rate = self.packet_counts[uuid] / elapsed_time
            if self.first_second_skipped[uuid]:
                print(self._format_status_line(uuid, sampling_rate))
            else:
                self.first_second_skipped[uuid] = True
            self.packet_counts[uuid] = 0
            self.start_times[uuid] = current_time

    async def notification_handler(self, uuid, sender, data):
        self.buffers[uuid] += data
        while b'\xAA\xAA' in self.buffers[uuid]:
            start_index = self.buffers[uuid].find(b'\xAA\xAA')
            if len(self.buffers[uuid]) > start_index + 2:
                packet_type = self.buffers[uuid][start_index + 2]
                if packet_type == 0x04:
                    if len(self.buffers[uuid]) >= start_index + 8:
                        packet = self.buffers[uuid][start_index:start_index + 8]
                        self.process_short_packet(uuid, packet)
                        self.buffers[uuid] = self.buffers[uuid][start_index + 8:]
                    else:
                        break
                elif packet_type == 0x20:
                    if len(self.buffers[uuid]) >= start_index + 36:
                        packet = self.buffers[uuid][start_index:start_index + 36]
                        self.process_long_packet(uuid, packet)
                        self.buffers[uuid] = self.buffers[uuid][start_index + 36:]
                    else:
                        break
                else:
                    # Unknown type; advance one byte to resync
                    self.buffers[uuid] = self.buffers[uuid][start_index + 1:]
            else:
                break
        self.calculate_signal_quality(uuid)

    async def read_data_from_device(self):
        retry_attempts = 5
        while retry_attempts > 0:
            try:
                async with BleakClient(self.address) as client:
                    print(f"Connected to {self.address}")
                    for ear, uuid in self.uuids.items():
                        await client.start_notify(
                            uuid,
                            lambda s, d, u=uuid: asyncio.create_task(self.notification_handler(u, s, d))
                        )
                    while True:
                        await asyncio.sleep(1)
            except Exception as e:
                retry_attempts -= 1
                logger.error(f"Connection error: {e}. Retries left: {retry_attempts}")
                print(f"Retrying connection... ({retry_attempts} attempts left)")
                await asyncio.sleep(5)


async def save_data_to_file(data_queues, file_handle):
    left_ear_queue = data_queues["6e400003-b5b0-f393-e0a9-e50e24dcca9f"]
    right_ear_queue = data_queues["6e400003-b5b1-f393-e0a9-e50e24dcca9f"]
    buffer = []
    left_buffer = []
    right_buffer = []

    file_handle.write("Left Ear,Right Ear\n")
    file_handle.flush()

    while True:
        while not left_ear_queue.empty():
            left_buffer.append(left_ear_queue.get())
        while not right_ear_queue.empty():
            right_buffer.append(right_ear_queue.get())

        while left_buffer and right_buffer:
            left_data = left_buffer.pop(0)
            right_data = right_buffer.pop(0)
            buffer.append(f"{left_data[1]:.6f},{right_data[1]:.6f}\n")

            if len(buffer) >= 100:
                file_handle.writelines(buffer)
                buffer.clear()
                file_handle.flush()

        if buffer:
            file_handle.writelines(buffer)
            buffer.clear()
            file_handle.flush()

        await asyncio.sleep(0)


# -------- Live Meditation Plot (simple line, always-on-top, main thread) -------- #

async def plot_meditation_live(ble_device: BLEDevice):
    # Ensure GUI backend and import in main thread
    try:
        import matplotlib
        try:
            matplotlib.use("TkAgg", force=True)
        except Exception:
            pass
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[Plot] matplotlib not available ({e}). Skipping live plot.")
        # Keep this task alive without disrupting others
        while True:
            await asyncio.sleep(3600)

    plt.ion()
    fig, ax = plt.subplots()
    ax.set_title("Live Meditation")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Meditation (0-100)")
    ax.set_ylim(0, 100)

    lines = {}
    for ear_name, uuid in ble_device.uuids.items():
        (line,) = ax.plot([], [], label=ear_name)
        lines[uuid] = line
    ax.legend(loc="upper right")

    # Try to keep window always on top (best-effort)
    try:
        mng = plt.get_current_fig_manager()
        try:
            mng.window.attributes("-topmost", 1)  # TkAgg
        except Exception:
            try:
                mng.window.raise_()
                mng.window.activateWindow()
            except Exception:
                pass
    except Exception:
        pass

    # Show non-blocking
    try:
        plt.show(block=False)
    except Exception:
        pass

    t0 = time.time()

    while True:
        updated_any = False
        for uuid, line in lines.items():
            ts = ble_device.med_history[uuid]["t"]
            vs = ble_device.med_history[uuid]["v"]
            if ts:
                t_rel = [t - t0 for t in ts]
                line.set_data(t_rel, vs)
                updated_any = True

        if updated_any:
            ax.relim()
            # Autoscale X only; keep Y fixed [0,100]
            xmax = 10.0
            for uuid in lines:
                ts = ble_device.med_history[uuid]["t"]
                if ts:
                    xmax = max(xmax, ts[-1] - t0)
            ax.set_xlim(0, xmax)

            fig.canvas.draw_idle()
            fig.canvas.flush_events()

            # Keep on top (periodic nudge)
            try:
                fig.canvas.manager.window.attributes("-topmost", 1)
            except Exception:
                pass

        # Small pause so GUI stays responsive
        try:
            import matplotlib.pyplot as plt  # safe reimport
            plt.pause(0.05)
        except Exception:
            pass

        await asyncio.sleep(0.1)


# ------------------------------- Main Orchestration --------------------------- #

async def main():
    data_queues = {uuid: queue.Queue() for uuid in UUIDS.values()}
    ble_device = BLEDevice(DEVICE_ADDRESS, UUIDS, data_queues, "1")

    with open(eeg_data_filename, "a", newline='') as file_handle:
        try:
            await asyncio.gather(
                ble_device.read_data_from_device(),
                save_data_to_file(data_queues, file_handle),
                # Run plotting task in the main thread/event loop (no extra threads)
                plot_meditation_live(ble_device),
            )
        except KeyboardInterrupt:
            print("Shutting down, flushing remaining data...")
            raise


if __name__ == "__main__":
    try:
        ctypes.windll.ole32.CoInitializeEx(0, 0x0)
    except AttributeError:
        pass
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program stopped by user.")
