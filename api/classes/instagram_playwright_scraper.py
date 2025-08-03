#!/usr/bin/env python3
"""
Instagram Profile Scraper using Playwright
Scrapes follower counts from Instagram profiles
"""

import asyncio
import re
import json
import random
import time
from playwright.async_api import async_playwright
from urllib.parse import urlparse

class InstagramPlaywrightScraper:
    def __init__(self, headless=True, slow_mo=1000, username=None, password=None):
        self.headless = headless
        self.slow_mo = slow_mo
        self.username = username
        self.password = password
        self.results = []
        self.logged_in = False
    
    async def setup_browser(self):
        """Set up Playwright browser with stealth settings."""
        self.playwright = await async_playwright().start()
        
        # Use Chrome browser with maximum stealth settings for Instagram
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
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-gpu',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-blink-features=AutomationControlled',
                '--exclude-switches=enable-automation',
                '--disable-component-extensions-with-background-pages',
                '--disable-default-apps',
                '--mute-audio',
                '--no-default-browser-check',
                '--autoplay-policy=user-gesture-required',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-client-side-phishing-detection',
                '--disable-component-update',
                '--disable-default-apps',
                '--disable-dev-shm-usage',
                '--disable-domain-reliability',
                '--disable-features=AudioServiceOutOfProcess',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-notifications',
                '--disable-offer-store-unmasked-wallet-cards',
                '--disable-popup-blocking',
                '--disable-print-preview',
                '--disable-prompt-on-repost',
                '--disable-renderer-backgrounding',
                '--disable-setuid-sandbox',
                '--disable-speech-api',
                '--disable-sync',
                '--hide-scrollbars',
                '--ignore-gpu-blacklist',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-default-browser-check',
                '--no-first-run',
                '--no-pings',
                '--no-sandbox',
                '--no-zygote',
                '--password-store=basic',
                '--use-gl=swiftshader',
                '--use-mock-keychain',
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
    
    async def login_to_instagram(self):
        """Login to Instagram if credentials are provided."""
        if not self.username or not self.password:
            return False
        
        try:
            print("🔑 Attempting to login to Instagram...")
            page = await self.context.new_page()
            
            # Go to Instagram login page
            await page.goto('https://www.instagram.com/accounts/login/', wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            # Wait for login form to be visible
            await page.wait_for_selector('input[name="username"]', timeout=10000)
            
            # Fill in credentials
            await page.fill('input[name="username"]', self.username)
            await page.fill('input[name="password"]', self.password)
            
            # Click login button
            await page.click('button[type="submit"]')
            
            # Wait for navigation or error
            await asyncio.sleep(5)
            
            # Check if login was successful
            current_url = page.url
            if 'challenge' in current_url:
                print("⚠️  2FA/Challenge required - you may need to complete this manually")
                # Wait a bit longer for manual intervention
                await asyncio.sleep(10)
            elif 'login' not in current_url:
                print("✅ Login successful!")
                self.logged_in = True
                await page.close()
                return True
            else:
                print("❌ Login failed - check credentials")
                await page.close()
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    async def scrape_page(self, url):
        """Scrape a single Instagram profile page."""
        page = await self.context.new_page()
        
        try:
            print(f"🔍 Scraping: {url}")
            
            # Use domcontentloaded strategy (proven to work reliably)
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=150000)
                await asyncio.sleep(4)  # Give time for dynamic content to load
                print("✅ Loaded with domcontentloaded")
            except Exception as e:
                print(f"❌ Loading failed: {str(e)[:100]}...")
                # Fallback: try without waiting for any events
                try:
                    await page.goto(url, timeout=10000)
                    await asyncio.sleep(6)  # Wait longer for content
                    print("✅ Loaded without waiting for events")
                except Exception as fallback_e:
                    print(f"❌ All loading strategies failed: {str(fallback_e)[:100]}...")
                    raise fallback_e
            
            # Wait a bit more for content to load
            await asyncio.sleep(random.uniform(3, 5))
            
            # Initialize result first
            current_url = page.url
            result = {
                'page_url': url,
                'final_url': current_url,
                'followers': 0,
                'following': 0,
                'posts': 0,
                'success': False,
                'method_used': [],
                'error': None
            }
            
            # Check if we need to handle login popup or other redirects
            login_wall_detected = 'login' in current_url or 'challenge' in current_url
            
            # Check for login modal even if URL seems fine
            login_modal = await page.query_selector('[role="dialog"], .login-modal, [data-testid="loginForm"]')
            if login_modal:
                login_wall_detected = True
            
            if login_wall_detected and not self.logged_in:
                print(f"⚠️  Hit login wall, trying bypass methods...")
                
                # If we have credentials but haven't logged in yet, try logging in
                if self.username and self.password and not self.logged_in:
                    print("🔑 Have credentials, attempting login...")
                    await page.close()  # Close current page
                    login_success = await self.login_to_instagram()
                    
                    if login_success:
                        # Create new page and try again
                        page = await self.context.new_page()
                        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                        await asyncio.sleep(3)
                        
                        # Update current URL and result
                        current_url = page.url
                        result['final_url'] = current_url
                        login_wall_detected = 'login' in current_url or 'challenge' in current_url
                        
                        if not login_wall_detected:
                            print("✅ Login bypass successful!")
                elif self.logged_in:
                    print("✅ Already logged in, should have access!")
                
                # If still hitting login wall, try other bypass methods
                if login_wall_detected:
                    # Bypass Method 1: Try to dismiss login modals/popups
                    try:
                        close_buttons = await page.query_selector_all('[aria-label="Close"], [aria-label="Dismiss"], .close, ._0mzm- button, [role="button"]:has-text("Close")')
                        for button in close_buttons:
                            try:
                                await button.click()
                                await asyncio.sleep(1)
                            except:
                                continue
                    except:
                        pass
                    
                    # Bypass Method 2: Try different user agents (mobile)
                    await page.set_extra_http_headers({
                        'User-Agent': 'Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US)'
                    })
                    
                    # Bypass Method 3: Try accessing through different endpoints
                    bypass_success = await self.try_alternative_endpoints(page, url, result)
                    
                    if not bypass_success:
                        # Bypass Method 4: Try reloading with different settings
                        print("🔄 Trying nuclear option - complete reload with different settings...")
                        try:
                            # Create a completely new page with different settings
                            await page.close()
                            page = await self.context.new_page()
                            
                            # Set mobile user agent before loading
                            await page.set_user_agent('Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1')
                            
                            # Try loading the mobile version directly
                            username = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
                            mobile_url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
                            
                            await page.goto(mobile_url, wait_until='domcontentloaded', timeout=8000)
                            await asyncio.sleep(3)
                            
                            # Update current URL
                            current_url = page.url
                            result['final_url'] = current_url
                            
                            if 'login' not in current_url:
                                print("✅ Nuclear option worked!")
                                bypass_success = True
                            
                        except Exception as e:
                            print(f"⚠️  Nuclear option failed: {str(e)[:50]}...")
                    
                    if not bypass_success:
                        # Bypass Method 5: Use aggressive extraction even with login wall
                        print("🔄 Trying to extract data despite login wall...")
                        await self.extract_from_cached_content(page, result)
            
            # Method 1: Look for specific Instagram selectors (title attribute)
            await self.extract_by_instagram_selectors(page, result)
            
            # Method 2: Look for text patterns
            if result['followers'] == 0:
                await self.extract_by_text_patterns(page, result)
            
            # Method 3: Extract from page text with broader patterns
            if result['followers'] == 0:
                await self.extract_from_page_text(page, result)
            
            # Method 4: Try scrolling and looking for more content
            if result['followers'] == 0:
                await self.extract_with_scrolling(page, result)
            
            # Method 5: Try extracting from meta tags and structured data
            if result['followers'] == 0:
                await self.extract_from_meta_and_structured_data(page, result)
            
            # Method 6: Try more aggressive text extraction for login walls
            if result['followers'] == 0:
                await self.extract_aggressive_text_search(page, result)
            
            # Check success
            if result['followers'] > 0 or result['following'] > 0 or result['posts'] > 0:
                result['success'] = True
                print(f"✅ Success! Followers: {result['followers']:,}, Following: {result['following']:,}, Posts: {result['posts']:,}")
            else:
                result['error'] = 'No follower/following data found'
                print(f"❌ No data found")
            
            return result
            
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            return {
                'page_url': url,
                'final_url': page.url if page else url,
                'followers': 0,
                'following': 0,
                'posts': 0,
                'success': False,
                'method_used': [],
                'error': str(e)
            }
        finally:
            await page.close()
    
    async def extract_by_instagram_selectors(self, page, result):
        """Extract using Instagram-specific CSS selectors."""
        try:
            # Method 1: Extract followers using title attribute
            title_selectors = [
                'span[title]',
                '.x5n08af.x1s688f[title]',
                'span.x5n08af.x1s688f[title]',
                'a[href*="followers"] span[title]',
            ]
            
            for selector in title_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        title_text = await element.get_attribute('title')
                        if title_text and title_text.replace(',', '').replace('.', '').isdigit():
                            number = self.convert_to_number(title_text)
                            
                            # Get parent link to determine what this number represents
                            parent_link = await element.query_selector('xpath=ancestor::a')
                            if parent_link:
                                href = await parent_link.get_attribute('href') or ''
                                
                                if 'followers' in href and result['followers'] == 0:
                                    result['followers'] = number
                                    result['method_used'].append('instagram_title_followers')
                            else:
                                # Usually followers are the largest numbers with title attributes
                                if number > 100 and result['followers'] == 0:
                                    result['followers'] = number
                                    result['method_used'].append('instagram_title_followers')
                except:
                    continue
            
            # Method 2: Extract following and posts using text content from specific span classes
            text_content_selectors = [
                'span.html-span.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x1hl2dhg.x16tdsg8.x1vvkbs',
                '.html-span.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x1hl2dhg.x16tdsg8.x1vvkbs',
            ]
            
            for selector in text_content_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text_content = await element.text_content()
                        if text_content and text_content.strip().replace(',', '').isdigit():
                            number = int(text_content.strip().replace(',', ''))
                            
                            # Get parent link to determine what this number represents
                            parent_link = await element.query_selector('xpath=ancestor::a')
                            if parent_link:
                                href = await parent_link.get_attribute('href') or ''
                                
                                if 'following' in href and result['following'] == 0:
                                    result['following'] = number
                                    result['method_used'].append('instagram_text_following')
                                elif '/p/' in href and result['posts'] == 0:
                                    # Posts usually link to individual posts
                                    result['posts'] = number
                                    result['method_used'].append('instagram_text_posts')
                            else:
                                # Try to guess based on typical ranges
                                # Posts are usually smaller numbers (< 1000 for most users)
                                # Following is usually moderate numbers
                                if number < 1000 and result['posts'] == 0:
                                    result['posts'] = number
                                    result['method_used'].append('instagram_text_guess_posts')
                                elif number > 0 and result['following'] == 0:
                                    result['following'] = number
                                    result['method_used'].append('instagram_text_guess_following')
                except:
                    continue
            
            # Method 3: Try to extract by analyzing the page structure more systematically
            await self.extract_by_page_structure(page, result)
                    
        except Exception as e:
            print(f"⚠️  Instagram selector extraction failed: {e}")
    
    async def extract_by_page_structure(self, page, result):
        """Extract by analyzing the page structure and order of elements."""
        try:
            # Instagram typically shows stats in order: Posts, Followers, Following
            # Look for all spans with numbers in the header area
            
            # Get all elements that could contain stats
            stat_elements = await page.query_selector_all('header span, header a span, [role="main"] header span')
            numbers_found = []
            
            for element in stat_elements:
                try:
                    # Try title attribute first (for followers)
                    title_text = await element.get_attribute('title')
                    if title_text and title_text.replace(',', '').replace('.', '').isdigit():
                        number = self.convert_to_number(title_text)
                        if number > 0:
                            numbers_found.append(('title', number, element))
                            continue
                    
                    # Try text content (for posts and following)
                    text_content = await element.text_content()
                    if text_content and text_content.strip().replace(',', '').isdigit():
                        number = int(text_content.strip().replace(',', ''))
                        if number > 0:
                            numbers_found.append(('text', number, element))
                except:
                    continue
            
            # Analyze the numbers we found
            for source_type, number, element in numbers_found:
                try:
                    # Get parent link to see context
                    parent_link = await element.query_selector('xpath=ancestor::a')
                    href = ''
                    if parent_link:
                        href = await parent_link.get_attribute('href') or ''
                    
                    # Determine what this number represents based on context
                    if 'followers' in href and result['followers'] == 0:
                        result['followers'] = number
                        result['method_used'].append('instagram_structure_followers')
                    elif 'following' in href and result['following'] == 0:
                        result['following'] = number
                        result['method_used'].append('instagram_structure_following')
                    elif source_type == 'title' and number > 100 and result['followers'] == 0:
                        # Large numbers with title are usually followers
                        result['followers'] = number
                        result['method_used'].append('instagram_structure_followers')
                    elif source_type == 'text' and number < 1000 and result['posts'] == 0:
                        # Small text numbers are usually posts
                        result['posts'] = number
                        result['method_used'].append('instagram_structure_posts')
                    elif source_type == 'text' and result['following'] == 0:
                        # Other text numbers are usually following
                        result['following'] = number
                        result['method_used'].append('instagram_structure_following')
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️  Page structure extraction failed: {e}")
    
    async def try_alternative_endpoints(self, page, original_url, result):
        """Try alternative endpoints to bypass login wall."""
        try:
            username = original_url.split('/')[-2] if original_url.endswith('/') else original_url.split('/')[-1]
            
            # Alternative endpoints to try
            alternatives = [
                f"https://www.instagram.com/{username}/?__a=1",  # API endpoint
                f"https://i.instagram.com/{username}/",  # Mobile version
                f"https://www.instagram.com/{username}/?hl=en",  # With language parameter
                f"https://www.instagram.com/{username}/?variant=following",  # Different variant
            ]
            
            for alt_url in alternatives:
                try:
                    print(f"🔄 Trying alternative endpoint: {alt_url}")
                    await page.goto(alt_url, wait_until='domcontentloaded', timeout=10000)
                    await asyncio.sleep(2)
                    
                    # Check if this worked better
                    current_url = page.url
                    if 'login' not in current_url and 'challenge' not in current_url:
                        print("✅ Alternative endpoint worked!")
                        return True
                        
                except Exception as e:
                    print(f"⚠️  Alternative endpoint failed: {str(e)[:50]}...")
                    continue
            
            return False
            
        except Exception as e:
            print(f"⚠️  Alternative endpoints failed: {e}")
            return False
    
    async def extract_from_cached_content(self, page, result):
        """Extract data from cached/pre-loaded content even with login wall."""
        try:
            print("🔄 Extracting from cached content...")
            
            # Method 1: Check for data in script tags (often contains JSON data)
            script_tags = await page.query_selector_all('script[type="application/json"], script:not([src])')
            for script in script_tags:
                try:
                    content = await script.text_content()
                    if content and 'follower' in content.lower():
                        # Look for follower data in JSON
                        import json
                        try:
                            data = json.loads(content)
                            followers = self.extract_from_json_data(data, 'followers')
                            following = self.extract_from_json_data(data, 'following')
                            posts = self.extract_from_json_data(data, 'posts')
                            
                            if followers > 0 and result['followers'] == 0:
                                result['followers'] = followers
                                result['method_used'].append('cached_json_followers')
                            if following > 0 and result['following'] == 0:
                                result['following'] = following
                                result['method_used'].append('cached_json_following')
                            if posts > 0 and result['posts'] == 0:
                                result['posts'] = posts
                                result['method_used'].append('cached_json_posts')
                        except:
                            # If not valid JSON, look for numbers in the text
                            numbers = re.findall(r'"(?:follower|following|post).*?(\d+)', content, re.IGNORECASE)
                            for num_str in numbers:
                                num = int(num_str)
                                if num > 1000 and result['followers'] == 0:
                                    result['followers'] = num
                                    result['method_used'].append('cached_script_followers')
                except:
                    continue
            
            # Method 2: Look for any remaining visible numbers on the page
            await self.extract_any_visible_numbers(page, result)
            
        except Exception as e:
            print(f"⚠️  Cached content extraction failed: {e}")
    
    def extract_from_json_data(self, data, stat_type):
        """Recursively search JSON data for specific stats."""
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    if stat_type in key.lower() and isinstance(value, int):
                        return value
                    elif isinstance(value, (dict, list)):
                        result = self.extract_from_json_data(value, stat_type)
                        if result > 0:
                            return result
            elif isinstance(data, list):
                for item in data:
                    result = self.extract_from_json_data(item, stat_type)
                    if result > 0:
                        return result
            return 0
        except:
            return 0
    
    async def extract_any_visible_numbers(self, page, result):
        """Extract any visible numbers that might be stats."""
        try:
            # Get all elements that contain only numbers
            all_elements = await page.query_selector_all('span, div, a')
            potential_stats = []
            
            for element in all_elements:
                try:
                    text = await element.text_content()
                    if text and text.strip().replace(',', '').replace('.', '').isdigit():
                        number = int(text.strip().replace(',', ''))
                        if 0 < number < 10000000:  # Reasonable range
                            potential_stats.append(number)
                except:
                    continue
            
            # Sort numbers and make educated guesses
            potential_stats = sorted(set(potential_stats), reverse=True)
            
            if len(potential_stats) >= 3:
                # Typical pattern: largest is followers, middle is following, smallest is posts
                if result['followers'] == 0:
                    result['followers'] = potential_stats[0]
                    result['method_used'].append('guess_largest_followers')
                if result['following'] == 0 and len(potential_stats) > 1:
                    result['following'] = potential_stats[1]
                    result['method_used'].append('guess_middle_following')
                if result['posts'] == 0 and len(potential_stats) > 2:
                    result['posts'] = potential_stats[-1]  # Usually smallest
                    result['method_used'].append('guess_smallest_posts')
                    
        except Exception as e:
            print(f"⚠️  Visible numbers extraction failed: {e}")
    
    async def extract_by_text_patterns(self, page, result):
        """Extract by looking for specific text patterns."""
        try:
            # Look for elements containing "followers" text
            if result['followers'] == 0:
                followers_elements = await page.query_selector_all('text=/.*followers?/i')
                for element in followers_elements:
                    try:
                        # Get parent element which might contain the number
                        parent = await element.query_selector('xpath=..')
                        if parent:
                            text = await parent.text_content()
                            number = self.extract_number_from_text(text)
                            if number > 0:
                                result['followers'] = number
                                result['method_used'].append('text_pattern_followers')
                                break
                    except:
                        continue
            
            # Look for elements containing "following" text
            if result['following'] == 0:
                following_elements = await page.query_selector_all('text=/.*following/i')
                for element in following_elements:
                    try:
                        # Get parent element which might contain the number
                        parent = await element.query_selector('xpath=..')
                        if parent:
                            text = await parent.text_content()
                            number = self.extract_number_from_text(text)
                            if number > 0:
                                result['following'] = number
                                result['method_used'].append('text_pattern_following')
                                break
                    except:
                        continue
                        
        except Exception as e:
            print(f"⚠️  Text pattern extraction failed: {e}")
    
    async def extract_from_page_text(self, page, result):
        """Extract from the full page text using regex patterns."""
        try:
            page_text = await page.text_content('body')
            
            # Patterns for followers
            followers_patterns = [
                r'([0-9.,]+[KMB]?)\s+followers?',
                r'followers?\s*[:\-]?\s*([0-9.,]+[KMB]?)',
                r'([0-9.,]+[KMB]?)\s*people\s+follow',
            ]
            
            # Patterns for following
            following_patterns = [
                r'([0-9.,]+[KMB]?)\s+following',
                r'following\s*[:\-]?\s*([0-9.,]+[KMB]?)',
                r'follows\s+([0-9.,]+[KMB]?)',
            ]
            
            # Patterns for posts
            posts_patterns = [
                r'([0-9.,]+[KMB]?)\s+posts?',
                r'posts?\s*[:\-]?\s*([0-9.,]+[KMB]?)',
            ]
            
            if result['followers'] == 0:
                for pattern in followers_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['followers'] = self.convert_to_number(match.group(1))
                        result['method_used'].append('page_text_followers')
                        break
            
            if result['following'] == 0:
                for pattern in following_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['following'] = self.convert_to_number(match.group(1))
                        result['method_used'].append('page_text_following')
                        break
            
            if result['posts'] == 0:
                for pattern in posts_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['posts'] = self.convert_to_number(match.group(1))
                        result['method_used'].append('page_text_posts')
                        break
                        
        except Exception as e:
            print(f"⚠️  Page text extraction failed: {e}")
    
    async def extract_with_scrolling(self, page, result):
        """Try scrolling to load more content and extract."""
        try:
            print("🔄 Trying with scrolling...")
            
            # Scroll down a few times to load dynamic content
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await asyncio.sleep(2)
            
            # Try extracting again after scrolling
            await self.extract_from_page_text(page, result)
            
        except Exception as e:
            print(f"⚠️  Scrolling extraction failed: {e}")
    
    async def extract_from_meta_and_structured_data(self, page, result):
        """Extract from meta tags and structured data."""
        try:
            print("🔄 Trying meta tags and structured data...")
            
            # Look for JSON-LD structured data
            json_ld_elements = await page.query_selector_all('script[type="application/ld+json"]')
            for element in json_ld_elements:
                try:
                    content = await element.text_content()
                    if content:
                        import json
                        data = json.loads(content)
                        
                        # Look for social media structured data
                        if isinstance(data, dict):
                            if 'interactionStatistic' in data:
                                for stat in data['interactionStatistic']:
                                    if 'userInteractionCount' in stat:
                                        count = int(stat['userInteractionCount'])
                                        if 'FollowAction' in str(stat) and result['followers'] == 0:
                                            result['followers'] = count
                                            result['method_used'].append('structured_data_followers')
                except:
                    continue
            
            # Look for meta tags with social media info
            meta_tags = await page.query_selector_all('meta[property], meta[name]')
            for tag in meta_tags:
                try:
                    property_name = await tag.get_attribute('property') or await tag.get_attribute('name')
                    content = await tag.get_attribute('content')
                    
                    if property_name and content:
                        # Look for Instagram-specific meta tags
                        if 'instagram' in property_name.lower() or 'followers' in property_name.lower():
                            number = self.extract_number_from_text(content)
                            if number > 0 and result['followers'] == 0:
                                result['followers'] = number
                                result['method_used'].append('meta_tag_followers')
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️  Meta tag extraction failed: {e}")
    
    async def extract_aggressive_text_search(self, page, result):
        """More aggressive text extraction for login walls."""
        try:
            print("🔄 Trying aggressive text search...")
            
            # Get all text content, including hidden elements
            all_text = await page.evaluate('''
                () => {
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    
                    let text = '';
                    let node;
                    while (node = walker.nextNode()) {
                        text += node.nodeValue + ' ';
                    }
                    return text;
                }
            ''')
            
            # More aggressive patterns for login-walled content
            if result['followers'] == 0:
                aggressive_follower_patterns = [
                    r'(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?)\s*(?:followers?|people follow)',
                    r'follow(?:ers?)?\s*[:\-•]\s*(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?)',
                    r'(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?)\s*followers?',
                ]
                
                for pattern in aggressive_follower_patterns:
                    matches = re.findall(pattern, all_text, re.IGNORECASE)
                    for match in matches:
                        number = self.convert_to_number(match)
                        if number > 0:  # Any positive number for followers
                            result['followers'] = number
                            result['method_used'].append('aggressive_text_followers')
                            break
                    if result['followers'] > 0:
                        break
                        
        except Exception as e:
            print(f"⚠️  Aggressive text search failed: {e}")
    
    def extract_number_from_text(self, text):
        """Extract the first meaningful number from text."""
        if not text:
            return 0
        
        # Look for number patterns (including K, M, B suffixes)
        pattern = r'([0-9.,]+[KMB]?)'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            return self.convert_to_number(match.group(1))
        
        return 0
    
    def convert_to_number(self, text):
        """Convert text like '1.4M', '10K', '13,145' to actual number."""
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
        """Scrape multiple Instagram profiles with shared browser session."""
        
        # Create browser session once and reuse it
        print("🔄 Setting up browser session...")
        await self.setup_browser()
        
        # Try to login once at the beginning if credentials are provided
        if self.username and self.password and not self.logged_in:
            print("🔑 Attempting initial login...")
            await self.login_to_instagram()
        
        try:
            for i, url in enumerate(urls):
                print(f"\n📄 Processing page {i+1}/{len(urls)}")
                
                # Try scraping with retries
                max_retries = 2
                result = None
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            print(f"🔄 Retry attempt {attempt + 1}/{max_retries}")
                            # Wait between retries
                            await asyncio.sleep(random.uniform(5, 10))
                        
                        result = await self.scrape_page(url)
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        print(f"❌ Attempt {attempt + 1} failed: {str(e)[:100]}...")
                        if attempt == max_retries - 1:
                            # Final attempt failed, create error result
                            result = {
                                'page_url': url,
                                'final_url': url,
                                'followers': 0,
                                'following': 0,
                                'posts': 0,
                                'success': False,
                                'method_used': [],
                                'error': f'All {max_retries} attempts failed. Last error: {str(e)}'
                            }
                
                self.results.append(result)
                
                # Random delay between pages to avoid rate limiting
                if i < len(urls) - 1:
                    delay = random.uniform(3, 8)  # Shorter delay since we're reusing session
                    print(f"⏳ Waiting {delay:.1f} seconds before next page...")
                    await asyncio.sleep(delay)
        
        finally:
            # Clean up browser session at the end
            await self.cleanup()
        
        return self.results
    
    async def cleanup(self):
        """Clean up browser resources."""
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

