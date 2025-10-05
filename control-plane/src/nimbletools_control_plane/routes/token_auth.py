"""
Auth Router for NimbleTools Control Plane
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])


@router.get("/v1/token_auth")
@router.post("/v1/token_auth")
async def auth_check() -> JSONResponse:
    """
    Auth endpoint for ingress validation.
    Returns 200 OK in core edition - enterprise editions can override this.
    """
    logger.debug("Auth check requested - returning 200 OK (core edition)")
    return JSONResponse(status_code=200, content={"authenticated": True})
