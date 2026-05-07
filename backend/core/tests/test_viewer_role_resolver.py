"""Tests for the per-RA viewer-role resolver.

The resolver determines whether a user is `auditor` or `respondent` on a given
RequirementAssessment, based on Actor membership in the RA's RequirementAssignments.
Folder roles (analyst / auditee / third-party respondent / etc.) do NOT influence
the resolution — only Actor-on-Assignment membership.
"""

import pytest
from django.contrib.auth import get_user_model

from core.models import (
    Actor,
    ComplianceAssessment,
    Framework,
    Perimeter,
    RequirementAssessment,
    RequirementAssignment,
    RequirementNode,
)
from core.utils import get_respondent_ra_ids, resolve_ra_viewer_role
from iam.models import Folder

User = get_user_model()


@pytest.fixture
def viewer_role_setup():
    """Build a minimal CA with three RAs and two RequirementAssignments.

    CA (folder=domain, framework=fw)
      ├── ra_1 ──┐
      ├── ra_2 ──┤── Assignment A1 (actor: alice)
      └── ra_3 ───── Assignment A2 (actor: bob)
    """
    root = Folder.get_root_folder()
    domain = Folder.objects.create(parent_folder=root, name="vrr-domain")
    perimeter = Perimeter.objects.create(name="vrr-perimeter", folder=domain)

    fw = Framework.objects.create(name="VRR FW", urn="urn:test:vrr-fw", folder=root)
    nodes = [
        RequirementNode.objects.create(
            name=f"Req {i}",
            urn=f"urn:test:vrr-req-{i}",
            ref_id=str(i),
            framework=fw,
            assessable=True,
            folder=root,
        )
        for i in (1, 2, 3)
    ]

    ca = ComplianceAssessment.objects.create(
        name="VRR CA", framework=fw, folder=domain, perimeter=perimeter
    )
    ras = [
        RequirementAssessment.objects.create(
            compliance_assessment=ca, requirement=node, folder=domain
        )
        for node in nodes
    ]

    alice = User.objects.create_user(email="alice-vrr@example.com", password="pw")
    bob = User.objects.create_user(email="bob-vrr@example.com", password="pw")
    eve = User.objects.create_user(email="eve-vrr@example.com", password="pw")

    a1 = RequirementAssignment.objects.create(compliance_assessment=ca)
    a1.actor.add(alice.actor)
    a1.requirement_assessments.add(ras[0], ras[1])

    a2 = RequirementAssignment.objects.create(compliance_assessment=ca)
    a2.actor.add(bob.actor)
    a2.requirement_assessments.add(ras[2])

    return {
        "ca": ca,
        "ra_1": ras[0],
        "ra_2": ras[1],
        "ra_3": ras[2],
        "alice": alice,
        "bob": bob,
        "eve": eve,
    }


@pytest.mark.django_db
class TestResolveRaViewerRole:
    """Per-RA role: respondent iff user is Actor on any assignment covering the RA."""

    def test_actor_on_covering_assignment_is_respondent(self, viewer_role_setup):
        s = viewer_role_setup
        assert resolve_ra_viewer_role(s["alice"], s["ra_1"]) == "respondent"
        assert resolve_ra_viewer_role(s["alice"], s["ra_2"]) == "respondent"

    def test_actor_only_on_other_assignment_is_auditor(self, viewer_role_setup):
        # alice covers ra_1, ra_2 but NOT ra_3.
        s = viewer_role_setup
        assert resolve_ra_viewer_role(s["alice"], s["ra_3"]) == "auditor"
        # bob covers only ra_3.
        assert resolve_ra_viewer_role(s["bob"], s["ra_1"]) == "auditor"
        assert resolve_ra_viewer_role(s["bob"], s["ra_3"]) == "respondent"

    def test_no_actor_membership_anywhere_is_auditor(self, viewer_role_setup):
        s = viewer_role_setup
        for ra in (s["ra_1"], s["ra_2"], s["ra_3"]):
            assert resolve_ra_viewer_role(s["eve"], ra) == "auditor"

    def test_user_without_any_actor_record_is_auditor(self, db):
        """A user whose Actor was deleted resolves to 'auditor' everywhere."""
        u = User.objects.create_user(email="no-actor@example.com", password="pw")
        Actor.objects.filter(user=u).delete()
        # build a throwaway RA
        root = Folder.get_root_folder()
        domain = Folder.objects.create(parent_folder=root, name="no-actor-domain")
        perimeter = Perimeter.objects.create(name="no-actor-perim", folder=domain)
        fw = Framework.objects.create(name="NA FW", urn="urn:test:na-fw", folder=root)
        node = RequirementNode.objects.create(
            name="NA Req",
            urn="urn:test:na-req",
            framework=fw,
            assessable=True,
            folder=root,
        )
        ca = ComplianceAssessment.objects.create(
            name="NA CA", framework=fw, folder=domain, perimeter=perimeter
        )
        ra = RequirementAssessment.objects.create(
            compliance_assessment=ca, requirement=node, folder=domain
        )
        assert resolve_ra_viewer_role(u, ra) == "auditor"


