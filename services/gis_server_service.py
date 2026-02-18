# -*- coding: utf-8 -*-
"""
GIS Server Service - WFS/WMS Implementation
============================================
Implements OGC-compliant web services for QGIS integration as per FSD requirements.

Features:
- WFS (Web Feature Service) for vector data access
- WMS (Web Map Service) for rendered map tiles
- GeoJSON REST API endpoints
- Spatial indexing support
- CRS transformation (EPSG:4326, local systems)
- QGIS project file generation
- Layer styling (SLD)
"""

import json
import math
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

from utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Enums and Data Classes ====================

class ServiceType(Enum):
    """OGC Service Types."""
    WFS = "WFS"
    WMS = "WMS"
    WCS = "WCS"
    WMTS = "WMTS"


class OutputFormat(Enum):
    """Supported output formats."""
    GEOJSON = "application/json"
    GML = "application/gml+xml"
    KML = "application/vnd.google-earth.kml+xml"
    SHAPEFILE = "application/x-shapefile"
    PNG = "image/png"
    JPEG = "image/jpeg"
    SVG = "image/svg+xml"


class CRS(Enum):
    """Coordinate Reference Systems."""
    WGS84 = "EPSG:4326"
    WEB_MERCATOR = "EPSG:3857"
    UTM_37N = "EPSG:32637"  # UTM Zone 37N for Syria/Iraq
    UTM_38N = "EPSG:32638"  # UTM Zone 38N for Iraq


@dataclass
class BoundingBox:
    """Geographic bounding box."""
    min_x: float  # min longitude
    min_y: float  # min latitude
    max_x: float  # max longitude
    max_y: float  # max latitude
    crs: str = "EPSG:4326"

    def to_wkt(self) -> str:
        """Convert to WKT POLYGON."""
        return f"POLYGON(({self.min_x} {self.min_y}, {self.max_x} {self.min_y}, {self.max_x} {self.max_y}, {self.min_x} {self.max_y}, {self.min_x} {self.min_y}))"

    def contains(self, x: float, y: float) -> bool:
        """Check if point is within bounding box."""
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def intersects(self, other: 'BoundingBox') -> bool:
        """Check if bounding boxes intersect."""
        return not (self.max_x < other.min_x or self.min_x > other.max_x or
                   self.max_y < other.min_y or self.min_y > other.max_y)


@dataclass
class LayerDefinition:
    """Definition of a GIS layer."""
    name: str
    title: str
    title_ar: str
    abstract: str
    abstract_ar: str
    geometry_type: str  # Point, Polygon, LineString
    srs: str = "EPSG:4326"
    queryable: bool = True
    bbox: Optional[BoundingBox] = None
    style: Optional[Dict[str, Any]] = None
    attributes: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.bbox:
            result['bbox'] = asdict(self.bbox)
        return result


@dataclass
class WFSRequest:
    """WFS Request parameters."""
    service: str = "WFS"
    version: str = "2.0.0"
    request: str = "GetCapabilities"
    type_names: Optional[List[str]] = None
    output_format: str = "application/json"
    bbox: Optional[BoundingBox] = None
    srs_name: str = "EPSG:4326"
    max_features: int = 1000
    start_index: int = 0
    filter_: Optional[str] = None  # CQL or OGC Filter
    property_names: Optional[List[str]] = None


@dataclass
class WMSRequest:
    """WMS Request parameters."""
    service: str = "WMS"
    version: str = "1.3.0"
    request: str = "GetCapabilities"
    layers: Optional[List[str]] = None
    styles: Optional[List[str]] = None
    crs: str = "EPSG:4326"
    bbox: Optional[BoundingBox] = None
    width: int = 256
    height: int = 256
    format_: str = "image/png"
    transparent: bool = True
    bgcolor: str = "0xFFFFFF"


# ==================== GIS Server Service ====================

