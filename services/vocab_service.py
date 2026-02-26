# -*- coding: utf-8 -*-
"""
Vocabulary Service - Single source of truth for vocabulary data.

Fetches from backend API on startup (GET /api/v1/vocabularies, public, no auth).
Falls back to hardcoded values from Vocabularies class + translation keys.
"""

import requests
from typing import Dict, List, Tuple, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

# ============ Module-level cache ============
_raw_vocabularies: List[Dict] = []
_lookup: Dict[str, Dict[int, Dict[str, Any]]] = {}
_options_cache: Dict[str, List[Tuple[int, str, str, int]]] = {}
_initialized: bool = False


# ============ Public API ============

def initialize_vocabularies():
    """
    Fetch vocabularies from backend API and build in-memory cache.
    Called once at app startup from main.py.
    """
    global _initialized
    from app.config import Config
    url = f"{Config.API_BASE_URL}/{Config.API_VERSION}/vocabularies"
    logger.info(f"Fetching vocabularies from: {url}")
    response = requests.get(url, timeout=10, verify=False)
    response.raise_for_status()
    data = response.json()
    _build_cache(data)
    _build_from_translation_keys()
    _initialized = True
    logger.info(f"Loaded {len(data)} vocabularies from API")


def get_label(vocab_name: str, code, lang: str = None) -> str:
    """
    Get display label for a vocabulary code.

    Args:
        vocab_name: Vocabulary name (case-insensitive, underscore-insensitive).
                    e.g. "BuildingType", "building_type", "buildingtype" all work.
        code: Integer code (or string for legacy data).
        lang: "ar" or "en". Defaults to current app language.

    Returns:
        Label string, or str(code) as fallback if not found.
    """
    if lang is None:
        lang = _get_current_language()

    key = _normalize_name(vocab_name)
    vocab = _lookup.get(key, {})

    # Try integer lookup first
    try:
        code_int = int(code)
        entry = vocab.get(code_int)
        if entry:
            return entry.get(lang, entry.get("ar", str(code)))
    except (ValueError, TypeError):
        pass

    # Try string code lookup (scan values for match)
    if code is not None:
        code_str = str(code).lower()
        for c, entry in vocab.items():
            if str(c).lower() == code_str:
                return entry.get(lang, entry.get("ar", str(code)))

    return str(code) if code is not None else ""


def get_options(vocab_name: str, lang: str = None) -> List[Tuple[int, str]]:
    """
    Get list of (code, label) tuples sorted by displayOrder.

    Args:
        vocab_name: Vocabulary name (case-insensitive, underscore-insensitive).
        lang: "ar" or "en". Defaults to current app language.

    Returns:
        List of (code, label) tuples for QComboBox population.
    """
    if lang is None:
        lang = _get_current_language()

    key = _normalize_name(vocab_name)
    options = _options_cache.get(key, [])

    result = []
    for code, label_ar, label_en, order in options:
        label = label_ar if lang == "ar" else label_en
        result.append((code, label))
    return result


def get_all_vocabularies() -> List[Dict]:
    """Get raw cached vocabulary data as returned by the API."""
    return _raw_vocabularies


def is_initialized() -> bool:
    """Check if vocabularies have been loaded."""
    return _initialized


def add_term(vocab_name: str, code: int, label_ar: str, label_en: str, order: int = 0):
    """Add a new term to the in-memory cache. Affects all dropdowns immediately."""
    key = _normalize_name(vocab_name)
    if key not in _lookup:
        _lookup[key] = {}
    if key not in _options_cache:
        _options_cache[key] = []

    _lookup[key][code] = {"ar": label_ar, "en": label_en, "order": order}
    _options_cache[key].append((code, label_ar, label_en, order))
    _options_cache[key].sort(key=lambda x: x[3])


def update_term(vocab_name: str, code: int, label_ar: str, label_en: str):
    """Update a term's labels in the in-memory cache."""
    key = _normalize_name(vocab_name)
    if key not in _lookup or code not in _lookup[key]:
        return
    _lookup[key][code]["ar"] = label_ar
    _lookup[key][code]["en"] = label_en
    opts = _options_cache.get(key, [])
    for i, (c, ar, en, order) in enumerate(opts):
        if c == code:
            _options_cache[key][i] = (c, label_ar, label_en, order)
            break


def remove_term(vocab_name: str, code: int):
    """Remove a term from the in-memory cache."""
    key = _normalize_name(vocab_name)
    if key in _lookup:
        _lookup[key].pop(code, None)
    if key in _options_cache:
        _options_cache[key] = [t for t in _options_cache[key] if t[0] != code]


def get_next_code(vocab_name: str) -> int:
    """Get next available integer code for a vocabulary."""
    key = _normalize_name(vocab_name)
    codes = [c for c in _lookup.get(key, {}).keys() if isinstance(c, int)]
    if not codes:
        return 1
    normal_codes = [c for c in codes if c < 90]
    if not normal_codes:
        return 1
    return max(normal_codes) + 1


