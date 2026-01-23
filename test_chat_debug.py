#!/usr/bin/env python
"""
Test the /chat endpoint to see debugging output
"""

import requests
import json

def test_chat_endpoint():
    """Test the chat endpoint with debug output"""
    
    print("\n" + "="*70)
    print("🧪 TESTING /chat ENDPOINT")
    print("="*70)
    
    # Make sure backend is running
    try:
        # First, test if backend is alive
        response = requests.get("http://localhost:8000/", timeout=2)
        print("✅ Backend is running")
    except:
        print("❌ Backend is NOT running!")
        print("   Start it with: F5 in VS Code")
        return
    
    # Now test the chat endpoint
    query = "What was the revenue in 2021?"
    payload = {"query": query}
    
    print(f"\n📤 SENDING REQUEST:")
    print(f"   URL: http://localhost:8000/chat")
    print(f"   Method: POST")
    print(f"   Payload: {json.dumps(payload, indent=2)}")
    print("\n" + "-"*70)
    print("⏳ WAITING FOR RESPONSE...")
    print("-"*70)
    
    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json=payload,
            timeout=10
        )
        
        print(f"\n✅ RESPONSE RECEIVED")
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        
        result = response.json()
        
        print(f"\n📥 RESPONSE DATA:")
        print(f"   Query: {result.get('query')}")
        print(f"   Response: {result.get('response')}")
        
        if "error" in result:
            print(f"\n❌ ERROR IN RESPONSE:")
            print(f"   {result.get('error')}")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETE")
        print("="*70 + "\n")
        
    except requests.exceptions.Timeout:
        print(f"\n⏱️  REQUEST TIMED OUT (10 seconds)")
        print("   → Backend might be paused at breakpoint")
        print("   → Press F5 in VS Code to continue")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print(f"   Type: {type(e).__name__}")

if __name__ == "__main__":
    test_chat_endpoint()
