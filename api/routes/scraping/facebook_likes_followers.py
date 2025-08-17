
from flask import Blueprint
from api.classes.facebook_playwrite_scraper import FacebookPlaywrightScraper
from api.routes.data.scraping.get_engagement import get_all_pages_engagement

fb_bp = Blueprint("facebook", __name__)
scraper = FacebookPlaywrightScraper(headless=True, slow_mo=500)




@fb_bp.route("/get_all_followers_and_likes", methods=["GET"])
async def response():
    return await get_all_pages_engagement(platform="facebook", scraper=scraper)
