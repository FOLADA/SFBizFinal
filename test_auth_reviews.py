#!/usr/bin/env python3
"""
Test script to verify authentication is required for review submission
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_unauthorized_review_submission():
    """Test that review submission fails without authentication"""
    print("Testing unauthorized review submission...")
    
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
        
        if response.status_code == 401:
            print("✅ Authentication required - unauthorized submission correctly rejected!")
        else:
            print(f"❌ Expected 401, got {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the Flask backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_authorized_review_submission():
    """Test that review submission works with authentication"""
    print("\nTesting authorized review submission...")
    
    # First, login to get a token
    login_data = {
        "email": "test@example.com",
        "password": "password123"
    }
    
    try:
        # Try to login (this might fail if user doesn't exist, which is expected)
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data["token"]
            
            # Now try to submit a review with the token
            review_data = {
                "businessId": 1,
                "name": "Test User",
                "rating": 5,
                "text": "This is a test review with authentication."
            }
            
            review_response = requests.post(
                f"{BASE_URL}/reviews",
                json=review_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
            )
            
            if review_response.status_code == 201:
                print("✅ Authorized review submission successful!")
            else:
                print(f"❌ Authorized submission failed: {review_response.status_code}")
                print(f"Error: {review_response.text}")
        else:
            print("ℹ️  Login failed (user might not exist) - this is expected for testing")
            print("To test authorized submission, first register a user at /auth/register")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the Flask backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_public_endpoints():
    """Test that public endpoints still work without authentication"""
    print("\nTesting public endpoints...")
    
    try:
        # Test getting reviews (should work without auth)
        response = requests.get(f"{BASE_URL}/reviews/1")
        
        if response.status_code == 200:
            print("✅ Public endpoint (GET reviews) works without authentication")
        else:
            print(f"❌ Public endpoint failed: {response.status_code}")
            
        # Test getting average rating (should work without auth)
        response = requests.get(f"{BASE_URL}/reviews/average/1")
        
        if response.status_code == 200:
            print("✅ Public endpoint (GET average rating) works without authentication")
        else:
            print(f"❌ Public endpoint failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the Flask backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🔐 Testing Authentication for Reviews API")
    print("=" * 50)
    
    test_unauthorized_review_submission()
    test_authorized_review_submission()
    test_public_endpoints()
    
    print("\n" + "=" * 50)
    print("✅ Authentication testing complete!")
    print("\nTo test full functionality:")
    print("1. Register a user: POST /auth/register")
    print("2. Login: POST /auth/login")
    print("3. Submit review with token: POST /reviews (with Authorization header)") 