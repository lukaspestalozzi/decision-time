"""API tests for tournament endpoints + full bracket flow test."""

from fastapi.testclient import TestClient


def _create_options(client: TestClient, count: int) -> list[dict]:
    """Helper: create N options and return their JSON dicts."""
    options = []
    for i in range(count):
        resp = client.post("/api/v1/options", json={"name": f"Option {i + 1}"})
        assert resp.status_code == 201
        options.append(resp.json())
    return options


class TestTournamentCRUD:
    def test_create_tournament_returns_201_with_defaults(self, client: TestClient) -> None:
        resp = client.post("/api/v1/tournaments", json={"name": "Test", "mode": "bracket"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test"
        assert data["mode"] == "bracket"
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert data["config"]["shuffle_seed"] is True

    def test_create_tournament_requires_name_and_mode(self, client: TestClient) -> None:
        resp = client.post("/api/v1/tournaments", json={"name": "Test"})
        assert resp.status_code == 422

    def test_get_tournament_returns_created(self, client: TestClient) -> None:
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        resp = client.get(f"/api/v1/tournaments/{tid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "T"

    def test_list_tournaments_filter_by_status(self, client: TestClient) -> None:
        client.post("/api/v1/tournaments", json={"name": "A", "mode": "bracket"})
        client.post("/api/v1/tournaments", json={"name": "B", "mode": "bracket"})
        resp = client.get("/api/v1/tournaments", params={"status": "draft"})
        assert len(resp.json()) == 2

    def test_update_tournament_draft_only(self, client: TestClient) -> None:
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        resp = client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["version"] == 2

    def test_update_tournament_stale_version_returns_409(self, client: TestClient) -> None:
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "name": "V2"})
        resp = client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "name": "Stale"})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONFLICT"

    def test_delete_tournament_returns_204(self, client: TestClient) -> None:
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        resp = client.delete(f"/api/v1/tournaments/{tid}")
        assert resp.status_code == 204


class TestTournamentLifecycle:
    def test_activate_requires_minimum_2_options(self, client: TestClient) -> None:
        options = _create_options(client, 1)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "selected_option_ids": [options[0]["id"]]})
        resp = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        assert resp.status_code == 422
        assert "at least 2" in resp.json()["error"]["message"]

    def test_activate_snapshots_options_into_entries(self, client: TestClient) -> None:
        options = _create_options(client, 3)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "selected_option_ids": [o["id"] for o in options]})
        resp = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert len(data["entries"]) == 3

    def test_activate_ignores_deleted_options(self, client: TestClient) -> None:
        options = _create_options(client, 3)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "selected_option_ids": [o["id"] for o in options]})
        # Delete one option
        client.delete(f"/api/v1/options/{options[0]['id']}")
        resp = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) == 2

    def test_cancel_from_draft(self, client: TestClient) -> None:
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        resp = client.post(f"/api/v1/tournaments/{tid}/cancel", json={"version": 1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_from_active(self, client: TestClient) -> None:
        options = _create_options(client, 2)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "selected_option_ids": [o["id"] for o in options]})
        client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        resp = client.post(f"/api/v1/tournaments/{tid}/cancel", json={"version": 3})
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_clone_creates_new_draft(self, client: TestClient) -> None:
        options = _create_options(client, 2)
        create = client.post("/api/v1/tournaments", json={"name": "Original", "mode": "bracket"})
        tid = create.json()["id"]
        client.put(f"/api/v1/tournaments/{tid}", json={"version": 1, "selected_option_ids": [o["id"] for o in options]})
        resp = client.post(f"/api/v1/tournaments/{tid}/clone")
        assert resp.status_code == 201
        clone = resp.json()
        assert clone["name"] == "Original (copy)"
        assert clone["status"] == "draft"
        assert clone["id"] != tid
        assert len(clone["selected_option_ids"]) == 2


