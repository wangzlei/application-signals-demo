const { Stack, RemovalPolicy } = require('aws-cdk-lib');
const ecrAssets = require('aws-cdk-lib/aws-ecr-assets');
const iam = require('aws-cdk-lib/aws-iam');
const { BedrockAgentCoreDeployer } = require('./bedrock-agentcore-deployer');

/**
 * CDK Stack that deploys the Pet Clinic Agents images to ECR and creates Bedrock AgentCore Runtime instances
 * for those images. AgentCore Runtime is a containerized host service for AI agents that processes user inputs,
 * maintains context, and executes actions using AI capabilities.
 * 
 * See: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html
 */
class PetClinicAgentsStack extends Stack {
  constructor(scope, id, props) {
    super(scope, id, props);

    const account = this.account;
    const region = this.region;

    // Create Bedrock AgentCore execution role:
    // See: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html
    const agentCoreRole = new iam.Role(this, 'BedrockAgentCoreRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      roleName: 'PetClinicBedrockAgentCoreRole',
      inlinePolicies: {
        AgentCorePolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ecr:BatchGetImage',
                'ecr:GetDownloadUrlForLayer',
                'ecr:GetAuthorizationToken'
              ],
              resources: ['*']
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
              ],
              resources: [`arn:aws:logs:${region}:${account}:*`]
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:*'
              ],
              resources: ['*']
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream'
              ],
              resources: ['*']
            }),
            // Application Signals permissions for telemetry
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords',
                'xray:GetSamplingRules',
                'xray:GetSamplingTargets',
                'xray:GetSamplingStatisticSummaries'
              ],
              resources: ['*']
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'cloudwatch:PutMetricData'
              ],
              resources: ['*'],
              conditions: {
                StringEquals: {
                  'cloudwatch:namespace': 'AWS/ApplicationSignals'
                }
              }
            })
          ]
        })
      }
    });
    
    const nutritionAgentImage = new ecrAssets.DockerImageAsset(this, 'NutritionAgentImage', {
      directory: '../../pet_clinic_ai_agents/nutrition_agent'
    });

    const primaryAgentImage = new ecrAssets.DockerImageAsset(this, 'PrimaryAgentImage', {
      directory: '../../pet_clinic_ai_agents/primary_agent'
    });

    // Common Application Signals environment variables
    const appSignalsEnvVars = {
      // OpenTelemetry configuration for Application Signals
      OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
      OTEL_EXPORTER_OTLP_ENDPOINT: 'http://localhost:4316',
      OTEL_AWS_APPLICATION_SIGNALS_ENABLED: 'true',
      OTEL_METRICS_EXPORTER: 'none',
      OTEL_PYTHON_DISABLED_INSTRUMENTATIONS: 'sqlalchemy,psycopg2,pymysql,sqlite3,aiopg,asyncpg,mysql_connector,system_metrics,google-genai',
      // Service identification for Application Signals
      OTEL_SERVICE_NAME: 'bedrock-agents',
      OTEL_RESOURCE_ATTRIBUTES: `service.name=bedrock-agents,aws.hostedIn.environment=bedrock-agentcore,aws.hostedIn.region=${region}`
    };

    // Deploy nutrition agent with optional environment variable
    const nutritionAgentProps = {
      AgentName: 'nutrition_agent',
      ImageUri: nutritionAgentImage.imageUri,
      ExecutionRole: agentCoreRole.roleArn,
      Entrypoint: 'nutrition_agent.py'
    };
    
    if (props?.nutritionServiceUrl) {
      nutritionAgentProps.EnvironmentVariables = {
        ...appSignalsEnvVars,
        NUTRITION_SERVICE_URL: props.nutritionServiceUrl,
        OTEL_RESOURCE_ATTRIBUTES: `service.name=nutrition-agent,aws.hostedIn.environment=bedrock-agentcore,aws.hostedIn.region=${region}`
      };
    } else {
      nutritionAgentProps.EnvironmentVariables = {
        ...appSignalsEnvVars,
        OTEL_RESOURCE_ATTRIBUTES: `service.name=nutrition-agent,aws.hostedIn.environment=bedrock-agentcore,aws.hostedIn.region=${region}`
      };
    }
    
    const nutritionAgent = new BedrockAgentCoreDeployer(this, 'NutritionAgent', nutritionAgentProps);

    // Deploy primary agent
    const primaryAgent = new BedrockAgentCoreDeployer(this, 'PrimaryAgent', {
      AgentName: 'pet_clinic_agent',
      ImageUri: primaryAgentImage.imageUri,
      ExecutionRole: agentCoreRole.roleArn,
      Entrypoint: 'pet_clinic_agent.py',
      EnvironmentVariables: {
        ...appSignalsEnvVars,
        NUTRITION_AGENT_ARN: nutritionAgent.agentArn,
        OTEL_RESOURCE_ATTRIBUTES: `service.name=primary-agent,aws.hostedIn.environment=bedrock-agentcore,aws.hostedIn.region=${region}`
      }
    });

    this.nutritionAgentImageUri = nutritionAgentImage.imageUri;
    this.primaryAgentImageUri = primaryAgentImage.imageUri;
    this.nutritionAgentArn = nutritionAgent.agentArn;
    this.primaryAgentArn = primaryAgent.agentArn;
  }
}

module.exports = { PetClinicAgentsStack };