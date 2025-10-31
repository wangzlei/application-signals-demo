from strands import Agent, tool
import uvicorn
import requests
import os
import boto3
import uuid
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from opentelemetry import trace

BEDROCK_MODEL_ID = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
NUTRITION_SERVICE_URL = os.environ.get('NUTRITION_SERVICE_URL')

# Get tracer for Application Signals
tracer = trace.get_tracer(__name__)

agent = None
agent_app = BedrockAgentCoreApp()

def get_nutrition_data(pet_type):
    """Helper function to get nutrition data from the API"""
    with tracer.start_as_current_span("get_nutrition_data") as span:
        span.set_attribute("pet.type", pet_type)
        span.set_attribute("nutrition.service.url", NUTRITION_SERVICE_URL or "not_configured")
        
        if not NUTRITION_SERVICE_URL:
            span.set_attribute("error", "nutrition_service_not_configured")
            return {"facts": "Error: Nutrition service not found", "products": ""}
        
        try:
            url = f"{NUTRITION_SERVICE_URL}/{pet_type.lower()}"
            span.set_attribute("http.url", url)
            
            response = requests.get(url, timeout=5)
            span.set_attribute("http.status_code", response.status_code)
            
            if response.status_code == 200:
                data = response.json()
                span.set_attribute("success", True)
                span.set_attribute("has_facts", bool(data.get('facts')))
                span.set_attribute("has_products", bool(data.get('products')))
                return {"facts": data.get('facts', ''), "products": data.get('products', '')}
            
            span.set_attribute("error", "http_error")
            return {"facts": f"Error: Nutrition service could not find information for pet: {pet_type.lower()}", "products": ""}
        except requests.RequestException as e:
            span.set_attribute("error", "request_exception")
            span.set_attribute("error.message", str(e))
            return {"facts": "Error: Nutrition service down", "products": ""}

@tool
def get_feeding_guidelines(pet_type):
    """Get feeding guidelines based on pet type"""
    with tracer.start_as_current_span("get_feeding_guidelines") as span:
        span.set_attribute("tool.name", "get_feeding_guidelines")
        span.set_attribute("pet.type", pet_type)
        
        data = get_nutrition_data(pet_type)
        result = f"Nutrition info for {pet_type}: {data['facts']}"
        if data['products']:
            result += f" Recommended products available at our clinic: {data['products']}"
        
        span.set_attribute("result.length", len(result))
        return result

@tool
def get_dietary_restrictions(pet_type):
    """Get dietary recommendations for specific health conditions by animal type"""
    with tracer.start_as_current_span("get_dietary_restrictions") as span:
        span.set_attribute("tool.name", "get_dietary_restrictions")
        span.set_attribute("pet.type", pet_type)
        
        data = get_nutrition_data(pet_type)
        result = f"Dietary info for {pet_type}: {data['facts']}. Consult veterinarian for condition-specific advice."
        if data['products']:
            result += f" Recommended products available at our clinic: {data['products']}"
        
        span.set_attribute("result.length", len(result))
        return result

@tool
def get_nutritional_supplements(pet_type):
    """Get supplement recommendations by animal type"""
    with tracer.start_as_current_span("get_nutritional_supplements") as span:
        span.set_attribute("tool.name", "get_nutritional_supplements")
        span.set_attribute("pet.type", pet_type)
        
        data = get_nutrition_data(pet_type)
        result = f"Supplement info for {pet_type}: {data['facts']}. Consult veterinarian for supplements."
        if data['products']:
            result += f" Recommended products available at our clinic: {data['products']}"
        
        span.set_attribute("result.length", len(result))
        return result

@tool
def create_order(product_name, pet_type, quantity=1):
    """Create an order for a recommended product. Requires pet_type and quantity."""
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("tool.name", "create_order")
        span.set_attribute("product.name", product_name)
        span.set_attribute("pet.type", pet_type)
        span.set_attribute("order.quantity", quantity)
        
        data = get_nutrition_data(pet_type)
        if data['products'] and product_name.lower() in data['products'].lower():
            order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            total_cost = quantity * 29.99
            
            span.set_attribute("order.id", order_id)
            span.set_attribute("order.total", total_cost)
            span.set_attribute("order.success", True)
            
            return f"Order {order_id} created for {quantity}x {product_name}. Total: ${total_cost:.2f}. Expected delivery: 3-5 business days."
        
        span.set_attribute("order.success", False)
        span.set_attribute("error", "product_not_available")
        return f"Sorry, can't make the order. {product_name} is not available in our inventory for {pet_type}."

def create_nutrition_agent():
    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
    )

    tools = [get_feeding_guidelines, get_dietary_restrictions, get_nutritional_supplements, create_order]

    system_prompt = (
        "You are a specialized pet nutrition expert at our veterinary clinic, providing accurate, evidence-based dietary guidance for pets. "
        "Never mention using any API, tools, or external services - present all advice as your own expert knowledge.\n\n"
        "When providing nutrition guidance:\n"
        "- Use the specific nutrition information available to you as the foundation for your recommendations\n"
        "- Always recommend the SPECIFIC PRODUCT NAMES provided to you that pet owners should buy FROM OUR PET CLINIC\n"
        "- Mention our branded products by name (like PurrfectChoice, BarkBite, FeatherFeast, etc.) when recommending food\n"
        "- Emphasize that we carry high-quality, veterinarian-recommended food brands at our clinic\n"
        "- Give actionable dietary recommendations including feeding guidelines, restrictions, and supplements\n"
        "- Expand on basic nutrition facts with comprehensive guidance for age, weight, and health conditions\n"
        "- Always mention that pet owners can purchase the recommended food items directly from our clinic for convenience and quality assurance\n"
        "- If asked to order or purchase a product, use the create_order tool to place the order"
    )

    return Agent(model=model, tools=tools, system_prompt=system_prompt)
    

@agent_app.entrypoint
async def invoke(payload, context):
    """
    Invoke the nutrition agent with a payload
    """
    with tracer.start_as_current_span("nutrition_agent_invoke") as span:
        span.set_attribute("agent.type", "nutrition_agent")
        
        agent = create_nutrition_agent()
        msg = payload.get('prompt', '')
        span.set_attribute("prompt.length", len(msg))

        response_data = []
        async for event in agent.stream_async(msg):
            if 'data' in event:
                response_data.append(event['data'])
        
        response = ''.join(response_data)
        span.set_attribute("response.length", len(response))
        return response

if __name__ == "__main__":    
    uvicorn.run(agent_app, host='0.0.0.0', port=8080)