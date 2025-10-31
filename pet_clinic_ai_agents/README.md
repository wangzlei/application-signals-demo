# Pet Clinic AI Agents

### Primary Agent (Pet Clinic Assistant)
- **Purpose**: General pet clinic assistant handling appointment scheduling, clinic information, and emergency contacts
- **Capabilities**: 
  - Answers general pet clinic questions
  - Provides clinic hours and contact information
  - Handles appointment-related queries
  - Delegates nutrition questions to the Nutrition Agent
  - Rejects requests unrelated to the pet clinic.
- **Entry Point**: `pet_clinic_agent.py`

### Nutrition Agent
- **Purpose**: Specialized agent focused on pet nutrition and dietary guidance
- **Capabilities**:
  - Provides pet nutrition recommendations
  - Offers diet guidelines for different pets
  - Answers feeding-related questions
  - Gives specialized nutritional advice
  - Includes configurable random failure simulations.
- **Entry Point**: `nutrition_agent.py`

## Architecture

- **Bedrock AgentCore Runtime**: Containerized host service for AI agents: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html
- **Strands SDK**: Code-first framework for building agents: https://strandsagents.com/latest/documentation/docs/

## Application Signals Integration

Both agents are instrumented with **AWS Application Signals** for comprehensive observability:

### Features Enabled
- **Distributed Tracing**: Full request tracing across agent interactions
- **Custom Metrics**: Agent-specific performance metrics
- **Service Maps**: Visual representation of agent dependencies
- **Error Tracking**: Automatic error detection and alerting

### Instrumentation Details
- **OpenTelemetry Auto-Instrumentation**: Automatic HTTP, Boto3, and request tracing
- **Manual Spans**: Custom spans for agent tools and operations
- **Service Identification**: Each agent identified as separate service in Application Signals
- **Trace Attributes**: Rich metadata including session IDs, tool names, and operation results

### Monitoring Capabilities
- Monitor agent response times and throughput
- Track tool usage patterns and performance
- Detect errors in agent-to-agent communication
- Analyze nutrition service API dependencies
- Set up SLOs for agent availability and latency

### Environment Variables
The following OpenTelemetry environment variables are automatically configured:
- `OTEL_AWS_APPLICATION_SIGNALS_ENABLED=true`
- `OTEL_SERVICE_NAME`: Set to `primary-agent` or `nutrition-agent`
- `OTEL_RESOURCE_ATTRIBUTES`: Includes service name and environment metadata
- `OTEL_EXPORTER_OTLP_ENDPOINT`: Configured for Application Signals collection
 
## Deployment

Deploy using the setup script:
```bash
cd scripts/agents && ./setup-agents-demo.sh --region=us-east-1
```

After deployment, agents will automatically send telemetry data to AWS Application Signals for monitoring and observability.