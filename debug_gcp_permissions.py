import os
from google.cloud import storage

def test_gcp_permissions():
    print("="*50)
    print("GCP PERMISSION DIAGNOSTIC TOOL")
    print("="*50)

    # 1. Check Environment Variables
    bucket_name = os.environ.get('GCS_BUCKET_NAME', 'stock-479103-deepseek-results')
    print(f"Target Bucket: {bucket_name}")
    
    # Check for credentials
    creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if creds:
        print(f"Credentials File: {creds}")
    else:
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS not set. Using default/implicit credentials.")

    try:
        # 2. Initialize Client
        print("\n[1/3] Initializing Storage Client...")
        client = storage.Client()
        print("SUCCESS: Client initialized.")
        
        # 3. Check Bucket Access
        print(f"\n[2/3] Checking access to bucket '{bucket_name}'...")
        try:
            bucket = client.get_bucket(bucket_name)
            print(f"SUCCESS: Bucket '{bucket_name}' found and accessible.")
        except Exception as e:
            if "404" in str(e):
                print(f"ERROR: Bucket '{bucket_name}' does not exist.")
            elif "403" in str(e):
                print(f"ERROR: Permission Denied. You do not have access to list/get bucket '{bucket_name}'.")
            else:
                print(f"ERROR: Failed to access bucket: {e}")
            return

        # 4. Test Upload
        print(f"\n[3/3] Testing write permission...")
        blob_name = "permission_test_file.txt"
        blob = bucket.blob(blob_name)
        try:
            blob.upload_from_string("This is a test file to verify write permissions.")
            print(f"SUCCESS: Successfully uploaded '{blob_name}'.")
            
            # Clean up
            blob.delete()
            print("SUCCESS: Successfully deleted test file.")
            print("\nVERDICT: Permissions are CORRECT.")
            
        except Exception as e:
            if "403" in str(e):
                print("ERROR: Permission Denied. You can see the bucket but CANNOT WRITE to it.")
                print("Fix: Grant 'Storage Object Admin' or 'Storage Object Creator' role.")
            else:
                print(f"ERROR: Upload failed: {e}")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        if "DefaultCredentialsError" in str(e) or "Could not automatically determine credentials" in str(e):
             print("Please set GOOGLE_APPLICATION_CREDENTIALS or run 'gcloud auth application-default login'")

if __name__ == "__main__":
    test_gcp_permissions()
