"""Tests pour app/utils.py — parse_date."""
import datetime
import pytest

from app.utils import parse_date


def test_parse_date_valid():
    result = parse_date("2026-03-22")
    assert result == datetime.date(2026, 3, 22)


def test_parse_date_none():
    result = parse_date(None)
    assert result is None


def test_parse_date_empty_string():
    result = parse_date("")
    assert result is None


def test_parse_date_whitespace_only():
    result = parse_date("   ")
    assert result is None


def test_parse_date_invalid_format():
    result = parse_date("22/03/2026")
    assert result is None


def test_parse_date_invalid_value():
    result = parse_date("not-a-date")
    assert result is None


def test_parse_date_strips_whitespace():
    result = parse_date("  2026-03-22  ")
    assert result == datetime.date(2026, 3, 22)
