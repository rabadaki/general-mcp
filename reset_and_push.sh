#!/bin/bash
# Reset to clean commit and re-add Google tools

echo "🔄 Resetting to clean commit b632c53..."
git reset --hard b632c53

echo "📦 Re-adding all changes (Google tools + clean env vars)..."
git add -A

echo "💾 Committing clean version..."
git commit -m "Add Google Search Console and GA4 API tools (clean version)

- Added 7 new Google API tools: search_console_performance, search_console_top_pages, search_console_top_queries, ga4_traffic_overview, ga4_traffic_sources, ga4_page_performance, ga4_realtime_users
- Updated tool schemas to be less restrictive (increased limits from 50 to 1000+ for most tools)
- Added Google API authentication support via service account  
- Updated requirements.txt with Google API dependencies and WebSocket support
- Added runtime.txt for Railway deployment
- All API keys use environment variables only (no hardcoded secrets)

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"

echo "🚀 Force pushing clean version to GitHub..."
git push origin main --force

echo "✅ Clean deployment complete!"
echo ""
echo "📝 Don't forget to set environment variables in Railway!"