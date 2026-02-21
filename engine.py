# engine.py
import json
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd

from ai.geo import GeoNormalizer


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

        self.rr_counters: Dict[Tuple[str, str, str, str], int] = {}
        self.unknown_loc_counter = 0

        # cache: office -> (lat, lon) if known
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

        # Optional: lat/lon (already enriched by AI layer)
        # If absent, we'll geocode by city inside get_office().
        if "lat" in df.columns:
            df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        if "lon" in df.columns:
            df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

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
        """
        Return nearest office name and distance_km by haversine using cached office coords.
        """
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

    def get_office(self, ticket: pd.Series) -> Tuple[str, str, Optional[float]]:
        """
        Decide office and return (office, reason, distance_km).
        reason:
            by_distance  - chosen by coordinates/haversine
            by_match     - chosen by substring match in office name
            50_50        - fallback for unknown location
            default      - fallback to astana when kz but unknown city match
        """
        country = str(ticket.get("country", "")).lower().strip()
        city_raw = str(ticket.get("city", "")).strip()
        city_norm = self.geo.normalise(city_raw)

        # 1) If ticket has coordinates -> choose nearest office by distance
        lat = ticket.get("lat")
        lon = ticket.get("lon")

        if pd.notna(lat) and pd.notna(lon):
            nearest, dist = self._nearest_office_by_coords(float(lat), float(lon))
            if nearest:
                return nearest, "by_distance", dist

        # 2) If no coords -> try geocode by city
        city_lat, city_lon = self.geo.geocode(city_norm)
        if city_lat is not None and city_lon is not None:
            nearest, dist = self._nearest_office_by_coords(float(city_lat), float(city_lon))
            if nearest:
                return nearest, "by_distance", dist

        # 3) substring match office name in city text
        matched_office: Optional[str] = None
        if city_norm:
            for off in self.units["office"].tolist():
                off_norm = self.geo.normalise(off)
                if off_norm and (off_norm in city_norm or city_norm in off_norm):
                    matched_office = off
                    break
        if matched_office:
            return matched_office, "by_match", None

        # 4) 50/50 for unknown or non-KZ
        is_kz = ("kaz" in country) or ("каз" in country)
        is_unknown = country in ["", "nan", "none"]

        if (not is_kz and not is_unknown) or (is_unknown and matched_office is None):
            office = [self.astana_office, self.almaty_office][self.unknown_loc_counter % 2]
            self.unknown_loc_counter += 1
            return office, "50_50", None

        # default for KZ but no match
        return self.astana_office, "default", None

    # ============================================================
    # DISTRIBUTION
    # ============================================================

    def distribute(self) -> pd.DataFrame:
        results: List[Dict[str, Any]] = []

        for _, ticket in self.tickets.iterrows():
            ai_type = ticket["ai_type"]
            ai_lang = ticket["ai_lang"]
            priority = ticket["priority"]
            segment = ticket["segment"]

            office, office_reason, distance_km = self.get_office(ticket)

            pool = self.managers[self.managers["office"] == office].copy()
            trace: Dict[str, Any] = {
                "office": office,
                "office_reason": office_reason,
                "distance_km": distance_km,
                "initial_pool": int(len(pool)),
            }

            subset = pool

            # VIP / PRIORITY filter
            if segment in ["VIP", "PRIORITY"]:
                subset = subset[subset["skills_set"].apply(lambda s: "VIP" in s)]
                trace["after_vip"] = int(len(subset))

            # Chief specialist for data change
            if ai_type == "Смена данных":
                subset = subset[
                    subset["pos_norm"].str.contains("глав") &
                    subset["pos_norm"].str.contains("спец")
                ]
                trace["after_chief"] = int(len(subset))

            # Language filter
            if ai_lang in ["KZ", "ENG"]:
                subset = subset[subset["skills_set"].apply(lambda s: ai_lang in s)]
                trace["after_lang"] = int(len(subset))

            # Escalation
            if subset.empty:
                results.append({
                    "guid": ticket["guid"],
                    "ai_type": ai_type,
                    "ai_lang": ai_lang,
                    "priority": priority,
                    "sentiment": ticket.get("sentiment", ""),
                    "summary": ticket.get("summary", ""),
                    "recommendation": ticket.get("recommendation", ""),
                    "office": office,
                    "office_reason": office_reason,
                    "distance_km": distance_km,
                    "manager": "CAPITAL_ESCALATION",
                    "trace": json.dumps({**trace, "escalation": True}, ensure_ascii=False),
                })
                continue

            subset = subset.sort_values(["load", "name"], kind="mergesort")
            top_2 = subset.head(2)

            rr_key = (office, segment, ai_type, ai_lang)
            rr_idx = self.rr_counters.get(rr_key, 0)

            selected = top_2.iloc[rr_idx % len(top_2)]
            self.rr_counters[rr_key] = rr_idx + 1

            manager_name = selected["name"]
            self.managers.at[selected.name, "load"] += 1

            trace.update({
                "escalation": False,
                "rr_index": rr_idx,
                "top2": top_2["name"].tolist(),
                "selected": manager_name,
            })

            results.append({
                "guid": ticket["guid"],
                "ai_type": ai_type,
                "ai_lang": ai_lang,
                "priority": priority,
                "sentiment": ticket.get("sentiment", ""),
                "summary": ticket.get("summary", ""),
                "recommendation": ticket.get("recommendation", ""),
                "office": office,
                "office_reason": office_reason,
                "distance_km": distance_km,
                "manager": manager_name,
                "trace": json.dumps(trace, ensure_ascii=False),
            })

        return pd.DataFrame(results)