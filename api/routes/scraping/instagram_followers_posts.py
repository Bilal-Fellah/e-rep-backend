
from flask import Blueprint
from api.classes.instagram_playwright_scraper import InstagramPlaywrightScraper


from api.routes.data.scraping.get_engagement import get_all_pages_engagement

username = "skwappw618@gmail.com"
password = "lolololo618"

instagram_bp = Blueprint("instagram", __name__)
scraper = InstagramPlaywrightScraper( 
        headless=True, 
        slow_mo=300, 
        username=username if username else None,
        password=password if password else None
        )





@instagram_bp.route("/get_all_followers_and_posts", methods=["GET"])
async def response():
    return await get_all_pages_engagement(platform="instagram", scraper=scraper)