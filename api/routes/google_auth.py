from datetime import datetime, timedelta, timezone
import json
from flask import Flask, redirect, request, jsonify, Blueprint, make_response
from gotrue import datetime
import jwt
import requests
import os
from api.utils.auth import OAUTH_USERS_FILE
from api.repositories.user_repository import UserRepository

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


# 1️⃣ Start login (open this in browser)
@oauth_bp.route("/google/login")
def login_google():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    url = requests.Request("GET", GOOGLE_AUTH_URL, params=params).prepare().url
    return redirect(url)


# 2️⃣ Google redirects here
@oauth_bp.route("/google/callback")
def google_callback():
    code = request.args.get("code")

    if not code:
        return jsonify({"error": "No code returned"}), 400

    # 3 Exchange code for token
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

    # 4️⃣ Fetch user info
    userinfo_res = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    )

    userinfo = userinfo_res.json()
    
    user =  UserRepository.find_by_email(userinfo["email"])
    if not user:
        user = UserRepository.create_user(
            first_name=userinfo.get("given_name", ""),
            last_name=userinfo.get("family_name", ""),
            email=userinfo["email"],
            password="",  # No password since it's OAuth
            role="registered"
        )

    # Access token (1 day)
    access_token_exp = datetime.now(timezone.utc) + timedelta(days=1)
    access_payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": access_token_exp
    }
    access_token = jwt.encode(access_payload, SECRET, algorithm="HS256")
    
    # Refresh token (30 days)
    refresh_token_exp = datetime.now(timezone.utc) + timedelta(days=30)
    refresh_payload = {
        "user_id": user.id,
        "exp": refresh_token_exp
    }
    refresh_token = jwt.encode(refresh_payload, SECRET, algorithm="HS256")

    # Save refresh token & expiry in DB
    UserRepository.update_refresh_token(
        user.id,
        token=refresh_token,
        exp=refresh_token_exp
    )

    frontend_url = 'https://brendex.net'

    response = make_response(redirect(frontend_url))

    # Access token (short-lived)
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=True,
        samesite="None",   # REQUIRED since frontend is another domain
        max_age= 24*60 * 60   # 1 day
    )

    # Refresh token (long-lived)
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="None",
        max_age=30 * 24 * 60 * 60  # 30 days
    )

    # Optional: non-sensitive info (can be readable by JS)
    response.set_cookie(
        "user_role",
        user.role,
        secure=True,
        samesite="None"
    )

    response.set_cookie(
        "user_id",
        str(user.id),
        secure=True,
        samesite="None"
    )

    return response




