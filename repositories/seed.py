# -*- coding: utf-8 -*-
"""
Database seeder for demo data.
Loads data from GeoJSON file for consistency with future API integration.
"""

import random
import json
import os
from datetime import datetime, timedelta
from typing import List

from models.building import Building
from models.unit import PropertyUnit
from models.person import Person
from models.relation import PersonUnitRelation
from models.claim import Claim
from models.user import User
from .database import Database
from .building_repository import BuildingRepository
from .unit_repository import UnitRepository
from .person_repository import PersonRepository
from .claim_repository import ClaimRepository
from .user_repository import UserRepository
from utils.logger import get_logger

logger = get_logger(__name__)

# Arabic first names
ARABIC_FIRST_NAMES_MALE = [
    ("Muhammad", "محمد"), ("Ahmad", "أحمد"), ("Ali", "علي"), ("Omar", "عمر"),
    ("Khalid", "خالد"), ("Hassan", "حسن"), ("Hussein", "حسين"), ("Ibrahim", "إبراهيم"),
    ("Yusuf", "يوسف"), ("Mahmoud", "محمود"), ("Samir", "سمير"), ("Faisal", "فيصل"),
    ("Nabil", "نبيل"), ("Tariq", "طارق"), ("Walid", "وليد"), ("Ziad", "زياد"),
]

ARABIC_FIRST_NAMES_FEMALE = [
    ("Fatima", "فاطمة"), ("Aisha", "عائشة"), ("Maryam", "مريم"), ("Zahra", "زهرة"),
    ("Layla", "ليلى"), ("Nour", "نور"), ("Huda", "هدى"), ("Sara", "سارة"),
    ("Rania", "رانيا"), ("Dina", "دينا"), ("Hana", "هناء"), ("Amira", "أميرة"),
]

ARABIC_LAST_NAMES = [
    ("Al-Halabi", "الحلبي"), ("Al-Shami", "الشامي"), ("Al-Ibrahim", "الإبراهيم"),
    ("Al-Hassan", "الحسن"), ("Al-Ahmad", "الأحمد"), ("Al-Ali", "العلي"),
    ("Al-Omar", "العمر"), ("Al-Khalil", "الخليل"), ("Al-Khatib", "الخطيب"),
    ("Al-Najjar", "النجار"), ("Al-Sabbagh", "الصباغ"), ("Al-Qadi", "القاضي"),
    ("Al-Masri", "المصري"), ("Al-Dimashqi", "الدمشقي"), ("Al-Hallab", "الحلاب"),
]

# Aleppo neighborhoods
NEIGHBORHOODS = [
    ("001", "Al-Jamiliyah", "الجميلية"),
    ("002", "Al-Aziziyah", "العزيزية"),
    ("003", "Al-Shahba", "الشهباء"),
    ("004", "Al-Hamdaniyah", "الحمدانية"),
    ("005", "Al-Midan", "الميدان"),
    ("006", "Salah al-Din", "صلاح الدين"),
    ("007", "Al-Firdaws", "الفردوس"),
    ("008", "Al-Sabil", "السبيل"),
    ("009", "Hanano", "هنانو"),
    ("010", "Al-Sha'ar", "الشعار"),
]

BUILDING_TYPES = ["residential", "commercial", "mixed_use"]
BUILDING_STATUSES = ["intact", "minor_damage", "major_damage", "destroyed"]
UNIT_TYPES = ["apartment", "shop", "office"]
RELATION_TYPES = ["owner", "tenant", "heir", "occupant"]
CASE_STATUSES = ["draft", "submitted", "screening", "under_review", "awaiting_docs", "approved"]


