import time
import os
import requests
from dotenv import load_dotenv

load_dotenv()  

class BrightDataScraper:
    def __init__(self):
        self.api_key = os.getenv("BD_API_KEY")
        self.api_base = f"{os.getenv('BD_URL')}/datasets/v3"

        if not self.api_key or not self.api_base:
            raise ValueError("Missing BD_API_KEY or BD_URL in environment variables.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        self.PLATFORM_CONFIG = {
            "tiktok": {
                "dataset_id": "gd_l1villgoiiidt09ci",
                "required_fields": ["url", "country"]
            },
            "instagram": {
                "dataset_id": "gd_l1vikfch901nx3by4",
                "required_fields": ["url"]
            },
            "linkedin": {
                "dataset_id": "gd_l1vikfnt1wgvvqz95w",
                "required_fields": ["url"]
            },
            "twitter": {
                "dataset_id": "gd_lwxmeb2u1cniijd7t4",
                "required_fields": ["url", "max_number_of_posts"]
            },
             "youtube": {  
                "dataset_id": "gd_lk538t2k2p1k3oos71",
                "required_fields": ["url"]
            }
        }

    def prepare_data(self, platform: str, urls: list, extra_info: dict = None) -> list:
        if extra_info is None:
            extra_info = {}

        if platform not in self.PLATFORM_CONFIG:
            raise ValueError(f"Unsupported platform: {platform}")

        config = self.PLATFORM_CONFIG[platform]
        data = []
        for url in urls:
            entry = {"url": url}
            if "country" in config["required_fields"]:
                entry["country"] = extra_info.get("country", "")
            if "max_number_of_posts" in config["required_fields"]:
                entry["max_number_of_posts"] = extra_info.get("max_number_of_posts", 10)
            data.append(entry)
        return data

    def trigger_collection(self, platform: str, urls: list, extra_info: dict = None) -> str:
        config = self.PLATFORM_CONFIG[platform]
        params = {
            "dataset_id": config["dataset_id"],
            "include_errors": "true",
        }
        data = self.prepare_data(platform, urls, extra_info)
        response = requests.post(f"{self.api_base}/trigger", headers=self.headers, params=params, json=data)
        result = response.json()
        snapshot_id = result.get("snapshot_id")
        if not snapshot_id:
            raise ValueError(f"Failed to trigger collection: {result}")
        print(f"[INFO] Triggered collection. Snapshot ID: {snapshot_id}")
        return snapshot_id

    def wait_until_ready(self, snapshot_id: str, check_interval: int = 10) -> None:
        url = f"{self.api_base}/progress/{snapshot_id}"
        while True:
            response = requests.get(url, headers=self.headers).json()
            status = response.get("status")
            print(f"[INFO] Status: {status}")
            if status == "ready":
                break
            elif status == "failed":
                raise RuntimeError("Data collection failed.")
            time.sleep(check_interval)

    def download_results(self, snapshot_id: str, fmt: str = "json") -> dict:
        url = f"{self.api_base}/snapshot/{snapshot_id}"
        params = {"format": fmt}
        response = requests.get(url, headers=self.headers, params=params)
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            return {"error": "Invalid JSON", "raw": response.text}


if __name__ == "__main__":
    scraper = BrightDataScraper()

    snapshot_id = scraper.trigger_collection(
        "tiktok",
        ["https://www.tiktok.com/@aymenbnroff", "https://www.tiktok.com/@brahim.sd"],
        {"country": ""}
    )

    scraper.wait_until_ready(snapshot_id, 15)

    results = scraper.download_results(snapshot_id, fmt="json")
    print(results)
