#!/usr/bin/env python3
import pymongo
from datetime import datetime, timezone, timedelta
import uuid

def create_test_user():
    # Connect to MongoDB
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client["test_database"]
    
    # Generate test data
    timestamp = int(datetime.now().timestamp())
    user_id = f"test-user-{timestamp}"
    session_token = f"test_session_{timestamp}"
    email = f"test.user.{timestamp}@example.com"
    
    # Create user
    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": "Test User",
        "picture": "https://via.placeholder.com/150",
        "subscription_status": "active",
        "subscription_expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Create session
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # Insert documents
        db.users.insert_one(user_doc)
        db.user_sessions.insert_one(session_doc)
        
        print(f"User created: {user_id}")
        print(f"Session token: {session_token}")
        
        # Verify insertion
        user_check = db.users.find_one({"user_id": user_id}, {"_id": 0})
        session_check = db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        
        print(f"User verification: {'✅' if user_check else '❌'}")
        print(f"Session verification: {'✅' if session_check else '❌'}")
        
        return session_token, user_id
        
    except Exception as e:
        print(f"Error: {e}")
        return None, None
    finally:
        client.close()

if __name__ == "__main__":
    create_test_user()