class GISServerService:
    """
    GIS Server Service for OGC-compliant web services.

    Provides WFS/WMS endpoints for QGIS integration as per FSD 15.4.
    """

    # Iraq approximate bounding box
    IRAQ_BBOX = BoundingBox(
        min_x=38.5,
        min_y=29.0,
        max_x=49.0,
        max_y=37.5,
        crs="EPSG:4326"
    )

    # Aleppo approximate bounding box
    ALEPPO_BBOX = BoundingBox(
        min_x=36.8,
        min_y=36.0,
        max_x=37.5,
        max_y=36.5,
        crs="EPSG:4326"
    )

    def __init__(self, db_connection, base_url: str = "http://localhost:8080/gis"):
        self.db = db_connection
        self.base_url = base_url
        self._layers = self._define_layers()

    def _define_layers(self) -> Dict[str, LayerDefinition]:
        """Define available GIS layers."""
        return {
            "buildings": LayerDefinition(
                name="buildings",
                title="Buildings",
                title_ar="المباني",
                abstract="Building footprints and locations",
                abstract_ar="مواقع ومساحات المباني",
                geometry_type="Polygon",
                queryable=True,
                bbox=self.ALEPPO_BBOX,
                style={
                    "fill_color": "#0072BC",
                    "fill_opacity": 0.6,
                    "stroke_color": "#004A7C",
                    "stroke_width": 1
                },
                attributes=[
                    {"name": "building_id", "type": "string"},
                    {"name": "building_uuid", "type": "string"},
                    {"name": "neighborhood_code", "type": "string"},
                    {"name": "building_type", "type": "string"},
                    {"name": "building_status", "type": "string"},
                    {"name": "number_of_units", "type": "integer"}
                ]
            ),
            "units": LayerDefinition(
                name="units",
                title="Property Units",
                title_ar="الوحدات العقارية",
                abstract="Property units within buildings",
                abstract_ar="الوحدات العقارية داخل المباني",
                geometry_type="Point",
                queryable=True,
                bbox=self.ALEPPO_BBOX,
                style={
                    "marker_type": "circle",
                    "marker_size": 6,
                    "fill_color": "#28A745",
                    "stroke_color": "#1E7B34"
                },
                attributes=[
                    {"name": "unit_id", "type": "string"},
                    {"name": "unit_uuid", "type": "string"},
                    {"name": "building_id", "type": "string"},
                    {"name": "unit_type", "type": "string"},
                    {"name": "floor_number", "type": "integer"}
                ]
            ),
            "claims": LayerDefinition(
                name="claims",
                title="Claims",
                title_ar="المطالبات",
                abstract="Claim locations with status information",
                abstract_ar="مواقع المطالبات مع معلومات الحالة",
                geometry_type="Point",
                queryable=True,
                bbox=self.ALEPPO_BBOX,
                style={
                    "marker_type": "square",
                    "marker_size": 8,
                    "fill_color": "#FFC107",
                    "stroke_color": "#D39E00"
                },
                attributes=[
                    {"name": "claim_uuid", "type": "string"},
                    {"name": "case_number", "type": "string"},
                    {"name": "case_status", "type": "string"},
                    {"name": "building_id", "type": "string"},
                    {"name": "unit_id", "type": "string"}
                ]
            ),
            "damage": LayerDefinition(
                name="damage",
                title="Damage Assessment",
                title_ar="تقييم الأضرار",
                abstract="Damage assessment locations with severity",
                abstract_ar="مواقع تقييم الأضرار مع مستوى الخطورة",
                geometry_type="Point",
                queryable=True,
                bbox=self.ALEPPO_BBOX,
                style={
                    "marker_type": "triangle",
                    "marker_size": 10,
                    "fill_color": "#DC3545",
                    "stroke_color": "#A71D2A"
                },
                attributes=[
                    {"name": "damage_id", "type": "string"},
                    {"name": "building_id", "type": "string"},
                    {"name": "damage_type", "type": "string"},
                    {"name": "severity", "type": "string"},
                    {"name": "assessment_date", "type": "date"}
                ]
            ),
            "occupancy": LayerDefinition(
                name="occupancy",
                title="Occupancy Distribution",
                title_ar="توزيع الإشغال",
                abstract="Occupancy distribution and household density",
                abstract_ar="توزيع الإشغال وكثافة الأسر",
                geometry_type="Point",
                queryable=True,
                bbox=self.ALEPPO_BBOX,
                style={
                    "marker_type": "circle",
                    "marker_size": 5,
                    "fill_color": "#17A2B8",
                    "stroke_color": "#117A8B"
                },
                attributes=[
                    {"name": "unit_id", "type": "string"},
                    {"name": "occupancy_status", "type": "string"},
                    {"name": "household_count", "type": "integer"},
                    {"name": "total_persons", "type": "integer"}
                ]
            )
        }

    # ==================== WFS Operations ====================

    def handle_wfs_request(self, request: WFSRequest) -> Union[str, Dict, bytes]:
        """Handle WFS request and return appropriate response."""
        if request.request == "GetCapabilities":
            return self.wfs_get_capabilities()
        elif request.request == "DescribeFeatureType":
            return self.wfs_describe_feature_type(request.type_names)
        elif request.request == "GetFeature":
            return self.wfs_get_feature(request)
        else:
            return {"error": f"Unsupported WFS request: {request.request}"}

    def wfs_get_capabilities(self) -> str:
        """Generate WFS GetCapabilities XML response."""
        root = ET.Element("wfs:WFS_Capabilities", {
            "version": "2.0.0",
            "xmlns:wfs": "http://www.opengis.net/wfs/2.0",
            "xmlns:ows": "http://www.opengis.net/ows/1.1",
            "xmlns:gml": "http://www.opengis.net/gml/3.2",
            "xmlns:xlink": "http://www.w3.org/1999/xlink"
        })

        # Service Identification
        service_id = ET.SubElement(root, "ows:ServiceIdentification")
        ET.SubElement(service_id, "ows:Title").text = "TRRCMS WFS Service"
        ET.SubElement(service_id, "ows:Abstract").text = "Web Feature Service for UN-Habitat TRRCMS"
        ET.SubElement(service_id, "ows:ServiceType").text = "WFS"
        ET.SubElement(service_id, "ows:ServiceTypeVersion").text = "2.0.0"

        # Service Provider
        provider = ET.SubElement(root, "ows:ServiceProvider")
        ET.SubElement(provider, "ows:ProviderName").text = "UN-Habitat"

        # Operations Metadata
        ops = ET.SubElement(root, "ows:OperationsMetadata")
        for op_name in ["GetCapabilities", "DescribeFeatureType", "GetFeature"]:
            op = ET.SubElement(ops, "ows:Operation", {"name": op_name})
            dcp = ET.SubElement(op, "ows:DCP")
            http = ET.SubElement(dcp, "ows:HTTP")
            ET.SubElement(http, "ows:Get", {"xlink:href": f"{self.base_url}/wfs?"})
            ET.SubElement(http, "ows:Post", {"xlink:href": f"{self.base_url}/wfs"})

        # Feature Type List
        ft_list = ET.SubElement(root, "wfs:FeatureTypeList")
        for layer_name, layer_def in self._layers.items():
            ft = ET.SubElement(ft_list, "wfs:FeatureType")
            ET.SubElement(ft, "wfs:Name").text = layer_name
            ET.SubElement(ft, "wfs:Title").text = layer_def.title
            ET.SubElement(ft, "wfs:Abstract").text = layer_def.abstract
            ET.SubElement(ft, "wfs:DefaultCRS").text = layer_def.srs

            if layer_def.bbox:
                bbox_elem = ET.SubElement(ft, "ows:WGS84BoundingBox")
                ET.SubElement(bbox_elem, "ows:LowerCorner").text = f"{layer_def.bbox.min_x} {layer_def.bbox.min_y}"
                ET.SubElement(bbox_elem, "ows:UpperCorner").text = f"{layer_def.bbox.max_x} {layer_def.bbox.max_y}"

        return ET.tostring(root, encoding="unicode", method="xml")

    def wfs_describe_feature_type(self, type_names: Optional[List[str]] = None) -> str:
        """Generate WFS DescribeFeatureType XML response."""
        root = ET.Element("xsd:schema", {
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "xmlns:gml": "http://www.opengis.net/gml/3.2",
            "xmlns:trrcms": f"{self.base_url}/schema"
        })

        layers_to_describe = type_names if type_names else list(self._layers.keys())

        for layer_name in layers_to_describe:
            if layer_name not in self._layers:
                continue

            layer_def = self._layers[layer_name]

            # Complex type definition
            complex_type = ET.SubElement(root, "xsd:complexType", {"name": f"{layer_name}Type"})
            complex_content = ET.SubElement(complex_type, "xsd:complexContent")
            extension = ET.SubElement(complex_content, "xsd:extension", {"base": "gml:AbstractFeatureType"})
            sequence = ET.SubElement(extension, "xsd:sequence")

            # Geometry element
            ET.SubElement(sequence, "xsd:element", {
                "name": "geometry",
                "type": f"gml:{layer_def.geometry_type}PropertyType",
                "minOccurs": "0"
            })

            # Attribute elements
            for attr in layer_def.attributes:
                xsd_type = {
                    "string": "xsd:string",
                    "integer": "xsd:integer",
                    "double": "xsd:double",
                    "date": "xsd:date",
                    "datetime": "xsd:dateTime",
                    "boolean": "xsd:boolean"
                }.get(attr["type"], "xsd:string")

                ET.SubElement(sequence, "xsd:element", {
                    "name": attr["name"],
                    "type": xsd_type,
                    "minOccurs": "0"
                })

            # Element definition
            ET.SubElement(root, "xsd:element", {
                "name": layer_name,
                "type": f"trrcms:{layer_name}Type",
                "substitutionGroup": "gml:AbstractFeature"
            })

        return ET.tostring(root, encoding="unicode", method="xml")

    def wfs_get_feature(self, request: WFSRequest) -> Dict:
        """Execute WFS GetFeature request and return GeoJSON."""
        if not request.type_names:
            return {"error": "No type names specified"}

        features = []

        for type_name in request.type_names:
            if type_name == "buildings":
                features.extend(self._get_buildings_features(request))
            elif type_name == "units":
                features.extend(self._get_units_features(request))
            elif type_name == "claims":
                features.extend(self._get_claims_features(request))
            elif type_name == "damage":
                features.extend(self._get_damage_features(request))
            elif type_name == "occupancy":
                features.extend(self._get_occupancy_features(request))

        return {
            "type": "FeatureCollection",
            "name": "TRRCMS_" + "_".join(request.type_names),
            "crs": {
                "type": "name",
                "properties": {"name": f"urn:ogc:def:crs:{request.srs_name.replace(':', '::')}"}
            },
            "numberMatched": len(features),
            "numberReturned": len(features),
            "features": features
        }

    def _get_buildings_features(self, request: WFSRequest) -> List[Dict]:
        """Get building features."""
        try:
            query = """
                SELECT building_uuid, building_id, neighborhood_code,
                       building_type, building_status, number_of_units,
                       latitude, longitude, polygon_wkt
                FROM buildings
                WHERE (latitude IS NOT NULL OR polygon_wkt IS NOT NULL)
            """
            params = []

            # Apply bbox filter
            if request.bbox:
                query += " AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"
                params.extend([request.bbox.min_y, request.bbox.max_y,
                              request.bbox.min_x, request.bbox.max_x])

            query += f" LIMIT {request.max_features} OFFSET {request.start_index}"

            cursor = self.db.cursor()
            cursor.execute(query, params)

            features = []
            for row in cursor.fetchall():
                geometry = None
                if row[8]:  # polygon_wkt
                    geometry = self._wkt_to_geojson(row[8])
                elif row[6] and row[7]:  # lat, lon
                    geometry = {"type": "Point", "coordinates": [row[7], row[6]]}

                if geometry:
                    features.append({
                        "type": "Feature",
                        "id": row[0],
                        "geometry": geometry,
                        "properties": {
                            "building_uuid": row[0],
                            "building_id": row[1],
                            "neighborhood_code": row[2],
                            "building_type": row[3],
                            "building_status": row[4],
                            "number_of_units": row[5]
                        }
                    })

            return features

        except Exception as e:
            logger.error(f"Error getting building features: {e}")
            return []

    def _get_units_features(self, request: WFSRequest) -> List[Dict]:
        """Get property unit features."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT u.unit_uuid, u.unit_id, u.building_uuid, u.unit_type, u.floor_number,
                       b.latitude, b.longitude
                FROM units u
                JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                LIMIT ? OFFSET ?
            """, (request.max_features, request.start_index))

            features = []
            for row in cursor.fetchall():
                features.append({
                    "type": "Feature",
                    "id": row[0],
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row[6], row[5]]
                    },
                    "properties": {
                        "unit_uuid": row[0],
                        "unit_id": row[1],
                        "building_id": row[2],
                        "unit_type": row[3],
                        "floor_number": row[4]
                    }
                })

            return features

        except Exception as e:
            logger.error(f"Error getting unit features: {e}")
            return []

    def _get_claims_features(self, request: WFSRequest) -> List[Dict]:
        """Get claim features."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT c.claim_uuid, c.case_number, c.case_status,
                       b.building_id, u.unit_id,
                       b.latitude, b.longitude
                FROM claims c
                JOIN units u ON c.unit_uuid = u.unit_uuid
                JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                LIMIT ? OFFSET ?
            """, (request.max_features, request.start_index))

            features = []
            for row in cursor.fetchall():
                features.append({
                    "type": "Feature",
                    "id": row[0],
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row[6], row[5]]
                    },
                    "properties": {
                        "claim_uuid": row[0],
                        "case_number": row[1],
                        "case_status": row[2],
                        "building_id": row[3],
                        "unit_id": row[4]
                    }
                })

            return features

        except Exception as e:
            logger.error(f"Error getting claim features: {e}")
            return []

    def _get_damage_features(self, request: WFSRequest) -> List[Dict]:
        """Get damage assessment features."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT d.damage_id, d.building_uuid, d.damage_type, d.severity, d.assessment_date,
                       b.latitude, b.longitude, b.building_id
                FROM damage_assessments d
                JOIN buildings b ON d.building_uuid = b.building_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                LIMIT ? OFFSET ?
            """, (request.max_features, request.start_index))

            features = []
            for row in cursor.fetchall():
                features.append({
                    "type": "Feature",
                    "id": row[0],
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row[6], row[5]]
                    },
                    "properties": {
                        "damage_id": row[0],
                        "building_id": row[7],
                        "damage_type": row[2],
                        "severity": row[3],
                        "assessment_date": row[4]
                    }
                })

            return features

        except Exception as e:
            logger.error(f"Error getting damage features: {e}")
            return []

    def _get_occupancy_features(self, request: WFSRequest) -> List[Dict]:
        """Get occupancy distribution features."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT u.unit_id, u.occupancy_status,
                       COUNT(h.household_id) as household_count,
                       SUM(h.total_members) as total_persons,
                       b.latitude, b.longitude
                FROM units u
                JOIN buildings b ON u.building_uuid = b.building_uuid
                LEFT JOIN households h ON u.unit_uuid = h.unit_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                GROUP BY u.unit_uuid
                LIMIT ? OFFSET ?
            """, (request.max_features, request.start_index))

            features = []
            for row in cursor.fetchall():
                features.append({
                    "type": "Feature",
                    "id": row[0],
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row[5], row[4]]
                    },
                    "properties": {
                        "unit_id": row[0],
                        "occupancy_status": row[1],
                        "household_count": row[2] or 0,
                        "total_persons": row[3] or 0
                    }
                })

            return features

        except Exception as e:
            logger.error(f"Error getting occupancy features: {e}")
            return []

    # ==================== WMS Operations ====================

    def handle_wms_request(self, request: WMSRequest) -> Union[str, bytes]:
        """Handle WMS request and return appropriate response."""
        if request.request == "GetCapabilities":
            return self.wms_get_capabilities()
        elif request.request == "GetMap":
            return self.wms_get_map(request)
        elif request.request == "GetLegendGraphic":
            return self.wms_get_legend(request)
        elif request.request == "GetFeatureInfo":
            return self.wms_get_feature_info(request)
        else:
            return f"Unsupported WMS request: {request.request}"

    def wms_get_capabilities(self) -> str:
        """Generate WMS GetCapabilities XML response."""
        root = ET.Element("WMS_Capabilities", {
            "version": "1.3.0",
            "xmlns": "http://www.opengis.net/wms",
            "xmlns:xlink": "http://www.w3.org/1999/xlink"
        })

        # Service
        service = ET.SubElement(root, "Service")
        ET.SubElement(service, "Name").text = "WMS"
        ET.SubElement(service, "Title").text = "TRRCMS WMS Service"
        ET.SubElement(service, "Abstract").text = "Web Map Service for UN-Habitat TRRCMS"

        online_resource = ET.SubElement(service, "OnlineResource")
        online_resource.set("{http://www.w3.org/1999/xlink}href", self.base_url)

        # Capability
        capability = ET.SubElement(root, "Capability")

        # Request
        req = ET.SubElement(capability, "Request")
        for op_name in ["GetCapabilities", "GetMap", "GetFeatureInfo", "GetLegendGraphic"]:
            op = ET.SubElement(req, op_name)
            format_elem = ET.SubElement(op, "Format")
            format_elem.text = "image/png" if op_name in ["GetMap", "GetLegendGraphic"] else "text/xml"
            dcp = ET.SubElement(op, "DCPType")
            http = ET.SubElement(dcp, "HTTP")
            get = ET.SubElement(http, "Get")
            ET.SubElement(get, "OnlineResource").set("{http://www.w3.org/1999/xlink}href", f"{self.base_url}/wms?")

        # Layer
        root_layer = ET.SubElement(capability, "Layer")
        ET.SubElement(root_layer, "Title").text = "TRRCMS Layers"
        ET.SubElement(root_layer, "CRS").text = "EPSG:4326"
        ET.SubElement(root_layer, "CRS").text = "EPSG:3857"

        # Individual layers
        for layer_name, layer_def in self._layers.items():
            layer = ET.SubElement(root_layer, "Layer", {"queryable": "1" if layer_def.queryable else "0"})
            ET.SubElement(layer, "Name").text = layer_name
            ET.SubElement(layer, "Title").text = layer_def.title
            ET.SubElement(layer, "Abstract").text = layer_def.abstract

            if layer_def.bbox:
                bbox = ET.SubElement(layer, "EX_GeographicBoundingBox")
                ET.SubElement(bbox, "westBoundLongitude").text = str(layer_def.bbox.min_x)
                ET.SubElement(bbox, "eastBoundLongitude").text = str(layer_def.bbox.max_x)
                ET.SubElement(bbox, "southBoundLatitude").text = str(layer_def.bbox.min_y)
                ET.SubElement(bbox, "northBoundLatitude").text = str(layer_def.bbox.max_y)

        return ET.tostring(root, encoding="unicode", method="xml")

    def wms_get_map(self, request: WMSRequest) -> bytes:
        """Generate map tile image (placeholder - actual rendering requires PIL/Cairo)."""
        # This is a simplified placeholder
        # Real implementation would use PIL, Cairo, or Mapnik for rendering
        logger.info(f"WMS GetMap request for layers: {request.layers}")

        # Return a simple SVG placeholder
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{request.width}" height="{request.height}">
    <rect width="100%" height="100%" fill="#E8F4F8"/>
    <text x="50%" y="50%" text-anchor="middle" fill="#666">
        TRRCMS Map Tile
    </text>
    <text x="50%" y="60%" text-anchor="middle" fill="#999" font-size="10">
        Layers: {', '.join(request.layers or [])}
    </text>
