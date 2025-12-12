# Copyright © 2021-2025 Technology Matters
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

from django.conf import settings

from apps.graphql.schema.schema import schema


def fetch_project_list(user_id, request, page_size=settings.EXPORT_PAGE_SIZE):
    """Fetch list of project IDs for a given user."""
    project_ids = []
    after = None
    gql = """
    query Projects($member: ID!, $first: Int!, $after: String) {
      projects(member: $member, first: $first, after: $after) {
        totalCount
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            id
          }
        }
      }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"member": user_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["projects"]
        batch = [e["node"]["id"] for e in conn["edges"]]
        project_ids.extend(batch)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return project_ids


def fetch_all_sites(project_id, request, page_size=settings.EXPORT_PAGE_SIZE):
    """Fetch set of site IDs for a given project."""
    site_ids = set()
    after = None
    gql = """
    query ProjectWithSites($id: ID!, $first: Int!, $after: String) {
        sites(project: $id, first: $first, after: $after) {
            pageInfo { hasNextPage endCursor }
            edges {
                cursor
                node {
                    id
                }
            }
        }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"id": project_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["sites"]
        batch = [e["node"]["id"] for e in conn["edges"]]
        site_ids.update(batch)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return site_ids


def fetch_user_owned_sites(user_id, request, page_size=settings.EXPORT_PAGE_SIZE):
    """Fetch set of site IDs owned by a specific user (not in any project)."""
    site_ids = set()
    after = None
    gql = """
    query UserOwnedSites($owner: ID!, $first: Int!, $after: String) {
        sites(owner: $owner, first: $first, after: $after) {
            pageInfo { hasNextPage endCursor }
            edges {
                cursor
                node {
                    id
                }
            }
        }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"owner": user_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["sites"]
        batch = [e["node"]["id"] for e in conn["edges"]]
        site_ids.update(batch)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return site_ids
