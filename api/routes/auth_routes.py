# routes/auth_routes.py

import os
from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, jsonify, make_response, redirect, request
from sqlalchemy.exc import SQLAlchemyError

from api import db
from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.user_repository import UserRepository
from api.routes.main import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    error_response,
    log_route_error,
    register_blueprint_error_handlers,
    success_response,
)
from api.services.auth_service import ACCESS_TOKEN_TTL, AuthService
from api.services.subscription_service import SubscriptionService
from api.utils.auth import (
    ENTITIES_FILE,
    MAILS_FILE,
    _extract_token,
    append_json_list,
    validate_email,
)
from api.utils.cookie_policy import COOKIE_SAMESITE, COOKIE_SECURE
from api.utils.datetime_utils import iso_utc
from api.utils.permissions import require_role
from api.utils.rate_limit import client_ip, record_failure, too_many_failures
from api.utils.validators import (
    ALLOWED_PROFESSIONS,
    ALLOWED_ROLES,
    sanitize_string,
    validate_enum,
    validate_password,
    validate_phone,
    validate_required_keys,
)
from api.utils.validators import validate_email as v_email

# from app import app
SECRET = os.environ.get("SECRET_KEY")
FRONTEND_REDIRECT_URL = os.environ.get(
    "FRONTEND_REDIRECT_URL", "https://www.brendex.net"
)
FRONTEND_COOKIE_DOMAIN = os.environ.get("FRONTEND_COOKIE_DOMAIN", ".brendex.net")
auth_bp = Blueprint("auth", __name__)
ALLOWED_ENTITY_TYPES = ["company", "influencer", "small-business"]
# Refresh windows with less than this left are refused outright — see refresh().
MIN_REFRESH_REMAINDER = timedelta(minutes=2)

register_blueprint_error_handlers(auth_bp, include_token_errors=True)


