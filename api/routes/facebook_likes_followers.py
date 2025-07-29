# app/routes/myworker.py

from flask import Blueprint, jsonify, request
from api.db.connection import supabase
from api.classes.facebook_playwrite_scraper import FacebookPlaywrightScraper

fb_bp = Blueprint("facebook", __name__)
scraper = FacebookPlaywrightScraper(headless=True, slow_mo=500)


@fb_bp.route("/get_followers_and_likes", methods=["GET"])
async def get_engagement():
    
    url = request.args.get("url")
    result = await scraper.scrape_page(url)
    insertion_response = supabase.table("influence_history").insert({"page_id": 2, "followers": result["followers"], "likes": result["likes"] }).execute()
    print(insertion_response)

    return jsonify({"result": result})


@fb_bp.route("/get_all_followers_and_likes", methods=["GET"])
async def get_all_pages_engagement():
   
    
    # getting pages from supabase
    response = supabase.table("pages").select("*").eq("platform", "facebook").execute()
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


