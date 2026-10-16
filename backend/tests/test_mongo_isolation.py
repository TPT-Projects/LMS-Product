"""MongoDB has no RLS, so the data layer must enforce tenant isolation."""

import ast
from pathlib import Path

import pytest

from common.mongo import ACTIVITY_LOGS, LEAD_FORM_RESPONSES, TenantCollection, TenantViolation
from common.tenancy.context import TenantContextError, set_current_tenant_id

A, B = 101, 202


@pytest.fixture
def logs():
    a = TenantCollection(ACTIVITY_LOGS, A)
    b = TenantCollection(ACTIVITY_LOGS, B)
    a.insert_many(
        [{"enquiry_id": 1, "type": "note_added"}, {"enquiry_id": 2, "type": "call_logged"}]
    )
    b.insert_one({"enquiry_id": 1, "type": "status_changed"})
    return a, b


def test_reads_only_see_own_tenant(logs):
    a, b = logs
    assert a.count_documents() == 2
    assert b.count_documents() == 1
    assert {d["type"] for d in a.find({"enquiry_id": 1})} == {"note_added"}
    assert b.find_one({"type": "note_added"}) is None


def test_filter_for_another_tenant_is_refused(logs):
    a, _ = logs
    with pytest.raises(TenantViolation):
        a.find({"tenant_id": B})
    with pytest.raises(TenantViolation):
        a.count_documents({"tenant_id": B})


def test_inserts_always_get_the_tenant(logs):
    a, b = logs
    doc_id = a.insert_one({"enquiry_id": 9, "type": "mention"})
    assert a.find_one({"_id": doc_id})["tenant_id"] == A
    assert b.find_one({"_id": doc_id}) is None
    with pytest.raises(TenantViolation):
        a.insert_one({"tenant_id": B, "type": "note_added"})


def test_updates_cannot_cross_or_change_tenant(logs):
    a, b = logs
    assert b.update_many({"enquiry_id": 1}, {"$set": {"type": "x"}}) == 1
    assert a.find_one({"enquiry_id": 1})["type"] == "note_added"  # A untouched
    with pytest.raises(TenantViolation):
        a.update_one({"enquiry_id": 1}, {"$set": {"tenant_id": B}})
    with pytest.raises(TenantViolation):
        a.update_one({"enquiry_id": 1}, {"type": "replace-whole-doc"})


def test_aggregate_is_scoped_and_cannot_join(logs):
    a, _ = logs
    result = a.aggregate([{"$group": {"_id": None, "n": {"$sum": 1}}}])
    assert result[0]["n"] == 2
    with pytest.raises(TenantViolation):
        a.aggregate([{"$lookup": {"from": LEAD_FORM_RESPONSES, "as": "x", "pipeline": []}}])


def test_tenant_id_is_required():
    for bad in (None, 0, -1, "1", True):
        with pytest.raises(TenantViolation):
            TenantCollection(ACTIVITY_LOGS, bad)


def test_for_current_tenant_uses_context():
    set_current_tenant_id(None)
    with pytest.raises(TenantContextError):
        TenantCollection.for_current_tenant(ACTIVITY_LOGS)
    set_current_tenant_id(A)
    try:
        assert TenantCollection.for_current_tenant(ACTIVITY_LOGS).tenant_id == A
    finally:
        set_current_tenant_id(None)


def test_only_the_data_layer_imports_pymongo():
    root = Path(__file__).resolve().parent.parent
    allowed = {root / "common" / "mongo.py"}
    offenders = []
    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "tests" in path.parts or path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n == "pymongo" or n.startswith("pymongo.") for n in names):
                offenders.append(str(path.relative_to(root)))
    assert offenders == []