class TestTournamentVoting:
    def _setup_active_bracket(self, client: TestClient, num_options: int = 4) -> tuple[str, int]:
        """Helper: create options, tournament, activate. Returns (tournament_id, version)."""
        options = _create_options(client, num_options)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        client.put(
            f"/api/v1/tournaments/{tid}",
            json={
                "version": 1,
                "selected_option_ids": [o["id"] for o in options],
                "config": {"shuffle_seed": False},
            },
        )
        resp = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        return tid, resp.json()["version"]

    def test_vote_context_returns_bracket_matchup(self, client: TestClient) -> None:
        tid, _ = self._setup_active_bracket(client)
        resp = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"})
        assert resp.status_code == 200
        ctx = resp.json()
        assert ctx["type"] == "bracket_matchup"
        assert "matchup_id" in ctx
        assert ctx["round"] == 1

    def test_submit_vote_updates_state(self, client: TestClient) -> None:
        tid, version = self._setup_active_bracket(client)
        ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={
                "version": version,
                "voter_label": "default",
                "payload": {"matchup_id": ctx["matchup_id"], "winner_entry_id": ctx["entry_a"]["id"]},
            },
        )
        assert resp.status_code == 200
        assert len(resp.json()["votes"]) == 1

    def test_submit_vote_stale_version_returns_409(self, client: TestClient) -> None:
        tid, version = self._setup_active_bracket(client)
        ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
        # Vote successfully
        client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={
                "version": version,
                "voter_label": "default",
                "payload": {"matchup_id": ctx["matchup_id"], "winner_entry_id": ctx["entry_a"]["id"]},
            },
        )
        # Try again with stale version
        ctx2 = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={
                "version": version,  # stale
                "voter_label": "default",
                "payload": {"matchup_id": ctx2["matchup_id"], "winner_entry_id": ctx2["entry_a"]["id"]},
            },
        )
        assert resp.status_code == 409

    def test_vote_on_draft_returns_409(self, client: TestClient) -> None:
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote", json={"version": 1, "voter_label": "default", "payload": {}}
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"

    def test_get_result_before_complete_returns_409(self, client: TestClient) -> None:
        tid, _ = self._setup_active_bracket(client)
        resp = client.get(f"/api/v1/tournaments/{tid}/result")
        assert resp.status_code == 409

    def test_get_state_returns_engine_state(self, client: TestClient) -> None:
        tid, _ = self._setup_active_bracket(client)
        resp = client.get(f"/api/v1/tournaments/{tid}/state")
        assert resp.status_code == 200
        state = resp.json()
        assert "rounds" in state
        assert "current_round" in state


class TestFullBracketFlow:
    def test_full_bracket_flow_4_options(self, client: TestClient) -> None:
        """Full flow: create options → create tournament → add options → activate → vote all → verify result."""
        # Step 1: Create 4 options
        options = _create_options(client, 4)
        option_ids = [o["id"] for o in options]

        # Step 2: Create a bracket tournament
        resp = client.post("/api/v1/tournaments", json={"name": "Test Bracket", "mode": "bracket"})
        assert resp.status_code == 201
        tournament = resp.json()
        tid = tournament["id"]
        assert tournament["status"] == "draft"
        assert tournament["version"] == 1

        # Step 3: Add options to tournament (disable shuffle for determinism)
        resp = client.put(
            f"/api/v1/tournaments/{tid}",
            json={
                "version": 1,
                "selected_option_ids": option_ids,
                "config": {"shuffle_seed": False},
            },
        )
        assert resp.status_code == 200
        tournament = resp.json()
        assert tournament["version"] == 2

        # Step 4: Activate tournament
        resp = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        assert resp.status_code == 200
        tournament = resp.json()
        assert tournament["status"] == "active"
        assert len(tournament["entries"]) == 4
        assert tournament["state"]["total_rounds"] == 2
        version = tournament["version"]

        # Step 5: Vote through all matchups
        # Round 1 (Semi-finals): 2 matchups
        for _ in range(2):
            ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
            assert ctx["type"] == "bracket_matchup"
            assert ctx["round"] == 1
            resp = client.post(
                f"/api/v1/tournaments/{tid}/vote",
                json={
                    "version": version,
                    "voter_label": "default",
                    "payload": {"matchup_id": ctx["matchup_id"], "winner_entry_id": ctx["entry_a"]["id"]},
                },
            )
            assert resp.status_code == 200
            version = resp.json()["version"]

        # Round 2 (Final): 1 matchup
        ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
        assert ctx["type"] == "bracket_matchup"
        assert ctx["round"] == 2
        assert ctx["round_name"] == "Final"
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={
                "version": version,
                "voter_label": "default",
                "payload": {"matchup_id": ctx["matchup_id"], "winner_entry_id": ctx["entry_a"]["id"]},
            },
        )
        assert resp.status_code == 200
        tournament = resp.json()
        assert tournament["status"] == "completed"

        # Step 6: Verify result
        resp = client.get(f"/api/v1/tournaments/{tid}/result")
        assert resp.status_code == 200
        result = resp.json()
        assert len(result["winner_ids"]) == 1
        assert len(result["ranking"]) == 4
        ranks = sorted(r["rank"] for r in result["ranking"])
        assert ranks == [1, 2, 3, 3]

        # Verify vote context after completion shows completed
        ctx = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "default"}).json()
        assert ctx["type"] == "completed"


