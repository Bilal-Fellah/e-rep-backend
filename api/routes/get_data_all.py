
import os
from flask import Blueprint, request, jsonify
from api.database.supabase_connection import supabase
from api.classes.BD_scraper import BrightDataScraper
import json
from datetime import datetime

all_data_bp = Blueprint("all_data", __name__)
scraper = BrightDataScraper()




@all_data_bp.route("/get_all_data", methods=["POST"])
async def response():
    request_data = request.get_json()
    platform = request_data.get("platform")
    print(platform)

    pages_response = supabase.table("pages").select("*").eq("platform", platform).execute()
    pages = pages_response.data if hasattr(pages_response, "data") else []
    pages_links = [page.get("link", None) for page in pages ]

    print(f" pages: {len(pages)}", pages_links[0])
    snapshot_id = scraper.trigger_collection(
        platform,
        pages_links,
        {"country": ""}
    )
    scraper.wait_until_ready(snapshot_id, 15)

    results = scraper.download_results(snapshot_id, fmt="json")

    print(f"pages: {len(pages_links)} and results: {len(results)}")
    # Ensure folder exists
    os.makedirs("api/data", exist_ok=True)

    # Create timestamped filename
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"api/data/{platform}_{current_datetime}.json"

    # Save results to file
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Return JSON response
    return jsonify(results)
