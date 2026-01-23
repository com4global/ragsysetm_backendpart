#!/usr/bin/env python
"""
Simple test to verify backend is running and accepting requests
Run this after you start the backend with F5
"""

import requests
import sys
from time import sleep

def test_backend():
    backend_url = "http://localhost:8000"
    
    print("\n" + "="*70)
    print("🧪 TESTING BACKEND CONNECTION")
    print("="*70)
    
    # Test 1: Check if backend is running
    print("\n1️⃣  Checking if backend is running...")
    try:
        response = requests.get(f"{backend_url}/", timeout=2)
        print(f"   ✅ Backend is running!")
        print(f"   Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot connect to {backend_url}")
        print(f"   Make sure to start debugging with F5 first!")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Check Swagger UI
    print("\n2️⃣  Checking Swagger UI...")
    try:
        response = requests.get(f"{backend_url}/docs", timeout=2)
        if response.status_code == 200:
            print(f"   ✅ Swagger UI is available at {backend_url}/docs")
    except Exception as e:
        print(f"   ⚠️  Swagger UI error: {e}")
    
    # Test 3: Test the /chat endpoint
    print("\n3️⃣  Testing /chat endpoint...")
    try:
        payload = {
            "query": "What is the revenue in 2021?"
        }
        print(f"   Sending: {payload}")
        
        response = requests.post(
            f"{backend_url}/chat",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"   ✅ /chat endpoint works!")
            print(f"   Response: {response.json()}")
        else:
            print(f"   ❌ Status code: {response.status_code}")
            print(f"   Response: {response.text}")
    except requests.exceptions.Timeout:
        print(f"   ⏳ Request timed out - backend might be paused at breakpoint")
        print(f"   → Press F5 in VS Code to continue")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    return True

if __name__ == "__main__":
    success = test_backend()
    sys.exit(0 if success else 1)
