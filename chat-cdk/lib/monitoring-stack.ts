import * as cdk from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as sns from 'aws-cdk-lib/aws-sns';
import { Construct } from 'constructs';

export class MonitoringStack extends Construct {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    const alarmTopic = new sns.Topic(this, 'AlarmTopic');

    // API Latency Alarm
    new cloudwatch.Alarm(this, 'ApiLatencyAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApiGateway',
        metricName: 'Latency',
        statistic: 'avg',
      }),
      threshold: 1000,
      evaluationPeriods: 3,
      alarmDescription: 'API latency is too high',
    }).addAlarmAction(new cdk.aws_cloudwatch_actions.SnsAction(alarmTopic));
  }
} 