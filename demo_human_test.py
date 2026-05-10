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
RUNS = 5
HEADLESS = False


def make_driver(headless=False):
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


def move_mouse_human(driver):
    body = driver.find_element(By.TAG_NAME, "body")

    try:
        ActionChains(driver).move_to_element_with_offset(body, 60, 80).perform()
    except Exception:
        pass

    offsets = [
        (40, 20), (25, 18), (35, 22), (30, 15), (28, 24),
        (-18, 20), (32, 18), (27, 26), (24, 19), (20, 15),
        (45, 30), (35, 18), (18, 12), (-15, 10), (22, 16)
    ]

    for dx, dy in offsets:
        try:
            ActionChains(driver).move_by_offset(dx, dy).pause(
                random.uniform(0.08, 0.22)
            ).perform()
        except Exception:
            pass


def type_human(element, text):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.07, 0.18))


def fill_form_human(driver, run_id):
    name_input = driver.find_element(By.ID, "fullName")
    email_input = driver.find_element(By.ID, "email")
    topic_select = driver.find_element(By.ID, "topic")
    message_input = driver.find_element(By.ID, "message")

    name_input.click()
    time.sleep(random.uniform(0.2, 0.5))
    type_human(name_input, f"Aruzhan User {run_id}")

    time.sleep(random.uniform(0.3, 0.8))
    email_input.click()
    type_human(email_input, f"aruzhan{run_id}@gmail.com")

    time.sleep(random.uniform(0.3, 0.7))
    topic_select.click()
    time.sleep(random.uniform(0.2, 0.4))
    topic_select.send_keys("\ue015")
    time.sleep(random.uniform(0.2, 0.4))
    topic_select.send_keys("\ue007")

    time.sleep(random.uniform(0.3, 0.8))
    message_input.click()
    type_human(
        message_input,
        "Hello, I would like to learn more about this behavioral verification demo."
    )


def scroll_human(driver):
    positions = [120, 240, 310, 260, 380, 340, 420]
    for pos in positions:
        driver.execute_script(f"window.scrollTo(0, {pos});")
        time.sleep(random.uniform(0.25, 0.55))


def click_check(driver):
    btn = driver.find_element(By.ID, "checkBtn")
    btn.click()


def wait_for_response(driver):
    output = driver.find_element(By.ID, "output")
    WebDriverWait(driver, 10).until(
        lambda d: output.text.strip() not in ("", "{}")
    )
    return output.text.strip()


def parse_response(raw_text):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"raw": raw_text}


def run_once(run_id, headless=False):
    driver = make_driver(headless=headless)
    try:
        open_demo_page(driver)
        time.sleep(random.uniform(0.8, 1.5))

        move_mouse_human(driver)
        time.sleep(random.uniform(0.4, 0.9))

        fill_form_human(driver, run_id)
        time.sleep(random.uniform(0.4, 1.0))

        scroll_human(driver)
        time.sleep(random.uniform(0.5, 1.2))

        move_mouse_human(driver)
        time.sleep(random.uniform(0.4, 0.8))

        click_check(driver)
        time.sleep(2)

        raw = wait_for_response(driver)
        data = parse_response(raw)

        print(f"\n=== HUMAN RUN {run_id} ===")
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
        time.sleep(random.uniform(1.0, 2.0)) """