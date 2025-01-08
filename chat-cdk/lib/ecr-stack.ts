import * as cdk from 'aws-cdk-lib';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import { Construct } from 'constructs';

export class EcrStack extends Construct {
  public readonly repository: ecr.Repository;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.repository = new ecr.Repository(this, 'SlackCloneRepo', {
      repositoryName: 'slack-clone-app',
      imageScanOnPush: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
  }
} 