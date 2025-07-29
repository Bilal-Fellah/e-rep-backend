#!/usr/bin/env python3
"""
LinkedIn Company Page Scraper using Playwright
Scrapes follower counts and employee numbers from LinkedIn company pages
"""

import asyncio
import re
import json
import random
import time
from playwright.async_api import async_playwright
from urllib.parse import urlparse

class LinkedInPlaywrightScraper:
    def __init__(self, headless=True, slow_mo=1000):
        self.headless = headless
        self.slow_mo = slow_mo
        self.results = []
    
    async def setup_browser(self):
        """Set up Playwright browser with stealth settings."""
        self.playwright = await async_playwright().start()
        
        # Use Chrome browser with enhanced stealth settings
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
        """Scrape a single LinkedIn company page."""
        page = await self.context.new_page()
        
        try:
            print(f"🔍 Scraping: {url}")
            
            # Use domcontentloaded strategy (proven to work reliably)
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
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
            
            # Check if we need to handle login popup or other redirects
            current_url = page.url
            if 'authwall' in current_url or 'login' in current_url:
                print(f"⚠️  Hit login wall, trying to extract what we can")
                # Try to dismiss any login modals/popups
                try:
                    # Look for and close any modal dialogs
                    close_buttons = await page.query_selector_all('[aria-label="Dismiss"], [aria-label="Close"], .modal__dismiss, .artdeco-modal__dismiss')
                    for button in close_buttons:
                        try:
                            await button.click()
                            await asyncio.sleep(1)
                        except:
                            continue
                except:
                    pass
            
            # Initialize result
            result = {
                'page_url': url,
                'final_url': current_url,
                'followers': 0,
                'employees': 0,
                'success': False,
                'method_used': [],
                'error': None
            }
            
            # Method 1: Look for specific LinkedIn selectors
            await self.extract_by_linkedin_selectors(page, result)
            
            # Method 2: Look for text patterns
            if result['followers'] == 0 or result['employees'] == 0:
                await self.extract_by_text_patterns(page, result)
            
            # Method 3: Extract from page text with broader patterns
            if result['followers'] == 0 or result['employees'] == 0:
                await self.extract_from_page_text(page, result)
            
            # Method 4: Try scrolling and looking for more content
            if result['followers'] == 0 or result['employees'] == 0:
                await self.extract_with_scrolling(page, result)
            
            # Method 5: Try extracting from meta tags and structured data
            if result['followers'] == 0 or result['employees'] == 0:
                await self.extract_from_meta_and_structured_data(page, result)
            
            # Method 6: Try more aggressive text extraction for login walls
            if result['followers'] == 0 or result['employees'] == 0:
                await self.extract_aggressive_text_search(page, result)
            
            # Check success
            if result['followers'] > 0 or result['employees'] > 0:
                result['success'] = True
                print(f"✅ Success! Followers: {result['followers']:,}, Employees: {result['employees']:,}")
            else:
                result['error'] = 'No follower/employee data found'
                print(f"❌ No data found")
            
            return result
            
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            return {
                'page_url': url,
                'final_url': page.url if page else url,
                'followers': 0,
                'employees': 0,
                'success': False,
                'method_used': [],
                'error': str(e)
            }
        finally:
            await page.close()
    
    async def extract_by_linkedin_selectors(self, page, result):
        """Extract using LinkedIn-specific CSS selectors."""
        try:
            # Followers selector based on the provided HTML
            followers_selectors = [
                '.org-top-card-summary-info-list__info-item',
                '.org-top-card-summary-info-list__info-item:has-text("followers")',
                '[data-test-id*="followers"]',
                '.follower-count',
                '.org-page-details__definition dt:has-text("Followers") + dd',
            ]
            
            for selector in followers_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.text_content()
                        if text and ('followers' in text.lower() or 'follower' in text.lower()):
                            number = self.extract_number_from_text(text)
                            if number > 0 and result['followers'] == 0:
                                result['followers'] = number
                                result['method_used'].append('linkedin_followers_selector')
                                break
                except:
                    continue
            
            # Employees selector based on the provided HTML
            employees_selectors = [
                '.t-normal.t-black--light.link-without-visited-state.link-without-hover-state',
                '.org-top-card-summary-info-list__info-item:has-text("employees")',
                '[data-test-id*="employees"]',
                '.employee-count',
                '.org-page-details__definition dt:has-text("Company size") + dd',
                '.org-page-details__definition dt:has-text("Employees") + dd',
            ]
            
            for selector in employees_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.text_content()
                        if text and ('employees' in text.lower() or 'employee' in text.lower()):
                            number = self.extract_number_from_text(text)
                            if number > 0 and result['employees'] == 0:
                                result['employees'] = number
                                result['method_used'].append('linkedin_employees_selector')
                                break
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️  LinkedIn selector extraction failed: {e}")
    
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
            
            # Look for elements containing "employees" text
            if result['employees'] == 0:
                employees_elements = await page.query_selector_all('text=/.*employees?/i')
                for element in employees_elements:
                    try:
                        # Get parent element which might contain the number
                        parent = await element.query_selector('xpath=..')
                        if parent:
                            text = await parent.text_content()
                            number = self.extract_number_from_text(text)
                            if number > 0:
                                result['employees'] = number
                                result['method_used'].append('text_pattern_employees')
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
                r'Follow\s+([0-9.,]+[KMB]?)',
            ]
            
            # Patterns for employees
            employees_patterns = [
                r'([0-9.,]+[KMB]?\+?)\s+employees?',
                r'employees?\s*[:\-]?\s*([0-9.,]+[KMB]?\+?)',
                r'Company\s+size\s*[:\-]?\s*([0-9.,]+[KMB]?\+?)',
                r'([0-9.,]+[KMB]?\+?)\s*people\s+work',
                r'Staff\s+size\s*[:\-]?\s*([0-9.,]+[KMB]?\+?)',
            ]
            
            if result['followers'] == 0:
                for pattern in followers_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['followers'] = self.convert_to_number(match.group(1))
                        result['method_used'].append('page_text_followers')
                        break
            
            if result['employees'] == 0:
                for pattern in employees_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['employees'] = self.convert_to_number(match.group(1))
                        result['method_used'].append('page_text_employees')
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
                        
                        # Look for employee count in structured data
                        if isinstance(data, dict):
                            if 'numberOfEmployees' in data and result['employees'] == 0:
                                result['employees'] = int(data['numberOfEmployees'])
                                result['method_used'].append('structured_data_employees')
                            
                            # Look for follower count in social media profiles
                            if 'sameAs' in data or 'followersCount' in data:
                                # Could contain social media info
                                pass
                except:
                    continue
            
            # Look for meta tags with company info
            meta_tags = await page.query_selector_all('meta[property], meta[name]')
            for tag in meta_tags:
                try:
                    property_name = await tag.get_attribute('property') or await tag.get_attribute('name')
                    content = await tag.get_attribute('content')
                    
                    if property_name and content:
                        # Look for employee-related meta tags
                        if any(word in property_name.lower() for word in ['employee', 'staff', 'team']) and result['employees'] == 0:
                            number = self.extract_number_from_text(content)
                            if number > 0:
                                result['employees'] = number
                                result['method_used'].append('meta_tag_employees')
                        
                        # Look for follower-related meta tags
                        if any(word in property_name.lower() for word in ['follower', 'follow']) and result['followers'] == 0:
                            number = self.extract_number_from_text(content)
                            if number > 0:
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
                    r'followers?\s*(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?)',
                ]
                
                for pattern in aggressive_follower_patterns:
                    matches = re.findall(pattern, all_text, re.IGNORECASE)
                    for match in matches:
                        number = self.convert_to_number(match)
                        if number > 1000:  # Reasonable threshold for followers
                            result['followers'] = number
                            result['method_used'].append('aggressive_text_followers')
                            break
                    if result['followers'] > 0:
                        break
            
            if result['employees'] == 0:
                aggressive_employee_patterns = [
                    r'(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?\+?)\s*(?:employees?|staff|people)',
                    r'employ(?:ees?)?\s*[:\-•]\s*(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?\+?)',
                    r'company\s*size\s*[:\-•]\s*(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?\+?)',
                    r'(\d+(?:,\d{3})*(?:\.\d+)?[KMB]?\+?)\s*employees?',
                ]
                
                for pattern in aggressive_employee_patterns:
                    matches = re.findall(pattern, all_text, re.IGNORECASE)
                    for match in matches:
                        number = self.convert_to_number(match)
                        if number > 10:  # Reasonable threshold for employees
                            result['employees'] = number
                            result['method_used'].append('aggressive_text_employees')
                            break
                    if result['employees'] > 0:
                        break
                        
        except Exception as e:
            print(f"⚠️  Aggressive text search failed: {e}")
    
    def extract_number_from_text(self, text):
        """Extract the first meaningful number from text."""
        if not text:
            return 0
        
        # Look for number patterns (including K, M, B suffixes and + signs)
        pattern = r'([0-9.,]+[KMB]?\+?)'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            return self.convert_to_number(match.group(1))
        
        return 0
    
    def convert_to_number(self, text):
        """Convert text like '1.4M', '10K+' to actual number."""
        if not text:
            return 0
        
        text = str(text).strip().lower()
        
        # Remove + sign if present
        text = text.replace('+', '')
        
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
        """Scrape multiple LinkedIn company pages with fresh browser session for each."""
        
        for i, url in enumerate(urls):
            print(f"\n📄 Processing page {i+1}/{len(urls)}")
            print("🔄 Creating fresh browser session...")
            
            # Create fresh browser session for each page to avoid login walls
            await self.setup_browser()
            
            try:
                # Try scraping with retries
                max_retries = 2  # Reduced retries since we have fresh sessions
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
                                'employees': 0,
                                'success': False,
                                'method_used': [],
                                'error': f'All {max_retries} attempts failed. Last error: {str(e)}'
                            }
                
                self.results.append(result)
                
            finally:
                # Clean up this browser session
                await self.cleanup()
                
                # Random delay between pages to avoid rate limiting
                if i < len(urls) - 1:
                    delay = random.uniform(2, 5)  # Longer delay between fresh sessions
                    print(f"⏳ Waiting {delay:.1f} seconds before next page...")
                    await asyncio.sleep(delay)
        
        return self.results
    
    async def cleanup(self):
        """Clean up browser resources."""
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

