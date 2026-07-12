# Route wiring for google auth endpoints.
from datetime import datetime, timedelta, timezone
from flask import redirect, request, Blueprint, session
import jwt
import requests
import os
from api.repositories.user_repository import UserRepository
import secrets
from api.routes.main import error_response, success_response, register_blueprint_error_handlers
from api.utils.login_codes_utils import store_login_code, consume_login_code



SECRET = os.environ.get("SECRET_KEY")
oauth_bp = Blueprint("oauth", __name__)

register_blueprint_error_handlers(oauth_bp)

# 🔑 From Google Console
GOOGLE_CLIENT_ID =  os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000")
FRONTEND_REDIRECT_URL = os.environ.get("FRONTEND_REDIRECT_URL", "https://www.brendex.net")

ALLOWED_RETURN_URLS = {
    url.strip()
    for url in os.environ.get("ALLOWED_OAUTH_RETURN_URLS", "").split(",")
    if url.strip()
}

if not ALLOWED_RETURN_URLS:
    ALLOWED_RETURN_URLS = {
        FRONTEND_REDIRECT_URL,
        "https://www.brendex.net",
        "https://brendex.net",
        "http://localhost:3000",
        "http://localhost:5000",
    }

# Must match Google Console redirect URI
REDIRECT_URI = f"{BACKEND_URL}/api/oauth/google/callback"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@oauth_bp.route("/google/login")
def login_google():
    return_to = request.args.get("return_to", FRONTEND_REDIRECT_URL)
    if return_to not in ALLOWED_RETURN_URLS:
        return error_response("Invalid return_to", 400)

    state = secrets.token_urlsafe(32)

    # login
    session["oauth_state"] = state
    session["return_to"] = return_to


    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    url = requests.Request("GET", GOOGLE_AUTH_URL, params=params).prepare().url
    return redirect(url)


@oauth_bp.route("/google/callback")
def google_callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return error_response("Missing code or state", 400)

    # callback
    if state != session.get("oauth_state"):
        return error_response("Invalid or expired state", 400)

    return_to = session.pop("return_to", FRONTEND_REDIRECT_URL)
    session.pop("oauth_state", None)
    if return_to not in ALLOWED_RETURN_URLS:
        return_to = FRONTEND_REDIRECT_URL
   
    # --- everything below stays the same ---
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        token_res = requests.post(GOOGLE_TOKEN_URL, data=token_data, timeout=15)
    except requests.RequestException:
        return error_response("Google authentication failed", 502)

    if token_res.status_code >= 400:
        return error_response("Google authentication failed", 502)

    token_json = token_res.json()

    if "access_token" not in token_json:
        return error_response("Google authentication failed", 400)

    access_token = token_json["access_token"]

    try:
        userinfo_res = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    except requests.RequestException:
        return error_response("Google authentication failed", 502)

    if userinfo_res.status_code >= 400:
        return error_response("Google authentication failed", 502)

    userinfo = userinfo_res.json()
    if "email" not in userinfo:
        return error_response("Google authentication failed", 502)

    user = UserRepository.find_by_email(userinfo["email"])
    if not user:
        user = UserRepository.create_user(
            first_name=userinfo.get("given_name", ""),
            last_name=userinfo.get("family_name", ""),
            email=userinfo["email"],
            password="",
            role="registered",
            is_verified=False
        )

    # 🔑 generate temporary login code
    login_code = secrets.token_urlsafe(32)
    store_login_code(login_code, user.id)


    return redirect(f"{return_to}/auth/complete?code={login_code}")


@oauth_bp.route("/google/finalize", methods=["POST"])
def finalize_google_login():
    body = request.get_json(silent=True) or {}
    code = body.get("code")
    if not code:
        return error_response("Missing code", 400)

    code_data = consume_login_code(code)
    if not code_data:
        return error_response("Invalid or expired code", 400)

    user_id = code_data["user_id"]


    user = UserRepository.get_by_id(int(user_id))
    if not user:
        return error_response("User not found", 404)

    # --- unchanged JWT logic ---
    access_token_exp = datetime.now(timezone.utc) + timedelta(days=1)
    access_payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": access_token_exp
    }
    access_token = jwt.encode(access_payload, SECRET, algorithm="HS256")

    refresh_token_exp = datetime.now(timezone.utc) + timedelta(days=30)
    refresh_payload = {
        "user_id": user.id,
        "exp": refresh_token_exp
    }
    refresh_token = jwt.encode(refresh_payload, SECRET, algorithm="HS256")

    UserRepository.update_refresh_token(
        user.id,
        token=refresh_token,
        exp=refresh_token_exp
    )

    

    response = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_role": user.role,
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "role": user.role,
                "is_verified": bool(getattr(user, "is_verified", False)),
                "profession": user.profession,
                "created_at": user.created_at.isoformat()
            }
    }

    return success_response(response, status_code=200)
