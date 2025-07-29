# app/routes/myworker.py

from flask import Blueprint, jsonify, request
from api.db.connection import supabase
from api.classes.linkedin_playwright_scraper import LinkedInPlaywrightScraper
import traceback
import random



linkedin_bp = Blueprint("linkedin", __name__)
scraper = LinkedInPlaywrightScraper(headless=True, slow_mo=500)


@linkedin_bp.route("/get_followers", methods=["GET"])
async def get_engagement():
    
    url = request.args.get("url")
    urls = [url]
    result = await scraper.scrape_multiple_pages(urls)
    print(result)
    # response = supabase.table("entities").select("*").execute()

    # return jsonify({"result": result, "response": response.data})
    return jsonify({"result": result})




@linkedin_bp.route("/get_all_followers", methods=["GET"])
async def get_all_pages_engagement():
    result_summary = {
        "scraped": [],
        "failed_scrape": [],
        "inserted": [],
        "failed_insert": [],
        "errors": []
    }

    try:
        # Fetch a large enough sample (say 50 pages) to allow randomness
        response = supabase.from_("pages") \
            .select("id, platform, link, influence_history(page_id, status)") \
            .eq("platform", "linkedin") \
            .execute()
            # .range(0, 49) \

        pages = response.data
        # print(f"Total pages fetched: {len(pages)}")

        print(pages)
        # Filter pages where influence_history.status != 'done'
        filtered_pages = []
        for page in pages:
            influence_histories = page.get("influence_history", [])
            if influence_histories==[] or any(not history.get("status") or history.get("status") != "done" for history in influence_histories):
                filtered_pages.append(page)

        print(f"Filtered pages (before random sampling): {len(filtered_pages)}")

        if not filtered_pages:
            return jsonify({"message": "No LinkedIn pages found.", "status": "no_data"}), 404

        # Randomly shuffle the filtered pages
        random.shuffle(filtered_pages)

        # Pick the first 10 (or less if not enough pages)
        pages_to_process = filtered_pages[:5]

    except Exception as e:
        error_details = traceback.format_exc()
        return jsonify({"message": "Error fetching or filtering pages.", "error": str(e), "traceback": error_details}), 500

    links = [page["link"] for page in pages_to_process]

    # Scrape followers
    try:
        results = await scraper.scrape_multiple_pages(links)
        if not results:
            return jsonify({"message": "Scraper returned no results.", "status": "scrape_failed"}), 500
    except Exception as e:
        error_details = traceback.format_exc()
        return jsonify({"message": "Error during scraping.", "error": str(e), "traceback": error_details}), 500

    # print(results)

    # Process insertion per page
    for page in pages_to_process:
        try:
            matching_result = next((res for res in results if res["page_url"] == page["link"]), None)
            if matching_result:
                insertion_data = {
                    "page_id": page["id"],
                    "followers": matching_result["followers"],
                    "status": "done"
                }
                insertion_response = supabase.table("influence_history").insert(insertion_data).execute()

                if insertion_response.status_code == 201:
                    result_summary["inserted"].append(page["id"])
                else:
                    result_summary["failed_insert"].append({
                        "page_id": page["id"],
                        "error": insertion_response.data
                    })
                result_summary["scraped"].append({
                    "page_id": page["id"],
                    "followers": matching_result["followers"]
                })
            else:
                # Scrape failure for this page
                insertion_data = {
                    "page_id": page["id"],
                    "followers": None,
                    "status": "failure"
                }
                insertion_response = supabase.table("influence_history").insert(insertion_data).execute()

                result_summary["failed_scrape"].append({
                    "page_id": page["id"],
                    "reason": "No matching result from scraper",
                    "insertion_status": insertion_response.status_code
                })

        except Exception as e:
            error_details = traceback.format_exc()
            result_summary["errors"].append({
                "page_id": page["id"],
                "error": str(e),
                "traceback": error_details
            })

    # Summary Response
    return jsonify({
        "summary": {
            "total_pages_fetched": len(pages),
            "filtered_pages": len(filtered_pages),
            "pages_processed": len(pages_to_process),
            "successfully_scraped": len(result_summary["scraped"]),
            "failed_scrapes": len(result_summary["failed_scrape"]),
            "successful_inserts": len(result_summary["inserted"]),
            "failed_inserts": len(result_summary["failed_insert"]),
            "errors": len(result_summary["errors"])
        },
        "details": result_summary
    }), 200
