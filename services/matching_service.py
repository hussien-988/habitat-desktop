# -*- coding: utf-8 -*-
"""
Entity Matching Service
=======================
Implements FR-D-5 (Person Matching) and FR-D-6 (Property Matching) from FSD v5.0

Features:
- Multi-attribute identity resolution for persons
- Arabic name similarity using phonetic and edit distance algorithms
- Spatial proximity matching for properties using PostGIS
- Configurable matching thresholds
- Candidate scoring and ranking
- Duplicate detection and resolution queue
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Matching thresholds
EXACT_MATCH_SCORE = 1.0
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.70
LOW_CONFIDENCE_THRESHOLD = 0.50

# Spatial proximity thresholds (meters)
SPATIAL_EXACT_MATCH = 5        # Same point essentially
SPATIAL_NEAR_MATCH = 20        # Very close proximity
SPATIAL_NEIGHBOR_MATCH = 50    # Same building area


class MatchType(Enum):
    """Type of match detection."""
    EXACT = "exact"                  # Exact match on unique identifier
    HIGH_CONFIDENCE = "high"         # Very likely same entity
    MEDIUM_CONFIDENCE = "medium"     # Likely same entity, needs review
    LOW_CONFIDENCE = "low"           # Possible match, requires verification
    NO_MATCH = "no_match"            # No matching candidates


class MatchField(Enum):
    """Fields used for matching."""
    # Person fields
    NATIONAL_ID = "national_id"
    PHONE = "phone"
    NAME = "name"
    FATHER_NAME = "father_name"
    YEAR_OF_BIRTH = "year_of_birth"
    GENDER = "gender"

    # Property fields
    BUILDING_ID = "building_id"
    UNIT_ID = "unit_id"
    ADDRESS = "address"
    COORDINATES = "coordinates"


@dataclass
class MatchCandidate:
    """A potential match candidate."""
    entity_id: str
    entity_type: str  # 'person' or 'building' or 'unit'
    score: float
    match_type: MatchType
    matched_fields: List[MatchField] = field(default_factory=list)
    field_scores: Dict[str, float] = field(default_factory=dict)
    entity_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entity_id': self.entity_id,
            'entity_type': self.entity_type,
            'score': self.score,
            'match_type': self.match_type.value,
            'matched_fields': [f.value for f in self.matched_fields],
            'field_scores': self.field_scores,
            'entity_data': self.entity_data
        }


@dataclass
class MatchResult:
    """Result of a matching operation."""
    source_id: str
    source_type: str
    candidates: List[MatchCandidate]
    best_match: Optional[MatchCandidate]
    match_type: MatchType
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_id': self.source_id,
            'source_type': self.source_type,
            'candidates_count': len(self.candidates),
            'candidates': [c.to_dict() for c in self.candidates[:10]],
            'best_match': self.best_match.to_dict() if self.best_match else None,
            'match_type': self.match_type.value,
            'timestamp': self.timestamp.isoformat()
        }


class ArabicNameMatcher:
    """
    Arabic name similarity matching.
    Handles:
    - Diacritics normalization
    - Common variations (ال، ة، ى)
    - Phonetic similarity
    - Edit distance
    """

    # Arabic normalization mappings
    ARABIC_NORMALIZATIONS = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا',  # Alef variants
        'ة': 'ه',  # Taa marbuta
        'ى': 'ي',  # Alef maksura
        'ؤ': 'و',  # Waw with hamza
        'ئ': 'ي',  # Yaa with hamza
    }

    # Common Arabic prefixes/articles
    ARABIC_PREFIXES = ['ال', 'ابن', 'أبو', 'عبد']

    @classmethod
    def normalize_arabic(cls, text: str) -> str:
        """Normalize Arabic text for comparison."""
        if not text:
            return ""

        # Remove diacritics (harakat)
        text = re.sub(r'[\u064B-\u065F\u0670]', '', text)

        # Apply character normalizations
        for orig, repl in cls.ARABIC_NORMALIZATIONS.items():
            text = text.replace(orig, repl)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text.strip()

    @classmethod
    def remove_prefixes(cls, name: str) -> str:
        """Remove common Arabic name prefixes."""
        name = cls.normalize_arabic(name)
        for prefix in cls.ARABIC_PREFIXES:
            if name.startswith(prefix + ' '):
                name = name[len(prefix) + 1:]
            elif name.startswith(prefix):
                name = name[len(prefix):]
        return name.strip()

    @classmethod
    def calculate_similarity(cls, name1: str, name2: str) -> float:
        """
        Calculate similarity between two Arabic names.
        Uses a combination of:
        - Exact match after normalization
        - Levenshtein edit distance
        - Token-based matching
        """
        if not name1 or not name2:
            return 0.0

        # Normalize both names
        norm1 = cls.normalize_arabic(name1)
        norm2 = cls.normalize_arabic(name2)

        # Exact match after normalization
        if norm1 == norm2:
            return 1.0

        # Without prefixes
        stripped1 = cls.remove_prefixes(name1)
        stripped2 = cls.remove_prefixes(name2)

        if stripped1 == stripped2:
            return 0.95

        # Token-based matching
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())

        if tokens1 == tokens2:
            return 0.95

        # Jaccard similarity of tokens
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        token_sim = intersection / union if union > 0 else 0

        # Edit distance similarity
        edit_sim = cls._edit_distance_similarity(norm1, norm2)

        # Combined score (weighted)
        return max(token_sim * 0.7 + edit_sim * 0.3, edit_sim)

    @classmethod
    def _edit_distance_similarity(cls, s1: str, s2: str) -> float:
        """Calculate normalized edit distance similarity."""
        if not s1 or not s2:
            return 0.0

        len1, len2 = len(s1), len(s2)
        max_len = max(len1, len2)

        if max_len == 0:
            return 1.0

        # Create distance matrix
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i-1] == s2[j-1] else 1
                dp[i][j] = min(
                    dp[i-1][j] + 1,      # Deletion
                    dp[i][j-1] + 1,      # Insertion
                    dp[i-1][j-1] + cost  # Substitution
                )

        distance = dp[len1][len2]
        return 1.0 - (distance / max_len)


class PersonMatcher:
    """
    Person matching service.
    Implements FR-D-5: Multi-attribute identity resolution.
    """

    # Field weights for overall score
    FIELD_WEIGHTS = {
        'national_id': 0.40,    # Strongest identifier
        'phone': 0.15,          # Good identifier
        'name': 0.25,           # Important but can vary
        'father_name': 0.10,    # Supporting evidence
        'year_of_birth': 0.05,  # Supporting evidence
        'gender': 0.05          # Basic check
    }

    def __init__(self, db):
        """
        Initialize person matcher.

        Args:
            db: Database instance
        """
        self.db = db
        self._name_matcher = ArabicNameMatcher()

    def find_matches(
        self,
        person_data: Dict[str, Any],
        threshold: float = LOW_CONFIDENCE_THRESHOLD,
        limit: int = 10
    ) -> MatchResult:
        """
        Find potential matches for a person.

        Args:
            person_data: Person data to match
            threshold: Minimum score threshold
            limit: Maximum candidates to return

        Returns:
            MatchResult with candidates
        """
        source_id = person_data.get('person_id', 'new')
        candidates = []

        # Stage 1: Exact national ID match (blocking)
        national_id = person_data.get('national_id')
        if national_id:
            exact_matches = self._find_by_national_id(national_id)
            for match in exact_matches:
                if match.get('person_id') != source_id:
                    candidates.append(MatchCandidate(
                        entity_id=match['person_id'],
                        entity_type='person',
                        score=EXACT_MATCH_SCORE,
                        match_type=MatchType.EXACT,
                        matched_fields=[MatchField.NATIONAL_ID],
                        field_scores={'national_id': 1.0},
                        entity_data=match
                    ))

        # Stage 2: Phone number match
        phone = person_data.get('phone_number') or person_data.get('mobile_number')
        if phone and not candidates:
            phone_matches = self._find_by_phone(phone)
            for match in phone_matches:
                if match.get('person_id') != source_id:
                    # Calculate full score with name similarity
                    score, field_scores = self._calculate_person_score(person_data, match)
                    if score >= threshold:
                        candidates.append(MatchCandidate(
                            entity_id=match['person_id'],
                            entity_type='person',
                            score=score,
                            match_type=self._get_match_type(score),
                            matched_fields=[MatchField.PHONE],
                            field_scores=field_scores,
                            entity_data=match
                        ))

        # Stage 3: Name-based search (if no strong matches yet)
        if not any(c.score >= HIGH_CONFIDENCE_THRESHOLD for c in candidates):
            first_name = person_data.get('first_name')
            last_name = person_data.get('last_name')

            if first_name or last_name:
                name_matches = self._find_by_name(first_name, last_name)
                for match in name_matches:
                    if match.get('person_id') != source_id:
                        # Check if already in candidates
                        if any(c.entity_id == match['person_id'] for c in candidates):
                            continue

                        score, field_scores = self._calculate_person_score(person_data, match)
                        if score >= threshold:
                            matched_fields = [MatchField.NAME]
                            if field_scores.get('father_name', 0) > 0.5:
                                matched_fields.append(MatchField.FATHER_NAME)

                            candidates.append(MatchCandidate(
                                entity_id=match['person_id'],
                                entity_type='person',
                                score=score,
                                match_type=self._get_match_type(score),
                                matched_fields=matched_fields,
                                field_scores=field_scores,
                                entity_data=match
                            ))

        # Sort by score and limit
        candidates.sort(key=lambda c: c.score, reverse=True)
        candidates = candidates[:limit]

        # Determine best match
        best_match = candidates[0] if candidates else None

        return MatchResult(
            source_id=source_id,
            source_type='person',
            candidates=candidates,
            best_match=best_match,
            match_type=best_match.match_type if best_match else MatchType.NO_MATCH
        )

    def _find_by_national_id(self, national_id: str) -> List[Dict[str, Any]]:
        """Find persons by exact national ID."""
        result = self.db.execute(
            """SELECT person_id, national_id, first_name, father_name, last_name,
                      phone_number, mobile_number, gender, year_of_birth
               FROM persons WHERE national_id = ?""",
            (national_id,)
        )
        return [dict(row) if hasattr(row, 'keys') else self._row_to_dict(row) for row in result]

    def _find_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        """Find persons by phone number."""
        # Normalize phone
        clean_phone = re.sub(r'\D', '', phone)

        result = self.db.execute(
            """SELECT person_id, national_id, first_name, father_name, last_name,
                      phone_number, mobile_number, gender, year_of_birth
               FROM persons
               WHERE REPLACE(REPLACE(phone_number, ' ', ''), '-', '') LIKE ?
                  OR REPLACE(REPLACE(mobile_number, ' ', ''), '-', '') LIKE ?
               LIMIT 20""",
            (f"%{clean_phone[-9:]}", f"%{clean_phone[-9:]}")
        )
        return [dict(row) if hasattr(row, 'keys') else self._row_to_dict(row) for row in result]

    def _find_by_name(self, first_name: str, last_name: str) -> List[Dict[str, Any]]:
        """Find persons by name similarity."""
        # Use normalized search
        norm_first = ArabicNameMatcher.normalize_arabic(first_name) if first_name else ''
        norm_last = ArabicNameMatcher.normalize_arabic(last_name) if last_name else ''

        # Build query based on available names
        conditions = []
        params = []

        if norm_first:
            conditions.append("first_name LIKE ?")
            params.append(f"%{norm_first[:3]}%")  # Prefix match

        if norm_last:
            conditions.append("last_name LIKE ?")
            params.append(f"%{norm_last[:3]}%")

        if not conditions:
            return []

        query = f"""
            SELECT person_id, national_id, first_name, father_name, last_name,
                   phone_number, mobile_number, gender, year_of_birth
            FROM persons
            WHERE {' OR '.join(conditions)}
            LIMIT 50
        """

        result = self.db.execute(query, params)
        return [dict(row) if hasattr(row, 'keys') else self._row_to_dict(row) for row in result]

    def _calculate_person_score(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate overall match score for a person."""
        field_scores = {}
        total_score = 0.0
        total_weight = 0.0

        # National ID
        src_nid = source.get('national_id')
        tgt_nid = target.get('national_id')
        if src_nid and tgt_nid:
            field_scores['national_id'] = 1.0 if src_nid == tgt_nid else 0.0
            total_score += field_scores['national_id'] * self.FIELD_WEIGHTS['national_id']
            total_weight += self.FIELD_WEIGHTS['national_id']

        # Phone
        src_phone = source.get('phone_number') or source.get('mobile_number')
        tgt_phone = target.get('phone_number') or target.get('mobile_number')
        if src_phone and tgt_phone:
            clean_src = re.sub(r'\D', '', src_phone)[-9:]
            clean_tgt = re.sub(r'\D', '', tgt_phone)[-9:]
            field_scores['phone'] = 1.0 if clean_src == clean_tgt else 0.0
            total_score += field_scores['phone'] * self.FIELD_WEIGHTS['phone']
            total_weight += self.FIELD_WEIGHTS['phone']

        # Full name similarity
        src_name = f"{source.get('first_name', '')} {source.get('last_name', '')}".strip()
        tgt_name = f"{target.get('first_name', '')} {target.get('last_name', '')}".strip()
        if src_name and tgt_name:
            field_scores['name'] = self._name_matcher.calculate_similarity(src_name, tgt_name)
            total_score += field_scores['name'] * self.FIELD_WEIGHTS['name']
            total_weight += self.FIELD_WEIGHTS['name']

        # Father name
        src_father = source.get('father_name')
        tgt_father = target.get('father_name')
        if src_father and tgt_father:
            field_scores['father_name'] = self._name_matcher.calculate_similarity(src_father, tgt_father)
            total_score += field_scores['father_name'] * self.FIELD_WEIGHTS['father_name']
            total_weight += self.FIELD_WEIGHTS['father_name']

        # Year of birth
        src_yob = source.get('year_of_birth')
        tgt_yob = target.get('year_of_birth')
        if src_yob and tgt_yob:
            try:
                diff = abs(int(src_yob) - int(tgt_yob))
                field_scores['year_of_birth'] = 1.0 if diff == 0 else (0.5 if diff <= 2 else 0.0)
                total_score += field_scores['year_of_birth'] * self.FIELD_WEIGHTS['year_of_birth']
                total_weight += self.FIELD_WEIGHTS['year_of_birth']
            except (ValueError, TypeError):
                pass

        # Gender
        src_gender = source.get('gender')
        tgt_gender = target.get('gender')
        if src_gender and tgt_gender:
            field_scores['gender'] = 1.0 if src_gender.lower() == tgt_gender.lower() else 0.0
            total_score += field_scores['gender'] * self.FIELD_WEIGHTS['gender']
            total_weight += self.FIELD_WEIGHTS['gender']

        # Normalize score
        final_score = total_score / total_weight if total_weight > 0 else 0.0

        return final_score, field_scores

    def _get_match_type(self, score: float) -> MatchType:
        """Determine match type from score."""
        if score >= HIGH_CONFIDENCE_THRESHOLD:
            return MatchType.HIGH_CONFIDENCE
        elif score >= MEDIUM_CONFIDENCE_THRESHOLD:
            return MatchType.MEDIUM_CONFIDENCE
        elif score >= LOW_CONFIDENCE_THRESHOLD:
            return MatchType.LOW_CONFIDENCE
        return MatchType.NO_MATCH

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert database row to dictionary."""
        return {
            'person_id': row[0],
            'national_id': row[1],
            'first_name': row[2],
            'father_name': row[3],
            'last_name': row[4],
            'phone_number': row[5],
            'mobile_number': row[6],
            'gender': row[7],
            'year_of_birth': row[8]
        }


class PropertyMatcher:
    """
    Property matching service.
    Implements FR-D-6: Location codes and spatial proximity matching.
    """

    def __init__(self, db):
        """
        Initialize property matcher.

        Args:
            db: Database instance (should support PostGIS for spatial queries)
        """
        self.db = db
        self._has_postgis = self._check_postgis()

    def _check_postgis(self) -> bool:
        """Check if PostGIS is available."""
        try:
            result = self.db.execute(
                "SELECT PostGIS_Version()"
            )
            return result is not None and len(result) > 0
        except Exception:
            return False

    def find_matches(
        self,
        property_data: Dict[str, Any],
        threshold: float = LOW_CONFIDENCE_THRESHOLD,
        limit: int = 10
    ) -> MatchResult:
        """
        Find potential matches for a property.

        Args:
            property_data: Property data to match
            threshold: Minimum score threshold
            limit: Maximum candidates to return

        Returns:
            MatchResult with candidates
        """
        property_type = 'building' if 'building_id' in property_data else 'unit'
        source_id = property_data.get('building_id') or property_data.get('unit_id') or 'new'
        candidates = []

        # Stage 1: Exact ID match
        if property_type == 'building':
            building_id = property_data.get('building_id')
            if building_id:
                exact_matches = self._find_building_by_id(building_id)
                for match in exact_matches:
                    if match.get('building_id') != source_id:
                        candidates.append(MatchCandidate(
                            entity_id=match['building_id'],
                            entity_type='building',
                            score=EXACT_MATCH_SCORE,
                            match_type=MatchType.EXACT,
                            matched_fields=[MatchField.BUILDING_ID],
                            field_scores={'building_id': 1.0},
                            entity_data=match
                        ))

        # Stage 2: Spatial proximity (if PostGIS available)
        if self._has_postgis and not candidates:
            lat = property_data.get('latitude')
            lng = property_data.get('longitude')

            if lat and lng:
                spatial_matches = self._find_by_spatial_proximity(lat, lng, SPATIAL_NEIGHBOR_MATCH)
                for match in spatial_matches:
                    match_id = match.get('building_id')
                    if match_id != source_id:
                        distance = match.get('distance', 0)
                        score = self._distance_to_score(distance)

                        if score >= threshold:
                            candidates.append(MatchCandidate(
                                entity_id=match_id,
                                entity_type='building',
                                score=score,
                                match_type=self._get_match_type(score),
                                matched_fields=[MatchField.COORDINATES],
                                field_scores={'coordinates': score, 'distance_m': distance},
                                entity_data=match
                            ))

        # Stage 3: Administrative code matching
        if not any(c.score >= HIGH_CONFIDENCE_THRESHOLD for c in candidates):
            code_matches = self._find_by_admin_codes(property_data)
            for match in code_matches:
                match_id = match.get('building_id')
                if match_id != source_id:
                    if any(c.entity_id == match_id for c in candidates):
                        continue

                    score, field_scores = self._calculate_code_score(property_data, match)
                    if score >= threshold:
                        candidates.append(MatchCandidate(
                            entity_id=match_id,
                            entity_type='building',
                            score=score,
                            match_type=self._get_match_type(score),
                            matched_fields=[MatchField.ADDRESS],
                            field_scores=field_scores,
                            entity_data=match
                        ))

        # Sort and limit
        candidates.sort(key=lambda c: c.score, reverse=True)
        candidates = candidates[:limit]

        best_match = candidates[0] if candidates else None

        return MatchResult(
            source_id=source_id,
            source_type=property_type,
            candidates=candidates,
            best_match=best_match,
            match_type=best_match.match_type if best_match else MatchType.NO_MATCH
        )

    def _find_building_by_id(self, building_id: str) -> List[Dict[str, Any]]:
        """Find building by exact ID."""
        result = self.db.execute(
            """SELECT building_id, governorate_code, district_code, subdistrict_code,
                      community_code, neighborhood_code, building_number,
                      building_type, latitude, longitude
               FROM buildings WHERE building_id = ?""",
            (building_id,)
        )
        return [dict(row) if hasattr(row, 'keys') else self._row_to_dict(row) for row in result]

    def _find_by_spatial_proximity(
        self,
        lat: float,
        lng: float,
        radius_meters: float
    ) -> List[Dict[str, Any]]:
        """Find buildings within radius using PostGIS."""
        try:
            # PostGIS query for spatial proximity
            query = """
                SELECT building_id, governorate_code, district_code, subdistrict_code,
                       community_code, neighborhood_code, building_number,
                       building_type, latitude, longitude,
                       ST_Distance(
                           ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                       ) as distance
                FROM buildings
                WHERE ST_DWithin(
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s
                )
                ORDER BY distance
                LIMIT 20
            """
            result = self.db.execute(query, (lng, lat, lng, lat, radius_meters))
            return [dict(row) if hasattr(row, 'keys') else self._spatial_row_to_dict(row) for row in result]

        except Exception as e:
            logger.warning(f"PostGIS query failed, using fallback: {e}")
            return self._find_by_bounding_box(lat, lng, radius_meters)

    def _find_by_bounding_box(
        self,
        lat: float,
        lng: float,
        radius_meters: float
    ) -> List[Dict[str, Any]]:
        """Fallback: Find buildings in bounding box (for SQLite)."""
        # Approximate degrees from meters at Syria's latitude
        deg_lat = radius_meters / 111000
        deg_lng = radius_meters / (111000 * 0.85)  # cos(35°) ≈ 0.82

        result = self.db.execute(
            """SELECT building_id, governorate_code, district_code, subdistrict_code,
                      community_code, neighborhood_code, building_number,
                      building_type, latitude, longitude
               FROM buildings
               WHERE latitude BETWEEN ? AND ?
                 AND longitude BETWEEN ? AND ?
               LIMIT 50""",
            (lat - deg_lat, lat + deg_lat, lng - deg_lng, lng + deg_lng)
        )

        matches = []
        for row in result:
            match = dict(row) if hasattr(row, 'keys') else self._row_to_dict(row)
            # Calculate approximate distance
            match['distance'] = self._haversine_distance(
                lat, lng,
                float(match.get('latitude', 0)),
                float(match.get('longitude', 0))
            )
            if match['distance'] <= radius_meters:
                matches.append(match)

        matches.sort(key=lambda m: m['distance'])
        return matches

    def _find_by_admin_codes(self, property_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find buildings by administrative codes."""
        conditions = []
        params = []

        # Build query from available codes
        for field in ['governorate_code', 'district_code', 'subdistrict_code',
                      'community_code', 'neighborhood_code']:
            value = property_data.get(field)
            if value:
                conditions.append(f"{field} = ?")
                params.append(value)

        if not conditions:
            return []

        query = f"""
            SELECT building_id, governorate_code, district_code, subdistrict_code,
                   community_code, neighborhood_code, building_number,
                   building_type, latitude, longitude
            FROM buildings
            WHERE {' AND '.join(conditions)}
            LIMIT 50
        """

        result = self.db.execute(query, params)
        return [dict(row) if hasattr(row, 'keys') else self._row_to_dict(row) for row in result]

    def _calculate_code_score(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate match score based on administrative codes."""
        field_scores = {}
        total_matches = 0
        total_fields = 0

        code_fields = [
            ('governorate_code', 0.25),
            ('district_code', 0.20),
            ('subdistrict_code', 0.20),
            ('community_code', 0.15),
            ('neighborhood_code', 0.10),
            ('building_number', 0.10)
        ]

        for field, weight in code_fields:
            src_val = source.get(field)
            tgt_val = target.get(field)
            if src_val and tgt_val:
                match = 1.0 if str(src_val) == str(tgt_val) else 0.0
                field_scores[field] = match
                total_matches += match * weight
                total_fields += weight

        final_score = total_matches / total_fields if total_fields > 0 else 0.0
        return final_score, field_scores

    def _distance_to_score(self, distance: float) -> float:
        """Convert distance in meters to match score."""
        if distance <= SPATIAL_EXACT_MATCH:
            return 0.98
        elif distance <= SPATIAL_NEAR_MATCH:
            return 0.90 - (distance / SPATIAL_NEAR_MATCH) * 0.10
        elif distance <= SPATIAL_NEIGHBOR_MATCH:
            return 0.80 - ((distance - SPATIAL_NEAR_MATCH) / (SPATIAL_NEIGHBOR_MATCH - SPATIAL_NEAR_MATCH)) * 0.20
        else:
            return max(0.5, 0.60 - (distance / 1000) * 0.10)

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate distance between two points in meters."""
        import math

        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (math.sin(delta_phi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _get_match_type(self, score: float) -> MatchType:
        """Determine match type from score."""
        if score >= HIGH_CONFIDENCE_THRESHOLD:
            return MatchType.HIGH_CONFIDENCE
        elif score >= MEDIUM_CONFIDENCE_THRESHOLD:
            return MatchType.MEDIUM_CONFIDENCE
        elif score >= LOW_CONFIDENCE_THRESHOLD:
            return MatchType.LOW_CONFIDENCE
        return MatchType.NO_MATCH

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert database row to dictionary."""
        return {
            'building_id': row[0],
            'governorate_code': row[1],
            'district_code': row[2],
            'subdistrict_code': row[3],
            'community_code': row[4],
            'neighborhood_code': row[5],
            'building_number': row[6],
            'building_type': row[7],
            'latitude': row[8],
            'longitude': row[9]
        }

    def _spatial_row_to_dict(self, row) -> Dict[str, Any]:
        """Convert spatial query row to dictionary."""
        d = self._row_to_dict(row)
        d['distance'] = row[10] if len(row) > 10 else 0
        return d


class MatchingService:
    """
    Unified matching service combining person and property matching.
    """

    def __init__(self, db):
        """
        Initialize matching service.

        Args:
            db: Database instance
        """
        self.db = db
        self.person_matcher = PersonMatcher(db)
        self.property_matcher = PropertyMatcher(db)

    def find_person_matches(
        self,
        person_data: Dict[str, Any],
        threshold: float = LOW_CONFIDENCE_THRESHOLD
    ) -> MatchResult:
        """Find matches for a person."""
        return self.person_matcher.find_matches(person_data, threshold)

    def find_property_matches(
        self,
        property_data: Dict[str, Any],
        threshold: float = LOW_CONFIDENCE_THRESHOLD
    ) -> MatchResult:
        """Find matches for a property."""
        return self.property_matcher.find_matches(property_data, threshold)

    def batch_match_persons(
        self,
        persons: List[Dict[str, Any]],
        threshold: float = LOW_CONFIDENCE_THRESHOLD
    ) -> List[MatchResult]:
        """Batch match multiple persons."""
        return [self.find_person_matches(p, threshold) for p in persons]

    def batch_match_properties(
        self,
        properties: List[Dict[str, Any]],
        threshold: float = LOW_CONFIDENCE_THRESHOLD
    ) -> List[MatchResult]:
        """Batch match multiple properties."""
        return [self.find_property_matches(p, threshold) for p in properties]

    def add_to_duplicate_queue(
        self,
        source_id: str,
        source_type: str,
        candidate_id: str,
        score: float,
        matched_fields: List[str]
    ) -> str:
        """
        Add a match to the duplicate resolution queue.
        Per FR-D-7: Conflicts queue for human review.
        """
        queue_id = str(datetime.utcnow().timestamp()).replace('.', '')

        self.db.execute("""
            INSERT INTO duplicate_candidates (
                id, source_id, source_type, candidate_id,
                score, matched_fields, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            queue_id,
            source_id,
            source_type,
            candidate_id,
            score,
            ','.join(matched_fields),
            'pending',
            datetime.utcnow().isoformat()
        ))

        return queue_id

    def get_duplicate_queue(
        self,
        status: str = 'pending',
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get items from duplicate resolution queue."""
        result = self.db.execute("""
            SELECT id, source_id, source_type, candidate_id,
                   score, matched_fields, status, created_at, resolved_at, resolved_by
            FROM duplicate_candidates
            WHERE status = ?
            ORDER BY score DESC, created_at ASC
            LIMIT ?
        """, (status, limit))

        return [dict(row) if hasattr(row, 'keys') else {
            'id': row[0],
            'source_id': row[1],
            'source_type': row[2],
            'candidate_id': row[3],
            'score': row[4],
            'matched_fields': row[5].split(',') if row[5] else [],
            'status': row[6],
            'created_at': row[7],
            'resolved_at': row[8],
            'resolved_by': row[9]
        } for row in result]

    def resolve_duplicate(
        self,
        queue_id: str,
        resolution: str,
        resolved_by: str
    ) -> bool:
        """
        Resolve a duplicate candidate.

        Args:
            queue_id: Queue entry ID
            resolution: 'merge', 'keep_existing', 'keep_new', 'skip'
            resolved_by: User performing resolution

        Returns:
            True if resolved successfully
        """
        self.db.execute("""
            UPDATE duplicate_candidates
            SET status = ?, resolution = ?, resolved_at = ?, resolved_by = ?
            WHERE id = ?
        """, (
            'resolved',
            resolution,
            datetime.utcnow().isoformat(),
            resolved_by,
            queue_id
        ))

        return True
