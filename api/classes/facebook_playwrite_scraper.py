import asyncio
import re
import random
from playwright.async_api import async_playwright

class FacebookPlaywrightScraper:
    def __init__(self, headless=True, slow_mo=1000):
        self.headless = headless
        self.slow_mo = slow_mo
        self.results = []
    
    async def setup_browser(self):
        """Set up Playwright browser with stealth settings."""
        self.playwright = await async_playwright().start()
        
        # Use Chrome browser with stealth settings
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,  # Slow down actions to appear more human
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
        
        # Create context with additional stealth settings
        self.context = await self.browser.new_context(
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
        
        # Add stealth scripts to avoid detection
        await self.context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock chrome object
            window.chrome = {
                runtime: {},
            };
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)
    
    async def scrape_page(self, url):
        """Scrape a single Facebook page."""
        
        page = await self.context.new_page()
        
        try:
            print(f" Scraping: {url}")
            
            # Navigate to the page
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait a bit for content to load
            await asyncio.sleep(random.uniform(2, 4))
            
            # Check if we got redirected to unsupported browser
            current_url = page.url
            if 'unsupportedbrowser' in current_url:
                print(f" Redirected to unsupported browser page")
                return await self.try_mobile_version(page, url)
            
            # Initialize result
            result = {
                'page_url': url,
                'final_url': current_url,
                'followers': 0,
                'likes': 0,
                'success': False,
                'method_used': [],
                'error': None
            }
            
            # Method 1: Look for follower/like elements by text content
            await self.extract_by_text_content(page, result)
            
            # Method 2: Look for specific selectors
            if result['followers'] == 0 or result['likes'] == 0:
                await self.extract_by_selectors(page, result)
            
            # Method 3: Extract from page text
            if result['followers'] == 0 or result['likes'] == 0:
                await self.extract_from_page_text(page, result)
            
            # Method 4: Try scrolling and looking for more content
            if result['followers'] == 0 or result['likes'] == 0:
                await self.extract_with_scrolling(page, result)
            
            # Check success
            if result['followers'] > 0 or result['likes'] > 0:
                result['success'] = True
                print(f" Success! Followers: {result['followers']:,}, Likes: {result['likes']:,}")
            else:
                result['error'] = 'No follower/like data found'
                print(f" No data found")
            
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
            await page.close()
    
    async def try_mobile_version(self, page, original_url):
        """Try accessing the mobile version of Facebook."""
        print(" Trying mobile version...")
        
        # Convert to mobile URL
        mobile_url = original_url.replace('www.facebook.com', 'm.facebook.com')
        if 'profile.php?id=' in mobile_url:
            # Mobile Facebook sometimes works better with profile URLs
            mobile_url = mobile_url.replace('m.facebook.com', 'mbasic.facebook.com')
        
        try:
            await page.goto(mobile_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))
            
            result = {
                'page_url': original_url,
                'final_url': page.url,
                'followers': 0,
                'likes': 0,
                'success': False,
                'method_used': ['mobile_version'],
                'error': None
            }
            
            # Try extracting from mobile version
            await self.extract_from_page_text(page, result)
            
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
    
    async def extract_by_text_content(self, page, result):
        """Extract followers/likes by looking for text patterns."""
        try:
            # Look for elements containing "followers" text
            followers_elements = await page.query_selector_all('text="followers"')
            for element in followers_elements:
                parent = await element.query_selector('xpath=..')
                if parent:
                    text = await parent.text_content()
                    numbers = self.extract_numbers_from_text(text)
                    if numbers and result['followers'] == 0:
                        result['followers'] = max(numbers)
                        result['method_used'].append('text_content_followers')
            
            # Look for elements containing "likes" text
            likes_elements = await page.query_selector_all('text="likes"')
            for element in likes_elements:
                parent = await element.query_selector('xpath=..')
                if parent:
                    text = await parent.text_content()
                    numbers = self.extract_numbers_from_text(text)
                    if numbers and result['likes'] == 0:
                        result['likes'] = max(numbers)
                        result['method_used'].append('text_content_likes')
                        
        except Exception as e:
            print(f"  Text content extraction failed: {e}")
    
    async def extract_by_selectors(self, page, result):
        """Extract using CSS selectors."""
        try:
            # Common selectors for Facebook page stats
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
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.text_content()
                        number = self.convert_to_number(text)
                        if number > 1000:  # Reasonable threshold
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
    
    async def extract_from_page_text(self, page, result):
        """Extract from the full page text."""
        try:
            page_text = await page.text_content('body')
            
            # Patterns for followers
            followers_patterns = [
                r'([0-9.,]+[KMB]?)\s+followers?',
                r'followers?\s*[:\-]?\s*([0-9.,]+[KMB]?)',
                r'([0-9.,]+[KMB]?)\s*people\s+follow',
                r'([0-9.,]+[KMB]?)\s+subscriber',
            ]
            
            # Patterns for likes
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
    
    async def extract_with_scrolling(self, page, result):
        """Try scrolling to load more content and extract."""
        try:
            print(" Trying with scrolling...")
            
            # Scroll down a few times to load dynamic content
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await asyncio.sleep(1)
            
            # Try extracting again after scrolling
            await self.extract_from_page_text(page, result)
            
        except Exception as e:
            print(f"  Scrolling extraction failed: {e}")
    
    def extract_numbers_from_text(self, text):
        """Extract all numbers from text that could be follower/like counts."""
        if not text:
            return []
        
        # Find all number patterns
        patterns = re.findall(r'([0-9.,]+[KMB]?)', text, re.IGNORECASE)
        numbers = []
        
        for pattern in patterns:
            number = self.convert_to_number(pattern)
            if number > 100:  #  ** it isn't right ** Filter out small numbers that are unlikely to be follower counts
                numbers.append(number)
        
        return numbers
    
    def convert_to_number(self, text):
        """Convert text like '1.4M' to actual number."""
        if not text:
            return 0
        
        text = str(text).strip().lower()
        
        multipliers = {
            'k': 1000,
            'm': 1000000,
            'b': 1000000000
        }
        
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
    
    async def scrape_multiple_pages(self, urls):
        """Scrape multiple Facebook pages."""
        await self.setup_browser()
        
        try:
            for i, url in enumerate(urls):
                print(f"\n Processing page {i+1}/{len(urls)}")
                result = await self.scrape_page(url)
                self.results.append(result)
                
                # Random delay between pages
                if i < len(urls) - 1:
                    delay = random.uniform(2, 4)
                    print(f" Waiting {delay:.1f} seconds before next page...")
                    await asyncio.sleep(delay)
            
            return self.results
            
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up browser resources."""
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
