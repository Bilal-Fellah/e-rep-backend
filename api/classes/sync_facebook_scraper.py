import re
import random
import time
from playwright.sync_api import sync_playwright

class FacebookPlaywrightScraper:
    def __init__(self, headless=True, slow_mo=1000):
        self.headless = headless
        self.slow_mo = slow_mo
        self.results = []

    def setup_browser(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-ipc-flooding-protection',
                '--enable-features=NetworkService,NetworkServiceLogging',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            }
        )

        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

    def scrape_page(self, url):
        self.setup_browser()
        
        page = self.context.new_page()
        try:
            print(f" Scraping: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)
            time.sleep(random.uniform(2, 4))
            current_url = page.url

            if 'unsupportedbrowser' in current_url:
                print(" Redirected to unsupported browser page")
                return self.try_mobile_version(page, url)

            result = {
                'page_url': url,
                'final_url': current_url,
                'followers': 0,
                'likes': 0,
                'success': False,
                'method_used': [],
                'error': None
            }

            self.extract_by_text_content(page, result)
            if result['followers'] == 0 or result['likes'] == 0:
                self.extract_by_selectors(page, result)
            if result['followers'] == 0 or result['likes'] == 0:
                self.extract_from_page_text(page, result)
            if result['followers'] == 0 or result['likes'] == 0:
                self.extract_with_scrolling(page, result)

            if result['followers'] > 0 or result['likes'] > 0:
                result['success'] = True
                print(f" Success! Followers: {result['followers']:,}, Likes: {result['likes']:,}")
            else:
                result['error'] = 'No follower/like data found'
                print(" No data found")

            return result
        except Exception as e:
            print(f" Error scraping {url}: {e}")
            return {
                'page_url': url,
                'final_url': page.url if page else url,
                'followers': 0,
                'likes': 0,
                'success': False,
                'method_used': [],
                'error': str(e)
            }
        finally:
            page.close()

    def try_mobile_version(self, page, original_url):
        print(" Trying mobile version...")
        mobile_url = original_url.replace('www.facebook.com', 'm.facebook.com')
        if 'profile.php?id=' in mobile_url:
            mobile_url = mobile_url.replace('m.facebook.com', 'mbasic.facebook.com')

        try:
            page.goto(mobile_url, wait_until='networkidle', timeout=30000)
            time.sleep(random.uniform(2, 4))

            result = {
                'page_url': original_url,
                'final_url': page.url,
                'followers': 0,
                'likes': 0,
                'success': False,
                'method_used': ['mobile_version'],
                'error': None
            }

            self.extract_from_page_text(page, result)

            if result['followers'] > 0 or result['likes'] > 0:
                result['success'] = True
                print(f" Mobile version success! Followers: {result['followers']:,}, Likes: {result['likes']:,}")

            return result

        except Exception as e:
            print(f" Mobile version also failed: {e}")
            return {
                'page_url': original_url,
                'final_url': mobile_url,
                'followers': 0,
                'likes': 0,
                'success': False,
                'method_used': ['mobile_version'],
                'error': f'Mobile version failed: {str(e)}'
            }

    def extract_by_text_content(self, page, result):
        try:
            followers_elements = page.query_selector_all('text="followers"')
            for element in followers_elements:
                parent = element.query_selector('xpath=..')
                if parent:
                    text = parent.text_content()
                    numbers = self.extract_numbers_from_text(text)
                    if numbers and result['followers'] == 0:
                        result['followers'] = max(numbers)
                        result['method_used'].append('text_content_followers')

            likes_elements = page.query_selector_all('text="likes"')
            for element in likes_elements:
                parent = element.query_selector('xpath=..')
                if parent:
                    text = parent.text_content()
                    numbers = self.extract_numbers_from_text(text)
                    if numbers and result['likes'] == 0:
                        result['likes'] = max(numbers)
                        result['method_used'].append('text_content_likes')

        except Exception as e:
            print(f"  Text content extraction failed: {e}")

    def extract_by_selectors(self, page, result):
        try:
            selectors = [
                'a[href*="followers"] strong',
                'a[href*="likes"] strong',
                'a[href*="friends_likes"] strong',
                '[data-testid*="follower"] strong',
                '[data-testid*="like"] strong',
                'strong:has-text("followers")',
                'strong:has-text("likes")',
            ]
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        text = element.text_content()
                        number = self.convert_to_number(text)
                        if number > 1000:
                            if 'follower' in selector and result['followers'] == 0:
                                result['followers'] = number
                                result['method_used'].append('css_selector')
                            elif 'like' in selector and result['likes'] == 0:
                                result['likes'] = number
                                result['method_used'].append('css_selector')
                except:
                    continue

        except Exception as e:
            print(f"  Selector extraction failed: {e}")

    def extract_from_page_text(self, page, result):
        try:
            page_text = page.text_content('body')

            followers_patterns = [
                r'([0-9.,]+[KMB]?)\s+followers?',
                r'followers?\s*[:\-]?\s*([0-9.,]+[KMB]?)',
                r'([0-9.,]+[KMB]?)\s*people\s+follow',
                r'([0-9.,]+[KMB]?)\s+subscriber',
            ]

            likes_patterns = [
                r'([0-9.,]+[KMB]?)\s+likes?',
                r'likes?\s*[:\-]?\s*([0-9.,]+[KMB]?)',
                r'([0-9.,]+[KMB]?)\s*people\s+like',
                r'([0-9.,]+[KMB]?)\s+fans?',
            ]

            if result['followers'] == 0:
                for pattern in followers_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['followers'] = self.convert_to_number(match.group(1))
                        result['method_used'].append('page_text_followers')
                        break

            if result['likes'] == 0:
                for pattern in likes_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['likes'] = self.convert_to_number(match.group(1))
                        result['method_used'].append('page_text_likes')
                        break

        except Exception as e:
            print(f"  Page text extraction failed: {e}")

    def extract_with_scrolling(self, page, result):
        try:
            print(" Trying with scrolling...")
            for _ in range(3):
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                time.sleep(1)
            self.extract_from_page_text(page, result)
        except Exception as e:
            print(f"  Scrolling extraction failed: {e}")

    def extract_numbers_from_text(self, text):
        if not text:
            return []
        patterns = re.findall(r'([0-9.,]+[KMB]?)', text, re.IGNORECASE)
        numbers = [self.convert_to_number(p) for p in patterns if self.convert_to_number(p) > 100]
        return numbers

    def convert_to_number(self, text):
        if not text:
            return 0
        text = str(text).strip().lower()
        multipliers = {'k': 1000, 'm': 1_000_000, 'b': 1_000_000_000}
        match = re.match(r'([0-9.,]+)([kmb]?)', text)
        if match:
            number_str, suffix = match.groups()
            try:
                number = float(number_str.replace(',', ''))
                if suffix in multipliers:
                    number *= multipliers[suffix]
                return int(number)
            except ValueError:
                return 0
        return 0

    def scrape_multiple_pages(self, urls):
        self.setup_browser()
        try:
            for i, url in enumerate(urls):
                print(f"\n Processing page {i+1}/{len(urls)}")
                result = self.scrape_page(url)
                self.results.append(result)
                if i < len(urls) - 1:
                    delay = random.uniform(5, 10)
                    print(f" Waiting {delay:.1f} seconds before next page...")
                    time.sleep(delay)
            return self.results
        finally:
            self.cleanup()

    def cleanup(self):
        if hasattr(self, 'context'):
            self.context.close()
        if hasattr(self, 'browser'):
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
