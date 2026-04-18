"""API tests for the Swiss tournament mode."""

from fastapi.testclient import TestClient


def _create_options(client: TestClient, count: int) -> list[dict]:
    options = []
    for i in range(count):
        resp = client.post("/api/v1/options", json={"name": f"Option {i + 1}"})
        assert resp.status_code == 201
        options.append(resp.json())
    return options


class TestSwissEndpoints:
    def test_create_swiss_tournament_returns_defaults(self, client: TestClient) -> None:
        resp = client.post("/api/v1/tournaments", json={"name": "T", "mode": "swiss"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "swiss"
        assert data["config"]["allow_draws"] is True
        assert data["config"]["total_rounds"] is None
        assert data["config"]["voter_labels"] == ["default"]

    def test_activate_swiss_populates_state(self, client: TestClient) -> None:
        options = _create_options(client, 4)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "swiss"})
        tid = create.json()["id"]
        client.put(
            f"/api/v1/tournaments/{tid}",
            json={
                "version": 1,
                "selected_option_ids": [o["id"] for o in options],
                "config": {"shuffle_seed": False, "voter_labels": ["default"]},
            },
        )
        resp = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        assert resp.status_code == 200
        t = resp.json()
        assert t["status"] == "active"
        assert t["state"]["total_rounds"] == 2
        assert len(t["state"]["rounds"]) == 1

    def test_vote_context_is_swiss_matchup(self, client: TestClient) -> None:
        tid, _ = self._create_and_activate(client, 4)
        resp = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"})
        ctx = resp.json()
        assert ctx["type"] == "swiss_matchup"
        assert ctx["round"] == 1
        assert ctx["total_rounds"] == 2
        assert ctx["allow_draws"] is True
        assert len(ctx["standings"]) == 4

    def test_submit_vote_advances_state(self, client: TestClient) -> None:
        tid, version = self._create_and_activate(client, 4)
        ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={
                "version": version,
                "voter_label": "default",
                "payload": {"matchup_id": ctx["matchup_id"], "result": "a_wins"},
            },
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["state"]["standings"][ctx["entry_a"]["id"]]["points"] == 1.0

    def test_draw_rejected_when_disabled(self, client: TestClient) -> None:
        tid, version = self._create_and_activate(client, 4, allow_draws=False)
        ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={
                "version": version,
                "voter_label": "default",
                "payload": {"matchup_id": ctx["matchup_id"], "result": "draw"},
            },
        )
        assert resp.status_code == 422

    def test_full_swiss_flow_completes(self, client: TestClient) -> None:
        tid, version = self._create_and_activate(client, 4)
        while True:
            ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
            if ctx["type"] == "completed":
                break
            resp = client.post(
                f"/api/v1/tournaments/{tid}/vote",
                json={
                    "version": version,
                    "voter_label": "default",
                    "payload": {"matchup_id": ctx["matchup_id"], "result": "a_wins"},
                },
            )
            assert resp.status_code == 200
            version = resp.json()["version"]
        result = client.get(f"/api/v1/tournaments/{tid}/result").json()
        assert len(result["ranking"]) == 4
        assert len(result["winner_ids"]) >= 1

    def _create_and_activate(self, client: TestClient, n: int, *, allow_draws: bool = True) -> tuple[str, int]:
        options = _create_options(client, n)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "swiss"})
        tid = create.json()["id"]
        client.put(
            f"/api/v1/tournaments/{tid}",
            json={
                "version": 1,
                "selected_option_ids": [o["id"] for o in options],
                "config": {"shuffle_seed": False, "allow_draws": allow_draws, "voter_labels": ["default"]},
            },
        )
        act = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        return tid, act.json()["version"]
