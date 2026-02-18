# -*- coding: utf-8 -*-
"""
Mock Data Provider for Development.

Provides mock/fake data for frontend development without requiring
a real backend. Simulates API responses with realistic delays.
"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .data_provider import (
    ApiResponse,
    DataProvider,
    DataProviderType,
    DataProviderEventEmitter,
    QueryParams,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class MockDataProvider(DataProvider, DataProviderEventEmitter):
    """
    Mock data provider for development and testing.

    Features:
    - In-memory data storage
    - Simulated network delays
    - Realistic Arabic/English data
    - CRUD operations with persistence to JSON file (optional)
    """

    def __init__(
        self,
        simulate_delay: bool = True,
        delay_ms: int = 200,
        persist_to_file: bool = False,
        data_file: Optional[Path] = None
    ):
        """
        Initialize mock data provider.

        Args:
            simulate_delay: Whether to simulate network latency
            delay_ms: Simulated delay in milliseconds
            persist_to_file: Whether to persist changes to a JSON file
            data_file: Path to JSON file for persistence
        """
        DataProviderEventEmitter.__init__(self)

        self.simulate_delay = simulate_delay
        self.delay_ms = delay_ms
        self.persist_to_file = persist_to_file
        self.data_file = data_file

        self._connected = False
        self._current_user = None
        self._auth_token = None

        # In-memory data stores
        self._buildings: Dict[str, Dict] = {}
        self._units: Dict[str, Dict] = {}
        self._persons: Dict[str, Dict] = {}
        self._claims: Dict[str, Dict] = {}
        self._relations: Dict[str, Dict] = {}
        self._documents: Dict[str, Dict] = {}
        self._users: Dict[str, Dict] = {}
        self._vocabularies: Dict[str, List[Dict]] = {}
        self._assignments: Dict[str, Dict] = {}
        self._audit_log: List[Dict] = []
        self._security_settings: Dict[str, Any] = {}
        self._duplicate_candidates: List[Dict] = []

    @property
    def provider_type(self) -> DataProviderType:
        return DataProviderType.MOCK

    def _simulate_delay(self):
        """Simulate network delay if enabled."""
        if self.simulate_delay and self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)

    def connect(self) -> bool:
        """Initialize mock data provider."""
        logger.info("Connecting to Mock Data Provider...")
        self._simulate_delay()

        # Load or generate initial data
        if self.persist_to_file and self.data_file and self.data_file.exists():
            self._load_from_file()
        else:
            self._generate_mock_data()

        self._connected = True
        self.emit("connected", {"provider": "mock"})
        logger.info("Mock Data Provider connected successfully")
        return True

    def disconnect(self) -> None:
        """Disconnect and optionally save data."""
        if self.persist_to_file and self.data_file:
            self._save_to_file()

        self._connected = False
        self.emit("disconnected", {"provider": "mock"})
        logger.info("Mock Data Provider disconnected")

    def is_connected(self) -> bool:
        return self._connected

    def health_check(self) -> Dict[str, Any]:
        self._simulate_delay()
        return {
            "status": "healthy" if self._connected else "disconnected",
            "provider": "mock",
            "data_counts": {
                "buildings": len(self._buildings),
                "units": len(self._units),
                "persons": len(self._persons),
                "claims": len(self._claims),
            },
            "timestamp": datetime.now().isoformat()
        }

    # ==================== Mock Data Generation ====================

    def _generate_mock_data(self):
        """Generate realistic mock data."""
        logger.info("Generating mock data...")

        # Generate users
        self._generate_users()

        # Generate vocabularies
        self._generate_vocabularies()

        # Generate buildings
        self._generate_buildings(50)

        # Generate units for each building
        self._generate_units()

        # Generate persons
        self._generate_persons(100)

        # Generate claims
        self._generate_claims(30)

        # Generate relations
        self._generate_relations()

        # Generate security settings
        self._generate_security_settings()

        logger.info(f"Generated mock data: {len(self._buildings)} buildings, "
                   f"{len(self._units)} units, {len(self._persons)} persons, "
                   f"{len(self._claims)} claims")

    def _generate_users(self):
        """Generate mock users."""
        users = [
            {
                "user_id": str(uuid.uuid4()),
                "username": "admin",
                "password_hash": "admin123",  # In real app, this would be hashed
                "email": "admin@trrcms.org",
                "full_name": "System Administrator",
                "full_name_ar": "مدير النظام",
                "role": "admin",
                "is_active": True,
                "is_locked": False,
                "created_at": datetime.now().isoformat()
            },
            {
                "user_id": str(uuid.uuid4()),
                "username": "data_manager",
                "password_hash": "dm123",
                "email": "dm@trrcms.org",
                "full_name": "Data Manager",
                "full_name_ar": "مدير البيانات",
                "role": "data_manager",
                "is_active": True,
                "is_locked": False,
                "created_at": datetime.now().isoformat()
            },
            {
                "user_id": str(uuid.uuid4()),
                "username": "clerk",
                "password_hash": "clerk123",
                "email": "clerk@trrcms.org",
                "full_name": "Office Clerk",
                "full_name_ar": "موظف المكتب",
                "role": "office_clerk",
                "is_active": True,
                "is_locked": False,
                "created_at": datetime.now().isoformat()
            }
        ]
        for user in users:
            self._users[user["user_id"]] = user

    def _generate_vocabularies(self):
        """Generate controlled vocabularies."""
        self._vocabularies = {
            "building_type": [
                {"code": "residential", "label": "Residential", "label_ar": "سكني"},
                {"code": "commercial", "label": "Commercial", "label_ar": "تجاري"},
                {"code": "mixed_use", "label": "Mixed Use", "label_ar": "متعدد الاستخدامات"},
                {"code": "industrial", "label": "Industrial", "label_ar": "صناعي"},
                {"code": "public", "label": "Public", "label_ar": "عام"},
            ],
            "building_status": [
                {"code": "intact", "label": "Intact", "label_ar": "سليم"},
                {"code": "minor_damage", "label": "Minor Damage", "label_ar": "ضرر طفيف"},
                {"code": "major_damage", "label": "Major Damage", "label_ar": "ضرر كبير"},
                {"code": "destroyed", "label": "Destroyed", "label_ar": "مدمر"},
            ],
            "unit_type": [
                {"code": "apartment", "label": "Apartment", "label_ar": "شقة"},
                {"code": "shop", "label": "Shop", "label_ar": "محل"},
                {"code": "office", "label": "Office", "label_ar": "مكتب"},
                {"code": "warehouse", "label": "Warehouse", "label_ar": "مستودع"},
            ],
            "relation_type": [
                {"code": "owner", "label": "Owner", "label_ar": "مالك"},
                {"code": "tenant", "label": "Tenant", "label_ar": "مستأجر"},
                {"code": "heir", "label": "Heir", "label_ar": "وريث"},
                {"code": "occupant", "label": "Occupant", "label_ar": "شاغل"},
            ],
            "case_status": [
                {"code": "draft", "label": "Draft", "label_ar": "مسودة"},
                {"code": "submitted", "label": "Submitted", "label_ar": "مقدمة"},
                {"code": "under_review", "label": "Under Review", "label_ar": "قيد المراجعة"},
                {"code": "approved", "label": "Approved", "label_ar": "موافق عليها"},
                {"code": "rejected", "label": "Rejected", "label_ar": "مرفوضة"},
            ],
            "document_type": [
                {"code": "TAPU_GREEN", "label": "Property Deed (Green Tapu)", "label_ar": "صك ملكية (طابو أخضر)"},
                {"code": "PROPERTY_REG", "label": "Property Registration", "label_ar": "بيان قيد عقاري"},
                {"code": "COURT_RULING", "label": "Court Ruling", "label_ar": "حكم قضائي"},
                {"code": "SALE_NOTARIZED", "label": "Notarized Sale Contract", "label_ar": "عقد بيع موثق"},
                {"code": "RENT_REGISTERED", "label": "Registered Rental", "label_ar": "عقد إيجار مثبت"},
                {"code": "UTILITY_BILL", "label": "Utility Bill", "label_ar": "فاتورة مرافق"},
                {"code": "MUKHTAR_CERT", "label": "Mukhtar Certificate", "label_ar": "شهادة المختار"},
            ]
        }

    def _generate_buildings(self, count: int):
        """Generate mock buildings."""
        neighborhoods = [
            ("001", "Al-Jamiliyah", "الجميلية"),
            ("002", "Al-Aziziyah", "العزيزية"),
            ("003", "Al-Shahba", "الشهباء"),
            ("004", "Al-Hamdaniyah", "الحمدانية"),
            ("005", "Salah al-Din", "صلاح الدين"),
        ]

        building_types = ["residential", "commercial", "mixed_use"]
        building_statuses = ["intact", "minor_damage", "major_damage", "destroyed"]

        for i in range(count):
            neighborhood = random.choice(neighborhoods)
            building_uuid = str(uuid.uuid4())
            building_id = f"01-01-01-{neighborhood[0]}-{random.randint(1,99):03d}-{random.randint(1,99999):05d}"

            self._buildings[building_uuid] = {
                "building_uuid": building_uuid,
                "building_id": building_id,
                "governorate_code": "01",
                "governorate_name": "Aleppo",
                "governorate_name_ar": "حلب",
                "district_code": "01",
                "district_name": "Aleppo City",
                "district_name_ar": "مدينة حلب",
                "neighborhood_code": neighborhood[0],
                "neighborhood_name": neighborhood[1],
                "neighborhood_name_ar": neighborhood[2],
                "building_number": str(random.randint(1, 500)),
                "building_type": random.choice(building_types),
                "building_status": random.choices(building_statuses, weights=[40, 30, 20, 10])[0],
                "number_of_floors": random.randint(1, 10),
                "number_of_units": random.randint(1, 20),
                "number_of_apartments": random.randint(0, 15),
                "number_of_shops": random.randint(0, 5),
                "latitude": 36.2 + random.uniform(-0.05, 0.05),
                "longitude": 37.15 + random.uniform(-0.05, 0.05),
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

    def _generate_units(self):
        """Generate units for each building."""
        unit_types = ["apartment", "shop", "office", "warehouse"]

        for building in self._buildings.values():
            num_units = building["number_of_units"]
            for i in range(num_units):
                unit_uuid = str(uuid.uuid4())
                unit_id = f"{building['building_id']}-{i+1:03d}"

                self._units[unit_uuid] = {
                    "unit_uuid": unit_uuid,
                    "unit_id": unit_id,
                    "building_id": building["building_id"],
                    "building_uuid": building["building_uuid"],
                    "unit_type": random.choice(unit_types),
                    "unit_number": str(i + 1),
                    "floor_number": random.randint(0, building["number_of_floors"]),
                    "area_sqm": random.randint(50, 300),
                    "created_at": building["created_at"],
                    "updated_at": datetime.now().isoformat(),
                }

    def _generate_persons(self, count: int):
        """Generate mock persons with Arabic names."""
        first_names = [
            ("Ahmad", "أحمد"), ("Mohammad", "محمد"), ("Ali", "علي"),
            ("Omar", "عمر"), ("Khalid", "خالد"), ("Hassan", "حسن"),
            ("Fatima", "فاطمة"), ("Aisha", "عائشة"), ("Maryam", "مريم"),
            ("Sara", "سارة"), ("Nour", "نور"), ("Layla", "ليلى")
        ]

        last_names = [
            ("Al-Halabi", "الحلبي"), ("Al-Shami", "الشامي"),
            ("Al-Masri", "المصري"), ("Al-Ahmad", "الأحمد"),
            ("Ibrahim", "إبراهيم"), ("Hassan", "حسن")
        ]

        genders = ["male", "female"]

        for i in range(count):
            person_id = str(uuid.uuid4())
            first = random.choice(first_names)
            last = random.choice(last_names)
            father = random.choice(first_names)
            gender = "male" if first[0] in ["Ahmad", "Mohammad", "Ali", "Omar", "Khalid", "Hassan"] else "female"

            self._persons[person_id] = {
                "person_id": person_id,
                "first_name": first[0],
                "first_name_ar": first[1],
                "father_name": father[0],
                "father_name_ar": father[1],
                "last_name": last[0],
                "last_name_ar": last[1],
                "gender": gender,
                "year_of_birth": random.randint(1950, 2000),
                "nationality": "Syrian",
                "national_id": f"{random.randint(10000000000, 99999999999)}",
                "phone_number": f"+963{random.randint(900000000, 999999999)}",
                "mobile_number": f"+963{random.randint(900000000, 999999999)}",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

    def _generate_claims(self, count: int):
        """Generate mock claims."""
        statuses = ["draft", "submitted", "under_review", "approved", "rejected"]
        units_list = list(self._units.values())
        persons_list = list(self._persons.values())

        for i in range(count):
            claim_uuid = str(uuid.uuid4())
            claim_id = f"CL-2025-{i+1:06d}"
            unit = random.choice(units_list) if units_list else None
            person = random.choice(persons_list) if persons_list else None

            self._claims[claim_uuid] = {
                "claim_uuid": claim_uuid,
                "claim_id": claim_id,
                "case_number": f"CN-{random.randint(1000, 9999)}",
                "unit_id": unit["unit_id"] if unit else None,
                "unit_uuid": unit["unit_uuid"] if unit else None,
                "person_ids": json.dumps([person["person_id"]]) if person else "[]",
                "case_status": random.choices(statuses, weights=[20, 25, 30, 15, 10])[0],
                "source": random.choice(["field_survey", "office_intake", "import"]),
                "priority": random.choice(["low", "normal", "high"]),
                "notes": "",
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 180))).isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

    def _generate_relations(self):
        """Generate person-unit relations."""
        relation_types = ["owner", "tenant", "heir", "occupant"]
        persons_list = list(self._persons.values())
        units_list = list(self._units.values())

        for unit in random.sample(units_list, min(len(units_list), 50)):
            # Assign 1-3 persons to each unit
            for person in random.sample(persons_list, random.randint(1, 3)):
                relation_id = str(uuid.uuid4())
                self._relations[relation_id] = {
                    "relation_id": relation_id,
                    "person_id": person["person_id"],
                    "unit_id": unit["unit_id"],
                    "relation_type": random.choice(relation_types),
                    "ownership_share": random.randint(0, 100) if random.random() > 0.5 else 0,
                    "verification_status": random.choice(["pending", "verified", "rejected"]),
                    "created_at": datetime.now().isoformat(),
                }

    def _generate_security_settings(self):
        """Generate default security settings."""
        self._security_settings = {
            "setting_id": "default",
            "password_min_length": 8,
            "password_require_uppercase": True,
            "password_require_lowercase": True,
            "password_require_digit": True,
            "password_require_symbol": False,
            "password_expiry_days": 90,
            "session_timeout_minutes": 30,
            "max_failed_login_attempts": 5,
            "account_lockout_duration_minutes": 15,
        }

    # ==================== Buildings ====================

    def get_buildings(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        params = params or QueryParams()

        # Filter buildings
        buildings = list(self._buildings.values())

        if params.filters:
            if params.filters.get("neighborhood_code"):
                buildings = [b for b in buildings if b["neighborhood_code"] == params.filters["neighborhood_code"]]
            if params.filters.get("building_type"):
                buildings = [b for b in buildings if b["building_type"] == params.filters["building_type"]]
            if params.filters.get("building_status"):
                buildings = [b for b in buildings if b["building_status"] == params.filters["building_status"]]

        if params.search:
            search_lower = params.search.lower()
            buildings = [b for b in buildings if
                        search_lower in b["building_id"].lower() or
                        search_lower in b.get("neighborhood_name", "").lower() or
                        search_lower in b.get("neighborhood_name_ar", "")]

        # Sort
        if params.sort_by and params.sort_by in buildings[0] if buildings else False:
            reverse = params.sort_order == "desc"
            buildings.sort(key=lambda x: x.get(params.sort_by, ""), reverse=reverse)

        # Paginate
        total = len(buildings)
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        buildings = buildings[start:end]

        return ApiResponse.ok(buildings, total_count=total, page=params.page, page_size=params.page_size)

    def get_building(self, building_id: str) -> ApiResponse:
        self._simulate_delay()

        # Search by building_id or building_uuid
        building = self._buildings.get(building_id)
        if not building:
            for b in self._buildings.values():
                if b["building_id"] == building_id:
                    building = b
                    break

        if building:
            # Add units
            building["units"] = [u for u in self._units.values() if u.get("building_uuid") == building["building_uuid"]]
            return ApiResponse.ok(building)

        return ApiResponse.error("Building not found", "E404")

    def create_building(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        building_uuid = str(uuid.uuid4())
        data["building_uuid"] = building_uuid
        data["created_at"] = datetime.now().isoformat()
        data["updated_at"] = datetime.now().isoformat()

        self._buildings[building_uuid] = data
        self._log_audit("create", "building", building_uuid, data)

        return ApiResponse.ok(data)

    def update_building(self, building_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        building = self._buildings.get(building_id)
        if not building:
            for uuid_key, b in self._buildings.items():
                if b["building_id"] == building_id:
                    building = b
                    building_id = uuid_key
                    break

        if not building:
            return ApiResponse.error("Building not found", "E404")

        data["updated_at"] = datetime.now().isoformat()
        self._buildings[building_id].update(data)
        self._log_audit("update", "building", building_id, data)

        return ApiResponse.ok(self._buildings[building_id])

    def delete_building(self, building_id: str) -> ApiResponse:
        self._simulate_delay()

        if building_id in self._buildings:
            del self._buildings[building_id]
            self._log_audit("delete", "building", building_id)
            return ApiResponse.ok({"deleted": True})

        return ApiResponse.error("Building not found", "E404")

    # ==================== Units ====================

    def get_units(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        params = params or QueryParams()

        units = list(self._units.values())

        if params.filters:
            if params.filters.get("building_id"):
                units = [u for u in units if u["building_id"] == params.filters["building_id"]]
            if params.filters.get("unit_type"):
                units = [u for u in units if u["unit_type"] == params.filters["unit_type"]]

        if params.search:
            search_lower = params.search.lower()
            units = [u for u in units if search_lower in u["unit_id"].lower()]

        total = len(units)
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        units = units[start:end]

        return ApiResponse.ok(units, total_count=total, page=params.page, page_size=params.page_size)

    def get_unit(self, unit_id: str) -> ApiResponse:
        self._simulate_delay()

        unit = self._units.get(unit_id)
        if not unit:
            for u in self._units.values():
                if u["unit_id"] == unit_id:
                    unit = u
                    break

        if unit:
            return ApiResponse.ok(unit)
        return ApiResponse.error("Unit not found", "E404")

    def create_unit(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        unit_uuid = str(uuid.uuid4())
        data["unit_uuid"] = unit_uuid
        data["created_at"] = datetime.now().isoformat()
        data["updated_at"] = datetime.now().isoformat()

        self._units[unit_uuid] = data
        self._log_audit("create", "unit", unit_uuid, data)

        return ApiResponse.ok(data)

    def update_unit(self, unit_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        unit = None
        unit_key = unit_id
        if unit_id in self._units:
            unit = self._units[unit_id]
        else:
            for key, u in self._units.items():
                if u["unit_id"] == unit_id:
                    unit = u
                    unit_key = key
                    break

        if not unit:
            return ApiResponse.error("Unit not found", "E404")

        data["updated_at"] = datetime.now().isoformat()
        self._units[unit_key].update(data)
        self._log_audit("update", "unit", unit_key, data)

        return ApiResponse.ok(self._units[unit_key])

    def delete_unit(self, unit_id: str) -> ApiResponse:
        self._simulate_delay()

        if unit_id in self._units:
            del self._units[unit_id]
            self._log_audit("delete", "unit", unit_id)
            return ApiResponse.ok({"deleted": True})

        return ApiResponse.error("Unit not found", "E404")

    # ==================== Persons ====================

    def get_persons(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        params = params or QueryParams()

        persons = list(self._persons.values())

        if params.search:
            search_lower = params.search.lower()
            persons = [p for p in persons if
                      search_lower in p.get("first_name", "").lower() or
                      search_lower in p.get("last_name", "").lower() or
                      search_lower in p.get("first_name_ar", "") or
                      search_lower in p.get("last_name_ar", "") or
                      search_lower in p.get("national_id", "")]

        total = len(persons)
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        persons = persons[start:end]

        return ApiResponse.ok(persons, total_count=total, page=params.page, page_size=params.page_size)

    def get_person(self, person_id: str) -> ApiResponse:
        self._simulate_delay()

        person = self._persons.get(person_id)
        if person:
            # Add relations
            person["relations"] = [r for r in self._relations.values() if r["person_id"] == person_id]
            return ApiResponse.ok(person)

        return ApiResponse.error("Person not found", "E404")

    def create_person(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        person_id = str(uuid.uuid4())
        data["person_id"] = person_id
        data["created_at"] = datetime.now().isoformat()
        data["updated_at"] = datetime.now().isoformat()

        self._persons[person_id] = data
        self._log_audit("create", "person", person_id, data)

        return ApiResponse.ok(data)

    def update_person(self, person_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        if person_id not in self._persons:
            return ApiResponse.error("Person not found", "E404")

        data["updated_at"] = datetime.now().isoformat()
        self._persons[person_id].update(data)
        self._log_audit("update", "person", person_id, data)

        return ApiResponse.ok(self._persons[person_id])

    def delete_person(self, person_id: str) -> ApiResponse:
        self._simulate_delay()

        if person_id in self._persons:
            del self._persons[person_id]
            self._log_audit("delete", "person", person_id)
            return ApiResponse.ok({"deleted": True})

        return ApiResponse.error("Person not found", "E404")

    # ==================== Claims ====================

    def get_claims(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        params = params or QueryParams()

        claims = list(self._claims.values())

        if params.filters:
            if params.filters.get("case_status"):
                claims = [c for c in claims if c["case_status"] == params.filters["case_status"]]
            if params.filters.get("unit_id"):
                claims = [c for c in claims if c.get("unit_id") == params.filters["unit_id"]]

        if params.search:
            search_lower = params.search.lower()
            claims = [c for c in claims if
                     search_lower in c.get("claim_id", "").lower() or
                     search_lower in c.get("case_number", "").lower()]

        total = len(claims)
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        claims = claims[start:end]

        return ApiResponse.ok(claims, total_count=total, page=params.page, page_size=params.page_size)

    def get_claim(self, claim_id: str) -> ApiResponse:
        self._simulate_delay()

        claim = self._claims.get(claim_id)
        if not claim:
            for c in self._claims.values():
                if c["claim_id"] == claim_id or c.get("case_number") == claim_id:
                    claim = c
                    break

        if claim:
            # Enrich with related data
            if claim.get("unit_uuid"):
                claim["unit"] = self._units.get(claim["unit_uuid"])
            return ApiResponse.ok(claim)

        return ApiResponse.error("Claim not found", "E404")

    def create_claim(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        claim_uuid = str(uuid.uuid4())
        claim_count = len(self._claims) + 1
        data["claim_uuid"] = claim_uuid
        data["claim_id"] = f"CL-{datetime.now().year}-{claim_count:06d}"
        data["created_at"] = datetime.now().isoformat()
        data["updated_at"] = datetime.now().isoformat()
        data["case_status"] = data.get("case_status", "draft")

        self._claims[claim_uuid] = data
        self._log_audit("create", "claim", claim_uuid, data)

        return ApiResponse.ok(data)

    def update_claim(self, claim_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        claim = self._claims.get(claim_id)
        claim_key = claim_id
        if not claim:
            for key, c in self._claims.items():
                if c["claim_id"] == claim_id:
                    claim = c
                    claim_key = key
                    break

        if not claim:
            return ApiResponse.error("Claim not found", "E404")

        data["updated_at"] = datetime.now().isoformat()
        self._claims[claim_key].update(data)
        self._log_audit("update", "claim", claim_key, data)

        return ApiResponse.ok(self._claims[claim_key])

    def delete_claim(self, claim_id: str) -> ApiResponse:
        self._simulate_delay()

        if claim_id in self._claims:
            del self._claims[claim_id]
            self._log_audit("delete", "claim", claim_id)
            return ApiResponse.ok({"deleted": True})

        return ApiResponse.error("Claim not found", "E404")

    # ==================== Relations ====================

    def get_relations(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        params = params or QueryParams()

        relations = list(self._relations.values())

        if params.filters:
            if params.filters.get("person_id"):
                relations = [r for r in relations if r["person_id"] == params.filters["person_id"]]
            if params.filters.get("unit_id"):
                relations = [r for r in relations if r["unit_id"] == params.filters["unit_id"]]

        total = len(relations)
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        relations = relations[start:end]

        return ApiResponse.ok(relations, total_count=total, page=params.page, page_size=params.page_size)

    def get_relation(self, relation_id: str) -> ApiResponse:
        self._simulate_delay()

        relation = self._relations.get(relation_id)
        if relation:
            return ApiResponse.ok(relation)
        return ApiResponse.error("Relation not found", "E404")

    def create_relation(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        relation_id = str(uuid.uuid4())
        data["relation_id"] = relation_id
        data["created_at"] = datetime.now().isoformat()

        self._relations[relation_id] = data
        self._log_audit("create", "relation", relation_id, data)

        return ApiResponse.ok(data)

    def update_relation(self, relation_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()

        if relation_id not in self._relations:
            return ApiResponse.error("Relation not found", "E404")

        data["updated_at"] = datetime.now().isoformat()
        self._relations[relation_id].update(data)
        self._log_audit("update", "relation", relation_id, data)

        return ApiResponse.ok(self._relations[relation_id])

    def delete_relation(self, relation_id: str) -> ApiResponse:
        self._simulate_delay()

        if relation_id in self._relations:
            del self._relations[relation_id]
            self._log_audit("delete", "relation", relation_id)
            return ApiResponse.ok({"deleted": True})

        return ApiResponse.error("Relation not found", "E404")

    # ==================== Documents ====================

    def get_documents(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        params = params or QueryParams()
        documents = list(self._documents.values())
        total = len(documents)
        return ApiResponse.ok(documents, total_count=total)

    def get_document(self, document_id: str) -> ApiResponse:
        self._simulate_delay()
        document = self._documents.get(document_id)
        if document:
            return ApiResponse.ok(document)
        return ApiResponse.error("Document not found", "E404")

    def create_document(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        document_id = str(uuid.uuid4())
        data["document_id"] = document_id
        data["created_at"] = datetime.now().isoformat()
        self._documents[document_id] = data
        return ApiResponse.ok(data)

    def update_document(self, document_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        if document_id not in self._documents:
            return ApiResponse.error("Document not found", "E404")
        self._documents[document_id].update(data)
        return ApiResponse.ok(self._documents[document_id])

    def delete_document(self, document_id: str) -> ApiResponse:
        self._simulate_delay()
        if document_id in self._documents:
            del self._documents[document_id]
            return ApiResponse.ok({"deleted": True})
        return ApiResponse.error("Document not found", "E404")

    # ==================== Users & Auth ====================

    def authenticate(self, username: str, password: str) -> ApiResponse:
        self._simulate_delay()

        for user in self._users.values():
            if user["username"] == username and user["password_hash"] == password:
                if not user["is_active"]:
                    return ApiResponse.error("User account is disabled", "E401")
                if user["is_locked"]:
                    return ApiResponse.error("User account is locked", "E401")

                self._current_user = user
                self._auth_token = str(uuid.uuid4())

                return ApiResponse.ok({
                    "token": self._auth_token,
                    "user": {
                        "user_id": user["user_id"],
                        "username": user["username"],
                        "full_name": user["full_name"],
                        "full_name_ar": user["full_name_ar"],
                        "role": user["role"],
                        "email": user["email"]
                    }
                })

        return ApiResponse.error("Invalid credentials", "E401")

    def get_current_user(self) -> ApiResponse:
        self._simulate_delay()
        if self._current_user:
            return ApiResponse.ok(self._current_user)
        return ApiResponse.error("Not authenticated", "E401")

    def get_users(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        users = list(self._users.values())
        # Remove sensitive fields
        safe_users = [{k: v for k, v in u.items() if k != "password_hash"} for u in users]
        return ApiResponse.ok(safe_users, total_count=len(safe_users))

    def create_user(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        user_id = str(uuid.uuid4())
        data["user_id"] = user_id
        data["created_at"] = datetime.now().isoformat()
        data["is_active"] = True
        data["is_locked"] = False
        self._users[user_id] = data
        return ApiResponse.ok({k: v for k, v in data.items() if k != "password_hash"})

    def update_user(self, user_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        if user_id not in self._users:
            return ApiResponse.error("User not found", "E404")
        self._users[user_id].update(data)
        return ApiResponse.ok({k: v for k, v in self._users[user_id].items() if k != "password_hash"})

    # ==================== Vocabularies ====================

    def get_vocabularies(self) -> ApiResponse:
        self._simulate_delay()
        return ApiResponse.ok(self._vocabularies)

    def get_vocabulary(self, vocab_name: str) -> ApiResponse:
        self._simulate_delay()
        vocab = self._vocabularies.get(vocab_name)
        if vocab:
            return ApiResponse.ok(vocab)
        return ApiResponse.error("Vocabulary not found", "E404")

    def update_vocabulary_term(self, vocab_name: str, term_code: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        if vocab_name not in self._vocabularies:
            return ApiResponse.error("Vocabulary not found", "E404")

        for term in self._vocabularies[vocab_name]:
            if term["code"] == term_code:
                term.update(data)
                return ApiResponse.ok(term)

        return ApiResponse.error("Term not found", "E404")

    # ==================== Dashboard & Statistics ====================

    def get_dashboard_stats(self) -> ApiResponse:
        self._simulate_delay()

        stats = {
            "buildings": {
                "total": len(self._buildings),
                "by_status": {},
                "by_type": {}
            },
            "units": {
                "total": len(self._units),
            },
            "persons": {
                "total": len(self._persons),
            },
            "claims": {
                "total": len(self._claims),
                "by_status": {}
            }
        }

        # Count buildings by status
        for b in self._buildings.values():
            status = b.get("building_status", "unknown")
            stats["buildings"]["by_status"][status] = stats["buildings"]["by_status"].get(status, 0) + 1
            btype = b.get("building_type", "unknown")
            stats["buildings"]["by_type"][btype] = stats["buildings"]["by_type"].get(btype, 0) + 1

        # Count claims by status
        for c in self._claims.values():
            status = c.get("case_status", "unknown")
            stats["claims"]["by_status"][status] = stats["claims"]["by_status"].get(status, 0) + 1

        return ApiResponse.ok(stats)

    def get_building_stats(self) -> ApiResponse:
        self._simulate_delay()
        return self.get_dashboard_stats()

    def get_claim_stats(self) -> ApiResponse:
        self._simulate_delay()
        stats = {"total": len(self._claims), "by_status": {}}
        for c in self._claims.values():
            status = c.get("case_status", "unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        return ApiResponse.ok(stats)

    # ==================== Duplicates ====================

    def get_duplicate_candidates(self, entity_type: str, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        # Return mock duplicate candidates
        candidates = [c for c in self._duplicate_candidates if c.get("entity_type") == entity_type]
        return ApiResponse.ok(candidates, total_count=len(candidates))

    def resolve_duplicate(self, resolution_data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        resolution_id = str(uuid.uuid4())
        resolution_data["resolution_id"] = resolution_id
        resolution_data["resolved_at"] = datetime.now().isoformat()
        return ApiResponse.ok(resolution_data)

    # ==================== Import/Export ====================

    def import_data(self, file_path: str, import_type: str) -> ApiResponse:
        self._simulate_delay()
        return ApiResponse.ok({
            "status": "completed",
            "import_id": str(uuid.uuid4()),
            "records_imported": random.randint(10, 100),
            "errors": []
        })

    def export_data(self, export_type: str, filters: Dict[str, Any] = None) -> ApiResponse:
        self._simulate_delay()
        return ApiResponse.ok({
            "status": "completed",
            "export_id": str(uuid.uuid4()),
            "file_path": f"/exports/{export_type}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        })

    # ==================== Assignments ====================

    def get_building_assignments(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        assignments = list(self._assignments.values())
        return ApiResponse.ok(assignments, total_count=len(assignments))

    def create_assignment(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        assignment_id = str(uuid.uuid4())
        data["assignment_id"] = assignment_id
        data["created_at"] = datetime.now().isoformat()
        self._assignments[assignment_id] = data
        return ApiResponse.ok(data)

    def update_assignment(self, assignment_id: str, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        if assignment_id not in self._assignments:
            return ApiResponse.error("Assignment not found", "E404")
        self._assignments[assignment_id].update(data)
        return ApiResponse.ok(self._assignments[assignment_id])

    # ==================== Audit ====================

    def get_audit_log(self, params: QueryParams = None) -> ApiResponse:
        self._simulate_delay()
        params = params or QueryParams()

        logs = self._audit_log

        total = len(logs)
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        logs = logs[start:end]

        return ApiResponse.ok(logs, total_count=total, page=params.page, page_size=params.page_size)

    def _log_audit(self, action: str, entity_type: str, entity_id: str, data: Any = None):
        """Log an audit entry."""
        self._audit_log.append({
            "log_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user_id": self._current_user["user_id"] if self._current_user else None,
            "data": data
        })

    # ==================== Settings ====================

    def get_security_settings(self) -> ApiResponse:
        self._simulate_delay()
        return ApiResponse.ok(self._security_settings)

    def update_security_settings(self, data: Dict[str, Any]) -> ApiResponse:
        self._simulate_delay()
        self._security_settings.update(data)
        return ApiResponse.ok(self._security_settings)

    # ==================== Persistence ====================

    def _load_from_file(self):
        """Load mock data from JSON file."""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._buildings = data.get("buildings", {})
                self._units = data.get("units", {})
                self._persons = data.get("persons", {})
                self._claims = data.get("claims", {})
                self._relations = data.get("relations", {})
                self._documents = data.get("documents", {})
                self._users = data.get("users", {})
                self._vocabularies = data.get("vocabularies", {})
                logger.info(f"Loaded mock data from {self.data_file}")
        except Exception as e:
            logger.error(f"Error loading mock data: {e}")
            self._generate_mock_data()

    def _save_to_file(self):
        """Save mock data to JSON file."""
        try:
            data = {
                "buildings": self._buildings,
                "units": self._units,
                "persons": self._persons,
                "claims": self._claims,
                "relations": self._relations,
                "documents": self._documents,
                "users": self._users,
                "vocabularies": self._vocabularies,
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved mock data to {self.data_file}")
        except Exception as e:
            logger.error(f"Error saving mock data: {e}")
