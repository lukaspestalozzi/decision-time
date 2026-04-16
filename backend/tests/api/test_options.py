"""API tests for option and tag endpoints."""

import uuid

from fastapi.testclient import TestClient


class TestOptionEndpoints:
    def test_create_option_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/options", json={"name": "Luna"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Luna"
        assert "id" in data

    def test_create_option_with_tags(self, client: TestClient) -> None:
        resp = client.post("/api/v1/options", json={"name": "Luna", "tags": ["italian", "short"]})
        assert resp.status_code == 201
        assert resp.json()["tags"] == ["italian", "short"]

    def test_create_option_blank_name_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/options", json={"name": "   "})
        assert resp.status_code == 422

    def test_get_option_returns_created(self, client: TestClient) -> None:
        create_resp = client.post("/api/v1/options", json={"name": "Mira"})
        option_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/options/{option_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Mira"

    def test_get_option_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/options/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_list_options_returns_all(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "A"})
        client.post("/api/v1/options", json={"name": "B"})
        resp = client.get("/api/v1/options")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_options_filter_by_q(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "Luna"})
        client.post("/api/v1/options", json={"name": "Mira"})
        resp = client.get("/api/v1/options", params={"q": "lun"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Luna"

    def test_list_options_filter_by_tags_all(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "A", "tags": ["italian", "short"]})
        client.post("/api/v1/options", json={"name": "B", "tags": ["italian"]})
        resp = client.get("/api/v1/options", params={"tags_all": "italian,short"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "A"

    def test_list_options_filter_by_tags_any(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "A", "tags": ["italian"]})
        client.post("/api/v1/options", json={"name": "B", "tags": ["german"]})
        client.post("/api/v1/options", json={"name": "C", "tags": ["french"]})
        resp = client.get("/api/v1/options", params={"tags_any": "italian,german"})
        assert len(resp.json()) == 2

    def test_update_option_partial(self, client: TestClient) -> None:
        create_resp = client.post("/api/v1/options", json={"name": "Old", "description": "Keep"})
        option_id = create_resp.json()["id"]
        resp = client.put(f"/api/v1/options/{option_id}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"
        assert resp.json()["description"] == "Keep"

    def test_delete_option_returns_204(self, client: TestClient) -> None:
        create_resp = client.post("/api/v1/options", json={"name": "ToDelete"})
        option_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/options/{option_id}")
        assert resp.status_code == 204
        # Confirm deleted
        resp = client.get(f"/api/v1/options/{option_id}")
        assert resp.status_code == 404

    def test_delete_option_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.delete(f"/api/v1/options/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestBulkOperations:
    def test_bulk_create_returns_created_and_updated_envelope(self, client: TestClient) -> None:
        resp = client.post("/api/v1/options/bulk", json={"names": ["A", "B", "C"]})
        assert resp.status_code == 201
        body = resp.json()
        assert list(body.keys()) == ["created", "updated"]
        assert len(body["created"]) == 3
        assert body["updated"] == []

    def test_bulk_create_merges_tags_into_existing(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "Existing", "tags": ["old"]})
        resp = client.post(
            "/api/v1/options/bulk",
            json={"names": ["Existing", "New"], "tags": ["new-tag"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["created"]) == 1
        assert body["created"][0]["name"] == "New"
        assert "new-tag" in body["created"][0]["tags"]
        assert len(body["updated"]) == 1
        assert body["updated"][0]["name"] == "Existing"
        # Union: old tag preserved, new tag added, no duplicates.
        assert sorted(body["updated"][0]["tags"]) == ["new-tag", "old"]

    def test_bulk_create_applies_tags(self, client: TestClient) -> None:
        resp = client.post("/api/v1/options/bulk", json={"names": ["A", "B"], "tags": ["baby-name"]})
        assert resp.status_code == 201
        for opt in resp.json()["created"]:
            assert "baby-name" in opt["tags"]

    def test_bulk_create_does_not_duplicate_existing_tag(self, client: TestClient) -> None:
        # Existing option already has the supplied tag → no update recorded.
        seeded = client.post("/api/v1/options", json={"name": "Luna", "tags": ["pet"]}).json()
        resp = client.post("/api/v1/options/bulk", json={"names": ["Luna"], "tags": ["pet"]})
        assert resp.status_code == 201
        assert resp.json() == {"created": [], "updated": []}
        # And the tag list was not duplicated on the stored record.
        stored = client.get(f"/api/v1/options/{seeded['id']}").json()
        assert stored["tags"] == ["pet"]

    def test_bulk_create_merge_with_no_tags_is_noop_on_existing(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "Existing"})
        resp = client.post("/api/v1/options/bulk", json={"names": ["Existing"]})
        assert resp.status_code == 201
        assert resp.json() == {"created": [], "updated": []}

    def test_bulk_update_tags_adds_and_removes(self, client: TestClient) -> None:
        a = client.post("/api/v1/options", json={"name": "A", "tags": ["old"]}).json()
        b = client.post("/api/v1/options", json={"name": "B", "tags": ["old"]}).json()
        resp = client.patch(
            "/api/v1/options/bulk",
            json={"option_ids": [a["id"], b["id"]], "add_tags": ["new"], "remove_tags": ["old"]},
        )
        assert resp.status_code == 200
        for opt in resp.json():
            assert "new" in opt["tags"]
            assert "old" not in opt["tags"]


class TestTagEndpoints:
    def test_list_tags_returns_sorted_unique(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "A", "tags": ["zebra", "apple"]})
        client.post("/api/v1/options", json={"name": "B", "tags": ["apple", "mango"]})
        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        assert resp.json() == ["apple", "mango", "zebra"]

    def test_list_tags_empty_when_no_options(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        assert resp.json() == []
