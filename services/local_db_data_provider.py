# -*- coding: utf-8 -*-
"""
Local Database Data Provider.

Wraps the existing SQLite/PostgreSQL database to conform to the DataProvider interface.
This provides backward compatibility with the existing codebase while enabling
the new abstraction layer.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .data_provider import (
    ApiResponse,
    DataProvider,
    DataProviderType,
    DataProviderEventEmitter,
    QueryParams,
)
from repositories.db_adapter import get_database, DatabaseAdapter
from utils.logger import get_logger

logger = get_logger(__name__)


class LocalDbDataProvider(DataProvider, DataProviderEventEmitter):
    """
    Local database data provider using existing SQLite/PostgreSQL.

    This is a bridge between the new DataProvider interface and
    the existing database infrastructure.
    """

    def __init__(self, db: DatabaseAdapter = None):
        """
        Initialize local DB data provider.

        Args:
            db: Optional database adapter. If None, uses default from factory.
        """
        DataProviderEventEmitter.__init__(self)
        self._db = db
        self._connected = False
        self._current_user = None

    @property
    def provider_type(self) -> DataProviderType:
        return DataProviderType.LOCAL_DB

    @property
    def db(self) -> DatabaseAdapter:
        """Get database adapter, creating if needed."""
        if self._db is None:
            self._db = get_database()
        return self._db

    def connect(self) -> bool:
        """Connect to local database."""
        try:
            if self._db is None:
                self._db = get_database()

            if not self._db.is_connected():
                self._db.connect()

            self._connected = self._db.is_connected()
            if self._connected:
                self.emit("connected", {"provider": "local_db", "type": self._db.db_type.value})
                logger.info(f"Local DB provider connected ({self._db.db_type.value})")

            return self._connected
        except Exception as e:
            logger.error(f"Failed to connect to local database: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from local database."""
        # Don't actually close the database - other parts of app might use it
        self._connected = False
        self.emit("disconnected", {"provider": "local_db"})
        logger.info("Local DB provider disconnected")

    def is_connected(self) -> bool:
        return self._connected and self._db is not None and self._db.is_connected()

    def health_check(self) -> Dict[str, Any]:
        try:
            result = self.db.fetch_one("SELECT 1 as ok")
            return {
                "status": "healthy" if result else "unhealthy",
                "provider": "local_db",
                "db_type": self._db.db_type.value if self._db else "unknown",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "provider": "local_db"
            }

    # ==================== Buildings ====================

    def get_buildings(self, params: QueryParams = None) -> ApiResponse:
        try:
            params = params or QueryParams()

            # Build query
            query = "SELECT * FROM buildings WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM buildings WHERE 1=1"
            query_params = []

            if params.filters.get("neighborhood_code"):
                query += " AND neighborhood_code = ?"
                count_query += " AND neighborhood_code = ?"
                query_params.append(params.filters["neighborhood_code"])

            if params.filters.get("building_type"):
                query += " AND building_type = ?"
                count_query += " AND building_type = ?"
                query_params.append(params.filters["building_type"])

            if params.filters.get("building_status"):
                query += " AND building_status = ?"
                count_query += " AND building_status = ?"
                query_params.append(params.filters["building_status"])

            if params.search:
                query += " AND (building_id LIKE ? OR neighborhood_name LIKE ? OR neighborhood_name_ar LIKE ?)"
                count_query += " AND (building_id LIKE ? OR neighborhood_name LIKE ? OR neighborhood_name_ar LIKE ?)"
                search_param = f"%{params.search}%"
                query_params.extend([search_param, search_param, search_param])

            # Get total count
            count_result = self.db.fetch_one(count_query, tuple(query_params))
            total = count_result["count"] if count_result else 0

            # Add sorting and pagination
            sort_col = params.sort_by or "building_id"
            sort_dir = "DESC" if params.sort_order == "desc" else "ASC"
            query += f" ORDER BY {sort_col} {sort_dir}"
            query += " LIMIT ? OFFSET ?"
            query_params.extend([params.page_size, (params.page - 1) * params.page_size])

            rows = self.db.fetch_all(query, tuple(query_params))
            buildings = [dict(row) for row in rows]

            return ApiResponse.ok(buildings, total_count=total, page=params.page, page_size=params.page_size)

        except Exception as e:
            logger.error(f"Error getting buildings: {e}")
            return ApiResponse.error(str(e), "E500")

    def get_building(self, building_id: str) -> ApiResponse:
        try:
            row = self.db.fetch_one(
                "SELECT * FROM buildings WHERE building_uuid = ? OR building_id = ?",
                (building_id, building_id)
            )
            if row:
                building = dict(row)
                # Get units
                units = self.db.fetch_all(
                    "SELECT * FROM property_units WHERE building_id = ?",
                    (building["building_id"],)
                )
                building["units"] = [dict(u) for u in units]
                return ApiResponse.ok(building)
            return ApiResponse.error("Building not found", "E404")
        except Exception as e:
            logger.error(f"Error getting building: {e}")
            return ApiResponse.error(str(e), "E500")

    def create_building(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            data["building_uuid"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()
            data["updated_at"] = datetime.now().isoformat()

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            query = f"INSERT INTO buildings ({columns}) VALUES ({placeholders})"

            self.db.execute(query, tuple(data.values()))
            return ApiResponse.ok(data)
        except Exception as e:
            logger.error(f"Error creating building: {e}")
            return ApiResponse.error(str(e), "E500")

    def update_building(self, building_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()

            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            query = f"UPDATE buildings SET {set_clause} WHERE building_uuid = ? OR building_id = ?"

            params = list(data.values()) + [building_id, building_id]
            self.db.execute(query, tuple(params))

            return self.get_building(building_id)
        except Exception as e:
            logger.error(f"Error updating building: {e}")
            return ApiResponse.error(str(e), "E500")

    def delete_building(self, building_id: str) -> ApiResponse:
        try:
            self.db.execute(
                "DELETE FROM buildings WHERE building_uuid = ? OR building_id = ?",
                (building_id, building_id)
            )
            return ApiResponse.ok({"deleted": True})
        except Exception as e:
            logger.error(f"Error deleting building: {e}")
            return ApiResponse.error(str(e), "E500")

    # ==================== Units ====================

    def get_units(self, params: QueryParams = None) -> ApiResponse:
        try:
            params = params or QueryParams()

            query = "SELECT * FROM property_units WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM property_units WHERE 1=1"
            query_params = []

            if params.filters.get("building_id"):
                query += " AND building_id = ?"
                count_query += " AND building_id = ?"
                query_params.append(params.filters["building_id"])

            if params.filters.get("unit_type"):
                query += " AND unit_type = ?"
                count_query += " AND unit_type = ?"
                query_params.append(params.filters["unit_type"])

            count_result = self.db.fetch_one(count_query, tuple(query_params))
            total = count_result["count"] if count_result else 0

            query += " ORDER BY unit_id LIMIT ? OFFSET ?"
            query_params.extend([params.page_size, (params.page - 1) * params.page_size])

            rows = self.db.fetch_all(query, tuple(query_params))
            return ApiResponse.ok([dict(r) for r in rows], total_count=total, page=params.page, page_size=params.page_size)
        except Exception as e:
            logger.error(f"Error getting units: {e}")
            return ApiResponse.error(str(e), "E500")

    def get_unit(self, unit_id: str) -> ApiResponse:
        try:
            row = self.db.fetch_one(
                "SELECT * FROM property_units WHERE unit_uuid = ? OR unit_id = ?",
                (unit_id, unit_id)
            )
            if row:
                return ApiResponse.ok(dict(row))
            return ApiResponse.error("Unit not found", "E404")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def create_unit(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            data["unit_uuid"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            query = f"INSERT INTO property_units ({columns}) VALUES ({placeholders})"

            self.db.execute(query, tuple(data.values()))
            return ApiResponse.ok(data)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_unit(self, unit_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            query = f"UPDATE property_units SET {set_clause} WHERE unit_uuid = ? OR unit_id = ?"
            self.db.execute(query, tuple(list(data.values()) + [unit_id, unit_id]))
            return self.get_unit(unit_id)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def delete_unit(self, unit_id: str) -> ApiResponse:
        try:
            self.db.execute("DELETE FROM property_units WHERE unit_uuid = ? OR unit_id = ?", (unit_id, unit_id))
            return ApiResponse.ok({"deleted": True})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Persons ====================

    def get_persons(self, params: QueryParams = None) -> ApiResponse:
        try:
            params = params or QueryParams()

            query = "SELECT * FROM persons WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM persons WHERE 1=1"
            query_params = []

            if params.search:
                query += " AND (first_name LIKE ? OR last_name LIKE ? OR first_name_ar LIKE ? OR last_name_ar LIKE ? OR national_id LIKE ?)"
                count_query += " AND (first_name LIKE ? OR last_name LIKE ? OR first_name_ar LIKE ? OR last_name_ar LIKE ? OR national_id LIKE ?)"
                sp = f"%{params.search}%"
                query_params.extend([sp, sp, sp, sp, sp])

            count_result = self.db.fetch_one(count_query, tuple(query_params))
            total = count_result["count"] if count_result else 0

            query += " ORDER BY last_name, first_name LIMIT ? OFFSET ?"
            query_params.extend([params.page_size, (params.page - 1) * params.page_size])

            rows = self.db.fetch_all(query, tuple(query_params))
            return ApiResponse.ok([dict(r) for r in rows], total_count=total, page=params.page, page_size=params.page_size)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def get_person(self, person_id: str) -> ApiResponse:
        try:
            row = self.db.fetch_one("SELECT * FROM persons WHERE person_id = ?", (person_id,))
            if row:
                person = dict(row)
                # Get relations
                relations = self.db.fetch_all(
                    "SELECT * FROM person_unit_relations WHERE person_id = ?",
                    (person_id,)
                )
                person["relations"] = [dict(r) for r in relations]
                return ApiResponse.ok(person)
            return ApiResponse.error("Person not found", "E404")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def create_person(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            data["person_id"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            self.db.execute(f"INSERT INTO persons ({columns}) VALUES ({placeholders})", tuple(data.values()))
            return ApiResponse.ok(data)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_person(self, person_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(f"UPDATE persons SET {set_clause} WHERE person_id = ?",
                          tuple(list(data.values()) + [person_id]))
            return self.get_person(person_id)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def delete_person(self, person_id: str) -> ApiResponse:
        try:
            self.db.execute("DELETE FROM persons WHERE person_id = ?", (person_id,))
            return ApiResponse.ok({"deleted": True})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Claims ====================

    def get_claims(self, params: QueryParams = None) -> ApiResponse:
        try:
            params = params or QueryParams()

            query = "SELECT * FROM claims WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM claims WHERE 1=1"
            query_params = []

            if params.filters.get("case_status"):
                query += " AND case_status = ?"
                count_query += " AND case_status = ?"
                query_params.append(params.filters["case_status"])

            if params.search:
                query += " AND (claim_id LIKE ? OR case_number LIKE ?)"
                count_query += " AND (claim_id LIKE ? OR case_number LIKE ?)"
                sp = f"%{params.search}%"
                query_params.extend([sp, sp])

            count_result = self.db.fetch_one(count_query, tuple(query_params))
            total = count_result["count"] if count_result else 0

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            query_params.extend([params.page_size, (params.page - 1) * params.page_size])

            rows = self.db.fetch_all(query, tuple(query_params))
            return ApiResponse.ok([dict(r) for r in rows], total_count=total, page=params.page, page_size=params.page_size)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def get_claim(self, claim_id: str) -> ApiResponse:
        try:
            row = self.db.fetch_one(
                "SELECT * FROM claims WHERE claim_uuid = ? OR claim_id = ? OR case_number = ?",
                (claim_id, claim_id, claim_id)
            )
            if row:
                return ApiResponse.ok(dict(row))
            return ApiResponse.error("Claim not found", "E404")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def create_claim(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            data["claim_uuid"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()
            if "case_status" not in data:
                data["case_status"] = "draft"

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            self.db.execute(f"INSERT INTO claims ({columns}) VALUES ({placeholders})", tuple(data.values()))
            return ApiResponse.ok(data)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_claim(self, claim_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(
                f"UPDATE claims SET {set_clause} WHERE claim_uuid = ? OR claim_id = ?",
                tuple(list(data.values()) + [claim_id, claim_id])
            )
            return self.get_claim(claim_id)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def delete_claim(self, claim_id: str) -> ApiResponse:
        try:
            self.db.execute("DELETE FROM claims WHERE claim_uuid = ? OR claim_id = ?", (claim_id, claim_id))
            return ApiResponse.ok({"deleted": True})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Relations ====================

    def get_relations(self, params: QueryParams = None) -> ApiResponse:
        try:
            params = params or QueryParams()
            query = "SELECT * FROM person_unit_relations WHERE 1=1"
            query_params = []

            if params.filters.get("person_id"):
                query += " AND person_id = ?"
                query_params.append(params.filters["person_id"])

            if params.filters.get("unit_id"):
                query += " AND unit_id = ?"
                query_params.append(params.filters["unit_id"])

            query += " LIMIT ? OFFSET ?"
            query_params.extend([params.page_size, (params.page - 1) * params.page_size])

            rows = self.db.fetch_all(query, tuple(query_params))
            return ApiResponse.ok([dict(r) for r in rows])
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def get_relation(self, relation_id: str) -> ApiResponse:
        try:
            row = self.db.fetch_one("SELECT * FROM person_unit_relations WHERE relation_id = ?", (relation_id,))
            if row:
                return ApiResponse.ok(dict(row))
            return ApiResponse.error("Relation not found", "E404")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def create_relation(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            data["relation_id"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            self.db.execute(f"INSERT INTO person_unit_relations ({columns}) VALUES ({placeholders})", tuple(data.values()))
            return ApiResponse.ok(data)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_relation(self, relation_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(f"UPDATE person_unit_relations SET {set_clause} WHERE relation_id = ?",
                          tuple(list(data.values()) + [relation_id]))
            return self.get_relation(relation_id)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def delete_relation(self, relation_id: str) -> ApiResponse:
        try:
            self.db.execute("DELETE FROM person_unit_relations WHERE relation_id = ?", (relation_id,))
            return ApiResponse.ok({"deleted": True})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Documents ====================

    def get_documents(self, params: QueryParams = None) -> ApiResponse:
        try:
            rows = self.db.fetch_all("SELECT * FROM documents ORDER BY created_at DESC")
            return ApiResponse.ok([dict(r) for r in rows])
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def get_document(self, document_id: str) -> ApiResponse:
        try:
            row = self.db.fetch_one("SELECT * FROM documents WHERE document_id = ?", (document_id,))
            if row:
                return ApiResponse.ok(dict(row))
            return ApiResponse.error("Document not found", "E404")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def create_document(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            data["document_id"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            self.db.execute(f"INSERT INTO documents ({columns}) VALUES ({placeholders})", tuple(data.values()))
            return ApiResponse.ok(data)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_document(self, document_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(f"UPDATE documents SET {set_clause} WHERE document_id = ?",
                          tuple(list(data.values()) + [document_id]))
            return self.get_document(document_id)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def delete_document(self, document_id: str) -> ApiResponse:
        try:
            self.db.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            return ApiResponse.ok({"deleted": True})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Users & Auth ====================

    def authenticate(self, username: str, password: str) -> ApiResponse:
        try:
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            row = self.db.fetch_one(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            )

            if row:
                user = dict(row)
                if user.get("password_hash") == password_hash:
                    if user.get("is_locked"):
                        return ApiResponse.error("Account is locked", "E401")

                    self._current_user = user
                    import uuid
                    token = str(uuid.uuid4())

                    return ApiResponse.ok({
                        "token": token,
                        "user": {k: v for k, v in user.items() if k not in ["password_hash", "password_salt"]}
                    })

            return ApiResponse.error("Invalid credentials", "E401")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def get_current_user(self) -> ApiResponse:
        if self._current_user:
            return ApiResponse.ok({k: v for k, v in self._current_user.items()
                                  if k not in ["password_hash", "password_salt"]})
        return ApiResponse.error("Not authenticated", "E401")

    def get_users(self, params: QueryParams = None) -> ApiResponse:
        try:
            rows = self.db.fetch_all("SELECT * FROM users ORDER BY username")
            users = [{k: v for k, v in dict(r).items() if k not in ["password_hash", "password_salt"]}
                    for r in rows]
            return ApiResponse.ok(users, total_count=len(users))
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def create_user(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            import hashlib

            data["user_id"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()

            if "password" in data:
                data["password_hash"] = hashlib.sha256(data.pop("password").encode()).hexdigest()

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            self.db.execute(f"INSERT INTO users ({columns}) VALUES ({placeholders})", tuple(data.values()))

            return ApiResponse.ok({k: v for k, v in data.items() if k not in ["password_hash"]})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_user(self, user_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            import hashlib

            data["updated_at"] = datetime.now().isoformat()
            if "password" in data:
                data["password_hash"] = hashlib.sha256(data.pop("password").encode()).hexdigest()

            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?",
                          tuple(list(data.values()) + [user_id]))

            row = self.db.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
            if row:
                return ApiResponse.ok({k: v for k, v in dict(row).items() if k not in ["password_hash"]})
            return ApiResponse.error("User not found", "E404")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Vocabularies ====================

    def get_vocabularies(self) -> ApiResponse:
        try:
            rows = self.db.fetch_all("SELECT * FROM vocabulary_terms WHERE status = 'active' ORDER BY vocabulary_name, term_code")
            vocabularies = {}
            for row in rows:
                r = dict(row)
                vocab_name = r["vocabulary_name"]
                if vocab_name not in vocabularies:
                    vocabularies[vocab_name] = []
                vocabularies[vocab_name].append({
                    "code": r["term_code"],
                    "label": r["term_label"],
                    "label_ar": r.get("term_label_ar")
                })
            return ApiResponse.ok(vocabularies)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def get_vocabulary(self, vocab_name: str) -> ApiResponse:
        try:
            rows = self.db.fetch_all(
                "SELECT * FROM vocabulary_terms WHERE vocabulary_name = ? AND status = 'active' ORDER BY term_code",
                (vocab_name,)
            )
            terms = [{"code": dict(r)["term_code"], "label": dict(r)["term_label"], "label_ar": dict(r).get("term_label_ar")}
                    for r in rows]
            return ApiResponse.ok(terms)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_vocabulary_term(self, vocab_name: str, term_code: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(
                f"UPDATE vocabulary_terms SET {set_clause} WHERE vocabulary_name = ? AND term_code = ?",
                tuple(list(data.values()) + [vocab_name, term_code])
            )
            return ApiResponse.ok({"updated": True})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Dashboard & Statistics ====================

    def get_dashboard_stats(self) -> ApiResponse:
        try:
            stats = {}

            # Building stats
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM buildings")
            stats["total_buildings"] = result["count"] if result else 0

            # Unit stats
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM property_units")
            stats["total_units"] = result["count"] if result else 0

            # Person stats
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM persons")
            stats["total_persons"] = result["count"] if result else 0

            # Claim stats
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM claims")
            stats["total_claims"] = result["count"] if result else 0

            # Claims by status
            rows = self.db.fetch_all("SELECT case_status, COUNT(*) as count FROM claims GROUP BY case_status")
            stats["claims_by_status"] = {dict(r)["case_status"]: dict(r)["count"] for r in rows}

            # Buildings by status
            rows = self.db.fetch_all("SELECT building_status, COUNT(*) as count FROM buildings GROUP BY building_status")
            stats["buildings_by_status"] = {dict(r)["building_status"]: dict(r)["count"] for r in rows}

            return ApiResponse.ok(stats)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def get_building_stats(self) -> ApiResponse:
        return self.get_dashboard_stats()

    def get_claim_stats(self) -> ApiResponse:
        try:
            stats = {}
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM claims")
            stats["total"] = result["count"] if result else 0

            rows = self.db.fetch_all("SELECT case_status, COUNT(*) as count FROM claims GROUP BY case_status")
            stats["by_status"] = {dict(r)["case_status"]: dict(r)["count"] for r in rows}

            return ApiResponse.ok(stats)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Duplicates ====================

    def get_duplicate_candidates(self, entity_type: str, params: QueryParams = None) -> ApiResponse:
        try:
            rows = self.db.fetch_all(
                "SELECT * FROM duplicate_candidates WHERE source_type = ? AND status = 'pending'",
                (entity_type,)
            )
            return ApiResponse.ok([dict(r) for r in rows])
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def resolve_duplicate(self, resolution_data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            resolution_data["resolution_id"] = str(uuid.uuid4())
            resolution_data["resolved_at"] = datetime.now().isoformat()

            columns = ", ".join(resolution_data.keys())
            placeholders = ", ".join(["?"] * len(resolution_data))
            self.db.execute(f"INSERT INTO duplicate_resolutions ({columns}) VALUES ({placeholders})",
                          tuple(resolution_data.values()))
            return ApiResponse.ok(resolution_data)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Import/Export ====================

    def import_data(self, file_path: str, import_type: str) -> ApiResponse:
        # Delegate to existing import service
        return ApiResponse.ok({"status": "not_implemented"})

    def export_data(self, export_type: str, filters: Dict[str, Any] = None) -> ApiResponse:
        # Delegate to existing export service
        return ApiResponse.ok({"status": "not_implemented"})

    # ==================== Assignments ====================

    def get_building_assignments(self, params: QueryParams = None) -> ApiResponse:
        try:
            rows = self.db.fetch_all("SELECT * FROM building_assignments ORDER BY assignment_date DESC")
            return ApiResponse.ok([dict(r) for r in rows])
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def create_assignment(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            import uuid
            data["assignment_id"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            self.db.execute(f"INSERT INTO building_assignments ({columns}) VALUES ({placeholders})",
                          tuple(data.values()))
            return ApiResponse.ok(data)
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_assignment(self, assignment_id: str, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(f"UPDATE building_assignments SET {set_clause} WHERE assignment_id = ?",
                          tuple(list(data.values()) + [assignment_id]))

            row = self.db.fetch_one("SELECT * FROM building_assignments WHERE assignment_id = ?", (assignment_id,))
            if row:
                return ApiResponse.ok(dict(row))
            return ApiResponse.error("Assignment not found", "E404")
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Audit ====================

    def get_audit_log(self, params: QueryParams = None) -> ApiResponse:
        try:
            params = params or QueryParams()
            query = "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            rows = self.db.fetch_all(query, (params.page_size, (params.page - 1) * params.page_size))
            return ApiResponse.ok([dict(r) for r in rows])
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    # ==================== Settings ====================

    def get_security_settings(self) -> ApiResponse:
        try:
            row = self.db.fetch_one("SELECT * FROM security_settings WHERE setting_id = 'default'")
            if row:
                return ApiResponse.ok(dict(row))
            return ApiResponse.ok({})
        except Exception as e:
            return ApiResponse.error(str(e), "E500")

    def update_security_settings(self, data: Dict[str, Any]) -> ApiResponse:
        try:
            data["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
            self.db.execute(f"UPDATE security_settings SET {set_clause} WHERE setting_id = 'default'",
                          tuple(data.values()))
            return self.get_security_settings()
        except Exception as e:
            return ApiResponse.error(str(e), "E500")
