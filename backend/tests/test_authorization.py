"""Org isolation and role checks.

These are the tests worth having. A bug here does not crash anything — it
quietly shows one customer another customer's board, and nobody notices until
they do.
"""

import pytest


@pytest.fixture
def outsider(make_user):
    """A perfectly valid user who belongs to no organization."""
    return make_user("outsider@example.com")


def test_outsider_cannot_read_a_board(client, workspace, outsider):
    response = client.get(f"/boards/{workspace.board_id}", headers=outsider.headers)
    assert response.status_code == 403


def test_outsider_cannot_list_boards_in_an_org(client, workspace, outsider):
    response = client.get(f"/orgs/{workspace.org_id}/boards", headers=outsider.headers)
    assert response.status_code == 403


def test_outsider_cannot_create_a_board(client, workspace, outsider):
    response = client.post(
        f"/orgs/{workspace.org_id}/boards", json={"title": "Mine now"}, headers=outsider.headers
    )
    assert response.status_code == 403


def test_outsider_cannot_read_an_issue_or_its_comments(client, workspace, outsider):
    assert client.get(f"/issues/{workspace.issue_id}", headers=outsider.headers).status_code == 403
    assert (
        client.get(
            f"/issues/{workspace.issue_id}/comments", headers=outsider.headers
        ).status_code
        == 403
    )


def test_outsider_cannot_delete_someone_elses_issue(client, workspace, outsider):
    response = client.delete(f"/issues/{workspace.issue_id}", headers=outsider.headers)
    assert response.status_code == 403
    # and it is still there
    assert client.get(
        f"/issues/{workspace.issue_id}", headers=workspace.owner.headers
    ).status_code == 200


def test_listing_orgs_only_returns_your_own(client, workspace, outsider):
    assert client.get("/orgs", headers=outsider.headers).json() == []
    mine = client.get("/orgs", headers=workspace.owner.headers).json()
    assert [o["id"] for o in mine] == [workspace.org_id]


def test_org_creator_becomes_admin(client, workspace):
    orgs = client.get("/orgs", headers=workspace.owner.headers).json()
    assert orgs[0]["role"] == "admin"


def test_plain_member_can_use_the_board_but_not_administer_it(client, workspace, make_user):
    member = make_user("member@example.com")
    h_owner = workspace.owner.headers

    added = client.post(
        f"/orgs/{workspace.org_id}/members",
        json={"email": member.email, "role": "member"},
        headers=h_owner,
    )
    assert added.status_code == 201

    # can read the board
    assert client.get(f"/boards/{workspace.board_id}", headers=member.headers).status_code == 200
    # cannot invite anyone else
    third = make_user("third@example.com")
    assert (
        client.post(
            f"/orgs/{workspace.org_id}/members",
            json={"email": third.email},
            headers=member.headers,
        ).status_code
        == 403
    )
    # cannot delete the board — that is an admin action
    assert (
        client.delete(f"/boards/{workspace.board_id}", headers=member.headers).status_code == 403
    )


def test_adding_an_unknown_email_is_404_and_adding_twice_is_409(client, workspace, make_user):
    h = workspace.owner.headers
    member = make_user("member@example.com")

    assert (
        client.post(
            f"/orgs/{workspace.org_id}/members",
            json={"email": "ghost@example.com"},
            headers=h,
        ).status_code
        == 404
    )

    first = client.post(
        f"/orgs/{workspace.org_id}/members", json={"email": member.email}, headers=h
    )
    second = client.post(
        f"/orgs/{workspace.org_id}/members", json={"email": member.email}, headers=h
    )
    assert first.status_code == 201
    assert second.status_code == 409


def test_missing_org_is_404_not_403(client, make_user):
    user = make_user("ada@example.com")
    response = client.get("/orgs/99999/members", headers=user.headers)
    assert response.status_code == 404
