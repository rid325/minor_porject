"""Email/password signup, login, session and logout endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pymongo.errors import PyMongoError

from ..schemas.api import (
    AccountProfileResponse,
    AccountProfileSaveRequest,
    AuthCredentialsRequest,
    AuthStatusResponse,
    AuthUserResponse,
    ChangePasswordRequest,
)
from ..services import auth_service
from ..services import account_profile_service
from ..schemas.profile import ApplicantProfile


router = APIRouter(prefix="/auth", tags=["authentication"])


def _handle_auth_error(error: Exception) -> HTTPException:
    if isinstance(error, auth_service.AuthNotConfigured):
        return HTTPException(
            status_code=503,
            detail="Authentication is not configured. Set MONGODB_URI for MongoDB Atlas.",
        )
    if isinstance(error, auth_service.EmailAlreadyRegistered):
        return HTTPException(status_code=409, detail="An account already uses this email.")
    if isinstance(error, auth_service.InvalidEmail):
        return HTTPException(status_code=422, detail="Enter a valid email address.")
    if isinstance(error, auth_service.WeakPassword):
        return HTTPException(
            status_code=422, detail="Password must be at least 8 characters long."
        )
    if isinstance(error, auth_service.InvalidCredentials):
        return HTTPException(status_code=401, detail="Email or password is incorrect.")
    return HTTPException(status_code=503, detail="Authentication service is unavailable.")


def _issue_session(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        value=token,
        max_age=int(auth_service.SESSION_TTL.total_seconds()),
        httponly=True,
        secure=auth_service.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _user_response(user: dict) -> AuthUserResponse:
    return AuthUserResponse(**user)


@router.post("/signup", response_model=AuthStatusResponse, status_code=201)
def signup(credentials: AuthCredentialsRequest, response: Response) -> AuthStatusResponse:
    try:
        user, token = auth_service.create_account(credentials.email, credentials.password)
    except (
        auth_service.AuthNotConfigured,
        auth_service.EmailAlreadyRegistered,
        auth_service.InvalidEmail,
        auth_service.WeakPassword,
        PyMongoError,
    ) as exc:
        raise _handle_auth_error(exc) from exc
    _issue_session(response, token)
    return AuthStatusResponse(authenticated=True, user=_user_response(user))


@router.post("/login", response_model=AuthStatusResponse)
def login(credentials: AuthCredentialsRequest, response: Response) -> AuthStatusResponse:
    try:
        user, token = auth_service.authenticate(credentials.email, credentials.password)
    except (
        auth_service.AuthNotConfigured,
        auth_service.InvalidCredentials,
        auth_service.InvalidEmail,
        PyMongoError,
    ) as exc:
        raise _handle_auth_error(exc) from exc
    _issue_session(response, token)
    return AuthStatusResponse(authenticated=True, user=_user_response(user))


@router.get("/me", response_model=AuthStatusResponse)
def current_user(request: Request) -> AuthStatusResponse:
    token = request.cookies.get(auth_service.SESSION_COOKIE_NAME, "")
    if not token:
        return AuthStatusResponse(authenticated=False)
    try:
        user = auth_service.user_for_session(token)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise _handle_auth_error(exc) from exc
    return AuthStatusResponse(
        authenticated=user is not None,
        user=_user_response(user) if user else None,
    )


def _require_user_id(request: Request):
    token = request.cookies.get(auth_service.SESSION_COOKIE_NAME, "")
    try:
        user_id = auth_service.user_id_for_session(token)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise _handle_auth_error(exc) from exc
    if user_id is None:
        raise HTTPException(status_code=401, detail="Sign in to access your saved profile.")
    return user_id


@router.get("/profile", response_model=AccountProfileResponse)
def get_account_profile(request: Request) -> AccountProfileResponse:
    user_id = _require_user_id(request)
    try:
        saved = account_profile_service.get_profile(user_id)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise _handle_auth_error(exc) from exc
    return AccountProfileResponse(**(saved or {}))


@router.put("/profile", response_model=AccountProfileResponse)
def put_account_profile(
    body: AccountProfileSaveRequest, request: Request
) -> AccountProfileResponse:
    user_id = _require_user_id(request)
    try:
        validation_profile = dict(body.profile)
        personal = validation_profile.get("personal")
        if isinstance(personal, dict) and personal.get("date_of_birth") == "":
            validation_profile["personal"] = {**personal, "date_of_birth": None}
        ApplicantProfile.model_validate(validation_profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Profile answers are invalid.") from exc
    try:
        saved = account_profile_service.save_profile(user_id, body.profile)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise _handle_auth_error(exc) from exc
    return AccountProfileResponse(**saved)


@router.post("/change-password")
def update_password(body: ChangePasswordRequest, request: Request) -> dict[str, bool]:
    user_id = _require_user_id(request)
    try:
        auth_service.change_password(user_id, body.current_password, body.new_password)
    except auth_service.IncorrectCurrentPassword as exc:
        raise HTTPException(status_code=400, detail="Current password is incorrect.") from exc
    except auth_service.WeakPassword as exc:
        raise _handle_auth_error(exc) from exc
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise _handle_auth_error(exc) from exc
    return {"updated": True}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(auth_service.SESSION_COOKIE_NAME, "")
    try:
        auth_service.revoke_session(token)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        response.delete_cookie(
            auth_service.SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            secure=auth_service.cookie_secure(),
            samesite="lax",
        )
        raise _handle_auth_error(exc) from exc
    response.delete_cookie(
        auth_service.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=auth_service.cookie_secure(),
        samesite="lax",
    )
    return {"authenticated": False}
