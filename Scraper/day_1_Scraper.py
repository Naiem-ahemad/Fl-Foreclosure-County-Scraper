import os
import pytz
from datetime import datetime, timedelta

def get_driver():
    import subprocess
    import contextlib
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--start-minimized") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=2")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(log_path=os.devnull)
    service.creation_flags = subprocess.CREATE_NO_WINDOW
    with open(os.devnull, 'w') as fnull, contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
        driver = webdriver.Chrome(options=options, service=service)
        driver.minimize_window()
    return driver

def check_auction_day1(base_url, driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)

    if now_ist.day != 1:
        return None

    # Calculate first day of previous month
    first_of_this_month = now_ist.replace(day=1)
    previous_month_last_day = first_of_this_month - timedelta(days=1)
    target_date = previous_month_last_day.replace(day=1)  # e.g. 2025-03-01

    # Format date for URL: YYYY-MM-DD
    target_date_str = target_date.strftime("%Y-%m-%d")

    # Construct full URL with encoded timestamp query string
    full_url = (
        f"{base_url}/index.cfm?zaction=user&zmethod=calendar&"
        f"selCalDate=%7Bts%20%27{target_date_str}%2000%3A00%3A00%27%7D"
    )
   
    driver.get(full_url)
    wait = WebDriverWait(driver, 10)

    try:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "CALDAYBOX")))
    except TimeoutException:
        print(f"⚠️ Calendar did not load in time for URL: {full_url}")
        return False

    # Find the target date box on calendar
    day_boxes = driver.find_elements(By.CSS_SELECTOR, "div.CALBOX.CALW5")
    target_str = target_date.strftime("%B-%d-%Y")  # e.g. March-01-2025
    target_box = None

    for box in day_boxes:
        aria_label = box.get_attribute("aria-label")
        if aria_label == target_str:
            target_box = box
            break

    if not target_box:
        print(f"⚠️ Date {target_str} not found in calendar on page: {full_url}")
        return False

    # Check if auction data available inside target box
    try:
        caltext = target_box.find_element(By.CLASS_NAME, "CALTEXT")
        calmsg = caltext.find_element(By.CLASS_NAME, "CALMSG")
        return True
    except NoSuchElementException:
        return False

def main():
    import pandas as pd
    from database.url import COUNTY_URLS  # dict of {county: base_url}

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)

    driver = get_driver()
    results = []

    for county, base_url in COUNTY_URLS.items():
        print(f"✅ Checking {county}🔍...")
        available = check_auction_day1(base_url, driver)
        if available is None:
            # Not day 1, so break
            break
        prev_month_first_day = (now_ist.replace(day=1) - timedelta(days=1)).replace(day=1)
        results.append({"County": county, "Date": prev_month_first_day.strftime("%Y-%m-%d"), "Available": available})

    driver.quit()

    prev_month_first_day = datetime.now(pytz.timezone('Asia/Kolkata')) - timedelta(days=1)
    filename = prev_month_first_day.strftime("availability_of_%m-%d-%Y") + ".xlsx"
    df = pd.DataFrame(results)
    df.to_excel(filename, index=False)
    print(f"✅ Results saved to {filename}")

if __name__ == "__main__":
    main()
