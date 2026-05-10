"""API tests for the new sort_by/sort_order params on GET /options."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.repositories.options import OptionRepository
from app.schemas.option import Option


@pytest.fixture
def option_repo(data_dir: Path) -> OptionRepository:
    return OptionRepository(data_dir)


def _seed(option_repo: OptionRepository) -> dict[str, str]:
    """Seed three options with rigged Elo ratings via direct repo access."""
    a = option_repo.create(Option(name="Apple"))
    b = option_repo.create(Option(name="Banana"))
    c = option_repo.create(Option(name="Cherry"))
    option_repo.bump_elo_rating(a.id, 1200.0)
    option_repo.bump_elo_rating(b.id, 800.0)
    option_repo.bump_elo_rating(c.id, 1500.0)
    return {"a": str(a.id), "b": str(b.id), "c": str(c.id)}


class TestOptionsSort:
    def test_sort_by_elo_rating_desc(self, client: TestClient, option_repo: OptionRepository) -> None:
        ids = _seed(option_repo)
        resp = client.get("/api/v1/options", params={"sort_by": "elo_rating", "sort_order": "desc"})
        assert resp.status_code == 200
        result_ids = [o["id"] for o in resp.json()]
        # c (1500) > a (1200) > b (800)
        assert result_ids == [ids["c"], ids["a"], ids["b"]]

    def test_sort_by_elo_rating_asc(self, client: TestClient, option_repo: OptionRepository) -> None:
        ids = _seed(option_repo)
        resp = client.get("/api/v1/options", params={"sort_by": "elo_rating", "sort_order": "asc"})
        assert resp.status_code == 200
        assert [o["id"] for o in resp.json()] == [ids["b"], ids["a"], ids["c"]]

    def test_sort_by_name_asc(self, client: TestClient, option_repo: OptionRepository) -> None:
        ids = _seed(option_repo)
        resp = client.get("/api/v1/options", params={"sort_by": "name", "sort_order": "asc"})
        assert resp.status_code == 200
        assert [o["id"] for o in resp.json()] == [ids["a"], ids["b"], ids["c"]]

    def test_default_sort_returns_all_three(self, client: TestClient, option_repo: OptionRepository) -> None:
        # Default sort is created_at desc, but within-microsecond ties are non-deterministic;
        # just assert all three options are returned.
        ids = _seed(option_repo)
        resp = client.get("/api/v1/options")
        assert resp.status_code == 200
        assert sorted(o["id"] for o in resp.json()) == sorted(ids.values())

    def test_invalid_sort_by_returns_422(self, client: TestClient) -> None:
        resp = client.get("/api/v1/options", params={"sort_by": "popularity"})
        assert resp.status_code == 422
        assert "sort_by" in resp.json()["error"]["message"]

    def test_invalid_sort_order_returns_422(self, client: TestClient) -> None:
        resp = client.get("/api/v1/options", params={"sort_order": "random"})
        assert resp.status_code == 422
        assert "sort_order" in resp.json()["error"]["message"]

    def test_response_includes_elo_rating_field(self, client: TestClient) -> None:
        client.post("/api/v1/options", json={"name": "Newbie"})
        resp = client.get("/api/v1/options")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["elo_rating"] == 1000.0
