"""End-to-end API tests for the per-RA viewer-role resolution.

Builds a CA with three RAs and two RequirementAssignments, then verifies that
every endpoint that surfaces `viewer_role` agrees on the same per-RA mapping
sourced from Actor-on-Assignment membership.
"""

import pytest
from knox.models import AuthToken
from rest_framework.test import APIClient

from core.models import (
    ComplianceAssessment,
    Framework,
    Perimeter,
    RequirementAssessment,
    RequirementAssignment,
    RequirementNode,
)
from iam.models import Folder, User, UserGroup


def _make_admin(email: str) -> User:
    """Create a user in the BI-UG-ADM group so the queryset isn't filtered out
    by RBAC. The viewer-role resolver runs against Actor membership, not against
    role assignments, so this is sufficient to test role resolution end-to-end."""
    u = User.objects.create_user(email=email, password="pw", is_published=True)
    admin_group = UserGroup.objects.get(name="BI-UG-ADM")
    u.folder = admin_group.folder
    u.save()
    admin_group.user_set.add(u)
    return u


def _make_token(user):
    _, raw = AuthToken.objects.create(user=user)
    return raw


def _client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Token {_make_token(user)}")
    return c


@pytest.fixture
def viewer_role_api_setup(app_config):
    """Lightweight CA + RAs + Assignments for API-level tests.

    Layout::

        CA c
          ├── ra_1, ra_2 ──── Assignment A1 (actor: alice)
          └── ra_3 ─────────── Assignment A2 (actor: bob)
    """
    root = Folder.get_root_folder()
    domain = Folder.objects.create(parent_folder=root, name="vrr-api-domain")
    perimeter = Perimeter.objects.create(name="vrr-api-perimeter", folder=domain)

    fw = Framework.objects.create(
        name="VRR API FW", urn="urn:test:vrr-api-fw", folder=root
    )
    nodes = [
        RequirementNode.objects.create(
            name=f"VRR API Req {i}",
            urn=f"urn:test:vrr-api-req-{i}",
            ref_id=str(i),
            framework=fw,
            assessable=True,
            folder=root,
        )
        for i in (1, 2, 3)
    ]
    ca = ComplianceAssessment.objects.create(
        name="VRR API CA", framework=fw, folder=domain, perimeter=perimeter
    )
    ras = [
        RequirementAssessment.objects.create(
            compliance_assessment=ca, requirement=node, folder=domain
        )
        for node in nodes
    ]

    # Both alice and bob are full admins (so RBAC doesn't filter the queryset)
    # AND have an Actor on a specific Assignment — the resolver tells respondent
    # from auditor purely on Actor membership, independent of admin status.
    alice = _make_admin("alice-api-vrr@example.com")
    bob = _make_admin("bob-api-vrr@example.com")

    a1 = RequirementAssignment.objects.create(compliance_assessment=ca)
    a1.actor.add(alice.actor)
    a1.requirement_assessments.add(ras[0], ras[1])

    a2 = RequirementAssignment.objects.create(compliance_assessment=ca)
    a2.actor.add(bob.actor)
    a2.requirement_assessments.add(ras[2])

    # Pure auditor — admin with no Actor on any assignment in this CA.
    admin = _make_admin("admin-api-vrr@tests.com")
    return {
        "ca": ca,
        "ra_1": ras[0],
        "ra_2": ras[1],
        "ra_3": ras[2],
        "a1": a1,
        "a2": a2,
        "alice": alice,
        "bob": bob,
        "admin": admin,
    }


