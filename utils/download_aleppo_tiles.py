# -*- coding: utf-8 -*-
"""
Download OpenStreetMap tiles for Aleppo, Syria area for offline use.
Stores tiles in MBTiles format (SQLite database).

Aleppo bounding box:
  - North: 36.25
  - South: 36.15
  - East: 37.22
  - West: 37.08
"""

import os
import sys
import sqlite3
import requests
import time
import math
from pathlib import Path

# Aleppo, Syria bounding box
BBOX = {
    'north': 36.26,
    'south': 36.14,
    'east': 37.23,
    'west': 37.07
}

# Zoom levels to download (10-16 covers city-level detail)
ZOOM_LEVELS = range(10, 17)

# Output file
OUTPUT_DIR = Path(__file__).parent.parent / "data"
MBTILES_FILE = OUTPUT_DIR / "aleppo_tiles.mbtiles"

# Tile server (OpenStreetMap)
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# User agent (required by OSM)
HEADERS = {
    'User-Agent': 'UN-Habitat TRRCMS/1.0 (Humanitarian Use; contact: un-habitat@example.org)'
}


def deg2num(lat_deg, lon_deg, zoom):
    """Convert lat/lon to tile numbers."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)


def get_tile_range(bbox, zoom):
    """Get tile range for bounding box at given zoom level."""
    x1, y1 = deg2num(bbox['north'], bbox['west'], zoom)
    x2, y2 = deg2num(bbox['south'], bbox['east'], zoom)
    return {
        'x_min': min(x1, x2),
        'x_max': max(x1, x2),
        'y_min': min(y1, y2),
        'y_max': max(y1, y2)
    }


def create_mbtiles_db(filepath):
    """Create MBTiles database with required schema."""
    conn = sqlite3.connect(filepath)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            name TEXT,
            value TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB,
            PRIMARY KEY (zoom_level, tile_column, tile_row)
        )
    ''')

    # Add metadata
    metadata = [
        ('name', 'Aleppo Syria'),
        ('type', 'baselayer'),
        ('version', '1.0'),
        ('description', 'OpenStreetMap tiles for Aleppo, Syria - UN-Habitat TRRCMS'),
        ('format', 'png'),
        ('bounds', f"{BBOX['west']},{BBOX['south']},{BBOX['east']},{BBOX['north']}"),
        ('center', f"{(BBOX['west']+BBOX['east'])/2},{(BBOX['north']+BBOX['south'])/2},14"),
        ('minzoom', str(min(ZOOM_LEVELS))),
        ('maxzoom', str(max(ZOOM_LEVELS))),
    ]

    cursor.execute('DELETE FROM metadata')
    cursor.executemany('INSERT INTO metadata (name, value) VALUES (?, ?)', metadata)

    conn.commit()
    return conn


def download_tiles(conn):
    """Download tiles and store in MBTiles database."""
    cursor = conn.cursor()

    total_tiles = 0
    downloaded = 0
    failed = 0
    skipped = 0

    # Calculate total tiles
    for zoom in ZOOM_LEVELS:
        tile_range = get_tile_range(BBOX, zoom)
        total_tiles += (tile_range['x_max'] - tile_range['x_min'] + 1) * \
                       (tile_range['y_max'] - tile_range['y_min'] + 1)

    print(f"Total tiles to download: {total_tiles}")
    print(f"Zoom levels: {min(ZOOM_LEVELS)} - {max(ZOOM_LEVELS)}")
    print("-" * 50)

    for zoom in ZOOM_LEVELS:
        tile_range = get_tile_range(BBOX, zoom)
        zoom_tiles = 0

        print(f"\nZoom level {zoom}:")
        print(f"  X range: {tile_range['x_min']} - {tile_range['x_max']}")
        print(f"  Y range: {tile_range['y_min']} - {tile_range['y_max']}")

        for x in range(tile_range['x_min'], tile_range['x_max'] + 1):
            for y in range(tile_range['y_min'], tile_range['y_max'] + 1):
                # Check if tile already exists
                cursor.execute(
                    'SELECT 1 FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?',
                    (zoom, x, flip_y(y, zoom))
                )
                if cursor.fetchone():
                    skipped += 1
                    continue

                # Download tile
                url = TILE_URL.format(z=zoom, x=x, y=y)
                try:
                    response = requests.get(url, headers=HEADERS, timeout=30)
                    if response.status_code == 200:
                        # MBTiles uses TMS scheme (y is flipped)
                        tms_y = flip_y(y, zoom)
                        cursor.execute(
                            'INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)',
                            (zoom, x, tms_y, response.content)
                        )
                        downloaded += 1
                        zoom_tiles += 1
                    else:
                        failed += 1
                        print(f"  Failed: {url} - Status {response.status_code}")
                except Exception as e:
                    failed += 1
                    print(f"  Error: {url} - {e}")

                # Progress
                progress = (downloaded + skipped + failed) / total_tiles * 100
                print(f"\r  Progress: {progress:.1f}% ({downloaded} downloaded, {skipped} skipped, {failed} failed)", end='')

                # Rate limiting (be nice to OSM servers)
                time.sleep(0.1)

        # Commit after each zoom level
        conn.commit()
        print(f"\n  Zoom {zoom} complete: {zoom_tiles} tiles")

    print("\n" + "-" * 50)
    print(f"Download complete!")
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")

    return downloaded


def flip_y(y, zoom):
    """Convert XYZ y to TMS y (flip)."""
    return (2 ** zoom) - 1 - y


def main():
    print("=" * 50)
    print("Aleppo Map Tiles Downloader")
    print("UN-Habitat TRRCMS - Offline Map Support")
    print("=" * 50)
    print()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Create/open database
    print(f"Output file: {MBTILES_FILE}")
    conn = create_mbtiles_db(MBTILES_FILE)

    try:
        download_tiles(conn)
    finally:
        conn.close()

    # Print file size
    size_mb = MBTILES_FILE.stat().st_size / (1024 * 1024)
    print(f"\nFile size: {size_mb:.2f} MB")
    print("\nDone! You can now use the map offline.")


if __name__ == "__main__":
    main()
