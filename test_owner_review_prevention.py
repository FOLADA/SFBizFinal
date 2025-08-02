#!/usr/bin/env python3
"""
Test script to verify that business owners cannot review their own businesses.
This tests both the backend validation and frontend logic.
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_owner_review_prevention():
    """Test that business owners cannot review their own businesses"""
    print("🧪 Testing Business Owner Review Prevention")
    print("=" * 50)
    
    # Step 1: Register a test user
    print("\n1. Registering test user...")
    user_data = {
        "email": "testowner@example.com",
        "password": "testpassword123"
    }
    
    register_response = requests.post(f"{BASE_URL}/auth/register", json=user_data)
    if register_response.status_code != 200:
        print(f"❌ Failed to register user: {register_response.status_code}")
        return
    
    user_info = register_response.json()
    token = user_info["token"]
    user_id = user_info["user"]["id"]
    print(f"✅ User registered: {user_info['user']['email']} (ID: {user_id})")
    
    # Step 2: Create a business for this user
    print("\n2. Creating business for the user...")
    business_data = {
        "name": "Test Business",
        "category": "Test Category",
        "description": "A test business for owner review prevention testing",
        "services": "Test Service 1\nTest Service 2",
        "image_url": "https://example.com/test.jpg",
        "location": "Test Location"
    }
    
    business_response = requests.post(
        f"{BASE_URL}/businesses",
        json=business_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if business_response.status_code != 201:
        print(f"❌ Failed to create business: {business_response.status_code}")
        print(f"Error: {business_response.text}")
        return
    
    business_info = business_response.json()
    business_id = business_info["id"]
    print(f"✅ Business created: {business_data['name']} (ID: {business_id})")
    
    # Step 3: Test owner check endpoint
    print("\n3. Testing owner check endpoint...")
    owner_check_response = requests.get(
        f"{BASE_URL}/businesses/{business_id}/owner-check",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if owner_check_response.status_code == 200:
        owner_status = owner_check_response.json()
        print(f"✅ Owner check successful: isOwner = {owner_status['isOwner']}")
        if not owner_status['isOwner']:
            print("⚠️  Warning: User is not detected as business owner")
    else:
        print(f"❌ Owner check failed: {owner_check_response.status_code}")
    
    # Step 4: Try to submit a review as the business owner
    print("\n4. Attempting to submit review as business owner...")
    review_data = {
        "businessId": business_id,
        "rating": 5,
        "text": "This is a test review from the business owner. This should be rejected.",
        "name": "Business Owner"
    }
    
    review_response = requests.post(
        f"{BASE_URL}/reviews",
        json=review_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if review_response.status_code == 403:
        error_data = review_response.json()
        print(f"✅ Owner review correctly rejected: {error_data['error']}")
    else:
        print(f"❌ Owner review was not rejected: {review_response.status_code}")
        print(f"Response: {review_response.text}")
    
    # Step 5: Register another user and try to review the business
    print("\n5. Testing review from non-owner user...")
    other_user_data = {
        "email": "testreviewer@example.com",
        "password": "testpassword123"
    }
    
    other_register_response = requests.post(f"{BASE_URL}/auth/register", json=other_user_data)
    if other_register_response.status_code != 200:
        print(f"❌ Failed to register other user: {other_register_response.status_code}")
        return
    
    other_user_info = other_register_response.json()
    other_token = other_user_info["token"]
    print(f"✅ Other user registered: {other_user_info['user']['email']}")
    
    # Check if other user is owner
    other_owner_check = requests.get(
        f"{BASE_URL}/businesses/{business_id}/owner-check",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    
    if other_owner_check.status_code == 200:
        other_owner_status = other_owner_check.json()
        print(f"✅ Other user owner check: isOwner = {other_owner_status['isOwner']}")
    
    # Submit review as non-owner
    other_review_data = {
        "businessId": business_id,
        "rating": 4,
        "text": "This is a legitimate review from a customer. This should be accepted.",
        "name": "Happy Customer"
    }
    
    other_review_response = requests.post(
        f"{BASE_URL}/reviews",
        json=other_review_data,
        headers={"Authorization": f"Bearer {other_token}"}
    )
    
    if other_review_response.status_code == 201:
        print("✅ Non-owner review successfully submitted")
    else:
        print(f"❌ Non-owner review failed: {other_review_response.status_code}")
        print(f"Error: {other_review_response.text}")
    
    # Step 6: Verify reviews
    print("\n6. Verifying reviews...")
    reviews_response = requests.get(f"{BASE_URL}/reviews/{business_id}")
    if reviews_response.status_code == 200:
        reviews_data = reviews_response.json()
        print(f"✅ Found {len(reviews_data['reviews'])} reviews for the business")
        for review in reviews_data['reviews']:
            print(f"  - {review['name']}: {review['rating']}/5 - {review['text'][:50]}...")
    else:
        print(f"❌ Failed to fetch reviews: {reviews_response.status_code}")
    
    print("\n" + "=" * 50)
    print("🎉 Owner review prevention test completed!")

if __name__ == "__main__":
    test_owner_review_prevention() 