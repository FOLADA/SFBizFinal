#!/usr/bin/env python3
"""
Test script for AI Service Recommendations
"""

import requests
import json
import os

# Configuration
BASE_URL = "http://localhost:5000"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_ai_recommendations():
    """Test the AI service recommendations endpoint"""
    
    print("🤖 Testing AI Service Recommendations...")
    print("=" * 50)
    
    # Step 1: Register a test user
    print("1. Registering test user...")
    register_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        register_response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        if register_response.status_code == 201:
            print("✅ User registered successfully")
            user_data = register_response.json()
            token = user_data["token"]
        elif register_response.status_code == 409:
            print("ℹ️ User already exists, proceeding to login...")
            # Try to login instead
            login_response = requests.post(f"{BASE_URL}/auth/login", json=register_data)
            if login_response.status_code == 200:
                user_data = login_response.json()
                token = user_data["token"]
                print("✅ User logged in successfully")
            else:
                print(f"❌ Login failed: {login_response.status_code}")
                return
        else:
            print(f"❌ Registration failed: {register_response.status_code}")
            return
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return
    
    # Step 2: Create a test business
    print("\n2. Creating test business...")
    business_data = {
        "name": "Test Beauty Salon",
        "category": "Beauty & Spa",
        "description": "A modern beauty salon offering hair styling, makeup, and spa services",
        "services": "Haircuts and styling\nManicures and pedicures\nFacial treatments",
        "location": "123 Main Street, Tbilisi, Georgia",
        "image_url": "",
        "socials": {
            "phone": "+995 123 456 789",
            "email": "info@testbeauty.com"
        }
    }
    
    try:
        business_response = requests.post(
            f"{BASE_URL}/businesses",
            json=business_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if business_response.status_code == 201:
            business_id = business_response.json()["id"]
            print(f"✅ Business created successfully with ID: {business_id}")
        else:
            print(f"❌ Business creation failed: {business_response.status_code}")
            print(f"Response: {business_response.text}")
            return
    except Exception as e:
        print(f"❌ Business creation error: {e}")
        return
    
    # Step 3: Test AI recommendations
    print("\n3. Testing AI recommendations...")
    try:
        recommendations_response = requests.get(
            f"{BASE_URL}/businesses/{business_id}/ai-recommendations",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if recommendations_response.status_code == 200:
            recommendations_data = recommendations_response.json()
            print("✅ AI recommendations retrieved successfully!")
            print(f"📊 Found {len(recommendations_data['recommendations'])} recommendations")
            
            print("\n🎯 AI Recommendations:")
            print("-" * 30)
            for i, rec in enumerate(recommendations_data['recommendations'], 1):
                print(f"\n{i}. {rec['service_name']}")
                print(f"   Category: {rec['category']}")
                print(f"   Price: {rec['estimated_price_range']}")
                print(f"   Description: {rec['description']}")
                print(f"   Reasoning: {rec['reasoning']}")
            
            print(f"\n📋 Business Info:")
            print(f"   Name: {recommendations_data['business_info']['name']}")
            print(f"   Category: {recommendations_data['business_info']['category']}")
            print(f"   Current Services: {recommendations_data['business_info']['services']}")
            
        else:
            print(f"❌ AI recommendations failed: {recommendations_response.status_code}")
            print(f"Response: {recommendations_response.text}")
            
    except Exception as e:
        print(f"❌ AI recommendations error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 AI Recommendations Test Complete!")

if __name__ == "__main__":
    test_ai_recommendations() 