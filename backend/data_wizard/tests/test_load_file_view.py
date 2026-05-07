"""
Integration tests for the LoadFileView HTTP endpoint.

Endpoint: POST /api/data-wizard/load-file/
Auth: force_authenticate via conftest api_client fixture
File: raw body with Content-Disposition header (FileUploadParser)

Key headers:
  X-Model-Type     model type string (required)
  X-Folder-Id      target folder UUID
  X-On-Conflict    stop | skip | update (default: stop)

Pattern mirrors tprm/test/test_views.py:
  - Real DRF request through the full view stack
  - RBAC patched via the shared all_accessible fixture
  - Asserts HTTP status code + response payload shape, not intermediate dicts
"""

import pytest

from core.models import (
    AppliedControl,
    Asset,
    Perimeter,
    Policy,
    ReferenceControl,
    SecurityException,
    Threat,
    Vulnerability,
)
from ebios_rm.models import ElementaryAction
from iam.models import User
from privacy.models import Processing

from data_wizard.tests.conftest import make_excel_file

URL = "/api/data-wizard/load-file/"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _post(client, data: bytes, filename: str, model_type: str, folder_id=None, **extra):
    headers = {
        "HTTP_X_MODEL_TYPE": model_type,
        "HTTP_CONTENT_DISPOSITION": f"attachment; filename={filename}",
        "content_type": "application/octet-stream",
    }
    if folder_id:
        headers["HTTP_X_FOLDER_ID"] = str(folder_id)
    headers.update(extra)
    return client.post(URL, data=data, **headers)


def _csv(text: str) -> bytes:
    return text.encode()


def _assert_response_shape(body: dict):
    """Verify the standard response envelope is complete."""
    results = body.get("results", {})
    for key in ("created", "updated", "skipped", "failed", "stopped", "errors"):
        assert key in results, f"Missing key '{key}' in response results"


