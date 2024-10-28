# EBS Snapshot Cost Demo

This project demonstrates different EBS snapshot retention strategies and their cost implications using AWS CDK. It creates two EC2 instances with attached EBS volumes, each following different snapshot retention policies.

## Architecture

The stack creates:
- VPC with public and private subnets
- Two EC2 instances (t3.micro) with Amazon Linux 2
- Two EBS volumes (GP3, 20GB each) with different retention strategies:
  - Volume 0: 3-day retention
  - Volume 1: Monthly retention
- DLM (Data Lifecycle Manager) policies for automated snapshot management
- IAM roles for EC2 and DLM

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.7 or higher
- AWS CDK CLI installed
- Virtual environment setup

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ebs-snapshot-cost-demo
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Project Structure

```plaintext
ebs-snapshot-cost-demo/
├── .env                    # Environment variables (create this)
├── app.py                  # CDK app entry point
├── requirements.txt        # Python dependencies
└── ebs_snapshot_cost_demo/
    ├── __init__.py
    └── ebs_snapshot_cost_demo_stack.py  # Main stack definition
```

## Code Implementation

### Requirements File
```txt
aws-cdk-lib==2.88.0
constructs>=10.0.0,<11.0.0
python-dotenv==1.0.0
```

### Main App Entry Point
```python
#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import aws_cdk as cdk
from ebs_snapshot_cost_demo.ebs_snapshot_cost_demo_stack import EbsSnapshotCostDemoStack

load_dotenv()  # Load environment variables from .env file

app = cdk.App()

instance_type = "t3.micro"  # You can change this to your desired instance type
volume_size_gb = 20  # You can adjust this value as needed

EbsSnapshotCostDemoStack(app, "EbsSnapshotCostDemoStack",
    instance_type=instance_type,
    volume_size_gb=volume_size_gb
)

app.synth()
```

### Stack Implementation
```python
import os
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_dlm as dlm,
    CfnOutput,
    RemovalPolicy,
    Tags,
    Size,
    Duration
)
from constructs import Construct

class EbsSnapshotCostDemoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, instance_type: str, volume_size_gb: int, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC
        vpc = ec2.Vpc(self, "VPC", max_azs=2)

        # Create IAM role for EC2 instances
        role = iam.Role(self, "EC2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )

        # User data script to create files and set up cron job
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "yum update -y",
            "yum install -y cronie",
            "echo '0 0 * * * dd if=/dev/zero of=/data/file_$(date +%Y%m%d).bin bs=1M count=2048' | crontab -",
            "systemctl enable crond && systemctl start crond"
        )

        # Create two EC2 instances with EBS volumes
        for i in range(2):
            instance = ec2.Instance(self, f"Instance{i}",
                instance_type=ec2.InstanceType(instance_type),
                machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
                vpc=vpc,
                role=role,
                user_data=user_data
            )

            # Add EBS volume
            volume = ec2.Volume(self, f"EBSVolume{i}",
                availability_zone=instance.instance_availability_zone,
                size=Size.gibibytes(volume_size_gb),
                volume_type=ec2.EbsDeviceVolumeType.GP3,
                encrypted=True
            )
            volume.apply_removal_policy(RemovalPolicy.DESTROY)

            # Attach volume to instance
            ec2.CfnVolumeAttachment(self, f"VolumeAttachment{i}",
                device="/dev/sdf",
                instance_id=instance.instance_id,
                volume_id=volume.volume_id
            )

            # Add tags for cost allocation
            Tags.of(volume).add("Purpose", f"EBSSnapshotCostDemo{i}")
            Tags.of(volume).add("Name", f"EBSVolume{i}")
            Tags.of(volume).add("RetentionStrategy", "3days" if i == 0 else "monthly")
            Tags.of(instance).add("Name", f"EC2-Instance{i}")

            CfnOutput(self, f"InstanceId{i}", value=instance.instance_id)
            CfnOutput(self, f"VolumeId{i}", value=volume.volume_id)

        # Create DLM Lifecycle Role
        dlm_role = iam.Role(self, "DLMLifecycleRole",
            assumed_by=iam.ServicePrincipal("dlm.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSDataLifecycleManagerServiceRole")
            ]
        )

        # Create DLM Lifecycle Policy for 3-day retention
        dlm.CfnLifecyclePolicy(self, "ThreeDayRetentionPolicy",
            description="EBS snapshot policy with 3-day retention",
            state="ENABLED",
            execution_role_arn=dlm_role.role_arn,
            policy_details={
                "resourceTypes": ["VOLUME"],
                "targetTags": [{
                    "key": "RetentionStrategy",
                    "value": "3days"
                }],
                "schedules": [{
                    "name": "3-day-retention-schedule",
                    "createRule": {
                        "interval": 24,
                        "intervalUnit": "HOURS",
                        "times": ["04:00"]
                    },
                    "retainRule": {
                        "count": 3
                    },
                    "copyTags": True,
                    "tagsToAdd": [{
                        "key": "SnapshotType",
                        "value": "3DayRetention"
                    }]
                }]
            }
        )
```

## Deployment

1. Bootstrap CDK (first time only):
```bash
cdk bootstrap
```

2. Deploy the stack:
```bash
cdk deploy
```

3. To destroy the resources:
```bash
cdk destroy
```

## Cost Monitoring

Monitor the costs associated with:
- EBS volumes (GP3, 20GB each)
- EBS snapshots (varying retention periods)
- EC2 instances (t3.micro)
- Data transfer

Use AWS Cost Explorer to track costs by tags:
- Purpose: EBSSnapshotCostDemo0, EBSSnapshotCostDemo1
- RetentionStrategy: 3days, monthly

## Security Considerations

- All EBS volumes are encrypted
- EC2 instances use IAM roles for secure access
- VPC security groups control network access
- DLM uses dedicated IAM role for snapshot management

## Useful Commands

```bash
# CDK Commands
cdk ls                      # List all stacks in the app
cdk synth                   # Synthesize CloudFormation template
cdk diff                    # Compare deployed stack with current state
cdk deploy                  # Deploy this stack to your default AWS account/region
cdk destroy                 # Destroy this stack from your default AWS account/region

# AWS CLI Commands
aws ec2 describe-volumes    # List EBS volumes
aws ec2 describe-snapshots  # List EBS snapshots
aws dlm describe-lifecycle-policies  # List DLM policies

# Python Virtual Environment
python -m venv .venv       # Create virtual environment
source .venv/bin/activate  # Activate virtual environment (Linux/Mac)
.venv\Scripts\activate     # Activate virtual environment (Windows)
deactivate                 # Deactivate virtual environment
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license here]

## Author

[Your Name]

## Acknowledgments

- AWS CDK Documentation
- AWS EBS Documentation
- AWS DLM Documentation