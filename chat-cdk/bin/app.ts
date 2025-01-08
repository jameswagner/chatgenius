import * as cdk from 'aws-cdk-lib';
import { NetworkingStack } from '../lib/networking-stack';
import { StorageStack } from '../lib/storage-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

// Create networking stack first
const networkingStack = new NetworkingStack(app, 'ChatGeniusNetworkingStack', { env });

// Create storage stack with VPC from networking stack
new StorageStack(app, 'ChatGeniusStorageStack', {
  env,
  vpc: networkingStack.vpc,
}); 