# ─────────────────────────────────────────────────────────────────────────────
# Request-level validation (no model needed, no RBAC patch needed)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRequestValidation:
    def test_no_data_returns_400(self, api_client):
        resp = api_client.post(URL, data=None, content_type="application/octet-stream")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_unsupported_file_format_returns_400(self, api_client, domain_folder):
        resp = _post(api_client, b"garbage", "data.txt", "Asset", domain_folder.id)
        assert resp.status_code == 400
        assert resp.json()["error"] == "unsupportedFileFormat"

    def test_unknown_model_type_returns_400(self, api_client, domain_folder):
        resp = _post(
            api_client, _csv("name\nTest"), "data.csv", "NoSuchModel", domain_folder.id
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "UnknownModelType"

    def test_unauthenticated_returns_401_or_403(self, domain_folder):
        from rest_framework.test import APIClient

        anon = APIClient()
        resp = _post(anon, _csv("name\nX"), "data.csv", "Asset", domain_folder.id)
        assert resp.status_code in (401, 403)

    def test_response_envelope_shape(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nShapeTest,SHP-001\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
        )
        assert resp.status_code == 200
        _assert_response_shape(resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# Conflict modes — tested on Asset as the representative model
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestConflictModes:
    def test_stop_mode_halts_on_duplicate(
        self, api_client, domain_folder, all_accessible
    ):
        Asset.objects.create(name="Web App", ref_id="AST-STOP", folder=domain_folder)
        resp = _post(
            api_client,
            _csv("name,ref_id\nWeb App,AST-STOP\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
        )
        body = resp.json()
        assert body["results"]["stopped"] is True
        assert body["results"]["failed"] == 1

    def test_skip_mode_ignores_duplicate(
        self, api_client, domain_folder, all_accessible
    ):
        Asset.objects.create(name="Web App", ref_id="AST-SKIP", folder=domain_folder)
        resp = _post(
            api_client,
            _csv("name,ref_id\nWeb App,AST-SKIP\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="skip",
        )
        body = resp.json()
        assert body["results"]["skipped"] == 1
        assert body["results"]["created"] == 0
        assert body["results"]["stopped"] is False

    def test_update_mode_patches_existing_record(
        self, api_client, domain_folder, all_accessible
    ):
        Asset.objects.create(
            name="Web App", ref_id="AST-UPD", folder=domain_folder, description="old"
        )
        resp = _post(
            api_client,
            _csv("name,ref_id,description\nWeb App,AST-UPD,new description\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="update",
        )
        assert resp.json()["results"]["updated"] == 1
        assert Asset.objects.get(ref_id="AST-UPD").description == "new description"

    def test_update_mode_deduplicates_by_ref_id_not_name(
        self, api_client, domain_folder, all_accessible
    ):
        """ref_id match must win even when the CSV name differs from the stored name."""
        asset = Asset.objects.create(
            name="Old Name", ref_id="AST-REF", folder=domain_folder
        )
        resp = _post(
            api_client,
            _csv("name,ref_id,description\nNew Name,AST-REF,updated\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="update",
        )
        assert resp.json()["results"]["updated"] == 1
        asset.refresh_from_db()
        assert asset.description == "updated"


# ─────────────────────────────────────────────────────────────────────────────
# CSV vs XLSX file detection
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFileFormatDetection:
    def test_csv_accepted(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nCSV Asset,CSV-001\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1

    def test_xlsx_accepted(self, api_client, domain_folder, all_accessible):
        excel = make_excel_file(
            {"Sheet1": [{"name": "Excel Asset", "ref_id": "XLS-001"}]}
        )
        resp = _post(api_client, excel.read(), "a.xlsx", "Asset", domain_folder.id)
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1

    def test_csv_and_xlsx_produce_same_result(
        self, api_client, domain_folder, all_accessible
    ):
        resp_csv = _post(
            api_client,
            _csv("name,ref_id\nSame,SAME-001\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
        )
        Asset.objects.filter(ref_id="SAME-001").delete()

        excel = make_excel_file({"Sheet1": [{"name": "Same", "ref_id": "SAME-001"}]})
        resp_excel = _post(
            api_client, excel.read(), "a.xlsx", "Asset", domain_folder.id
        )

        assert resp_csv.json()["results"]["created"] == 1
        assert resp_excel.json()["results"]["created"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Per-model smoke tests — one create + response shape per model type
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAssetEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id,type\nWeb App,AST-001,primary\n"),
            "a.csv",
            "Asset",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert Asset.objects.filter(ref_id="AST-001", folder=domain_folder).exists()

    def test_missing_name_fails(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client, _csv("ref_id\nAST-X\n"), "a.csv", "Asset", domain_folder.id
        )
        assert resp.json()["results"]["failed"] == 1

    def test_xlsx_create(self, api_client, domain_folder, all_accessible):
        excel = make_excel_file(
            {"Sheet1": [{"name": "Excel Asset", "ref_id": "AST-XLS"}]}
        )
        resp = _post(api_client, excel.read(), "a.xlsx", "Asset", domain_folder.id)
        assert resp.json()["results"]["created"] == 1


@pytest.mark.django_db
class TestAppliedControlEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nPatch Mgmt,AC-001\n"),
            "a.csv",
            "AppliedControl",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert AppliedControl.objects.filter(ref_id="AC-001").exists()

    def test_ref_id_deduplication_on_skip(
        self, api_client, domain_folder, all_accessible
    ):
        AppliedControl.objects.create(
            name="Original", ref_id="AC-DUP", folder=domain_folder
        )
        resp = _post(
            api_client,
            _csv("name,ref_id\nDifferent,AC-DUP\n"),
            "a.csv",
            "AppliedControl",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="skip",
        )
        assert resp.json()["results"]["skipped"] == 1
        assert AppliedControl.objects.get(ref_id="AC-DUP").name == "Original"


@pytest.mark.django_db
class TestVulnerabilityEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id,severity\nLog4Shell,CVE-2021-44228,critical\n"),
            "a.csv",
            "Vulnerability",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert Vulnerability.objects.filter(ref_id="CVE-2021-44228").exists()

    def test_deduplication_by_ref_id(self, api_client, domain_folder, all_accessible):
        Vulnerability.objects.create(
            name="Log4Shell", ref_id="CVE-SKIP", folder=domain_folder
        )
        resp = _post(
            api_client,
            _csv("name,ref_id\nDifferent,CVE-SKIP\n"),
            "a.csv",
            "Vulnerability",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="skip",
        )
        assert resp.json()["results"]["skipped"] == 1


@pytest.mark.django_db
class TestPerimeterEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nMain Scope,PRM-001\n"),
            "a.csv",
            "Perimeter",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert Perimeter.objects.filter(ref_id="PRM-001").exists()


@pytest.mark.django_db
class TestThreatEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nPhishing,THR-001\n"),
            "a.csv",
            "Threat",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert Threat.objects.filter(ref_id="THR-001").exists()


@pytest.mark.django_db
class TestReferenceControlEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nMFA Enforcement,RC-001\n"),
            "a.csv",
            "ReferenceControl",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert ReferenceControl.objects.filter(ref_id="RC-001").exists()


@pytest.mark.django_db
class TestPolicyEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nData Classification,POL-001\n"),
            "a.csv",
            "Policy",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert Policy.objects.filter(ref_id="POL-001").exists()


@pytest.mark.django_db
class TestSecurityExceptionEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nLegacy System,SE-001\n"),
            "a.csv",
            "SecurityException",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert SecurityException.objects.filter(ref_id="SE-001").exists()

    def test_ref_id_deduplication_on_skip(
        self, api_client, domain_folder, all_accessible
    ):
        SecurityException.objects.create(
            name="Original", ref_id="SE-DUP", folder=domain_folder
        )
        resp = _post(
            api_client,
            _csv("name,ref_id\nDifferent,SE-DUP\n"),
            "a.csv",
            "SecurityException",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="skip",
        )
        assert resp.json()["results"]["skipped"] == 1


@pytest.mark.django_db
class TestUserEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("email,first_name,last_name\nnewuser@test.com,New,User\n"),
            "a.csv",
            "User",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert User.objects.filter(email="newuser@test.com").exists()

    def test_missing_email_fails(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client, _csv("first_name\nAlice\n"), "a.csv", "User", domain_folder.id
        )
        assert resp.json()["results"]["failed"] == 1


@pytest.mark.django_db
class TestElementaryActionEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id,attack_stage\nPhishing Email,EA-001,know\n"),
            "a.csv",
            "ElementaryAction",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert ElementaryAction.objects.filter(
            ref_id="EA-001", folder=domain_folder
        ).exists()

    def test_ref_id_deduplication_on_skip(
        self, api_client, domain_folder, all_accessible
    ):
        ElementaryAction.objects.create(
            name="Original", ref_id="EA-DUP", folder=domain_folder
        )
        resp = _post(
            api_client,
            _csv("name,ref_id\nDifferent,EA-DUP\n"),
            "a.csv",
            "ElementaryAction",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="skip",
        )
        assert resp.json()["results"]["skipped"] == 1

    def test_xlsx_create(self, api_client, domain_folder, all_accessible):
        excel = make_excel_file(
            {"Sheet1": [{"name": "XLSX Action", "ref_id": "EA-XLS"}]}
        )
        resp = _post(
            api_client, excel.read(), "a.xlsx", "ElementaryAction", domain_folder.id
        )
        assert resp.json()["results"]["created"] == 1


@pytest.mark.django_db
class TestProcessingEndpoint:
    def test_create(self, api_client, domain_folder, all_accessible):
        resp = _post(
            api_client,
            _csv("name,ref_id\nHR Payroll,PRC-001\n"),
            "a.csv",
            "Processing",
            domain_folder.id,
        )
        assert resp.status_code == 200
        assert resp.json()["results"]["created"] == 1
        assert Processing.objects.filter(
            ref_id="PRC-001", folder=domain_folder
        ).exists()

    def test_ref_id_deduplication_on_skip(
        self, api_client, domain_folder, all_accessible
    ):
        Processing.objects.create(
            name="Original", ref_id="PRC-DUP", folder=domain_folder
        )
        resp = _post(
            api_client,
            _csv("name,ref_id\nDifferent,PRC-DUP\n"),
            "a.csv",
            "Processing",
            domain_folder.id,
            HTTP_X_ON_CONFLICT="skip",
        )
        assert resp.json()["results"]["skipped"] == 1

    def test_xlsx_create(self, api_client, domain_folder, all_accessible):
        excel = make_excel_file(
            {"Sheet1": [{"name": "XLSX Processing", "ref_id": "PRC-XLS"}]}
        )
        resp = _post(api_client, excel.read(), "a.xlsx", "Processing", domain_folder.id)
        assert resp.json()["results"]["created"] == 1
