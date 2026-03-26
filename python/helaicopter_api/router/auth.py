"""Auth credential store REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from helaicopter_api.application.auth import (
    complete_oauth_callback,
    connect_claude_cli_credential,
    create_credential,
    initiate_oauth,
    list_credentials,
    record_cost,
    refresh_credential,
    revoke_credential,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.auth import (
    CreateCredentialRequest,
    CredentialResponse,
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    RecordCostRequest,
)
from helaicopter_api.server.dependencies import get_services

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post(
    "/credentials",
    response_model=CredentialResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new auth credential.",
)
async def credential_create(
    body: CreateCredentialRequest,
    services: BackendServices = Depends(get_services),
) -> CredentialResponse:
    return create_credential(services.sqlite_engine, body)


@auth_router.post(
    "/credentials/claude-cli/connect",
    response_model=CredentialResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a local Claude CLI session credential.",
)
async def credential_claude_cli_connect(
    services: BackendServices = Depends(get_services),
) -> CredentialResponse:
    try:
        return connect_claude_cli_credential(services.sqlite_engine, settings=services.settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@auth_router.post(
    "/credentials/oauth/initiate",
    response_model=OAuthInitiateResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    summary="Start a managed OAuth credential flow.",
)
async def credential_oauth_initiate(
    body: OAuthInitiateRequest,
) -> OAuthInitiateResponse:
    try:
        return initiate_oauth(provider=body.provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@auth_router.get(
    "/credentials/oauth/callback",
    response_model=CredentialResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    summary="Complete a managed OAuth credential flow.",
)
async def credential_oauth_callback(
    code: str,
    state: str,
    services: BackendServices = Depends(get_services),
) -> CredentialResponse:
    try:
        return complete_oauth_callback(engine=services.sqlite_engine, code=code, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@auth_router.get(
    "/credentials",
    response_model=list[CredentialResponse],
    response_model_by_alias=True,
    summary="List all credentials (secrets redacted).",
)
async def credential_list(
    services: BackendServices = Depends(get_services),
) -> list[CredentialResponse]:
    return list_credentials(services.sqlite_engine)


@auth_router.delete(
    "/credentials/{credential_id}",
    status_code=status.HTTP_200_OK,
    summary="Revoke a credential.",
)
async def credential_revoke(
    credential_id: str,
    services: BackendServices = Depends(get_services),
) -> dict[str, str]:
    if not revoke_credential(services.sqlite_engine, credential_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    return {"ok": "true"}


@auth_router.post(
    "/credentials/{credential_id}/record-cost",
    status_code=status.HTTP_200_OK,
    summary="Record cost against a credential.",
)
async def credential_record_cost(
    credential_id: str,
    body: RecordCostRequest,
    services: BackendServices = Depends(get_services),
) -> dict[str, str]:
    if not record_cost(services.sqlite_engine, credential_id, body):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    return {"ok": "true"}


@auth_router.post(
    "/credentials/{credential_id}/refresh",
    response_model=CredentialResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    summary="Refresh a managed OAuth credential.",
)
async def credential_refresh(
    credential_id: str,
    services: BackendServices = Depends(get_services),
) -> CredentialResponse:
    try:
        refreshed = refresh_credential(services.sqlite_engine, credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    return refreshed