def seed_database(db: Database, force_reseed: bool = False):
    """
    Seed the database with demo data from GeoJSON.

    Args:
        db: Database instance
        force_reseed: If True, clear existing data and re-seed from GeoJSON
    """
    # Set random seed for consistent data generation
    random.seed(42)

    # Always seed fresh data (database is cleaned on startup)
    logger.info("Seeding database with demo data from GeoJSON...")

    # Initialize repositories
    user_repo = UserRepository(db)
    building_repo = BuildingRepository(db)
    unit_repo = UnitRepository(db)
    person_repo = PersonRepository(db)
    claim_repo = ClaimRepository(db)

    # Seed users (only if no users exist)
    user_count = db.fetch_one("SELECT COUNT(*) as count FROM users")
    if user_count and user_count['count'] == 0:
        _seed_users(user_repo)
        logger.info(">> Created 5 test users")
    else:
        logger.info(">> Users already exist, skipping user seed")

    # Seed buildings from GeoJSON
    buildings = _seed_buildings_from_geojson(building_repo)

    # Seed units (2-8 per building)
    units = _seed_units(unit_repo, buildings)

    # Seed persons (150 persons)
    persons = _seed_persons(person_repo, 150)

    # Seed claims (50 claims)
    _seed_claims(claim_repo, units, persons, 50)

    logger.info(">> Database seeding completed successfully!")
    logger.info(f"  - Users: {user_count['count'] if user_count else 0}")
    logger.info(f"  - Buildings: {len(buildings)} (from GeoJSON)")
    logger.info(f"  - Units: {len(units)}")
    logger.info(f"  - Persons: {len(persons)}")
    logger.info(f"  - Claims: 50")


def reset_test_user_passwords(db: Database):
    """
    Reset passwords for test users to fix login issues.
    Call this when users can't login with default credentials.
    """
    user_repo = UserRepository(db)
    test_users = {
        "admin": "admin123",
        "manager": "manager123",
        "clerk": "clerk123",
        "supervisor": "supervisor123",
        "analyst": "analyst123",
    }

    for username, password in test_users.items():
        user = user_repo.get_by_username(username)
        if user:
            user.set_password(password, track_history=False)
            # Update password in database using the adapter's execute method
            db.execute(
                "UPDATE users SET password_hash = ?, password_salt = ?, is_locked = 0, failed_attempts = 0 WHERE username = ?",
                (user.password_hash, user.password_salt, username)
            )
            logger.info(f"Reset password for user: {username}")


def _seed_users(repo: UserRepository):
    """
    Seed default users for all roles as per UC-009.

    Test accounts created:
    - admin / admin123 - مدير النظام (Full system access)
    - manager / manager123 - مدير البيانات (Data import/export/review)
    - clerk / clerk123 - موظف المكتب (Data entry/document scanning)
    - supervisor / supervisor123 - مشرف ميداني (Field oversight)
    - analyst / analyst123 - محلل (Reports/analysis)
    """
    users = [
        User(
            username="admin",
            full_name="System Administrator",
            full_name_ar="مدير النظام",
            role="admin",
            email="admin@unhabitat.org"
        ),
        User(
            username="manager",
            full_name="Data Manager",
            full_name_ar="مدير البيانات",
            role="data_manager",
            email="manager@unhabitat.org"
        ),
        User(
            username="clerk",
            full_name="Office Clerk",
            full_name_ar="موظف المكتب",
            role="office_clerk",
            email="clerk@unhabitat.org"
        ),
        User(
            username="supervisor",
            full_name="Field Supervisor",
            full_name_ar="مشرف ميداني",
            role="field_supervisor",
            email="supervisor@unhabitat.org"
        ),
        User(
            username="analyst",
            full_name="Data Analyst",
            full_name_ar="محلل البيانات",
            role="analyst",
            email="analyst@unhabitat.org"
        ),
    ]

    passwords = ["admin123", "manager123", "clerk123", "supervisor123", "analyst123"]

    for user, password in zip(users, passwords):
        user.set_password(password)
        repo.create(user)
        logger.debug(f"Created user: {user.username}")


def _polygon_to_wkt(coordinates):
    """Convert GeoJSON polygon coordinates to WKT format."""
    # coordinates is a list of rings, we use the first (outer) ring
    outer_ring = coordinates[0]
    points = [f"{lon} {lat}" for lon, lat in outer_ring]
    return f"POLYGON(({', '.join(points)}))"


