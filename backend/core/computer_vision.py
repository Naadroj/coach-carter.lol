"""
Computer Vision - Détection de la position sur la minimap
Réplique du module CV d'AMOKK
Utilise PyTorch + OpenCV + dxcam pour capturer et analyser la minimap
"""
import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("amokk.cv")

ASSETS_DIR = Path(__file__).parent.parent / "assets"
MODEL_PATH = ASSETS_DIR / "minimap_detector.pt"
ZONES_DIR = ASSETS_DIR / "minimap_zones"
ZONES_DESC_PATH = ASSETS_DIR / "minimap_zones_descriptions.json"

# Taille de la minimap capturée (pixels)
MINIMAP_SIZE = 210


class MinimapZone:
    """Représente une zone de la minimap avec son polygone en coordonnées UV [0,1]"""

    def __init__(self, name: str, points: list[dict]):
        self.name = name
        # Convertir les points UV en coordonnées pixel
        self.uv_points = [(p["u"], p["v"]) for p in points]

    def contains(self, u: float, v: float) -> bool:
        """Ray casting pour point-in-polygon"""
        x, y = u, v
        n = len(self.uv_points)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = self.uv_points[i]
            xj, yj = self.uv_points[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside


class ComputerVision:
    """
    Capture la minimap toutes les secondes et détecte la position du joueur.
    Utilise le modèle minimap_detector.pt (YOLO ou similaire).
    """

    def __init__(self):
        self._zones: dict[str, MinimapZone] = {}
        self._zones_desc: dict = {}
        self._model = None
        self._camera = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.current_zone: Optional[str] = None
        self.current_zone_description: Optional[str] = None
        self.player_uv: tuple[float, float] = (0.5, 0.5)
        self.enemy_positions: list[tuple[float, float, Optional[str]]] = []
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self):
        """Charge le modèle et les zones (appelé au démarrage)"""
        try:
            self._load_zones()
            self._load_model()
            self._initialized = True
            logger.info("Computer Vision module initialized.")
        except Exception as e:
            logger.warning(f"CV init failed (non-blocking): {e}")

    def _load_zones(self):
        # Charger les descriptions
        if ZONES_DESC_PATH.exists():
            with open(ZONES_DESC_PATH, "r", encoding="utf-8") as f:
                self._zones_desc = json.load(f)

        # Charger les polygones
        for zone_file in ZONES_DIR.glob("*.json"):
            zone_name = zone_file.stem
            try:
                with open(zone_file, "r", encoding="utf-8") as f:
                    points = json.load(f)
                self._zones[zone_name] = MinimapZone(zone_name, points)
            except Exception as e:
                logger.debug(f"Could not load zone {zone_name}: {e}")

        logger.info(f"Minimap zones loaded. ({len(self._zones)} zones)")

    def _load_model(self):
        """Charge le modèle PyTorch de détection de la minimap"""
        try:
            import torch
            if MODEL_PATH.exists():
                self._model = torch.load(str(MODEL_PATH), map_location="cpu", weights_only=False)
                self._model.eval()
                logger.info("Minimap heatmap model loaded.")
            else:
                logger.warning(f"Model not found at {MODEL_PATH}, CV will use fallback")
        except ImportError:
            logger.warning("PyTorch not available, CV disabled")
        except Exception as e:
            logger.warning(f"Model load error: {e}")

    def _init_camera(self):
        """Initialise dxcam pour la capture écran"""
        try:
            import dxcam
            self._camera = dxcam.create(output_color="BGR")
            logger.info("DXCam initialized.")
            return True
        except Exception as e:
            logger.warning(f"DXCam not available: {e}")
            return False

    def start(self):
        if not self._initialized:
            self.initialize()
        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True, name="cv-thread")
        self._thread.start()
        logger.info("Computer Vision update thread started.")

    def stop(self):
        self._running = False

    def _update_loop(self):
        camera_ok = self._init_camera()
        while self._running:
            try:
                if camera_ok and self._camera:
                    self._capture_and_analyze()
            except Exception as e:
                logger.debug(f"CV loop error: {e}")
            import time
            time.sleep(0.5)

    def _capture_and_analyze(self):
        """Capture la minimap et détecte la position du joueur"""
        import numpy as np
        import cv2

        frame = self._camera.grab()
        if frame is None:
            return

        h, w = frame.shape[:2]
        # La minimap est en bas à gauche (~200x200px)
        minimap_size = min(int(h * 0.18), 220)
        minimap = frame[h - minimap_size:h, 0:minimap_size]
        minimap_resized = cv2.resize(minimap, (MINIMAP_SIZE, MINIMAP_SIZE))

        if self._model is not None:
            uv = self._detect_with_model(minimap_resized)
        else:
            uv = self._detect_fallback(minimap_resized)

        enemy_uvs = self._detect_enemies(minimap_resized)
        enemy_positions = [(u, v, self._find_zone(u, v)) for u, v in enemy_uvs]

        with self._lock:
            self.player_uv = uv
            self.current_zone = self._find_zone(uv[0], uv[1])
            self.current_zone_description = self._get_zone_description(
                self.current_zone, team_side="SW"
            )
            self.enemy_positions = enemy_positions

    def _detect_with_model(self, minimap_img) -> tuple[float, float]:
        """Utilise le modèle pour détecter la position (retourne u, v normalisés)"""
        try:
            import torch
            import numpy as np
            import cv2

            img = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0)

            with torch.no_grad():
                output = self._model(tensor)

            if isinstance(output, torch.Tensor):
                # Heatmap → position max
                heatmap = output.squeeze().numpy()
                idx = np.unravel_index(np.argmax(heatmap), heatmap.shape)
                v = idx[0] / heatmap.shape[0]
                u = idx[1] / heatmap.shape[1]
                return (u, v)
        except Exception as e:
            logger.debug(f"Model inference error: {e}")
        return self._detect_fallback(minimap_img)

    def _detect_enemies(self, minimap_img) -> list[tuple[float, float]]:
        """Détecte les icônes ennemies (points rouges) sur la minimap"""
        try:
            import numpy as np
            import cv2

            hsv = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2HSV)
            # Rouge : deux plages dans l'espace HSV
            lower_red1 = np.array([0, 120, 80])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 120, 80])
            upper_red2 = np.array([180, 255, 255])
            mask = cv2.bitwise_or(
                cv2.inRange(hsv, lower_red1, upper_red1),
                cv2.inRange(hsv, lower_red2, upper_red2),
            )
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            positions = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 20 < area < 400:
                    M = cv2.moments(cnt)
                    if M["m00"] > 0:
                        cx = M["m10"] / M["m00"]
                        cy = M["m01"] / M["m00"]
                        positions.append((cx / MINIMAP_SIZE, cy / MINIMAP_SIZE))
            return positions
        except Exception as e:
            logger.debug(f"Enemy detection error: {e}")
            return []

    def _detect_fallback(self, minimap_img) -> tuple[float, float]:
        """Fallback: détection par couleur (point bleu de l'allié)"""
        try:
            import numpy as np
            import cv2

            hsv = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2HSV)
            # Bleu allié
            lower_blue = np.array([100, 100, 100])
            upper_blue = np.array([130, 255, 255])
            mask = cv2.inRange(hsv, lower_blue, upper_blue)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                M = cv2.moments(largest)
                if M["m00"] > 0:
                    cx = M["m10"] / M["m00"]
                    cy = M["m01"] / M["m00"]
                    return (cx / MINIMAP_SIZE, cy / MINIMAP_SIZE)
        except Exception:
            pass
        return (0.5, 0.5)

    def _find_zone(self, u: float, v: float) -> Optional[str]:
        """Trouve la zone contenant le point (u, v)"""
        for name, zone in self._zones.items():
            if zone.contains(u, v):
                return name
        return None

    def _get_zone_description(self, zone_name: Optional[str], team_side: str = "SW") -> Optional[str]:
        if not zone_name or zone_name not in self._zones_desc:
            return None
        zone = self._zones_desc[zone_name]
        key = f"description_{team_side.lower()}"
        desc = zone.get(key, {})
        return desc.get("fr")

    def get_current_zone(self) -> tuple[Optional[str], Optional[str]]:
        with self._lock:
            return self.current_zone, self.current_zone_description

    def get_enemy_positions(self) -> list[tuple[float, float, Optional[str]]]:
        with self._lock:
            return list(self.enemy_positions)

    def get_player_uv(self) -> tuple[float, float]:
        with self._lock:
            return self.player_uv


# Singleton
cv_module = ComputerVision()
