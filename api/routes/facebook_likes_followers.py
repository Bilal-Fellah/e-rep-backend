# app/routes/myworker.py

from flask import Blueprint, jsonify, request
from api.db.connection import supabase
from api.classes.facebook_playwrite_scraper import FacebookPlaywrightScraper
from api.routes.data.scraping.get_engagement import get_all_pages_engagement

fb_bp = Blueprint("facebook", __name__)
scraper = FacebookPlaywrightScraper(headless=True, slow_mo=500)


@fb_bp.route("/get_followers_and_likes", methods=["GET"])
async def get_engagement():
    
    url = request.args.get("url")
    urls = [url]
    result = await scraper.scrape_multiple_pages(urls)
    insertion_response = supabase.table("influence_history").insert({"page_id": 2, "followers": result["followers"], "likes": result["likes"] }).execute()
    print(insertion_response)

    return jsonify({"result": result})


@fb_bp.route("/get_all_followers_and_likes", methods=["GET"])
async def response():
    return await get_all_pages_engagement(platform="facebook", scraper=scraper)
