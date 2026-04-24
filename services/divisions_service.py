# -*- coding: utf-8 -*-
"""
Administrative Divisions Service — API-only.

Reads hierarchical data (governorate -> district -> subdistrict -> community)
from Backend API.

Usage:
    service = DivisionsService()
    governorates = service.get_governorates()
    districts = service.get_districts("01")  # Aleppo
    subdistricts = service.get_subdistricts("01", "03")  # Al-Bab
    communities = service.get_communities("01", "03", "02")  # Tadef
"""

from typing import List, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class DivisionsService:
    """Administrative divisions data provider (API-only)."""

    _instance = None

    def __new__(cls):
        """Singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._governorates_cache = None
        self._districts_cache = {}
        self._subdistricts_cache = {}
        self._communities_cache = {}

    def _get_api_client(self):
        """Get API client if available."""
        try:
            from services.api_client import get_api_client
            return get_api_client()
        except Exception:
            return None

    def get_governorates(self) -> List[Tuple[str, str, str]]:
        """Get all governorates as [(code, name_en, name_ar)]."""
        if self._governorates_cache is not None:
            return self._governorates_cache

        api = self._get_api_client()
        items = api.get_governorates()
        self._governorates_cache = [
            (g.get("code", ""), g.get("nameEnglish", ""), g.get("nameArabic", ""))
            for g in items if g.get("isActive", True)
        ]
        return self._governorates_cache

    def get_districts(self, gov_code: str) -> List[Tuple[str, str, str]]:
        """Get districts for a governorate as [(code, name_en, name_ar)]."""
        if gov_code in self._districts_cache:
            return self._districts_cache[gov_code]

        api = self._get_api_client()
        items = api.get_districts(governorate_code=gov_code)
        self._districts_cache[gov_code] = [
            (d.get("code", ""), d.get("nameEnglish", ""), d.get("nameArabic", ""))
            for d in items if d.get("isActive", True)
        ]
        return self._districts_cache[gov_code]

    def get_subdistricts(self, gov_code: str, dist_code: str) -> List[Tuple[str, str, str]]:
        """Get subdistricts for a district as [(code, name_en, name_ar)]."""
        cache_key = (gov_code, dist_code)
        if cache_key in self._subdistricts_cache:
            return self._subdistricts_cache[cache_key]

        api = self._get_api_client()
        items = api.get_sub_districts(
            governorate_code=gov_code, district_code=dist_code
        )
        self._subdistricts_cache[cache_key] = [
            (s.get("code", ""), s.get("nameEnglish", ""), s.get("nameArabic", ""))
            for s in items if s.get("isActive", True)
        ]
        return self._subdistricts_cache[cache_key]

    def get_communities(self, gov_code: str, dist_code: str, subdist_code: str) -> List[Tuple[str, str, str]]:
        """Get communities for a subdistrict as [(code, name_en, name_ar)]."""
        cache_key = (gov_code, dist_code, subdist_code)
        if cache_key in self._communities_cache:
            return self._communities_cache[cache_key]

        try:
            api = self._get_api_client()
            items = api.get_communities(
                governorate_code=gov_code,
                district_code=dist_code,
                sub_district_code=subdist_code
            )
            result = [
                (c.get("code", ""), c.get("nameEnglish", ""), c.get("nameArabic", ""))
                for c in items if c.get("isActive", True)
            ]
            if result:
                self._communities_cache[cache_key] = result
                return result
        except Exception:
            pass

    # Local fallback from populated places dataset
        try:
            from services import boundary_service
            places = boundary_service.get_places_list(admin3_pcode=subdist_code)
            if places:
                result = [
                    (p.get('pcode', ''), p.get('name_en', ''), p.get('name_ar', ''))
                    for p in places
                ]
                self._communities_cache[cache_key] = result
                return result
        except Exception:
            pass

        self._communities_cache[cache_key] = []
        return []

    def get_governorate_name(self, gov_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a governorate."""
        for code, name_en, name_ar in self.get_governorates():
            if code == gov_code:
                return (name_en, name_ar)
        return ("", "")

    def get_district_name(self, gov_code: str, dist_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a district."""
        for code, name_en, name_ar in self.get_districts(gov_code):
            if code == dist_code:
                return (name_en, name_ar)
        return ("", "")

    def get_subdistrict_name(self, gov_code: str, dist_code: str, subdist_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a subdistrict."""
        for code, name_en, name_ar in self.get_subdistricts(gov_code, dist_code):
            if code == subdist_code:
                return (name_en, name_ar)
        return ("", "")

    def get_community_name(self, gov_code: str, dist_code: str, subdist_code: str, comm_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a community."""
        for code, name_en, name_ar in self.get_communities(gov_code, dist_code, subdist_code):
            if code == comm_code:
                return (name_en, name_ar)
        return ("", "")
