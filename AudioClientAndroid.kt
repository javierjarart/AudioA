package com.example.audioaudiostreamer

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.io.IOException
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

class MainActivity : AppCompatActivity() {

    companion object {
        private const val SAMPLE_RATE = 48000
        private const val CHANNELS = 2
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_STEREO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        private const val CHUNK_FRAMES = 512
        private const val BYTES_PER_FRAME = CHANNELS * 2
        private const val CHUNK_BYTES = CHUNK_FRAMES * BYTES_PER_FRAME
        private const val PERMISSION_REQUEST_CODE = 100
        private const val BUFFER_SIZE_MULTIPLIER = 4

        private val BUFFER_SIZE = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT
        ) * BUFFER_SIZE_MULTIPLIER
    }

    private var isStreaming = false
    private var audioRecord: AudioRecord? = null
    private var socket: DatagramSocket? = null
    private var streamThread: Thread? = null

    private lateinit var ipInput: EditText
    private lateinit var portInput: EditText
    private lateinit var startButton: Button
    private lateinit var statusText: TextView

    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        ipInput = findViewById(R.id.ipInput)
        portInput = findViewById(R.id.portInput)
        startButton = findViewById(R.id.startButton)
        statusText = findViewById(R.id.statusText)

        portInput.setText("9999")

        startButton.setOnClickListener {
            if (isStreaming) {
                stopStream()
            } else {
                startStream()
            }
        }

        checkAudioPermission()
    }

    private fun checkAudioPermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this, arrayOf(Manifest.permission.RECORD_AUDIO), PERMISSION_REQUEST_CODE
            )
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST_CODE) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                updateStatus("Permiso concedido")
            } else {
                updateStatus("Permiso denegado")
            }
        }
    }

    private fun startStream() {
        val ip = ipInput.text.toString().trim()
        val port = portInput.text.toString().trim().toIntOrNull() ?: 9999

        if (ip.isEmpty()) {
            updateStatus("Ingresa una IP")
            return
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            checkAudioPermission()
            return
        }

        isStreaming = true
        startButton.text = "Detener stream"
        updateStatus("Streaming a $ip:$port...")

        streamThread = Thread {
            try {
                val serverAddress = InetAddress.getByName(ip)
                socket = DatagramSocket()
                audioRecord = AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    CHANNEL_CONFIG,
                    AUDIO_FORMAT,
                    BUFFER_SIZE
                )

                if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                    handler.post { updateStatus("Error: No se pudo inicializar AudioRecord") }
                    stopStream()
                    return@Thread
                }

                val buffer = ByteArray(CHUNK_BYTES)
                audioRecord?.startRecording()

                while (isStreaming) {
                    val bytesRead = audioRecord?.read(buffer, 0, CHUNK_BYTES) ?: -1
                    if (bytesRead > 0) {
                        val packet = DatagramPacket(buffer, bytesRead, serverAddress, port)
                        socket?.send(packet)
                    }
                }

            } catch (e: IOException) {
                handler.post { updateStatus("Error de red: ${e.message}") }
            } catch (e: SecurityException) {
                handler.post { updateStatus("Permiso denegado") }
            } finally {
                cleanup()
            }
        }

        streamThread?.start()
    }

    private fun stopStream() {
        isStreaming = false
        startButton.text = "Iniciar stream"
        updateStatus("Detenido")
        cleanup()
    }

    private fun cleanup() {
        try {
            audioRecord?.let {
                if (it.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    it.stop()
                }
                it.release()
            }
        } catch (e: Exception) {
            // ignore
        }
        audioRecord = null

        try {
            socket?.close()
        } catch (e: Exception) {
            // ignore
        }
        socket = null

        streamThread?.join(1000)
        streamThread = null
    }

    private fun updateStatus(msg: String) {
        handler.post { statusText.text = msg }
    }

    override fun onDestroy() {
        stopStream()
        super.onDestroy()
    }
}
