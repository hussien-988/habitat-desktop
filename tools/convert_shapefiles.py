# -*- coding: utf-8 -*-
"""
One-time conversion script: Syria Shapefiles (ZIP) → GeoJSON files.
Run once from Habitat-Desktop root:
    python tools/convert_shapefiles.py

Input:  ../Map/OneDrive_*.zip
Output: assets/geojson/*.geojson
"""

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    import shapefile
except ImportError:
    print("ERROR: pyshp not installed. Run: pip install pyshp")
    sys.exit(1)


# Maps output name → (zip filename prefix, shapefile name inside zip)
SHAPEFILES = {
    'country':        ('OneDrive_3', 'syr_admin0'),
    'governorates':   ('OneDrive_4', 'syr_admin1'),
    'districts':      ('OneDrive_5', 'syr_admin2'),
    'subdistricts':   ('OneDrive_6', 'syr_admin3'),
    'neighbourhoods': ('OneDrive_2', 'city_neighbourhoods'),
}


def find_zip(zip_dir: Path, prefix: str) -> Path:
    """Find ZIP file starting with the given prefix."""
    for f in zip_dir.iterdir():
        if f.name.startswith(prefix) and f.suffix == '.zip':
            return f
    raise FileNotFoundError(f"No ZIP file starting with '{prefix}' in {zip_dir}")


def shapefile_to_geojson(shp_path: Path, dbf_path: Path) -> dict:
    """Convert .shp + .dbf to GeoJSON FeatureCollection dict."""
    sf = shapefile.Reader(str(shp_path))
    fields = [f[0] for f in sf.fields[1:]]  # skip DeletionFlag
    all_records = list(sf.shapeRecords())
    sf.close()

    features = []
    for shape_record in all_records:
        geom = shape_record.shape.__geo_interface__
        props = dict(zip(fields, shape_record.record))

        # Decode bytes to str for JSON serialization
        decoded_props = {}
        for k, v in props.items():
            if isinstance(v, bytes):
                try:
                    decoded_props[k] = v.decode('utf-8')
                except UnicodeDecodeError:
                    decoded_props[k] = v.decode('latin-1', errors='replace')
            else:
                decoded_props[k] = v

        features.append({
            'type': 'Feature',
            'geometry': geom,
            'properties': decoded_props,
        })

    return {
        'type': 'FeatureCollection',
        'features': features,
    }


def convert_all(zip_dir: Path, out_dir: Path):
    """Convert all configured shapefiles from ZIP archives to GeoJSON."""
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, (zip_prefix, shp_name) in SHAPEFILES.items():
        out_path = out_dir / f"{name}.geojson"
        print(f"\n[{name}]")

        try:
            zip_path = find_zip(zip_dir, zip_prefix)
            print(f"  ZIP: {zip_path.name}")
        except FileNotFoundError as e:
            print(f"  SKIP: {e}")
            continue

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(tmp_path)

            # Find .shp file (may be in subdirectory)
            shp_files = list(tmp_path.rglob(f"{shp_name}.shp"))
            if not shp_files:
                # Try case-insensitive
                shp_files = [
                    p for p in tmp_path.rglob("*.shp")
                    if p.stem.lower() == shp_name.lower()
                ]

            if not shp_files:
                print(f"  SKIP: '{shp_name}.shp' not found in ZIP")
                continue

            shp_path = shp_files[0]
            dbf_path = shp_path.with_suffix('.dbf')
            print(f"  SHP: {shp_path.name}")

            geojson = shapefile_to_geojson(shp_path, dbf_path)
            feature_count = len(geojson['features'])

            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, ensure_ascii=False, separators=(',', ':'))

            size_kb = out_path.stat().st_size // 1024
            print(f"  OK: {feature_count} features, {size_kb} KB -> {out_path.name}")

            # Print first feature properties as sample
            if geojson['features']:
                sample_props = list(geojson['features'][0]['properties'].keys())
                print(f"  Properties: {sample_props[:8]}")


