#!/usr/bin/env python3
"""
Audio Streaming UDP — Cliente Windows (GUI PySide6)
Captura audio del sistema o micrófono y lo envía por UDP como PCM crudo.
"""

import socket
import sys
from queue import Queue, Empty

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

RATE = 48000
CHANNELS = 2
DTYPE = "int16"
BYTES_PER_FRAME = CHANNELS * 2

CHUNK_OPTIONS = {
    "256  (~5.3ms)": 256,
    "512  (~10.6ms)": 512,
    "1024 (~21.3ms)": 1024,
}


class AudioStreamThread(QThread):
    status_signal = Signal(str)
    packets_signal = Signal(int)

    def __init__(self, server_ip, port, device_idx, chunk_frames, parent=None):
        super().__init__(parent)
        self.server_ip = server_ip
        self.port = port
        self.device_idx = device_idx
        self.chunk_frames = chunk_frames
        self.chunk_bytes = chunk_frames * BYTES_PER_FRAME
        self._running = False

    def run(self):
        self._running = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        q = Queue()
        packet_count = 0

        def callback(indata, frames, time_info, status):
            if status:
                self.status_signal.emit(f"Status: {status}")
            q.put(indata.copy())

        try:
            stream = sd.InputStream(
                device=self.device_idx,
                samplerate=RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=self.chunk_frames,
                callback=callback,
                latency="low",
            )
            stream.start()
            self.status_signal.emit(f"Streaming a {self.server_ip}:{self.port}")

            buffer = np.empty((0, CHANNELS), dtype=np.int16)

            while self._running:
                try:
                    data = q.get(timeout=0.1)
                    buffer = np.concatenate((buffer, data))
                    while len(buffer) >= self.chunk_frames:
                        chunk = buffer[: self.chunk_frames]
                        buffer = buffer[self.chunk_frames :]
                        sock.sendto(chunk.tobytes(), (self.server_ip, self.port))
                        packet_count += 1
                        self.packets_signal.emit(packet_count)
                except Empty:
                    if len(buffer) > 0:
                        n = min(self.chunk_frames, len(buffer))
                        chunk = buffer[:n]
                        buffer = buffer[n:]
                        if n == self.chunk_frames:
                            sock.sendto(chunk.tobytes(), (self.server_ip, self.port))
                            packet_count += 1
                            self.packets_signal.emit(packet_count)

        except Exception as e:
            self.status_signal.emit(f"Error: {e}")
        finally:
            try:
                stream.stop()
            except Exception:
                pass
            sock.close()
            self.status_signal.emit("Detenido")

    def stop(self):
        self._running = False
        self.wait(2000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Stream UDP")
        self.setMinimumWidth(420)

        self.thread = None
        self._build_ui()
        self._populate_devices()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.X")
        form.addRow("Servidor IP:", self.ip_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(9999)
        form.addRow("Puerto:", self.port_input)

        self.device_combo = QComboBox()
        form.addRow("Dispositivo:", self.device_combo)

        self.chunk_combo = QComboBox()
        self.chunk_combo.addItems(CHUNK_OPTIONS.keys())
        self.chunk_combo.setCurrentText("512  (~10.6ms)")
        form.addRow("Chunk:", self.chunk_combo)

        layout.addLayout(form)

        self.toggle_btn = QPushButton("Iniciar stream")
        self.toggle_btn.setMinimumHeight(40)
        self.toggle_btn.clicked.connect(self._toggle_stream)
        layout.addWidget(self.toggle_btn)

        self.status_label = QLabel("Listo")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.packets_label = QLabel("Paquetes enviados: 0")
        self.packets_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.packets_label)

    def _populate_devices(self):
        self.device_combo.clear()
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev["maxInputChannels"] > 0:
                    api = sd.query_hostapis(dev["hostapi"])["name"]
                    ch = dev["maxInputChannels"]
                    lb = " [loopback]" if dev.get("is_loopback", False) else ""
                    label = f"{i}: {dev['name']} ({api}, {ch}ch){lb}"
                    self.device_combo.addItem(label, userData=i)
        except Exception as e:
            self.status_label.setText(f"Error listando dispositivos: {e}")

    def _toggle_stream(self):
        if self.thread is not None and self.thread.isRunning():
            self._stop_stream()
        else:
            self._start_stream()

    def _start_stream(self):
        ip = self.ip_input.text().strip()
        if not ip:
            self.status_label.setText("Ingresa una IP")
            return

        port = self.port_input.value()
        device_idx = self.device_combo.currentData()
        if device_idx is None:
            self.status_label.setText("Selecciona un dispositivo")
            return

        chunk_frames = CHUNK_OPTIONS[self.chunk_combo.currentText()]

        self.thread = AudioStreamThread(ip, port, device_idx, chunk_frames)
        self.thread.status_signal.connect(self.status_label.setText)
        self.thread.packets_signal.connect(
            lambda n: self.packets_label.setText(f"Paquetes enviados: {n}")
        )
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()

        self.toggle_btn.setText("Detener stream")
        self.toggle_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self._set_inputs_enabled(False)

    def _stop_stream(self):
        if self.thread:
            self.thread.stop()
            self.thread = None
        self.toggle_btn.setText("Iniciar stream")
        self.toggle_btn.setStyleSheet("")
        self._set_inputs_enabled(True)
        self.status_label.setText("Detenido")

    def _on_thread_finished(self):
        self.toggle_btn.setText("Iniciar stream")
        self.toggle_btn.setStyleSheet("")
        self._set_inputs_enabled(True)

    def _set_inputs_enabled(self, enabled):
        self.ip_input.setEnabled(enabled)
        self.port_input.setEnabled(enabled)
        self.device_combo.setEnabled(enabled)
        self.chunk_combo.setEnabled(enabled)

    def closeEvent(self, event):
        self._stop_stream()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
