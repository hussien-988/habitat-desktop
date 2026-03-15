# -*- coding: utf-8 -*-
"""
Generate .uhc test packages for TRRCMS import testing.

Python port of TRRCMS-Backend/src/tools/GenerateTestUhc/Program.cs

Usage:
    python tools/generate_test_uhc.py                        # Happy path (valid package)
    python tools/generate_test_uhc.py --scenario invalid     # Validation failure (bad codes)
    python tools/generate_test_uhc.py --scenario quarantine  # Quarantine (bad checksum)
"""

import argparse
import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta


def derive_guid(base_guid: str, seed: str) -> str:
    """Derive a deterministic UUID from a base UUID and seed string."""
    data = f"{base_guid}:{seed}".encode("utf-8")
    h = hashlib.sha256(data).digest()
    return str(uuid.UUID(bytes=h[:16]))


def _create_tables(conn):
    """Create all required tables in the .uhc SQLite database."""
    conn.execute("""
        CREATE TABLE manifest (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE surveys (
            id                       TEXT PRIMARY KEY,
            building_id              TEXT NOT NULL,
            survey_date              TEXT NOT NULL,
            property_unit_id         TEXT,
            gps_coordinates          TEXT,
            interviewee_name         TEXT,
            interviewee_relationship TEXT,
            notes                    TEXT,
            field_collector_id       TEXT,
            contact_person_id        TEXT,
            reference_code           TEXT,
            type                     INTEGER,
            source                   INTEGER,
            status                   INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE buildings (
            id                       TEXT PRIMARY KEY,
            governorate_code         TEXT NOT NULL,
            district_code            TEXT NOT NULL,
            sub_district_code        TEXT NOT NULL,
            community_code           TEXT NOT NULL,
            neighborhood_code        TEXT NOT NULL,
            building_number          TEXT NOT NULL,
            building_type            INTEGER,
            building_status          INTEGER,
            number_of_property_units INTEGER,
            number_of_apartments     INTEGER,
            number_of_shops          INTEGER,
            latitude                 REAL,
            longitude                REAL,
            building_geometry_wkt    TEXT,
            notes                    TEXT,
            building_id              TEXT,
            governorate_name         TEXT,
            district_name            TEXT,
            sub_district_name        TEXT,
            community_name           TEXT,
            neighborhood_name        TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE building_documents (
            id                  TEXT PRIMARY KEY,
            building_id         TEXT NOT NULL,
            original_file_name  TEXT NOT NULL,
            file_size_bytes     INTEGER NOT NULL,
            file_path           TEXT NOT NULL,
            file_hash           TEXT,
            description         TEXT,
            notes               TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE property_units (
            id                  TEXT PRIMARY KEY,
            building_id         TEXT NOT NULL,
            unit_identifier     TEXT NOT NULL,
            unit_type           INTEGER,
            status              INTEGER,
            floor_number        INTEGER,
            number_of_rooms     INTEGER,
            area_square_meters  REAL,
            description         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE persons (
            id                   TEXT PRIMARY KEY,
            family_name_arabic   TEXT NOT NULL,
            first_name_arabic    TEXT NOT NULL,
            father_name_arabic   TEXT NOT NULL,
            mother_name_arabic   TEXT,
            national_id          TEXT,
            year_of_birth        INTEGER,
            email                TEXT,
            mobile_number        TEXT,
            phone_number         TEXT,
            gender               INTEGER,
            nationality          INTEGER,
            household_id         TEXT,
            relationship_to_head INTEGER,
            is_contact_person    INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE households (
            id                          TEXT PRIMARY KEY,
            property_unit_id            TEXT NOT NULL,
            head_of_household_name      TEXT NOT NULL,
            household_size              INTEGER NOT NULL,
            head_of_household_person_id TEXT,
            male_count                  INTEGER DEFAULT 0,
            female_count                INTEGER DEFAULT 0,
            male_child_count            INTEGER DEFAULT 0,
            female_child_count          INTEGER DEFAULT 0,
            male_elderly_count          INTEGER DEFAULT 0,
            female_elderly_count        INTEGER DEFAULT 0,
            male_disabled_count         INTEGER DEFAULT 0,
            female_disabled_count       INTEGER DEFAULT 0,
            notes                       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE person_property_relations (
            id               TEXT PRIMARY KEY,
            person_id        TEXT NOT NULL,
            property_unit_id TEXT NOT NULL,
            relation_type    INTEGER NOT NULL,
            ownership_share  REAL,
            notes            TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE claims (
            id                   TEXT PRIMARY KEY,
            property_unit_id     TEXT NOT NULL,
            claim_type           TEXT NOT NULL,
            claim_source         INTEGER NOT NULL,
            primary_claimant_id  TEXT,
            tenure_contract_type INTEGER,
            ownership_share      REAL,
            claim_description    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE evidences (
            id                          TEXT PRIMARY KEY,
            evidence_type               INTEGER NOT NULL,
            description                 TEXT,
            original_file_name          TEXT,
            file_path                   TEXT,
            file_size_bytes             INTEGER,
            person_id                   TEXT,
            person_property_relation_id TEXT,
            claim_id                    TEXT,
            file_hash                   TEXT,
            document_issued_date        TEXT,
            document_expiry_date        TEXT,
            issuing_authority           TEXT,
            document_reference_number   TEXT,
            notes                       TEXT
        )
    """)