def decode_field(value):
    """Decode a DBF field value to a plain Python type."""
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8').strip()
        except UnicodeDecodeError:
            return value.decode('latin-1', errors='replace').strip()
    if isinstance(value, str):
        return value.strip()
    return value


def extract_places_json(zip_dir: Path, out_dir: Path):
    """
    Extract syr_pplp_adm4_unocha attributes (no geometry) as compact JSON array.

    Output: assets/geojson/populated_places.json
    Each element: {name_ar, name_en, lat, lng, pcode,
                   admin1_pcode, admin1_ar, admin2_pcode, admin2_ar,
                   admin3_pcode, admin3_ar, is_capital}
    """
    out_path = out_dir / 'populated_places.json'
    print('\n[populated_places]')

    try:
        zip_path = find_zip(zip_dir, 'OneDrive_7')
        print(f'  ZIP: {zip_path.name}')
    except FileNotFoundError as e:
        print(f'  SKIP: {e}')
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmp_path)

        shp_files = list(tmp_path.rglob('syr_pplp_adm4_unocha.shp'))
        if not shp_files:
            shp_files = [p for p in tmp_path.rglob('*.shp')
                         if 'pplp' in p.name.lower() or 'adm4' in p.name.lower()]
        if not shp_files:
            print('  SKIP: shapefile not found in ZIP')
            return

        shp_path = shp_files[0]
        print(f'  SHP: {shp_path.name}')

        sf = shapefile.Reader(str(shp_path))
        fields = [f[0] for f in sf.fields[1:]]
        all_shape_records = list(sf.shapeRecords())
        sf.close()

        places = []
        for shape_record in all_shape_records:
            rec = shape_record.record
            props = {fields[i]: decode_field(rec[i]) for i in range(len(fields))}

            lat = props.get('Latitude_y') or props.get('LATITUDE_Y') or 0
            lng = props.get('Longitude_') or props.get('LONGITUDE_') or 0
            try:
                lat = float(lat)
                lng = float(lng)
            except (TypeError, ValueError):
                continue

            if not lat or not lng:
                continue

            is_cap_raw = props.get('IsAdmin1Ca') or props.get('ISADMIN1CA') or ''
            is_capital = str(is_cap_raw).strip().lower() in ('yes', 'true', '1')

            places.append({
                'name_ar':    props.get('admin4Na_1') or props.get('ADMIN4NA_1') or '',
                'name_en':    props.get('admin4Name') or props.get('ADMIN4NAME') or '',
                'lat':        round(lat, 6),
                'lng':        round(lng, 6),
                'pcode':      props.get('admin4Pcod') or props.get('ADMIN4PCOD') or '',
                'admin1_pcode': props.get('admin1Pcod') or props.get('ADMIN1PCOD') or '',
                'admin1_ar':    props.get('admin1Na_1') or props.get('ADMIN1NA_1') or '',
                'admin2_pcode': props.get('admin2Pcod') or props.get('ADMIN2PCOD') or '',
                'admin2_ar':    props.get('admin2Na_1') or props.get('ADMIN2NA_1') or '',
                'admin3_pcode': props.get('admin3Pcod') or props.get('ADMIN3PCOD') or '',
                'admin3_ar':    props.get('admin3Na_1') or props.get('ADMIN3NA_1') or '',
                'is_capital': is_capital,
            })

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(places, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = out_path.stat().st_size // 1024
    print(f'  OK: {len(places)} places, {size_kb} KB -> {out_path.name}')
    if places:
        print(f'  Sample: {places[0]}')


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    zip_dir = project_root.parent / 'Map'
    out_dir = project_root / 'assets' / 'geojson'

    print(f"ZIP source: {zip_dir}")
    print(f"GeoJSON output: {out_dir}")

    if not zip_dir.exists():
        print(f"\nERROR: Map directory not found: {zip_dir}")
        sys.exit(1)

    convert_all(zip_dir, out_dir)
    extract_places_json(zip_dir, out_dir)
    print("\nConversion complete.")


if __name__ == '__main__':
    main()