def _seed_buildings_from_geojson(repo: BuildingRepository) -> List[Building]:
    """Load buildings from GeoJSON file - single source of truth."""
    buildings = []

    # Path to GeoJSON file
    geojson_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_buildings.geojson")

    if not os.path.exists(geojson_path):
        logger.warning(f"GeoJSON file not found: {geojson_path}")
        logger.warning("Falling back to legacy random generation...")
        return _seed_buildings(repo, 10)

    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)

        logger.info(f"Loading buildings from GeoJSON: {geojson_path}")

        for feature in geojson_data.get('features', []):
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            geom_type = geom.get('type')
            coords = geom.get('coordinates')

            # Extract coordinates
            if geom_type == 'Point':
                lon, lat = coords
                geo_location = None  # Point geometry - no polygon
            elif geom_type == 'Polygon':
                # Get center point (first coordinate of outer ring)
                lon, lat = coords[0][0]
                # Convert polygon to WKT
                geo_location = _polygon_to_wkt(coords)
            else:
                logger.warning(f"Unsupported geometry type: {geom_type}")
                continue

            # Create building object
            building = Building(
                building_id=props.get('building_id'),
                governorate_code=props.get('governorate_code', '01'),
                governorate_name=props.get('governorate_name', 'Aleppo'),
                governorate_name_ar=props.get('governorate_name_ar', 'حلب'),
                district_code=props.get('district_code', '01'),
                district_name=props.get('district_name', 'Aleppo City'),
                district_name_ar=props.get('district_name_ar', 'مدينة حلب'),
                subdistrict_code=props.get('subdistrict_code', '01'),
                subdistrict_name=props.get('subdistrict_name', 'Aleppo Center'),
                subdistrict_name_ar=props.get('subdistrict_name_ar', 'حلب المركز'),
                community_code=props.get('community_code', '001'),
                community_name=props.get('community_name', 'Downtown'),
                community_name_ar=props.get('community_name_ar', 'وسط المدينة'),
                neighborhood_code=props.get('neighborhood_code', '001'),
                neighborhood_name=props.get('neighborhood_name', 'Unknown'),
                neighborhood_name_ar=props.get('neighborhood_name_ar', 'غير معروف'),
                building_number=props.get('building_number', '00001'),
                building_type=props.get('building_type', 'residential'),
                building_status=props.get('building_status', 'intact'),
                number_of_floors=props.get('number_of_floors', 1),
                number_of_units=props.get('number_of_units', 0),
                number_of_apartments=props.get('number_of_apartments', 0),
                number_of_shops=props.get('number_of_shops', 0),
                latitude=lat,
                longitude=lon,
                geo_location=geo_location,
                created_at=datetime.now(),
                created_by="system"
            )

            repo.create(building)
            buildings.append(building)
            logger.debug(f"Created building: {building.building_id} (type: {geom_type})")

        logger.info(f">> Loaded {len(buildings)} buildings from GeoJSON")
        return buildings

    except Exception as e:
        logger.error(f"Failed to load GeoJSON: {e}")
        logger.warning("Falling back to legacy random generation...")
        return _seed_buildings(repo, 10)


def _seed_buildings(repo: BuildingRepository, count: int) -> List[Building]:
    """LEGACY: Seed buildings with random data (fallback only)."""
    buildings = []

    # Base coordinates for Aleppo city center
    base_lat = 36.2021
    base_lon = 37.1343

    for i in range(count):
        neighborhood = random.choice(NEIGHBORHOODS)

        building = Building(
            governorate_code="01",
            governorate_name="Aleppo",
            governorate_name_ar="حلب",
            district_code="01",
            district_name="Aleppo City",
            district_name_ar="مدينة حلب",
            subdistrict_code="01",
            subdistrict_name="Aleppo Center",
            subdistrict_name_ar="حلب المركز",
            community_code="001",
            community_name="Downtown",
            community_name_ar="وسط المدينة",
            neighborhood_code=neighborhood[0],
            neighborhood_name=neighborhood[1],
            neighborhood_name_ar=neighborhood[2],
            building_number=str(i + 1).zfill(5),
            building_type=random.choice(BUILDING_TYPES),
            building_status=random.choices(
                BUILDING_STATUSES,
                weights=[40, 30, 20, 10]  # More intact buildings
            )[0],
            number_of_floors=random.randint(1, 8),
            latitude=base_lat + random.uniform(-0.05, 0.05),
            longitude=base_lon + random.uniform(-0.05, 0.05),
            geo_location=None,  # No polygon in legacy mode
            created_at=datetime.now() - timedelta(days=random.randint(1, 365)),
            created_by="system"
        )

        # Calculate units based on type and floors
        if building.building_type == "residential":
            building.number_of_apartments = building.number_of_floors * random.randint(2, 4)
            building.number_of_shops = random.randint(0, 2)
        elif building.building_type == "commercial":
            building.number_of_shops = building.number_of_floors * random.randint(2, 6)
            building.number_of_apartments = 0
        else:  # mixed_use
            building.number_of_apartments = (building.number_of_floors - 1) * random.randint(2, 4)
            building.number_of_shops = random.randint(2, 6)

        building.number_of_units = building.number_of_apartments + building.number_of_shops

        repo.create(building)
        buildings.append(building)

    logger.debug(f"Created {len(buildings)} buildings (legacy mode)")
    return buildings