def _insert_manifest(conn, package_id, collector_user_id, now_utc, checksum=""):
    """Insert manifest key-value pairs."""
    vocab_versions = """{
        "ownership_type": "1.0.0",
        "document_type": "1.0.0",
        "building_type": "1.0.0",
        "property_unit_type": "1.0.0",
        "claim_type": "1.0.0",
        "relation_type": "1.0.0",
        "evidence_type": "1.0.0"
    }"""

    manifest = {
        "package_id": package_id,
        "schema_version": "1.2.0",
        "created_utc": now_utc.isoformat(),
        "device_id": "TABLET-TEST-001",
        "app_version": "1.0.0",
        "exported_by_user_id": collector_user_id,
        "exported_date_utc": now_utc.isoformat(),
        "checksum": checksum,
        "digital_signature": "",
        "form_schema_version": "1.0.0",
        "survey_count": "1",
        "building_count": "1",
        "property_unit_count": "2",
        "person_count": "4",
        "household_count": "2",
        "relation_count": "2",
        "claim_count": "1",
        "document_count": "1",
        "building_document_count": "1",
        "total_attachment_size_bytes": "0",
        "vocab_versions": vocab_versions,
    }

    for key, value in manifest.items():
        conn.execute("INSERT INTO manifest (key, value) VALUES (?, ?)", (key, value))