def load_db_customizations(db):
    """Merge user-added vocabulary terms from DB into the cache.
    Called after initialize_vocabularies() to restore user edits."""
    if not db:
        return
    try:
        rows = db.fetch_all(
            "SELECT vocabulary_name, term_code, term_label, term_label_ar, status "
            "FROM vocabulary_terms WHERE source = 'manual' ORDER BY vocabulary_name, term_code"
        )
        added = 0
        for row in rows:
            vocab_name = row[0]
            term_code = row[1]
            term_label = row[2]
            term_label_ar = row[3]
            status = row[4]

            try:
                code = int(term_code)
            except (ValueError, TypeError):
                continue

            key = _normalize_name(vocab_name)
            if status == "deleted":
                if key in _lookup and code in _lookup[key]:
                    remove_term(vocab_name, code)
                continue

            label_ar = term_label_ar or term_label or ""
            label_en = term_label or label_ar

            if key in _lookup and code in _lookup[key]:
                update_term(vocab_name, code, label_ar, label_en)
            else:
                existing = _options_cache.get(key, [])
                max_order = max((t[3] for t in existing), default=0)
                add_term(vocab_name, code, label_ar, label_en, order=max_order + 1)
            added += 1
        if added:
            logger.info(f"Loaded {added} user vocabulary customizations from DB")
    except Exception as e:
        logger.warning(f"Failed to load DB vocabulary customizations: {e}")


# ============ Internal helpers ============

def _normalize_name(name: str) -> str:
    """Normalize vocabulary name for case/underscore-insensitive lookup."""
    return name.lower().replace("_", "")


def _get_current_language() -> str:
    """Get current app language, defaulting to Arabic."""
    try:
        from services.translation_manager import get_language
        return get_language()
    except Exception:
        return "ar"


# ============ Cache builders ============

def _build_cache(api_data: List[Dict]):
    """Build lookup dicts from API response."""
    global _raw_vocabularies, _lookup, _options_cache
    _raw_vocabularies = api_data
    _lookup = {}
    _options_cache = {}

    for vocab in api_data:
        name = vocab.get("vocabularyName", "")
        key = _normalize_name(name)

        code_map = {}
        options_list = []

        for val in vocab.get("values", []):
            code = val.get("code")
            entry = {
                "ar": val.get("labelArabic", ""),
                "en": val.get("labelEnglish", ""),
                "order": val.get("displayOrder", 0),
            }
            code_map[code] = entry
            options_list.append((code, entry["ar"], entry["en"], entry["order"]))

        # Sort by displayOrder
        options_list.sort(key=lambda x: x[3])

        _lookup[key] = code_map
        _options_cache[key] = options_list

    # Add aliases for API vocab names that differ from our code's naming convention
    # e.g. API uses "tenure_contract_type" but our code calls it "ContractType"
    _ALIASES = {
        "contracttype": "tenurecontracttype",     # ContractType → tenure_contract_type
        "casestatus": "claimstatus",              # CaseStatus → claim_status
        "unittype": "propertyunittype",           # UnitType → property_unit_type
        "unitstatus": "propertyunitstatus",       # UnitStatus → property_unit_status
    }
    for alias, real_key in _ALIASES.items():
        if real_key in _lookup and alias not in _lookup:
            _lookup[alias] = _lookup[real_key]
            _options_cache[alias] = _options_cache[real_key]


def _build_cache_from_hardcoded():
    """Build cache from hardcoded Vocabularies class + translation keys as fallback."""
    global _raw_vocabularies, _lookup, _options_cache
    _raw_vocabularies = []
    _lookup = {}
    _options_cache = {}

    # --- From app/config.py Vocabularies class (code, en, ar) tuples ---
    try:
        from app.config import Vocabularies
        _vocabs_from_config = {
            "buildingtype": getattr(Vocabularies, "BUILDING_TYPES", []),
            "buildingstatus": getattr(Vocabularies, "BUILDING_STATUS", []),
            "gender": getattr(Vocabularies, "GENDERS", []),
            "relationtype": getattr(Vocabularies, "RELATION_TYPES", []),
            "documenttype": getattr(Vocabularies, "DOCUMENT_TYPES", []),
            "casestatus": getattr(Vocabularies, "CASE_STATUS", []),
            "verificationstatus": getattr(Vocabularies, "VERIFICATION_STATUS", []),
        }
        for key, tuples in _vocabs_from_config.items():
            if not tuples:
                continue
            code_map = {}
            options_list = []
            for idx, (code, en, ar) in enumerate(tuples):
                entry = {"ar": ar, "en": en, "order": idx + 1}
                code_map[code] = entry
                options_list.append((code, ar, en, idx + 1))
            _lookup[key] = code_map
            _options_cache[key] = options_list
    except Exception as e:
        logger.warning(f"Failed to load from Vocabularies class: {e}")

    # --- From display_mappings translation keys (vocabs not in config) ---
    _build_from_translation_keys()


