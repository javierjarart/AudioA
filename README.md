# AudioA

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
| `audio_app.py` | Windows / Linux | App unificada — servidor o cliente con GUI (PySide6 + sounddevice) |
| `audio_server.py` | Linux | CLI — receptor UDP, reproduce con PyAudio |
| `audio_client_windows.py` | Windows | CLI — captura micrófono/loopback y envía por UDP |
| `audio_client_gui.py` | Windows | GUI (PySide6) — misma funcionalidad que el CLI con interfaz gráfica |
| `AudioClientAndroid.kt` | Android | App Kotlin — captura micrófono y envía por UDP |
| `activity_main.xml` | Android | Layout para la app Android |
| `installer.iss` | Windows | Script Inno Setup para empaquetar `audio_app.py` como instalador |
| `build_installer.bat` | Windows | Build automatizado del instalador |
| `resources/icon.png` | — | Icono del proyecto (letra A + ondas de sonido) |
| `resources/generate_icon.py` | — | Script para regenerar el icono |

## App Unificada (Recomendada)

Un solo ejecutable que funciona como **servidor** o **cliente** con interfaz gráfica.

```bash
pip install pyside6 sounddevice
python audio_app.py
```

| Modo | Qué hace |
|---|---|
| Servidor | Escucha UDP y reproduce audio con `sd.OutputStream` |
| Cliente | Captura micrófono/loopback y envía por UDP |

Selector de modo mediante radio buttons. Cada modo muestra su panel con parámetros específicos.

### Buildear .exe standalone

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "AudioA" ^
  --add-data "resources/icon.png;resources" ^
  --icon resources/icon.ico audio_app.py
```

Salida: `dist/AudioA.exe`

### Buildear instalador (Windows)

Requiere [Inno Setup](https://jrsoftware.org/isdl.php) instalado.

```bat
build_installer.bat
```

O manualmente:

```bat
ISCC.exe installer.iss
```

Salida: `dist/AudioA_Setup.exe`

## Servidor Linux (CLI legacy)

```bash
sudo apt install python3-pyaudio portaudio19-dev

python3 audio_server.py --list
python3 audio_server.py
python3 audio_server.py --device 2 --port 9999 --buffer 4
```

## Cliente Windows (CLI legacy)

```bash
pip install sounddevice

python audio_client_windows.py --server 192.168.1.X --list
python audio_client_windows.py --server 192.168.1.X
python audio_client_windows.py --server 192.168.1.X --device 3 --port 9999
```

### Loopback (audio del sistema)

1. Panel de control → Sonido → Grabación
2. Click derecho → "Mostrar dispositivos desactivados"
3. Habilitar "Mezcla estéreo" o "Stereo Mix"

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

**Nota:** La app captura el micrófono. Para audio interno (altavoz) se requiere Android 10+ y `MediaProjection`.

## Parámetros

### Latencia

```
Total = captura + red + jitter buffer + reproducción
```

| Chunk (frames) | Latencia por paquete |
|---|---|
| 256 | ~5.3ms |
| 512 (default) | ~10.6ms |
| 1024 | ~21.3ms |

### Jitter buffer (servidor)

| Valor | Uso |
|---|---|
| 3–4 | Latencia mínima, redes estables |
| 6 (default) | Balance |
| 10+ | Redes inestables (WiFi con interferencia) |

### Bitrate

```
48000 Hz × 2 canales × 2 bytes = 192 KB/s = 1.536 Mbps
```

Manejable en cualquier WiFi moderno (incluso 802.11n).

## Troubleshooting

| Problema | Solución |
|---|---|
| Sin audio | Verificar firewall (UDP 9999), `--list` para dispositivo correcto, volumen activo |
| Cortes / crackling | Aumentar `--buffer` en servidor, usar WiFi 5GHz |
| Alta latencia | Reducir chunk en cliente, reducir buffer en servidor, conectar servidor por Ethernet |

## Licencia

MIT
