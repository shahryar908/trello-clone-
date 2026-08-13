"""Board behaviour: ordering, the aggregate payload, moves, and cascade deletes."""


def test_sections_and_issues_get_increasing_positions(client, workspace):
    h = workspace.owner.headers

    second = client.post(
        f"/boards/{workspace.board_id}/sections", json={"title": "Doing"}, headers=h
    ).json()
    first_position = client.get(f"/boards/{workspace.board_id}", headers=h).json()["sections"][0][
        "position"
    ]
    assert second["position"] > first_position

    extra = client.post(
        f"/sections/{workspace.section_id}/issues", json={"title": "Second"}, headers=h
    ).json()
    assert extra["position"] > 1


def test_board_detail_nests_issues_under_their_section(client, workspace):
    h = workspace.owner.headers
    detail = client.get(f"/boards/{workspace.board_id}", headers=h).json()

    assert detail["title"] == "Roadmap"
    assert len(detail["sections"]) == 1
    section = detail["sections"][0]
    assert section["id"] == workspace.section_id
    assert [i["id"] for i in section["issues"]] == [workspace.issue_id]
    assert section["issues"][0]["label_ids"] == []


def test_issue_carries_the_board_id_of_its_section(client, workspace):
    # board_id on Issue is denormalized, so it can drift from the section's.
    # The authorization checks read it, which is why it matters.
    issue = client.get(f"/issues/{workspace.issue_id}", headers=workspace.owner.headers).json()
    assert issue["board_id"] == workspace.board_id
    assert issue["section_id"] == workspace.section_id


def test_moving_an_issue_between_sections_of_the_same_board(client, workspace):
    h = workspace.owner.headers
    target = client.post(
        f"/boards/{workspace.board_id}/sections", json={"title": "Done"}, headers=h
    ).json()

    moved = client.patch(
        f"/issues/{workspace.issue_id}/move",
        json={"section_id": target["id"], "position": 1.5},
        headers=h,
    )
    assert moved.status_code == 200
    assert moved.json()["section_id"] == target["id"]
    assert moved.json()["position"] == 1.5


def test_moving_an_issue_to_another_board_is_rejected(client, workspace):
    h = workspace.owner.headers
    other_board = client.post(
        f"/orgs/{workspace.org_id}/boards", json={"title": "Other"}, headers=h
    ).json()
    other_section = client.post(
        f"/boards/{other_board['id']}/sections", json={"title": "Elsewhere"}, headers=h
    ).json()

    response = client.patch(
        f"/issues/{workspace.issue_id}/move",
        json={"section_id": other_section["id"], "position": 1},
        headers=h,
    )
    assert response.status_code == 400


def test_moving_to_a_missing_section_is_404(client, workspace):
    response = client.patch(
        f"/issues/{workspace.issue_id}/move",
        json={"section_id": 99999, "position": 1},
        headers=workspace.owner.headers,
    )
    assert response.status_code == 404


def test_deleting_a_section_takes_its_issues_with_it(client, workspace):
    h = workspace.owner.headers

    assert client.delete(f"/sections/{workspace.section_id}", headers=h).status_code == 204
    # the issue must not survive as an orphan pointing at a section that is gone
    assert client.get(f"/issues/{workspace.issue_id}", headers=h).status_code == 404


def test_deleting_a_board_takes_everything_below_it(client, workspace):
    h = workspace.owner.headers

    assert client.delete(f"/boards/{workspace.board_id}", headers=h).status_code == 204
    assert client.get(f"/boards/{workspace.board_id}", headers=h).status_code == 404
    assert client.get(f"/issues/{workspace.issue_id}", headers=h).status_code == 404
    assert client.get(f"/orgs/{workspace.org_id}/boards", headers=h).json() == []


def test_renaming_a_board_bumps_updated_at(client, workspace):
    h = workspace.owner.headers
    before = client.get(f"/orgs/{workspace.org_id}/boards", headers=h).json()[0]

    renamed = client.patch(
        f"/boards/{workspace.board_id}", json={"title": "Renamed"}, headers=h
    ).json()

    assert renamed["title"] == "Renamed"
    assert renamed["updated_at"] >= before["updated_at"]
