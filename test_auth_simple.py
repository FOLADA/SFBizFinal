#!/usr/bin/env python3

import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_auth():
    print("🧪 Testing Authentication Endpoints")
    print("=" * 50)
    
    # Test registration
    print("1. Testing user registration...")
    register_data = {
        "email": "test@example.com",
        "password": "password123"
    }
    
    try:
        r = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        print(f"   Status: {r.status_code}")
        if r.status_code == 201:
            response = r.json()
            print("   ✅ Registration successful!")
            print(f"   User ID: {response.get('user', {}).get('id')}")
            token = response.get('token')
            
            # Test login
            print("\n2. Testing user login...")
            login_data = {
                "email": "test@example.com",
                "password": "password123"
            }
            
            r2 = requests.post(f"{BASE_URL}/auth/login", json=login_data)
            print(f"   Status: {r2.status_code}")
            if r2.status_code == 200:
                print("   ✅ Login successful!")
                login_response = r2.json()
                token = login_response.get('token')
                
                # Test token verification
                print("\n3. Testing token verification...")
                headers = {"Authorization": f"Bearer {token}"}
                r3 = requests.get(f"{BASE_URL}/auth/verify", headers=headers)
                print(f"   Status: {r3.status_code}")
                if r3.status_code == 200:
                    print("   ✅ Token verification successful!")
                else:
                    print(f"   ❌ Token verification failed: {r3.text}")
                    
            else:
                print(f"   ❌ Login failed: {r2.text}")
                
        elif r.status_code == 409:
            print("   ℹ️  User already exists, testing login...")
            login_data = {
                "email": "test@example.com",
                "password": "password123"
            }
            
            r2 = requests.post(f"{BASE_URL}/auth/login", json=login_data)
            print(f"   Login Status: {r2.status_code}")
            if r2.status_code == 200:
                print("   ✅ Login successful!")
                response = r2.json()
                token = response.get('token')
                
                # Test token verification
                print("\n3. Testing token verification...")
                headers = {"Authorization": f"Bearer {token}"}
                r3 = requests.get(f"{BASE_URL}/auth/verify", headers=headers)
                print(f"   Status: {r3.status_code}")
                if r3.status_code == 200:
                    print("   ✅ Token verification successful!")
                else:
                    print(f"   ❌ Token verification failed: {r3.text}")
            else:
                print(f"   ❌ Login failed: {r2.text}")
                
        else:
            print(f"   ❌ Registration failed: {r.text}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Authentication testing complete!")

if __name__ == "__main__":
    test_auth()