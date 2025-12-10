from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from openai import OpenAI
import json
import base64
from pathlib import Path
from PIL import Image
import io
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
app = FastAPI()

class ProductDealAgent:
    def __init__(self, openai_api_key):
        self.client = OpenAI(api_key=openai_api_key)
        self.driver = None
    
    def setup_browser(self):
        """Initialize Chrome browser with Selenium"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # Remove this line - let Chrome auto-detect
        # chrome_options.binary_location = "/usr/bin/chromium-browser"
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
    def close_browser(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
    
    def capture_screenshots(self, url):
        """Open URL, take screenshots while scrolling - captures 3 sections for better coverage"""
        try:
            print(f"Opening URL: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(5)
            
            screenshots = []
            
            # Get page dimensions
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            # Take first screenshot (top section - usually has product image and title)
            print("Capturing screenshot 1 (top section)...")
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            screenshot1 = self.driver.get_screenshot_as_png()
            screenshots.append(screenshot1)
            
            # Calculate scroll positions for 3 sections
            # Section 2: First third to middle (catches product details, price, description start)
            scroll_position_2 = min(viewport_height * 0.8, total_height * 0.33)
            self.driver.execute_script(f"window.scrollTo(0, {scroll_position_2});")
            time.sleep(2)
            
            print("Capturing screenshot 2 (middle section)...")
            screenshot2 = self.driver.get_screenshot_as_png()
            screenshots.append(screenshot2)
            
            # Section 3: Second third to bottom (catches full description, specs, reviews)
            if total_height > viewport_height * 1.5:
                scroll_position_3 = min(total_height * 0.66, total_height - viewport_height)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position_3});")
                time.sleep(2)
                
                print("Capturing screenshot 3 (lower section)...")
                screenshot3 = self.driver.get_screenshot_as_png()
                screenshots.append(screenshot3)
            else:
                # For shorter pages, capture bottom section
                self.driver.execute_script(f"window.scrollTo(0, {max(0, total_height - viewport_height)});")
                time.sleep(2)
                
                print("Capturing screenshot 3 (bottom section)...")
                screenshot3 = self.driver.get_screenshot_as_png()
                screenshots.append(screenshot3)
            
            print(f"✓ Successfully captured {len(screenshots)} screenshots")
            return screenshots
            
        except Exception as e:
            print(f"Error capturing screenshots: {str(e)}")
            return None
    
    def find_gallery_containers(self):
        """Identify product gallery containers from the page"""
        gallery_selectors = [
            "[data-gallery]",
            ".product-gallery",
            ".product__media",
            ".woocommerce-product-gallery",
            ".product-images",
            ".product-image-gallery",
            ".gallery",
            ".swiper-slide",
            ".slick-slide",
            "[data-carousel]",
            ".carousel-item",
            ".image-gallery",
            ".photo-gallery",
            "[class*='gallery']",
            "[class*='product-image']",
            "[class*='media']",
        ]
        
        gallery_containers = []
        
        for selector in gallery_selectors:
            try:
                containers = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for container in containers:
                    if container not in gallery_containers:
                        gallery_containers.append(container)
            except:
                continue
        
        return gallery_containers
    
    def extract_image_urls_from_gallery(self, gallery_containers):
        """Extract image URLs from identified gallery containers"""
        image_urls = []
        seen_filenames = set()  # Track duplicates
        
        for container in gallery_containers:
            try:
                # Find all images within this container
                images = container.find_elements(By.TAG_NAME, "img")
                
                for img_element in images:
                    # Check if image dimensions are adequate (width >= 300px)
                    try:
                        width = img_element.size.get('width', 0)
                        if width < 300:
                            continue
                    except:
                        pass
                    
                    # Extract URLs from multiple attributes
                    image_url = None
                    
                    # Priority 1: data-large_image
                    image_url = img_element.get_attribute("data-large_image")
                    
                    # Priority 2: src
                    if not image_url:
                        image_url = img_element.get_attribute("src")
                    
                    # Priority 3: data-src (lazy loading)
                    if not image_url:
                        image_url = img_element.get_attribute("data-src")
                    
                    # Priority 4: srcset (pick the largest)
                    if not image_url:
                        srcset = img_element.get_attribute("srcset")
                        if srcset:
                            # Extract the last (largest) URL from srcset
                            srcset_urls = [url.split()[0] for url in srcset.split(",")]
                            image_url = srcset_urls[-1] if srcset_urls else None
                    
                    # Check if parent is a zoom link
                    if not image_url:
                        parent_link = img_element.find_element(By.XPATH, "parent::a")
                        try:
                            image_url = parent_link.get_attribute("href")
                        except:
                            pass
                    
                    if image_url:
                        # Normalize URL
                        image_url = image_url.strip()
                        
                        # Handle relative URLs
                        if image_url.startswith('/'):
                            base_url = self.driver.execute_script("return window.location.origin")
                            image_url = base_url + image_url
                        elif not image_url.startswith(('http://', 'https://')):
                            # Might be a protocol-relative URL
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            else:
                                base_url = self.driver.execute_script("return window.location.origin")
                                if not image_url.startswith('/'):
                                    image_url = '/' + image_url
                                image_url = base_url + image_url
                        
                        # Avoid duplicates
                        filename = urlparse(image_url).path.split('/')[-1]
                        if filename not in seen_filenames:
                            image_urls.append(image_url)
                            seen_filenames.add(filename)
            
            except Exception as e:
                print(f"⚠ Error extracting images from container: {str(e)}")
                continue
        
        return image_urls
    
    def optimize_image_url(self, image_url):
        """Optimize image URL for highest quality"""
        # Shopify optimization: convert to highest resolution
        if 'cdn.shopify.com' in image_url or 'shopifycdn' in image_url:
            image_url = re.sub(r'_\d+x\d+\.', '_2048x2048.', image_url)
        
        return image_url
    
    def download_image_with_retry(self, image_url, save_path, max_retries=3):
        """Download a single image with retry logic"""
        for attempt in range(max_retries):
            try:
                response = requests.get(image_url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    return True
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"⚠ Failed to download after {max_retries} retries: {image_url[:50]}... - {str(e)}")
                    return False
                time.sleep(1)  # Wait before retry
        
        return False
    
    def extract_product_gallery_images(self, product_name, max_images=5):
        """
        Extract product gallery images with quality filtering and deduplication.
        
        Args:
            product_name: Name of the product (used for folder naming)
            max_images: Maximum number of images to keep (3-5, default: 5)
        
        Returns:
            List of saved image paths (deduplicated, max 5), or empty list if no images found
        """
        saved_images = []
        
        try:
            print("🔍 Identifying product gallery containers...")
            gallery_containers = self.find_gallery_containers()
            
            if not gallery_containers:
                print("⚠ No gallery containers found, searching all images...")
                # Fallback: find all images on the page
                all_images = self.driver.find_elements(By.TAG_NAME, "img")
                gallery_containers = all_images
            
            print(f"✓ Found {len(gallery_containers)} potential gallery containers")
            
            # Extract image URLs
            image_urls = self.extract_image_urls_from_gallery(gallery_containers)
            print(f"✓ Extracted {len(image_urls)} unique image URLs")
            
            if not image_urls:
                print("⚠ No product images found")
                return saved_images
            
            # Limit to max_images (3-5 range)
            image_urls = image_urls[:max_images]
            print(f"✓ Limited to {len(image_urls)} images for download")
            
            # Create folder for product images
            # Sanitize product name for folder creation
            safe_product_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '-', '_'))[:50]
            safe_product_name = safe_product_name.replace(' ', '_').strip('_')
            
            if not safe_product_name:
                safe_product_name = "product_images"
            
            product_folder = Path(safe_product_name)
            product_folder.mkdir(exist_ok=True)
            
            print(f"📁 Saving images to folder: {product_folder}")
            
            # Track downloaded images to avoid duplicates
            downloaded_files = set()
            
            # Download images in parallel
            download_tasks = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                for idx, image_url in enumerate(image_urls, 1):
                    # Optimize URL
                    image_url = self.optimize_image_url(image_url)
                    
                    # Use simple numbered naming
                    save_path = product_folder / f"{idx}.jpg"
                    task = executor.submit(self.download_image_with_retry, image_url, str(save_path))
                    download_tasks.append((idx, image_url, save_path, task))
            
            # Collect results (maintain order, skip failed downloads)
            for idx, image_url, save_path, task in download_tasks:
                if task.result():
                    image_path_str = str(save_path).replace('\\', '/')
                    # Only add if successfully downloaded and not already added
                    if image_path_str not in downloaded_files:
                        saved_images.append(image_path_str)
                        downloaded_files.add(image_path_str)
                        print(f"✓ Downloaded image {idx}: {image_path_str}")
                else:
                    print(f"✗ Failed to download image {idx}: {image_url[:50]}...")
            
            # Final limit: ensure we never return more than 5 images
            saved_images = saved_images[:5]
            
            print(f"✓ Successfully saved {len(saved_images)} images")
            return saved_images
        
        except Exception as e:
            print(f"❌ Error in extract_product_gallery_images: {str(e)}")
            return saved_images
    
    def encode_image_from_bytes(self, image_bytes):
        """Encode image bytes to base64"""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def extract_product_info_from_screenshots(self, screenshots, url):
        """Extract product information from multiple screenshots using Vision API"""
        try:
            # Prepare multiple images for the API
            image_contents = []
            
            for i, screenshot in enumerate(screenshots):
                image_base64 = self.encode_image_from_bytes(screenshot)
                image_contents.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                })
            
            # Create the prompt
            prompt_text = {
                "type": "text",
                "text": f"""You are analyzing a product deal page from {url}. I'm providing you with 3 screenshots covering different sections of the page (top, middle, and bottom).

