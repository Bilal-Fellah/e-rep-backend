
from flask import Blueprint
from api.classes.linkedin_playwright_scraper import LinkedInPlaywrightScraper


from api.routes.data.scraping.get_engagement import get_all_pages_engagement



linkedin_bp = Blueprint("linkedin", __name__)
scraper = LinkedInPlaywrightScraper(headless=True, slow_mo=500)





@linkedin_bp.route("/get_all_followers", methods=["GET"])
async def response():
    return await get_all_pages_engagement(platform="linkedin", scraper=scraper)