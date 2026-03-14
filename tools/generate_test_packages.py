# -*- coding: utf-8 -*-
"""
Generate test .uhc packages for Import Wizard testing.

Creates 5 packages with different scenarios:
  1. test_pkg_clean.uhc      — Clean data (happy path)
  2. test_pkg_large.uhc      — Large dataset (pagination)
  3. test_pkg_duplicates.uhc  — Duplicates with pkg_clean (conflicts)
  4. test_pkg_minimal.uhc     — Minimum viable package
  5. test_pkg_batch2.uhc      — Independent batch (list filling)

Usage:
    python tools/generate_test_packages.py
"""

import hashlib
import json
import os
import random
import sqlite3
import uuid
from datetime import datetime, timedelta

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_data")

# Shared constants matching existing test .uhc structure
SCHEMA_VERSION = "2.0"
APP_VERSION = "1.0.0"
FORM_SCHEMA_VERSION = "2.1"
DEVICE_ID = "DEVICE-TEST-DESKTOP"
VOCAB_VERSIONS = json.dumps({
    "building_types": "2.0",
    "damage_levels": "1.5",
    "occupancy_types": "2.1",
    "claim_types": "1.8",
})

# Arabic data pools
FIRST_NAMES_M = [
    "أحمد", "محمد", "خالد", "عمر", "يوسف",
    "حسن", "إبراهيم", "محمود", "سمير", "فيصل",
    "نبيل", "طارق", "وليد", "زياد", "سعيد",
]
FIRST_NAMES_F = [
    "فاطمة", "عائشة", "مريم", "سارة", "نور",
    "ليلى", "هدى", "رانيا", "أميرة", "دينا",
    "زهرة", "هناء", "لمى", "جنى", "ريم",
]
LAST_NAMES = [
    "الحلبي", "الشامي", "الأحمد", "الحسن", "العلي",
    "العمر", "الخليل", "النجار", "القاضي", "المصري",
    "الدمشقي", "الإبراهيم", "الخطيب", "الصباغ", "الحلاب",
]
FATHER_NAMES = [
    "محمد", "أحمد", "علي", "حسن", "خالد",
    "عمر", "إبراهيم", "يوسف", "سعيد", "نبيل",
]

BUILDING_TYPES = [1, 2, 3]  # 1=residential, 2=commercial, 3=mixed_use
BUILDING_STATUSES = [1, 2, 3, 4, 5]  # 1=intact ... 5=destroyed
UNIT_TYPES = [1, 2, 3]  # 1=apartment, 2=shop, 3=office
OCCUPANCY = ["occupied", "vacant", "unknown"]

# Aleppo base coordinates
BASE_LAT = 36.2021
BASE_LON = 37.1343


def _now_iso():
    return datetime.utcnow().isoformat() + "Z"


def _past_iso(days_back=30):
    dt = datetime.utcnow() - timedelta(days=random.randint(1, days_back))
    return dt.isoformat()


def _make_building(
    building_id, gov="01", dist="01", sub="01",
    comm="001", neigh="001", lat=None, lon=None,
    btype=None, bstatus=None, floors=None, year=None,
):
    return {
        "building_id": building_id,
        "building_number": building_id[-5:],
        "governorate_code": gov,
        "district_code": dist,
        "sub_district_code": sub,
        "community_code": comm,
        "neighborhood_code": neigh,
        "building_type": btype if btype is not None else random.choice(BUILDING_TYPES),
        "status": bstatus if bstatus is not None else random.choice(BUILDING_STATUSES),
        "number_of_floors": floors or random.randint(1, 8),
        "year_of_construction": year or random.randint(1970, 2020),
        "latitude": lat or BASE_LAT + random.uniform(-0.02, 0.02),
        "longitude": lon or BASE_LON + random.uniform(-0.02, 0.02),
    }


def _make_unit(building_id, unit_num, floor=None):
    return {
        "unit_identifier": f"UNIT-{unit_num:04d}",
        "building_id": building_id,
        "unit_type": random.choice(UNIT_TYPES),
        "floor_number": floor if floor is not None else random.randint(0, 5),
        "number_of_rooms": random.randint(1, 6),
        "occupancy_status": random.choice(OCCUPANCY),
        "area_square_meters": round(random.uniform(30, 200), 1),
    }


