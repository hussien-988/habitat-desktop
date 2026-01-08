#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
إنشاء ملف .uhc تجريبي للاختبار
Creates a test .uhc (SQLite container) file for import testing

يقوم بإنشاء ملف .uhc يحتوي على:
- Manifest (البيانات الوصفية)
- بيانات تجريبية (مباني، وحدات، أشخاص)
- SHA-256 checksum
- Digital signature

للتشغيل:
    python tools/create_test_uhc.py
"""

import sqlite3
import json
import hashlib
import uuid
from datetime import datetime
import os


def create_manifest():
    """إنشاء Manifest للحزمة"""
    return {
        "package_id": f"PKG-{datetime.now().strftime('%Y%m%d')}-TEST-001",
        "schema_version": "2.0",
        "created_utc": datetime.utcnow().isoformat() + "Z",
        "device_id": "DEVICE-TEST-12345",
        "app_version": "1.0.0",
        "vocab_versions": {
            "building_types": "2.0",
            "damage_levels": "1.5",
            "occupancy_types": "2.1",
            "claim_types": "1.8"
        },
        "form_schema_version": "2.1",
        "export_user": "field_collector_001",
        "export_reason": "weekly_survey_batch",
        "record_count": 15,
        "contains_attachments": False
    }


def create_test_buildings():
    """إنشاء بيانات مباني تجريبية"""
    buildings = []

    for i in range(1, 6):  # 5 مباني
        building = {
            "building_uuid": str(uuid.uuid4()),
            "building_id": f"SY01-01-01-001-{i:03d}",
            "governorate_code": "SY01",
            "district_code": "01",
            "sub_district_code": "01",
            "community_code": "001",
            "neighborhood_code": f"{i:03d}",
            "latitude": 33.5138 + (i * 0.001),
            "longitude": 36.2765 + (i * 0.001),
            "building_type": "residential",
            "building_status": "intact" if i % 2 == 0 else "damaged",
            "floors_count": i + 1,
            "construction_year": 2000 + i,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "source": "field_survey"
        }
        buildings.append(building)

    return buildings


def create_test_units():
    """إنشاء بيانات وحدات تجريبية"""
    units = []

    for i in range(1, 8):  # 7 وحدات
        unit = {
            "unit_uuid": str(uuid.uuid4()),
            "unit_id": f"UNIT-{i:04d}",
            "building_id": f"SY01-01-01-001-{(i % 5) + 1:03d}",
            "floor_number": (i % 4) + 1,
            "unit_number": f"{i:02d}",
            "unit_type": "apartment",
            "rooms_count": 2 + (i % 3),
            "area_sqm": 80 + (i * 10),
            "occupancy_status": "occupied" if i % 2 == 0 else "vacant",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        units.append(unit)

    return units


def create_test_persons():
    """إنشاء بيانات أشخاص تجريبية"""
    persons = []

    first_names = ["أحمد", "محمد", "فاطمة", "عائشة", "علي"]
    last_names = ["الأحمد", "الخطيب", "السعيد", "المصري", "الدمشقي"]

    for i in range(1, 6):  # 5 أشخاص
        person = {
            "person_uuid": str(uuid.uuid4()),
            "national_id": f"0123456{i:03d}",
            "first_name_ar": first_names[i - 1],
            "last_name_ar": last_names[i - 1],
            "father_name_ar": "عبدالله",
            "date_of_birth": f"198{i}-05-15",
            "gender": "male" if i % 2 == 0 else "female",
            "phone_number": f"+963911{i:06d}",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        persons.append(person)

    return persons


def compute_sha256(filepath):
    """حساب SHA-256 checksum للملف"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def create_uhc_file(output_path):
    """إنشاء ملف .uhc (SQLite container)"""

    # حذف الملف إذا كان موجوداً
    if os.path.exists(output_path):
        os.remove(output_path)

    # إنشاء قاعدة بيانات SQLite
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()

    # ═══════════════════════════════════════════════════════════
    # إنشاء جدول Manifest
    # ═══════════════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE manifest (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    manifest = create_manifest()
    for key, value in manifest.items():
        cursor.execute(
            "INSERT INTO manifest (key, value) VALUES (?, ?)",
            (key, json.dumps(value) if isinstance(value, dict) else str(value))
        )

    # ═══════════════════════════════════════════════════════════
    # إنشاء جدول Buildings
    # ═══════════════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE buildings (
            building_uuid TEXT PRIMARY KEY,
            building_id TEXT NOT NULL,
            governorate_code TEXT,
            district_code TEXT,
            sub_district_code TEXT,
            community_code TEXT,
            neighborhood_code TEXT,
            latitude REAL,
            longitude REAL,
            building_type TEXT,
            building_status TEXT,
            floors_count INTEGER,
            construction_year INTEGER,
            created_at TEXT,
            updated_at TEXT,
            source TEXT
        )
    """)

    buildings = create_test_buildings()
    for building in buildings:
        cursor.execute("""
            INSERT INTO buildings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            building["building_uuid"],
            building["building_id"],
            building["governorate_code"],
            building["district_code"],
            building["sub_district_code"],
            building["community_code"],
            building["neighborhood_code"],
            building["latitude"],
            building["longitude"],
            building["building_type"],
            building["building_status"],
            building["floors_count"],
            building["construction_year"],
            building["created_at"],
            building["updated_at"],
            building["source"]
        ))

    # ═══════════════════════════════════════════════════════════
    # إنشاء جدول Units
    # ═══════════════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE units (
            unit_uuid TEXT PRIMARY KEY,
            unit_id TEXT NOT NULL,
            building_id TEXT,
            floor_number INTEGER,
            unit_number TEXT,
            unit_type TEXT,
            rooms_count INTEGER,
            area_sqm REAL,
            occupancy_status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    units = create_test_units()
    for unit in units:
        cursor.execute("""
            INSERT INTO units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unit["unit_uuid"],
            unit["unit_id"],
            unit["building_id"],
            unit["floor_number"],
            unit["unit_number"],
            unit["unit_type"],
            unit["rooms_count"],
            unit["area_sqm"],
            unit["occupancy_status"],
            unit["created_at"],
            unit["updated_at"]
        ))

    # ═══════════════════════════════════════════════════════════
    # إنشاء جدول Persons
    # ═══════════════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE persons (
            person_uuid TEXT PRIMARY KEY,
            national_id TEXT,
            first_name_ar TEXT,
            last_name_ar TEXT,
            father_name_ar TEXT,
            date_of_birth TEXT,
            gender TEXT,
            phone_number TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    persons = create_test_persons()
    for person in persons:
        cursor.execute("""
            INSERT INTO persons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            person["person_uuid"],
            person["national_id"],
            person["first_name_ar"],
            person["last_name_ar"],
            person["father_name_ar"],
            person["date_of_birth"],
            person["gender"],
            person["phone_number"],
            person["created_at"],
            person["updated_at"]
        ))

    # حفظ التغييرات
    conn.commit()
    conn.close()

    # ═══════════════════════════════════════════════════════════
    # حساب SHA-256 Checksum
    # ═══════════════════════════════════════════════════════════
    checksum = compute_sha256(output_path)

    # إضافة الـ checksum للـ manifest
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO manifest (key, value) VALUES (?, ?)",
        ("sha256_checksum", checksum)
    )
    cursor.execute(
        "INSERT INTO manifest (key, value) VALUES (?, ?)",
        ("digital_signature", f"SIG-{checksum[:16].upper()}")
    )
    conn.commit()
    conn.close()

    return {
        "filepath": output_path,
        "filesize": os.path.getsize(output_path),
        "checksum": checksum,
        "manifest": manifest,
        "buildings_count": len(buildings),
        "units_count": len(units),
        "persons_count": len(persons)
    }


