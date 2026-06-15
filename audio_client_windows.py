#!/usr/bin/env python3
"""
Audio Streaming UDP — Cliente Windows
Captura audio del sistema (loopback) o micrófono y lo envía por UDP como PCM crudo.
Usa sounddevice (WASAPI) para captura loopback.
"""

import argparse
import socket
import sys
import time
from queue import Queue, Empty

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    sys.exit("ERROR: sounddevice no instalado. Ejecuta: pip install sounddevice")

RATE = 48000
CHANNELS = 2
DTYPE = "int16"
CHUNK_FRAMES = 512
BYTES_PER_FRAME = CHANNELS * 2
CHUNK_BYTES = CHUNK_FRAMES * BYTES_PER_FRAME


def list_devices():
    print(f"{'Idx':<6} {'Name':<55} {'API':<20} {'Ch':<5} {'Loopback':<9}")
    print("-" * 100)
    for i, dev in enumerate(sd.query_devices()):
        api = sd.query_hostapis(dev["hostapi"])["name"]
        is_loopback = "Sí" if dev.get("is_loopback", False) else "No"
        if dev["maxInputChannels"] > 0:
            print(f"{i:<6} {dev['name']:<55} {api:<20} {dev['maxInputChannels']:<5} {is_loopback:<9}")


def main():
    parser = argparse.ArgumentParser(description="Cliente de audio UDP para Windows")
    parser.add_argument("--server", required=True, help="IP del servidor")
    parser.add_argument("--port", type=int, default=9999, help="Puerto UDP (default: 9999)")
    parser.add_argument("--device", type=int, default=None, help="Índice del dispositivo de entrada")
    parser.add_argument("--chunk", type=int, default=CHUNK_FRAMES, help=f"Frames por paquete (default: {CHUNK_FRAMES})")
    parser.add_argument("--list", action="store_true", help="Listar dispositivos de entrada")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return

    chunk_frames = max(64, args.chunk)
    chunk_bytes = chunk_frames * BYTES_PER_FRAME

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    q = Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"Status: {status}")
        q.put(indata.copy())

    try:
        stream = sd.InputStream(
            device=args.device,
            samplerate=RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=chunk_frames,
            callback=callback,
            latency="low",
        )

        stream.start()
        print(f"Enviando audio a {args.server}:{args.port}")
        print(f"Chunk: {chunk_frames} frames ({chunk_frames * 1000 / RATE:.1f}ms)")
        print("Presiona Ctrl+C para detener.")

        buffer = np.empty((0, CHANNELS), dtype=np.int16)

        while True:
            try:
                data = q.get(timeout=0.1)
                buffer = np.concatenate((buffer, data))
                while len(buffer) >= chunk_frames:
                    chunk = buffer[:chunk_frames]
                    buffer = buffer[chunk_frames:]
                    sock.sendto(chunk.tobytes(), (args.server, args.port))
            except Empty:
                if len(buffer) > 0:
                    chunk = buffer[: min(chunk_frames, len(buffer))]
                    buffer = buffer[len(chunk) :]
                    if len(chunk) == chunk_frames:
                        sock.sendto(chunk.tobytes(), (args.server, args.port))

    except KeyboardInterrupt:
        print("\nDetenido.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            stream.stop()
        except Exception:
            pass
        sock.close()


if __name__ == "__main__":
    main()
