"""Options and Tags API endpoints."""

from typing import Any, get_args
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.dependencies import get_option_service
from app.exceptions import ValidationError
from app.repositories.options import SortBy, SortOrder
from app.services.option_service import OptionService

_VALID_SORT_BY: tuple[str, ...] = get_args(SortBy)
_VALID_SORT_ORDER: tuple[str, ...] = get_args(SortOrder)

router = APIRouter(tags=["options"])


# --- Request models ---


class CreateOptionRequest(BaseModel):
    name: str = Field(..., max_length=256)
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class BulkCreateRequest(BaseModel):
    names: list[str]
    tags: list[str] = Field(default_factory=list)


class UpdateOptionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class BulkTagUpdateRequest(BaseModel):
    option_ids: list[UUID]
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)


# --- Endpoints ---


@router.get("/options")
def list_options(
    q: str | None = None,
    tags_all: str | None = None,
    tags_any: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    service: OptionService = Depends(get_option_service),
) -> list[dict[str, Any]]:
    if sort_by not in _VALID_SORT_BY:
        raise ValidationError(f"sort_by must be one of {list(_VALID_SORT_BY)}")
    if sort_order not in _VALID_SORT_ORDER:
        raise ValidationError(f"sort_order must be one of {list(_VALID_SORT_ORDER)}")
    tags_all_list = [t.strip() for t in tags_all.split(",")] if tags_all else None
    tags_any_list = [t.strip() for t in tags_any.split(",")] if tags_any else None
    options = service.list_options(
        q=q,
        tags_all=tags_all_list,
        tags_any=tags_any_list,
        sort_by=sort_by,  # type: ignore[arg-type]
        sort_order=sort_order,  # type: ignore[arg-type]
    )
    return [o.model_dump(mode="json") for o in options]


@router.post("/options", status_code=201)
def create_option(
    body: CreateOptionRequest,
    service: OptionService = Depends(get_option_service),
) -> dict[str, Any]:
    option = service.create_option(name=body.name, description=body.description, tags=body.tags)
    return option.model_dump(mode="json")


@router.post("/options/bulk", status_code=201)
def bulk_create(
    body: BulkCreateRequest,
    service: OptionService = Depends(get_option_service),
) -> dict[str, Any]:
    result = service.bulk_create(names=body.names, tags=body.tags)
    return result.model_dump(mode="json")


@router.get("/options/{option_id}")
def get_option(
    option_id: UUID,
    service: OptionService = Depends(get_option_service),
) -> dict[str, Any]:
    option = service.get_option(option_id)
    return option.model_dump(mode="json")


@router.put("/options/{option_id}")
def update_option(
    option_id: UUID,
    body: UpdateOptionRequest,
    service: OptionService = Depends(get_option_service),
) -> dict[str, Any]:
    option = service.update_option(option_id, name=body.name, description=body.description, tags=body.tags)
    return option.model_dump(mode="json")


@router.patch("/options/bulk")
def bulk_update_tags(
    body: BulkTagUpdateRequest,
    service: OptionService = Depends(get_option_service),
) -> list[dict[str, Any]]:
    options = service.bulk_update_tags(option_ids=body.option_ids, add_tags=body.add_tags, remove_tags=body.remove_tags)
    return [o.model_dump(mode="json") for o in options]


@router.delete("/options/{option_id}", status_code=204)
def delete_option(
    option_id: UUID,
    service: OptionService = Depends(get_option_service),
) -> Response:
    service.delete_option(option_id)
    return Response(status_code=204)


@router.get("/tags")
def list_tags(
    service: OptionService = Depends(get_option_service),
) -> list[str]:
    return service.get_all_tags()
