# engine.py  v2
"""
FIRE Engine — Pure Routing Core  v2

Improvements:
- Weighted Round-Robin: if load spread > 3 → always pick least loaded
- Hierarchical VIP fallback: VIP → VIP+no-lang → chief → any → escalation
- Region passed to GeoNormalizer for better geocoding
- City cleaning ("City/City2", "NULL") before geocoding
- Better office substring matching with normalizer
- Track original home office separately from final office in trace
"""

import json
import re
import time
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd

from ai.geo import GeoNormalizer


_CHIEF_POSITION_PATTERNS = (
    "глав",
    "chief",
    "гл. спец",
    "гл спец",
)


def _is_chief(pos_norm: str) -> bool:
    return any(pos_norm.startswith(p) or p in pos_norm for p in _CHIEF_POSITION_PATTERNS)


def _clean_city(raw: str) -> str:
    """Normalize messy city strings from CSV."""
    if not raw:
        return ""
    s = str(raw).strip()
    if s.lower() in ("null", "nan", "none", "-", ""):
        return ""
    s = re.split(r"[/|\\]", s)[0].strip()
    s = re.sub(r"\(.*?\)", "", s).strip()
    return s


def _normalize_segment(segment: str) -> str:
    s = str(segment).strip().upper()
    if s in ("VIP", "ВИП"):
        return "VIP"
    if s in ("PRIORITY", "ПРИОРИТЕТ", "PRIOR"):
        return "PRIORITY"
    return s