def _seed_units(repo: UnitRepository, buildings: List[Building]) -> List[PropertyUnit]:
    """Seed property units for buildings."""
    units = []

    for building in buildings:
        unit_count = random.randint(2, 8)

        for j in range(unit_count):
            floor = j // 2  # 2 units per floor
            unit_type = "apartment" if building.building_type == "residential" else random.choice(UNIT_TYPES)

            if floor == 0 and building.building_type in ["commercial", "mixed_use"]:
                unit_type = "shop"

            unit = PropertyUnit(
                building_id=building.building_id,
                unit_type=unit_type,
                unit_number=str(j + 1).zfill(3),
                floor_number=floor,
                apartment_number=f"{floor}{j % 2 + 1}",
                apartment_status=random.choice(["occupied", "vacant", "unknown"]),
                area_sqm=random.uniform(50, 200) if unit_type == "apartment" else random.uniform(20, 100),
                created_at=building.created_at,
                created_by="system"
            )

            repo.create(unit)
            units.append(unit)

    logger.debug(f"Created {len(units)} units")
    return units


def _seed_persons(repo: PersonRepository, count: int) -> List[Person]:
    """Seed persons with Arabic names."""
    persons = []

    for i in range(count):
        is_male = random.random() > 0.4  # 60% male
        first_name = random.choice(ARABIC_FIRST_NAMES_MALE if is_male else ARABIC_FIRST_NAMES_FEMALE)
        father = random.choice(ARABIC_FIRST_NAMES_MALE)
        mother = random.choice(ARABIC_FIRST_NAMES_FEMALE)
        last_name = random.choice(ARABIC_LAST_NAMES)

        person = Person(
            first_name=first_name[0],
            first_name_ar=first_name[1],
            father_name=father[0],
            father_name_ar=father[1],
            mother_name=mother[0],
            mother_name_ar=mother[1],
            last_name=last_name[0],
            last_name_ar=last_name[1],
            gender="male" if is_male else "female",
            year_of_birth=random.randint(1950, 2000),
            nationality="Syrian",
            national_id=str(random.randint(10000000000, 99999999999)),
            mobile_number=f"+963 9{random.randint(10000000, 99999999)}",
            created_at=datetime.now() - timedelta(days=random.randint(1, 365)),
            created_by="system"
        )

        repo.create(person)
        persons.append(person)

    logger.debug(f"Created {len(persons)} persons")
    return persons


def _seed_claims(repo: ClaimRepository, units: List[PropertyUnit], persons: List[Person], count: int):
    """Seed claims linking persons to units."""
    claims = []
    used_units = set()

    for i in range(min(count, len(units), len(persons))):
        # Find an unused unit
        available_units = [u for u in units if u.unit_id not in used_units]
        if not available_units:
            break

        unit = random.choice(available_units)
        used_units.add(unit.unit_id)

        # Select 1-3 persons for this claim
        claim_persons = random.sample(persons, min(random.randint(1, 3), len(persons)))

        claim = Claim(
            source=random.choice(["FIELD_COLLECTION", "OFFICE_SUBMISSION"]),
            person_ids=",".join(p.person_id for p in claim_persons),
            unit_id=unit.unit_id,
            case_status=random.choice(CASE_STATUSES),
            claim_type="ownership",
            priority=random.choice(["low", "normal", "high"]),
            submission_date=datetime.now().date() - timedelta(days=random.randint(1, 180)),
            has_conflict=random.random() < 0.1,  # 10% have conflicts
            created_at=datetime.now() - timedelta(days=random.randint(1, 365)),
            created_by="system"
        )

        repo.create(claim)
        claims.append(claim)

    logger.debug(f"Created {len(claims)} claims")
    return claims
