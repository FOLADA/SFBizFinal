#!/usr/bin/env python3

import requests
import json

# Test configuration
BASE_URL = "http://localhost:5000"

def test_search_endpoints():
    """Test the search API endpoints"""
    
    print("🧪 Testing Search API Endpoints")
    print("=" * 50)
    
    # Test 1: Basic search
    print("\n1. Testing basic search...")
    response = requests.get(f"{BASE_URL}/businesses/search?q=restaurant")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Basic search successful - Found {len(data.get('businesses', []))} results")
        print(f"   Total results: {data.get('pagination', {}).get('total', 0)}")
    else:
        print(f"❌ Basic search failed - Status: {response.status_code}")
    
    # Test 2: Category filter
    print("\n2. Testing category filter...")
    response = requests.get(f"{BASE_URL}/businesses/search?category=Restaurants%20%26%20Cafes")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Category filter successful - Found {len(data.get('businesses', []))} results")
    else:
        print(f"❌ Category filter failed - Status: {response.status_code}")
    
    # Test 3: Location filter
    print("\n3. Testing location filter...")
    response = requests.get(f"{BASE_URL}/businesses/search?location=Tbilisi")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Location filter successful - Found {len(data.get('businesses', []))} results")
    else:
        print(f"❌ Location filter failed - Status: {response.status_code}")
    
    # Test 4: Rating filter
    print("\n4. Testing rating filter...")
    response = requests.get(f"{BASE_URL}/businesses/search?minRating=4.0")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Rating filter successful - Found {len(data.get('businesses', []))} results")
    else:
        print(f"❌ Rating filter failed - Status: {response.status_code}")
    
    # Test 5: Combined filters
    print("\n5. Testing combined filters...")
    response = requests.get(f"{BASE_URL}/businesses/search?q=cafe&category=Restaurants%20%26%20Cafes&location=Tbilisi&minRating=3.0&sortBy=rating&sortOrder=desc")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Combined filters successful - Found {len(data.get('businesses', []))} results")
    else:
        print(f"❌ Combined filters failed - Status: {response.status_code}")
    
    # Test 6: Search suggestions
    print("\n6. Testing search suggestions...")
    response = requests.get(f"{BASE_URL}/search-suggestions?q=rest")
    if response.status_code == 200:
        data = response.json()
        suggestions = data.get('suggestions', [])
        print(f"✅ Search suggestions successful - Found {len(suggestions)} suggestions")
        for suggestion in suggestions[:3]:  # Show first 3
            print(f"   - {suggestion.get('text')} ({suggestion.get('type')})")
    else:
        print(f"❌ Search suggestions failed - Status: {response.status_code}")
    
    # Test 7: Filter options
    print("\n7. Testing filter options...")
    response = requests.get(f"{BASE_URL}/businesses/filter-options")
    if response.status_code == 200:
        data = response.json()
        categories = data.get('categories', [])
        locations = data.get('locations', [])
        rating_range = data.get('ratingRange', {})
        print(f"✅ Filter options successful:")
        print(f"   - Categories: {len(categories)} available")
        print(f"   - Locations: {len(locations)} available")
        print(f"   - Rating range: {rating_range.get('min', 0)} - {rating_range.get('max', 5)}")
    else:
        print(f"❌ Filter options failed - Status: {response.status_code}")
    
    # Test 8: Pagination
    print("\n8. Testing pagination...")
    response = requests.get(f"{BASE_URL}/businesses/search?page=1&limit=5")
    if response.status_code == 200:
        data = response.json()
        pagination = data.get('pagination', {})
        print(f"✅ Pagination successful:")
        print(f"   - Page: {pagination.get('page', 1)}")
        print(f"   - Limit: {pagination.get('limit', 12)}")
        print(f"   - Total: {pagination.get('total', 0)}")
        print(f"   - Pages: {pagination.get('pages', 1)}")
    else:
        print(f"❌ Pagination failed - Status: {response.status_code}")
    
    print("\n" + "=" * 50)
    print("🎉 Search API testing completed!")

def test_frontend_endpoints():
    """Test that the frontend can access the search page"""
    
    print("\n🌐 Testing Frontend Search Page")
    print("=" * 50)
    
    # This would require a running frontend server
    # For now, we'll just check if the search page file exists
    import os
    search_page_path = "sfbizfrnt/app/search/page.tsx"
    if os.path.exists(search_page_path):
        print("✅ Search page exists")
    else:
        print("❌ Search page not found")
    
    # Check if AdvancedSearch component exists
    advanced_search_path = "sfbizfrnt/components/AdvancedSearch.tsx"
    if os.path.exists(advanced_search_path):
        print("✅ AdvancedSearch component exists")
    else:
        print("❌ AdvancedSearch component not found")

if __name__ == "__main__":
    try:
        test_search_endpoints()
        test_frontend_endpoints()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the backend server.")
        print("   Make sure the Flask backend is running on http://localhost:5000")
    except Exception as e:
        print(f"❌ An error occurred: {e}") 