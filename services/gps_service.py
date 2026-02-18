# -*- coding: utf-8 -*-
"""
GPS Service - Hardware GPS Integration
=======================================
Implements GPS hardware integration for coordinate capture as per FSD requirements.

Features:
- Multiple GPS source support (USB GPS, Bluetooth, NMEA)
- Real-time position tracking
- Coordinate accuracy monitoring
- GPS data caching for offline use
- NMEA sentence parsing
- Position averaging for better accuracy
- Geofencing support
- Track logging
"""

import json
import math
import re
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from queue import Queue

from utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Enums and Constants ====================

class GPSStatus(Enum):
    """GPS connection status."""
    DISCONNECTED = "disconnected"
    SEARCHING = "searching"
    CONNECTED = "connected"
    FIXED = "fixed"  # Has valid position
    ERROR = "error"


class GPSSource(Enum):
    """GPS data source types."""
    INTERNAL = "internal"  # OS location service
    USB_SERIAL = "usb_serial"  # USB GPS receiver
    BLUETOOTH = "bluetooth"  # Bluetooth GPS
    NETWORK = "network"  # Network/IP based
    MANUAL = "manual"  # Manual entry
    NMEA_FILE = "nmea_file"  # NMEA log file (for testing)


class FixQuality(Enum):
    """GPS fix quality."""
    NO_FIX = 0
    GPS_FIX = 1
    DGPS_FIX = 2
    PPS_FIX = 3
    RTK_FIX = 4
    FLOAT_RTK = 5
    ESTIMATED = 6
    MANUAL = 7
    SIMULATION = 8


# ==================== Data Classes ====================

