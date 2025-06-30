import os
import re
import json
import time
import requests
import pandas as pd
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from typing import List
from googleapiclient.discovery import build


class NovaClipImageGenerator:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.output_dir = 'outputs/images'
        self.api_key = "AIzaSyCXVNZjrHkmf65kFsMUThLe9_vGAe6ih7k"  # Replace with your actual Google API key
        self.cse_id = "a71b1ebb654dc4e4b"   # Replace with your actual Custom Search Engine ID
        self.credits_file = os.path.join(self.output_dir, "image_credits.json")
        self.stop_processing = False

        # Quality control settings
        self.MIN_RESOLUTION = (960, 640)
        self.DELAY_BETWEEN_REQUESTS = 2.0
        self.MAX_API_CALLS = 60
        self.RETRY_FAILED_DOWNLOADS = True
        self.WHITELISTED_SIZES = [(1080, 1350), (1080, 1080), (1280, 720)]

        os.makedirs(self.output_dir, exist_ok=True)

    def emit_log(self, message: str, log_type: str = 'info'):
        if self.socketio:
            self.socketio.emit('log', {'message': message, 'type': log_type})
        print(f"[{log_type.upper()}] {message}")

    def check_stop_signal(self):
        return self.stop_processing

    def filter_valid_rows(self, input_file: str) -> pd.DataFrame:
        df = pd.read_excel(input_file)
        df["Search Results"] = pd.to_numeric(df["Search Results"], errors="coerce")
        self.emit_log("📊 Filtering: persons with 1M-20M search results")
        filtered_df = df[(df["Is Person"] == True) & (df["Search Results"].between(1_000_000, 20_000_000))]
        self.emit_log(f"✅ Found {len(filtered_df)} valid entries for image generation")
        return filtered_df

    def download_image(self, url: str, filepath: str) -> bool:
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            response.raise_for_status()

            img = Image.open(BytesIO(response.content))
            img.verify()
            img = Image.open(BytesIO(response.content))

            # Whitelisted size bypass
            if (img.width, img.height) in self.WHITELISTED_SIZES:
                self.emit_log(f"[✓] Accepted whitelisted size: {img.width}x{img.height}", 'info')
                img.convert("RGB").save(filepath, "JPEG", quality=95)
                return True

            # Check resolution
            if img.width < self.MIN_RESOLUTION[0] or img.height < self.MIN_RESOLUTION[1]:
                self.emit_log(f"[!] Skipping low-res: {img.size[0]}x{img.size[1]}", 'warning')
                return False

            # Check aspect ratio
            aspect_ratio = img.width / img.height
            if not (0.8 < aspect_ratio < 2.0):
                self.emit_log(f"[!] Skipping bad aspect ratio: {aspect_ratio:.2f} ({img.size[0]}x{img.size[1]})", 'warning')
                return False

            img.convert("RGB").save(filepath, "JPEG", quality=95)
            self.emit_log(f"[✓] Saved: {os.path.basename(filepath)} ({img.size[0]}x{img.size[1]})")
            return True

        except UnidentifiedImageError:
            self.emit_log(f"[!] Corrupt or unknown image format at {url}", 'warning')
            return False
        except Exception as e:
            self.emit_log(f"[!] Failed to download {url}: {str(e)}", 'warning')
            return False

    def search_and_save_images(self, query: str, count: int = 20) -> bool:
        if self.check_stop_signal():
            return False

        try:
            service = build("customsearch", "v1", developerKey=self.api_key)
            saved_credits = []
            api_calls = 0
            saved_count = 0

            safe_name = re.sub(r"[^\w\s]", "", query).strip().lower().replace(" ", "_")
            image_dir = os.path.join(self.output_dir, f"{safe_name}_images")
            os.makedirs(image_dir, exist_ok=True)

            self.emit_log(f"🖼️ Searching for {count} high-quality images of: {query}")

            for i in range(count):
                if self.check_stop_signal():
                    self.emit_log("⛔ Image generation stopped by user", 'warning')
                    break

                time.sleep(self.DELAY_BETWEEN_REQUESTS)
                size_params = ["XXLARGE", "LARGE", ""]
                res = None

                for size_param in size_params:
                    try:
                        params = {
                            "q": query,
                            "cx": self.cse_id,
                            "searchType": "image",
                            "num": 1,
                            "start": i + 1,
                            "fileType": "jpg|png"
                        }
                        if size_param:
                            params["imgSize"] = size_param

                        res = service.cse().list(**params).execute()
                        api_calls += 1
                        break
                    except Exception as e:
                        self.emit_log(f"[!] API call failed with size {size_param}: {str(e)}", 'warning')
                        continue

                if res is None:
                    self.emit_log("[!] All API calls failed for this query", 'error')
                    break

                items = res.get("items", [])
                if not items:
                    self.emit_log("[!] No more results from Google", 'warning')
                    break

                item = items[0]
                img_url = item["link"]
                source_url = item.get("image", {}).get("contextLink", img_url)

                url_variations = [
                    img_url.split("=s")[0] + "=s0" if "=s" in img_url else img_url,
                    img_url,
                    source_url
                ]

                filename = f"{safe_name}_{saved_count + 1}.jpg"
                filepath = os.path.join(image_dir, filename)
                download_success = False

                for url in url_variations:
                    if self.download_image(url, filepath):
                        saved_credits.append({
                            "filename": filename,
                            "query": query,
                            "image_url": url,
                            "source": source_url,
                            "resolution": f"{Image.open(filepath).size[0]}x{Image.open(filepath).size[1]}",
                            "downloaded_at": pd.Timestamp.now().isoformat()
                        })
                        saved_count += 1
                        download_success = True
                        break

                if not download_success:
                    self.emit_log(f"[!] Failed to download any variation for image {i+1}", 'warning')

                if (i + 1) % 5 == 0:
                    self.emit_log(f"📥 Downloaded {saved_count}/{i + 1} images for {query}")

            if saved_credits and not self.check_stop_signal():
                try:
                    existing_credits = []
                    if os.path.exists(self.credits_file):
                        with open(self.credits_file, "r", encoding="utf-8") as f:
                            existing_credits = json.load(f)

                    existing_credits.extend(saved_credits)

                    with open(self.credits_file, "w", encoding="utf-8") as f:
                        json.dump(existing_credits, f, indent=2, ensure_ascii=False)

                except Exception as e:
                    self.emit_log(f"⚠️ Could not save image credits: {e}", 'warning')

            if not self.check_stop_signal():
                self.emit_log(f"✅ Successfully downloaded {saved_count}/{count} high-quality images for {query}")

            return saved_count > 0

        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Image search failed for {query}: {e}", 'error')
            return False

    def generate_images_from_file(self, input_file: str) -> bool:
        if self.check_stop_signal():
            return False

        try:
            df = self.filter_valid_rows(input_file)

            if df.empty:
                self.emit_log("⚠️ No valid entries found for image generation", 'warning')
                return False

            total_entries = len(df)
            success_count = 0

            for idx, (_, row) in enumerate(df.iterrows(), 1):
                if self.check_stop_signal():
                    self.emit_log("⛔ Image generation stopped by user", 'warning')
                    break

                name = row['Name']
                self.emit_log(f"🖼️ Generating images {idx}/{total_entries}: {name}")

                if self.search_and_save_images(name, count=20):
                    success_count += 1

            if not self.check_stop_signal():
                self.emit_log(f"✅ Image generation completed: {success_count}/{total_entries} successful")

            return success_count > 0

        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Image generation failed: {e}", 'error')
            return False

    def generate_images_for_name(self, name: str, count: int = 20) -> bool:
        if self.check_stop_signal():
            return False

        try:
            self.emit_log(f"🖼️ Generating {count} high-quality images for: {name}")
            return self.search_and_save_images(name, count)
        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Single image generation failed: {e}", 'error')
            return False
