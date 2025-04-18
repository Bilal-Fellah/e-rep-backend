from flask import Blueprint, jsonify, request

callback_bp = Blueprint('facebook_call_back', __name__, url_prefix='/facebook_call_back')

@callback_bp.route('/', methods=["GET", "POST"])
def callback():
    # secret_key = 'suuuuuuuppa'
    # print('facebook has callbacked us!')
    # return jsonify({'message': 'Hello from callback!'})
    if request.method == 'GET':
        verify_token = "SUUUPPA77"
        if request.args.get("hub.verify_token") == verify_token:
            return request.args.get("hub.challenge")
        return "Verification failed", 403
    elif request.method == 'POST':
        data = request.json
        print("Received Webhook Data:", data)
        return "OK", 200


@callback_bp.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    return f"Received code: {code}"