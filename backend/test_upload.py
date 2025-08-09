#!/usr/bin/env python3
"""
Test script for file upload functionality
"""

import os
import sys
import requests
from pathlib import Path

def test_upload():
    """Test the file upload endpoint"""
    
    # Test file path
    test_file_path = "test_document.txt"
    
    # Create a simple test file
    with open(test_file_path, "w") as f:
        f.write("This is a test document for the MindCrunch upload feature.\n")
        f.write("It contains multiple lines of text to test the chunking functionality.\n")
        f.write("The system should be able to process this and create chunks.\n")
    
    print(f"Created test file: {test_file_path}")
    
    # Test the upload endpoint
    url = "http://localhost:8000/api/files/upload/1"  # Assuming course ID 1 exists
    
    try:
        with open(test_file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print("✅ Upload test successful!")
        else:
            print("❌ Upload test failed!")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure it's running on localhost:8000")
    except Exception as e:
        print(f"❌ Error during upload test: {e}")
    
    # Clean up test file
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
        print(f"Cleaned up test file: {test_file_path}")

if __name__ == "__main__":
    test_upload()
