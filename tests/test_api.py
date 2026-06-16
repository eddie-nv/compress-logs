import pytest
from fastapi.testclient import TestClient

from compression.api import app

client = TestClient(app)


# --- /health ---


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- POST /v1/compress ---


def test_compress_endpoint_returns_expected_fields():
    lines = ["Dec 10 sshd: Invalid user admin from 1.2.3.4"] * 10
    response = client.post("/v1/compress", json={"lines": lines})
    assert response.status_code == 200
    body = response.json()
    assert "compressed" in body
    assert "raw_tokens" in body
    assert "compressed_tokens" in body
    assert "reduction_pct" in body


def test_compress_endpoint_reduces_tokens():
    lines = ["Dec 10 sshd: Invalid user admin from 1.2.3.4"] * 20
    response = client.post("/v1/compress", json={"lines": lines})
    body = response.json()
    assert body["raw_tokens"] > body["compressed_tokens"]
    assert body["reduction_pct"] > 0


def test_compress_endpoint_with_empty_lines():
    response = client.post("/v1/compress", json={"lines": []})
    assert response.status_code == 200
    body = response.json()
    assert body["compressed"] == ""
    assert body["raw_tokens"] == 0
    assert body["compressed_tokens"] == 0
    assert body["reduction_pct"] == 0


def test_compress_endpoint_reduction_pct_is_percentage():
    lines = ["GET /api/v1/users 200 42ms upstream=users-service"] * 50
    response = client.post("/v1/compress", json={"lines": lines})
    body = response.json()
    assert 0 <= body["reduction_pct"] <= 100


def test_compress_endpoint_invalid_payload_returns_422():
    response = client.post("/v1/compress", json={"not_lines": "wrong"})
    assert response.status_code == 422


def test_compress_endpoint_lines_must_be_list():
    response = client.post("/v1/compress", json={"lines": "not a list"})
    assert response.status_code == 422
