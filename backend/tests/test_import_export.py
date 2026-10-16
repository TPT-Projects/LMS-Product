"""Phase 3: import (live and background), failed-row report, notifications, export, audit."""

import csv
import io
from datetime import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.audit.models import AuditLog
from apps.enquiries.models import Enquiry
from common.tenancy.context import tenant_context

from .conftest import create_enquiry

pytestmark = pytest.mark.django_db


def csv_file(rows: list[list[str]], name="leads.csv") -> SimpleUploadedFile:
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return SimpleUploadedFile(name, ("﻿" + out.getvalue()).encode("utf-8"), content_type="text/csv")


def upload(session, file) -> dict:
    r = session.client.post("/api/v1/imports", {"file": file}, format="multipart")
    assert r.status_code == 201, r.data
    return r.data


# --- the Phase 3 "Done when" -----------------------------------------------------------------
def test_live_import_maps_previews_links_duplicates_and_reports_failures(signup):
    owner = signup()
    owner.client.post("/api/v1/custom-fields", {"label": "City", "type": "text"}, format="json")
    existing = create_enquiry(owner, name="Karan", phone="+919800022222")
    job = upload(
        owner,
        csv_file(
            [
                ["Full Name", "Mobile", "Email", "City", "Date", "Notes"],
                ["Aarav Shah", "919800022222", "k@example.com", "Ahmedabad", "05/07/2026", "x"],
                ["Riya Shah", "+91 98765 43210", "", "Surat", "06/07/2026 14:30", ""],
                ["Bad Phone", "12345", "", "", "31/02/2026", ""],
            ]
        ),
    )
    assert job["row_count"] == 3
    assert job["mapping"] == {
        "Full Name": "name",
        "Mobile": "phone",
        "Email": "email",
        "City": "cf:city",
        "Date": "created_at",
    }
    assert job["sample"][0]["Full Name"] == "Aarav Shah"

    r = owner.client.post(
        f"/api/v1/imports/{job['id']}/map",
        {"mapping": {**job["mapping"], "Notes": ""}},
        format="json",
    )
    assert r.status_code == 200 and r.data["status"] == "mapped"

    preview = owner.client.get(f"/api/v1/imports/{job['id']}/preview").data
    assert preview["summary"] == {
        "total": 3, "valid": 2, "invalid": 1, "existing_contacts": 1, "duplicates_in_file": 0,
    }  # fmt: skip
    assert preview["mode"] == "live"
    assert any("Phone" in e for e in preview["rows"][2]["errors"])
    with tenant_context(owner.tenant_id):
        assert Enquiry.objects.count() == 1  # preview saved nothing

    r = owner.client.post(f"/api/v1/imports/{job['id']}/run")
    assert r.data["status"] == "completed_with_errors"
    assert (r.data["created_count"], r.data["linked_count"], r.data["failed_count"]) == (1, 1, 1)

    rows = owner.client.get("/api/v1/enquiries", {"source": "import"}).data["results"]
    karan = next(e for e in rows if e["name"] == "Aarav Shah")
    assert karan["is_repeat"] and karan["contact_id"] == existing["contact"]["id"]
    assert karan["custom_fields"] == {"city": "Ahmedabad"}
    assert karan["created_at"].startswith("2026-07-04T18:30")  # 05/07/2026 00:00 IST in UTC

    report = owner.client.get(f"/api/v1/imports/{job['id']}/failed-report")
    text = report.content.decode("utf-8-sig")
    assert "Bad Phone" in text and "Errors" in text and "Date" in text

    timeline = owner.client.get(f"/api/v1/enquiries/{karan['id']}/timeline").data["results"]
    created = next(i for i in timeline if i["type"] == "enquiry_created")
    assert created["details"]["import_job_id"] == job["id"]


