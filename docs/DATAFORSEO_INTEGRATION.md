# DataForSEO Integration Documentation

## Overview
Successfully integrated DataForSEO API into the general-mcp server, adding powerful SEO and SERP analysis capabilities. DataForSEO provides comprehensive search engine optimization data including SERP results, keyword research, and competitor analysis.

## New Tools Added

### 1. `search_serp`
**Purpose**: Search Google SERP (Search Engine Results Page) data
**Parameters**:
- `query` (required): Search query to analyze
- `location` (optional): Location code (default: "United States") 
- `language` (optional): Language code (default: "en")
- `limit` (optional): Number of results (max 100, default: 10)

**Example Usage**:
```json
{
  "query": "python programming",
  "location": "New York",
  "language": "en", 
  "limit": 10
}
```

**Returns**: Formatted SERP results with titles, URLs, descriptions, and rankings

### 2. `keyword_research`
**Purpose**: Get keyword suggestions and search volume data
**Parameters**:
- `keywords` (required): Array of keywords to research (max 10)
- `location` (optional): Location for search volume data (default: "United States")
- `language` (optional): Language code (default: "en")

**Example Usage**:
```json
{
  "keywords": ["python", "programming", "tutorial"],
  "location": "United States",
  "language": "en"
}
```

**Returns**: Search volume, CPC, and competition data for each keyword

### 3. `competitor_analysis`
**Purpose**: Analyze competitor rankings and backlinks
**Parameters**:
- `domain` (required): Domain to analyze (e.g., "example.com")
- `analysis_type` (optional): Type of analysis - "organic", "backlinks", or "competitors" (default: "organic")
- `limit` (optional): Number of results to return (default: 10)

**Example Usage**:
```json
{
  "domain": "stackoverflow.com",
  "analysis_type": "competitors",
  "limit": 5
}
```

**Returns**: 
- **Organic**: Domain metrics (keywords, traffic, avg position)
- **Competitors**: Top competing domains with shared keywords
- **Backlinks**: Pages with most backlinks and referring domains

## Technical Implementation

### Authentication
DataForSEO uses HTTP Basic Authentication with login/password credentials:
```python
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
```

### API Configuration
- **Base URL**: `https://api.dataforseo.com/v3`
- **Timeout**: 30 seconds for reliable API calls
- **Authentication**: Base64 encoded Basic Auth
- **Content-Type**: `application/json`

### Error Handling
All tools include comprehensive error handling:
- Missing credentials: Returns informative mock response
- API errors: Shows DataForSEO status codes and messages
- Network issues: Graceful timeout and error responses
- Invalid parameters: Input validation and sanitization

### Cost Tracking
Each tool logs API usage with estimated costs:
- SERP searches: ~$0.0025 per request
- Keyword research: ~$0.001 per keyword
- Competitor analysis: ~$0.01 per request

## Setup Instructions

### 1. Get DataForSEO Credentials
1. Sign up at [DataForSEO.com](https://dataforseo.com/)
2. Get your login and password from the dashboard
3. Fund your account (typically $10-20 minimum)

### 2. Configure Environment Variables
```bash
export DATAFORSEO_LOGIN="your_login_here"
export DATAFORSEO_PASSWORD="your_password_here"
```

### 3. Test Integration
```bash
python test_dataforseo.py
```

## API Endpoints Used

### SERP Data
- **Endpoint**: `serp/google/organic/live/advanced`
- **Purpose**: Real-time Google SERP results
- **Data**: Rankings, titles, URLs, descriptions

### Keyword Research  
- **Endpoint**: `keywords_data/google_ads/search_volume/live`
- **Purpose**: Search volume and competition data
- **Data**: Monthly volume, CPC, competition level

### Competitor Analysis
- **Organic**: `dataforseo_labs/google/domain_rank_overview/live`
- **Competitors**: `dataforseo_labs/google/competitors_domain/live` 
- **Backlinks**: `backlinks/domain_pages/live`

## Benefits

### For SEO Professionals
- **SERP Tracking**: Monitor keyword rankings across locations
- **Keyword Research**: Find high-volume, low-competition keywords
- **Competitor Intelligence**: Analyze competitor strategies and backlinks

### For Content Creators
- **Content Ideas**: Discover trending keywords and topics
- **Competition Analysis**: Understand what content ranks well
- **Market Research**: Analyze search trends by location/language

### For Developers
- **SEO APIs**: Integrate search data into applications
- **Automation**: Programmatic access to SEO metrics
- **Reporting**: Generate automated SEO reports

## Cost Optimization

### Smart Defaults
- Limited results per request (max 10-100)
- Cached responses when possible
- Input validation to prevent excessive API calls

### Usage Monitoring
- All API calls logged with costs
- Real-time usage tracking
- Cost estimates provided to users

### Graceful Degradation
- Works without credentials (mock responses)
- Clear error messages for configuration issues
- Fallback to alternative tools when needed

## File Changes Made

### Core Integration
- **`mcp_stdio_server.py`**: Added DataForSEO tools and authentication
- **`server.py`**: Synchronized tools for FastAPI web interface
- **`count_tools.py`**: Updated tool count tracking

### Test Files
- **`test_dataforseo.py`**: Comprehensive integration testing
- **`DATAFORSEO_INTEGRATION.md`**: This documentation file

### Configuration
- Added environment variable support for credentials
- Integrated with existing API usage tracking system
- Added proper error handling and timeouts

## Current Tool Count
**Total: 18 tools** (15 original + 3 DataForSEO tools)

### By Category:
- **Reddit**: 3 tools
- **Twitter**: 2 tools  
- **Instagram**: 2 tools
- **TikTok**: 2 tools
- **YouTube**: 2 tools
- **AI/Search**: 3 tools (Perplexity, Google Trends)
- **SEO/SERP**: 3 tools (DataForSEO) ⭐ **NEW**
- **Performance**: 3 tools (Lighthouse)
- **Monitoring**: 1 tool

## Future Enhancements

### Additional DataForSEO Features
- Historical SERP data tracking
- Local SEO and Google My Business data
- Technical SEO audits and site analysis
- Social media mention tracking

### Integration Improvements
- Caching for frequently requested data
- Bulk operations for multiple domains/keywords
- Automated reporting and alerts
- Dashboard integration for visual analytics

## Support and Troubleshooting

### Common Issues
1. **"API Required" message**: Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD
2. **Timeout errors**: Check internet connection and API status
3. **Rate limit errors**: DataForSEO has generous limits, contact support if issues persist

### Getting Help
- DataForSEO Documentation: https://docs.dataforseo.com/
- Support Email: support@dataforseo.com
- API Status: https://status.dataforseo.com/

The DataForSEO integration significantly enhances the MCP server's capabilities, making it a comprehensive platform for SEO professionals, content creators, and developers who need reliable search engine data. 