class FIREEngine:
    def __init__(
        self,
        tickets_df: pd.DataFrame,
        managers_df: pd.DataFrame,
        units_df: pd.DataFrame,
    ):
        self.geo = GeoNormalizer()

        self.tickets = self._prepare_tickets(tickets_df)
        self.managers = self._prepare_managers(managers_df)
        self.units = self._prepare_units(units_df)

        self.astana_office = self._find_office("астан")
        self.almaty_office = self._find_office("алмат")

        self.rr_counters: Dict[Tuple[str, str], int] = {}
        self.unknown_loc_counter = 0

        # Cache office coords
        self._office_coords: Dict[str, Tuple[float, float]] = {}
        for off in self.units["office"].tolist():
            lat, lon = self.geo.geocode(off)
            if lat is not None:
                self._office_coords[off] = (lat, lon)

    # ──────────────────────────────────────────────────────────────────────────
    # PREPARE
    # ──────────────────────────────────────────────────────────────────────────

    def _prepare_tickets(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower().str.replace("ё", "е")

        rename_map = {
            "guid клиента": "guid", "client_guid": "guid", "id": "guid",
            "населенный пункт": "city", "город": "city",
            "страна": "country",
            "сегмент клиента": "segment", "сегмент": "segment",
            "область": "region",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        required = {"guid", "city", "country", "segment"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Tickets CSV missing columns: {missing}")

        # Clean city and segment
        df["city"] = df["city"].astype(str).apply(_clean_city)
        df["segment"] = df["segment"].astype(str).apply(_normalize_segment)
        df["region"] = df.get("region", pd.Series([""] * len(df))).fillna("").astype(str)
        df["country"] = df["country"].fillna("").astype(str)

        if "lat" in df.columns:
            df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        if "lon" in df.columns:
            df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

        return df

    def _prepare_managers(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower().str.replace("ё", "е")

        rename_map = {
            "фио": "name", "менеджер": "name",
            "должность ": "position", "должность": "position",
            "навыки": "skills", "офис": "office",
            "бизнес-единица": "office",
            "количество обращений в работе": "load",
            "кол-во обращений в работе": "load",
            "нагрузка": "load",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        required = {"name", "position", "skills", "office", "load"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Managers CSV missing columns: {missing}")

        df["load"] = pd.to_numeric(df["load"], errors="coerce").fillna(0).astype(int)
        df["name"] = df["name"].astype(str).str.strip()
        df["office"] = df["office"].astype(str).str.strip()
        df["pos_norm"] = (
            df["position"].astype(str).str.lower()
            .str.replace("ё", "е")
            .str.replace("специалист", "спец")
            .str.strip()
        )
        df["is_chief"] = df["pos_norm"].apply(_is_chief)
        df["skills_set"] = df["skills"].apply(self._parse_skills)
        return df

    def _prepare_units(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower().str.replace("ё", "е")
        rename_map = {"офис": "office", "бизнес-единица": "office", "unit": "office"}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        if "office" not in df.columns:
            raise ValueError("Business Units CSV must contain 'office' column")
        df["office"] = df["office"].astype(str).str.strip()
        return df

    @staticmethod
    def _parse_skills(value: Any) -> set:
        if pd.isna(value):
            return set()
        return {s.strip().upper() for s in str(value).replace(";", ",").split(",") if s.strip()}

    # ──────────────────────────────────────────────────────────────────────────
    # OFFICE LOGIC
    # ──────────────────────────────────────────────────────────────────────────

    def _find_office(self, pattern: str) -> str:
        mask = self.units["office"].str.lower().str.contains(pattern, na=False)
        found = self.units.loc[mask, "office"].values
        return found[0] if len(found) else pattern.capitalize()

    def _nearest_office_by_coords(
        self, lat: float, lon: float, exclude: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[float]]:
        best_office: Optional[str] = None
        best_dist: float = float("inf")
        for office, (olat, olon) in self._office_coords.items():
            if office == exclude:
                continue
            d = self.geo.distance_km(lat, lon, olat, olon)
            if d < best_dist:
                best_dist = d
                best_office = office
        return (best_office, round(best_dist, 2)) if best_office else (None, None)

    def _offices_sorted_by_distance(
        self, lat: float, lon: float
    ) -> List[Tuple[str, float]]:
        result = [
            (office, round(self.geo.distance_km(lat, lon, olat, olon), 2))
            for office, (olat, olon) in self._office_coords.items()
        ]
        result.sort(key=lambda x: x[1])
        return result

    def get_office(
        self, ticket: pd.Series
    ) -> Tuple[str, str, Optional[float]]:
        """Decide home office → (office, reason, distance_km)."""
        country = str(ticket.get("country", "")).lower().strip()
        city_raw = str(ticket.get("city", "")).strip()
        region = str(ticket.get("region", "")).strip()

        # Use pre-cleaned city; also try region for geocoding
        lat = ticket.get("lat")
        lon = ticket.get("lon")

        # 1. Explicit coords in ticket
        if pd.notna(lat) and pd.notna(lon):
            nearest, dist = self._nearest_office_by_coords(float(lat), float(lon))
            if nearest:
                return nearest, "by_coords", dist

        # 2. Geocode city (with region fallback inside GeoNormalizer)
        city_lat, city_lon = self.geo.geocode(city_raw, region)
        if city_lat is not None:
            nearest, dist = self._nearest_office_by_coords(city_lat, city_lon)
            if nearest:
                return nearest, "by_distance", dist

        # 3. Substring match city vs office names
        city_norm = self.geo.normalise(city_raw)
        for off in self.units["office"].tolist():
            off_norm = self.geo.normalise(off)
            if off_norm and city_norm and (off_norm in city_norm or city_norm in off_norm):
                return off, "by_match", None

        # 4. Non-KZ country → 50/50 Astana/Almaty round-robin
        is_kz = "kaz" in country or "каз" in country
        is_unk = country in ("", "nan", "none")
        if not is_kz and not is_unk:
            off = [self.astana_office, self.almaty_office][self.unknown_loc_counter % 2]
            self.unknown_loc_counter += 1
            return off, "50_50", None

        # 5. Default
        return self.astana_office, "default", None

    # ──────────────────────────────────────────────────────────────────────────
    # FILTER + SELECT
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_filters(
        self,
        pool: pd.DataFrame,
        segment: str,
        ai_type: str,
        ai_lang: str,
    ) -> pd.DataFrame:
        s = pool.copy()
        if segment in ("VIP", "PRIORITY"):
            s = s[s["skills_set"].apply(lambda x: "VIP" in x)]
        if ai_type == "Смена данных":
            s = s[s["is_chief"]]
        if ai_lang in ("KZ", "ENG"):
            s = s[s["skills_set"].apply(lambda x: ai_lang in x)]
        return s

    def _select_manager(self, subset: pd.DataFrame, rr_key: tuple) -> pd.Series:
        """
        Weighted Round-Robin:
        - If max-min load spread > 3 → always take least loaded (fair)
        - Otherwise RR among top-2
        """
        subset = subset.copy().sort_values(["load", "name"], kind="mergesort")
        loads = subset["load"].values
        if len(loads) > 1 and (loads.max() - loads.min()) > 3:
            # Large spread — pick least loaded always
            selected = subset.iloc[0]
        else:
            top2 = subset.head(2)
            idx = self.rr_counters.get(rr_key, 0)
            selected = top2.iloc[idx % len(top2)]
            self.rr_counters[rr_key] = idx + 1

        self.managers.at[selected.name, "load"] += 1
        return selected

    def _get_ticket_coords(
        self, ticket: pd.Series
    ) -> Tuple[Optional[float], Optional[float]]:
        lat = ticket.get("lat")
        lon = ticket.get("lon")
        if pd.notna(lat) and pd.notna(lon):
            return float(lat), float(lon)
        city = str(ticket.get("city", ""))
        region = str(ticket.get("region", ""))
        return self.geo.geocode(city, region)

    # ──────────────────────────────────────────────────────────────────────────
    # HIERARCHICAL FALLBACK (especially for VIP)
    # ──────────────────────────────────────────────────────────────────────────

    def _find_nearest_manager(
        self,
        ticket: pd.Series,
        current_office: str,
        segment: str,
        ai_type: str,
        ai_lang: str,
    ) -> Tuple[Optional[pd.Series], Optional[str], Optional[float]]:
        """
        Multi-pass search in nearby offices:
          Pass 1: full filters (VIP + chief + lang)
          Pass 2: VIP + chief, no lang filter
          Pass 3: VIP only (no chief, no lang)
          Pass 4: any manager from nearest office
        """
        lat, lon = self._get_ticket_coords(ticket)

        if lat is None:
            # No coordinates → fallback to Astana or Almaty
            for fallback_off in [self.astana_office, self.almaty_office]:
                if fallback_off == current_office:
                    continue
                pool = self.managers[self.managers["office"] == fallback_off].copy()
                for pass_filters in self._filter_passes(segment, ai_type, ai_lang):
                    sub = pass_filters(pool)
                    if not sub.empty:
                        sel = self._select_manager(sub, (fallback_off, ai_lang))
                        return sel, fallback_off, None
            return None, None, None

        offices_by_dist = self._offices_sorted_by_distance(lat, lon)

        # Run each pass across all offices before degrading to next pass
        for pass_filters in self._filter_passes(segment, ai_type, ai_lang):
            for office, dist in offices_by_dist:
                if office == current_office:
                    continue
                pool = self.managers[self.managers["office"] == office].copy()
                sub = pass_filters(pool)
                if not sub.empty:
                    sel = self._select_manager(sub, (office, ai_lang))
                    return sel, office, dist

        return None, None, None

    def _filter_passes(self, segment: str, ai_type: str, ai_lang: str):
        """
        Generator of filter functions from strictest to most lenient.
        """
        is_vip = segment in ("VIP", "PRIORITY")
        is_chief_required = ai_type == "Смена данных"
        is_lang_required = ai_lang in ("KZ", "ENG")

        def full(pool):
            return self._apply_filters(pool, segment, ai_type, ai_lang)

        def no_lang(pool):
            s = pool.copy()
            if is_vip:
                s = s[s["skills_set"].apply(lambda x: "VIP" in x)]
            if is_chief_required:
                s = s[s["is_chief"]]
            return s

        def vip_only(pool):
            if not is_vip:
                return pool.copy()
            return pool[pool["skills_set"].apply(lambda x: "VIP" in x)].copy()

        def any_manager(pool):
            return pool.copy()

        passes = [full]
        if is_lang_required:
            passes.append(no_lang)
        if is_vip or is_chief_required:
            passes.append(vip_only)
        passes.append(any_manager)

        return passes

    # ──────────────────────────────────────────────────────────────────────────
    # DISTRIBUTE
    # ──────────────────────────────────────────────────────────────────────────

    def distribute(self) -> pd.DataFrame:
        results: List[Dict[str, Any]] = []

        for _, ticket in self.tickets.iterrows():
            t_start = time.time()

            ai_type = ticket.get("ai_type", "Консультация")
            ai_lang = ticket.get("ai_lang", "RU")
            priority = ticket.get("priority", 5)
            segment = ticket.get("segment", "MASS")

            office, office_reason, distance_km = self.get_office(ticket)

            pool = self.managers[self.managers["office"] == office].copy()
            trace: Dict[str, Any] = {
                "home_office":    office,
                "office_reason":  office_reason,
                "distance_km":    distance_km,
                "initial_pool":   int(len(pool)),
            }

            subset = self._apply_filters(pool, segment, ai_type, ai_lang)

            if segment in ("VIP", "PRIORITY"):
                trace["after_vip"] = int(len(subset))
            if ai_type == "Смена данных":
                trace["after_chief"] = int(len(subset))
            if ai_lang in ("KZ", "ENG"):
                trace["after_lang"] = int(len(subset))

            elapsed_ms = int((time.time() - t_start) * 1000)

            if not subset.empty:
                rr_key = (office, ai_lang)
                selected = self._select_manager(subset, rr_key)
                manager_name = selected["name"]
                trace.update({
                    "escalation": False,
                    "selected": manager_name,
                    "routing_ms": elapsed_ms,
                    "top2": subset.sort_values(["load", "name"]).head(2)["name"].tolist(),
                })
                results.append(self._build_row(
                    ticket, ai_type, ai_lang, priority, segment,
                    office, office_reason, distance_km, manager_name, trace
                ))
                continue

            # No suitable manager in home office → search nearby
            trace["escalation_reason"] = "no_suitable_manager_in_home_office"
            near_mgr, near_office, near_dist = self._find_nearest_manager(
                ticket, office, segment, ai_type, ai_lang
            )
            elapsed_ms = int((time.time() - t_start) * 1000)

            if near_mgr is not None:
                manager_name = near_mgr["name"]
                trace.update({
                    "escalation": False,
                    "redirected_to_office": near_office,
                    "redirected_distance_km": near_dist,
                    "selected": manager_name,
                    "routing_ms": elapsed_ms,
                })
                results.append(self._build_row(
                    ticket, ai_type, ai_lang, priority, segment,
                    near_office, "nearest_office", near_dist, manager_name, trace
                ))
            else:
                trace["escalation"] = True
                trace["routing_ms"] = elapsed_ms
                results.append(self._build_row(
                    ticket, ai_type, ai_lang, priority, segment,
                    office, office_reason, distance_km, "CAPITAL_ESCALATION", trace
                ))

        return pd.DataFrame(results)

    @staticmethod
    def _build_row(
        ticket: pd.Series,
        ai_type: str, ai_lang: str, priority: int, segment: str,
        office: str, office_reason: str, distance_km: Optional[float],
        manager: str, trace: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "guid":           ticket["guid"],
            "ai_type":        ai_type,
            "ai_lang":        ai_lang,
            "priority":       priority,
            "sentiment":      ticket.get("sentiment", ""),
            "summary":        ticket.get("summary", ""),
            "recommendation": ticket.get("recommendation", ""),
            "office":         office,
            "office_reason":  office_reason,
            "distance_km":    distance_km,
            "manager":        manager,
            "trace":          json.dumps(trace, ensure_ascii=False),
        }