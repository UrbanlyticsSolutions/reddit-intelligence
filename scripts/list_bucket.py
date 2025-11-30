from google.cloud import storage
client = storage.Client()
bucket = client.bucket('stock-479103-deepseek-results')
blobs = list(bucket.list_blobs())
print('count', len(blobs))
for blob in blobs:
    print(blob.name, blob.updated)
