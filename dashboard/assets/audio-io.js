/**
 * Aura IA Audio I/O Module
 *
 * Browser-based audio capture (STT) and playback (TTS)
 * PRD Section 8.12 compliant - Model never touches audio directly
 *
 * Stack:
 * - STT: WebAudio + MediaRecorder → Gateway → Vosk
 * - TTS: Gateway → Coqui TTS → AudioContext playback
 */

const AudioIO = (function () {
    'use strict';

    // ========================================================================
    // Configuration
    // ========================================================================

    const CONFIG = {
        // API endpoints (routed through Gateway)
        STT_ENDPOINT: '/api/stt/transcribe',
        TTS_ENDPOINT: '/api/tts/synthesize',
        TTS_STATUS_ENDPOINT: '/api/tts/status',
        STT_STATUS_ENDPOINT: '/api/stt/status',

        // Audio settings
        SAMPLE_RATE: 16000,          // 16kHz for Vosk
        CHANNELS: 1,                  // Mono
        CHUNK_INTERVAL_MS: 250,       // Send chunks every 250ms
        MAX_RECORDING_MS: 60000,      // Max 60 seconds

        // TTS settings
        TTS_SPEED: 1.0,               // Normal speed
        TTS_FORMAT: 'wav',            // Output format

        // UI settings
        ENABLE_WAVEFORM: true,        // Show waveform visualization
        ENABLE_VOICE_ACTIVITY: true,  // Voice activity detection

        // Gateway base URL (same origin)
        GATEWAY_URL: window.location.origin.replace(':9205', ':9200'),
    };

    // ========================================================================
    // State
    // ========================================================================

    let state = {
        // Recording state
        isRecording: false,
        mediaStream: null,
        mediaRecorder: null,
        audioChunks: [],
        recordingStartTime: null,

        // Playback state
        isPlaying: false,
        audioContext: null,
        currentSource: null,

        // Service status
        sttAvailable: false,
        ttsAvailable: false,

        // Callbacks
        onTranscription: null,
        onRecordingStart: null,
        onRecordingStop: null,
        onPlaybackStart: null,
        onPlaybackEnd: null,
        onError: null,

        // Visualization
        analyser: null,
        waveformCanvas: null,
        animationFrame: null,
    };

    // ========================================================================
    // Initialization
    // ========================================================================

    /**
     * Initialize the Audio I/O module.
     * @param {Object} options - Configuration options
     * @returns {Promise<boolean>} - True if initialization successful
     */
    async function initialize(options = {}) {
        // Merge options with defaults
        Object.assign(CONFIG, options);

        // Check browser support
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.error('AudioIO: getUserMedia not supported');
            return false;
        }

        if (!window.AudioContext && !window.webkitAudioContext) {
            console.error('AudioIO: AudioContext not supported');
            return false;
        }

        // Initialize AudioContext
        state.audioContext = new (window.AudioContext || window.webkitAudioContext)();

        // Check service availability
        await checkServiceStatus();

        console.log('AudioIO: Initialized', {
            sttAvailable: state.sttAvailable,
            ttsAvailable: state.ttsAvailable,
        });

        return true;
    }

    /**
     * Check STT/TTS service availability.
     */
    async function checkServiceStatus() {
        try {
            // Check STT
            const sttResponse = await fetch(`${CONFIG.GATEWAY_URL}${CONFIG.STT_STATUS_ENDPOINT}`);
            if (sttResponse.ok) {
                const sttStatus = await sttResponse.json();
                state.sttAvailable = sttStatus.available && sttStatus.model_loaded;
            }
        } catch (e) {
            console.warn('AudioIO: STT service not available', e);
            state.sttAvailable = false;
        }

        try {
            // Check TTS
            const ttsResponse = await fetch(`${CONFIG.GATEWAY_URL}${CONFIG.TTS_STATUS_ENDPOINT}`);
            if (ttsResponse.ok) {
                const ttsStatus = await ttsResponse.json();
                state.ttsAvailable = ttsStatus.available && ttsStatus.model_loaded;
            }
        } catch (e) {
            console.warn('AudioIO: TTS service not available', e);
            state.ttsAvailable = false;
        }
    }

    // ========================================================================
    // Speech-to-Text (Recording)
    // ========================================================================

    /**
     * Start recording audio for speech-to-text.
     * @returns {Promise<boolean>} - True if recording started
     */
    async function startRecording() {
        if (state.isRecording) {
            console.warn('AudioIO: Already recording');
            return false;
        }

        try {
            // Request microphone access
            state.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: CONFIG.CHANNELS,
                    sampleRate: CONFIG.SAMPLE_RATE,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                }
            });

            // Set up MediaRecorder
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';

            state.mediaRecorder = new MediaRecorder(state.mediaStream, { mimeType });
            state.audioChunks = [];
            state.recordingStartTime = Date.now();

            // Collect audio chunks
            state.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    state.audioChunks.push(event.data);
                }
            };

            // Handle recording stop
            state.mediaRecorder.onstop = async () => {
                await processRecording();
            };

            // Set up visualization
            if (CONFIG.ENABLE_WAVEFORM && state.waveformCanvas) {
                setupWaveformVisualization();
            }

            // Start recording with interval chunks
            state.mediaRecorder.start(CONFIG.CHUNK_INTERVAL_MS);
            state.isRecording = true;

            // Auto-stop after max duration
            setTimeout(() => {
                if (state.isRecording) {
                    stopRecording();
                }
            }, CONFIG.MAX_RECORDING_MS);

            // Callback
            if (state.onRecordingStart) {
                state.onRecordingStart();
            }

            console.log('AudioIO: Recording started');
            return true;

        } catch (error) {
            console.error('AudioIO: Failed to start recording', error);
            if (state.onError) {
                state.onError('microphone', error.message);
            }
            return false;
        }
    }

    /**
     * Stop recording and process audio.
     * @returns {Promise<void>}
     */
    async function stopRecording() {
        if (!state.isRecording || !state.mediaRecorder) {
            return;
        }

        state.isRecording = false;

        // Stop visualization
        if (state.animationFrame) {
            cancelAnimationFrame(state.animationFrame);
            state.animationFrame = null;
        }

        // Stop MediaRecorder (triggers onstop -> processRecording)
        state.mediaRecorder.stop();

        // Stop all tracks
        if (state.mediaStream) {
            state.mediaStream.getTracks().forEach(track => track.stop());
            state.mediaStream = null;
        }

        console.log('AudioIO: Recording stopped');
    }

    /**
     * Process recorded audio and send to STT service.
     */
    async function processRecording() {
        if (state.audioChunks.length === 0) {
            console.warn('AudioIO: No audio data recorded');
            return;
        }

        const recordingDuration = (Date.now() - state.recordingStartTime) / 1000;
        console.log(`AudioIO: Processing ${recordingDuration.toFixed(1)}s of audio`);

        // Combine chunks into blob
        const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });

        // Convert to WAV for Vosk (if needed)
        const wavBlob = await convertToWav(audioBlob);

        // Send to STT service
        try {
            const formData = new FormData();
            formData.append('file', wavBlob, 'audio.wav');

            const response = await fetch(`${CONFIG.GATEWAY_URL}${CONFIG.STT_ENDPOINT}`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`STT request failed: ${response.status}`);
            }

            const result = await response.json();

            console.log('AudioIO: Transcription result', result);

            // Callback with result
            if (state.onTranscription) {
                state.onTranscription(result);
            }

            // Callback for recording stop
            if (state.onRecordingStop) {
                state.onRecordingStop(result);
            }

        } catch (error) {
            console.error('AudioIO: STT request failed', error);
            if (state.onError) {
                state.onError('stt', error.message);
            }
        }
    }

    /**
     * Convert WebM audio to WAV format for Vosk.
     * @param {Blob} webmBlob - WebM audio blob
     * @returns {Promise<Blob>} - WAV audio blob
     */
    async function convertToWav(webmBlob) {
        // Use AudioContext to decode and re-encode
        const arrayBuffer = await webmBlob.arrayBuffer();

        try {
            const audioBuffer = await state.audioContext.decodeAudioData(arrayBuffer);

            // Convert to 16kHz mono PCM
            const offlineContext = new OfflineAudioContext(
                1,  // mono
                audioBuffer.duration * CONFIG.SAMPLE_RATE,
                CONFIG.SAMPLE_RATE
            );

            const source = offlineContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(offlineContext.destination);
            source.start();

            const renderedBuffer = await offlineContext.startRendering();

            // Convert to WAV blob
            return encodeWav(renderedBuffer);

        } catch (error) {
            console.warn('AudioIO: WAV conversion failed, sending raw', error);
            return webmBlob;
        }
    }

    /**
     * Encode AudioBuffer to WAV format.
     * @param {AudioBuffer} audioBuffer - Audio buffer to encode
     * @returns {Blob} - WAV blob
     */
    function encodeWav(audioBuffer) {
        const numChannels = audioBuffer.numberOfChannels;
        const sampleRate = audioBuffer.sampleRate;
        const format = 1;  // PCM
        const bitDepth = 16;

        const samples = audioBuffer.getChannelData(0);
        const buffer = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buffer);

        // WAV header
        writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + samples.length * 2, true);
        writeString(view, 8, 'WAVE');
        writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true);  // fmt chunk size
        view.setUint16(20, format, true);
        view.setUint16(22, numChannels, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * numChannels * bitDepth / 8, true);
        view.setUint16(32, numChannels * bitDepth / 8, true);
        view.setUint16(34, bitDepth, true);
        writeString(view, 36, 'data');
        view.setUint32(40, samples.length * 2, true);

        // Audio data
        let offset = 44;
        for (let i = 0; i < samples.length; i++) {
            const s = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            offset += 2;
        }

        return new Blob([buffer], { type: 'audio/wav' });
    }

    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    // ========================================================================
    // Text-to-Speech (Playback)
    // ========================================================================

    /**
     * Synthesize and play speech from text.
     * @param {string} text - Text to synthesize
     * @param {Object} options - TTS options
     * @returns {Promise<boolean>} - True if playback started
     */
    async function speak(text, options = {}) {
        if (!text || !text.trim()) {
            console.warn('AudioIO: Empty text for TTS');
            return false;
        }

        const speed = options.speed || CONFIG.TTS_SPEED;
        const format = options.format || CONFIG.TTS_FORMAT;

        // Stop any current playback
        if (state.isPlaying) {
            stopPlayback();
        }

        try {
            // Request TTS from server
            const response = await fetch(`${CONFIG.GATEWAY_URL}${CONFIG.TTS_ENDPOINT}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    speed: speed,
                    output_format: format,
                }),
            });

            if (!response.ok) {
                throw new Error(`TTS request failed: ${response.status}`);
            }

            // Get audio data
            const audioBuffer = await response.arrayBuffer();

            // Log metadata from headers
            const duration = response.headers.get('X-TTS-Duration-Seconds');
            const processingMs = response.headers.get('X-TTS-Processing-Ms');
            console.log(`AudioIO: TTS received ${duration}s audio (${processingMs}ms processing)`);

            // Play audio
            await playAudioBuffer(audioBuffer);

            return true;

        } catch (error) {
            console.error('AudioIO: TTS request failed', error);
            if (state.onError) {
                state.onError('tts', error.message);
            }
            return false;
        }
    }

    /**
     * Play audio buffer.
     * @param {ArrayBuffer} arrayBuffer - Audio data
     */
    async function playAudioBuffer(arrayBuffer) {
        try {
            // Resume AudioContext if suspended (Safari)
            if (state.audioContext.state === 'suspended') {
                await state.audioContext.resume();
            }

            // Decode audio data
            const audioBuffer = await state.audioContext.decodeAudioData(arrayBuffer);

            // Create source
            const source = state.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(state.audioContext.destination);

            // Track playback state
            state.currentSource = source;
            state.isPlaying = true;

            source.onended = () => {
                state.isPlaying = false;
                state.currentSource = null;
                if (state.onPlaybackEnd) {
                    state.onPlaybackEnd();
                }
            };

            // Start playback
            source.start(0);

            if (state.onPlaybackStart) {
                state.onPlaybackStart();
            }

            console.log(`AudioIO: Playing ${audioBuffer.duration.toFixed(1)}s audio`);

        } catch (error) {
            console.error('AudioIO: Audio playback failed', error);
            state.isPlaying = false;
            throw error;
        }
    }

    /**
     * Stop current audio playback.
     */
    function stopPlayback() {
        if (state.currentSource) {
            try {
                state.currentSource.stop();
            } catch (e) {
                // Already stopped
            }
            state.currentSource = null;
        }
        state.isPlaying = false;
    }

    // ========================================================================
    // Visualization
    // ========================================================================

    /**
     * Set up waveform visualization canvas.
     * @param {HTMLCanvasElement} canvas - Canvas element
     */
    function setWaveformCanvas(canvas) {
        state.waveformCanvas = canvas;
    }

    /**
     * Set up waveform visualization during recording.
     */
    function setupWaveformVisualization() {
        if (!state.waveformCanvas || !state.mediaStream) return;

        const source = state.audioContext.createMediaStreamSource(state.mediaStream);
        state.analyser = state.audioContext.createAnalyser();
        state.analyser.fftSize = 256;
        source.connect(state.analyser);

        drawWaveform();
    }

    /**
     * Draw waveform on canvas.
     */
    function drawWaveform() {
        if (!state.isRecording || !state.analyser || !state.waveformCanvas) return;

        const canvas = state.waveformCanvas;
        const ctx = canvas.getContext('2d');
        const bufferLength = state.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        state.analyser.getByteFrequencyData(dataArray);

        // Clear canvas
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw bars
        const barWidth = (canvas.width / bufferLength) * 2.5;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const barHeight = (dataArray[i] / 255) * canvas.height;

            // Gradient color (cyan to purple)
            const hue = 180 + (i / bufferLength) * 60;
            ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
            ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

            x += barWidth + 1;
        }

        state.animationFrame = requestAnimationFrame(drawWaveform);
    }

    // ========================================================================
    // Event Handlers
    // ========================================================================

    /**
     * Set callback for transcription results.
     * @param {Function} callback - Callback function(result)
     */
    function onTranscription(callback) {
        state.onTranscription = callback;
    }

    /**
     * Set callback for recording start.
     * @param {Function} callback - Callback function()
     */
    function onRecordingStart(callback) {
        state.onRecordingStart = callback;
    }

    /**
     * Set callback for recording stop.
     * @param {Function} callback - Callback function(result)
     */
    function onRecordingStop(callback) {
        state.onRecordingStop = callback;
    }

    /**
     * Set callback for playback start.
     * @param {Function} callback - Callback function()
     */
    function onPlaybackStart(callback) {
        state.onPlaybackStart = callback;
    }

    /**
     * Set callback for playback end.
     * @param {Function} callback - Callback function()
     */
    function onPlaybackEnd(callback) {
        state.onPlaybackEnd = callback;
    }

    /**
     * Set callback for errors.
     * @param {Function} callback - Callback function(type, message)
     */
    function onError(callback) {
        state.onError = callback;
    }

    // ========================================================================
    // Utility Functions
    // ========================================================================

    /**
     * Check if recording is in progress.
     * @returns {boolean}
     */
    function isRecording() {
        return state.isRecording;
    }

    /**
     * Check if audio is playing.
     * @returns {boolean}
     */
    function isPlaying() {
        return state.isPlaying;
    }

    /**
     * Get service status.
     * @returns {Object}
     */
    function getStatus() {
        return {
            sttAvailable: state.sttAvailable,
            ttsAvailable: state.ttsAvailable,
            isRecording: state.isRecording,
            isPlaying: state.isPlaying,
        };
    }

    // ========================================================================
    // Public API
    // ========================================================================

    return {
        // Initialization
        initialize,
        checkServiceStatus,

        // STT (Recording)
        startRecording,
        stopRecording,
        isRecording,

        // TTS (Playback)
        speak,
        stopPlayback,
        isPlaying,

        // Visualization
        setWaveformCanvas,

        // Events
        onTranscription,
        onRecordingStart,
        onRecordingStop,
        onPlaybackStart,
        onPlaybackEnd,
        onError,

        // Status
        getStatus,
    };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AudioIO;
}
