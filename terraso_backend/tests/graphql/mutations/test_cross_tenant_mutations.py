# Copyright © 2026 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

"""Cross-tenant mutation probes — security-audit dashboard.

For each authenticated mutation that takes a resource id, assert that an
unrelated user (not an owner, member, or manager of the targeted resource)
gets rejected.  The mutation base classes (BaseAuthenticatedMutation /
BaseWriteMutation / BaseDeleteMutation) only check is_authenticated; the
object-level check is the resolver's responsibility.  These tests verify
the object-level checks are present and effective.

NOTE on duplication: Several of these mutations also have cross-tenant
tests in their respective test_*.py files (e.g. updateGroup is also
tested in test_group_mutations.py).  This file is intentionally a
centralized audit dashboard — having the security-relevant probes
collected in one place makes the audit trail easier to grep, review,
and re-run as a security regression suite.  Do not "DRY up" by deleting
duplicates here; they earn their keep as audit artifacts.

Pattern:
1. Set up a resource owned by some user other than the test caller.
2. force_login as an unrelated user (the JWTAwareClient in the conftest
   auto-attaches a JWT on force_login).
3. Send the mutation targeting the resource.
4. Assert the mutation either rejects with an error payload or returns
   no successful payload, AND the resource state in the DB is unchanged.
"""

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.collaboration.models import Membership as CollaborationMembership
from apps.collaboration.models import MembershipList
from apps.core import group_collaboration_roles, landscape_collaboration_roles
from apps.core.models import Group, Landscape, SharedResource, User
from apps.project_management.models import Project, Site
from apps.shared_data.models import DataEntry
from apps.story_map.models import StoryMap

pytestmark = pytest.mark.django_db


def _has_mutation_error(response_body, mutation_name):
    """A mutation 'failed' if either there's a top-level errors array, or
    the mutation payload's `errors` field is set, or the mutation payload's
    primary result field is null."""
    if "errors" in response_body:
        return True
    payload = response_body.get("data", {}).get(mutation_name)
    if payload is None:
        return True
    if payload.get("errors"):
        return True
    return False


# --- Group mutations ---


def test_delete_group_cross_tenant_rejected(client):
    """User A (not a manager of group) cannot delete it."""
    owner = mixer.blend(User)
    group = mixer.blend(
        Group,
        membership_list=mixer.blend(
            MembershipList, membership_type=MembershipList.MEMBERSHIP_TYPE_CLOSED
        ),
    )
    group.add_manager(owner)

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation deleteGroup($input: GroupDeleteMutationInput!) "
        "{ deleteGroup(input: $input) { errors group { id } } }",
        variables={"input": {"id": str(group.id)}},
        client=client,
    )
    assert _has_mutation_error(response.json(), "deleteGroup")
    assert Group.objects.filter(id=group.id).exists()


def test_save_group_membership_cross_tenant_rejected(client):
    """User A (non-manager) cannot add anyone to user B's group."""
    owner = mixer.blend(User)
    group = mixer.blend(
        Group,
        membership_list=mixer.blend(
            MembershipList, membership_type=MembershipList.MEMBERSHIP_TYPE_CLOSED
        ),
    )
    group.add_manager(owner)

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation save($input: GroupMembershipSaveMutationInput!) "
        "{ saveGroupMembership(input: $input) { errors } }",
        variables={
            "input": {
                "userRole": group_collaboration_roles.ROLE_MANAGER,
                "userEmails": [attacker.email],
                "groupSlug": group.slug,
            }
        },
        client=client,
    )
    assert _has_mutation_error(response.json(), "saveGroupMembership")
    # attacker did NOT become a member
    assert not CollaborationMembership.objects.filter(
        user=attacker, membership_list=group.membership_list
    ).exists()


# --- Landscape mutations ---


def test_update_landscape_cross_tenant_rejected(client):
    landscape = mixer.blend(Landscape, name="Original Name")
    owner = mixer.blend(User)
    landscape.membership_list.save_membership(
        owner.email,
        landscape_collaboration_roles.ROLE_MANAGER,
        CollaborationMembership.APPROVED,
    )

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation update($input: LandscapeUpdateMutationInput!) "
        "{ updateLandscape(input: $input) { errors landscape { id name } } }",
        variables={"input": {"id": str(landscape.id), "name": "PWNED"}},
        client=client,
    )
    assert _has_mutation_error(response.json(), "updateLandscape")
    landscape.refresh_from_db()
    assert landscape.name == "Original Name"


def test_delete_landscape_cross_tenant_rejected(client):
    landscape = mixer.blend(Landscape)
    owner = mixer.blend(User)
    landscape.membership_list.save_membership(
        owner.email,
        landscape_collaboration_roles.ROLE_MANAGER,
        CollaborationMembership.APPROVED,
    )

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation delete($input: LandscapeDeleteMutationInput!) "
        "{ deleteLandscape(input: $input) { errors } }",
        variables={"input": {"id": str(landscape.id)}},
        client=client,
    )
    assert _has_mutation_error(response.json(), "deleteLandscape")
    assert Landscape.objects.filter(id=landscape.id).exists()


