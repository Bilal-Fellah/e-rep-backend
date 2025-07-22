from flask import  jsonify

def error_response(message, status=400):
    return jsonify({"success": False, "error": message}), status

def success_response(data, status_code=200):
    return {"success": True, "data": data}, status_code