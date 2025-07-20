# app/routes/myworker.py

from flask import Blueprint, jsonify, request
from api.db.connection import supabase
from api.classes.sync_facebook_scraper import FacebookPlaywrightScraper

fb_bp = Blueprint("facebook", __name__)
scraper = FacebookPlaywrightScraper(headless=True, slow_mo=500)


@fb_bp.route("/get_followers_and_likes", methods=["GET"])
async def get_engagement():
    
    url = request.args.get("url")
    result = await scraper.scrape_page(url)
    response = supabase.table("entities").select("*").execute()

    return jsonify({"result": result, "response": response.data})


@fb_bp.route("/get_all_followers_and_likes", methods=["GET"])
async def get_all_pages_engagement():
    # pages = [
    #     {"url": "https://web.facebook.com/sarl.cebon", "page_id": 2},
    #     {"url": "https://www.facebook.com/Aromes.Alimentaires", "page_id": 4}
    # ]
    
    # getting pages from supabase
    response = supabase.table("pages").select("*").execute()
    pages = response.data
    print(pages)
    results = []
    for page in pages:
        try:
            
            result = scraper.scrape_page(page["link"])
            results.append(result)
        except Exception as e:
            print(f"Error scraping {page['link']}: {str(e)}")
            continue
        
        insertion_response = supabase.table("influence_history").insert({"page_id": page["id"], "followers": result["followers"], "likes": result["likes"] }).execute()
        print(insertion_response)
    print(results)
    # response = supabase.table("influence_history").select("*").execute()

    return jsonify({"result": results, })