</svg>'''
        return svg.encode('utf-8')

    def wms_get_legend(self, request: WMSRequest) -> bytes:
        """Generate legend graphic."""
        if not request.layers:
            return b""

        layer_name = request.layers[0]
        layer_def = self._layers.get(layer_name)

        if not layer_def or not layer_def.style:
            return b""

        # Simple SVG legend
        fill_color = layer_def.style.get("fill_color", "#0072BC")
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="150" height="30">
    <rect x="5" y="5" width="20" height="20" fill="{fill_color}" stroke="#000"/>
    <text x="30" y="20" font-size="12">{layer_def.title}</text>
</svg>'''
        return svg.encode('utf-8')

    def wms_get_feature_info(self, request: WMSRequest) -> str:
        """Get feature info at clicked point."""
        # This would return feature attributes at the clicked location
        return json.dumps({"info": "Feature info placeholder"})

    # ==================== REST API Endpoints ====================

    def get_geo_layer(self, layer_name: str, params: Dict[str, Any] = None) -> Dict:
        """
        REST API endpoint for geo layers.

        Implements FSD 15.4 REST API endpoints:
        - /api/geo/buildings
        - /api/geo/units
        - /api/geo/claims
        - /api/geo/damage
        - /api/geo/occupancy
        """
        params = params or {}

        request = WFSRequest(
            request="GetFeature",
            type_names=[layer_name],
            max_features=params.get("limit", 1000),
            start_index=params.get("offset", 0),
            output_format="application/json"
        )

        # Apply bbox filter if provided
        if all(k in params for k in ["minx", "miny", "maxx", "maxy"]):
            request.bbox = BoundingBox(
                min_x=float(params["minx"]),
                min_y=float(params["miny"]),
                max_x=float(params["maxx"]),
                max_y=float(params["maxy"])
            )

        return self.wfs_get_feature(request)

    def get_available_layers(self) -> List[Dict[str, Any]]:
        """Get list of available GIS layers."""
        return [
            {
                "name": name,
                "title": layer.title,
                "title_ar": layer.title_ar,
                "description": layer.abstract,
                "description_ar": layer.abstract_ar,
                "geometry_type": layer.geometry_type,
                "queryable": layer.queryable,
                "endpoint": f"/api/geo/{name}",
                "wfs_endpoint": f"{self.base_url}/wfs?service=WFS&request=GetFeature&typeName={name}",
                "attributes": layer.attributes
            }
            for name, layer in self._layers.items()
        ]

    # ==================== QGIS Integration ====================

    def generate_qgis_project(self, output_path: Path) -> bool:
        """
        Generate QGIS project file (.qgs) for easy QGIS integration.

        Implements FSD requirement for QGIS interoperability.
        """
        try:
            root = ET.Element("qgis", {
                "version": "3.28",
                "projectname": "TRRCMS"
            })

            # Project title
            title = ET.SubElement(root, "title")
            title.text = "UN-Habitat TRRCMS GIS Project"

            # Project CRS
            project_crs = ET.SubElement(root, "projectCrs")
            spatial_ref = ET.SubElement(project_crs, "spatialrefsys")
            ET.SubElement(spatial_ref, "authid").text = "EPSG:4326"

            # Map canvas
            mapcanvas = ET.SubElement(root, "mapcanvas")
            ET.SubElement(mapcanvas, "units").text = "degrees"

            extent = ET.SubElement(mapcanvas, "extent")
            ET.SubElement(extent, "xmin").text = str(self.ALEPPO_BBOX.min_x)
            ET.SubElement(extent, "ymin").text = str(self.ALEPPO_BBOX.min_y)
            ET.SubElement(extent, "xmax").text = str(self.ALEPPO_BBOX.max_x)
            ET.SubElement(extent, "ymax").text = str(self.ALEPPO_BBOX.max_y)

            # Layer tree
            layer_tree = ET.SubElement(root, "layer-tree-group")

            # Add WFS layers
            for layer_name, layer_def in self._layers.items():
                layer_elem = ET.SubElement(layer_tree, "layer-tree-layer", {
                    "id": layer_name,
                    "name": layer_def.title,
                    "checked": "Qt::Checked",
                    "providerKey": "WFS"
                })

                # Custom properties for WFS connection
                custom_props = ET.SubElement(layer_elem, "customproperties")
                prop = ET.SubElement(custom_props, "property", {"key": "wfsUrl"})
                prop.text = f"{self.base_url}/wfs?service=WFS&request=GetFeature&typeName={layer_name}"

            # Project layers
            project_layers = ET.SubElement(root, "projectlayers")

            for layer_name, layer_def in self._layers.items():
                maplayer = ET.SubElement(project_layers, "maplayer", {
                    "type": "vector",
                    "geometry": layer_def.geometry_type
                })
                ET.SubElement(maplayer, "id").text = layer_name
                ET.SubElement(maplayer, "layername").text = layer_def.title

                datasource = ET.SubElement(maplayer, "datasource")
                datasource.text = f"url='{self.base_url}/wfs' typename='{layer_name}' version='2.0.0'"

                ET.SubElement(maplayer, "provider").text = "WFS"

            # Write project file
            tree = ET.ElementTree(root)
            tree.write(output_path, encoding="utf-8", xml_declaration=True)

            logger.info(f"QGIS project file generated: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error generating QGIS project: {e}")
            return False

    def generate_sld_style(self, layer_name: str) -> str:
        """Generate SLD (Styled Layer Descriptor) for a layer."""
        layer_def = self._layers.get(layer_name)
        if not layer_def or not layer_def.style:
            return ""

        style = layer_def.style

        root = ET.Element("StyledLayerDescriptor", {
            "version": "1.0.0",
            "xmlns": "http://www.opengis.net/sld",
            "xmlns:ogc": "http://www.opengis.net/ogc",
            "xmlns:se": "http://www.opengis.net/se"
        })

        named_layer = ET.SubElement(root, "NamedLayer")
        ET.SubElement(named_layer, "Name").text = layer_name

        user_style = ET.SubElement(named_layer, "UserStyle")
        ET.SubElement(user_style, "Title").text = layer_def.title

        feature_type_style = ET.SubElement(user_style, "FeatureTypeStyle")
        rule = ET.SubElement(feature_type_style, "Rule")
        ET.SubElement(rule, "Name").text = layer_name

        # Symbolizer based on geometry type
        if layer_def.geometry_type == "Polygon":
            symbolizer = ET.SubElement(rule, "PolygonSymbolizer")
            fill = ET.SubElement(symbolizer, "Fill")
            ET.SubElement(fill, "CssParameter", {"name": "fill"}).text = style.get("fill_color", "#0072BC")
            ET.SubElement(fill, "CssParameter", {"name": "fill-opacity"}).text = str(style.get("fill_opacity", 0.6))
            stroke = ET.SubElement(symbolizer, "Stroke")
            ET.SubElement(stroke, "CssParameter", {"name": "stroke"}).text = style.get("stroke_color", "#004A7C")
            ET.SubElement(stroke, "CssParameter", {"name": "stroke-width"}).text = str(style.get("stroke_width", 1))
        else:
            symbolizer = ET.SubElement(rule, "PointSymbolizer")
            graphic = ET.SubElement(symbolizer, "Graphic")
            mark = ET.SubElement(graphic, "Mark")
            ET.SubElement(mark, "WellKnownName").text = style.get("marker_type", "circle")
            fill = ET.SubElement(mark, "Fill")
            ET.SubElement(fill, "CssParameter", {"name": "fill"}).text = style.get("fill_color", "#28A745")
            ET.SubElement(graphic, "Size").text = str(style.get("marker_size", 6))

        return ET.tostring(root, encoding="unicode", method="xml")

    # ==================== Utility Methods ====================

    def _wkt_to_geojson(self, wkt: str) -> Optional[Dict]:
        """Convert WKT to GeoJSON geometry."""
        try:
            wkt = wkt.strip()

            if wkt.upper().startswith("POINT"):
                coords_str = wkt[wkt.index("(")+1:wkt.rindex(")")].strip()
                parts = coords_str.split()
                return {
                    "type": "Point",
                    "coordinates": [float(parts[0]), float(parts[1])]
                }

            elif wkt.upper().startswith("POLYGON"):
                coords_str = wkt[wkt.index("((")+2:wkt.rindex("))")]
                rings = []
                for ring_str in coords_str.split("),("):
                    ring = []
                    for point_str in ring_str.split(","):
                        parts = point_str.strip().split()
                        ring.append([float(parts[0]), float(parts[1])])
                    rings.append(ring)
                return {
                    "type": "Polygon",
                    "coordinates": rings
                }

            elif wkt.upper().startswith("LINESTRING"):
                coords_str = wkt[wkt.index("(")+1:wkt.rindex(")")].strip()
                coords = []
                for point_str in coords_str.split(","):
                    parts = point_str.strip().split()
                    coords.append([float(parts[0]), float(parts[1])])
                return {
                    "type": "LineString",
                    "coordinates": coords
                }

        except Exception as e:
            logger.warning(f"Failed to parse WKT: {e}")

        return None

    def transform_coordinates(
        self,
        x: float,
        y: float,
        from_crs: CRS,
        to_crs: CRS
    ) -> Tuple[float, float]:
        """
        Transform coordinates between CRS.

        Supports EPSG:4326 <-> EPSG:3857 transformation.
        """
        if from_crs == to_crs:
            return x, y

        # WGS84 to Web Mercator
        if from_crs == CRS.WGS84 and to_crs == CRS.WEB_MERCATOR:
            x_out = x * 20037508.34 / 180
            y_out = math.log(math.tan((90 + y) * math.pi / 360)) / (math.pi / 180)
            y_out = y_out * 20037508.34 / 180
            return x_out, y_out

        # Web Mercator to WGS84
        if from_crs == CRS.WEB_MERCATOR and to_crs == CRS.WGS84:
            x_out = x * 180 / 20037508.34
            y_out = y * 180 / 20037508.34
            y_out = math.atan(math.exp(y_out * math.pi / 180)) * 360 / math.pi - 90
            return x_out, y_out

        # Unsupported transformation
        logger.warning(f"Unsupported CRS transformation: {from_crs} -> {to_crs}")
        return x, y
