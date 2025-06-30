import os
import re
import time
import random
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Union, Optional, Callable
from langdetect import detect
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import openai
import warnings
import platform

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Set your OpenAI API key
openai.api_key = "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"

class NovaClipScraper:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.driver = None
        self.output_dir = 'outputs/trends_data'
        os.makedirs(self.output_dir, exist_ok=True)
    
    def emit_log(self, message: str, log_type: str = 'info'):
        """Emit log message to frontend"""
        if self.socketio:
            self.socketio.emit('log', {'message': message, 'type': log_type})
        print(f"[{log_type.upper()}] {message}")
    
    def clean_name(self, name: str) -> str:
        """Clean and normalize names"""
        if not name:
            return ""
        name = re.sub(r"[^\w\s'\u00C0-\u017F]", "", str(name), flags=re.UNICODE)
        name = re.sub(r"(?<!\w)'(?!\w)", "", name)
        return re.sub(r"\s+", " ", name).strip()
    
    def is_person_openai(self, name: str) -> bool:
        """Use OpenAI to verify if name is a real person"""
        try:
            prompt = f"Is '{name}' the name of a real person in any language or culture? Reply only with 'Yes' or 'No'."
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=3,
            )
            answer = (response.choices[0].message.content or "").strip().lower()
            self.emit_log(f"🧠 GPT verification for '{name}': {answer}")
            return answer == "yes"
        except Exception as e:
            self.emit_log(f"❌ OpenAI error for '{name}': {e}", 'error')
            return False
    
    def configure_driver(self) -> webdriver.Chrome:
        """Configure Chrome WebDriver"""
        try:
            chromedriver_autoinstaller.install()
        except Exception as e:
            self.emit_log(f"⚠️ ChromeDriver installation warning: {e}", 'warning')
        
        chrome_options = Options()
        chrome_options.add_argument("--window-size=300,300")
        #chrome_options.add_argument("--headless=new")  # Run in headless mode for server
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        return webdriver.Chrome(options=chrome_options)
        
    
    def scrape_trends(self, driver: webdriver.Chrome, timeout: int = 30, max_names: int = 25, stop_check: Callable = None) -> set:
        """Scrape trending names from Google Trends TV with stop check"""
        names = set()
        start = time.time()
        
        while (time.time() - start) < timeout and len(names) < max_names:
            # Check for stop signal
            if stop_check and stop_check():
                self.emit_log("🛑 Scraping stopped by user", 'warning')
                break
                
            try:
                items = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.NJfIwe a.vcW2ic[jsname='thYVgf']"))
                )
                new_names = {self.clean_name(item.text) for item in items if item.text}
                names.update(new_names)
                
                self.emit_log(f"📊 Found {len(names)} unique names so far...")
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                self.emit_log(f"⚠️ Scraping iteration error: {e}", 'warning')
                break
        
        return names
    
    def get_wikipedia_summary(self, wiki_url: str) -> str:
        """Extract Wikipedia summary from URL"""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(wiki_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.select("div.mw-parser-output > p")
            
            full_text = ""
            for para in paragraphs:
                text = para.get_text(strip=True)
                if text:
                    full_text += text + "\n\n"
                if len(full_text.split()) > 800:
                    break
            
            return full_text.strip() if full_text else "Summary not available"
        except Exception as e:
            self.emit_log(f"❌ Error fetching Wikipedia summary: {e}", 'error')
            return "Summary not available"
    
    def extract_search_results(self, name: str, stop_check: Callable = None) -> Dict[str, Union[str, None]]:
        """Extract search results and Wikipedia info for a name with stop check"""
        driver = None
        try:
            # Check for stop signal before starting
            if stop_check and stop_check():
                return {
                    "result_count": "N/A",
                    "wiki_url": "N/A", 
                    "wiki_summary": "Summary not available"
                }
                
            driver = self.configure_driver()
            search_url = f"https://www.google.com/search?q={'+'.join(name.split())}&hl=en&gl=us"
            
            self.emit_log(f"🔍 Searching for: {name}")
            driver.get(search_url)
            wait = WebDriverWait(driver, 15)
            
            # Check for stop signal during processing
            if stop_check and stop_check():
                return {
                    "result_count": "N/A",
                    "wiki_url": "N/A",
                    "wiki_summary": "Summary not available"
                }
            
            # Click Tools button to get result stats
            try:
                tools_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Tools']")))
                tools_button.click()
                time.sleep(random.uniform(2, 4))
            except:
                pass  # Tools button might not be available
            
            # Get result count
            result_count = "0"
            try:
                result_stats = wait.until(EC.presence_of_element_located((By.ID, "result-stats")))
                raw_text = result_stats.text
                match = re.search(r'About ([\d,]+)', raw_text)
                result_count = match.group(1).replace(",", "") if match else "0"
            except:
                pass
            
            # Look for Wikipedia link
            wiki_url = "N/A"
            summary = "Summary not available"
            try:
                wiki_element = driver.find_element(By.XPATH, "//a[contains(@href, 'wikipedia.org')]")
                wiki_url = wiki_element.get_attribute("href")
                if wiki_url:
                    self.emit_log(f"📚 Wikipedia link found for {name}")
                    summary = self.get_wikipedia_summary(wiki_url)
            except:
                pass  # Wikipedia link not found
            
            return {
                "result_count": result_count,
                "wiki_url": wiki_url,
                "wiki_summary": summary
            }
            
        except Exception as e:
            self.emit_log(f"⚠️ Search error for {name}: {str(e)[:100]}...", 'warning')
            return {
                "result_count": "N/A",
                "wiki_url": "N/A",
                "wiki_summary": "Summary not available"
            }
        finally:
            if driver:
                driver.quit()
    
    def extract_and_save_trends(self, geo_region: str = 'US', stop_check: Callable = None) -> str:
        """Extract trending names and save to Excel file with stop check"""
        self.driver = None
        
        try:
            # Check for stop signal before starting
            if stop_check and stop_check():
                self.emit_log("🛑 Process stopped before starting trends extraction", 'warning')
                return ""
                
            self.driver = self.configure_driver()
            trends_url = f"https://trends.google.com/tv/?geo={geo_region}&rows=5&cols=5"
            
            self.emit_log(f"🌐 Loading Google Trends TV for {geo_region}...")
            self.driver.get(trends_url)
            
            self.emit_log("🔄 Scraping trending names...")
            names = self.scrape_trends(self.driver, stop_check=stop_check)
            
            # Check for stop signal after scraping
            if stop_check and stop_check():
                self.emit_log("🛑 Process stopped after scraping", 'warning')
                return ""
            
            if not names:
                self.emit_log("❌ No names collected", 'error')
                return ""
            
            self.emit_log(f"✅ Collected {len(names)} unique names")
            
            # Create DataFrame
            data = []
            for name in names:
                try:
                    data.append({
                        "Name": name,
                        "Search Results": np.nan,
                        "Wikipedia Link": "",
                        "Wiki_Summary": "",
                        "Is Person": "",
                        "GPT Verified": ""
                    })
                except Exception as e:
                    self.emit_log(f"⚠️ Name processing error: {e}", 'warning')
            
            # Save to Excel
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime("%d_%m_%Y_%I-%M%p")
            filename = os.path.join(self.output_dir, f"GTV_{geo_region}_{timestamp}.xlsx")
            df.to_excel(filename, index=False)
            
            self.emit_log(f"💾 Trends data saved: {os.path.basename(filename)}")
            return filename
            
        except Exception as e:
            self.emit_log(f"❌ Fatal scraping error: {e}", 'error')
            return ""
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def enrich_search_results(self, filename: str, stop_check: Callable = None, progress_callback: Callable = None) -> None:
        """Enrich trends data with search results and Wikipedia info with stop check"""
        if not os.path.exists(filename):
            self.emit_log(f"❌ File not found: {filename}", 'error')
            return
        
        try:
            df = pd.read_excel(filename)
            total = len(df)
            
            self.emit_log(f"🔍 Enriching {total} entries with search data...")
            
            for count, (idx, row) in enumerate(df.iterrows(), 1):
                # Check for stop signal at the beginning of each iteration
                if stop_check and stop_check():
                    self.emit_log(f"🛑 Enrichment stopped by user at {count}/{total}", 'warning')
                    break
                    
                name = row['Name']
                self.emit_log(f"🔍 Processing {count}/{total}: {name}")
                
                # Update progress if callback provided
                if progress_callback:
                    progress_callback(count / total)
                
                # Skip if already processed
                if pd.notna(row["Search Results"]) and row["Search Results"] not in ["", "N/A"]:
                    self.emit_log(f"✅ Row {count}/{total}: Already processed")
                    continue
                
                # Get search results with stop check
                results = self.extract_search_results(name, stop_check=stop_check)
                
                # Check for stop signal after search
                if stop_check and stop_check():
                    self.emit_log(f"🛑 Enrichment stopped during search for {name}", 'warning')
                    break
                
                df.at[idx, "Search Results"] = results.get("result_count", "N/A")
                df.at[idx, "Wikipedia Link"] = results.get("wiki_url", "N/A")
                df.at[idx, "Wiki_Summary"] = results.get("wiki_summary", "Summary not available")
                
                # Check if it's a person using OpenAI
                try:
                    search_result = int(str(df.at[idx, "Search Results"]).replace(",", ""))
                except ValueError:
                    search_result = 0
                
                # Only use OpenAI for names with reasonable search results
                if 1_000_000 <= search_result <= 20_000_000:
                    # Check for stop signal before OpenAI call
                    if stop_check and stop_check():
                        self.emit_log(f"🛑 Enrichment stopped before OpenAI verification for {name}", 'warning')
                        break
                        
                    self.emit_log(f"🤖 Asking OpenAI if '{name}' is a real person...")
                    gpt_result = self.is_person_openai(name)
                    df.at[idx, "GPT Verified"] = gpt_result
                    df.at[idx, "Is Person"] = gpt_result
                else:
                    df.at[idx, "GPT Verified"] = "Skipped: Threshold"
                    df.at[idx, "Is Person"] = False
                
                # Clear data for non-persons
                if not df.at[idx, "Is Person"]:
                    df.at[idx, "Search Results"] = search_result
                    df.at[idx, "Wikipedia Link"] = "Skipped: Threshold"
                    df.at[idx, "Wiki_Summary"] = "Skipped: Threshold"
                
                # Save progress
                df.to_excel(filename, index=False)
                
                # Check for stop signal before sleep
                if stop_check and stop_check():
                    self.emit_log(f"🛑 Enrichment stopped before sleep after {name}", 'warning')
                    break
                
                # Sleep to avoid rate limiting
                sleep_time = random.randint(5, 15)
                self.emit_log(f"⏳ Sleeping {sleep_time} seconds...")
                time.sleep(sleep_time)
            
            if not (stop_check and stop_check()):
                self.emit_log("✅ Enrichment complete!")
            
        except Exception as e:
            self.emit_log(f"❌ Enrichment failed: {e}", 'error')