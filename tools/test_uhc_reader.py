#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
اختبار قراءة ملفات .uhc
Test reading .uhc files
"""

import sqlite3
import json
from pathlib import Path


def test_read_uhc(filepath: str):
    """اختبار قراءة ملف .uhc"""

    print("=" * 80)
    print(f"📦 اختبار قراءة ملف: {filepath}")
    print("=" * 80)
    print()

    path = Path(filepath)

    if not path.exists():
        print(f"❌ الملف غير موجود: {filepath}")
        return

    if path.suffix != '.uhc':
        print(f"❌ صيغة الملف غير صحيحة: {path.suffix}")
        return

    try:
        # فتح قاعدة البيانات
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # قراءة الجداول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✅ الجداول الموجودة: {', '.join(tables)}")
        print()

        # قراءة Manifest
        if 'manifest' in tables:
            print("📋 بيانات Manifest:")
            print("-" * 80)
            cursor.execute("SELECT key, value FROM manifest")
            manifest = {}
            for row in cursor.fetchall():
                key = row['key']
                value = row['value']
                try:
                    manifest[key] = json.loads(value)
                except:
                    manifest[key] = value

                # طباعة القيم المهمة
                if key in ['package_id', 'schema_version', 'created_utc', 'record_count', 'sha256_checksum']:
                    print(f"  {key}: {manifest[key]}")
            print()

        # قراءة عدد السجلات في كل جدول
        print("📊 إحصائيات السجلات:")
        print("-" * 80)

        total_records = 0

        if 'buildings' in tables:
            cursor.execute("SELECT COUNT(*) FROM buildings")
            count = cursor.fetchone()[0]
            print(f"  🏢 المباني: {count}")
            total_records += count

        if 'units' in tables:
            cursor.execute("SELECT COUNT(*) FROM units")
            count = cursor.fetchone()[0]
            print(f"  🏠 الوحدات: {count}")
            total_records += count

        if 'persons' in tables:
            cursor.execute("SELECT COUNT(*) FROM persons")
            count = cursor.fetchone()[0]
            print(f"  👤 الأشخاص: {count}")
            total_records += count

        print(f"\n  📦 إجمالي السجلات: {total_records}")
        print()

        # عرض نموذج من البيانات
        if 'buildings' in tables:
            print("🏢 نموذج من بيانات المباني:")
            print("-" * 80)
            cursor.execute("SELECT * FROM buildings LIMIT 1")
            building = cursor.fetchone()
            if building:
                for key in building.keys():
                    print(f"  {key}: {building[key]}")
            print()

        conn.close()

        print("=" * 80)
        print("✅ تم قراءة الملف بنجاح!")
        print("=" * 80)

    except sqlite3.DatabaseError as e:
        print(f"❌ خطأ في قاعدة البيانات: {e}")
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    import io

    # Fix encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # Test both files
    test_read_uhc("tools/test_data/survey_data_valid.uhc")
    print("\n\n")
    test_read_uhc("tools/test_data/survey_data_small.uhc")
