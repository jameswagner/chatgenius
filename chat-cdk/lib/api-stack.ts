import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import { Construct } from 'constructs';

export class ApiStack extends Construct {
  public readonly httpApi: apigateway.RestApi;
  public readonly wsApi: apigatewayv2.CfnApi;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    // REST API for HTTP endpoints
    this.httpApi = new apigateway.RestApi(this, 'SlackCloneApi', {
      restApiName: 'slack-clone-api',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
    });

    // WebSocket API for real-time messaging
    this.wsApi = new apigatewayv2.CfnApi(this, 'SlackCloneWebSocketApi', {
      name: 'slack-clone-websocket-api',
      protocolType: 'WEBSOCKET',
      routeSelectionExpression: '$request.body.action',
    });
  }
} 