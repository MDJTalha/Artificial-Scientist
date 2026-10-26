"""API endpoints for the controlled computational laboratory."""

from fastapi import APIRouter

from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.models import LabRunRequest, LabRunResponse

router = APIRouter(prefix="/api/v1/lab", tags=["controlled computational laboratory"])


@router.post("/runs", response_model=LabRunResponse, status_code=201)
def create_lab_run(request: LabRunRequest) -> LabRunResponse:
    """Execute a bounded declarative run using existing allowlisted math operations."""
    return run_lab(request)
