import json
from flask import Flask, redirect, request, jsonify, Blueprint
import requests
import os

import urllib
from api.utils.auth import OAUTH_USERS_FILE
from api.repositories.user_repository import UserRepository

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
    
    with open(OAUTH_USERS_FILE, "r+") as f:
        users = json.load(f)

        users.append(userinfo)
        f.seek(0)
        json.dump(users, f, indent=4)

    frontend_url = (
        "https://brendex.net"
        )
    return redirect(frontend_url)




