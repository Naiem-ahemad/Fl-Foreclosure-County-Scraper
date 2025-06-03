import os
import time
import subprocess
import contextlib
import pandas as pd
from selenium import webdriver
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup date
yesterday = datetime.now() - timedelta(days=1)
AUCTION_DATE = yesterday.strftime("%m/%d/%Y")
FOLDER_NAME = AUCTION_DATE.replace("/", "-")
os.makedirs(FOLDER_NAME, exist_ok=True)

def get_driver():
    options = Options()
    service = Service()
    options.add_argument("--disable-gpu")
    options.add_argument("--start-minimized") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")  # Suppress Chrome internal logs
    options.add_experimental_option("excludeSwitches", ["enable-logging"]) # Suppress DevTools logs
    service.creation_flags = subprocess.CREATE_NO_WINDOW

    service = Service(log_path=os.devnull)  # Silence ChromeDriver output

    # Suppress all stdout/stderr (covers underlying native libs like TensorFlow Lite)
    with open(os.devnull, 'w') as fnull, contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
        driver = webdriver.Chrome(options=options, service=service)
        driver.minimize_window()
    return driver

def scrape_auctions_on_page(driver, county_name):
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[id^="AITEM_"]')))
    auction_boxes = driver.find_elements(By.CSS_SELECTOR, 'div[id^="AITEM_"]')
    print(f"✅ Found {len(auction_boxes)} auction boxes on current page.")
    all_data = []

    for idx, box in enumerate(auction_boxes, 1):
        entry = {
            
            "Auction Sold": "",
            "Amount": "",
            "Sold To": "",
            "Case #": "",
            "Parcel ID": "",
            "Property Address": "",
            "Final Judgment Amount": "",
            "Assessed Value": "",
            "Plaintiff Max Bid": "",
            "Opening Bid":"",
            "Auction Type":""
        }

        try:
            # --- Extract auction status block ---
            stat_labels = box.find_elements(By.CSS_SELECTOR, ".AUCTION_STATS .ASTAT_LBL")
            stat_values = box.find_elements(By.CSS_SELECTOR, ".AUCTION_STATS .Astat_DATA")

            for label, value in zip(stat_labels, stat_values):
                key = label.text.strip()
                val = value.text.strip()

                if "Auction Sold" in key:
                    entry["Auction Sold"] = val
                elif "Amount" in key and "Max Bid" not in key:
                    entry["Amount"] = val
                elif "Sold To" in key:
                    entry["Sold To"] = val

            # --- Extract auction detail block ---
            labels = box.find_elements(By.CSS_SELECTOR, ".AUCTION_DETAILS .AD_LBL")
            values = box.find_elements(By.CSS_SELECTOR, ".AUCTION_DETAILS .AD_DTA")

            address_buffer = ""

            for label, value in zip(labels, values):
                key = label.text.strip().rstrip(":")
                val = value.text.strip()

                if key == "Case #":
                    entry["Case #"] = val
                elif key == "Parcel ID":
                    entry["Parcel ID"] = val
                elif key == "Auction Type":
                    entry["Auction Type"] = val
                elif key == "Opening Bid":
                    entry["Opening Bid"] = val
                elif key == "Property Address":
                    address_buffer = val  # We'll add city/state later
                elif key == "" and val:
                    if address_buffer:
                        entry["Property Address"] = f"{address_buffer}, {val}"
                        address_buffer = ""
                elif "Final Judgment" in key:
                    entry["Final Judgment Amount"] = val
                elif "Assessed Value" in key:
                    entry["Assessed Value"] = val
                elif "Max Bid" in key:
                    entry["Plaintiff Max Bid"] = val

            # If city/state never showed up as empty-label but address_buffer is not empty
            if address_buffer:
                  entry["Property Address"] = address_buffer

            all_data.append(entry)

        except Exception as e:
            print(f"[!] Error parsing box {idx}: {e}")
            continue

    return all_data

def click_next_page(driver, wait):
    try:
        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="BID_WINDOW_CONTAINER"]/div[4]/div[6]/span[5]')))
        driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", next_button)
        return True
    except Exception as e:
        print(f"[-] Pagination failed: {e}")
        return False

def scrape_county(county_name, base_url):
    print(f"\n=== Scraping {county_name} ===")
    full_url = f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={AUCTION_DATE}"

    driver = get_driver()
    wait = WebDriverWait(driver, 20)
    all_auctions = []

    try:
        print("🔄 Loading page...")
        driver.get(full_url)
        time.sleep(10)

        print("🔄 Scraping page 1 🕸️...")
        all_auctions.extend(scrape_auctions_on_page(driver, county_name))

        try:
            total_pages = int(driver.find_element(By.ID, "maxCA").text.strip())
            print(f"✅ Total pages: {total_pages}")
        except:
            total_pages = 1
            print("✅ Defaulting to 1 page.")

        for page_num in range(2, total_pages + 1):
            print(f"🔄 Navigating to page {page_num}...")
            if not click_next_page(driver, wait):
                break
            time.sleep(10)
            all_auctions.extend(scrape_auctions_on_page(driver, county_name))


        if all_auctions:
            df = pd.DataFrame(all_auctions)
            filename = os.path.join(FOLDER_NAME, f"{county_name.lower()}_{FOLDER_NAME}.xlsx")
            df.to_excel(filename, index=False)
            print(f"✅ Saved to '{filename}'")
        else:
            print("⚠️ No auctions found.")

    except Exception as e:
        print(f"⚠️ Scrape failed for {county_name}: {e}")
    finally:
        driver.quit()

def main():
    from database.url import COUNTY_URLS
    availability_file = f"availability_of_{FOLDER_NAME}.xlsx"
    if not os.path.exists(availability_file):
        print(f"⚠️ Missing availability file: '{availability_file}'")
        return

    df_availability = pd.read_excel(availability_file)

    for county, url in COUNTY_URLS.items():
        match = df_availability[df_availability["County"].str.lower() == county.lower()]
        if not match.empty:
            available = str(match.iloc[0]["Available"]).strip().lower() == "true"
            if available:
                print(f"✅ Scraping {county} 🕸️...")
                scrape_county(county, url)
            else:
                print(f"▶️ Skipping {county} (not available)")
        else:
            print(f"⚠️ No match for {county}")

    try:
        os.remove(availability_file)
        print(f"✅ Deleted availability file '{availability_file}'")
    except Exception as e:
        print(f"⚠️ Could not delete availability file: {e}")

if __name__ == "__main__":
    main()
