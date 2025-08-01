from flask import jsonify
from api.db.connection import supabase
import traceback
import random


async def get_all_pages_engagement(platform, scraper=None):
    result_summary = {
        "scraped": [],
        "failed_scrape": [],
        "inserted": [],
        "failed_insert": [],
        "errors": []
    }

    try:
        response = supabase.rpc("get_pages_to_scrape", {"query_platform": platform}).execute()
        if not hasattr(response, "data"):
            return jsonify({"message": "No pages found.", "status": "no_data"}), 500
        
        filtered_pages = response.data
        
        # Randomly shuffle the filtered pages
        random.shuffle(filtered_pages)

        # Pick the first 5 (or less if not enough pages)
        pages_to_process = filtered_pages[:2]

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
                    "page_id": page["page_id"],
                    "followers": matching_result["followers"],
                    "likes": matching_result.get("likes", None),
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
        "details": result_summary
    }), 200
