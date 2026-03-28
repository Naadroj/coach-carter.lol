"""
Triggerer - Système de déclenchement des alertes de coaching
Polling toutes les 5 secondes.
Spawn alerts : alertes escaladées (2 min → 1 min → 30 s → 10 s avant spawn).
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("amokk.triggerer")

TRIGGERS_PATH = Path(__file__).parent.parent / "assets" / "triggers.json"
POLL_INTERVAL = 5.0  # secondes entre chaque évaluation
EVENT_WINDOW  = 8.0  # fenêtre de détection d'événements (> POLL_INTERVAL)


# ── Phases d'alerte spawn par défaut ─────────────────────────────────────────

DEFAULT_SPAWN_PHASES = [120, 60, 30, 10]   # secondes avant le spawn


class SpawnPhaseTracker:
    """
    Suit les alertes multi-phases pour un objectif donné.
    Exemple : alerte à 120 s, puis 60 s, puis 30 s, puis 10 s avant le spawn.
    Se réinitialise automatiquement à chaque nouveau cycle de spawn.
    """

    def __init__(self, phases: list[int] | None = None):
        self.phases: list[int] = sorted(phases or DEFAULT_SPAWN_PHASES, reverse=True)
        self.enabled: bool = True
        self._alerted: set[int] = set()
        self._tracked_spawn: float = -1.0

    def check(self, time_until: float | None, next_spawn: float) -> int | None:
        """
        Retourne le seuil de phase (en secondes) qui doit déclencher une alerte,
        ou None si aucune alerte n'est due.
        """
        if not self.enabled or time_until is None or time_until <= 0:
            return None

        # Nouveau cycle de spawn → réinitialiser les phases alertées
        if next_spawn != self._tracked_spawn:
            self._alerted = set()
            self._tracked_spawn = next_spawn

        for phase in self.phases:
            if time_until <= phase and phase not in self._alerted:
                self._alerted.add(phase)
                return phase
        return None


# ── TriggerState ─────────────────────────────────────────────────────────────

class TriggerState:
    """Suit l'état d'un trigger individuel (cooldowns, dernière activation)"""

    def __init__(self, config: dict):
        self.first_cooldown: float = config.get("first_cooldown", 0)
        self.cooldown: float       = config.get("cooldown", 300)
        self.expiration: float     = config.get("expiration", 1_000_000)
        self.blockers: list[str]   = config.get("blockers", [])
        self.enabled: bool         = True
        self._last_fired: float    = -1_000_000
        self._fired_count: int     = 0

    def can_fire(self, game_time: float, conditions: dict) -> bool:
        if not self.enabled:
            return False
        if game_time > self.expiration:
            return False
        elapsed  = game_time - self._last_fired
        required = self.first_cooldown if self._fired_count == 0 else self.cooldown
        if elapsed < required:
            return False
        for blocker in self.blockers:
            if conditions.get(blocker, False):
                return False
        return True

    def mark_fired(self, game_time: float):
        self._last_fired   = game_time
        self._fired_count += 1


# ── Triggerer principal ───────────────────────────────────────────────────────

class Triggerer:
    """
    Évalue en continu les conditions de jeu et déclenche les alertes appropriées.
    Polling toutes les POLL_INTERVAL secondes.
    """

    def __init__(self):
        self._triggers_config: dict = {}
        self._trigger_states: dict[str, dict[str, TriggerState]] = {}
        self._running: bool   = False
        self._task: Optional[asyncio.Task] = None

        # Modules injectés
        self._assistant         = None
        self._game_tracker      = None
        self._objectives_tracker = None
        self._cv_module         = None

        # Phases d'alerte spawn (une instance par objectif)
        self._spawn_phases: dict[str, SpawnPhaseTracker] = {
            "dragon": SpawnPhaseTracker(),
            "baron":  SpawnPhaseTracker(),
            "herald": SpawnPhaseTracker(),
        }

        self._load_triggers()
        logger.info("Triggerer initialized (poll=%.0fs).", POLL_INTERVAL)

    # ── Chargement ────────────────────────────────────────────────────────────

    def _load_triggers(self):
        with open(TRIGGERS_PATH, "r", encoding="utf-8") as f:
            self._triggers_config = json.load(f)
        for role, triggers in self._triggers_config.items():
            self._trigger_states[role] = {}
            for name, cfg in triggers.items():
                self._trigger_states[role][name] = TriggerState(cfg)

    def inject_dependencies(self, assistant, game_tracker, objectives_tracker, cv_module):
        self._assistant          = assistant
        self._game_tracker       = game_tracker
        self._objectives_tracker = objectives_tracker
        self._cv_module          = cv_module

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._evaluation_loop())
        logger.info("Triggerer evaluation loop started.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    # ── Boucle principale ─────────────────────────────────────────────────────

    async def _evaluation_loop(self):
        while self._running:
            try:
                await self._evaluate()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Triggerer error: %s", e)
            await asyncio.sleep(POLL_INTERVAL)

    async def _evaluate(self):
        if not self._game_tracker:
            return
        state = self._game_tracker.get_state()
        if not state.active:
            return

        game_time  = state.game_time
        role       = state.player.role if state.player.role in self._trigger_states else "MIDDLE"
        conditions = self._build_conditions(state)

        # 1. Alertes spawn escaladées (logique dédiée)
        await self._evaluate_spawn_phases(state, role, conditions)

        # 2. Tous les autres triggers (cooldown classique)
        _spawn_obj_map = {
            "dragon_next_spawn_alert": "dragon",
            "baron_next_spawn_alert":  "baron",
            "herald_next_spawn_alert": "herald",
        }
        for name, ts in self._trigger_states.get(role, {}).items():
            if ts.can_fire(game_time, conditions):
                if await self._check_trigger_condition(name, state, conditions):
                    extra = None
                    if name in _spawn_obj_map:
                        t_until = self._time_until(_spawn_obj_map[name], game_time)
                        if t_until is not None:
                            extra = {"time_until": int(t_until)}
                    ts.mark_fired(game_time)
                    await self._fire_trigger(name, state, extra=extra)

    # ── Phases spawn ──────────────────────────────────────────────────────────

    async def _evaluate_spawn_phases(self, state, role: str, conditions: dict):
        """
        Vérifie chaque objectif et déclenche une alerte si on vient de passer
        un seuil de phase (120 s, 60 s, 30 s, 10 s avant le spawn).
        """
        if not self._objectives_tracker:
            return
        if conditions.get("is_allied_base_collapsing"):
            return

        game_time = state.game_time

        obj_map = [
            ("dragon", "dragon_next_spawn_alert", state.objectives.dragon_next_spawn),
            ("baron",  "baron_next_spawn_alert",  state.objectives.baron_next_spawn),
            ("herald", "herald_next_spawn_alert", state.objectives.herald_next_spawn),
        ]

        for obj_name, trigger_name, next_spawn in obj_map:
            # Vérifier que le trigger est activé pour ce rôle
            ts = self._trigger_states.get(role, {}).get(trigger_name)
            if ts and not ts.enabled:
                continue

            phase_tracker = self._spawn_phases[obj_name]
            time_until    = self._time_until(obj_name, game_time)
            phase         = phase_tracker.check(time_until, next_spawn)

            if phase is not None:
                logger.info("Spawn phase alert: %s in %ds (phase=%ds)", obj_name, int(time_until), phase)
                await self._fire_trigger(trigger_name, state, extra={"time_until": int(time_until)})

    def _time_until(self, objective: str, game_time: float) -> float | None:
        if not self._objectives_tracker:
            return None
        if objective == "dragon":
            return self._objectives_tracker.time_until_dragon(game_time)
        if objective == "baron":
            return self._objectives_tracker.time_until_baron(game_time)
        if objective == "herald":
            return self._objectives_tracker.time_until_herald(game_time)
        return None

    # ── Conditions ────────────────────────────────────────────────────────────

    def _build_conditions(self, state) -> dict:
        # Seuil pour back_alert : composant minimal ~500 or (Long Sword, Doran, etc.)
        GOLD_COMPONENT_THRESHOLD = 500
        return {
            "is_player_in_teamfight":             state.is_in_teamfight,
            "is_late_game":                       state.is_late_game,
            "is_allied_base_collapsing":          state.is_allied_base_collapsing,
            "is_any_build_completed":             state.any_build_completed,
            "is_player_champion_dead":            state.player.is_dead,
            "is_last_objective_death_advice_recent": (
                state.game_time - state.last_objective_advice_time < 120
            ),
            "is_ward_absent_from_player_inventory": not any(
                "ward" in (item.get("displayName", "") or "").lower()
                for item in state.player.items
            ),
            # back_alert : bloquer si pas assez d'or pour acheter un composant
            "is_not_enough_gold_for_back": state.player.current_gold < GOLD_COMPONENT_THRESHOLD,
        }

    async def _check_trigger_condition(self, trigger_name: str, state, conditions: dict) -> bool:
        t = state.game_time

        event_triggers = {
            "death_advice":                     lambda: (t - state.last_death_time) < EVENT_WINDOW,
            "dragon_death_advice":              lambda: self._recent_event(state, "DragonKill",    EVENT_WINDOW, allied=False),
            "baron_death_advice":               lambda: self._recent_event(state, "BaronKill",     EVENT_WINDOW, allied=False),
            "herald_death_advice":              lambda: self._recent_event(state, "HeraldKill",    EVENT_WINDOW, allied=False),
            "champion_killed_matchup_advice":   lambda: self._recent_event(state, "ChampionKill",  EVENT_WINDOW, by_player=True),
            "first_turret_killed_on_lane_advice": lambda: self._recent_event(state, "TurretKilled", EVENT_WINDOW),
            "endgame_summary":                  lambda: self._recent_event(state, "GameEnd",       60),
        }

        periodic_triggers = {
            "creepscore_alert", "ward_score_alert", "back_alert", "global_strategic_advice",
        }

        if trigger_name in ("dragon_next_spawn_alert", "baron_next_spawn_alert", "herald_next_spawn_alert"):
            _obj_map = {
                "dragon_next_spawn_alert": "dragon",
                "baron_next_spawn_alert":  "baron",
                "herald_next_spawn_alert": "herald",
            }
            t_until = self._time_until(_obj_map[trigger_name], state.game_time)
            # < 120s : les phases escaladées gèrent cette fenêtre
            return t_until is not None and t_until > 120

        if trigger_name == "item_buy_advice":
            zone_name = None
            if self._cv_module:
                zone_name, _ = self._cv_module.get_current_zone()
            return zone_name is not None and "base" in zone_name.lower()

        if trigger_name == "dead_reminder":
            return state.player.is_dead

        if trigger_name == "base_reminder":
            if self._cv_module:
                zone_name, _ = self._cv_module.get_current_zone()
                return zone_name is not None and "base" in zone_name.lower()
            return False

        if trigger_name == "jungler_tracking":
            # Ne déclencher que si le jungler adverse est connu ET visible sur la minimap
            if not bool(state.objectives.enemy_jungler_champion):
                return False
            if self._cv_module:
                enemy_positions = self._cv_module.get_enemy_positions()
                return len(enemy_positions) > 0
            return False

        if trigger_name in event_triggers:
            return event_triggers[trigger_name]()
        if trigger_name in periodic_triggers:
            return True
        return True

    def _recent_event(self, state, event_name: str, window: float,
                      allied: bool = True, by_player: bool = False) -> bool:
        t = state.game_time
        for event in reversed(state.events[-20:]):
            if event.get("EventName") == event_name:
                if t - event.get("EventTime", 0) <= window:
                    if by_player:
                        return event.get("KillerName") == state.player.name
                    return True
        return False

    # ── Fire ─────────────────────────────────────────────────────────────────

    async def _fire_trigger(self, trigger_name: str, state, extra: dict | None = None):
        logger.info("Firing trigger: %s (role=%s, t=%.0fs)", trigger_name, state.player.role, state.game_time)

        zone_name, zone_desc = (None, None)
        if self._cv_module:
            zone_name, zone_desc = self._cv_module.get_current_zone()

        enemy_jungler_visible_zone = None
        if trigger_name == "jungler_tracking" and self._cv_module:
            enemy_positions = self._cv_module.get_enemy_positions()
            if enemy_positions:
                enemy_jungler_visible_zone = enemy_positions[0][2]

        context = {
            "role":             state.player.role,
            "champion":         state.player.champion,
            "cs":               state.player.cs,
            "kills":            state.player.kills,
            "deaths":           state.player.deaths,
            "assists":          state.player.assists,
            "game_time":        state.game_time,
            "zone_name":        zone_name,
            "zone_description": zone_desc,
            "items":            [i.get("displayName", "") for i in state.player.items if i.get("displayName")],
            "current_gold":     state.player.current_gold,
            "enemy_jungler":             state.objectives.enemy_jungler_champion,
            "enemy_jungler_kills":        state.objectives.enemy_jungler_kills,
            "enemy_jungler_cs":           state.objectives.enemy_jungler_cs,
            "enemy_jungler_visible_zone": enemy_jungler_visible_zone,
        }
        if extra:
            context.update(extra)

        if self._assistant:
            text = await self._assistant.generate_coaching_advice(trigger_name, context)
            await self._assistant.say(text)

        if "objective" in trigger_name:
            state.last_objective_advice_time = state.game_time

    # ── API config ────────────────────────────────────────────────────────────

    def get_config(self) -> list[dict]:
        """Retourne la config de tous les triggers (dédupliqués) + phases spawn"""
        seen: dict[str, dict] = {}
        for role, triggers in self._trigger_states.items():
            for name, ts in triggers.items():
                if name not in seen:
                    seen[name] = {
                        "name":     name,
                        "enabled":  ts.enabled,
                        "cooldown": int(ts.cooldown),
                    }
        # Ajouter les phases spawn dans les triggers concernés
        for obj_name, trigger_name in [
            ("dragon", "dragon_next_spawn_alert"),
            ("baron",  "baron_next_spawn_alert"),
            ("herald", "herald_next_spawn_alert"),
        ]:
            if trigger_name in seen:
                tracker = self._spawn_phases[obj_name]
                seen[trigger_name]["spawn_phases"] = tracker.phases
                seen[trigger_name]["enabled"]      = tracker.enabled

        return list(seen.values())

    def update_config(self, name: str, enabled: bool | None = None,
                      cooldown: int | None = None, spawn_phases: list[int] | None = None):
        """Met à jour un trigger sur tous les rôles"""
        # Mise à jour des phases spawn si trigger spawn
        spawn_map = {
            "dragon_next_spawn_alert": "dragon",
            "baron_next_spawn_alert":  "baron",
            "herald_next_spawn_alert": "herald",
        }
        if name in spawn_map:
            tracker = self._spawn_phases[spawn_map[name]]
            if enabled is not None:
                tracker.enabled = enabled
            if spawn_phases:
                tracker.phases = sorted(spawn_phases, reverse=True)
            logger.info("Spawn phases '%s' updated: enabled=%s, phases=%s", name, enabled, spawn_phases)

        # Mise à jour des TriggerStates (cooldown / enabled)
        updated = False
        for role, triggers in self._trigger_states.items():
            if name in triggers:
                ts = triggers[name]
                if enabled is not None:
                    ts.enabled = enabled
                if cooldown is not None:
                    ts.cooldown = float(cooldown)
                updated = True
        if not updated:
            logger.warning("Trigger inconnu: %s", name)
        else:
            logger.info("Trigger '%s' mis à jour: enabled=%s, cooldown=%s", name, enabled, cooldown)

    def get_spawn_phases(self) -> dict[str, list[int]]:
        return {obj: t.phases for obj, t in self._spawn_phases.items()}


# Singleton
triggerer = Triggerer()
