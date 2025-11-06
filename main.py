import time
import json
import random
import datetime
import openpyxl
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class InstagramParser:
    def __init__(self, cookies_file='cookies.json'):
        self.cookies_file = cookies_file
        self.driver = None
        self.collected_usernames = set()

    def setup_driver(self):
        print("[SETUP] Запуск браузера...")
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        print("[SETUP] Драйвер готов")

    def load_cookies(self):
        print(f"[COOKIES] Загрузка cookies из {self.cookies_file}")
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
        except Exception as e:
            print(f"[ERROR] Не удалось загрузить cookies: {e}")
            return False

        self.driver.get("https://www.instagram.com/")
        time.sleep(3)

        added = 0
        for c in cookies:
            try:
                if 'instagram' not in c.get('domain', ''):
                    continue
                self.driver.add_cookie({
                    'name': c.get('name'),
                    'value': c.get('value'),
                    'domain': '.instagram.com'
                })
                added += 1
            except Exception:
                pass

        print(f"[COOKIES] Добавлено {added} cookies")
        self.driver.refresh()
        time.sleep(3)
        return True

    def go_to_profile(self, username):
        url = f"https://www.instagram.com/{username}/"
        print(f"[NAVIGATION] Открываю профиль: {url}")
        self.driver.get(url)
        time.sleep(3)

    def open_modal(self, mode):
        print(f"[MODAL] Открываю список: {mode}")
        try:
            if mode == "followers":
                btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers')]"))
                )
            else:
                try:
                    btn = WebDriverWait(self.driver, 6).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/following')]"))
                    )
                except TimeoutException:
                    btn = WebDriverWait(self.driver, 6).until(
                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[2]/div[1]/section/main/div/div/header/div/section[2]/div/div[3]/div[3]/a"))
                    )

            btn.click()
            time.sleep(3)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
            )
            print("[MODAL] Модальное окно открыто")
            return True
        except Exception as e:
            print(f"[ERROR] Не удалось открыть окно: {e}")
            return False

    def extract_usernames(self):
        users = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/') and contains(@class, '_a6hd')]")
        new_count = 0
        for u in users:
            href = u.get_attribute('href')
            if href:
                username = href.rstrip('/').split('/')[-1]
                if username and not any(x in username for x in ['explore', 'direct', 'accounts', 'stories', 'reels']):
                    if username not in self.collected_usernames:
                        self.collected_usernames.add(username)
                        new_count += 1
        return new_count

    def _has_recommendations_block(self):
        """Проверяем, появился ли блок 'Рекомендации для вас'"""
        try:
            block = self.driver.find_elements(By.XPATH, "//h4[contains(text(), 'Рекомендации для вас')]")
            return len(block) > 0
        except Exception:
            return False

    def scroll_and_collect(self, mode):
        print("[SCROLL] Начало сбора данных...")
        no_new = 0
        iteration = 0

        # выбираем контейнер по режиму
        try:
            if mode == "followers":
                container = self.driver.find_element(By.XPATH, "//div[@role='dialog']//div[contains(@class,'x7r02ix')]")
            else:
                container = self.driver.find_element(By.XPATH, "/html/body/div[4]/div[2]/div/div/div[1]/div/div[2]/div/div/div/div/div[2]/div/div/div[3]")
            print("[SCROLL] Контейнер найден")
        except NoSuchElementException:
            print("[ERROR] Контейнер для скролла не найден")
            return

        while True:
            iteration += 1
            new_found = self.extract_usernames()
            total = len(self.collected_usernames)
            print(f"[ИТЕРАЦИЯ {iteration}] Новых: {new_found} | Всего: {total}")

            if self._has_recommendations_block():
                print("[INFO] Найден блок 'Рекомендации для вас' — завершаем сбор.")
                break

            if new_found == 0:
                no_new += 1
                if no_new >= 40:
                    print("[SCROLL] 40 итераций без новых данных — выходим")
                    break
            else:
                no_new = 0

            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
            time.sleep(random.uniform(0.3, 0.8))
            time.sleep(3)

        print(f"[РЕЗУЛЬТАТ] Всего собрано: {len(self.collected_usernames)}")

    def save_excel(self, username, mode):
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"{mode}_{username}_{now}.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Users"
        ws.append(["Username"])
        for name in sorted(self.collected_usernames):
            ws.append([name])
        wb.save(fname)
        print(f"[SAVE] Сохранено {len(self.collected_usernames)} имён в {fname}")

    def run(self, username, mode):
        try:
            self.setup_driver()
            if not self.load_cookies():
                return
            self.go_to_profile(username)
            if not self.open_modal(mode):
                return
            self.scroll_and_collect(mode)
            if self.collected_usernames:
                self.save_excel(username, mode)
            else:
                print("[WARNING] Не собрано ни одного имени")
        finally:
            if self.driver:
                self.driver.quit()
                print("[DONE] Работа завершена.")


if __name__ == "__main__":
    print("=" * 60)
    print("Instagram Parser — сбор подписчиков и подписок")
    print("=" * 60)
    profile = input("Введите username профиля (например: accepy.ua): ").strip()
    mode = ""
    while mode not in ("followers", "following"):
        mode = input("Выберите режим (followers / following): ").strip().lower()
    cookies = input("Введите имя файла с cookies (по умолчанию cookies.json): ").strip() or "cookies.json"

    parser = InstagramParser(cookies)
    parser.run(profile, mode)
