import boto3
import os
import subprocess
import time
import sys

sqs = boto3.client('sqs', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
ec2 = boto3.client('ec2', region_name='us-east-1')

ASU_ID = "1234175958"
INPUT_BUCKET = f"{ASU_ID}-in-bucket"
OUTPUT_BUCKET = f"{ASU_ID}-out-bucket"
REQ_QUEUE_URL = sqs.get_queue_url(QueueName=f"{ASU_ID}-req-queue")['QueueUrl']
RESP_QUEUE_URL = sqs.get_queue_url(QueueName=f"{ASU_ID}-resp-queue")['QueueUrl']
MINIMUM_RUNTIME = 300  # Run for at least 60 seconds before terminating

def get_instance_id():
    # Get the instance ID of the current instance using IMDS
    import requests
    response = requests.get('http://169.254.169.254/latest/meta-data/instance-id')
    instance_id = response.text
    return instance_id

def predict(image_path):
    # Verify the image file exists and is readable
    if not os.path.exists(image_path):
        return "Unknown"

    # Verify face_recognition.py exists and is executable
    face_recognition_script = "/home/ec2-user/model/face_recognition.py"
    if not os.path.exists(face_recognition_script):
        return "Unknown"

    # Log the current working directory and environment
    command = ['python3', face_recognition_script, image_path]
    print(f"Running command: {' '.join(command)}")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        prediction = result.stdout.strip()
        if not prediction:
            return "Unknown"
        return prediction
    else:
        return "Unknown"

def process_message():
    processed = False
    instance_id = get_instance_id()

    start_time = time.time()
    while time.time() - start_time < MINIMUM_RUNTIME:
        response = sqs.receive_message(
            QueueUrl=REQ_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20  # Long polling :)
        )

        if 'Messages' not in response:
            continue

        message = response['Messages'][0]
        receipt_handle = message['ReceiptHandle']
        filename = message['Body']

        local_path = f"/tmp/{filename}"
        s3.download_file(INPUT_BUCKET, filename, local_path)

        prediction = predict(local_path)

        output_key = filename.split('.')[0]
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=f"{output_key}:{prediction}"
        )

        result_message = f"{output_key}:{prediction}"
        sqs.send_message(
            QueueUrl=RESP_QUEUE_URL,
            MessageBody=result_message
        )

        sqs.delete_message(QueueUrl=REQ_QUEUE_URL, ReceiptHandle=receipt_handle)

        if os.path.exists(local_path):
            os.remove(local_path)

        processed = True

    if instance_id:
        ec2.terminate_instances(InstanceIds=[instance_id])
        print(f"Terminated instance: {instance_id}")

if __name__ == "__main__":
    process_message()
