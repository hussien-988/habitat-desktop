# -*- coding: utf-8 -*-
"""
Vocabulary Service - Single source of truth for vocabulary data.

Fetches from backend API on startup (GET /api/v1/vocabularies, public, no auth).
Falls back to hardcoded values from Vocabularies class + translation keys.
"""

import json
import requests
from typing import Dict, List, Tuple, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)
_raw_vocabularies: List[Dict] = []
_lookup: Dict[str, Dict[int, Dict[str, Any]]] = {}
_options_cache: Dict[str, List[Tuple[int, str, str, int]]] = {}
_initialized: bool = False

def initialize_vocabularies():
    """
    Fetch vocabularies from backend API and build in-memory cache.
    Falls back to hardcoded values if API is unavailable.
    Called once at app startup from main.py.
    """
    global _initialized
    from app.config import Config, get_api_base_url, should_verify_ssl
    url = f"{get_api_base_url()}/v2/vocabularies"
    logger.info(f"Fetching vocabularies from: {url}")
    try:
        response = requests.get(url, timeout=10, verify=should_verify_ssl(url))
        response.raise_for_status()
        raw = response.json()
        data = raw.get("items", raw) if isinstance(raw, dict) else raw
        _build_cache(data)
        _build_from_translation_keys()
        _save_vocab_cache(data)
        _initialized = True
        logger.info(f"Loaded {len(data)} vocabularies from API")
    except Exception as e:
        logger.warning(f"Could not load vocabularies from API ({e}).")
        cached = _load_vocab_cache()
        if cached:
            _build_cache(cached)
            _build_from_translation_keys()
            logger.info("Using locally cached vocabularies (offline mode)")
        else:
            logger.error("API unavailable and no local cache. Vocabularies not loaded.")
        _initialized = True


def refresh_vocabularies():
    """
    Re-fetch vocabularies from backend API and rebuild cache.
    Can be called at runtime without restarting the app.
    """
    global _initialized, _raw_vocabularies, _lookup, _options_cache
    _initialized = False
    _raw_vocabularies = []
    _lookup = {}
    _options_cache = {}
    initialize_vocabularies()


def _save_vocab_cache(data: list) -> None:
    """Save raw API vocabulary data to local cache file."""
    try:
        from app.config import Config
        cache_path = Config.DATA_DIR / "vocab_cache.json"
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info(f"Saved vocab cache ({len(data)} vocabularies)")
    except Exception as e:
        logger.warning(f"Could not save vocab cache: {e}")


def _load_vocab_cache() -> list:
    """Load vocabulary data from local cache file. Returns [] if not found."""
    try:
        from app.config import Config
        cache_path = Config.DATA_DIR / "vocab_cache.json"
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded vocab cache ({len(data)} vocabularies)")
            return data
    except Exception as e:
        logger.warning(f"Could not load vocab cache: {e}")
    return []


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


def get_options(vocab_name: str, lang: str = None, include_deprecated: bool = False) -> List[Tuple[int, str]]:
    """
    Get list of (code, label) tuples sorted by displayOrder.

    Args:
        vocab_name: Vocabulary name (case-insensitive, underscore-insensitive).
        lang: "ar" or "en". Defaults to current app language.
        include_deprecated: If True, include deprecated values.

    Returns:
        List of (code, label) tuples for QComboBox population.
    """
    if lang is None:
        lang = _get_current_language()

    key = _normalize_name(vocab_name)
    options = _options_cache.get(key, [])

    result = []
    for item in options:
        code = item[0]
        label_ar = item[1]
        label_en = item[2]
        deprecated = item[4] if len(item) > 4 else False
        if not include_deprecated and deprecated:
            continue
        label = label_ar if lang == "ar" else label_en
        result.append((code, label))
    return result


def get_all_vocabularies() -> List[Dict]:
    """Get raw cached vocabulary data as returned by the API."""
    return _raw_vocabularies


def is_initialized() -> bool:
    """Check if vocabularies have been loaded."""
    return _initialized


