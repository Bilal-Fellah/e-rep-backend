from flask import jsonify
from api.database.supabase_connection import supabase
import traceback
import random

pages_per_request = 5  # Number of pages to process per request

async def get_all_pages_engagement(platform, scraper=None):
    result_summary = {
        "scraped": [],
        "failed_scrape": [],
        "inserted": [],
        "failed_insert": [],
        "errors": []
    }

    try:
        response = supabase.rpc("get_scraped_pages", {"query_platform": platform}).execute()
        if not hasattr(response, "data"):
            return jsonify({"message": "No pages found.", "status": "no_data"}), 500
        
        data = response.data
        
        filtered_pages = [page for page in data if page.get("status") is None]
        if filtered_pages is None or len(filtered_pages) == 0:
            return jsonify({"message": "No pages found to scrape.", "status": "no_data"}), 500
        
        # Randomly shuffle the filtered pages
        random.shuffle(filtered_pages)

        # Pick the first 5 (or less if not enough pages)
        pages_to_process = filtered_pages[:pages_per_request]

    except Exception as e:
        error_details = traceback.format_exc()
        return jsonify({"message": "Error fetching or filtering pages.", "status": "error", "error": str(e), "traceback": error_details}), 500

    links = [page["link"] for page in pages_to_process]

    # Scrape followers
    try:
        # print("before scraping")
        results = await scraper.scrape_multiple_pages(links)
        # print("after scraping")
        if not results:
            return jsonify({"message": "Scraper returned no results.", "status": "scrape_failed"}), 500
    except Exception as e:
        error_details = traceback.format_exc()
        return jsonify({"message": "Error during scraping.", "error": str(e), "traceback": error_details}), 500

    # print(results)
    platform_field_map = {
    "facebook": "likes",
    "linkedin": "employees",
    "instagram": "posts"
    }

    # Process insertion per page
    for page in pages_to_process:
        try:
            matching_result = next((res for res in results if res["page_url"] == page["link"]), None)
            if matching_result:
                insertion_data = {
                    "page_id": page["page_id"],
                    "followers": matching_result["followers"],
                    f"{platform_field_map[platform]}": matching_result.get(platform_field_map[platform], None),
                    "status": "done"
                }
                insertion_response = supabase.table("influence_history").insert(insertion_data).execute()

                if hasattr(insertion_response,"data"):
                    result_summary["inserted"].append(page["page_id"])
                else:
                    result_summary["failed_insert"].append({
                        "page_id": page["page_id"],
                        "error": insertion_response.data
                    })
                result_summary["scraped"].append({
                    "page_id": page["page_id"],
                    "followers": matching_result["followers"]
                })
            else:
                # Scrape failure for this page
                insertion_data = {
                    "page_id": page["page_id"],
                    "followers": None,
                    "likes": None,
                    "status": "failure"
                }
                insertion_response = supabase.table("influence_history").insert(insertion_data).execute()

                result_summary["failed_scrape"].append({
                    "page_id": page["page_id"],
                    "reason": "No matching result from scraper",
                    "insertion_status": insertion_response.data["status"] 
                })

        except Exception as e:
            error_details = traceback.format_exc()
            result_summary["errors"].append({
                "page_id": page["page_id"],
                "error": str(e),
                "traceback": error_details
            })

    # Summary Response
    return jsonify({
        "summary": {
            "filtered_pages": len(filtered_pages),
            "pages_processed": len(pages_to_process),
            "successfully_scraped": len(result_summary["scraped"]),
            "failed_scrapes": len(result_summary["failed_scrape"]),
            "successful_inserts": len(result_summary["inserted"]),
            "failed_inserts": len(result_summary["failed_insert"]),
            "errors": len(result_summary["errors"])
        },
        "details": result_summary,
        "status": "success"
    }), 200
