# AudioA — Audio Streaming UDP (PCM sin comprimir)

Streaming de audio en tiempo real desde Windows/Android a Linux vía UDP, con latencia ~10–40ms en LAN.

**Formato:** PCM int16, 48 kHz, estéreo — sin compresión, sin pérdidas.

```
Windows ──┐
           ├──► UDP (PCM crudo) ──► Linux (servidor)
Android ──┘
```

## Componentes

| Archivo | Plataforma | Función |
|---|---|---|
| `audio_app.py` | Windows / Linux | **App unificada** — servidor o cliente con GUI (PySide6 + sounddevice) |
| `audio_server.py` | Linux | CLI — receptor UDP, reproduce audio con PyAudio |
| `audio_client_windows.py` | Windows | CLI — captura micrófono/loopback y envía por UDP |
| `audio_client_gui.py` | Windows | GUI (PySide6) — misma funcionalidad con interfaz gráfica |
| `AudioClientAndroid.kt` | Android | App Kotlin — captura micrófono y envía por UDP |
| `activity_main.xml` | Android | Layout para la App |

## Servidor Linux

```bash
sudo apt install python3-pyaudio portaudio19-dev
# o: pip install pyaudio

# Listar dispositivos de salida
python3 audio_server.py --list

# Iniciar
python3 audio_server.py

# Dispositivo específico y puerto personalizado
python3 audio_server.py --device 2 --port 9999

# Ajustar jitter buffer (menor = menos latencia, mayor = más estabilidad)
python3 audio_server.py --buffer 4
```

## Cliente Windows (CLI)

```bash
pip install sounddevice

# Listar dispositivos
python audio_client_windows.py --server 192.168.1.X --list

# Enviar micrófono por defecto
python audio_client_windows.py --server 192.168.1.X

# Enviar loopback (audio del sistema, dispositivo índice 3)
python audio_client_windows.py --server 192.168.1.X --device 3

# Puerto personalizado
python audio_client_windows.py --server 192.168.1.X --port 9999
```

## Cliente Windows (GUI)

```bash
pip install pyside6 sounddevice
python audio_client_gui.py
```

Interfaz gráfica con selección de dispositivo, ajuste de chunk, contador de paquetes e indicador de estado.

## App Unificada (Windows)

```bash
pip install pyside6 sounddevice
python audio_app.py
```

Un solo ejecutable que funciona como **servidor** o **cliente**:

| Modo | Qué hace |
|---|---|
| Servidor | Recibe UDP y reproduce con `sd.OutputStream` (reemplaza PyAudio) |
| Cliente | Captura micrófono/loopback y envía por UDP |

Selector de modo mediante radio buttons, panel dinámico con parámetros específicos de cada modo.

### Buildear .exe standalone

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "AudioA" --add-data "resources/icon.png;resources" --icon resources/icon.ico audio_app.py
```

Salida: `dist/AudioA.exe`

### Buildear instalador (Inno Setup)

Requiere [Inno Setup](https://jrsoftware.org/isdl.php) instalado.

```bash
build_installer.bat
```

O manualmente:

```bash
ISCC.exe installer.iss
```

Salida: `dist/AudioA_Setup.exe`

## Cliente Android

1. Crear proyecto Android Studio (Empty Activity, min SDK 23, Kotlin)
2. Reemplazar `MainActivity.kt` con `AudioClientAndroid.kt`
3. Copiar `activity_main.xml` a `res/layout/`
4. En `AndroidManifest.xml` agregar:
   ```xml
   <uses-permission android:name="android.permission.RECORD_AUDIO"/>
   <uses-permission android:name="android.permission.INTERNET"/>
   ```
5. Build, instalar, ingresar IP del servidor y presionar "Iniciar stream"

## Parámetros

### Latencia total
captura + red + jitter buffer + reproducción

| Chunk (frames) | Latencia por paquete |
|---|---|
| 256 | ~5.3ms |
| 512 (default) | ~10.6ms |
| 1024 | ~21.3ms |

### Jitter buffer (servidor)
`--buffer N`: paquetes acumulados antes de reproducir

- **3–4:** menor latenza, redes estables
- **6 (default):** balance
- **10+:** redes inestables (WiFi con interferencia)

### Bitrate
```
48000 Hz × 2 canales × 2 bytes = 192 KB/s = 1.536 Mbps
```

## Troubleshooting

| Problema | Solución |
|---|---|
| Sin audio | Verificar firewall (UDP 9999), `--list` para dispositivo correcto, volumen activo |
| Cortes/crackling | Aumentar `--buffer` en servidor, usar WiFi 5GHz |
| Alta latencia | Reducir chunk en cliente, reducir buffer en servidor, conectar servidor por Ethernet |
