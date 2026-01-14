from flask import Flask, request
import boto3
from waitress import serve
import os

app = Flask(__name__)

s3 = boto3.client('s3', region_name='us-east-1')
sqs = boto3.client('sqs', region_name='us-east-1')

ASU_ID = "1234175958"
INPUT_BUCKET = f"{ASU_ID}-in-bucket"
REQ_QUEUE_URL = sqs.get_queue_url(QueueName=f"{ASU_ID}-req-queue")['QueueUrl']
RESP_QUEUE_URL = sqs.get_queue_url(QueueName=f"{ASU_ID}-resp-queue")['QueueUrl']

@app.route('/', methods=['POST'])
def project1p2():
    print("Received POST request")
    print(f"Request form: {request.form}")
    print(f"Request files: {request.files}")
    if 'inputFile' not in request.files:
        print("Error: No inputFile in request")
        return "ERROR: No inputFile provided", 400
    file = request.files['inputFile']
    filename = file.filename
    if not filename:
        print("Error: No filename provided")
        return "ERROR: No filename provided", 400
    print(f"Processing file: {filename}")

    local_path = f"/tmp/{filename}"
    print(f"Saving file to {local_path}")
    file.save(local_path)
    print(f"File saved: {os.path.exists(local_path)}")

    print(f"Uploading {local_path} to s3://{INPUT_BUCKET}/{filename}")
    s3.upload_file(local_path, INPUT_BUCKET, filename)
    print("Upload to S3 successful")

    print(f"Sending message to request queue: {filename}")
    sqs.send_message(QueueUrl=REQ_QUEUE_URL, MessageBody=filename)
    print("Message sent to request queue")

    print(f"Request for {filename} queued successfully")
    return f"{filename.split('.')[0]}:Processing", 200

if __name__ == "__main__":
    print("Starting server on port 8000...")
    serve(app, host='0.0.0.0', port=8000, threads=32)
