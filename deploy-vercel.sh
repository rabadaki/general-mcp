#!/bin/bash

# Vercel Deployment Script for MCP Server
# This script helps you deploy your MCP server to Vercel

set -e  # Exit on any error

echo "🚀 MCP Server Vercel Deployment Script"
echo "======================================="

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Installing..."
    npm install -g vercel
fi

echo "✅ Vercel CLI is available"

# Check for required files
if [[ ! -f "vercel.json" ]]; then
    echo "❌ vercel.json not found!"
    exit 1
fi

if [[ ! -f "api/index.py" ]]; then
    echo "❌ api/index.py not found!"
    exit 1
fi

if [[ ! -f "server.py" ]]; then
    echo "❌ server.py not found!"
    exit 1
fi

echo "✅ All required files present"

# Test the server locally first
echo "🧪 Testing server locally..."
python3 -c "from server import app; print('✅ Server imports successfully')" || {
    echo "❌ Server import failed. Please fix the errors first."
    exit 1
}

echo "✅ Server passes basic import test"

# Deploy to Vercel
echo "🚀 Deploying to Vercel..."
echo ""
echo "📝 Instructions:"
echo "1. When prompted, choose your Vercel account/team"
echo "2. Choose a project name (or use the suggested one)"
echo "3. Confirm the settings"
echo ""
echo "After deployment, don't forget to set your environment variables:"
echo "- YOUTUBE_API_KEY"
echo "- APIFY_TOKEN"
echo "- PERPLEXITY_API_KEY"
echo "- SCRAPINGBEE_API_KEY"
echo ""

# Run Vercel deployment
vercel

echo ""
echo "🎉 Deployment initiated!"
echo ""
echo "📋 Next Steps:"
echo "1. Go to your Vercel dashboard: https://vercel.com/dashboard"
echo "2. Find your project and go to Settings → Environment Variables"
echo "3. Add the API keys listed above"
echo "4. Test your deployment using the provided URL"
echo ""
echo "📖 For detailed instructions, see: VERCEL_DEPLOYMENT.md"
echo ""
echo "✨ Happy deploying!"