"""The only MongoDB data layer in the project.

MongoDB has no Row Level Security, so every read and write goes through
`TenantCollection`, which always adds `tenant_id` to filters, inserts and
aggregation pipelines. No other module may import `pymongo` (a test checks).

Collections (see spec section 3):
    lead_form_responses   raw Meta leads
    activity_logs         append-only timeline events
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from django.conf import settings
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from common.tenancy.context import require_current_tenant_id

LEAD_FORM_RESPONSES = "lead_form_responses"
ACTIVITY_LOGS = "activity_logs"

_client: MongoClient | None = None


class TenantViolation(ValueError):
    """Raised when code tries to read or write another tenant's documents."""


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if settings.MONGO_URI.startswith("mongomock://"):
            import mongomock  # dev/test only

            _client = mongomock.MongoClient(tz_aware=True)
        else:
            _client = MongoClient(settings.MONGO_URI, tz_aware=True, serverSelectionTimeoutMS=5000)
    return _client


def get_database() -> Database:
    return get_client()[settings.MONGO_DB_NAME]


def ensure_indexes() -> None:
    """Create the indexes from the spec. Safe to run many times."""
    db = get_database()
    db[LEAD_FORM_RESPONSES].create_index(
        [("tenant_id", ASCENDING), ("leadgen_id", ASCENDING)], unique=True
    )
    db[LEAD_FORM_RESPONSES].create_index(
        [("tenant_id", ASCENDING), ("form_id", ASCENDING), ("created_time", ASCENDING)]
    )
    db[LEAD_FORM_RESPONSES].create_index([("tenant_id", ASCENDING), ("enquiry_id", ASCENDING)])
    db[ACTIVITY_LOGS].create_index(
        [("tenant_id", ASCENDING), ("enquiry_id", ASCENDING), ("created_at", DESCENDING)]
    )
    db[ACTIVITY_LOGS].create_index(
        [("tenant_id", ASCENDING), ("contact_id", ASCENDING), ("created_at", DESCENDING)]
    )
    db[ACTIVITY_LOGS].create_index(
        [("tenant_id", ASCENDING), ("type", ASCENDING), ("created_at", ASCENDING)]
    )


class TenantCollection:
    """A MongoDB collection that can only see one tenant's documents."""

    def __init__(self, name: str, tenant_id: int):
        if not isinstance(tenant_id, int) or isinstance(tenant_id, bool) or tenant_id <= 0:
            raise TenantViolation("A valid tenant_id is required.")
        self.name = name
        self.tenant_id = tenant_id

    @classmethod
    def for_current_tenant(cls, name: str) -> TenantCollection:
        return cls(name, require_current_tenant_id())

    @property
    def _collection(self) -> Collection:
        return get_database()[self.name]

    # --- scoping helpers ---------------------------------------------------
    def _scope_filter(self, filter_: Mapping[str, Any] | None) -> dict[str, Any]:
        scoped = dict(filter_ or {})
        if "tenant_id" in scoped and scoped["tenant_id"] != self.tenant_id:
            raise TenantViolation("Filter targets another tenant.")
        scoped["tenant_id"] = self.tenant_id
        return scoped

    def _scope_document(self, document: Mapping[str, Any]) -> dict[str, Any]:
        doc = dict(document)
        if "tenant_id" in doc and doc["tenant_id"] != self.tenant_id:
            raise TenantViolation("Document belongs to another tenant.")
        doc["tenant_id"] = self.tenant_id
        return doc

    @staticmethod
    def _check_update(update: Mapping[str, Any]) -> None:
        for operator, fields in update.items():
            if not operator.startswith("$"):
                raise TenantViolation("Use update operators ($set, $push, ...), not a document.")
            if isinstance(fields, Mapping) and "tenant_id" in fields:
                raise TenantViolation("tenant_id cannot be changed.")

    # --- reads -------------------------------------------------------------
    def find(
        self,
        filter_: Mapping[str, Any] | None = None,
        *,
        projection: Mapping[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        cursor = self._collection.find(self._scope_filter(filter_), projection)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def find_one(
        self, filter_: Mapping[str, Any] | None = None, *, projection=None
    ) -> dict[str, Any] | None:
        return self._collection.find_one(self._scope_filter(filter_), projection)

    def count_documents(self, filter_: Mapping[str, Any] | None = None) -> int:
        return self._collection.count_documents(self._scope_filter(filter_))

    def aggregate(self, pipeline: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        stages = list(pipeline)
        blocked = {"$lookup", "$graphLookup", "$unionWith", "$out", "$merge"}
        if any(blocked & set(stage) for stage in stages):
            raise TenantViolation("Cross-collection stages are not allowed.")
        return list(
            self._collection.aggregate([{"$match": {"tenant_id": self.tenant_id}}, *stages])
        )

    # --- writes ------------------------------------------------------------
    def insert_one(self, document: Mapping[str, Any]) -> Any:
        return self._collection.insert_one(self._scope_document(document)).inserted_id

    def insert_many(self, documents: Iterable[Mapping[str, Any]]) -> list[Any]:
        docs = [self._scope_document(d) for d in documents]
        return self._collection.insert_many(docs).inserted_ids if docs else []

    def update_one(
        self, filter_: Mapping[str, Any], update: Mapping[str, Any], *, upsert: bool = False
    ) -> int:
        self._check_update(update)
        return self._collection.update_one(
            self._scope_filter(filter_), update, upsert=upsert
        ).modified_count

    def update_many(self, filter_: Mapping[str, Any], update: Mapping[str, Any]) -> int:
        self._check_update(update)
        return self._collection.update_many(self._scope_filter(filter_), update).modified_count

    def delete_many(self, filter_: Mapping[str, Any]) -> int:
        """For tenant data deletion (DPDP). Never use on activity_logs from user actions."""
        return self._collection.delete_many(self._scope_filter(filter_)).deleted_count