@pytest.mark.django_db
class TestGetRespondentRaIds:
    """Set-of-RA-ids variant used by list endpoints to avoid N+1 queries."""

    def test_returns_only_assigned_ra_ids(self, viewer_role_setup):
        s = viewer_role_setup
        assert get_respondent_ra_ids(s["alice"], s["ca"]) == {
            s["ra_1"].id,
            s["ra_2"].id,
        }
        assert get_respondent_ra_ids(s["bob"], s["ca"]) == {s["ra_3"].id}

    def test_empty_set_for_unassigned_user(self, viewer_role_setup):
        s = viewer_role_setup
        assert get_respondent_ra_ids(s["eve"], s["ca"]) == set()

    def test_other_ca_assignments_do_not_leak(self, viewer_role_setup):
        """An assignment in a *different* CA must not pollute the set."""
        s = viewer_role_setup
        # Build a second CA in the same domain with its own assignment for alice
        other_fw = Framework.objects.create(
            name="Other FW",
            urn="urn:test:vrr-other-fw",
            folder=Folder.get_root_folder(),
        )
        other_node = RequirementNode.objects.create(
            name="Other Req",
            urn="urn:test:vrr-other-req",
            framework=other_fw,
            assessable=True,
            folder=Folder.get_root_folder(),
        )
        other_ca = ComplianceAssessment.objects.create(
            name="Other CA",
            framework=other_fw,
            folder=s["ca"].folder,
            perimeter=Perimeter.objects.first(),
        )
        other_ra = RequirementAssessment.objects.create(
            compliance_assessment=other_ca,
            requirement=other_node,
            folder=s["ca"].folder,
        )
        other_assignment = RequirementAssignment.objects.create(
            compliance_assessment=other_ca
        )
        other_assignment.actor.add(s["alice"].actor)
        other_assignment.requirement_assessments.add(other_ra)

        # The CA-scoped query must still only return ra_1, ra_2 for alice in s["ca"].
        assert get_respondent_ra_ids(s["alice"], s["ca"]) == {
            s["ra_1"].id,
            s["ra_2"].id,
        }


@pytest.mark.django_db
class TestMixedRolesInSameCa:
    """The headline scenario the refactor is built around."""

    def test_user_can_be_respondent_and_auditor_in_same_ca(self, viewer_role_setup):
        s = viewer_role_setup
        # Alice: respondent on ra_1, ra_2; auditor on ra_3 — all in the same CA.
        roles = {
            ra.id: resolve_ra_viewer_role(s["alice"], ra)
            for ra in (s["ra_1"], s["ra_2"], s["ra_3"])
        }
        assert roles == {
            s["ra_1"].id: "respondent",
            s["ra_2"].id: "respondent",
            s["ra_3"].id: "auditor",
        }

    def test_team_actor_membership_propagates(self, viewer_role_setup):
        """A user who is a member of a Team whose Actor is on an Assignment is a respondent."""
        from core.models import Team

        s = viewer_role_setup
        leader = User.objects.create_user(
            email="team-lead-vrr@example.com", password="pw"
        )
        member = User.objects.create_user(
            email="team-member-vrr@example.com", password="pw"
        )
        team = Team.objects.create(name="VRR Team", leader=leader)
        team.members.add(member)

        a3 = RequirementAssignment.objects.create(compliance_assessment=s["ca"])
        a3.actor.add(team.actor)
        a3.requirement_assessments.add(s["ra_3"])

        # Both leader and member should resolve as respondent on ra_3 via the team's Actor.
        assert resolve_ra_viewer_role(leader, s["ra_3"]) == "respondent"
        assert resolve_ra_viewer_role(member, s["ra_3"]) == "respondent"
        # And still auditor on ra_1 (no team or personal actor on a1).
        assert resolve_ra_viewer_role(leader, s["ra_1"]) == "auditor"
        assert resolve_ra_viewer_role(member, s["ra_1"]) == "auditor"
