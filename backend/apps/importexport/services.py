"""Import jobs: upload, map, preview, run (live or background), failed-record report."""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterator

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from apps.contacts.models import Contact
from apps.customfields.models import CustomField
from apps.enquiries.ingestion import ingest_enquiry
from apps.notifications.service import IMPORT_FINISHED, notify
from apps.tenants.models import Tenant
from common.tenancy.context import tenant_context

from .models import ImportJob, ImportMode, ImportRowFailed, ImportStatus
from .processing import RowContext, match_key, row_to_data, suggest_mapping, validate_mapping
from .readers import ReadError, file_type_for, read_table

logger = logging.getLogger(__name__)
CHUNK = 100  # rows per transaction (progress is saved after each chunk)
PREVIEW_ROWS = 10


def _rows(job: ImportJob) -> Iterator[dict[str, str]]:
    with job.file.open("rb") as fh:
        _, rows = read_table(fh, job.file_type)
        yield from rows


# --- upload ------------------------------------------------------------------------------
def create_job(*, tenant: Tenant, user, upload) -> ImportJob:
    try:
        file_type = file_type_for(upload.name)
    except ReadError as exc:
        raise ValidationError({"file": [str(exc)]}) from None
    if upload.size > settings.IMPORT_MAX_BYTES:
        mb = settings.IMPORT_MAX_BYTES // (1024 * 1024)
        raise ValidationError({"file": [_("Files can be at most %(mb)s MB.") % {"mb": mb}]})
    try:
        headers, rows = read_table(upload, file_type)
        count = 0
        for _row in rows:
            count += 1
            if count > settings.IMPORT_MAX_ROWS:
                raise ValidationError(
                    {"file": [_("At most %(n)s rows per file.") % {"n": settings.IMPORT_MAX_ROWS}]}
                )
    except ReadError as exc:
        raise ValidationError({"file": [str(exc)]}) from None
    if count == 0:
        raise ValidationError({"file": [_("The file has a header but no rows.")]})

    upload.seek(0)
    fields = list(CustomField.objects.filter(tenant=tenant, is_active=True))
    job = ImportJob(
        tenant=tenant,
        created_by=user,
        original_name=upload.name[:255],
        file_type=file_type,
        headers=headers,
        row_count=count,
        mapping=suggest_mapping(headers, fields),
    )
    job.file.save(upload.name, upload, save=False)
    job.save()
    return job


def sample_rows(job: ImportJob, limit: int = 5) -> list[dict[str, str]]:
    rows = []
    for row in _rows(job):
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def set_mapping(job: ImportJob, mapping: dict[str, str]) -> ImportJob:
    if job.status not in (ImportStatus.UPLOADED, ImportStatus.MAPPED):
        raise ValidationError({"detail": _("This import has already run.")})
    mapping = {h: t for h, t in mapping.items() if t}  # "" = ignore column
    fields = list(CustomField.objects.filter(tenant_id=job.tenant_id, is_active=True))
    if errors := validate_mapping(mapping, job.headers, fields):
        raise ValidationError({"mapping": errors})
    job.mapping = mapping
    job.status = ImportStatus.MAPPED
    job.save(update_fields=["mapping", "status"])
    return job


# --- preview --------------------------------------------------------------------------------
def preview(job: ImportJob) -> dict:
    """First rows as they will be imported + a duplicate summary. Nothing is saved."""
    if not job.mapping:
        raise ValidationError({"mapping": [_("Map the columns first.")]})
    ctx = RowContext.load(job.tenant, job.mapping)
    rows_out, valid, invalid = [], 0, 0
    keys: list[tuple[str, str]] = []
    seen, in_file_dupes = set(), 0
    for number, row in enumerate(_rows(job), start=1):
        data, errors = row_to_data(ctx, row)
        if errors:
            invalid += 1
        else:
            valid += 1
            key = match_key(ctx, data)
            if key:
                if key in seen:
                    in_file_dupes += 1
                seen.add(key)
                keys.append(key)
        if number <= PREVIEW_ROWS:
            rows_out.append(
                {
                    "row_number": number,
                    "values": {t: (row.get(h) or "") for h, t in job.mapping.items()},
                    "errors": errors,
                }
            )

    existing = 0
    for column in ("phone_e164", "email_lower"):
        values = list({v for c, v in keys if c == column})
        for i in range(0, len(values), 1000):
            existing += Contact.objects.filter(
                tenant_id=job.tenant_id,
                deleted_at__isnull=True,
                **{f"{column}__in": values[i : i + 1000]},
            ).count()
    return {
        "rows": rows_out,
        "summary": {
            "total": job.row_count,
            "valid": valid,
            "invalid": invalid,
            "existing_contacts": existing,
            "duplicates_in_file": in_file_dupes,
        },
        "mode": (
            ImportMode.LIVE
            if job.row_count <= settings.IMPORT_LIVE_LIMIT
            else ImportMode.BACKGROUND
        ),
    }