class TestCustomVoterLabels:
    def _setup_active_score(self, client: TestClient, voter_labels: list[str] | None = None) -> tuple[str, int]:
        """Create + activate a 3-option score tournament with optional custom voter labels."""
        options = _create_options(client, 3)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "score"})
        tid = create.json()["id"]
        config: dict = {"min_score": 1, "max_score": 5}
        if voter_labels is not None:
            config["voter_labels"] = voter_labels
        client.put(
            f"/api/v1/tournaments/{tid}",
            json={
                "version": 1,
                "selected_option_ids": [o["id"] for o in options],
                "config": config,
            },
        )
        resp = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": 2})
        return tid, resp.json()["version"]

    def test_create_score_with_custom_labels_round_trips(self, client: TestClient) -> None:
        tid, _ = self._setup_active_score(client, voter_labels=["Alice", "Bob"])
        resp = client.get(f"/api/v1/tournaments/{tid}")
        assert resp.status_code == 200
        assert resp.json()["config"]["voter_labels"] == ["Alice", "Bob"]

    def test_default_voter_label_is_default(self, client: TestClient) -> None:
        tid, _ = self._setup_active_score(client)
        assert client.get(f"/api/v1/tournaments/{tid}").json()["config"]["voter_labels"] == ["default"]

    def test_vote_context_for_known_voter(self, client: TestClient) -> None:
        tid, _ = self._setup_active_score(client, voter_labels=["Alice", "Bob"])
        resp = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "Alice"})
        assert resp.status_code == 200
        assert resp.json()["type"] == "ballot"

    def test_vote_context_for_unknown_voter_returns_422(self, client: TestClient) -> None:
        tid, _ = self._setup_active_score(client, voter_labels=["Alice", "Bob"])
        resp = client.get(f"/api/v1/tournaments/{tid}/vote-context", params={"voter": "Charlie"})
        assert resp.status_code == 422
        assert "Unknown voter" in resp.json()["error"]["message"]

    def test_submit_vote_for_unknown_voter_returns_422(self, client: TestClient) -> None:
        tid, version = self._setup_active_score(client, voter_labels=["Alice", "Bob"])
        # Get entry IDs by fetching the tournament
        entries = client.get(f"/api/v1/tournaments/{tid}").json()["entries"]
        scores = [{"entry_id": e["id"], "score": 3} for e in entries]
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={"version": version, "voter_label": "Charlie", "payload": {"scores": scores}},
        )
        assert resp.status_code == 422
        assert "Unknown voter" in resp.json()["error"]["message"]

    def test_vote_then_revote_same_voter_returns_422(self, client: TestClient) -> None:
        tid, version = self._setup_active_score(client, voter_labels=["Alice", "Bob"])
        entries = client.get(f"/api/v1/tournaments/{tid}").json()["entries"]
        scores = [{"entry_id": e["id"], "score": 3} for e in entries]
        resp1 = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={"version": version, "voter_label": "Alice", "payload": {"scores": scores}},
        )
        assert resp1.status_code == 200
        resp2 = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={"version": resp1.json()["version"], "voter_label": "Alice", "payload": {"scores": scores}},
        )
        assert resp2.status_code == 422
        assert "already" in resp2.json()["error"]["message"].lower()

    def test_bracket_rejects_multiple_voter_labels_at_update(self, client: TestClient) -> None:
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "bracket"})
        tid = create.json()["id"]
        resp = client.put(
            f"/api/v1/tournaments/{tid}",
            json={"version": 1, "config": {"voter_labels": ["Alice", "Bob"]}},
        )
        assert resp.status_code == 422
        assert "single voter" in resp.json()["error"]["message"].lower()

    def test_invalid_voter_labels_at_update_returns_422(self, client: TestClient) -> None:
        # duplicate labels
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "score"})
        tid = create.json()["id"]
        resp = client.put(
            f"/api/v1/tournaments/{tid}",
            json={"version": 1, "config": {"voter_labels": ["Alice", "Alice"]}},
        )
        assert resp.status_code == 422


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestUndoEndpoint:
    """Tests for POST /tournaments/{id}/undo."""

    def _setup_active_2voter_score(self, client: TestClient, *, allow_undo: bool = True) -> tuple[str, int]:
        """Create + activate a 2-voter score tournament. Returns (tid, version)."""
        options = _create_options(client, 3)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "score"})
        tid = create.json()["id"]
        version = create.json()["version"]
        config = {
            "min_score": 1,
            "max_score": 5,
            "voter_labels": ["Alice", "Bob"],
            "allow_undo": allow_undo,
        }
        upd = client.put(
            f"/api/v1/tournaments/{tid}",
            json={
                "version": version,
                "selected_option_ids": [o["id"] for o in options],
                "config": config,
            },
        )
        version = upd.json()["version"]
        act = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": version})
        return tid, act.json()["version"]

    def _vote_as(self, client: TestClient, tid: str, version: int, voter: str, scores: list[int]) -> dict:
        t = client.get(f"/api/v1/tournaments/{tid}").json()
        entry_ids = [e["id"] for e in t["entries"]]
        resp = client.post(
            f"/api/v1/tournaments/{tid}/vote",
            json={
                "version": version,
                "voter_label": voter,
                "payload": {
                    "scores": [{"entry_id": eid, "score": s} for eid, s in zip(entry_ids, scores, strict=True)]
                },
            },
        )
        return resp.json()

    def test_undo_returns_200_with_tournament_and_context(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client)
        after_vote = self._vote_as(client, tid, v, "Alice", [5, 3, 1])
        v = after_vote["version"]

        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": v, "voter_label": "Alice"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "tournament" in body
        assert "vote_context" in body
        # Alice can vote again — context should be a ballot
        assert body["vote_context"]["type"] == "ballot"

    def test_undo_missing_version_returns_422(self, client: TestClient) -> None:
        tid, _ = self._setup_active_2voter_score(client)
        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"voter_label": "Alice"},
        )
        assert resp.status_code == 422

    def test_undo_missing_voter_label_returns_422(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client)
        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": v},
        )
        assert resp.status_code == 422

    def test_undo_stale_version_returns_409(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client)
        after_vote = self._vote_as(client, tid, v, "Alice", [5, 3, 1])
        stale_v = after_vote["version"] - 1
        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": stale_v, "voter_label": "Alice"},
        )
        assert resp.status_code == 409

    def test_undo_no_vote_returns_422(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client)
        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": v, "voter_label": "Alice"},
        )
        assert resp.status_code == 422

    def test_undo_unknown_voter_returns_422(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client)
        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": v, "voter_label": "Charlie"},
        )
        assert resp.status_code == 422

    def test_undo_on_completed_returns_409(self, client: TestClient) -> None:
        """Single-voter submit completes immediately; undo should be rejected."""
        options = _create_options(client, 3)
        create = client.post("/api/v1/tournaments", json={"name": "T", "mode": "score"})
        tid = create.json()["id"]
        v = create.json()["version"]
        upd = client.put(
            f"/api/v1/tournaments/{tid}",
            json={
                "version": v,
                "selected_option_ids": [o["id"] for o in options],
                "config": {"voter_labels": ["Alice"]},
            },
        )
        v = upd.json()["version"]
        v = client.post(f"/api/v1/tournaments/{tid}/activate", json={"version": v}).json()["version"]
        after = self._vote_as(client, tid, v, "Alice", [5, 3, 1])
        assert after["status"] == "completed"

        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": after["version"], "voter_label": "Alice"},
        )
        assert resp.status_code == 409

    def test_undo_disabled_returns_409(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client, allow_undo=False)
        after_vote = self._vote_as(client, tid, v, "Alice", [5, 3, 1])
        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": after_vote["version"], "voter_label": "Alice"},
        )
        assert resp.status_code == 409

    def test_undo_preserves_vote_record_as_superseded(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client)
        after_vote = self._vote_as(client, tid, v, "Alice", [5, 3, 1])
        v = after_vote["version"]
        client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": v, "voter_label": "Alice"},
        )
        t = client.get(f"/api/v1/tournaments/{tid}").json()
        assert len(t["votes"]) == 1
        assert t["votes"][0]["status"] == "superseded"
        assert t["votes"][0]["superseded_at"] is not None

    def test_response_includes_refreshed_tournament_status(self, client: TestClient) -> None:
        tid, v = self._setup_active_2voter_score(client)
        after_vote = self._vote_as(client, tid, v, "Alice", [5, 3, 1])
        resp = client.post(
            f"/api/v1/tournaments/{tid}/undo",
            json={"version": after_vote["version"], "voter_label": "Alice"},
        )
        tournament = resp.json()["tournament"]
        assert tournament["status"] == "active"
