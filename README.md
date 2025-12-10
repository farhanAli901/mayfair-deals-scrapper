# Product Deal Extractor API

A FastAPI-based service to extract product information and images from e-commerce websites (Noon, Amazon, Carrefour, Shopify, etc.)

## Features

✅ **Multi-Site Support**
- Noon.com
- Amazon
- Carrefour
- Shopify stores
- Any e-commerce website

✅ **Product Information Extraction**
- Product title, brand, category
- Original & discounted prices
- Discount percentage
- Expiry date
- Detailed product description

✅ **Image Download**
- Automatic product image detection
- Fallback folder naming if extraction fails
- File size reporting
- Support for lazy-loaded images

✅ **Cloud Ready**
- Docker & Docker Compose support
- Environment variable configuration
- Health check endpoints
- Error handling & logging

---

## Quick Start

### 1. Clone/Setup
```bash
cd "Selenium automation"
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set API Key
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### 4. Run Server
```bash
python api.py
```

Server starts at: `http://localhost:8000`

### 5. Test
```bash
curl -X POST "http://localhost:8000/extract-product" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://noon.com/product"}'
```

---

## API Usage

### Endpoint: POST /extract-product

**Request:**
```json
{
  "url": "https://noon.com/uae/en/p/B07XJ1NYPB",
  "save_image": true
}
```

**Response (200 OK):**
```json
{
  "title": "Samsung Galaxy S24 Ultra",
  "brand": "Samsung",
  "category": "Electronics",
  "original_price": "AED 4999",
  "discounted_price": "AED 3499",
  "discount_percentage": "30% OFF",
  "expiry_date": "2025-12-31",
  "description": "Latest Samsung flagship with advanced features...",
  "images": ["Samsung_Galaxy_S24_Ultra_20251210_143522/1.jpg"],
  "image_count": 1
}
```

**Response (Error):**
```json
{
  "detail": "Failed to extract product: Connection timeout"
}
```

---

## Docker Deployment

### Build Image
```bash
docker build -t product-api:latest .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="your-api-key" \
  product-api:latest
```

### Using Docker Compose
```bash
OPENAI_API_KEY="your-api-key" docker-compose up
```

---

## Cloud Deployment

See **DEPLOYMENT.md** for detailed instructions for:
- AWS EC2
- Google Cloud Run
- Azure Container Instances
- Heroku
- DigitalOcean

---

## API Documentation

Interactive API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## File Structure

```
.
├── api.py                  # FastAPI server
├── app.py                  # Core ProductDealAgent class
├── test_client.py          # Example client for testing
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker compose config
├── DEPLOYMENT.md           # Cloud deployment guide
├── .env.example            # Environment configuration template
└── README.md               # This file
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `PORT` | No | 8000 | Port to run server |
| `HOST` | No | 0.0.0.0 | Server host |

### Browser Options

Edit `app.py` to customize Selenium options:
```python
chrome_options.add_argument('--headless')      # Run without UI
chrome_options.add_argument('--no-sandbox')    # For Docker
chrome_options.add_argument('--disable-dev-shm-usage')  # Memory
```

---

## Performance

| Metric | Value |
|--------|-------|
| Processing Time | 15-30 seconds |
| Memory Usage | ~800MB per instance |
| Concurrent Requests | 1 (single worker) |
| Image Download | 3-10 seconds |
| Max Request Timeout | 60 seconds |

---

## Error Handling

The API handles various error scenarios:

| Error | Status | Description |
|-------|--------|-------------|
| Invalid URL | 400 | URL format is incorrect |
| Connection Timeout | 500 | Target website unreachable |
| AI Extraction Failed | 500 | Screenshot analysis failed |
| Image Download Failed | 200 | Returns product data without image |

---

## Example Clients

### Python
```python
import requests

response = requests.post(
    "http://localhost:8000/extract-product",
    json={"url": "https://noon.com/product"}
)
print(response.json())
```

### JavaScript
```javascript
fetch('http://localhost:8000/extract-product', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'https://noon.com/product' })
})
.then(r => r.json())
.then(data => console.log(data));
```

### cURL
```bash
curl -X POST http://localhost:8000/extract-product \
  -H "Content-Type: application/json" \
  -d '{"url": "https://noon.com/product"}'
```

---

## Troubleshooting

### Server won't start
- Check if port 8000 is in use: `lsof -i :8000`
- Verify OPENAI_API_KEY is set: `echo $OPENAI_API_KEY`

### Chromium not found
- Install: `apt-get install chromium-browser chromium-driver`
- Or use Docker (includes Chromium)

### Slow extraction
- Normal: 15-30 seconds per request
- Check target website load time
- Increase timeout: Edit `api.py`

### Image not downloading
- Check folder permissions
- Verify disk space available
- Check image URL in logs

---

## Support

For issues or questions:
1. Check DEPLOYMENT.md for setup help
2. Review error logs for details
3. Test with different URLs
4. Verify OPENAI_API_KEY is valid

---

## License

This project is for authorized use only.