Your task is to CAREFULLY and INTELLIGENTLY extract product information with HIGH ACCURACY.

IMPORTANT INSTRUCTIONS:

1. **Deal Title**: Extract the main product title/name (usually at the top of the page, often in large text)

2. **Brand**: Find the brand name (may be shown near the title, in product details, or as a separate field)

3. **Category**: Identify the product category (e.g., Electronics, Fashion, Food & Beverages, Home & Kitchen, etc.)

4. **Original Price (AED)**: Find the original/regular price BEFORE any discount. Look for crossed-out prices, "Was" prices, or "Regular Price". MUST be in AED currency format.

5. **Discount Price (AED)**: Find the current/sale price AFTER discount. Look for highlighted prices, "Now" prices, or "Sale Price". MUST be in AED currency format.

6. **Expiry Date**: Look for expiry date, validity date, or "offer valid until" date. This could be for the deal expiry OR product expiry (food/medicine).

7. **Description**: This is CRITICAL - Be INTELLIGENT and thorough:
   - Look for sections labeled: "Product Overview", "Description", "Details", "About this item", "Features", "Specifications", "Product Information"
   - The description might be in bullet points or paragraph form
   - Include ALL relevant details: what the product is, features, specifications, materials, dimensions, usage instructions
   - Combine information from multiple sections if needed
   - If you see product specs/features, include them in the description

