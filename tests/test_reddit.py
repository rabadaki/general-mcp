import requests
import json

# Test with improved headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

url = 'https://www.reddit.com/search.json'
params = {
    'q': 'python programming',
    'sort': 'relevance',
    't': 'all',
    'limit': 5
}

response = requests.get(url, params=params, headers=headers)
print(f'Status Code: {response.status_code}')
print(f'Content-Type: {response.headers.get("Content-Type", "Unknown")}')

if response.status_code == 200:
    try:
        data = response.json()
        if 'data' in data and 'children' in data['data']:
            print(f'\nFound {len(data["data"]["children"])} results')
            for i, child in enumerate(data['data']['children'][:3]):
                post = child['data']
                print(f'\nResult {i+1}:')
                print(f'Title: {post.get("title", "N/A")[:80]}...')
                print(f'Subreddit: r/{post.get("subreddit", "N/A")}')
                print(f'Score: {post.get("score", 0)}')
        else:
            print('\nUnexpected data structure:')
            print(json.dumps(data, indent=2)[:500])
    except json.JSONDecodeError:
        print('\nFailed to parse JSON. Response preview:')
        print(response.text[:500])
else:
    print(f'\nError response. Preview:')
    print(response.text[:500]) 