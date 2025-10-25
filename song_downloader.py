#!/usr/bin/env python3
"""
Dependency:
pip install selenium webdriver-manager
"""

import time
import subprocess
from pathlib import Path
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

first_video_link = None # Stores the link
file_name = None # Stores the downloaded file name
a = 1 # Toggle between two downloader sites
index = 0 # To keep track of current line index

with open("song_list.txt", encoding="utf-8") as f:
    lines = f.readlines()

with open("song_list.txt", encoding="utf-8") as file:
    for line in file:        
        # Step-1: Extracting the link
        def get_first_youtube_link_from_search(query: str, timeout: int = 10, headless: bool = True) -> str:
            if not query:
                raise ValueError("Empty query provided.")

            search_url = "https://www.youtube.com/results?search_query=" + quote_plus(query)

            # Chrome options
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            if headless:
                options.add_argument("--headless=new") # If the version of Chrome does not supports it, use "--headless"
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            wait = WebDriverWait(driver, timeout)

            try:
                driver.get(search_url)

                # Wait for video results
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a#video-title")))

                anchors = driver.find_elements(By.CSS_SELECTOR, "a#video-title")

                first_href = None
                for a in anchors:
                    href = a.get_attribute("href")
                    if href and "/watch" in href and a.is_displayed():
                        first_href = href
                        break
                    
                # fallback: check all <a> elements
                if not first_href:
                    all_anchors = driver.find_elements(By.TAG_NAME, "a")
                    for a in all_anchors:
                        href = a.get_attribute("href")
                        if href and "/watch" in href and "list=" not in href and a.is_displayed():
                            first_href = href
                            break
                        
                if not first_href:
                    raise RuntimeError("Couldn't find the first video link.")

                return first_href

            finally:
                driver.quit()

        if __name__ == "__main__":
            query = line.strip()
            if not query:
                print("No input entered. Exiting.")
            else:
                first_video_link = get_first_youtube_link_from_search(query, timeout=10, headless=True)

        # Step-2: Downloading the song using the extracted link and shifting it to a separate folder
        def open_and_fill_then_tab_sequence(url: str, user_input: str, timeout: int = 15, max_retries: int = 3):
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--headless=new")  # enable for headless if you want
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

            try:
                driver.get(url)
                wait = WebDriverWait(driver, timeout)

                time.sleep(1)

                input_box = None
                try:
                    # prefer explicit selectors
                    candidates = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search'], input:not([type])")
                    for c in candidates:
                        try:
                            if c.is_displayed() and c.is_enabled():
                                input_box = c
                                break
                        except StaleElementReferenceException:
                            # element vanished, skip it
                            continue
                except Exception:
                    input_box = None

                if not input_box:
                    # fallback: try to find textarea or contenteditable element
                    try:
                        candidates = driver.find_elements(By.CSS_SELECTOR, "textarea, [contenteditable='true']")
                        for c in candidates:
                            try:
                                if c.is_displayed() and c.is_enabled():
                                    input_box = c
                                    break
                            except StaleElementReferenceException:
                                continue
                    except Exception:
                        input_box = None

                if not input_box:
                    raise RuntimeError("No visible text input or textarea found on the page.")

                # Fill the input. Use JS fallback if send_keys fails repeatedly.
                try:
                    input_box.clear()
                except Exception:
                    pass
                
                try:
                    input_box.send_keys(user_input)
                except StaleElementReferenceException:
                    # try a quick re-find by CSS and send again
                    try:
                        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='search'], input:not([type])")))
                        input_box.clear()
                        input_box.send_keys(user_input)
                    except Exception:
                        # fallback to JS set
                        driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", input_box, user_input)

                # --- Perform the key sequence robustly using ActionChains ---
                actions = ActionChains(driver)

                # We'll attempt the sequence; if StaleElementReference occurs we retry up to max_retries
                attempt = 0
                while attempt < max_retries:
                    attempt += 1
                    try:
                        # it's safer to target the body so even if active element changes, keys go to page
                        body = driver.find_element(By.TAG_NAME, "body")

                        # Focus the input_box or body first (ensures the browser receives the keys)
                        try:
                            input_box.click()
                        except Exception:
                            # ignore if click fails; we still can send keys to body
                            pass
                        
                        # subprocess.run("pbcopy", text=True, input=first_video_link) # For macOS clipboard copy if needed
                        # subprocess.run("clip", text=True, input=first_video_link, shell=True) # For Windows clipboard copy if needed
                        actions = ActionChains(driver)
                        actions.move_to_element(body)  # ensure actions target the page
                        actions.send_keys(Keys.TAB)
                        actions.send_keys(Keys.TAB)
                        actions.send_keys(Keys.RETURN)
                        actions.perform()
                        time.sleep(4) # time varies for the processing time
                        actions.send_keys(Keys.TAB)
                        actions.send_keys(Keys.RETURN)
                        actions.perform()
                        break
                    except StaleElementReferenceException:
                        # element changed; re-find input_box/body and retry
                        time.sleep(0.25)
                        try:
                            input_box = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='search'], input:not([type])")
                        except Exception:
                            # keep previous reference if re-find fails
                            pass
                        continue
                    except Exception as ex:
                        # other exceptions: print a short message and retry a couple times
                        if attempt >= max_retries:
                            raise
                        time.sleep(0.25)
                        continue
                    
                # Give the page a moment to react to the key presses
                time.sleep(1)

                downloads = Path.home() / "Downloads"
                existing = set(downloads.iterdir())

                while True:
                    time.sleep(2)
                    new_files = set(downloads.iterdir()) - existing
                    if new_files:
                        for f in new_files:
                            print(f"Song downloaded: {f.name}")
                            file_name = f.name
                        break
                    
                source_file = Path.home() / "Downloads" / file_name
                destination_folder = Path.home() / "Desktop" / "Songs"
                destination_folder.mkdir(parents=True, exist_ok=True)

                destination_file = destination_folder / source_file.name
                source_file.rename(destination_file)

            finally:
                driver.quit()

        if __name__ == "__main__":
            if(a==0):
                url = "https://ytmp3.as/"
            else:
                url = "https://y2mate.nu/"
            a = 1 - a
            text = first_video_link
            if not url or not text:
                print("Both URL and text are required. Exiting.")
            else:
                open_and_fill_then_tab_sequence(url, text)
       
        factor = " ✅\n"
        lines[index] = line.rstrip() + factor
        index +=1

        # Step-3: Updating the song list file
        with open("song_list_data.txt","a", encoding="utf-8") as f3:
            f3.write(lines[index-1])
        with open("song_list.txt", "w", encoding="utf-8") as f2:
            f2.writelines(lines[index:len(lines)])

