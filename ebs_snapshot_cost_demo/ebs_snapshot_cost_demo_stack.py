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

        # Update this line
        size=Size.gibibytes(volume_size_gb),

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
            # policy_type="EBS_SNAPSHOT_POLICY",
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
                        "times": ["00:05"]
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

        # Create DLM Lifecycle Policy for monthly retention
        dlm.CfnLifecyclePolicy(self, "MonthlyRetentionPolicy",
            description="EBS snapshot policy with monthly retention",
            state="ENABLED",
            execution_role_arn=dlm_role.role_arn,
            # policy_type="EBS_SNAPSHOT_POLICY",
            policy_details={
                "resourceTypes": ["VOLUME"],
                "targetTags": [{
                    "key": "RetentionStrategy",
                    "value": "monthly"
                }],
                "schedules": [{
                    "name": "monthly-retention-schedule",
                    "createRule": {
                        "interval": 24,
                        "intervalUnit": "HOURS",
                        "times": ["00:21"]
                    },
                    "retainRule": {
                        "count": 30
                    },
                    "copyTags": True,
                    "tagsToAdd": [{
                        "key": "SnapshotType",
                        "value": "MonthlyRetention"
                    }]
                }]
            }
        )
