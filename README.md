# Elastic Face Recognition Service on AWS

An auto-scaling, distributed face recognition system built on AWS EC2 with custom scaling logic. The system dynamically provisions and terminates EC2 instances based on workload demand, processing face recognition requests through a decoupled multi-tier architecture.

## Architecture Overview

```
                                    +------------------+
                                    |   App Tier EC2   |
                                    |   (Instance 1)   |
+--------+      +-----------+       +------------------+
| Client | ---> |  Web Tier | --->  |   App Tier EC2   |  ---> S3 Output
+--------+      |   (EC2)   |       |   (Instance 2)   |       Bucket
                +-----------+       +------------------+
                      |             |       ...        |
                      v             +------------------+
                 S3 Input           |   App Tier EC2   |
                  Bucket            |   (Instance N)   |
                                    +------------------+
                                           ^
                                           |
                                    +------+------+
                                    |  Controller |
                                    | (Auto-Scale)|
                                    +-------------+
```

## Components

### Web Tier

A Flask-based REST API server that serves as the entry point for all client requests.

**Responsibilities:**
- Accept image uploads via HTTP POST
- Store images in S3 input bucket
- Enqueue processing requests to SQS request queue
- Return immediate acknowledgment to clients

### Controller (Auto-Scaler)

A custom scaling controller that monitors queue depth and manages the EC2 instance pool.

**Scaling Logic:**
- Monitors SQS request queue length via long polling
- Maintains a minimum of 5 instances
- Scales up to a maximum of 15 instances
- Launches instances in batches (up to 5 at a time)
- Scales in when queue is empty (respecting minimum threshold)
- Calculates desired instances: 1 instance per 5 pending messages

**Features:**
- Tag-based instance tracking (`app-tier-instance-*`)
- Unique instance naming for identification
- Configurable scaling parameters

### App Tier (Worker Instances)

EC2 instances running a backend worker that processes face recognition requests.

**Processing Pipeline:**
1. Poll SQS request queue for new messages
2. Download image from S3 input bucket
3. Execute face recognition model
4. Store results in S3 output bucket
5. Send completion notification to SQS response queue
6. Self-terminate after idle timeout (5 minutes)

## AWS Services Used

| Service | Purpose |
|---------|---------|
| EC2 | Hosts web tier and scalable app tier instances |
| S3 | Input bucket for images, output bucket for results |
| SQS | Request queue and response queue for decoupling |
| IAM | Instance profiles for secure AWS API access |

## Technical Details

**Web Server:** Flask with Waitress (32 threads)

**Instance Type:** t2.micro

**Scaling Parameters:**
- Minimum Instances: 5
- Maximum Instances: 15
- Messages per Instance: 5
- Minimum Runtime: 300 seconds

**Queue Configuration:** Long polling (20 seconds wait time)

## Prerequisites

- AWS Account with appropriate IAM permissions
- Pre-configured AMI with face recognition model
- VPC with configured subnet and security group
- IAM instance profile for app tier instances
- SQS queues created (request and response)
- S3 buckets created (input and output)

## Dependencies

```
flask
boto3
waitress
requests
```

## Deployment

1. Create the required AWS infrastructure (VPC, subnets, security groups)
2. Build an AMI with the face recognition model installed
3. Create SQS queues and S3 buckets
4. Deploy the web tier EC2 instance
5. Start the controller process on the web tier
6. Configure the web server to accept requests

## Usage

```bash
curl -X POST -F "inputFile=@face.jpg" http://<web-tier-ip>:8000/
```

## Scaling Behavior

The system automatically adapts to varying workloads:

- **Low Load:** Maintains minimum 5 instances for quick response
- **High Load:** Scales out to handle burst traffic (up to 15 instances)
- **Scale In:** Gracefully terminates idle instances when demand decreases

## Project Context

This project was developed as part of a Cloud Computing course at Arizona State University, demonstrating advanced IaaS concepts including custom auto-scaling, distributed processing, message queue architectures, and multi-tier application design on AWS.
