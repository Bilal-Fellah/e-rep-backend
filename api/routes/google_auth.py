from datetime import datetime, timedelta, timezone
from flask import redirect, request, jsonify, Blueprint,  session
from datetime import datetime
import jwt
import requests
import os
from api.repositories.user_repository import UserRepository
import secrets
from api.utils.login_codes_utils import store_login_code, consume_login_code



SECRET = os.environ.get("SECRET_KEY")
oauth_bp = Blueprint("oauth", __name__)

# 🔑 From Google Console
GOOGLE_CLIENT_ID =  os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000")
# Must match Google Console redirect URI
REDIRECT_URI = f"{BACKEND_URL}/api/oauth/google/callback"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@oauth_bp.route("/google/login")
def login_google():
    return_to = request.args.get("return_to")

    # ALLOWED_RETURN_URLS = {
    #     "https://www.brendex.net",
    #     "https://brendex.net",
    # }

    # if return_to not in ALLOWED_RETURN_URLS:
    #     return jsonify({"error": "Invalid return_to"}), 400

    state = secrets.token_urlsafe(32)

    # login
    session["oauth_state"] = state
    session["return_to"] = return_to

    print("SET STATE:", state)
    print("SESSION:", dict(session))


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
        return jsonify({"error": "Missing code or state"}), 400

    # callback
    if state != session.get("oauth_state"):
        return jsonify({"error": "Invalid or expired state"}), 400

    return_to = session.pop("return_to")
    session.pop("oauth_state")

    print("CALLBACK STATE:", state)
    print("SESSION:", dict(session))
   
    # --- everything below stays the same ---
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_res = requests.post(GOOGLE_TOKEN_URL, data=token_data)
    token_json = token_res.json()

    if "access_token" not in token_json:
        return jsonify(token_json), 400

    access_token = token_json["access_token"]

    userinfo_res = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    )

    userinfo = userinfo_res.json()

    user = UserRepository.find_by_email(userinfo["email"])
    if not user:
        user = UserRepository.create_user(
            first_name=userinfo.get("given_name", ""),
            last_name=userinfo.get("family_name", ""),
            email=userinfo["email"],
            password="",
            role="registered"
        )

    # 🔑 generate temporary login code
    login_code = secrets.token_urlsafe(32)
    store_login_code(login_code, user.id)


    return redirect(f"{return_to}/auth/complete?code={login_code}")


@oauth_bp.route("/google/finalize", methods=["POST"])
def finalize_google_login():
    code = request.json.get("code")

    code_data = consume_login_code(code)
    if not code_data:
        return jsonify({"error": "Invalid or expired code"}), 400

    user_id = code_data["user_id"]


    user = UserRepository.find_by_id(int(user_id))

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

    response = jsonify({"success": True})

    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=True,
        samesite="None",
        domain=".brendex.net",
        max_age=86400
    )

    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="None",
        domain=".brendex.net",
        max_age=30 * 86400
    )

    return response
