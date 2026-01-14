import boto3
import time
import logging

sqs = boto3.client('sqs', region_name='us-east-1')
ec2 = boto3.client('ec2', region_name='us-east-1')

ASU_ID = "1234175958"
AMI_ID = "ami-0e4ef738f957a42bc"
REQ_QUEUE_URL = sqs.get_queue_url(QueueName=f"{ASU_ID}-req-queue")['QueueUrl']
MAX_INSTANCES = 15
MESSAGES_PER_INSTANCE = 5
MINIMUM_INSTANCES = 5
SECURITY_GROUP_IDS = ["sg-0980f5de22ec6f0f1"]
SUBNET_ID = "subnet-0f6d7b7f42c63a0af"

logging.basicConfig(filename='/tmp/controller.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_running_instances():
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['app-tier-instance*']},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
        ]
    )
    instances = [inst['InstanceId'] for res in response['Reservations'] for inst in res['Instances']]
    logging.info(f"Running instances: {len(instances)} ({instances})")
    return instances

def launch_instances(count, instance_count):
    response = ec2.run_instances(
        InstanceType='t2.micro',
        ImageId=AMI_ID,
        MinCount=count,
        MaxCount=count,
        KeyName="KeyPair",
        SecurityGroupIds=SECURITY_GROUP_IDS,
        SubnetId=SUBNET_ID,
        IamInstanceProfile={'Name': 'app-tier-role'},
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'app-tier-instance'}]
        }],
        UserData='''#!/bin/bash
touch /tmp/backend.log
chmod 666 /tmp/backend.log
su - ec2-user -c "/usr/bin/python3 /home/ec2-user/backend.py >> /tmp/backend.log 2>&1 &"
sleep 30
'''
    )
    instance_ids = [inst['InstanceId'] for inst in response['Instances']]
    logging.info(f"Launched {count} instances: {instance_ids}")

    # instance unique name generation
    for i, instance_id in enumerate(instance_ids):
        ec2.create_tags(
            Resources=[instance_id],
            Tags=[{'Key': 'Name', 'Value': f'app-tier-instance-{instance_count + i}'}]
        )
        logging.info(f"Tagged instance {instance_id} as app-tier-instance-{instance_count + i}")
    return instance_ids

def terminate_instances(instance_ids):
    if instance_ids:
        ec2.terminate_instances(InstanceIds=instance_ids)
        logging.info(f"Terminated instances: {instance_ids}")

def manage_instances():
    instance_count = 0
    while True:
        start_time = time.time()
        logging.info("Polling request queue...")
        messages = sqs.receive_message(
            QueueUrl=REQ_QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20  # Long polling :)
        )
        queue_length = len(messages.get('Messages', []))
        logging.info(f"Received {queue_length} messages")

        running_instances = get_running_instances()
        running_count = len(running_instances)

        #calc desired number of instances
        desired_instances = max(
            MINIMUM_INSTANCES,
            min((queue_length + MESSAGES_PER_INSTANCE - 1) // MESSAGES_PER_INSTANCE, MAX_INSTANCES)
        ) if queue_length > 0 else MINIMUM_INSTANCES
        instances_to_launch = max(desired_instances - running_count, 0)
        instances_to_launch = min(instances_to_launch, 5)
        instances_to_terminate = max(running_count - desired_instances, 0)

        # scale out
        if instances_to_launch > 0:
            logging.info(f"Launching {instances_to_launch} new instances (total desired: {desired_instances})")
            new_instance_ids = launch_instances(instances_to_launch, instance_count)
            instance_count += len(new_instance_ids)

        # scale in
        if instances_to_terminate > 0 and running_count > MINIMUM_INSTANCES and queue_length == 0:
            instances_to_terminate_ids = running_instances[:instances_to_terminate]
            logging.info(f"Terminating {instances_to_terminate} instances (keeping {MINIMUM_INSTANCES})")
            terminate_instances(instances_to_terminate_ids)

        elapsed_time = time.time() - start_time
        sleep_time = max(1, 5 - elapsed_time)
        logging.info(f"Sleeping for {sleep_time:.2f} seconds")
        time.sleep(sleep_time)

if __name__ == "__main__":
    logging.info("Starting controller.py...")
    manage_instances()

