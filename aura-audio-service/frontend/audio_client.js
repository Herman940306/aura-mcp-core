// frontend/audio_client.js
// Browser-based audio client for Aura Audio Service
// Integrates with MCP Concierge dashboard for speech input/output

/**
 * Audio recording and STT integration
 * @param {Function} onTranscript - Callback with transcribed text
 * @returns {Function} Stop function to end recording
 */
export async function startRecording(onTranscript) {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
        alert("Browser recording not supported");
        return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

    recorder.ondataavailable = async (e) => {
        const form = new FormData();
        form.append("audio", e.data, "chunk.webm");

        try {
            const res = await fetch("/api/audio/stt", { method: "POST", body: form });
            if (res.status === 200) {
                const json = await res.json();
                if (json.policy_blocked) {
                    console.warn("Speech contained blocked content");
                    onTranscript("[POLICY BLOCKED]", { blocked: true });
                } else {
                    onTranscript(json.text, {
                        confidence: json.confidence,
                        redacted: json.redacted
                    });
                }
            } else {
                console.error("STT error", res.status);
            }
        } catch (err) {
            console.error("STT request failed", err);
        }
    };

    recorder.start(1000); // chunk every 1s

    return () => { // stop function
        recorder.stop();
        stream.getTracks().forEach(t => t.stop());
    };
}

/**
 * Text-to-Speech - prefers browser TTS, falls back to server
 * @param {string} text - Text to speak
 * @param {Object} options - TTS options
 */
export async function speakText(text, options = {}) {
    const { preferServer = false, voice = "default" } = options;

    // Prefer client-side built-in TTS (faster, no network)
    if (!preferServer && 'speechSynthesis' in window) {
        const ut = new SpeechSynthesisUtterance(text);
        ut.rate = options.rate || 1.0;
        ut.pitch = options.pitch || 1.0;
        window.speechSynthesis.speak(ut);
        return { source: "browser" };
    }

    // Fallback to server-side TTS (higher quality)
    try {
        const res = await fetch("/api/audio/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, voice, format: "wav" })
        });

        if (res.ok) {
            const arrayBuffer = await res.arrayBuffer();
            const ctx = new AudioContext();
            const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
            const src = ctx.createBufferSource();
            src.buffer = audioBuffer;
            src.connect(ctx.destination);
            src.start();
            return { source: "server", duration: audioBuffer.duration };
        } else {
            const error = await res.json();
            console.error("TTS error", res.status, error);
            return { error: error.detail };
        }
    } catch (err) {
        console.error("TTS request failed", err);
        return { error: err.message };
    }
}

/**
 * Check audio service health
 */
export async function checkAudioHealth() {
    try {
        const res = await fetch("/api/audio/health", { timeout: 5000 });
        return res.ok ? await res.json() : { status: "error" };
    } catch {
        return { status: "unreachable" };
    }
}

/**
 * Audio Service UI Component for Dashboard integration
 */
export class AudioServiceUI {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.isRecording = false;
        this.stopRecording = null;
        this.render();
    }

    render() {
        if (!this.container) return;

        this.container.innerHTML = `
      <div class="audio-controls" style="display: flex; gap: 10px; align-items: center;">
        <button id="audio-record-btn" class="btn btn-primary" title="Start/Stop Recording">
          🎤 <span id="record-status">Record</span>
        </button>
        <button id="audio-speak-btn" class="btn btn-secondary" title="Speak last response">
          🔊 Speak
        </button>
        <span id="audio-status" style="font-size: 12px; color: #888;"></span>
      </div>
    `;

        this.bindEvents();
    }

    bindEvents() {
        const recordBtn = document.getElementById('audio-record-btn');
        const speakBtn = document.getElementById('audio-speak-btn');

        recordBtn?.addEventListener('click', () => this.toggleRecording());
        speakBtn?.addEventListener('click', () => this.speakLastResponse());
    }

    async toggleRecording() {
        const statusEl = document.getElementById('record-status');
        const audioStatus = document.getElementById('audio-status');

        if (this.isRecording) {
            this.stopRecording?.();
            this.isRecording = false;
            statusEl.textContent = 'Record';
            audioStatus.textContent = '';
        } else {
            this.stopRecording = await startRecording((text, meta) => {
                audioStatus.textContent = meta.blocked ? '⚠️ Blocked' : `✓ "${text.slice(0, 30)}..."`;
                // Dispatch event for chat integration
                this.container.dispatchEvent(new CustomEvent('transcript', { detail: { text, meta } }));
            });
            this.isRecording = true;
            statusEl.textContent = 'Stop';
            audioStatus.textContent = '🔴 Recording...';
        }
    }

    async speakLastResponse() {
        // Get last assistant message from chat (integrate with your chat UI)
        const lastResponse = document.querySelector('.chat-message.assistant:last-child')?.textContent;
        if (lastResponse) {
            await speakText(lastResponse);
        }
    }
}

// Auto-initialize if container exists
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('audio-service-ui')) {
        window.audioServiceUI = new AudioServiceUI('audio-service-ui');
    }
});