@auth_bp.route("/register_mail", methods=["POST"])
def register_mail():
    try:
        payload = request.get_json(silent=True) or {}
        email = payload.get("email")
        if not email or not validate_email(email):
            return error_response("Invalid email", 400)

        if UserRepository.find_by_email(email):
            return error_response("Email already exists", 400)

        init_status = "unverified"
        email_object = {
            "email": email,
            "status": init_status,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        # Create-if-missing: the backing file is gitignored, so a fresh
        # deployment won't have it (r+ would raise FileNotFoundError).
        append_json_list(MAILS_FILE, email_object)

        return success_response(
            data={"message": f"Email {email} registered for temporary access"}
        )
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/register_user", methods=["POST"])
def register_user():
    try:
        data = request.get_json(silent=True) or {}
        required_keys = ["full_name", "email", "password", "phone_number", "profession"]
        missing = validate_required_keys(data, required_keys)
        if missing:
            return error_response(f"missing required key: {missing}", 400)

        if not v_email(data["email"]):
            return error_response("Invalid email format", 400)

        if not validate_password(data["password"]):
            return error_response("Password must be at least 8 characters", 400)

        if not validate_phone(data["phone_number"]):
            return error_response("Invalid phone number format", 400)

        role = data.get("role", "registered")
        err = validate_enum(role, ALLOWED_ROLES, "role")
        if err:
            return error_response(err, 400)

        err = validate_enum(data["profession"], ALLOWED_PROFESSIONS, "profession")
        if err:
            return error_response(err, 400)

        full_name = sanitize_string(data["full_name"], 100)
        if not full_name:
            return error_response("Invalid full_name", 400)

        user = AuthService.signup(
            first_name=full_name.split()[0],
            last_name=" ".join(full_name.split()[1:])
            if len(full_name.split()) > 1
            else "",
            email=data["email"].strip().lower(),
            password=data["password"],
            phone_number=data["phone_number"].strip(),
            role=role,
            profession=data["profession"],
            is_verified=True,
        )

        tokens = AuthService.issue_token_pair(user)
        AuthService.persist_refresh_token(
            user.id,
            token=tokens["refresh_token"],
            exp=tokens["refresh_token_exp"],
        )

        response = AuthService.build_auth_response(
            user,
            tokens["access_token"],
            tokens["refresh_token"],
        )
        response["is_verified"] = bool(getattr(user, "is_verified", False))

        return success_response(data=response)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/register_entity_name", methods=["POST"])
def register_entity_name():
    try:
        payload = request.get_json(silent=True) or {}
        entity_name = payload.get("entity_name")

        if not entity_name or not isinstance(entity_name, str):
            return error_response(
                "Missing or invalid required field: 'entity_name'.", 400
            )

        if EntityRepository.get_by_name(entity_name=entity_name):
            return error_response(f"entity name {entity_name} already exists")

        init_status = "unverified"
        entity_object = {
            "entity_name": entity_name,
            "status": init_status,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }

        # Create-if-missing (see register_mail): gitignored backing file.
        append_json_list(ENTITIES_FILE, entity_object)

        return success_response(
            data={"message": f"Entity {entity_name} registered for temporary access"}
        )
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/register_entity", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def register_entity():
    try:
        required_keys = ["entity_name", "type", "category_id"]
        data = request.get_json(silent=True) or {}
        missing = validate_required_keys(data, required_keys)
        if missing:
            return error_response(f"missing required key: {missing}", 400)

        name = sanitize_string(data["entity_name"], 120)
        if not name:
            return error_response("Invalid entity_name", 400)

        entity_type = sanitize_string(data["type"], 20)
        if not entity_type:
            return error_response("Invalid type", 400)
        type_error = validate_enum(entity_type, ALLOWED_ENTITY_TYPES, "type")
        if type_error:
            return error_response(type_error, 400)

        try:
            category_id = int(data["category_id"])
        except (TypeError, ValueError):
            return error_response("category_id must be an integer", 400)

        pages_data = data.get("pages")
        if pages_data is not None and not isinstance(pages_data, list):
            return error_response("pages must be a list", 400)

        if not CategoryRepository.get_by_id(category_id=category_id):
            return error_response("Invalid category_id", 400)

        if EntityRepository.get_by_name(entity_name=name):
            return error_response(f"entity name {name} already exists", 409)

        # Persist entity, category mapping, and pages in a single commit
        # to avoid partially inserted data when any downstream step fails.
        entity = EntityRepository.create(
            name=name,
            type_=entity_type,
            commit=False,
        )
        entity_category = EntityCategoryRepository.add(
            entity_id=entity.id,
            category_id=category_id,
            commit=False,
        )
        pages_response = AuthService.create_entity_pages(
            entity, pages_data, commit=False
        )
        db.session.commit()

        payload = {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "category_id": entity_category.category_id,
            "pages": pages_response,
        }

        return success_response(payload, status_code=201)

    except ValueError as ve:
        db.session.rollback()
        log_route_error(ve, SEVERITY_LOW, 400, "Entity registration validation failed")
        return error_response(str(ve), 400)
    except SQLAlchemyError as db_err:
        db.session.rollback()
        log_route_error(
            db_err, SEVERITY_HIGH, 500, "Entity registration database insertion failed"
        )
        return error_response(
            "Failed to save entity data. Check entity uniqueness, category mapping, and page values.",
            500,
        )
    except Exception as ex:
        db.session.rollback()
        log_route_error(
            ex, SEVERITY_HIGH, 500, "Entity registration failed unexpectedly"
        )
        return error_response("Entity registration failed unexpectedly", 500)


# Per-IP login throttle to blunt password brute-forcing. Generous enough not to
# trip up a user fumbling their password. Only FAILED attempts are counted, so a
# successful login (or a malformed request) never consumes a shared IP's budget.
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SECONDS = 60


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        # Resolve the throttle key and check the failure count. Fail OPEN: any
        # limiter error must not lock a legitimate user out.
        rl_key = None
        try:
            rl_key = f"login:{client_ip()}"
            limited, retry_after = too_many_failures(rl_key, LOGIN_MAX_FAILURES)
        except Exception:
            limited, retry_after = False, 0
        if limited:
            response = make_response(
                error_response(
                    "Too many failed login attempts. Please try again later.", 429
                )
            )
            response.headers["Retry-After"] = str(retry_after)
            return response

        def _record_failed_login():
            if not rl_key:
                return
            try:
                record_failure(rl_key, LOGIN_WINDOW_SECONDS)
            except Exception:
                pass  # best-effort; never fail the request over accounting

        data = request.get_json(silent=True) or {}
        missing = validate_required_keys(data, ["email", "password"])
        if missing:
            return error_response(f"missing required key: {missing}", 400)

        if not v_email(data["email"]):
            return error_response("Invalid email format", 400)

        # Reject blank passwords outright: OAuth-only accounts have no usable
        # password, and validate_required_keys treats "" as present.
        if not data.get("password"):
            _record_failed_login()
            return error_response("Invalid credentials", status_code=401)

        user = UserRepository.find_by_email(data["email"].strip().lower())
        if not user or not user.check_password(data["password"]):
            _record_failed_login()
            return error_response("Invalid credentials", status_code=401)

        # Keep role aligned with subscription windows before issuing tokens.
        user, active_subscription, _ = SubscriptionService.get_effective_access_for_user(user)
        if not user:
            _record_failed_login()
            return error_response("Invalid credentials", status_code=401)

        tokens = AuthService.issue_token_pair(user)
        AuthService.persist_refresh_token(
            user.id,
            token=tokens["refresh_token"],
            exp=tokens["refresh_token_exp"],
        )

        response = AuthService.build_auth_response(
            user,
            tokens["access_token"],
            tokens["refresh_token"],
        )
        response["is_verified"] = bool(getattr(user, "is_verified", False))
        response["subscription"] = {
            "pack_code": getattr(active_subscription, "pack_code", None),
            "status": getattr(active_subscription, "status", None),
            "starts_at": iso_utc(getattr(active_subscription, "starts_at", None)),
            "ends_at": iso_utc(getattr(active_subscription, "ends_at", None)),
        }

        return success_response(response, status_code=200)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/get_user_data", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def get_user_data():
    try:
        # Auth payload is already validated by @require_role decorator
        current_user_id = getattr(request, "user_id", None)
        if not isinstance(current_user_id, int):
            return error_response("User not found", 404)
        user = UserRepository.get_by_id(current_user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        user, active_subscription, _ = SubscriptionService.get_effective_access(user.id)

        return success_response(
            data={
                "email": user.email,
                "user_id": user.id,
                "role": user.role,
                "is_verified": bool(getattr(user, "is_verified", False)),
                "profession": user.profession,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "created_at": iso_utc(user.created_at),
                "subscription": {
                    "pack_code": getattr(active_subscription, "pack_code", None),
                    "status": getattr(active_subscription, "status", None),
                    "starts_at": iso_utc(getattr(active_subscription, "starts_at", None)),
                    "ends_at": iso_utc(getattr(active_subscription, "ends_at", None)),
                },
            }
        )
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/refresh_token", methods=["POST"])
def refresh():

    try:
        # Every exit from this route uses the standard envelope (see
        # routes/main.py) — including the failures, which are the paths clients
        # act on to send a user back to the login page.
        token = _extract_token("refresh_token")
        if not token:
            return error_response("Missing refresh token", 400)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user = UserRepository.get_by_id(payload["user_id"])

        if not user or user.refresh_token != token:
            return error_response("Invalid refresh token", 401)

        # `refresh_token_exp` is a naive `db.DateTime` column, so it comes back
        # from Postgres without a tzinfo even though it is written as UTC.
        # Comparing it to an aware `now()` raised TypeError, which the
        # blueprint's handler turned into a 400 — so *every* refresh failed and
        # the frontends logged the user out on the spot. Normalize before
        # comparing; this is what actually keeps a session alive between
        # access-token expiries.
        refresh_exp = user.refresh_token_exp
        if refresh_exp is None:
            return error_response("Invalid refresh token", 401)
        if refresh_exp.tzinfo is None:
            refresh_exp = refresh_exp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        # Treat a window about to close as already closed. Handing back a token
        # with seconds of life left reads as success to the clients, which store
        # it, immediately 401 on the next call, and refresh again — a loop that
        # only ends when the window actually expires. One clean 401 sends them
        # to the login page instead.
        remaining = refresh_exp - now
        if remaining < MIN_REFRESH_REMAINDER:
            return error_response("Refresh token expired", 401)

        # Keep role aligned with subscription windows before issuing tokens,
        # same as /login and /redirect_to_app. `require_auth` re-resolves the
        # role from the DB on every request, so this is not the primary guard —
        # but it is the value `require_auth` falls back to when that lookup
        # fails, and with a 72h token a stale claim would linger for three days.
        user, _, _ = SubscriptionService.get_effective_access_for_user(user)
        if not user:
            return error_response("Invalid refresh token", 401)

        # Same TTL as a fresh login — a refreshed session is a session, and a
        # shorter window here would send users back to the login page long
        # before their 72 hours were up. Capped at the refresh window, which is
        # the real session limit: this route doesn't rotate the stored refresh
        # token, so an uncapped 72h access token issued just before that window
        # closed would outlive it by up to three days.
        tokens = AuthService.issue_token_pair(
            user,
            access_delta=min(ACCESS_TOKEN_TTL, remaining),
        )
        # Only the access token is used. `tokens["refresh_token"]` is minted and
        # deliberately dropped: the DB still holds the original, so setting the
        # new one as a cookie *without* also persisting it would desync the two
        # and make every later refresh fail the `user.refresh_token != token`
        # check above. Rotate in both places or neither.
        new_access = tokens["access_token"]
        access_exp = tokens["access_token_exp"]

        response = {"access_token": new_access}
        flask_response = make_response(success_response(response))
        flask_response.set_cookie(
            "access_token",
            new_access,
            expires=access_exp,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=FRONTEND_COOKIE_DOMAIN or None,
            path="/",
        )
        return flask_response
    except jwt.ExpiredSignatureError:
        return error_response("Refresh token expired", status_code=401)
    except jwt.InvalidTokenError:
        return error_response("Invalid refresh token", status_code=401)


@auth_bp.route("/logout", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def logout():
    try:
        user_id = None

        refresh_token = _extract_token("refresh_token")
        if refresh_token:
            try:
                refresh_payload = jwt.decode(
                    refresh_token, SECRET, algorithms=["HS256"]
                )
                user_id = refresh_payload.get("user_id")
            except jwt.InvalidTokenError:
                user_id = None

        if user_id is None:
            access_token = _extract_token("access_token")
            if access_token:
                try:
                    access_payload = jwt.decode(
                        access_token, SECRET, algorithms=["HS256"]
                    )
                    user_id = access_payload.get("user_id")
                except jwt.InvalidTokenError:
                    user_id = None

        if user_id is not None:
            user = UserRepository.get_by_id(user_id)
            if user:
                AuthService.persist_refresh_token(
                    user.id,
                    token="",
                    exp=datetime.now(timezone.utc),
                )

        cookie_domain = FRONTEND_COOKIE_DOMAIN or None
        response = make_response(
            success_response(data={"message": "Logged out successfully"})
        )
        response.set_cookie(
            "access_token",
            "",
            expires=0,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=cookie_domain,
            path="/",
        )
        response.set_cookie(
            "refresh_token",
            "",
            expires=0,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=cookie_domain,
            path="/",
        )

        return response
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/validate_user_role", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def validate_user_role():
    """this route updates the user role, after signing from google auth"""

    required_keys = ["user_id", "role"]
    try:
        # Auth payload is already validated by @require_role decorator
        current_user_id = getattr(request, "user_id", None)
        if not isinstance(current_user_id, int):
            return error_response("User not found", 404)
        caller = UserRepository.get_by_id(current_user_id)
        if not caller:
            return error_response("User not found", 404)
        if caller.role != "admin":
            return error_response("Access denied", 403)

        data = request.get_json(silent=True) or {}
        for key in required_keys:
            if key not in data:
                return error_response(f"Missing required key {key}", 400)

        user_id = data["user_id"]
        role = data["role"]

        user = UserRepository.update_role(user_id=user_id, role=role, is_verified=True)
        response = {
            "user_id": user.id,
            "role": user.role,
            "is_verified": bool(getattr(user, "is_verified", False)),
        }
        return success_response(data=response)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/complete_profile", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def complete_profile():
    """
    After Google sign-up, allows the user to add phone_number and profession.
    Requires a valid access token.
    """
    try:
        # Auth payload is already validated by @require_role decorator
        current_user_id = getattr(request, "user_id", None)
        if not isinstance(current_user_id, int):
            return error_response("User not found", 404)
        user = UserRepository.get_by_id(current_user_id)
        if not user:
            return error_response("User not found", 404)

        data = request.get_json(silent=True) or {}
        missing = validate_required_keys(data, ["phone_number", "profession"])
        if missing:
            return error_response(f"missing required key: {missing}", 400)

        if not validate_phone(data["phone_number"]):
            return error_response("Invalid phone number format", 400)

        err = validate_enum(data["profession"], ALLOWED_PROFESSIONS, "profession")
        if err:
            return error_response(err, 400)

        user = UserRepository.update_profile(
            user_id=user.id,
            phone_number=data["phone_number"].strip(),
            profession=data["profession"],
        )

        return success_response(
            data={
                "user_id": user.id,
                "phone_number": user.phone_number,
                "profession": user.profession,
                "is_verified": bool(getattr(user, "is_verified", False)),
            }
        )

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@auth_bp.route("/redirect_to_app", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def redirect_to_app():
    """This route is called after user finishes subscription, and now to be redirected to the app with a valid tokens
    It receives the email as input, checks if the user exists and is subscribed, then generates access and refresh tokens
    and redirects the user to the app subdomain after setting those tokens in cookies
    """

    try:
        # Auth payload is already validated by @require_role decorator
        current_user_id = getattr(request, "user_id", None)
        if not isinstance(current_user_id, int):
            return error_response("User not found", 404)
        user = UserRepository.get_by_id(current_user_id)
        if not user:
            return error_response("User not found", 404)

        user, active_subscription, _ = SubscriptionService.get_effective_access(user.id)
        if user.role not in ("subscribed", "admin"):
            return error_response("Active subscription required", 403)

        tokens = AuthService.issue_token_pair(user)
        AuthService.persist_refresh_token(
            user.id,
            token=tokens["refresh_token"],
            exp=tokens["refresh_token_exp"],
        )

        cookie_domain = FRONTEND_COOKIE_DOMAIN or None
        response = make_response(redirect(FRONTEND_REDIRECT_URL))
        response.set_cookie(
            "access_token",
            tokens["access_token"],
            expires=tokens["access_token_exp"],
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=cookie_domain,
            path="/",
        )
        response.set_cookie(
            "refresh_token",
            tokens["refresh_token"],
            expires=tokens["refresh_token_exp"],
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=cookie_domain,
            path="/",
        )

        return response

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