8. **Image**: The screenshots contain the product image - we will extract it separately

PRICE FORMAT RULES:
- Always express prices in AED (if shown in different currency, note it but keep original)
- Format: "AED XXX" or "XXX AED" 
- If you see "د.إ" or "Dhs" or "Dirham", convert to "AED" format
- Example: "AED 299" or "299.99 AED"

Return the information in this EXACT JSON format:
{{
    "title": "product title here",
    "brand": "brand name",
    "category": "product category",
    "original_price": "AED amount",
    "discounted_price": "AED amount",
    "discount_percentage": "XX% OFF" or "Not found",
    "expiry_date": "date" or "Not found",
    "description": "comprehensive product description including all features, specs, and details"
}}

If any field is not found in ANY of the screenshots, use "Not found" as the value.
ANALYZE ALL 3 SCREENSHOTS CAREFULLY before responding. Be thorough and accurate."""
            }
            
            # Combine prompt and images
            content = [prompt_text] + image_contents
            
            print("Analyzing screenshots with AI...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result = response.choices[0].message.content
            
            # Extract JSON from the response
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            
            product_data = json.loads(result)
            return product_data
            
        except Exception as e:
            return {"error": f"Error extracting info from screenshots: {str(e)}"}
    
    def get_product_deal(self, url, save_image=True):
        """Main method to get product deal information"""
        try:
            # Setup browser
            self.setup_browser()
            
            # Capture screenshots
            screenshots = self.capture_screenshots(url)
            
            if not screenshots:
                return {"error": "Failed to capture screenshots"}
            
            # Extract product information from all screenshots
            product_info = self.extract_product_info_from_screenshots(screenshots, url)
            
            # Download product gallery images (3-5 images max)
            if save_image and "error" not in product_info:
                product_name = product_info.get("title", "Product")
                image_paths = self.extract_product_gallery_images(product_name, max_images=5)
                
                # Clean and deduplicate image paths
                unique_images = []
                seen_paths = set()
                for img_path in image_paths:
                    normalized_path = str(img_path).replace('\\', '/').strip()
                    if normalized_path and normalized_path not in seen_paths:
                        unique_images.append(normalized_path)
                        seen_paths.add(normalized_path)
                
                # Limit to 5 images max
                unique_images = unique_images[:5]
                
                # Add to product info
                product_info["images"] = unique_images
                product_info["image_count"] = len(unique_images)
            else:
                # No images if error or save_image is False
                product_info["images"] = []
                product_info["image_count"] = 0
            
            # Ensure clean JSON structure (no duplicate fields)
            clean_result = {
                "title": product_info.get("title", "Not found"),
                "brand": product_info.get("brand", "Not found"),
                "category": product_info.get("category", "Not found"),
                "original_price": product_info.get("original_price", "Not found"),
                "discounted_price": product_info.get("discounted_price", "Not found"),
                "discount_percentage": product_info.get("discount_percentage", "Not found"),
                "expiry_date": product_info.get("expiry_date", "Not found"),
                "description": product_info.get("description", "Not found"),
                "images": product_info.get("images", []),
                "image_count": product_info.get("image_count", 0)
            }
            
            return clean_result
            
        except Exception as e:
            return {"error": f"Error: {str(e)}"}
        
        finally:
            # Always close browser
            self.close_browser()


class URLRequest(BaseModel):
    url: str
    save_image: bool = True


@app.post("/extract-product")
async def extract_product(request: URLRequest):
    """
    Extract product deal information from a given URL
    """
    try:
        url = request.url.strip()
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Initialize the agent with OpenAI API key
        api_key = OPENAI_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        agent = ProductDealAgent(api_key)
        
        result = agent.get_product_deal(url, save_image=request.save_image)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """
    Root endpoint with API information
    """
    return {
        "message": "Product Deal Extractor API",
        "version": "1.0",
        "endpoints": {
            "/extract-product": "POST - Extract product information from URL"
        },
        "usage": {
            "method": "POST",
            "endpoint": "/extract-product",
            "body": {
                "url": "https://example.com/product",
                "save_image": True
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)