def test_save_landscape_membership_cross_tenant_rejected(client):
    """User A cannot self-promote into a landscape they don't manage."""
    landscape = mixer.blend(Landscape)
    owner = mixer.blend(User)
    landscape.membership_list.save_membership(
        owner.email,
        landscape_collaboration_roles.ROLE_MANAGER,
        CollaborationMembership.APPROVED,
    )

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation save($input: LandscapeMembershipSaveMutationInput!) "
        "{ saveLandscapeMembership(input: $input) { errors } }",
        variables={
            "input": {
                "userRole": landscape_collaboration_roles.ROLE_MANAGER,
                "userEmails": [attacker.email],
                "landscapeSlug": landscape.slug,
            }
        },
        client=client,
    )
    assert _has_mutation_error(response.json(), "saveLandscapeMembership")
    assert not CollaborationMembership.objects.filter(
        user=attacker, membership_list=landscape.membership_list
    ).exists()


# --- Site mutations ---


def test_update_site_cross_tenant_rejected(client):
    """User A cannot update someone else's unaffiliated site."""
    owner = mixer.blend(User)
    site = mixer.blend(Site, owner=owner, name="Original")

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation update($input: SiteUpdateMutationInput!) "
        "{ updateSite(input: $input) { errors site { id name } } }",
        variables={"input": {"id": str(site.id), "name": "PWNED"}},
        client=client,
    )
    assert _has_mutation_error(response.json(), "updateSite")
    site.refresh_from_db()
    assert site.name == "Original"


def test_delete_site_cross_tenant_rejected(client):
    owner = mixer.blend(User)
    site = mixer.blend(Site, owner=owner)

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation delete($input: SiteDeleteMutationInput!) "
        "{ deleteSite(input: $input) { errors } }",
        variables={"input": {"id": str(site.id)}},
        client=client,
    )
    assert _has_mutation_error(response.json(), "deleteSite")
    assert Site.objects.filter(id=site.id).exists()


def test_transfer_sites_cross_tenant_rejected(client):
    """User A cannot transfer someone else's sites into a project.
    transferSites doesn't error on permission failure — it returns the
    rejected sites in the `bad_permissions` field and leaves them
    unchanged in the DB."""
    owner = mixer.blend(User)
    site = mixer.blend(Site, owner=owner)
    target_project = mixer.blend(Project)
    target_project.add_manager(owner)

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation transfer($input: SiteTransferMutationInput!) "
        "{ transferSites(input: $input) { "
        "    updated { site { id } } badPermissions { id } errors "
        "} }",
        variables={
            "input": {
                "siteIds": [str(site.id)],
                "projectId": str(target_project.id),
            }
        },
        client=client,
    )
    body = response.json()
    payload = body["data"]["transferSites"]
    assert payload["updated"] == []
    assert any(p["id"] == str(site.id) for p in payload["badPermissions"])
    site.refresh_from_db()
    assert site.project_id is None  # site stays unaffiliated


# --- StoryMap mutations ---


def test_delete_story_map_cross_tenant_rejected(client):
    creator = mixer.blend(User)
    story_map = mixer.blend(StoryMap, created_by=creator, is_published=False)

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation delete($input: StoryMapDeleteMutationInput!) "
        "{ deleteStoryMap(input: $input) { errors } }",
        variables={"input": {"id": str(story_map.id)}},
        client=client,
    )
    assert _has_mutation_error(response.json(), "deleteStoryMap")
    assert StoryMap.objects.filter(id=story_map.id).exists()


# --- SharedResource mutations ---


def test_update_shared_resource_cross_tenant_rejected(client):
    """User A cannot change share-access on someone else's shared
    resource (e.g. flipping a private group's resource to share_access=ALL)."""
    owner = mixer.blend(User)
    target_group = mixer.blend(Group)
    target_group.membership_list.save_membership(
        owner.email,
        group_collaboration_roles.ROLE_MANAGER,
        CollaborationMembership.APPROVED,
    )
    resource = mixer.blend(
        SharedResource,
        target=target_group,
        source=mixer.blend(DataEntry, created_by=owner, size=100),
        share_access=SharedResource.SHARE_ACCESS_MEMBERS,
    )

    attacker = mixer.blend(User)
    client.force_login(attacker)
    response = graphql_query(
        "mutation update($input: SharedResourceUpdateMutationInput!) "
        "{ updateSharedResource(input: $input) { errors } }",
        variables={"input": {"id": str(resource.id), "shareAccess": "ALL"}},
        client=client,
    )
    assert _has_mutation_error(response.json(), "updateSharedResource")
    resource.refresh_from_db()
    assert resource.share_access == SharedResource.SHARE_ACCESS_MEMBERS
