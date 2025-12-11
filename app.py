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
    
    def get_product_deal(self, url):
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
            
            # Return only product information without images
            clean_result = {
                "title": product_info.get("title", "Not found"),
                "brand": product_info.get("brand", "Not found"),
                "category": product_info.get("category", "Not found"),
                "original_price": product_info.get("original_price", "Not found"),
                "discounted_price": product_info.get("discounted_price", "Not found"),
                "discount_percentage": product_info.get("discount_percentage", "Not found"),
                "expiry_date": product_info.get("expiry_date", "Not found"),
                "description": product_info.get("description", "Not found")
            }
            
            return clean_result
            
        except Exception as e:
            return {"error": f"Error: {str(e)}"}
        
        finally:
            # Always close browser
            self.close_browser()


class URLRequest(BaseModel):
    url: str


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
        
        result = agent.get_product_deal(url)
        
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
                "url": "https://example.com/product"
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)