def _make_person(national_id, gender=None):
    is_male = gender == "male" if gender else random.random() > 0.4
    first = random.choice(FIRST_NAMES_M if is_male else FIRST_NAMES_F)
    return {
        "national_id": national_id,
        "first_name_arabic": first,
        "family_name_arabic": random.choice(LAST_NAMES),
        "father_name_arabic": random.choice(FATHER_NAMES),
        "mother_name_arabic": random.choice(FIRST_NAMES_F),
        "year_of_birth": random.randint(1960, 2005),
        "gender": "male" if is_male else "female",
        "nationality": "Syrian",
        "mobile_number": f"+9639{random.randint(10000000, 99999999)}",
        "phone_number": "",
        "email": "",
    }


def _compute_checksum(file_path):
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def create_uhc(file_path, pkg_id, buildings, units, persons):
    """Create a .uhc SQLite file matching the existing test format."""
    if os.path.exists(file_path):
        os.remove(file_path)

    total = len(buildings) + len(units) + len(persons)
    now = _now_iso()

    conn = sqlite3.connect(file_path)
    cur = conn.cursor()

    # manifest table (matching existing format)
    cur.execute("CREATE TABLE manifest (key TEXT PRIMARY KEY, value TEXT)")
    manifest = {
        "package_id": pkg_id,
        "schema_version": SCHEMA_VERSION,
        "created_utc": now,
        "device_id": DEVICE_ID,
        "app_version": APP_VERSION,
        "vocab_versions": VOCAB_VERSIONS,
        "form_schema_version": FORM_SCHEMA_VERSION,
        "exported_by": "test_generator",
        "exported_by_user_id": str(uuid.uuid4()),
        "export_type": "full",
        "record_count": str(total),
        "record_counts": json.dumps({
            "buildings": len(buildings),
            "property_units": len(units),
            "persons": len(persons),
        }),
        "total_attachments": "0",
        "total_size_bytes": "0",
        "sequence_number": "1",
        "total_sequences": "1",
        "contains_attachments": "False",
    }
    for k, v in manifest.items():
        cur.execute("INSERT INTO manifest VALUES (?, ?)", (k, v))

    # Column type mapping for proper SQLite types
    INT_COLS = {
        "building_type", "status", "number_of_floors", "year_of_construction",
        "unit_type", "floor_number", "number_of_rooms",
        "year_of_birth",
    }
    REAL_COLS = {"latitude", "longitude", "area_square_meters"}

    def _col_type(name):
        if name in INT_COLS:
            return "INTEGER"
        if name in REAL_COLS:
            return "REAL"
        return "TEXT"

    def _insert_rows(table_name, rows):
        if not rows:
            return
        cols = list(rows[0].keys())
        col_defs = ", ".join(f'"{c}" {_col_type(c)}' for c in cols)
        cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
        ph = ", ".join(["?"] * len(cols))
        for row in rows:
            vals = []
            for c in cols:
                v = row[c]
                if v is None:
                    vals.append(None)
                elif c in INT_COLS:
                    vals.append(int(v))
                elif c in REAL_COLS:
                    vals.append(float(v))
                else:
                    vals.append(str(v))
            cur.execute(f'INSERT INTO "{table_name}" VALUES ({ph})', vals)

    _insert_rows("buildings", buildings)
    _insert_rows("property_units", units)
    _insert_rows("persons", persons)

    conn.commit()
    conn.close()

    # Compute checksum and signature, then update manifest
    checksum = _compute_checksum(file_path)
    signature = f"SIG-{checksum[:16].upper()}"

    conn = sqlite3.connect(file_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO manifest VALUES (?, ?)", ("sha256_checksum", checksum))
    cur.execute("INSERT INTO manifest VALUES (?, ?)", ("digital_signature", signature))
    conn.commit()
    conn.close()

    return {"path": file_path, "pkg_id": pkg_id, "total": total,
            "buildings": len(buildings), "units": len(units), "persons": len(persons)}


# ----------------------------------------------------------------
# Package generators
# ----------------------------------------------------------------

# Fixed national IDs for clean package (reused in duplicates package)
CLEAN_NATIONAL_IDS = [
    "1100000001", "1100000002", "1100000003", "1100000004", "1100000005",
    "1100000006", "1100000007", "1100000008", "1100000009", "1100000010",
]
CLEAN_BUILDING_IDS = [
    "01010100100100001",
    "01010100100200002",
    "01010100100300003",
]


def generate_clean_package():
    """PKG 1: Clean data — 3 buildings, 6 units, 10 persons."""
    buildings = [
        _make_building(CLEAN_BUILDING_IDS[0], neigh="001", btype=1,
                       bstatus=1, floors=3, year=2005,
                       lat=36.2050, lon=37.1360),
        _make_building(CLEAN_BUILDING_IDS[1], neigh="002", btype=1,
                       bstatus=2, floors=5, year=1998,
                       lat=36.2070, lon=37.1380),
        _make_building(CLEAN_BUILDING_IDS[2], neigh="003", btype=3,
                       bstatus=4, floors=4, year=2010,
                       lat=36.2030, lon=37.1320),
    ]

    unit_num = 1001
    units = []
    for b in buildings:
        for floor in range(b["number_of_floors"]):
            units.append(_make_unit(b["building_id"], unit_num, floor))
            unit_num += 1
            if len(units) >= 6:
                break
        if len(units) >= 6:
            break

    persons = [_make_person(nid) for nid in CLEAN_NATIONAL_IDS]

    path = os.path.join(OUTPUT_DIR, "test_pkg_clean.uhc")
    pkg_id = str(uuid.uuid4())
    return create_uhc(path, pkg_id, buildings, units, persons)


def generate_large_package():
    """PKG 2: Large dataset — 8 buildings, 20 units, 30 persons."""
    buildings = []
    for i in range(8):
        bid = f"0101010020{(i % 5) + 1:02d}{i+1:05d}"
        neigh = f"00{(i % 5) + 1}"
        buildings.append(_make_building(bid, neigh=neigh))

    unit_num = 2001
    units = []
    for b in buildings:
        count = random.randint(2, 4)
        for floor in range(count):
            units.append(_make_unit(b["building_id"], unit_num, floor))
            unit_num += 1
            if len(units) >= 20:
                break
        if len(units) >= 20:
            break

    persons = []
    for i in range(30):
        nid = f"22{i+1:08d}"
        persons.append(_make_person(nid))

    path = os.path.join(OUTPUT_DIR, "test_pkg_large.uhc")
    pkg_id = str(uuid.uuid4())
    return create_uhc(path, pkg_id, buildings, units, persons)


def generate_duplicates_package():
    """PKG 3: Duplicates — reuses national_ids and building_ids from clean package."""
    # Reuse 2 building IDs from clean package (same building_id = property duplicate)
    buildings = [
        _make_building(CLEAN_BUILDING_IDS[0], neigh="001", btype=1,
                       bstatus=1, floors=3, year=2005,
                       lat=36.2050, lon=37.1360),
        _make_building(CLEAN_BUILDING_IDS[1], neigh="002", btype=1,
                       bstatus=2, floors=5, year=1998,
                       lat=36.2070, lon=37.1380),
    ]

    unit_num = 3001
    units = [
        _make_unit(CLEAN_BUILDING_IDS[0], unit_num, 0),
        _make_unit(CLEAN_BUILDING_IDS[0], unit_num + 1, 1),
        _make_unit(CLEAN_BUILDING_IDS[1], unit_num + 2, 0),
    ]

    # Reuse 3 national IDs from clean package (same national_id = person duplicate)
    # + 2 new persons
    persons = [
        _make_person(CLEAN_NATIONAL_IDS[0]),
        _make_person(CLEAN_NATIONAL_IDS[1]),
        _make_person(CLEAN_NATIONAL_IDS[2]),
        _make_person("3300000001"),
        _make_person("3300000002"),
    ]

    path = os.path.join(OUTPUT_DIR, "test_pkg_duplicates.uhc")
    pkg_id = str(uuid.uuid4())
    return create_uhc(path, pkg_id, buildings, units, persons)


def generate_minimal_package():
    """PKG 4: Minimal — 1 building, 1 unit, 1 person."""
    buildings = [
        _make_building("01010100100400001", neigh="004", btype=1,
                       bstatus=1, floors=2, year=2015,
                       lat=36.2100, lon=37.1400),
    ]
    units = [_make_unit("01010100100400001", 4001, 0)]
    persons = [_make_person("4400000001", gender="male")]

    path = os.path.join(OUTPUT_DIR, "test_pkg_minimal.uhc")
    pkg_id = str(uuid.uuid4())
    return create_uhc(path, pkg_id, buildings, units, persons)


def generate_batch2_package():
    """PKG 5: Independent batch — 4 buildings, 8 units, 12 persons."""
    buildings = []
    for i in range(4):
        bid = f"0102010010{(i % 5) + 6:02d}{i+1:05d}"
        neigh = f"00{(i % 5) + 6}"  # neighborhoods 006-010
        buildings.append(_make_building(bid, dist="02", neigh=neigh))

    unit_num = 5001
    units = []
    for b in buildings:
        for floor in range(2):
            units.append(_make_unit(b["building_id"], unit_num, floor))
            unit_num += 1
            if len(units) >= 8:
                break
        if len(units) >= 8:
            break

    persons = []
    for i in range(12):
        nid = f"55{i+1:08d}"
        persons.append(_make_person(nid))

    path = os.path.join(OUTPUT_DIR, "test_pkg_batch2.uhc")
    pkg_id = str(uuid.uuid4())
    return create_uhc(path, pkg_id, buildings, units, persons)


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------

def main():
    random.seed(42)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  UHC Test Package Generator")
    print("=" * 60)

    generators = [
        ("1. Clean (happy path)", generate_clean_package),
        ("2. Large (pagination)", generate_large_package),
        ("3. Duplicates (conflicts)", generate_duplicates_package),
        ("4. Minimal (min viable)", generate_minimal_package),
        ("5. Batch 2 (independent)", generate_batch2_package),
    ]

    results = []
    for label, gen_func in generators:
        info = gen_func()
        results.append((label, info))
        size_kb = os.path.getsize(info["path"]) / 1024
        print(f"\n  {label}")
        print(f"    File:      {os.path.basename(info['path'])}")
        print(f"    Package:   {info['pkg_id']}")
        print(f"    Buildings: {info['buildings']}")
        print(f"    Units:     {info['units']}")
        print(f"    Persons:   {info['persons']}")
        print(f"    Total:     {info['total']} records")
        print(f"    Size:      {size_kb:.1f} KB")

    # Verify each file is valid SQLite
    print("\n" + "-" * 60)
    print("  Verification")
    print("-" * 60)
    all_ok = True
    for label, info in results:
        try:
            conn = sqlite3.connect(info["path"])
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT value FROM manifest WHERE key='package_id'")
            pid = cur.fetchone()[0]
            conn.close()
            status = "OK"
            if "manifest" not in tables:
                status = "MISSING manifest"
                all_ok = False
        except Exception as e:
            status = f"ERROR: {e}"
            all_ok = False
        print(f"  {os.path.basename(info['path'])}: {status} (tables: {tables})")

    print("\n" + "=" * 60)
    if all_ok:
        print("  All 5 packages generated successfully!")
    else:
        print("  Some packages have issues - check above.")
    print(f"  Output: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)

    print("\n  Testing order:")
    print("    1. Upload test_pkg_clean.uhc    (happy path)")
    print("    2. Upload test_pkg_large.uhc    (large dataset)")
    print("    3. Upload test_pkg_duplicates.uhc (conflicts - after clean)")
    print("    4. Upload test_pkg_minimal.uhc  (minimum)")
    print("    5. Upload test_pkg_batch2.uhc   (fill list)")


if __name__ == "__main__":
    main()