@pytest.mark.django_db
class TestComplianceAssessmentRequirementsList:
    """`GET /compliance-assessments/{id}/requirements_list/` returns per-RA roles."""

    def test_per_ra_viewer_role_reflects_actor_membership(self, viewer_role_api_setup):
        s = viewer_role_api_setup
        client = _client_for(s["alice"])
        resp = client.get(
            f"/api/compliance-assessments/{s['ca'].id}/requirements_list/?assessable=True"
        )
        assert resp.status_code == 200
        body = resp.json()
        # Aggregate is "respondent" because alice is respondent on at least one RA.
        assert body["viewer_role"] == "respondent"

        roles = {ra["id"]: ra["viewer_role"] for ra in body["requirement_assessments"]}
        assert roles[str(s["ra_1"].id)] == "respondent"
        assert roles[str(s["ra_2"].id)] == "respondent"
        assert roles[str(s["ra_3"].id)] == "auditor"

    def test_pure_auditor_gets_auditor_aggregate_and_per_ra(
        self, viewer_role_api_setup
    ):
        """A user with no Actor-on-Assignment in the CA sees auditor everywhere."""
        s = viewer_role_api_setup
        client = _client_for(s["admin"])
        resp = client.get(
            f"/api/compliance-assessments/{s['ca'].id}/requirements_list/?assessable=True"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["viewer_role"] == "auditor"
        assert all(
            ra["viewer_role"] == "auditor" for ra in body["requirement_assessments"]
        )


@pytest.mark.django_db
class TestRequirementAssessmentDetail:
    """The bare detail GET resolves the per-RA role from the request user."""

    def test_detail_get_returns_per_ra_viewer_role(self, viewer_role_api_setup):
        s = viewer_role_api_setup

        client = _client_for(s["alice"])
        # ra_1: alice is respondent.
        resp = client.get(f"/api/requirement-assessments/{s['ra_1'].id}/")
        assert resp.status_code == 200
        assert resp.json()["viewer_role"] == "respondent"

        # ra_3: alice has no Actor on its assignment — auditor.
        resp = client.get(f"/api/requirement-assessments/{s['ra_3'].id}/")
        assert resp.status_code == 200
        assert resp.json()["viewer_role"] == "auditor"


@pytest.mark.django_db
class TestComplianceAssessmentDetail:
    """The CA detail GET surfaces an aggregate `viewer_role`."""

    def test_aggregate_is_respondent_when_user_has_any_assignment(
        self, viewer_role_api_setup
    ):
        s = viewer_role_api_setup
        client = _client_for(s["alice"])
        resp = client.get(f"/api/compliance-assessments/{s['ca'].id}/")
        assert resp.status_code == 200
        assert resp.json().get("viewer_role") == "respondent"

    def test_aggregate_is_auditor_otherwise(self, viewer_role_api_setup):
        s = viewer_role_api_setup
        client = _client_for(s["admin"])
        resp = client.get(f"/api/compliance-assessments/{s['ca'].id}/")
        assert resp.status_code == 200
        assert resp.json().get("viewer_role") == "auditor"


@pytest.mark.django_db
class TestIsAuditeeEndpoint:
    """`is-auditee` now reports respondent-ness via Actor membership."""

    def test_returns_true_for_actor_on_any_assignment(self, viewer_role_api_setup):
        s = viewer_role_api_setup
        client = _client_for(s["alice"])
        resp = client.get(f"/api/compliance-assessments/{s['ca'].id}/is-auditee/")
        assert resp.status_code == 200
        assert resp.json() == {"is_auditee": True}

    def test_returns_false_for_pure_auditor(self, viewer_role_api_setup):
        s = viewer_role_api_setup
        client = _client_for(s["admin"])
        resp = client.get(f"/api/compliance-assessments/{s['ca'].id}/is-auditee/")
        assert resp.status_code == 200
        assert resp.json() == {"is_auditee": False}


@pytest.mark.django_db
class TestPerRaWriteEnforcement:
    """PATCH on a respondent RA strips hidden fields; PATCH on an auditor RA
    in the same CA does not."""

    def test_respondent_patch_drops_auditor_only_fields(self, viewer_role_api_setup):
        """Score is `auditor: edit, respondent: hidden` by DEFAULT_VISIBILITY,
        so a respondent's PATCH of `score` is silently dropped."""
        s = viewer_role_api_setup
        client = _client_for(s["alice"])

        before = s["ra_1"].score  # None initially
        resp = client.patch(
            f"/api/requirement-assessments/{s['ra_1'].id}/",
            data={"score": 7},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        s["ra_1"].refresh_from_db()
        assert s["ra_1"].score == before  # silently dropped

    def test_auditor_patch_on_neighbour_ra_persists_score(self, viewer_role_api_setup):
        """Same user, same CA, but on an RA where they are auditor — score
        persists because the respondent stripping doesn't fire."""
        s = viewer_role_api_setup
        # Make sure score is editable in the read serializer too so the user
        # can verify the change. Auditor default for `score` is `edit`.
        client = _client_for(s["alice"])

        resp = client.patch(
            f"/api/requirement-assessments/{s['ra_3'].id}/",
            data={"score": 5, "is_scored": True},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        s["ra_3"].refresh_from_db()
        assert s["ra_3"].score == 5
        assert s["ra_3"].is_scored is True


@pytest.mark.django_db
class TestReadStripPerRole:
    """Fields hidden by `field_visibility` for the resolved per-RA role must
    be absent from the GET payload, not merely flagged for UI gating."""

    def test_extended_result_is_stripped_for_respondent_by_default(
        self, viewer_role_api_setup
    ):
        """`extended_result` is AUDITOR_ONLY by default — a respondent's GET
        on an RA they're an actor for must not surface it."""
        s = viewer_role_api_setup
        # Seed DEFAULT_VISIBILITY explicitly so the test does not depend on
        # the CA-creation hook running for ad-hoc objects.
        s["ca"].field_visibility = {
            "extended_result": {"auditor": "edit", "respondent": "hidden"},
            "answers": {"auditor": "edit", "respondent": "edit"},
        }
        s["ca"].save(update_fields=["field_visibility"])

        client = _client_for(s["alice"])
        # ra_1 — alice is respondent. extended_result must be stripped.
        resp = client.get(f"/api/requirement-assessments/{s['ra_1'].id}/")
        assert resp.status_code == 200
        assert "extended_result" not in resp.json()

        # ra_3 — alice is auditor on this RA in the same CA. The same field
        # must surface here, proving the strip is per-RA, not per-CA.
        resp = client.get(f"/api/requirement-assessments/{s['ra_3'].id}/")
        assert resp.status_code == 200
        body = resp.json()
        assert "extended_result" in body
        assert body["viewer_role"] == "auditor"

    def test_answers_visibility_is_honoured(self, viewer_role_api_setup):
        """`answers` is in the visibility editor; flipping it to hidden must
        strip it from the GET payload (regression: the field's visibility was
        silently ignored across every edit surface before the audit fix)."""
        s = viewer_role_api_setup
        s["ca"].field_visibility = {
            "answers": {"auditor": "edit", "respondent": "hidden"},
        }
        s["ca"].save(update_fields=["field_visibility"])

        client = _client_for(s["alice"])
        # respondent on ra_1 — `answers` hidden.
        resp = client.get(f"/api/requirement-assessments/{s['ra_1'].id}/")
        assert resp.status_code == 200
        assert "answers" not in resp.json()

        # auditor on ra_3 — `answers` visible.
        resp = client.get(f"/api/requirement-assessments/{s['ra_3'].id}/")
        assert resp.status_code == 200
        assert "answers" in resp.json()

    def test_respondent_patch_of_extended_result_is_dropped(
        self, viewer_role_api_setup
    ):
        """Symmetric to the read strip: a respondent's PATCH of an
        AUDITOR_ONLY field must be silently dropped."""
        s = viewer_role_api_setup
        s["ca"].field_visibility = {
            "extended_result": {"auditor": "edit", "respondent": "hidden"},
        }
        s["ca"].save(update_fields=["field_visibility"])

        client = _client_for(s["alice"])
        before = s["ra_1"].extended_result  # None initially
        resp = client.patch(
            f"/api/requirement-assessments/{s['ra_1'].id}/",
            data={"extended_result": "minor_nonconformity"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        s["ra_1"].refresh_from_db()
        assert s["ra_1"].extended_result == before
