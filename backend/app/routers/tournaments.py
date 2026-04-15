"""Tournament API endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.dependencies import get_tournament_service
from app.schemas.common import TournamentMode, TournamentStatus
from app.services.tournament_service import TournamentService

router = APIRouter(tags=["tournaments"])


# --- Request models ---


class CreateTournamentRequest(BaseModel):
    name: str = Field(..., max_length=256)
    mode: TournamentMode
    description: str = ""


class UpdateTournamentRequest(BaseModel):
    version: int
    name: str | None = None
    description: str | None = None
    selected_option_ids: list[UUID] | None = None
    config: dict[str, Any] | None = None


class ActivateRequest(BaseModel):
    version: int


class CancelRequest(BaseModel):
    version: int


class VoteRequest(BaseModel):
    version: int
    voter_label: str
    payload: dict[str, Any]


class UndoRequest(BaseModel):
    version: int
    voter_label: str
    # Forward-compat — only "latest" accepted in v1.
    scope: str = "latest"


# --- Endpoints ---


@router.get("/tournaments")
def list_tournaments(
    status: str | None = None,
    service: TournamentService = Depends(get_tournament_service),
) -> list[dict[str, Any]]:
    status_list = None
    if status:
        status_list = [TournamentStatus(s.strip()) for s in status.split(",")]
    tournaments = service.list_tournaments(status=status_list)
    return [t.model_dump(mode="json") for t in tournaments]


@router.post("/tournaments", status_code=201)
def create_tournament(
    body: CreateTournamentRequest,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    tournament = service.create_tournament(name=body.name, mode=body.mode, description=body.description)
    return tournament.model_dump(mode="json")


@router.get("/tournaments/{tournament_id}")
def get_tournament(
    tournament_id: UUID,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    tournament = service.get_tournament(tournament_id)
    return tournament.model_dump(mode="json")


@router.put("/tournaments/{tournament_id}")
def update_tournament(
    tournament_id: UUID,
    body: UpdateTournamentRequest,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    tournament = service.update_tournament(
        tournament_id,
        version=body.version,
        name=body.name,
        description=body.description,
        selected_option_ids=body.selected_option_ids,
        config=body.config,
    )
    return tournament.model_dump(mode="json")


@router.delete("/tournaments/{tournament_id}", status_code=204)
def delete_tournament(
    tournament_id: UUID,
    service: TournamentService = Depends(get_tournament_service),
) -> Response:
    service.delete_tournament(tournament_id)
    return Response(status_code=204)


@router.post("/tournaments/{tournament_id}/activate")
def activate_tournament(
    tournament_id: UUID,
    body: ActivateRequest,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    tournament = service.activate_tournament(tournament_id, version=body.version)
    return tournament.model_dump(mode="json")


@router.post("/tournaments/{tournament_id}/cancel")
def cancel_tournament(
    tournament_id: UUID,
    body: CancelRequest,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    tournament = service.cancel_tournament(tournament_id, version=body.version)
    return tournament.model_dump(mode="json")


@router.post("/tournaments/{tournament_id}/clone", status_code=201)
def clone_tournament(
    tournament_id: UUID,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    tournament = service.clone_tournament(tournament_id)
    return tournament.model_dump(mode="json")


@router.get("/tournaments/{tournament_id}/vote-context")
def get_vote_context(
    tournament_id: UUID,
    voter: str = "default",
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    context = service.get_vote_context(tournament_id, voter_label=voter)
    return context.model_dump(mode="json")


@router.post("/tournaments/{tournament_id}/vote")
def submit_vote(
    tournament_id: UUID,
    body: VoteRequest,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    tournament = service.submit_vote(
        tournament_id,
        version=body.version,
        voter_label=body.voter_label,
        payload=body.payload,
    )
    return tournament.model_dump(mode="json")


@router.post("/tournaments/{tournament_id}/undo")
def undo_vote(
    tournament_id: UUID,
    body: UndoRequest,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    """Undo the calling voter's most recent active vote.

    Returns the refreshed tournament and the voter's new vote_context in a
    single response so the UI can update without a second round-trip.
    """
    if body.scope != "latest":
        from app.exceptions import ValidationError

        raise ValidationError(f"Unsupported undo scope: '{body.scope}'")
    tournament = service.undo_vote(
        tournament_id,
        version=body.version,
        voter_label=body.voter_label,
    )
    vote_context = service.get_vote_context(tournament_id, voter_label=body.voter_label)
    return {
        "tournament": tournament.model_dump(mode="json"),
        "vote_context": vote_context.model_dump(mode="json"),
    }


@router.get("/tournaments/{tournament_id}/result")
def get_result(
    tournament_id: UUID,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    result = service.get_result(tournament_id)
    return result.model_dump(mode="json")


@router.get("/tournaments/{tournament_id}/state")
def get_state(
    tournament_id: UUID,
    service: TournamentService = Depends(get_tournament_service),
) -> dict[str, Any]:
    return service.get_state(tournament_id)
