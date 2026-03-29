"""
Assistant - Génération et lecture des conseils vocaux via TTS
Utilise Anthropic Claude pour la génération de texte
et OpenAI TTS pour la synthèse vocale en français (voix onyx)
Lecture audio via playsound (compatible Python 3.14+)
"""
import asyncio
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger("amokk.assistant")

# Clés API depuis l'env
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CLAUDE_MODEL = "claude-haiku-4-5"   # rapide + économique pour le coaching temps réel
OPENAI_TTS_MODEL  = "tts-1"          # tts-1 (rapide) ou tts-1-hd (haute qualité)
OPENAI_TTS_VOICE  = "onyx"           # onyx=grave/masculin, nova=féminin, alloy=neutre
OPENAI_TTS_FORMAT = "wav"            # wav pour sounddevice (contrôle volume réel)


class Assistant:
    """
    Génère des conseils de coaching et les lit à voix haute.
    - Génération de texte : Anthropic Claude (claude-haiku-4-5)
    - TTS : OpenAI TTS (voix onyx, qualité neurale, français natif)
    - Playback : playsound (compatible Python 3.14+, lecture MP3 directe)
    """

    def __init__(self):
        self._volume: float = 0.67       # 0.0 → 1.0
        self._running: bool = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._interrupt_event: threading.Event = threading.Event()
        self._task: Optional[asyncio.Task] = None
        self._anthropic_client = None
        self._playsound_available: bool = False
        self._current_tmpfile: Optional[str] = None
        self._openai_client = None
        self._initialized = False
        self._usage = {
            'anthropic_input_tokens':  0,
            'anthropic_output_tokens': 0,
            'openai_tts_chars':        0,
        }

    def initialize(self):
        self._init_anthropic()
        self._init_openai()
        self._init_audio()
        self._initialized = True
        logger.info("Assistant initialized (Anthropic Claude + OpenAI TTS + playsound).")

    def _init_anthropic(self):
        if not ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not set — coaching advice will use static fallback")
            return
        try:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info("Anthropic client initialized (model: %s).", CLAUDE_MODEL)
        except ImportError:
            logger.warning("anthropic package not installed — run: pip install anthropic")

    def _init_openai(self):
        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set — TTS will use fallback")
            return
        try:
            import openai
            self._openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI TTS client initialized (model: %s, voice: %s).", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
        except ImportError:
            logger.warning("openai package not installed — run: pip install openai")

    def _init_audio(self):
        try:
            import sounddevice  # noqa
            import soundfile    # noqa
            self._playsound_available = True
            logger.info("Audio player: sounddevice + soundfile (WAV, volume réel)")
        except ImportError:
            logger.warning("sounddevice/soundfile not available — run: pip install sounddevice soundfile")

    async def start(self):
        if not self._initialized:
            self.initialize()
        self._running = True
        self._task = asyncio.create_task(self._process_queue())

    async def stop(self):
        self._running = False
        self.interrupt()
        if self._task:
            self._task.cancel()

    def set_volume(self, volume_percent: int):
        """Volume réel appliqué à la lecture audio (0-100 → 0.0-1.0)"""
        self._volume = max(0, min(100, volume_percent)) / 100.0
        logger.info("Volume set to %.0f%%", volume_percent)

    def interrupt(self):
        """Interrompt la lecture en cours"""
        self._interrupt_event.set()

    async def say(self, text: str, priority: int = 5):
        """Ajoute un message à la queue TTS"""
        await self._queue.put((priority, text))
        logger.info("Assistant queued: %s...", text[:80])

    async def _process_queue(self):
        while self._running:
            try:
                _, text = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                self._interrupt_event.clear()
                await self._speak(text)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("TTS error: %s", e)

    async def _speak(self, text: str):
        if not text:
            return
        logger.info("Speaking: %s", text[:100])
        audio_data = await self._generate_tts(text)
        if audio_data:
            await asyncio.get_event_loop().run_in_executor(None, self._play_audio, audio_data)
        else:
            logger.info("[TTS FALLBACK] %s", text)

    async def _generate_tts(self, text: str) -> Optional[bytes]:
        """Génère l'audio via OpenAI TTS"""
        if not self._openai_client:
            logger.warning("OpenAI TTS client not available")
            return None
        try:
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, self._openai_tts_generate, text)
            return audio_bytes
        except Exception as e:
            logger.error("OpenAI TTS generation error: %s", e)
            return None

    def _openai_tts_generate(self, text: str) -> Optional[bytes]:
        """Synthèse synchrone via OpenAI TTS (format WAV pour sounddevice)"""
        try:
            response = self._openai_client.audio.speech.create(
                model=OPENAI_TTS_MODEL,
                voice=OPENAI_TTS_VOICE,
                input=text,
                response_format=OPENAI_TTS_FORMAT,
            )
            self._usage['openai_tts_chars'] += len(text)
            return response.content
        except Exception as e:
            logger.error("OpenAI TTS error: %s", e)
            return None

    def _play_audio(self, audio_data: bytes):
        """Joue l'audio WAV via sounddevice avec volume réel"""
        if not self._playsound_available:
            return
        try:
            import io
            import sounddevice as sd
            import soundfile as sf
            import numpy as np

            if self._interrupt_event.is_set():
                return

            data, samplerate = sf.read(io.BytesIO(audio_data))
            data = (data * self._volume).astype(np.float32)

            sd.play(data, samplerate)
            # Attendre la fin en vérifiant l'interruption toutes les 100ms
            while sd.get_stream().active:
                if self._interrupt_event.is_set():
                    sd.stop()
                    return
                import time
                time.sleep(0.1)
        except Exception as e:
            logger.error("sounddevice playback error: %s", e)

    async def generate_coaching_advice(self, trigger_type: str, context: dict) -> str:
        """
        Génère un conseil de coaching contextuel via Claude Anthropic.
        Utilise le contexte de jeu pour personnaliser le conseil.
        """
        if not self._anthropic_client:
            return _get_fallback_advice(trigger_type, context)

        system_prompt = (
            "Tu es AMOKK, un coach IA expert en League of Legends. "
            "Tu donnes des conseils courts, directs et actionnables en français. "
            "Maximum 2 phrases. Ton professionnel mais encourageant. "
            "Utilise obligatoirement les termes français de LoL : "
            "'voie' (pas 'lane'), 'tourelle' (pas 'tower/turret'), 'inhibiteur' (pas 'inhib'), "
            "'héraut' (pas 'herald'), 'balise' ou 'vision' (pas 'ward'), "
            "'combat d'équipe' (pas 'teamfight'), 'retour en base' (pas 'back'), "
            "'minions' ou 'farm' (pas 'CS'), 'jungler', 'gank', 'roam', 'objectif', "
            "'voie du haut', 'voie du milieu', 'voie du bas', 'carry', 'engage', 'poke'. "
            "N'utilise jamais de termes anglais quand un équivalent français existe."
        )

        user_prompt = _build_prompt(trigger_type, context)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._anthropic_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=150,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
            )
            usage = response.usage
            self._usage['anthropic_input_tokens']  += usage.input_tokens
            self._usage['anthropic_output_tokens'] += usage.output_tokens
            return response.content[0].text.strip()
        except Exception as e:
            logger.error("Claude API error: %s", e)
            return _get_fallback_advice(trigger_type, context)

    def get_usage(self) -> dict:
        inp   = self._usage['anthropic_input_tokens']
        out   = self._usage['anthropic_output_tokens']
        chars = self._usage['openai_tts_chars']
        anthropic_cost = (inp * 1.00 + out * 5.00) / 1_000_000
        openai_cost    = chars * 15.00 / 1_000_000
        return {
            'anthropic': {
                'input_tokens':  inp,
                'output_tokens': out,
                'cost_usd':      round(anthropic_cost, 4),
            },
            'openai_tts': {
                'chars':    chars,
                'cost_usd': round(openai_cost, 4),
            },
            'total_cost_usd': round(anthropic_cost + openai_cost, 4),
        }