def test_background_import_notifies_when_done(signup, django_capture_on_commit_callbacks):
    owner = signup()
    rows = [["Name", "Phone"]] + [[f"Lead {i}", f"+9198{i:08d}"] for i in range(150)]
    job = upload(owner, csv_file(rows))
    owner.client.post(
        f"/api/v1/imports/{job['id']}/map", {"mapping": job["mapping"]}, format="json"
    )

    with django_capture_on_commit_callbacks(execute=True):
        r = owner.client.post(f"/api/v1/imports/{job['id']}/run")
    assert r.data["mode"] == "background" and r.data["status"] == "queued"

    done = owner.client.get(f"/api/v1/imports/{job['id']}").data
    assert done["status"] == "completed" and done["created_count"] == 150
    assert owner.client.get("/api/v1/enquiries").data["count"] == 150

    notes = owner.client.get("/api/v1/notifications").data
    assert notes["unread_count"] == 1
    assert notes["results"][0]["link"] == f"/imports/{job['id']}"
    assert owner.client.post("/api/v1/notifications/read-all").status_code == 204
    assert owner.client.get("/api/v1/notifications").data["unread_count"] == 0


def test_excel_import_reads_numbers_and_dates(signup):
    owner = signup()
    book = Workbook()
    sheet = book.active
    sheet.append(["Name", "Phone", "Date"])
    sheet.append(["Excel Lead", 919812345678, datetime(2026, 7, 5)])
    data = io.BytesIO()
    book.save(data)
    file = SimpleUploadedFile(
        "leads.xlsx", data.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )  # fmt: skip
    job = upload(owner, file)
    assert job["sample"][0] == {"Name": "Excel Lead", "Phone": "919812345678", "Date": "05/07/2026"}
    owner.client.post(
        f"/api/v1/imports/{job['id']}/map", {"mapping": job["mapping"]}, format="json"
    )
    assert owner.client.post(f"/api/v1/imports/{job['id']}/run").data["created_count"] == 1
    row = owner.client.get("/api/v1/enquiries").data["results"][0]
    assert row["phone_e164"] == "+919812345678"


def test_bad_files_and_mappings_are_refused(signup):
    owner = signup()
    r = owner.client.post(
        "/api/v1/imports",
        {"file": SimpleUploadedFile("x.pdf", b"%PDF", content_type="application/pdf")},
        format="multipart",
    )
    assert r.status_code == 400
    job = upload(owner, csv_file([["Name", "City"], ["A", "B"]]))
    r = owner.client.post(
        f"/api/v1/imports/{job['id']}/map", {"mapping": {"Name": "name"}}, format="json"
    )
    assert r.status_code == 400  # needs phone or email
    assert owner.client.post(f"/api/v1/imports/{job['id']}/run").status_code == 400


def test_agents_cannot_import_or_export(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    assert agent.client.get("/api/v1/imports").status_code == 403
    assert agent.client.post("/api/v1/exports", {}, format="json").status_code == 403


# --- export ---------------------------------------------------------------------------------
def test_export_matches_the_filtered_list_and_is_audited(signup):
    owner = signup()
    other = signup()
    create_enquiry(other, name="Not mine", phone="+919899999999")
    statuses = {s["name"]: s["id"] for s in owner.client.get("/api/v1/statuses").data}
    keep = create_enquiry(owner, name="Riya ₹5 cr – Dubai", phone="+919811111111")
    drop = create_enquiry(owner, name="Drop", phone="+919822222222")
    owner.client.patch(
        f"/api/v1/enquiries/{drop['id']}", {"status_id": statuses["Lost"]}, format="json"
    )

    r = owner.client.post(
        "/api/v1/exports",
        {"status": [statuses["New"]], "columns": ["phone", "name", "created"]},
        format="json",
    )
    assert r.status_code == 200
    body = b"".join(r.streaming_content).decode("utf-8")
    assert body.startswith("﻿")
    rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
    assert rows[0] == ["Phone", "Name", "Created"]
    assert rows[1][:2] == ["+919811111111", "Riya ₹5 cr – Dubai"]
    assert len(rows[1][2]) == 10 and rows[1][2][2] == "/"  # DD/MM/YYYY
    assert len(rows) == 2  # Lost one and the other workspace's lead are not exported
    assert keep["id"]

    with tenant_context(owner.tenant_id):
        log = AuditLog.objects.get(action="export.enquiries")
        assert log.details["rows"] == 1 and log.actor_id == owner.user_id


def test_role_changes_are_audited(signup, invite_and_join):
    owner = signup()
    agent = invite_and_join(owner, "agent")
    owner.client.patch(f"/api/v1/users/{agent.user_id}/role", {"role": "manager"}, format="json")
    with tenant_context(owner.tenant_id):
        log = AuditLog.objects.get(action="user.role_changed")
        assert log.details["from"] == "agent" and log.details["to"] == "manager"
