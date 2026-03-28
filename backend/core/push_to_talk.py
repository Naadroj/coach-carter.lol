"""
Push-to-Talk — AMOKK
Appuie sur PTT_KEY pour parler à AMOKK.
Flux : enregistrement micro → Whisper STT → Claude → OpenAI TTS
"""
import asyncio
import io
import logging
import os
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger("amokk.ptt")

# ── Config ─────────────────────────────────────────────────────────────────────
PTT_KEY        = "f9"          # Touche push-to-talk (modifiable)
SAMPLE_RATE    = 16000         # Hz — optimal pour Whisper
MAX_DURATION   = 15            # secondes max d'enregistrement
SILENCE_THRESH = 0.01          # seuil silence (RMS) pour arrêt auto
SILENCE_DELAY  = 1.5           # secondes de silence avant arrêt auto


class PushToTalk:
    """
    Gère le push-to-talk global.
    - Détection de la touche via `keyboard`
    - Enregistrement micro via sounddevice
    - Transcription via OpenAI Whisper API
    - Réponse via Claude + TTS (injectés depuis assistant.py)
    """

    def __init__(self):
        self._assistant = None
        self._openai_client = None
        self._recording: bool = False
        self._frames: list = []
        self._stream: Optional[sd.InputStream] = None
        self._enabled: bool = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def inject(self, assistant, openai_client):
        self._assistant = assistant
        self._openai_client = openai_client

    def start(self, loop: asyncio.AbstractEventLoop):
        """Démarre l'écoute de la touche PTT dans un thread dédié."""
        if self._enabled:
            return
        self._loop = loop
        self._enabled = True
        self._thread = threading.Thread(target=self._listen_hotkey, daemon=True)
        self._thread.start()
        logger.info("Push-to-Talk activé — touche: %s", PTT_KEY.upper())

    def stop(self):
        self._enabled = False
        self._stop_recording()

    # ── Hotkey ─────────────────────────────────────────────────────────────────

    def _listen_hotkey(self):
        try:
            import keyboard
            keyboard.on_press_key(PTT_KEY,   lambda _: self._on_press(),   suppress=False)
            keyboard.on_release_key(PTT_KEY, lambda _: self._on_release(), suppress=False)
            logger.info("PTT keyboard hook installé (%s)", PTT_KEY.upper())
            while self._enabled:
                time.sleep(0.1)
            keyboard.unhook_all()
        except Exception as e:
            logger.error("PTT keyboard error: %s", e)

    def _on_press(self):
        if not self._recording:
            self._start_recording()

    def _on_release(self):
        if self._recording:
            self._stop_recording()
            # Traitement dans un thread séparé pour ne pas bloquer
            threading.Thread(target=self._process, daemon=True).start()

    # ── Enregistrement ─────────────────────────────────────────────────────────

    def _start_recording(self):
        self._frames = []
        self._recording = True
        logger.info("PTT — Enregistrement démarré")

        def callback(indata, frames, time_info, status):
            if self._recording:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def _stop_recording(self):
        self._recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        logger.info("PTT — Enregistrement arrêté (%d chunks)", len(self._frames))

    # ── Traitement ─────────────────────────────────────────────────────────────

    def _process(self):
        if not self._frames:
            return

        audio = np.concatenate(self._frames, axis=0).flatten()
        if len(audio) < SAMPLE_RATE * 0.3:  # moins de 0.3s → ignorer
            logger.info("PTT — Audio trop court, ignoré")
            return

        # 1. Transcription Whisper
        text = self._transcribe(audio)
        if not text:
            return
        logger.info("PTT — Transcrit: %s", text)

        # 2. Réponse Claude
        if self._loop and self._assistant:
            asyncio.run_coroutine_threadsafe(
                self._respond(text), self._loop
            )

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        """Transcription via OpenAI Whisper API"""
        if not self._openai_client:
            logger.warning("PTT — OpenAI client non disponible")
            return None
        try:
            # Convertir numpy array → WAV bytes
            import wave
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes((audio * 32767).astype(np.int16).tobytes())
            buf.seek(0)
            buf.name = "audio.wav"  # requis par l'API OpenAI

            response = self._openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=buf,
                language="fr",
            )
            return response.text.strip()
        except Exception as e:
            logger.error("PTT Whisper error: %s", e)
            return None

    async def _respond(self, question: str):
        """Génère une réponse Claude et la lit via TTS"""
        if not self._assistant:
            return
        try:
            import anthropic
            client = self._assistant._anthropic_client
            if not client:
                await self._assistant.say(f"Tu as demandé : {question}. Je n'ai pas de connexion IA disponible.")
                return

            system = (
                "Tu es AMOKK, un coach IA expert en League of Legends. "
                "Le joueur te parle directement via microphone. "
                "Réponds de façon courte, directe et utile en français. "
                "Maximum 3 phrases. Ne répète pas la question."
            )

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=200,
                    system=system,
                    messages=[{"role": "user", "content": question}],
                )
            )
            answer = response.content[0].text.strip()
            logger.info("PTT — Réponse Claude: %s", answer[:100])
            await self._assistant.say(answer, priority=1)  # priorité haute

        except Exception as e:
            logger.error("PTT respond error: %s", e)


# Singleton
push_to_talk = PushToTalk()
