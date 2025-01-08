import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs_patterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import { Construct } from 'constructs';

interface EcsStackProps {
  userPool: cognito.UserPool;
  messageTable: dynamodb.Table;
  channelTable: dynamodb.Table;
  repository: ecr.Repository;
}

export class EcsStack extends Construct {
  constructor(scope: Construct, id: string, props: EcsStackProps) {
    super(scope, id);

    // Create VPC
    const vpc = new ec2.Vpc(this, 'SlackCloneVPC', {
      maxAzs: 2,
    });

    // Create ECS Cluster
    const cluster = new ecs.Cluster(this, 'SlackCloneCluster', {
      vpc: vpc,
    });

    // Create Fargate Service
    const fargateService = new ecs_patterns.ApplicationLoadBalancedFargateService(this, 'SlackCloneService', {
      cluster: cluster,
      cpu: 256,
      memoryLimitMiB: 512,
      desiredCount: 1,
      taskImageOptions: {
        image: ecs.ContainerImage.fromEcrRepository(props.repository, 'latest'),
        environment: {
          USER_POOL_ID: props.userPool.userPoolId,
          MESSAGES_TABLE: props.messageTable.tableName,
          CHANNELS_TABLE: props.channelTable.tableName,
        },
      },
      publicLoadBalancer: true,
    });

    // Grant permissions
    props.messageTable.grantReadWriteData(fargateService.taskDefinition.taskRole);
    props.channelTable.grantReadWriteData(fargateService.taskDefinition.taskRole);
  }
} 