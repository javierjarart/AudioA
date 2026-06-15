#!/usr/bin/env python3
"""
Audio Streaming UDP — Servidor Linux
Recibe PCM crudo (int16, 48kHz, estéreo) por UDP y lo reproduce.
"""

import argparse
import socket
import struct
import sys
import threading
from collections import deque

try:
    import pyaudio
except ImportError:
    sys.exit("ERROR: pyaudio no instalado. Ejecuta: pip install pyaudio")

FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 48000
CHUNK_FRAMES = 512
BUFFER_PKTS = 6
BYTES_PER_FRAME = CHANNELS * 2  # 4 bytes
CHUNK_BYTES = CHUNK_FRAMES * BYTES_PER_FRAME


def list_devices():
    p = pyaudio.PyAudio()
    print(f"{'Idx':<5} {'Name':<50} {'Channels':<10} {'Rate':<10}")
    print("-" * 80)
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxOutputChannels"] > 0:
            print(f"{i:<5} {info['name']:<50} {info['maxOutputChannels']:<10} {int(info['defaultSampleRate']):<10}")
    p.terminate()


def audio_callback(in_data, frame_count, time_info, status):
    return (None, pyaudio.paContinue)


def main():
    parser = argparse.ArgumentParser(description="Servidor de audio UDP (PCM)")
    parser.add_argument("--port", type=int, default=9999, help="Puerto UDP (default: 9999)")
    parser.add_argument("--device", type=int, default=None, help="Índice del dispositivo de salida")
    parser.add_argument("--list", action="store_true", help="Listar dispositivos de salida")
    parser.add_argument("--buffer", type=int, default=BUFFER_PKTS, help=f"Jitter buffer en paquetes (default: {BUFFER_PKTS})")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return

    buffer_pkts = max(2, args.buffer)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)

    p = pyaudio.PyAudio()

    device_index = args.device
    if device_index is None:
        device_index = p.get_default_output_device_info()["index"]

    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        output=True,
        output_device_index=device_index,
        frames_per_buffer=CHUNK_FRAMES,
    )

    jitter_buffer = deque()
    buffer_lock = threading.Lock()
    BUFFER_TARGET = buffer_pkts

    def fill_jitter():
        while True:
            try:
                data, addr = sock.recvfrom(65536)
                if len(data) == CHUNK_BYTES:
                    with buffer_lock:
                        jitter_buffer.append(data)
                        if len(jitter_buffer) > BUFFER_TARGET + 10:
                            jitter_buffer.popleft()
            except Exception:
                pass

    recv_thread = threading.Thread(target=fill_jitter, daemon=True)
    recv_thread.start()

    print(f"Servidor escuchando en 0.0.0.0:{args.port}")
    print(f"Buffer: {buffer_pkts} paquetes | Dispositivo: {device_index}")
    print("Esperando audio...")

    while True:
        with buffer_lock:
            if len(jitter_buffer) >= BUFFER_TARGET:
                data = jitter_buffer.popleft()
            else:
                data = b"\x00" * CHUNK_BYTES
        try:
            stream.write(data)
        except Exception as e:
            print(f"Error reproduciendo: {e}")

    stream.close()
    p.terminate()
    sock.close()


if __name__ == "__main__":
    main()