def _insert_data(conn, ids, collector_user_id, now_utc, scenario="valid"):
    """Insert all data rows. scenario controls whether codes are valid or not."""
    survey_date = (now_utc - timedelta(hours=2)).isoformat()

    # Building codes: valid = Aleppo (14), invalid = fake codes (99)
    if scenario == "invalid":
        gov_code, dist_code, sub_code = "99", "99", "99"
        com_code, neigh_code = "999", "999"
        building_num = "99999"
        building_id_code = "99999999999999999"
    else:
        gov_code, dist_code, sub_code = "14", "14", "01"
        com_code, neigh_code = "010", "011"
        building_num = "00001"
        building_id_code = "14140101001100001"

    # Survey
    conn.execute(
        "INSERT INTO surveys VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["survey"], ids["building"], survey_date, ids["unit1"],
            "36.2021,37.1343", "أحمد محمد العلي", "مالك",
            "مسح ميداني لمبنى سكني في حي الجميلية",
            collector_user_id, ids["person1"], "SRV-2026-001", 1, 1, 3,
        ),
    )

    # Building
    conn.execute(
        "INSERT INTO buildings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["building"], gov_code, dist_code, sub_code, com_code, neigh_code, building_num,
            1, 1, 2, 2, 0,
            36.2021, 37.1343,
            "POINT(37.1343 36.2021)",
            "مبنى سكني من 3 طوابق بحالة جيدة",
            building_id_code,
            "حلب", "حلب", "مركز حلب", "حلب المدينة", "الجميلية",
        ),
    )

    # Building document
    conn.execute(
        "INSERT INTO building_documents VALUES (?,?,?,?,?,?,?,?)",
        (
            ids["building_doc"], ids["building"],
            "building_photo_front.jpg", 512000,
            "documents/building_photo_front.jpg",
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "صورة واجهة المبنى الأمامية",
            "تم التقاط الصورة أثناء المسح الميداني",
        ),
    )

    # Property units
    conn.execute(
        "INSERT INTO property_units VALUES (?,?,?,?,?,?,?,?,?)",
        (ids["unit1"], ids["building"], "شقة 1", 1, 1, 1, 4, 120.5, "شقة أرضية مع حديقة صغيرة"),
    )
    conn.execute(
        "INSERT INTO property_units VALUES (?,?,?,?,?,?,?,?,?)",
        (ids["unit2"], ids["building"], "شقة 2", 1, 1, 2, 3, 110.0, "شقة في الطابق الأول"),
    )

    # Persons
    conn.execute(
        "INSERT INTO persons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["person1"], "العلي", "أحمد", "محمد", "فاطمة",
            "01234567890", 1978, None, "+963-944-123456", None,
            1, 1, ids["household1"], 1, 1,
        ),
    )
    conn.execute(
        "INSERT INTO persons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["person2"], "الحسن", "فاطمة", "علي", "زينب",
            "01234567891", 1982, None, "+963-944-123457", None,
            2, 1, ids["household1"], 2, 0,
        ),
    )
    conn.execute(
        "INSERT INTO persons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["person3"], "الخالد", "عمر", "خالد", "سعاد",
            "09876543210", 1985, None, "+963-944-654321", None,
            1, 1, ids["household2"], 1, 0,
        ),
    )
    conn.execute(
        "INSERT INTO persons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["person4"], "الرشيد", "مريم", "رشيد", "هدى",
            None, 1988, None, "+963-944-654322", None,
            2, 1, ids["household2"], 2, 0,
        ),
    )

    # Households
    conn.execute(
        "INSERT INTO households VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["household1"], ids["unit1"], "أحمد محمد العلي", 4, ids["person1"],
            1, 1, 1, 1, 0, 0, 0, 0, "عائلة مقيمة منذ 2005",
        ),
    )
    conn.execute(
        "INSERT INTO households VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["household2"], ids["unit2"], "عمر خالد الخالد", 3, ids["person3"],
            1, 1, 1, 0, 0, 0, 0, 0, "عائلة نازحة من الرقة منذ 2016",
        ),
    )

    # Person-property relations
    conn.execute(
        "INSERT INTO person_property_relations VALUES (?,?,?,?,?,?)",
        (ids["relation1"], ids["person1"], ids["unit1"], 1, 100.0, "مالك بموجب سند ملكية"),
    )
    conn.execute(
        "INSERT INTO person_property_relations VALUES (?,?,?,?,?,?)",
        (ids["relation2"], ids["person3"], ids["unit2"], 3, None, "مستأجر بعقد سنوي"),
    )

    # Claims
    conn.execute(
        "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?)",
        (
            ids["claim1"], ids["unit1"], "Ownership", 1, ids["person1"], 1, 100.0,
            "مطالبة ملكية للشقة 1 بناءً على سند ملكية أصلي",
        ),
    )

    # Evidences
    conn.execute(
        "INSERT INTO evidences VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ids["evidence1"], 2,
            "سند ملكية أصلي صادر عن السجل العقاري في حلب",
            "ownership_deed_ahmed_45678.pdf",
            "documents/ownership_deed_ahmed_45678.pdf",
            245760,
            ids["person1"], ids["relation1"], ids["claim1"],
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "2005-03-15", None,
            "السجل العقاري - حلب",
            "45678/2005",
            "نسخة مصورة عن السند الأصلي",
        ),
    )


