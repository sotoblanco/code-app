import requests
import os
import time

# Production Modal URL
BASE_URL = "https://sotoblanco263542--code-app-fastapi-app.modal.run"

def test_remote_fix():
    print(f"Testing against Production: {BASE_URL}")
    
    session = requests.Session()
    timestamp = int(time.time())
    username = f"verifier_{timestamp}"
    password = "password123"
    
    # 1. Register
    print(f"1. Registering {username}...")
    res = session.post(f"{BASE_URL}/auth/signup", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": password,
        "role": "admin"
    })
    
    # 2. Login
    print("2. Logging in...")
    res = session.post(f"{BASE_URL}/auth/login", data={
        "username": username,
        "password": password
    })
    
    if res.status_code != 200:
        print(f"Login failed: {res.text}")
        return False

    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Create Course (This was failing before migration)
    print("3. Creating Course...")
    res = session.post(f"{BASE_URL}/courses/", json={
        "title": f"Fixed Course {timestamp}",
        "description": "Verifying DB fix",
        "slug": f"fixed-course-{timestamp}",
        "is_published": True
    }, headers=headers)
    
    if res.status_code != 200:
        print(f"FAILED: Could not create course. DB might still be broken. Status: {res.status_code}, Resp: {res.text}")
        return False
        
    course_id = res.json()["id"]
    print(f"SUCCESS: Course created (ID: {course_id})")
    
    # 4. Create Rust Exercise
    print("4. Creating Rust Exercise...")
    res = session.post(f"{BASE_URL}/courses/{course_id}/exercises/", json={
        "title": "Rust Verification",
        "slug": f"rust-verify-{timestamp}",
        "description": "Checking language field",
        "language": "rust",
        "initial_code": "fn main() {}",
        "test_code": "fn main() {}",
        "order": 0,
        "course_id": course_id
    }, headers=headers)
    
    if res.status_code != 200:
        print(f"FAILED: Could not create exercise. {res.text}")
        return False
        
    data = res.json()
    if data.get("language") == "rust":
        print("SUCCESS: Exercise created with language='rust'")
        return True
    else:
        print(f"FAILED: Language field mismatch. Got {data.get('language')}")
        return False

if __name__ == "__main__":
    try:
        if test_remote_fix():
            print("\n✅ VERIFICATION PASSED: Database is fixed and Rust support is active.")
        else:
            print("\n❌ VERIFICATION FAILED.")
            exit(1)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
