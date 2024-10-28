#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import aws_cdk as cdk
from ebs_snapshot_cost_demo.ebs_snapshot_cost_demo_stack import EbsSnapshotCostDemoStack

load_dotenv()  # Load environment variables from .env file

app = cdk.App()

# Add the missing arguments here
instance_type = "t3.micro"  # You can change this to your desired instance type
volume_size_gb = 20  # You can adjust this value as needed

EbsSnapshotCostDemoStack(app, "EbsSnapshotCostDemoStack",
    instance_type=instance_type,
    volume_size_gb=volume_size_gb
)

app.synth()