# --- run ---------------------------------------------------------------------------------------
def start(job: ImportJob) -> ImportJob:
    """Up to 100 rows run now (result on screen); bigger files go to a background worker."""
    if job.status != ImportStatus.MAPPED:
        raise ValidationError({"detail": _("Map the columns before running the import.")})
    if job.row_count <= settings.IMPORT_LIVE_LIMIT:
        job.mode = ImportMode.LIVE
        job.save(update_fields=["mode"])
        run(job.pk, job.tenant_id)
        job.refresh_from_db()
        return job

    from .tasks import run_import  # avoid a Celery import at module load

    job.mode = ImportMode.BACKGROUND
    job.status = ImportStatus.QUEUED
    job.save(update_fields=["mode", "status"])
    transaction.on_commit(lambda: run_import.delay(job.pk, job.tenant_id))
    return job


def run(job_id: int, tenant_id: int) -> None:
    """Process the whole file in chunks. Each chunk is one transaction; each row a savepoint."""
    with tenant_context(tenant_id):
        job = ImportJob.objects.select_related("tenant", "created_by").get(pk=job_id)
        if job.is_finished or job.status == ImportStatus.RUNNING:
            return  # already done (task retried or delivered twice)
        job.status, job.started_at = ImportStatus.RUNNING, timezone.now()
        job.save(update_fields=["status", "started_at"])
        ctx = RowContext.load(job.tenant, job.mapping)

    def process_chunk(chunk: list[tuple[int, dict]]) -> None:
        with tenant_context(tenant_id):
            created = linked = failed = 0
            for number, row in chunk:
                data, errors = row_to_data(ctx, row)
                if not errors:
                    data.extra_details = {"import_job_id": job_id}
                    try:
                        result = ingest_enquiry(tenant=ctx.tenant, data=data, actor=job.created_by)
                    except Exception as exc:  # one bad row must not stop the file
                        logger.exception("Import %s row %s failed", job_id, number)
                        errors = [_("Could not save this row: %(e)s") % {"e": str(exc)[:200]}]
                    else:
                        if result.is_repeat:
                            linked += 1
                        else:
                            created += 1
                if errors:
                    failed += 1
                    ImportRowFailed.objects.create(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        row_number=number,
                        data=row,
                        errors=errors,
                    )
            ImportJob.objects.filter(pk=job_id).update(
                processed_count=job.processed_count + len(chunk),
                created_count=job.created_count + created,
                linked_count=job.linked_count + linked,
                failed_count=job.failed_count + failed,
            )
            job.processed_count += len(chunk)
            job.created_count += created
            job.linked_count += linked
            job.failed_count += failed

    try:
        chunk: list[tuple[int, dict]] = []
        for number, row in enumerate(_rows(job), start=1):
            chunk.append((number, row))
            if len(chunk) >= CHUNK:
                process_chunk(chunk)
                chunk = []
        if chunk:
            process_chunk(chunk)
        final = ImportStatus.COMPLETED_WITH_ERRORS if job.failed_count else ImportStatus.COMPLETED
        error = ""
    except Exception as exc:
        logger.exception("Import %s stopped", job_id)
        final, error = ImportStatus.FAILED, str(exc)[:500]

    with tenant_context(tenant_id):
        ImportJob.objects.filter(pk=job_id).update(
            status=final, error=error, finished_at=timezone.now()
        )
        if job.processed_count >= 1000:
            # Fresh planner statistics after a big load keep lists fast straight away.
            with connection.cursor() as cursor:
                cursor.execute("ANALYZE enquiries, contacts, enquiry_custom_values")
        if job.mode == ImportMode.BACKGROUND and job.created_by_id:
            notify(
                tenant_id=tenant_id,
                user_id=job.created_by_id,
                kind=IMPORT_FINISHED,
                title=(
                    _("Import finished: %(name)s") % {"name": job.original_name}
                    if final == ImportStatus.COMPLETED
                    else _("Import finished with errors: %(name)s") % {"name": job.original_name}
                ),
                body=_("%(c)s new, %(l)s added to existing contacts, %(f)s failed.")
                % {"c": job.created_count, "l": job.linked_count, "f": job.failed_count},
                link=f"/imports/{job_id}",
                data={"import_id": job_id, "status": final},
            )


# --- failed-record report ------------------------------------------------------------------
def failed_report_csv(job: ImportJob) -> str:
    """The failed rows with an extra "Errors" column. UTF-8 with BOM so Excel opens it."""
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out)
    writer.writerow([*job.headers, _("Errors")])
    for failed in job.failed_rows.all():
        writer.writerow([failed.data.get(h, "") for h in job.headers] + ["; ".join(failed.errors)])
    return out.getvalue()
