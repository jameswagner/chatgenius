import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as nodejs from 'aws-cdk-lib/aws-lambda-nodejs';
import { Construct } from 'constructs';

export class LambdaStack extends Construct {
  public readonly wsHandler: lambda.Function;
  public readonly authHandler: lambda.Function;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.wsHandler = new nodejs.NodejsFunction(this, 'WebSocketHandler', {
      entry: 'lambda/websocket/handler.ts',
      handler: 'handler',
      runtime: lambda.Runtime.NODEJS_18_X,
    });

    this.authHandler = new nodejs.NodejsFunction(this, 'AuthHandler', {
      entry: 'lambda/auth/handler.ts',
      handler: 'handler',
      runtime: lambda.Runtime.NODEJS_18_X,
    });
  }
} 