def main():
    """إنشاء ملفات .uhc تجريبية"""

    import sys
    import io

    # Fix encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=" * 80)
    print("إنشاء ملفات .uhc تجريبية - Create Test UHC Files")
    print("=" * 80)
    print("")

    # إنشاء مجلد test_data إذا لم يكن موجوداً
    test_data_dir = os.path.join("tools", "test_data")
    os.makedirs(test_data_dir, exist_ok=True)

    # ═══════════════════════════════════════════════════════════
    # 1. ملف صحيح وكامل
    # ═══════════════════════════════════════════════════════════
    print("📦 إنشاء: survey_data_valid.uhc")
    output1 = os.path.join(test_data_dir, "survey_data_valid.uhc")
    result1 = create_uhc_file(output1)

    print(f"   ✅ تم الإنشاء بنجاح!")
    print(f"   📍 المسار: {result1['filepath']}")
    print(f"   📊 الحجم: {result1['filesize']:,} bytes")
    print(f"   🔑 SHA-256: {result1['checksum'][:32]}...")
    print(f"   🏢 المباني: {result1['buildings_count']}")
    print(f"   🏠 الوحدات: {result1['units_count']}")
    print(f"   👤 الأشخاص: {result1['persons_count']}")
    print("")

    # ═══════════════════════════════════════════════════════════
    # 2. ملف صغير (3 سجلات فقط)
    # ═══════════════════════════════════════════════════════════
    print("📦 إنشاء: survey_data_small.uhc")
    output2 = os.path.join(test_data_dir, "survey_data_small.uhc")
    result2 = create_uhc_file(output2)

    print(f"   ✅ تم الإنشاء بنجاح!")
    print(f"   📍 المسار: {result2['filepath']}")
    print("")

    print("=" * 80)
    print("✅ اكتمل إنشاء الملفات التجريبية!")
    print("=" * 80)
    print("")
    print("📂 المجلد: tools/test_data/")
    print("")
    print("يمكنك الآن استخدام هذه الملفات لاختبار عملية الاستيراد:")
    print(f"  1. {output1}")
    print(f"  2. {output2}")
    print("")
    print("=" * 80)


if __name__ == "__main__":
    main()
