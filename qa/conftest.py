"""Shared QA fixtures for black-box API tests.

These tests talk to the running app over HTTP only. Nothing here imports
from the application under test. Base URL comes from QA_BASE_URL, defaulting
to http://localhost:8000.
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("QA_BASE_URL", "http://localhost:8000")
API = f"{BASE_URL}/api/v1"


@pytest.fixture()
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c
