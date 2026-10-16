from datetime import UTC, date, datetime

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from common.dates import format_date, format_datetime, parse_display_date, parse_meta_time
from common.pagination import StandardPagination


def test_parse_meta_time_is_utc():
    value = parse_meta_time("2026-06-29T17:58:13+0000")
    assert value == datetime(2026, 6, 29, 17, 58, 13, tzinfo=UTC)


def test_display_is_dd_mm_yyyy_in_workspace_timezone():
    late_utc = datetime(2026, 6, 29, 20, 0, tzinfo=UTC)  # already 30 June in India
    assert format_date(late_utc, "Asia/Kolkata") == "30/06/2026"
    assert format_datetime(late_utc, "Asia/Kolkata") == "30/06/2026 01:30"
    assert format_date(date(2026, 7, 5)) == "05/07/2026"


def test_parse_display_date():
    assert parse_display_date(" 05/07/2026 ") == date(2026, 7, 5)
    with pytest.raises(ValueError):
        parse_display_date("2026-07-05")


def test_naive_datetimes_are_refused():
    with pytest.raises(ValueError):
        format_date(datetime(2026, 1, 1), "Asia/Kolkata")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", 25),
        ("?page_size=50", 50),
        ("?page_size=200", 200),
        ("?page_size=500", 25),
        ("?page_size=30", 25),
        ("?page_size=abc", 25),
    ],
)
def test_page_size_options(query, expected):
    request = Request(APIRequestFactory().get(f"/x{query}"))
    assert StandardPagination().get_page_size(request) == expected
