""" import json
import random
import time

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "http://127.0.0.1:3000/"
RUNS = 3
HEADLESS = False


def make_driver(headless: bool = False):
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


def open_demo_page(driver):
    driver.get(BASE_URL)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "fullName"))
    )
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "checkBtn"))
    )


def move_mouse_fast(driver):
    body = driver.find_element(By.TAG_NAME, "body")

    try:
        ActionChains(driver).move_to_element_with_offset(body, 50, 50).perform()
    except Exception:
        pass

    offsets = [
        (120, 40),
        (160, 20),
        (-180, 60),
        (240, 80),
        (-140, 50),
        (210, 70),
    ]

    for dx, dy in offsets:
        try:
            ActionChains(driver).move_by_offset(dx, dy).pause(
                random.uniform(0.02, 0.06)
            ).perform()
        except Exception:
            pass


def fill_form_fast(driver, run_id: int):
    name_input = driver.find_element(By.ID, "fullName")
    email_input = driver.find_element(By.ID, "email")
    topic_select = driver.find_element(By.ID, "topic")
    message_input = driver.find_element(By.ID, "message")

    name_input.click()
    name_input.send_keys(f"Bot User {run_id}")

    email_input.click()
    email_input.send_keys(f"bot{run_id}@test.kz")

    topic_select.click()
    time.sleep(0.03)
    topic_select.send_keys("\ue015")
    time.sleep(0.03)
    topic_select.send_keys("\ue007")

    message_input.click()
    message_input.send_keys("Fast automated submission for model testing.")


def scroll_burst(driver):
    positions = [300, 50, 420, 140, 520, 90, 470]
    for pos in positions:
        driver.execute_script(f"window.scrollTo(0, {pos});")
        time.sleep(random.uniform(0.03, 0.08))


def click_check(driver):
    btn = driver.find_element(By.ID, "checkBtn")
    btn.click()


def wait_for_response(driver):
    output = driver.find_element(By.ID, "output")
    WebDriverWait(driver, 10).until(
        lambda d: output.text.strip() not in ("", "{}")
    )
    return output.text.strip()


def parse_response(raw_text: str):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"raw": raw_text}


def run_once(run_id: int, headless: bool = False):
    driver = make_driver(headless=headless)
    try:
        open_demo_page(driver)
        time.sleep(0.2)

        move_mouse_fast(driver)
        time.sleep(0.08)

        fill_form_fast(driver, run_id)
        time.sleep(0.05)

        scroll_burst(driver)
        time.sleep(0.05)

        click_check(driver)
        time.sleep(1.5)

        raw = wait_for_response(driver)
        data = parse_response(raw)

        print(f"\n=== RUN {run_id} ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if isinstance(data, dict):
            print("decision:", data.get("decision"))
            print("score:", data.get("score"))
            print("source:", data.get("source"))
            print("model_source:", data.get("model_source"))

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    for i in range(1, RUNS + 1):
        run_once(i, headless=HEADLESS)
        time.sleep(random.uniform(0.5, 1.0)) """