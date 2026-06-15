#!/usr/bin/env python3
"""
AudioA — Audio Streaming UDP (PCM)
App unificada: funciona como servidor (recibe y reproduce) o cliente (captura y envía).
"""

import socket
import sys
from collections import deque
from queue import Queue, Empty

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
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


class ServerThread(QThread):
    status_signal = Signal(str)

    def __init__(self, port, device_idx, buffer_pkts, parent=None):
        super().__init__(parent)
        self.port = port
        self.device_idx = device_idx
        self.buffer_pkts = max(2, buffer_pkts)
        self._running = False

    def run(self):
        self._running = True
        chunk_frames = 512
        chunk_bytes = chunk_frames * BYTES_PER_FRAME

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.port))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)
        sock.settimeout(1.0)

        jitter = deque()
        BUFFER_TARGET = self.buffer_pkts

        try:
            stream = sd.OutputStream(
                device=self.device_idx,
                samplerate=RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=chunk_frames,
                latency="low",
            )
            stream.start()
            self.status_signal.emit(
                f"Servidor escuchando en puerto {self.port} — buffer {BUFFER_TARGET} pkts"
            )

            while self._running:
                try:
                    data, addr = sock.recvfrom(65536)
                    if len(data) == chunk_bytes:
                        jitter.append(data)
                        if len(jitter) > BUFFER_TARGET + 10:
                            jitter.popleft()
                except socket.timeout:
                    pass

                if len(jitter) >= BUFFER_TARGET:
                    frame_data = jitter.popleft()
                else:
                    frame_data = b"\x00" * chunk_bytes

                try:
                    stream.write(np.frombuffer(frame_data, dtype=np.int16).reshape(-1, CHANNELS))
                except Exception:
                    pass

        except Exception as e:
            self.status_signal.emit(f"Error: {e}")
        finally:
            try:
                stream.stop()
            except Exception:
                pass
            sock.close()
            self.status_signal.emit("Servidor detenido")

    def stop(self):
        self._running = False
        self.wait(3000)


class ClientThread(QThread):
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
            self.status_signal.emit(f"Enviando a {self.server_ip}:{self.port}")

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


class AudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AudioA")
        self.setMinimumWidth(440)
        self.setMinimumHeight(320)

        try:
            self.setWindowIcon(QIcon("resources/icon.png"))
        except Exception:
            pass

        self.thread = None
        self._build_ui()
        self._populate_devices()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        # mode selector
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(4)
        self.mode_label = QLabel("Modo:")
        self.server_radio = QRadioButton("Servidor")
        self.client_radio = QRadioButton("Cliente")
        self.server_radio.setChecked(True)
        self.server_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.server_radio)
        mode_layout.addWidget(self.client_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # stacked panels
        self.stack = QStackedWidget()

        # server panel
        self.server_panel = QWidget()
        s_layout = QVBoxLayout(self.server_panel)

        s_form = QFormLayout()
        self.s_port = QSpinBox()
        self.s_port.setRange(1024, 65535)
        self.s_port.setValue(9999)
        s_form.addRow("Puerto:", self.s_port)

        self.s_device = QComboBox()
        s_form.addRow("Dispositivo salida:", self.s_device)

        self.s_buffer = QSpinBox()
        self.s_buffer.setRange(2, 15)
        self.s_buffer.setValue(6)
        self.s_buffer.setPrefix("")
        s_form.addRow("Jitter buffer (pkts):", self.s_buffer)

        s_layout.addLayout(s_form)
        s_layout.addStretch()
        self.stack.addWidget(self.server_panel)

        # client panel
        self.client_panel = QWidget()
        c_layout = QVBoxLayout(self.client_panel)

        c_form = QFormLayout()
        self.c_ip = QLineEdit()
        self.c_ip.setPlaceholderText("192.168.1.X")
        c_form.addRow("Servidor IP:", self.c_ip)

        self.c_port = QSpinBox()
        self.c_port.setRange(1024, 65535)
        self.c_port.setValue(9999)
        c_form.addRow("Puerto:", self.c_port)

        self.c_device = QComboBox()
        c_form.addRow("Dispositivo entrada:", self.c_device)

        self.c_chunk = QComboBox()
        self.c_chunk.addItems(CHUNK_OPTIONS.keys())
        self.c_chunk.setCurrentText("512  (~10.6ms)")
        c_form.addRow("Chunk:", self.c_chunk)

        c_layout.addLayout(c_form)
        c_layout.addStretch()
        self.stack.addWidget(self.client_panel)

        layout.addWidget(self.stack)

        # toggle button
        self.toggle_btn = QPushButton("Iniciar")
        self.toggle_btn.setMinimumHeight(40)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        # status
        self.status_label = QLabel("Listo")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.packets_label = QLabel("")
        self.packets_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.packets_label)

    def _populate_devices(self):
        self.s_device.clear()
        self.c_device.clear()
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                api = sd.query_hostapis(dev["hostapi"])["name"]
                lb = " [loopback]" if dev.get("is_loopback", False) else ""

                if dev["maxOutputChannels"] > 0:
                    label = f"{i}: {dev['name']} ({api}, {dev['maxOutputChannels']}ch){lb}"
                    self.s_device.addItem(label, userData=i)

                if dev["maxInputChannels"] > 0:
                    label = f"{i}: {dev['name']} ({api}, {dev['maxInputChannels']}ch){lb}"
                    self.c_device.addItem(label, userData=i)
        except Exception as e:
            self.status_label.setText(f"Error listando dispositivos: {e}")

    def _on_mode_changed(self):
        if self.thread and self.thread.isRunning():
            self._stop()
        self.stack.setCurrentIndex(0 if self.server_radio.isChecked() else 1)
        self.packets_label.setText("")
        self.status_label.setText("Listo")

    def _toggle(self):
        if self.thread and self.thread.isRunning():
            self._stop()
        else:
            self._start()

    def _start(self):
        if self.server_radio.isChecked():
            self._start_server()
        else:
            self._start_client()

    def _start_server(self):
        port = self.s_port.value()
        device_idx = self.s_device.currentData()
        if device_idx is None:
            self.status_label.setText("Selecciona un dispositivo de salida")
            return
        buffer_pkts = self.s_buffer.value()

        self.thread = ServerThread(port, device_idx, buffer_pkts)
        self.thread.status_signal.connect(self.status_label.setText)
        self.thread.finished.connect(self._on_finished)
        self.thread.start()

        self.toggle_btn.setText("Detener")
        self.toggle_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self._set_inputs_enabled(False)

    def _start_client(self):
        ip = self.c_ip.text().strip()
        if not ip:
            self.status_label.setText("Ingresa una IP")
            return
        port = self.c_port.value()
        device_idx = self.c_device.currentData()
        if device_idx is None:
            self.status_label.setText("Selecciona un dispositivo de entrada")
            return
        chunk_frames = CHUNK_OPTIONS[self.c_chunk.currentText()]

        self.thread = ClientThread(ip, port, device_idx, chunk_frames)
        self.thread.status_signal.connect(self.status_label.setText)
        self.thread.packets_signal.connect(
            lambda n: self.packets_label.setText(f"Paquetes enviados: {n}")
        )
        self.thread.finished.connect(self._on_finished)
        self.thread.start()

        self.toggle_btn.setText("Detener")
        self.toggle_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self._set_inputs_enabled(False)

    def _stop(self):
        if self.thread:
            self.thread.stop()
            self.thread = None
        self._reset_ui()

    def _on_finished(self):
        self._reset_ui()

    def _reset_ui(self):
        self.toggle_btn.setText("Iniciar")
        self.toggle_btn.setStyleSheet("")
        self._set_inputs_enabled(True)

    def _set_inputs_enabled(self, enabled):
        self.server_radio.setEnabled(enabled)
        self.client_radio.setEnabled(enabled)
        self.s_port.setEnabled(enabled)
        self.s_device.setEnabled(enabled)
        self.s_buffer.setEnabled(enabled)
        self.c_ip.setEnabled(enabled)
        self.c_port.setEnabled(enabled)
        self.c_device.setEnabled(enabled)
        self.c_chunk.setEnabled(enabled)

    def closeEvent(self, event):
        self._stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioApp()
    window.show()
    sys.exit(app.exec())