def _build_prompt(trigger_type: str, ctx: dict) -> str:
    """Construit le prompt selon le type de trigger"""
    role = ctx.get("role", "MIDDLE")
    champ = ctx.get("champion", "ton champion")
    cs = ctx.get("cs", 0)
    kills = ctx.get("kills", 0)
    deaths = ctx.get("deaths", 0)
    assists = ctx.get("assists", 0)
    game_time = ctx.get("game_time", 0)
    zone = ctx.get("zone_description", "")
    minutes = int(game_time // 60)
    items = ctx.get("items", [])
    items_str = ", ".join(items) if items else "aucun item"
    gold = int(ctx.get("current_gold", 0))
    enemy_jgl = ctx.get("enemy_jungler", "")
    enemy_jgl_kills = ctx.get("enemy_jungler_kills", 0)
    enemy_jgl_cs = ctx.get("enemy_jungler_cs", 0)

    base = f"Partie en cours : {minutes} minutes, rôle {role}, {champ}. Score: {kills}/{deaths}/{assists}, {cs} CS."
    if zone:
        base += f" Position: {zone}."

    prompts = {
        "creepscore_alert": f"{base} Le joueur a {cs} CS à {minutes} minutes. Donne un conseil sur le farm.",
        "ward_score_alert": f"{base} Conseil sur le placement des balises de vision.",
        "back_alert": (
            f"{base} Le joueur a {gold} or et devrait rentrer à la base pour acheter. "
            f"Items actuels : {items_str}. Dis-lui quoi acheter en rentrant. Sois court."
        ),
        "item_buy_advice": (
            f"{base} Le joueur est à la base. Or disponible : {gold}. "
            f"Items actuels : {items_str}. "
            f"Recommande précisément le prochain item ou composant à acheter et pourquoi. Sois direct."
        ),
        "global_strategic_advice": f"{base} Donne un conseil stratégique global pour ce moment de la partie.",
        "death_advice": f"{base} Le joueur vient de mourir. Analyse brève et conseil pour éviter ça.",
        "dragon_death_advice": f"{base} Le dragon vient d'être tué par l'ennemi. Conseil de réaction.",
        "baron_death_advice": f"{base} Le Baron vient d'être tué par l'ennemi. Conseil urgent.",
        "herald_death_advice": f"{base} Le Héraut vient d'être tué. Conseil.",
        "champion_killed_matchup_advice": f"{base} Le joueur vient de tuer un ennemi. Comment en profiter ?",
        "endgame_summary": f"{base} La partie est terminée. Résumé des 2 points principaux à améliorer.",
        "jungler_tracking": (
            f"{base} Le jungler adverse est {enemy_jgl} ({enemy_jgl_kills} kills, {enemy_jgl_cs} CS de jungle). "
            f"En tenant compte du timing de partie ({minutes} min) et de la voie du joueur ({role}), "
            f"estime où se trouve probablement ce jungler et si le joueur risque un gank. "
            f"Conseil de positionnement et de balise. Sois très court (1-2 phrases)."
        ),
        "dragon_next_spawn_alert": _spawn_prompt(base, "dragon", ctx.get("time_until")),
        "baron_next_spawn_alert":  _spawn_prompt(base, "baron",  ctx.get("time_until")),
        "herald_next_spawn_alert": _spawn_prompt(base, "héraut", ctx.get("time_until")),
    }
    return prompts.get(trigger_type, f"{base} Donne un conseil général.")


def _spawn_prompt(base: str, objective: str, time_until: int | None) -> str:
    if time_until is None:
        return f"{base} L'{objective} va bientôt spawner. Conseil de préparation."
    if time_until <= 15:
        return f"{base} L'{objective} spawn dans {time_until} secondes ! Positionnez-vous maintenant."
    if time_until <= 35:
        return f"{base} L'{objective} spawn dans {time_until} secondes. Rappelle à l'équipe de se regrouper."
    mins = time_until // 60
    secs = time_until % 60
    label = f"{mins} minute{'s' if mins > 1 else ''}" + (f" {secs}s" if secs else "")
    return f"{base} L'{objective} spawne dans {label}. Conseil de préparation et de placement."


def _get_fallback_advice(trigger_type: str, ctx: dict) -> str:
    """Conseils statiques si Anthropic n'est pas disponible"""
    fallbacks = {
        "creepscore_alert": "Concentre-toi sur ton farm, chaque CS compte.",
        "ward_score_alert": "N'oublie pas de poser tes wards pour avoir la vision.",
        "back_alert": "Pense à rentrer à la base pour récupérer de la vie et acheter.",
        "global_strategic_advice": "Regarde la minimap et suis les objectifs avec ton équipe.",
        "death_advice": "Analyse ce qui t'a tué et évite cette situation la prochaine fois.",
        "dragon_death_advice": "L'équipe ennemie a le dragon, prépare-toi à contester le prochain.",
        "baron_death_advice": "Baron pris par l'ennemi — défends bien et attends que le buff expire.",
        "herald_death_advice": "Le Herald est pris — cible les tourelles avec ton équipe.",
        "champion_killed_matchup_advice": "Tu as tué ton adversaire, exploite cet avantage maintenant.",
        "endgame_summary": "Belle partie ! Continue à travailler ton farm et ta vision.",
        "dragon_next_spawn_alert": "Le dragon spawn bientôt, prépare ton équipe.",
        "baron_next_spawn_alert": "Le Baron spawn bientôt, posez des balises et rassemblez-vous.",
        "jungler_tracking": "Fais attention au jungler adverse, il pourrait tenter un gank. Warde ta voie.",
    }
    return fallbacks.get(trigger_type, "Continue à jouer proprement.")


# Singleton
assistant = Assistant()