def is_deprecated(vocab_name: str, code) -> bool:
    """Check if a vocabulary code is deprecated."""
    key = _normalize_name(vocab_name)
    try:
        code_int = int(code)
        entry = _lookup.get(key, {}).get(code_int)
        return entry.get("deprecated", False) if entry else False
    except (ValueError, TypeError):
        return False


def add_term(vocab_name: str, code: int, label_ar: str, label_en: str, order: int = 0):
    """Add a new term to the in-memory cache. Affects all dropdowns immediately."""
    key = _normalize_name(vocab_name)
    if key not in _lookup:
        _lookup[key] = {}
    if key not in _options_cache:
        _options_cache[key] = []

    _lookup[key][code] = {"ar": label_ar, "en": label_en, "order": order, "deprecated": False}
    _options_cache[key].append((code, label_ar, label_en, order, False))
    _options_cache[key].sort(key=lambda x: x[3])


def update_term(vocab_name: str, code: int, label_ar: str, label_en: str):
    """Update a term's labels in the in-memory cache."""
    key = _normalize_name(vocab_name)
    if key not in _lookup or code not in _lookup[key]:
        return
    _lookup[key][code]["ar"] = label_ar
    _lookup[key][code]["en"] = label_en
    opts = _options_cache.get(key, [])
    for i, item in enumerate(opts):
        if item[0] == code:
            deprecated = item[4] if len(item) > 4 else False
            _options_cache[key][i] = (code, label_ar, label_en, item[3], deprecated)
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
                "deprecated": val.get("isDeprecated", False),
            }
            code_map[code] = entry
            options_list.append((code, entry["ar"], entry["en"], entry["order"], entry["deprecated"]))

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
            (2, "mapping.evidence_type.ownership_deed"),
            (3, "mapping.evidence_type.rental_contract"),
            (4, "mapping.evidence_type.utility_bill"),
            (6, "mapping.evidence_type.official_letter"),
            (7, "mapping.evidence_type.court_order"),
            (8, "mapping.evidence_type.inheritance_document"),
            (9, "mapping.evidence_type.tax_receipt"),
            (99, "mapping.evidence_type.other"),
        ],
        "identificationdocumenttype": [
            (0, "mapping.select"),
            (1, "mapping.id_doc_type.personal_id_photo"),
            (2, "mapping.id_doc_type.family_record"),
            (3, "mapping.id_doc_type.photo"),
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
        "importstatus": [
            (0, "mapping.import_status.pending"),
            (1, "mapping.import_status.validated"),
            (2, "mapping.import_status.imported"),
            (3, "mapping.import_status.failed"),
            (4, "mapping.import_status.partial"),
        ],
        "documenttype": [
            ("TAPU_GREEN", "mapping.document_type.tapu_green"),
            ("PROPERTY_REG", "mapping.document_type.property_reg"),
            ("TEMP_REG", "mapping.document_type.temp_reg"),
            ("COURT_RULING", "mapping.document_type.court_ruling"),
            ("POWER_ATTORNEY", "mapping.document_type.power_attorney"),
            ("SALE_NOTARIZED", "mapping.document_type.sale_notarized"),
            ("SALE_INFORMAL", "mapping.document_type.sale_informal"),
            ("RENT_REGISTERED", "mapping.document_type.rent_registered"),
            ("RENT_INFORMAL", "mapping.document_type.rent_informal"),
            ("UTILITY_BILL", "mapping.document_type.utility_bill"),
            ("MUKHTAR_CERT", "mapping.document_type.mukhtar_cert"),
            ("INHERITANCE", "mapping.document_type.inheritance"),
            ("WITNESS_STATEMENT", "mapping.document_type.witness_statement"),
            ("CLAIMANT_STATEMENT", "mapping.document_type.claimant_statement"),
        ],
        "evidencestatus": [
            ("pending", "mapping.evidence_status.pending"),
            ("verified", "mapping.evidence_status.verified"),
            ("rejected", "mapping.evidence_status.rejected"),
        ],
        "surveystatus": [
            (1, "mapping.survey_status.draft"),
            (3, "mapping.survey_status.finalized"),
            (4, "mapping.survey_status.obstructed"),
            (8, "mapping.survey_status.cancelled"),
            (99, "mapping.survey_status.archived"),
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
