# app/routes/myworker.py

from flask import Blueprint, jsonify, request
from api.classes.facebook_playwrite_scraper import FacebookPlaywrightScraper

fb_bp = Blueprint("facebook", __name__)
scraper = FacebookPlaywrightScraper(headless=True, slow_mo=500)


@fb_bp.route("/get_followers_and_likes", methods=["GET"])
async def get_engagement():
    
    url = request.args.get("url")
    result = await scraper.scrape_page(url)
    return jsonify({"result": result})


