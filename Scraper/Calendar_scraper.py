import os
import pytz
import subprocess
import contextlib
from selenium import webdriver
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC

def get_driver():
    options = Options()
    service = Service()
    options.add_argument("--disable-gpu")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--start-minimized") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=2")  # Suppress Chrome internal logs
    service.creation_flags = subprocess.CREATE_NO_WINDOW

    service = Service(log_path=os.devnull)  # Silence ChromeDriver output

    # Suppress all stdout/stderr (covers underlying native libs like TensorFlow Lite)
    with open(os.devnull, 'w') as fnull, contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
        driver = webdriver.Chrome(options=options, service=service)
        driver.minimize_window()
    return driver

def check_auction_yesterday(url, driver):
    # IST timezone
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    yesterday = now_ist - timedelta(days=1)

    # Format date to match aria-label e.g. "May-31-2025"
    yesterday_str = yesterday.strftime("%B-%d-%Y")  # Month-fullname-Day-Year

    driver.get(url)
    wait = WebDriverWait(driver, 10)

    # Wait for calendar container to load
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "CALDAYBOX")))

    # Note: Removed day==1 check here because we handle it in main()
    
    # Find all day boxes
    day_boxes = driver.find_elements(By.CSS_SELECTOR, "div.CALBOX.CALW5")

    yesterday_box = None
    for box in day_boxes:
        aria_label = box.get_attribute("aria-label")
        if aria_label == yesterday_str:
            yesterday_box = box
            break

    if not yesterday_box:
        print(f"⚠️ Date {yesterday_str} not found in calendar on page: {url}")
        return False

    # Check for presence of <span class="CALTEXT"> with <span class="CALMSG"> inside
    try:
        caltext = yesterday_box.find_element(By.CLASS_NAME, "CALTEXT")
        calmsg = caltext.find_element(By.CLASS_NAME, "CALMSG")
        # If found, auction data is available
        return True
    except NoSuchElementException:
        # If CALTEXT or CALMSG not found, no auction data for that day
        return False

def main():
    from Scraper import day_1_Scraper
    from database.calendar_database import URL  # your county URLs
    
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)

    # RUN day_1_Scraper ONLY if today is 1, then EXIT immediately
    if now_ist.day == 1:
        day_1_Scraper.main()
        return  # exit, don't run anything else

    driver = get_driver()

    results = []
    for county, url in URL.items():
        print(f"Checking {county} 🔍...")
        available = check_auction_yesterday(url, driver)
        results.append({"County": county, "Available": available})

    driver.quit()

    import pandas as pd
    df = pd.DataFrame(results)
    yesterday = now_ist - timedelta(days=1)
    filename = yesterday.strftime("availability_of_%m-%d-%Y") + ".xlsx"
    df.to_excel(filename, index=False)
    print(f"✅ Results saved to {filename}")

if __name__ == "__main__":
    main()
