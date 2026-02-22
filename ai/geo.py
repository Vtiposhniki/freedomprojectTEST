# ai/geo.py
"""
Offline geo-normalization + distance utilities.

Goal:
- Work without any external APIs
- Deterministic behavior
- Robust to messy city strings (prefixes, punctuation, kazakh letters, aliases)

Public API:
- GeoNormalizer.normalise(text: str) -> str
- GeoNormalizer.geocode(city: str) -> (lat, lon) or (None, None)
- GeoNormalizer.distance_km(lat1, lon1, lat2, lon2) -> float
- GeoNormalizer.nearest_office_by_city(city: str, office_names: list[str]) -> (office, dist_km) or (None, None)
"""

from __future__ import annotations

import math
import re
from typing import Final, Optional, Tuple


# ---------------------------------------------------------------------
# Canonical coordinates (WGS84).
# Keys MUST be normalized strings produced by GeoNormalizer.normalise().
# ---------------------------------------------------------------------

CITY_COORDS: Final[dict[str, tuple[float, float]]] = {
    # Core
    "астана": (51.1694, 71.4491),
    "алматы": (43.2389, 76.8897),
    "шымкент": (42.3417, 69.5901),
    "караганда": (49.8060, 73.0850),

    # East / North / West / South
    "усть-каменогорск": (49.9483, 82.6275),
    "семей": (50.4111, 80.2275),
    "павлодар": (52.2870, 76.9674),
    "костанай": (53.2145, 63.6246),
    "кокшетау": (53.2833, 69.3833),
    "петропавловск": (54.8753, 69.1620),
    "орал": (51.2333, 51.3667),
    "атырау": (47.1167, 51.8833),
    "актау": (43.6532, 51.1975),
    "актобе": (50.2839, 57.1660),
    "тараз": (42.9000, 71.3667),
    "кызылорда": (44.8528, 65.5092),
}

# Aliases: normalized -> canonical normalized key
ALIASES: Final[dict[str, str]] = {
    # Astana variants
    "нур-султан": "астана",
    "нурсултан": "астана",
    "nur-sultan": "астана",
    "nur sultan": "астана",
    "astana": "астана",

    # Almaty
    "almaty": "алматы",

    # Shymkent
    "shymkent": "шымкент",

    # Oskemen / Ust-Kamenogorsk
    "oskemen": "усть-каменогорск",
    "oскемен": "усть-каменогорск",
    "өскемен": "усть-каменогорск",
    "ust-kamenogorsk": "усть-каменогорск",
    "ust kamenogorsk": "усть-каменогорск",
    "усть каменогорск": "усть-каменогорск",
    "устькаменогорск": "усть-каменогорск",

    # Common latin spellings
    "karaganda": "караганда",
    "pavlodar": "павлодар",
    "kostanay": "костанай",
    "kokshetau": "кокшетау",
    "petropavlovsk": "петропавловск",
    "atyrau": "атырау",
    "aktau": "актау",
    "aktobe": "актобе",
    "taraz": "тараз",
    "kyzylorda": "кызылорда",

    # ✅ ФИКС: Уральск — официальное русское название города Орал
    "уральск": "орал",
    "oral": "орал",
    "uralsk": "орал",
}


class GeoNormalizer:
    """Offline geocoder and distance helper."""

    _PREFIX_RE: Final[re.Pattern] = re.compile(r"^\s*(г\.|город|city)\s+", re.IGNORECASE)
    _SPACES_RE: Final[re.Pattern] = re.compile(r"\s+")
    _DASH_SPACES_RE: Final[re.Pattern] = re.compile(r"\s*-\s*")
    _TRASH_RE: Final[re.Pattern] = re.compile(r"[^0-9a-zA-Zа-яА-ЯёЁ\-\s]", re.IGNORECASE)

    def normalise(self, text: str) -> str:
        """Normalize a city/office name into a stable comparable key."""
        if not text:
            return ""

        s = str(text).strip().lower()

        # remove prefixes
        s = self._PREFIX_RE.sub("", s)

        # normalize punctuation
        s = s.replace("—", "-").replace("–", "-")
        s = self._TRASH_RE.sub(" ", s)
        s = self._DASH_SPACES_RE.sub("-", s)
        s = self._SPACES_RE.sub(" ", s).strip()

        # unify ё -> е
        s = s.replace("ё", "е")

        # minimal kazakh-to-russian letter normalization (reduce mismatches)
        s = (
            s.replace("қ", "к")
             .replace("ө", "о")
             .replace("ү", "у")
             .replace("ұ", "у")
             .replace("ә", "а")
             .replace("ң", "н")
             .replace("ғ", "г")
             .replace("һ", "х")
             .replace("і", "и")
        )

        return s

    def geocode(self, city: str) -> Tuple[Optional[float], Optional[float]]:
        """Return (lat, lon) if city is known, else (None, None)."""
        key = self.normalise(city)
        if not key:
            return None, None

        # exact
        if key in CITY_COORDS:
            return CITY_COORDS[key]

        # alias
        alias = ALIASES.get(key)
        if alias and alias in CITY_COORDS:
            return CITY_COORDS[alias]

        # fuzzy (substring) – conservative
        for known_key, coords in CITY_COORDS.items():
            if known_key in key or key in known_key:
                return coords

        return None, None

    @staticmethod
    def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in kilometers."""
        r = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
        )
        return 2.0 * r * math.asin(math.sqrt(a))

    def nearest_office_by_city(
        self,
        city: str,
        office_names: list[str],
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        Find nearest office (by distance) given a ticket city and list of office names.

        Returns:
            (office_name, distance_km) or (None, None) if cannot geocode.
        """
        lat, lon = self.geocode(city)
        if lat is None or lon is None:
            return None, None

        best_office: Optional[str] = None
        best_dist: float = float("inf")

        for office in office_names:
            off_lat, off_lon = self.geocode(office)
            if off_lat is None or off_lon is None:
                continue

            d = self.distance_km(lat, lon, off_lat, off_lon)
            if d < best_dist:
                best_dist = d
                best_office = office

        if best_office is None:
            return None, None

        return best_office, round(best_dist, 2)