import requests
import json

# Test the chat endpoint
def test_chat_endpoint():
    url = "http://127.0.0.1:5000/chat"
    
    data = {
        "message": "Hello, can you help me?",
        "business_id": 1,
        "history": []
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Chat endpoint is working!")
        else:
            print("❌ Chat endpoint returned an error")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure the Flask server is running on http://127.0.0.1:5000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Testing chat endpoint...")
    test_chat_endpoint() 