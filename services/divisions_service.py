# -*- coding: utf-8 -*-
"""
Administrative Divisions Service — API-only.

Reads hierarchical data (governorate -> district -> subdistrict -> community)
from Backend API.

Each level can be queried by raw code or OCHA pCode. The deepest pCode
provided is sufficient — the backend infers parent levels.

Usage:
    service = DivisionsService()
    governorates = service.get_governorates()
    districts = service.get_districts(gov_pcode="SY02")            # by pCode
    districts = service.get_districts(gov_code="02")               # by raw code
    subdistricts = service.get_subdistricts(gov_pcode="SY02", dist_pcode="SY0200")
    communities = service.get_communities(subdist_pcode="SY020000")

Result tuple shape: (code, pCode, name_en, name_ar)
"""

from typing import List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

# (code, pCode, name_en, name_ar)
DivisionRow = Tuple[str, str, str, str]


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
        self._governorates_cache: Optional[List[DivisionRow]] = None
        self._districts_cache: dict = {}
        self._subdistricts_cache: dict = {}
        self._communities_cache: dict = {}

    def invalidate(self):
        """Force-clear all cached admin divisions (used by OCHA migration on first launch)."""
        self._governorates_cache = None
        self._districts_cache.clear()
        self._subdistricts_cache.clear()
        self._communities_cache.clear()
        logger.info("DivisionsService cache invalidated")

    def _get_api_client(self):
        """Get API client if available."""
        try:
            from services.api_client import get_api_client
            return get_api_client()
        except Exception:
            return None

    @staticmethod
    def _row(item: dict, code_field: str = "code") -> DivisionRow:
        """Build a (code, pCode, name_en, name_ar) row from an API item."""
        return (
            item.get(code_field, "") or "",
            item.get("pCode", "") or "",
            item.get("nameEnglish", "") or "",
            item.get("nameArabic", "") or "",
        )

    def get_governorates(self) -> List[DivisionRow]:
        """Get all governorates as [(code, pCode, name_en, name_ar)]."""
        if self._governorates_cache is not None:
            return self._governorates_cache

        api = self._get_api_client()
        items = api.get_governorates() or []
        self._governorates_cache = [
            self._row(g) for g in items if g.get("isActive", True)
        ]
        return self._governorates_cache

    def get_districts(
        self,
        gov_code: Optional[str] = None,
        gov_pcode: Optional[str] = None,
    ) -> List[DivisionRow]:
        """Get districts under a governorate (by raw code or pCode)."""
        cache_key = gov_pcode or gov_code or ""
        if cache_key in self._districts_cache:
            return self._districts_cache[cache_key]

        api = self._get_api_client()
        items = api.get_districts(
            governorate_code=gov_code, governorate_pcode=gov_pcode
        ) or []
        self._districts_cache[cache_key] = [
            self._row(d) for d in items if d.get("isActive", True)
        ]
        return self._districts_cache[cache_key]

    def get_subdistricts(
        self,
        gov_code: Optional[str] = None,
        dist_code: Optional[str] = None,
        gov_pcode: Optional[str] = None,
        dist_pcode: Optional[str] = None,
    ) -> List[DivisionRow]:
        """Get subdistricts under a district (by raw codes or pCodes)."""
        cache_key = dist_pcode or (gov_code, dist_code)
        if cache_key in self._subdistricts_cache:
            return self._subdistricts_cache[cache_key]

        api = self._get_api_client()
        items = api.get_sub_districts(
            governorate_code=gov_code, district_code=dist_code,
            governorate_pcode=gov_pcode, district_pcode=dist_pcode,
        ) or []
        self._subdistricts_cache[cache_key] = [
            self._row(s) for s in items if s.get("isActive", True)
        ]
        return self._subdistricts_cache[cache_key]

    def get_communities(
        self,
        gov_code: Optional[str] = None,
        dist_code: Optional[str] = None,
        subdist_code: Optional[str] = None,
        gov_pcode: Optional[str] = None,
        dist_pcode: Optional[str] = None,
        subdist_pcode: Optional[str] = None,
    ) -> List[DivisionRow]:
        """Get communities under a subdistrict (by raw codes or pCodes)."""
        cache_key = subdist_pcode or (gov_code, dist_code, subdist_code)
        if cache_key in self._communities_cache:
            return self._communities_cache[cache_key]

        try:
            api = self._get_api_client()
            items = api.get_communities(
                governorate_code=gov_code,
                district_code=dist_code,
                sub_district_code=subdist_code,
                governorate_pcode=gov_pcode,
                district_pcode=dist_pcode,
                sub_district_pcode=subdist_pcode,
            ) or []
            result = [self._row(c) for c in items if c.get("isActive", True)]
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
                    (p.get('pcode', ''), '', p.get('name_en', ''), p.get('name_ar', ''))
                    for p in places
                ]
                self._communities_cache[cache_key] = result
                return result
        except Exception:
            pass

        self._communities_cache[cache_key] = []
        return []

    # -------- Convenience name lookups (return Arabic + English names) --------

    def get_governorate_name(self, gov_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a governorate by raw code."""
        for code, _pcode, name_en, name_ar in self.get_governorates():
            if code == gov_code:
                return (name_en, name_ar)
        return ("", "")

    def get_governorate_name_by_pcode(self, gov_pcode: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a governorate by pCode."""
        for _code, pcode, name_en, name_ar in self.get_governorates():
            if pcode == gov_pcode:
                return (name_en, name_ar)
        return ("", "")

    def get_district_name(self, gov_code: str, dist_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a district."""
        for code, _pcode, name_en, name_ar in self.get_districts(gov_code=gov_code):
            if code == dist_code:
                return (name_en, name_ar)
        return ("", "")

    def get_subdistrict_name(self, gov_code: str, dist_code: str, subdist_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a subdistrict."""
        for code, _pcode, name_en, name_ar in self.get_subdistricts(gov_code=gov_code, dist_code=dist_code):
            if code == subdist_code:
                return (name_en, name_ar)
        return ("", "")

    def get_community_name(self, gov_code: str, dist_code: str, subdist_code: str, comm_code: str) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a community."""
        for code, _pcode, name_en, name_ar in self.get_communities(
            gov_code=gov_code, dist_code=dist_code, subdist_code=subdist_code
        ):
            if code == comm_code:
                return (name_en, name_ar)
        return ("", "")

    def get_district_name_by_pcode(
        self,
        dist_pcode: str,
        gov_code: Optional[str] = None,
        gov_pcode: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a district by pCode. Needs gov context to fetch list."""
        if not dist_pcode:
            return ("", "")
        for _code, pcode, name_en, name_ar in self.get_districts(
            gov_code=gov_code, gov_pcode=gov_pcode
        ):
            if pcode == dist_pcode:
                return (name_en, name_ar)
        return ("", "")

    def get_subdistrict_name_by_pcode(
        self,
        subdist_pcode: str,
        gov_code: Optional[str] = None,
        dist_code: Optional[str] = None,
        gov_pcode: Optional[str] = None,
        dist_pcode: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a subdistrict by pCode. Needs district context."""
        if not subdist_pcode:
            return ("", "")
        for _code, pcode, name_en, name_ar in self.get_subdistricts(
            gov_code=gov_code, dist_code=dist_code,
            gov_pcode=gov_pcode, dist_pcode=dist_pcode,
        ):
            if pcode == subdist_pcode:
                return (name_en, name_ar)
        return ("", "")

    def get_community_name_by_pcode(
        self,
        comm_pcode: str,
        gov_code: Optional[str] = None,
        dist_code: Optional[str] = None,
        subdist_code: Optional[str] = None,
        gov_pcode: Optional[str] = None,
        dist_pcode: Optional[str] = None,
        subdist_pcode: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Get (name_en, name_ar) for a community by pCode. Needs subdistrict context."""
        if not comm_pcode:
            return ("", "")
        for _code, pcode, name_en, name_ar in self.get_communities(
            gov_code=gov_code, dist_code=dist_code, subdist_code=subdist_code,
            gov_pcode=gov_pcode, dist_pcode=dist_pcode, subdist_pcode=subdist_pcode,
        ):
            if pcode == comm_pcode:
                return (name_en, name_ar)
        return ("", "")
