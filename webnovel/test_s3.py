import warnings
warnings.simplefilter("always")
import sys
import os
import importlib

print("\n==== ENVIRONMENT & PATHS ====")
print("Python executable:", sys.executable)
print("sys.path:", sys.path)
print("DJANGO_SETTINGS_MODULE:", os.environ.get("DJANGO_SETTINGS_MODULE"))

print("\n==== CHECK S3Boto3Storage IMPORT ====")
try:
    importlib.import_module("storages.backends.s3boto3")
    print("S3Boto3Storage import: OK")
except Exception as e:
    print("S3Boto3Storage import ERROR:", e, file=sys.stderr)

print("\n==== DJANGO SETUP ====")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webnovel.settings")
import django
django.setup()

# Clear Django's storage cache to force reinitialization
from django.core.files.storage import default_storage
from django.utils.functional import empty
if hasattr(default_storage, '_wrapped'):
    default_storage._wrapped = empty

from django.conf import settings

print("\n==== SETTINGS CHECK ====")
print("Settings module:", getattr(settings, "SETTINGS_MODULE", None))
print("DEFAULT_FILE_STORAGE from settings:", getattr(settings, "DEFAULT_FILE_STORAGE", None))

# Print all locations where DEFAULT_FILE_STORAGE is set in settings.py
print("\n==== SEARCHING settings.py FOR DEFAULT_FILE_STORAGE ====")
settings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "settings.py"))
if not os.path.exists(settings_path):
    # Try parent directory
    settings_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.py"))
try:
    with open(settings_path) as f:
        for i, line in enumerate(f, 1):
            if "DEFAULT_FILE_STORAGE" in line:
                print(f"Line {i}: {line.strip()}")
except Exception as e:
    print("Could not read settings.py:", e)

print("\n==== ENVIRONMENT VARIABLES ====")
print("AWS_ACCESS_KEY_ID:", os.environ.get("AWS_ACCESS_KEY_ID"))
print("AWS_STORAGE_BUCKET_NAME:", os.environ.get("AWS_STORAGE_BUCKET_NAME"))

print("\n==== DEFAULT STORAGE BACKEND (BEFORE SAVE) ====")
from django.core.files.storage import default_storage
print("default_storage type:", type(default_storage))
backend = getattr(default_storage, '_wrapped', None)
if backend is None:
    print("_wrapped is None (not initialized)")
else:
    print("_wrapped type:", type(backend))

print("\n==== SAVE TEST FILE USING default_storage ====")
from django.core.files.base import ContentFile
test_path = "test_s3_output/test_file.txt"
test_content = "Hello from S3 test!"
try:
    saved_path = default_storage.save(test_path, ContentFile(test_content.encode("utf-8")))
    print("File saved at:", saved_path)
    print("File URL:", default_storage.url(saved_path))
except Exception as e:
    print("Error saving file to storage:", e)

print("\n==== DEFAULT STORAGE BACKEND (AFTER SAVE) ====")
backend = getattr(default_storage, '_wrapped', None)
if backend is None:
    # Force initialization
    _ = default_storage.exists('dummy')
    backend = default_storage._wrapped
print("Actual backend after save:", type(backend))

print("\n==== DIRECT S3Boto3Storage USAGE ====")
try:
    from storages.backends.s3boto3 import S3Boto3Storage
    s3_storage = S3Boto3Storage()
    print("Direct S3Boto3Storage instance:", type(s3_storage))
    # Try saving a file directly
    try:
        s3_saved_path = s3_storage.save("test_s3_output/direct_test_file.txt", ContentFile(b"Direct S3 test!"))
        print("Direct S3Boto3Storage file saved at:", s3_saved_path)
        print("Direct S3Boto3Storage file URL:", s3_storage.url(s3_saved_path))
    except Exception as e:
        print("Direct S3Boto3Storage save error:", e)
except Exception as e:
    print("Direct S3Boto3Storage import/instantiation error:", e)

print("\n==== DETAILED STORAGE DEBUGGING ====")
# Check all AWS settings
print("AWS_ACCESS_KEY_ID:", bool(settings.AWS_ACCESS_KEY_ID))
print("AWS_SECRET_ACCESS_KEY:", bool(settings.AWS_SECRET_ACCESS_KEY))
print("AWS_STORAGE_BUCKET_NAME:", settings.AWS_STORAGE_BUCKET_NAME)
print("AWS_S3_REGION_NAME:", settings.AWS_S3_REGION_NAME)
print("AWS_S3_CUSTOM_DOMAIN:", settings.AWS_S3_CUSTOM_DOMAIN)

# Try to instantiate the storage backend using the exact setting value
try:
    storage_class_path = settings.DEFAULT_FILE_STORAGE
    print(f"Storage class path: {storage_class_path}")
    
    # Import the storage class
    module_path, class_name = storage_class_path.rsplit('.', 1)
    storage_module = importlib.import_module(module_path)
    storage_class = getattr(storage_module, class_name)
    print(f"Storage class: {storage_class}")
    
    # Try to instantiate it
    test_storage = storage_class()
    print(f"Test storage instance: {type(test_storage)}")
    
    # Check if it has the expected attributes
    print(f"Has location: {hasattr(test_storage, 'location')}")
    print(f"Has bucket_name: {hasattr(test_storage, 'bucket_name')}")
    print(f"Bucket name: {getattr(test_storage, 'bucket_name', 'N/A')}")
    
except Exception as e:
    print(f"Error instantiating storage class: {e}")

# Check if there are any other storage-related settings that might interfere
print("\n==== CHECKING FOR OTHER STORAGE SETTINGS ====")
storage_settings = [
    'STATICFILES_STORAGE',
    'FILE_UPLOAD_HANDLERS',
    'FILE_UPLOAD_TEMP_DIR',
    'FILE_UPLOAD_PERMISSIONS',
    'FILE_UPLOAD_MAX_MEMORY_SIZE',
]

for setting_name in storage_settings:
    value = getattr(settings, setting_name, None)
    if value is not None:
        print(f"{setting_name}: {value}")

print("\n==== END OF DEBUG OUTPUT ====")