def _build_from_translation_keys():
    """Build fallback entries for vocabularies that only exist in display_mappings."""
    try:
        from services.translations.ar import AR_TRANSLATIONS
        from services.translations.en import EN_TRANSLATIONS
    except ImportError:
        logger.warning("Translation files not available for fallback.")
        return

    # Each entry: (code, tr_key)
    _extra_vocabs = {
        "contracttype": [
            (0, "mapping.select"),
            (1, "mapping.contract_type.full_ownership"),
            (2, "mapping.contract_type.shared_ownership"),
            (3, "mapping.contract_type.long_term_rental"),
            (4, "mapping.contract_type.short_term_rental"),
            (5, "mapping.contract_type.informal_tenure"),
            (6, "mapping.contract_type.unauthorized_occupation"),
            (7, "mapping.contract_type.customary_rights"),
            (8, "mapping.contract_type.inheritance_based"),
            (9, "mapping.contract_type.hosted_guest"),
            (10, "mapping.contract_type.temporary_shelter"),
            (11, "mapping.contract_type.government_allocation"),
            (12, "mapping.contract_type.usufruct"),
            (99, "mapping.contract_type.other"),
        ],
        "evidencetype": [
            (0, "mapping.select"),
            (1, "mapping.evidence_type.identification_document"),
            (2, "mapping.evidence_type.ownership_deed"),
            (3, "mapping.evidence_type.rental_contract"),
            (4, "mapping.evidence_type.utility_bill"),
            (5, "mapping.evidence_type.photo"),
            (6, "mapping.evidence_type.official_letter"),
            (7, "mapping.evidence_type.court_order"),
            (8, "mapping.evidence_type.inheritance_document"),
            (9, "mapping.evidence_type.tax_receipt"),
            (99, "mapping.evidence_type.other"),
        ],
        "occupancytype": [
            (0, "mapping.select"),
            (1, "mapping.occupancy_type.owner_occupied"),
            (2, "mapping.occupancy_type.tenant_occupied"),
            (3, "mapping.occupancy_type.family_occupied"),
            (4, "mapping.occupancy_type.mixed_occupancy"),
            (5, "mapping.occupancy_type.vacant"),
            (6, "mapping.occupancy_type.temporary_seasonal"),
            (7, "mapping.occupancy_type.commercial_use"),
            (8, "mapping.occupancy_type.abandoned"),
            (9, "mapping.occupancy_type.disputed"),
            (99, "mapping.occupancy_type.unknown"),
        ],
        "occupancynature": [
            (0, "mapping.select"),
            (1, "mapping.occupancy_nature.legal_formal"),
            (2, "mapping.occupancy_nature.informal"),
            (3, "mapping.occupancy_nature.customary"),
            (4, "mapping.occupancy_nature.temporary_emergency"),
            (5, "mapping.occupancy_nature.authorized"),
            (6, "mapping.occupancy_nature.unauthorized"),
            (7, "mapping.occupancy_nature.pending_regularization"),
            (8, "mapping.occupancy_nature.contested"),
            (99, "mapping.occupancy_nature.unknown"),
        ],
        "nationality": [
            (1, "mapping.nationality.syrian"),
            (2, "mapping.nationality.palestinian"),
            (3, "mapping.nationality.iraqi"),
            (4, "mapping.nationality.lebanese"),
            (5, "mapping.nationality.jordanian"),
            (6, "mapping.nationality.turkish"),
            (7, "mapping.nationality.egyptian"),
            (8, "mapping.nationality.yemeni"),
            (9, "mapping.nationality.sudanese"),
            (10, "mapping.nationality.libyan"),
            (11, "mapping.nationality.somali"),
            (12, "mapping.nationality.afghan"),
            (97, "mapping.nationality.stateless"),
            (98, "mapping.nationality.other"),
            (99, "mapping.nationality.unknown"),
        ],
        "claimtype": [
            (1, "mapping.claim_type.ownership"),
            (2, "mapping.claim_type.occupancy"),
            (3, "mapping.claim_type.tenancy"),
        ],
        "claimstatus": [
            (1, "mapping.claim_status.new"),
            (2, "mapping.claim_status.under_review"),
            (3, "mapping.claim_status.completed"),
            (4, "mapping.claim_status.pending"),
            (5, "mapping.claim_status.draft"),
        ],
        "casepriority": [
            (1, "mapping.priority.low"),
            (2, "mapping.priority.normal"),
            (3, "mapping.priority.high"),
            (4, "mapping.priority.urgent"),
        ],
        "claimsource": [
            (1, "mapping.source.field_survey"),
            (2, "mapping.source.direct_request"),
            (3, "mapping.source.referral"),
            (4, "mapping.source.office_submission"),
        ],
        "businessnature": [
            (1, "mapping.business_type.residential"),
            (2, "mapping.business_type.commercial"),
            (3, "mapping.business_type.agricultural"),
        ],
    }

    for key, items in _extra_vocabs.items():
        if key in _lookup:
            continue  # Already loaded from Vocabularies class
        code_map = {}
        options_list = []
        for idx, (code, tr_key) in enumerate(items):
            ar = AR_TRANSLATIONS.get(tr_key, tr_key)
            en = EN_TRANSLATIONS.get(tr_key, tr_key)
            entry = {"ar": ar, "en": en, "order": idx + 1}
            code_map[code] = entry
            options_list.append((code, ar, en, idx + 1))
        _lookup[key] = code_map
        _options_cache[key] = options_list