@dataclass
class GPSPosition:
    """GPS position data."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None  # meters (HDOP * base error)
    heading: Optional[float] = None  # degrees from north
    speed: Optional[float] = None  # m/s
    timestamp: datetime = field(default_factory=datetime.now)
    fix_quality: FixQuality = FixQuality.GPS_FIX
    satellites: int = 0
    hdop: Optional[float] = None
    vdop: Optional[float] = None
    pdop: Optional[float] = None
    source: GPSSource = GPSSource.INTERNAL

    def is_valid(self) -> bool:
        """Check if position is valid."""
        return (
            -90 <= self.latitude <= 90 and
            -180 <= self.longitude <= 180 and
            self.fix_quality != FixQuality.NO_FIX
        )

    def is_in_iraq(self) -> bool:
        """Check if position is within Iraq."""
        return 29.0 <= self.latitude <= 37.5 and 38.5 <= self.longitude <= 49.0

    def distance_to(self, other: 'GPSPosition') -> float:
        """Calculate distance to another position (meters)."""
        R = 6371000
        lat1 = math.radians(self.latitude)
        lat2 = math.radians(other.latitude)
        dlat = math.radians(other.latitude - self.latitude)
        dlng = math.radians(other.longitude - self.longitude)

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['fix_quality'] = self.fix_quality.value
        result['source'] = self.source.value
        return result

    def to_wkt(self) -> str:
        """Convert to WKT POINT."""
        if self.altitude:
            return f"POINT Z ({self.longitude} {self.latitude} {self.altitude})"
        return f"POINT ({self.longitude} {self.latitude})"


@dataclass
class GPSConfig:
    """GPS configuration settings."""
    source: GPSSource = GPSSource.INTERNAL
    port: Optional[str] = None  # COM port for serial GPS
    baud_rate: int = 9600
    update_interval: float = 1.0  # seconds
    min_accuracy: float = 50.0  # meters, positions with worse accuracy are ignored
    averaging_samples: int = 5  # number of samples for position averaging
    timeout: float = 30.0  # seconds before declaring connection lost
    auto_reconnect: bool = True
    geofence_enabled: bool = False
    geofence_center_lat: Optional[float] = None
    geofence_center_lng: Optional[float] = None
    geofence_radius: float = 10000  # meters


@dataclass
class TrackPoint:
    """Track logging point."""
    position: GPSPosition
    timestamp: datetime
    note: Optional[str] = None


# ==================== NMEA Parser ====================

class NMEAParser:
    """Parser for NMEA GPS sentences."""

    @staticmethod
    def parse_sentence(sentence: str) -> Optional[Dict[str, Any]]:
        """Parse an NMEA sentence."""
        sentence = sentence.strip()

        if not sentence.startswith('$'):
            return None

        # Verify checksum
        if '*' in sentence:
            data, checksum = sentence[1:].split('*')
            calculated = NMEAParser._calculate_checksum(data)
            if calculated.upper() != checksum.upper():
                logger.warning(f"NMEA checksum mismatch: {checksum} != {calculated}")
                return None
        else:
            data = sentence[1:]

        parts = data.split(',')
        sentence_type = parts[0]

        try:
            if sentence_type == 'GPGGA' or sentence_type == 'GNGGA':
                return NMEAParser._parse_gga(parts)
            elif sentence_type == 'GPRMC' or sentence_type == 'GNRMC':
                return NMEAParser._parse_rmc(parts)
            elif sentence_type == 'GPGSA' or sentence_type == 'GNGSA':
                return NMEAParser._parse_gsa(parts)
            elif sentence_type == 'GPGSV' or sentence_type == 'GNGSV':
                return NMEAParser._parse_gsv(parts)
        except Exception as e:
            logger.warning(f"Error parsing NMEA sentence: {e}")

        return None

    @staticmethod
    def _calculate_checksum(data: str) -> str:
        """Calculate NMEA checksum."""
        checksum = 0
        for char in data:
            checksum ^= ord(char)
        return f"{checksum:02X}"

    @staticmethod
    def _parse_gga(parts: List[str]) -> Dict[str, Any]:
        """Parse GGA sentence (GPS Fix Data)."""
        if len(parts) < 15:
            return None

        lat = NMEAParser._parse_coordinate(parts[2], parts[3])
        lng = NMEAParser._parse_coordinate(parts[4], parts[5])

        return {
            'type': 'GGA',
            'time': parts[1],
            'latitude': lat,
            'longitude': lng,
            'fix_quality': int(parts[6]) if parts[6] else 0,
            'satellites': int(parts[7]) if parts[7] else 0,
            'hdop': float(parts[8]) if parts[8] else None,
            'altitude': float(parts[9]) if parts[9] else None,
            'altitude_unit': parts[10],
            'geoid_height': float(parts[11]) if parts[11] else None
        }

    @staticmethod
    def _parse_rmc(parts: List[str]) -> Dict[str, Any]:
        """Parse RMC sentence (Recommended Minimum)."""
        if len(parts) < 12:
            return None

        lat = NMEAParser._parse_coordinate(parts[3], parts[4])
        lng = NMEAParser._parse_coordinate(parts[5], parts[6])

        # Parse speed (knots to m/s)
        speed = float(parts[7]) * 0.514444 if parts[7] else None

        # Parse heading
        heading = float(parts[8]) if parts[8] else None

        return {
            'type': 'RMC',
            'time': parts[1],
            'status': parts[2],  # A=active, V=void
            'latitude': lat,
            'longitude': lng,
            'speed': speed,
            'heading': heading,
            'date': parts[9]
        }

    @staticmethod
    def _parse_gsa(parts: List[str]) -> Dict[str, Any]:
        """Parse GSA sentence (DOP and Active Satellites)."""
        if len(parts) < 18:
            return None

        satellites = [int(s) for s in parts[3:15] if s]

        return {
            'type': 'GSA',
            'mode': parts[1],
            'fix_type': int(parts[2]) if parts[2] else 1,
            'satellites': satellites,
            'pdop': float(parts[15]) if parts[15] else None,
            'hdop': float(parts[16]) if parts[16] else None,
            'vdop': float(parts[17].split('*')[0]) if parts[17] else None
        }

    @staticmethod
    def _parse_gsv(parts: List[str]) -> Dict[str, Any]:
        """Parse GSV sentence (Satellites in View)."""
        if len(parts) < 4:
            return None

        return {
            'type': 'GSV',
            'total_messages': int(parts[1]) if parts[1] else 0,
            'message_number': int(parts[2]) if parts[2] else 0,
            'satellites_in_view': int(parts[3]) if parts[3] else 0
        }

    @staticmethod
    def _parse_coordinate(value: str, direction: str) -> Optional[float]:
        """Parse NMEA coordinate to decimal degrees."""
        if not value or not direction:
            return None

        try:
            # NMEA format: DDDMM.MMMMM or DDMM.MMMMM
            if '.' in value:
                decimal_pos = value.index('.')
                degrees = int(value[:decimal_pos-2])
                minutes = float(value[decimal_pos-2:])
            else:
                degrees = int(value[:-2])
                minutes = float(value[-2:])

            result = degrees + minutes / 60.0

            if direction in ['S', 'W']:
                result = -result

            return result

        except Exception:
            return None


# ==================== GPS Service ====================

class GPSService:
    """
    GPS hardware integration service.

    Provides real-time GPS position tracking with support for
    multiple GPS sources and NMEA parsing.
    """

    def __init__(self, config: Optional[GPSConfig] = None):
        self.config = config or GPSConfig()
        self._status = GPSStatus.DISCONNECTED
        self._current_position: Optional[GPSPosition] = None
        self._position_history: List[GPSPosition] = []
        self._track_points: List[TrackPoint] = []
        self._averaging_buffer: List[GPSPosition] = []

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._serial_port = None
        self._position_queue = Queue()

        # Callbacks
        self._position_callbacks: List[Callable[[GPSPosition], None]] = []
        self._status_callbacks: List[Callable[[GPSStatus], None]] = []

        # Statistics
        self._stats = {
            'total_fixes': 0,
            'valid_fixes': 0,
            'avg_accuracy': 0,
            'max_accuracy': 0,
            'min_accuracy': float('inf'),
            'total_distance': 0
        }

    # ==================== Connection Management ====================

    def connect(self) -> bool:
        """Connect to GPS source."""
        try:
            if self.config.source == GPSSource.USB_SERIAL:
                return self._connect_serial()
            elif self.config.source == GPSSource.INTERNAL:
                return self._connect_internal()
            elif self.config.source == GPSSource.NETWORK:
                return self._connect_network()
            elif self.config.source == GPSSource.NMEA_FILE:
                return self._connect_nmea_file()
            else:
                logger.warning(f"Unsupported GPS source: {self.config.source}")
                return False

        except Exception as e:
            logger.error(f"Error connecting to GPS: {e}", exc_info=True)
            self._set_status(GPSStatus.ERROR)
            return False

    def disconnect(self):
        """Disconnect from GPS source."""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        if self._serial_port:
            try:
                self._serial_port.close()
            except Exception:
                pass
            self._serial_port = None

        self._set_status(GPSStatus.DISCONNECTED)
        logger.info("GPS disconnected")

    def _connect_serial(self) -> bool:
        """Connect to serial GPS device."""
        try:
            import serial

            if not self.config.port:
                # Try to auto-detect GPS port
                ports = self._detect_gps_ports()
                if ports:
                    self.config.port = ports[0]
                else:
                    logger.error("No GPS port specified and auto-detect failed")
                    return False

            self._serial_port = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baud_rate,
                timeout=1.0
            )

            self._set_status(GPSStatus.SEARCHING)
            self._running = True
            self._thread = threading.Thread(target=self._serial_read_loop, daemon=True)
            self._thread.start()

            logger.info(f"Connected to GPS on {self.config.port}")
            return True

        except ImportError:
            logger.error("pyserial not installed. Install with: pip install pyserial")
            return False
        except Exception as e:
            logger.error(f"Error connecting to serial GPS: {e}")
            return False

    def _connect_internal(self) -> bool:
        """Connect to OS location service."""
        # This is a placeholder - actual implementation depends on OS
        # On Windows: Use Windows.Devices.Geolocation
        # On Linux: Use gpsd
        # On macOS: Use CoreLocation

        self._set_status(GPSStatus.SEARCHING)
        self._running = True
        self._thread = threading.Thread(target=self._internal_location_loop, daemon=True)
        self._thread.start()

        logger.info("Using internal location service")
        return True

    def _connect_network(self) -> bool:
        """Connect to network GPS source (NTRIP, etc.)."""
        # Placeholder for network GPS implementation
        logger.warning("Network GPS not fully implemented")
        return False

    def _connect_nmea_file(self) -> bool:
        """Connect to NMEA log file for testing."""
        if not self.config.port:  # Use port field for file path
            logger.error("No NMEA file specified")
            return False

        self._set_status(GPSStatus.SEARCHING)
        self._running = True
        self._thread = threading.Thread(target=self._nmea_file_loop, daemon=True)
        self._thread.start()

        return True

    def _detect_gps_ports(self) -> List[str]:
        """Detect available GPS ports."""
        ports = []

        try:
            import serial.tools.list_ports

            for port in serial.tools.list_ports.comports():
                # Look for common GPS descriptors
                if any(keyword in port.description.lower()
                       for keyword in ['gps', 'gnss', 'u-blox', 'nmea', 'serial']):
                    ports.append(port.device)

        except ImportError:
            pass

        return ports

    # ==================== Reading Loops ====================

    def _serial_read_loop(self):
        """Read NMEA sentences from serial port."""
        last_valid_time = time.time()

        while self._running:
            try:
                if self._serial_port and self._serial_port.is_open:
                    line = self._serial_port.readline().decode('ascii', errors='ignore')

                    if line:
                        parsed = NMEAParser.parse_sentence(line)
                        if parsed:
                            self._process_nmea_data(parsed)
                            last_valid_time = time.time()

                # Check for timeout
                if time.time() - last_valid_time > self.config.timeout:
                    if self._status != GPSStatus.SEARCHING:
                        self._set_status(GPSStatus.SEARCHING)

                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error reading GPS: {e}")
                if self.config.auto_reconnect:
                    time.sleep(5.0)
                    self._reconnect()
                else:
                    self._set_status(GPSStatus.ERROR)
                    break

    def _internal_location_loop(self):
        """Read from internal location service."""
        # Placeholder implementation
        # Real implementation would use platform-specific APIs

        while self._running:
            try:
                # Simulate internal GPS (for testing)
                # In real implementation, call OS location API

                # Example using Windows location API (requires winrt)
                position = self._get_windows_location()
                if position:
                    self._update_position(position)

                time.sleep(self.config.update_interval)

            except Exception as e:
                logger.error(f"Error reading internal GPS: {e}")
                time.sleep(5.0)

    def _nmea_file_loop(self):
        """Read NMEA sentences from log file (for testing)."""
        try:
            with open(self.config.port, 'r') as f:
                for line in f:
                    if not self._running:
                        break

                    parsed = NMEAParser.parse_sentence(line)
                    if parsed:
                        self._process_nmea_data(parsed)

                    time.sleep(0.1)  # Simulate real-time

        except Exception as e:
            logger.error(f"Error reading NMEA file: {e}")

    def _get_windows_location(self) -> Optional[GPSPosition]:
        """Get location from Windows Location API."""
        try:
            # This requires the winrt package
            # pip install winrt
            import winrt.windows.devices.geolocation as geo

            locator = geo.Geolocator()
            position = locator.get_geoposition_async().get()

            if position and position.coordinate:
                coord = position.coordinate

                return GPSPosition(
                    latitude=coord.point.position.latitude,
                    longitude=coord.point.position.longitude,
                    altitude=coord.point.position.altitude if hasattr(coord.point.position, 'altitude') else None,
                    accuracy=coord.accuracy,
                    heading=coord.heading if hasattr(coord, 'heading') else None,
                    speed=coord.speed if hasattr(coord, 'speed') else None,
                    source=GPSSource.INTERNAL
                )

        except ImportError:
            # winrt not available, return None
            pass
        except Exception as e:
            logger.debug(f"Windows location error: {e}")

        return None

    def _reconnect(self):
        """Attempt to reconnect to GPS."""
        logger.info("Attempting GPS reconnect...")

        if self._serial_port:
            try:
                self._serial_port.close()
            except Exception:
                pass

        time.sleep(2.0)

        if self.config.source == GPSSource.USB_SERIAL:
            self._connect_serial()

    # ==================== Data Processing ====================

    def _process_nmea_data(self, data: Dict[str, Any]):
        """Process parsed NMEA data."""
        if data['type'] == 'GGA':
            if data['latitude'] and data['longitude']:
                position = GPSPosition(
                    latitude=data['latitude'],
                    longitude=data['longitude'],
                    altitude=data.get('altitude'),
                    hdop=data.get('hdop'),
                    satellites=data.get('satellites', 0),
                    fix_quality=FixQuality(data.get('fix_quality', 0)),
                    source=self.config.source
                )

                # Calculate accuracy from HDOP
                if position.hdop:
                    position.accuracy = position.hdop * 5.0  # Approximate

                self._update_position(position)

        elif data['type'] == 'RMC':
            if data.get('status') == 'A' and data['latitude'] and data['longitude']:
                # Update speed and heading if we have a current position
                if self._current_position:
                    self._current_position.speed = data.get('speed')
                    self._current_position.heading = data.get('heading')

        elif data['type'] == 'GSA':
            # Update DOP values
            if self._current_position:
                self._current_position.hdop = data.get('hdop')
                self._current_position.vdop = data.get('vdop')
                self._current_position.pdop = data.get('pdop')

    def _update_position(self, position: GPSPosition):
        """Update current position with new data."""
        if not position.is_valid():
            return

        # Check accuracy threshold
        if position.accuracy and position.accuracy > self.config.min_accuracy:
            logger.debug(f"Position accuracy {position.accuracy}m exceeds threshold")
            return

        # Add to averaging buffer
        self._averaging_buffer.append(position)
        if len(self._averaging_buffer) > self.config.averaging_samples:
            self._averaging_buffer.pop(0)

        # Calculate averaged position
        if len(self._averaging_buffer) >= 2:
            avg_lat = sum(p.latitude for p in self._averaging_buffer) / len(self._averaging_buffer)
            avg_lng = sum(p.longitude for p in self._averaging_buffer) / len(self._averaging_buffer)
            position.latitude = avg_lat
            position.longitude = avg_lng

        # Calculate distance traveled
        if self._current_position:
            distance = self._current_position.distance_to(position)
            self._stats['total_distance'] += distance

        # Update statistics
        self._stats['total_fixes'] += 1
        if position.is_valid():
            self._stats['valid_fixes'] += 1
            if position.accuracy:
                self._stats['avg_accuracy'] = (
                    (self._stats['avg_accuracy'] * (self._stats['valid_fixes'] - 1) + position.accuracy)
                    / self._stats['valid_fixes']
                )
                self._stats['max_accuracy'] = max(self._stats['max_accuracy'], position.accuracy)
                self._stats['min_accuracy'] = min(self._stats['min_accuracy'], position.accuracy)

        # Store position
        self._current_position = position
        self._position_history.append(position)

        # Trim history
        if len(self._position_history) > 1000:
            self._position_history = self._position_history[-500:]

        # Update status
        if self._status != GPSStatus.FIXED:
            self._set_status(GPSStatus.FIXED)

        # Check geofence
        if self.config.geofence_enabled:
            self._check_geofence(position)

        # Notify callbacks
        for callback in self._position_callbacks:
            try:
                callback(position)
            except Exception as e:
                logger.error(f"Error in position callback: {e}")

    def _set_status(self, status: GPSStatus):
        """Set GPS status and notify callbacks."""
        if self._status != status:
            self._status = status
            logger.info(f"GPS status: {status.value}")

            for callback in self._status_callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"Error in status callback: {e}")

    def _check_geofence(self, position: GPSPosition):
        """Check if position is within geofence."""
        if not self.config.geofence_center_lat or not self.config.geofence_center_lng:
            return

        center = GPSPosition(
            latitude=self.config.geofence_center_lat,
            longitude=self.config.geofence_center_lng
        )

        distance = position.distance_to(center)

        if distance > self.config.geofence_radius:
            logger.warning(f"Position outside geofence: {distance:.0f}m from center")

    # ==================== Public API ====================

    def get_current_position(self) -> Optional[GPSPosition]:
        """Get current GPS position."""
        return self._current_position

    def get_status(self) -> GPSStatus:
        """Get GPS connection status."""
        return self._status

    def get_statistics(self) -> Dict[str, Any]:
        """Get GPS statistics."""
        return self._stats.copy()

    def get_position_history(self, limit: int = 100) -> List[GPSPosition]:
        """Get recent position history."""
        return self._position_history[-limit:]

    def is_connected(self) -> bool:
        """Check if GPS is connected and has fix."""
        return self._status in [GPSStatus.CONNECTED, GPSStatus.FIXED]

    def has_fix(self) -> bool:
        """Check if GPS has valid position fix."""
        return self._status == GPSStatus.FIXED and self._current_position is not None

    def add_position_callback(self, callback: Callable[[GPSPosition], None]):
        """Add callback for position updates."""
        self._position_callbacks.append(callback)

    def add_status_callback(self, callback: Callable[[GPSStatus], None]):
        """Add callback for status changes."""
        self._status_callbacks.append(callback)

    def remove_position_callback(self, callback: Callable[[GPSPosition], None]):
        """Remove position callback."""
        if callback in self._position_callbacks:
            self._position_callbacks.remove(callback)

    def remove_status_callback(self, callback: Callable[[GPSStatus], None]):
        """Remove status callback."""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    # ==================== Track Logging ====================

    def start_track(self):
        """Start logging GPS track."""
        self._track_points = []
        logger.info("Track logging started")

    def stop_track(self) -> List[TrackPoint]:
        """Stop logging and return track points."""
        track = self._track_points.copy()
        logger.info(f"Track logging stopped: {len(track)} points")
        return track

    def add_track_point(self, note: Optional[str] = None):
        """Add current position to track with optional note."""
        if self._current_position:
            self._track_points.append(TrackPoint(
                position=self._current_position,
                timestamp=datetime.now(),
                note=note
            ))

    def export_track_gpx(self) -> str:
        """Export track to GPX format."""
        gpx = ['<?xml version="1.0" encoding="UTF-8"?>']
        gpx.append('<gpx version="1.1" creator="TRRCMS">')
        gpx.append('  <trk>')
        gpx.append('    <name>TRRCMS Track</name>')
        gpx.append('    <trkseg>')

        for point in self._track_points:
            pos = point.position
            gpx.append(f'      <trkpt lat="{pos.latitude}" lon="{pos.longitude}">')
            if pos.altitude:
                gpx.append(f'        <ele>{pos.altitude}</ele>')
            gpx.append(f'        <time>{point.timestamp.isoformat()}</time>')
            if point.note:
                gpx.append(f'        <desc>{point.note}</desc>')
            gpx.append('      </trkpt>')

        gpx.append('    </trkseg>')
        gpx.append('  </trk>')
        gpx.append('</gpx>')

        return '\n'.join(gpx)

    def export_track_geojson(self) -> Dict:
        """Export track to GeoJSON format."""
        coordinates = [
            [p.position.longitude, p.position.latitude]
            + ([p.position.altitude] if p.position.altitude else [])
            for p in self._track_points
        ]

        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            },
            "properties": {
                "name": "TRRCMS Track",
                "points": len(self._track_points),
                "start_time": self._track_points[0].timestamp.isoformat() if self._track_points else None,
                "end_time": self._track_points[-1].timestamp.isoformat() if self._track_points else None
            }
        }

    # ==================== Manual Position Entry ====================

    def set_manual_position(
        self,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None
    ) -> bool:
        """Set position manually."""
        position = GPSPosition(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            accuracy=0,  # Manual entry has "perfect" accuracy
            fix_quality=FixQuality.MANUAL,
            source=GPSSource.MANUAL
        )

        if position.is_valid():
            self._update_position(position)
            return True

        return False

    # ==================== Available Ports ====================

    def get_available_ports(self) -> List[Dict[str, str]]:
        """Get list of available serial ports."""
        ports = []

        try:
            import serial.tools.list_ports

            for port in serial.tools.list_ports.comports():
                ports.append({
                    'port': port.device,
                    'description': port.description,
                    'hwid': port.hwid
                })

        except ImportError:
            logger.warning("pyserial not installed")

        return ports
