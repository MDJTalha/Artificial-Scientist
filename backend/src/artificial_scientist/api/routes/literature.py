"""HTTP API for searching scholarly metadata sources."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from artificial_scientist.api.routes.records import get_record_store, record_access
from artificial_scientist.config import get_settings
from artificial_scientist.literature.models import (
    LiteratureSearchRequest,
    LiteratureSearchResponse,
)
from artificial_scientist.literature.service import (
    LiteraturePersistenceError,
    LiteratureService,
)
from artificial_scientist.records.store import RecordStore

router = APIRouter(prefix="/api/v1/literature", tags=["literature"])


def get_literature_service(
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> LiteratureService:
    """Build a request-scoped literature service using the configured providers."""
    return LiteratureService(store=store, settings=get_settings())


@router.post(
    "/search",
    response_model=LiteratureSearchResponse,
    summary="Search OpenAlex and Crossref scholarly metadata",
)
def search_literature(
    request: LiteratureSearchRequest,
    service: Annotated[LiteratureService, Depends(get_literature_service)],
    tenant_id: Annotated[str | None, Depends(record_access("record:create"))],
) -> LiteratureSearchResponse:
    """Retrieve bounded bibliographic metadata and optionally save source records.

    The endpoint does not fetch full-text papers, judge scientific truth, or claim
    that search results are exhaustive.
    """
    try:
        return service.search(request, tenant_id=tenant_id)
    except LiteraturePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
