# -*- coding: utf-8 -*-
"""
Administrative Divisions Service — Provider Pattern.

Reads hierarchical data (governorate → district → subdistrict → community)
from local JSON file. Ready for future migration to Backend API.

Usage:
    service = DivisionsService()
    governorates = service.get_governorates()
    districts = service.get_districts("01")  # Aleppo
    subdistricts = service.get_subdistricts("01", "03")  # Al-Bab
    communities = service.get_communities("01", "03", "02")  # Tadef
"""

import json
from pathlib import Path
from typing import List, Tuple, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class DivisionsService:
    """Administrative divisions data provider (local JSON → future API)."""

    _instance = None
    _data = None

    def __new__(cls):
        """Singleton — load JSON once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._data is None:
            self._load_data()

    def _load_data(self):
        """Load administrative divisions from JSON file."""
        try:
            data_file = Path(__file__).parent.parent / "data" / "administrative_divisions.json"
            with open(data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._data = raw.get("governorates", [])
            logger.info(f"Loaded {len(self._data)} governorates from {data_file.name}")
        except Exception as e:
            logger.error(f"Failed to load administrative divisions: {e}")
            self._data = []

    def get_governorates(self) -> List[Tuple[str, str, str]]:
        """Get all governorates as [(code, name_en, name_ar)]."""
        return [
            (g["code"], g["name_en"], g["name_ar"])
            for g in self._data
        ]

    def get_districts(self, gov_code: str) -> List[Tuple[str, str, str]]:
        """Get districts for a governorate as [(code, name_en, name_ar)]."""
        for g in self._data:
            if g["code"] == gov_code:
                return [
                    (d["code"], d["name_en"], d["name_ar"])
                    for d in g.get("districts", [])
                ]
        return []

    def get_subdistricts(self, gov_code: str, dist_code: str) -> List[Tuple[str, str, str]]:
        """Get subdistricts for a district as [(code, name_en, name_ar)]."""
        for g in self._data:
            if g["code"] == gov_code:
                for d in g.get("districts", []):
                    if d["code"] == dist_code:
                        return [
                            (s["code"], s["name_en"], s["name_ar"])
                            for s in d.get("subdistricts", [])
                        ]
        return []

    def get_communities(self, gov_code: str, dist_code: str, subdist_code: str) -> List[Tuple[str, str, str]]:
        """Get communities for a subdistrict as [(code, name_en, name_ar)]."""
        for g in self._data:
            if g["code"] == gov_code:
                for d in g.get("districts", []):
                    if d["code"] == dist_code:
                        for s in d.get("subdistricts", []):
                            if s["code"] == subdist_code:
                                return [
                                    (c["code"], c["name_en"], c["name_ar"])
                                    for c in s.get("communities", [])
                                ]
        return []

    def get_district_name(self, gov_code: str, dist_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a district."""
        for g in self._data:
            if g["code"] == gov_code:
                for d in g.get("districts", []):
                    if d["code"] == dist_code:
                        return (d["name_en"], d["name_ar"])
        return ("", "")

    def get_subdistrict_name(self, gov_code: str, dist_code: str, subdist_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a subdistrict."""
        for g in self._data:
            if g["code"] == gov_code:
                for d in g.get("districts", []):
                    if d["code"] == dist_code:
                        for s in d.get("subdistricts", []):
                            if s["code"] == subdist_code:
                                return (s["name_en"], s["name_ar"])
        return ("", "")

    def get_community_name(self, gov_code: str, dist_code: str, subdist_code: str, comm_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a community."""
        for g in self._data:
            if g["code"] == gov_code:
                for d in g.get("districts", []):
                    if d["code"] == dist_code:
                        for s in d.get("subdistricts", []):
                            if s["code"] == subdist_code:
                                for c in s.get("communities", []):
                                    if c["code"] == comm_code:
                                        return (c["name_en"], c["name_ar"])
        return ("", "")