def generate_package(scenario="valid", output_dir=None):
    """Generate a .uhc test package.

    Scenarios:
        valid      - Happy path, passes all validation
        invalid    - Bad building codes, triggers ValidationFailed (status 4)
        quarantine - Fake checksum, triggers Quarantine (status 5)
    """
    package_id = str(uuid.uuid4())

    ids = {
        "building": derive_guid(package_id, "building"),
        "unit1": derive_guid(package_id, "unit_1"),
        "unit2": derive_guid(package_id, "unit_2"),
        "person1": derive_guid(package_id, "person_1"),
        "person2": derive_guid(package_id, "person_2"),
        "person3": derive_guid(package_id, "person_3"),
        "person4": derive_guid(package_id, "person_4"),
        "household1": derive_guid(package_id, "household_1"),
        "household2": derive_guid(package_id, "household_2"),
        "relation1": derive_guid(package_id, "relation_1"),
        "relation2": derive_guid(package_id, "relation_2"),
        "claim1": derive_guid(package_id, "claim_1"),
        "evidence1": derive_guid(package_id, "evidence_1"),
        "survey": derive_guid(package_id, "survey_1"),
        "building_doc": derive_guid(package_id, "building_doc_1"),
    }

    collector_user_id = "00000000-0000-0000-0000-000000000000"
    now_utc = datetime.now(timezone.utc)

    suffix = {"valid": "valid", "invalid": "invalid", "quarantine": "quarantine"}
    filename = f"test-package-{suffix.get(scenario, scenario)}.uhc"

    if output_dir is None:
        output_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    output_path = os.path.join(output_dir, filename)

    if os.path.exists(output_path):
        os.remove(output_path)

    conn = sqlite3.connect(output_path)
    _create_tables(conn)

    # Checksum: empty for valid/invalid (backend skips check), fake for quarantine
    checksum = ""
    if scenario == "quarantine":
        checksum = "0000000000000000000000000000000000000000000000000000000000000000"

    _insert_manifest(conn, package_id, collector_user_id, now_utc, checksum=checksum)
    _insert_data(conn, ids, collector_user_id, now_utc, scenario=scenario)

    conn.commit()
    conn.close()

    file_size = os.path.getsize(output_path)
    return {
        "path": output_path,
        "package_id": package_id,
        "size": file_size,
        "scenario": scenario,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate TRRCMS test .uhc packages")
    parser.add_argument(
        "--scenario",
        choices=["valid", "invalid", "quarantine", "all"],
        default="valid",
        help="Test scenario (default: valid)",
    )
    args = parser.parse_args()

    print("=== TRRCMS Test .uhc Package Generator (Python) ===\n")

    scenarios = ["valid", "invalid", "quarantine"] if args.scenario == "all" else [args.scenario]

    for sc in scenarios:
        info = generate_package(scenario=sc)
        label = {"valid": "Happy Path", "invalid": "Validation Failed", "quarantine": "Quarantine"}
        print(f"--- {label.get(sc, sc)} ---")
        print(f"  File:      {info['path']}")
        print(f"  Size:      {info['size']:,} bytes ({info['size'] / 1024:.1f} KB)")
        print(f"  PackageId: {info['package_id']}")
        print()

    print("=== Data Summary (per package) ===")
    print("  Building: 1, Units: 2, Persons: 4, Households: 2")
    print("  Relations: 2, Claims: 1, Evidence: 1, Survey: 1, Bldg Docs: 1")


if __name__ == "__main__":
    main()
