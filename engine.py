# engine.py
import json
import time
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd

from ai.geo import GeoNormalizer


# ── Нормализованные варианты должности "Главный специалист" ──
# ТЗ говорит "Глав спец", но в реальных данных могут быть вариации
_CHIEF_POSITION_PATTERNS = (
    "глав",        # Глав спец, Главный специалист, Главный спец
    "chief",       # Chief specialist (ENG)
    "гл. спец",    # сокращение
    "гл спец",
)


def _is_chief(pos_norm: str) -> bool:
    """Проверяет, является ли должность "Главным специалистом" в любой форме."""
    return any(pos_norm.startswith(p) or p in pos_norm for p in _CHIEF_POSITION_PATTERNS)


class FIREEngine:
    """
    Pure Routing Core (no NLP inside).

    Expects tickets already enriched with:
        ai_type, ai_lang, priority, sentiment, summary, recommendation
    Optionally:
        lat, lon (from GeoNormalizer in AI layer)
    """

    def __init__(self, tickets_df: pd.DataFrame, managers_df: pd.DataFrame, units_df: pd.DataFrame):
        self.geo = GeoNormalizer()

        self.tickets = self._prepare_tickets(tickets_df)
        self.managers = self._prepare_managers(managers_df)
        self.units = self._prepare_units(units_df)

        self.astana_office = self._find_office("астан")
        self.almaty_office = self._find_office("алмат")

        # Round Robin счётчики: ключ = (office, ai_lang) — достаточно гранулярно
        # НЕ включаем ai_type и segment, иначе RR перестаёт работать как чередование
        self.rr_counters: Dict[Tuple[str, str], int] = {}
        self.unknown_loc_counter = 0

        # cache: office -> (lat, lon)
        self._office_coords: Dict[str, Tuple[float, float]] = {}
        for off in self.units["office"].tolist():
            lat, lon = self.geo.geocode(off)
            if lat is not None and lon is not None:
                self._office_coords[off] = (lat, lon)

    # ============================================================
    # PREPARE DATA
    # ============================================================

    def _prepare_tickets(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower().str.replace("ё", "е")

        rename_map = {
            "guid клиента": "guid",
            "client_guid": "guid",
            "id": "guid",
            "населенный пункт": "city",
            "город": "city",
            "страна": "country",
            "сегмент клиента": "segment",
            "сегмент": "segment",
        }
        df = df.rename(columns=rename_map)

        required = {"guid", "city", "country", "segment"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Tickets CSV missing columns: {missing}")

        if "lat" in df.columns:
            df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        if "lon" in df.columns:
            df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

        # Нормализуем сегмент в верхний регистр — фикс бага с "Priority" vs "PRIORITY"
        if "segment" in df.columns:
            df["segment"] = df["segment"].astype(str).str.strip().str.upper()

        return df

    def _prepare_managers(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower().str.replace("ё", "е")

        rename_map = {
            "фио": "name",
            "менеджер": "name",
            "должность": "position",
            "навыки": "skills",
            "офис": "office",
            "бизнес-единица": "office",
            "количество обращений в работе": "load",
            "кол-во обращений в работе": "load",
            "нагрузка": "load",
        }
        df = df.rename(columns=rename_map)

        required = {"name", "position", "skills", "office", "load"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Managers CSV missing columns: {missing}")

        df["load"] = pd.to_numeric(df["load"], errors="coerce").fillna(0).astype(int)
        df["name"] = df["name"].astype(str).str.strip()
        df["office"] = df["office"].astype(str).str.strip()

        df["pos_norm"] = (
            df["position"]
            .astype(str)
            .str.lower()
            .str.replace("ё", "е")
            .str.replace("специалист", "спец")
            .str.strip()
        )

        # Флаг "главный специалист" через робастную функцию
        df["is_chief"] = df["pos_norm"].apply(_is_chief)

        df["skills_set"] = df["skills"].apply(self._parse_skills)
        return df

    def _prepare_units(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip().str.lower().str.replace("ё", "е")

        rename_map = {
            "офис": "office",
            "бизнес-единица": "office",
            "unit": "office",
        }
        df = df.rename(columns=rename_map)

        if "office" not in df.columns:
            raise ValueError("Business Units CSV must contain 'office' column")

        df["office"] = df["office"].astype(str).str.strip()
        return df

    @staticmethod
    def _parse_skills(value: Any) -> set:
        if pd.isna(value):
            return set()
        return {s.strip().upper() for s in str(value).replace(";", ",").split(",") if s.strip()}

    # ============================================================
    # OFFICE LOGIC
    # ============================================================

    def _find_office(self, pattern: str) -> str:
        mask = self.units["office"].str.lower().str.contains(pattern, na=False)
        found = self.units.loc[mask, "office"].values
        return found[0] if len(found) else pattern.capitalize()

    def _nearest_office_by_coords(self, lat: float, lon: float) -> Tuple[Optional[str], Optional[float]]:
        if not self._office_coords:
            return None, None

        best_office: Optional[str] = None
        best_dist: float = float("inf")

        for office, (olat, olon) in self._office_coords.items():
            d = self.geo.distance_km(lat, lon, olat, olon)
            if d < best_dist:
                best_dist = d
                best_office = office

        if best_office is None:
            return None, None

        return best_office, round(best_dist, 2)

    def _offices_sorted_by_distance(self, lat: float, lon: float) -> List[Tuple[str, float]]:
        """Вернуть все офисы отсортированные по расстоянию от точки (lat, lon)."""
        result = []
        for office, (olat, olon) in self._office_coords.items():
            d = self.geo.distance_km(lat, lon, olat, olon)
            result.append((office, round(d, 2)))
        result.sort(key=lambda x: x[1])
        return result

    def get_office(self, ticket: pd.Series) -> Tuple[str, str, Optional[float]]:
        """Decide office and return (office, reason, distance_km)."""
        country = str(ticket.get("country", "")).lower().strip()
        city_raw = str(ticket.get("city", "")).strip()
        city_norm = self.geo.normalise(city_raw)

        lat = ticket.get("lat")
        lon = ticket.get("lon")

        if pd.notna(lat) and pd.notna(lon):
            nearest, dist = self._nearest_office_by_coords(float(lat), float(lon))
            if nearest:
                return nearest, "by_distance", dist

        city_lat, city_lon = self.geo.geocode(city_norm)
        if city_lat is not None and city_lon is not None:
            nearest, dist = self._nearest_office_by_coords(float(city_lat), float(city_lon))
            if nearest:
                return nearest, "by_distance", dist

        matched_office: Optional[str] = None
        if city_norm:
            for off in self.units["office"].tolist():
                off_norm = self.geo.normalise(off)
                if off_norm and (off_norm in city_norm or city_norm in off_norm):
                    matched_office = off
                    break
        if matched_office:
            return matched_office, "by_match", None

        is_kz = ("kaz" in country) or ("каз" in country)
        is_unknown = country in ["", "nan", "none"]

        if (not is_kz and not is_unknown) or (is_unknown and matched_office is None):
            office = [self.astana_office, self.almaty_office][self.unknown_loc_counter % 2]
            self.unknown_loc_counter += 1
            return office, "50_50", None

        return self.astana_office, "default", None

    # ============================================================
    # FILTER HELPERS
    # ============================================================

    def _apply_filters(self, pool: pd.DataFrame, segment: str, ai_type: str, ai_lang: str) -> pd.DataFrame:
        """Применить VIP / chief / language фильтры к пулу менеджеров."""
        subset = pool

        # segment уже в верхнем регистре после _prepare_tickets
        if segment in ("VIP", "PRIORITY"):
            subset = subset[subset["skills_set"].apply(lambda s: "VIP" in s)]

        # Только Главный специалист — используем робастный флаг is_chief
        if ai_type == "Смена данных":
            subset = subset[subset["is_chief"]]

        if ai_lang in ("KZ", "ENG"):
            subset = subset[subset["skills_set"].apply(lambda s: ai_lang in s)]

        return subset

    def _get_ticket_coords(self, ticket: pd.Series) -> Tuple[Optional[float], Optional[float]]:
        """Получить координаты тикета (из lat/lon или геокодирования города)."""
        lat = ticket.get("lat")
        lon = ticket.get("lon")
        if pd.notna(lat) and pd.notna(lon):
            return float(lat), float(lon)

        city_norm = self.geo.normalise(str(ticket.get("city", "")))
        city_lat, city_lon = self.geo.geocode(city_norm)
        return city_lat, city_lon

    def _select_manager(self, subset: pd.DataFrame, rr_key: tuple) -> pd.Series:
        """
        Round-Robin выбор из топ-2 менеджеров по нагрузке.

        ВАЖНО: rr_key = (office, ai_lang) — НЕ включаем ai_type/segment,
        иначе для каждого типа обращения будет отдельный счётчик и реального
        чередования между менеджерами не происходит.
        """
        subset = subset.sort_values(["load", "name"], kind="mergesort")
        top_2 = subset.head(2)
        rr_idx = self.rr_counters.get(rr_key, 0)
        selected = top_2.iloc[rr_idx % len(top_2)]
        self.rr_counters[rr_key] = rr_idx + 1
        return selected

    # ============================================================
    # NEAREST OFFICE ESCALATION
    # ============================================================

    def _find_nearest_manager(
        self,
        ticket: pd.Series,
        current_office: str,
        segment: str,
        ai_type: str,
        ai_lang: str,
    ) -> Tuple[Optional[pd.Series], Optional[str], Optional[float]]:
        """
        Ищет подходящего менеджера в ближайших офисах (кроме текущего).

        Стратегия:
          1. Перебираем офисы по возрастанию расстояния от тикета
          2. Сначала пробуем с полными фильтрами (VIP + язык + должность)
          3. Если не нашли — берём любого менеджера из ближайшего офиса

        Возвращает (manager_row, office_name, distance_km) или (None, None, None)
        """
        lat, lon = self._get_ticket_coords(ticket)

        if lat is None or lon is None:
            fallback_office = self.astana_office
            if fallback_office == current_office:
                fallback_office = self.almaty_office

            pool = self.managers[self.managers["office"] == fallback_office].copy()
            subset = self._apply_filters(pool, segment, ai_type, ai_lang)
            if subset.empty:
                subset = pool
            if not subset.empty:
                rr_key = (fallback_office, ai_lang)
                selected = self._select_manager(subset, rr_key)
                return selected, fallback_office, None
            return None, None, None

        offices_by_dist = self._offices_sorted_by_distance(lat, lon)

        # Проход 1: с полными фильтрами
        for office, dist in offices_by_dist:
            if office == current_office:
                continue
            pool = self.managers[self.managers["office"] == office].copy()
            subset = self._apply_filters(pool, segment, ai_type, ai_lang)
            if not subset.empty:
                rr_key = (office, ai_lang)
                selected = self._select_manager(subset, rr_key)
                return selected, office, dist

        # Проход 2: без фильтров (любой менеджер из ближайшего офиса)
        for office, dist in offices_by_dist:
            if office == current_office:
                continue
            pool = self.managers[self.managers["office"] == office].copy()
            if not pool.empty:
                rr_key = (office, ai_lang)
                selected = self._select_manager(pool, rr_key)
                return selected, office, dist

        return None, None, None

    # ============================================================
    # DISTRIBUTION
    # ============================================================

    def distribute(self) -> pd.DataFrame:
        results: List[Dict[str, Any]] = []

        for _, ticket in self.tickets.iterrows():
            t_start = time.time()

            ai_type   = ticket["ai_type"]
            ai_lang   = ticket["ai_lang"]
            priority  = ticket["priority"]
            segment   = ticket["segment"]

            office, office_reason, distance_km = self.get_office(ticket)

            pool = self.managers[self.managers["office"] == office].copy()
            trace: Dict[str, Any] = {
                "office": office,
                "office_reason": office_reason,
                "distance_km": distance_km,
                "initial_pool": int(len(pool)),
            }

            subset = self._apply_filters(pool, segment, ai_type, ai_lang)

            # Трейс фильтров
            if segment in ("VIP", "PRIORITY"):
                trace["after_vip"] = int(len(subset))
            if ai_type == "Смена данных":
                trace["after_chief"] = int(len(subset))
            if ai_lang in ("KZ", "ENG"):
                trace["after_lang"] = int(len(subset))

            # ── Менеджер найден в своём офисе ──────────────────────
            if not subset.empty:
                # RR-ключ = (office, ai_lang) — чтобы реальное чередование работало
                rr_key = (office, ai_lang)
                selected = self._select_manager(subset, rr_key)
                manager_name = selected["name"]
                self.managers.at[selected.name, "load"] += 1

                elapsed_ms = int((time.time() - t_start) * 1000)
                trace.update({
                    "escalation": False,
                    "rr_index": self.rr_counters.get(rr_key, 1) - 1,
                    "top2": subset.sort_values(["load", "name"]).head(2)["name"].tolist(),
                    "selected": manager_name,
                    "routing_ms": elapsed_ms,
                })

                results.append(self._build_row(ticket, ai_type, ai_lang, priority, segment,
                                               office, office_reason, distance_km,
                                               manager_name, trace))
                continue

            # ── Своего офиса нет → ищем ближайший ──────────────────
            trace["escalation_reason"] = "no_suitable_manager_in_home_office"

            near_manager, near_office, near_dist = self._find_nearest_manager(
                ticket, office, segment, ai_type, ai_lang
            )

            elapsed_ms = int((time.time() - t_start) * 1000)

            if near_manager is not None:
                manager_name = near_manager["name"]
                self.managers.at[near_manager.name, "load"] += 1

                trace.update({
                    "escalation": False,
                    "redirected_to_office": near_office,
                    "redirected_distance_km": near_dist,
                    "selected": manager_name,
                    "routing_ms": elapsed_ms,
                })

                results.append(self._build_row(ticket, ai_type, ai_lang, priority, segment,
                                               near_office, "nearest_office", near_dist,
                                               manager_name, trace))
            else:
                # Абсолютная эскалация — нет никого нигде
                trace["escalation"] = True
                trace["routing_ms"] = elapsed_ms
                results.append(self._build_row(ticket, ai_type, ai_lang, priority, segment,
                                               office, office_reason, distance_km,
                                               "CAPITAL_ESCALATION", trace))

        return pd.DataFrame(results)

    # ============================================================
    # HELPERS
    # ============================================================

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