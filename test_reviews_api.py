#!/usr/bin/env python3
"""
Simple test script for the Reviews API endpoints
Run this after starting the Flask backend
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_create_review():
    """Test creating a new review"""
    print("Testing review creation...")
    
    review_data = {
        "businessId": 1,
        "name": "Test User",
        "rating": 5,
        "text": "This is a test review with more than 10 characters to meet the minimum requirement."
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/reviews",
            json=review_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            print("✅ Review created successfully!")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Failed to create review: {response.status_code}")
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the Flask backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_get_reviews():
    """Test getting reviews for a business"""
    print("\nTesting getting reviews...")
    
    try:
        response = requests.get(f"{BASE_URL}/reviews/1")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Reviews retrieved successfully!")
            print(f"Total reviews: {data['pagination']['total']}")
            print(f"Reviews: {len(data['reviews'])}")
        else:
            print(f"❌ Failed to get reviews: {response.status_code}")
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the Flask backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_get_average_rating():
    """Test getting average rating for a business"""
    print("\nTesting getting average rating...")
    
    try:
        response = requests.get(f"{BASE_URL}/reviews/average/1")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Average rating retrieved successfully!")
            print(f"Average rating: {data['averageRating']}")
            print(f"Total reviews: {data['totalReviews']}")
        else:
            print(f"❌ Failed to get average rating: {response.status_code}")
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the Flask backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_validation():
    """Test validation errors"""
    print("\nTesting validation...")
    
    # Test invalid rating
    invalid_data = {
        "businessId": 1,
        "rating": 6,  # Invalid rating
        "text": "Test review"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/reviews",
            json=invalid_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 400:
            print("✅ Validation working correctly!")
            print(f"Error: {response.json()}")
        else:
            print(f"❌ Expected validation error, got: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 Testing Reviews API Endpoints")
    print("=" * 40)
    
    test_create_review()
    test_get_reviews()
    test_get_average_rating()
    test_validation()
    
    print("\n" + "=" * 40)
    print("✅ Testing complete!") 