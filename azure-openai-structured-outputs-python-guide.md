# Azure OpenAI Structured Outputs - Python Developer Guide

A comprehensive reference guide for implementing structured outputs with Azure OpenAI using Python.

## Table of Contents

- [Overview](#overview)
- [Supported Models](#supported-models)
- [API Support](#api-support)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Authentication Setup](#authentication-setup)
- [Basic Implementation](#basic-implementation)
- [Function Calling with Structured Outputs](#function-calling-with-structured-outputs)
- [Schema Requirements and Limitations](#schema-requirements-and-limitations)
- [Advanced Examples](#advanced-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Structured outputs ensure that Azure OpenAI models follow a specific JSON Schema definition that you provide as part of your inference API call. This feature guarantees strict adherence to the supplied schema, unlike the older JSON mode which only guaranteed valid JSON.

**Key Benefits:**
- Guaranteed schema compliance
- Improved function calling reliability
- Structured data extraction
- Complex multi-step workflow support

**Current Limitations:**
- Not supported with "Bring your own data" scenarios
- Not supported with Assistants or Azure AI Agents Service
- Not supported with audio preview models

## Supported Models

The following models support structured outputs:

- `gpt-4o` (versions: `2024-08-06`, `2024-11-20`)
- `gpt-4o-mini` (version: `2024-07-18`)
- `gpt-4.1` (version: `2025-04-14`)
- `gpt-4.1-mini` (version: `2025-04-14`)
- `gpt-4.1-nano` (version: `2025-04-14`)
- `gpt-4.5-preview` (version: `2025-02-27`)
- `o1` (version: `2024-12-17`)
- `o3` (version: `2025-04-16`)
- `o3-mini` (version: `2025-01-31`)
- `o3-pro` (version: `2025-06-10`)
- `o4-mini` (version: `2025-04-16`)
- `codex-mini` (version: `2025-05-16`)

## API Support

- **First Available:** API version `2024-08-01-preview`
- **Latest GA API:** `2024-10-21`
- **Preview APIs:** Available in latest preview versions

## Prerequisites

- Azure OpenAI resource with a supported model deployment
- Python 3.7+
- Azure subscription with appropriate permissions

## Installation

```bash
pip install openai pydantic azure-identity --upgrade
```

**Tested Versions:**
- `openai >= 1.42.0`
- `pydantic >= 2.8.2`

## Authentication Setup

### Option 1: Microsoft Entra ID (Recommended)

```python
import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

# Set up token provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), 
    "https://cognitiveservices.azure.com/.default"
)

# Initialize client
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_ad_token_provider=token_provider,
    api_version="2024-10-21"
)
```

### Option 2: API Key Authentication

```python
import os
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-21"
)
```

## Basic Implementation

### Simple Schema Example

```python
from pydantic import BaseModel
from typing import List

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: List[str]

# Make the API call
completion = client.beta.chat.completions.parse(
    model="YOUR_MODEL_DEPLOYMENT_NAME",
    messages=[
        {"role": "system", "content": "Extract the event information."},
        {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
    ],
    response_format=CalendarEvent,
)

# Access parsed result
event = completion.choices[0].message.parsed
print(f"Event: {event.name} on {event.date} with {event.participants}")

# Raw JSON output
print(completion.model_dump_json(indent=2))
```

### Expected Output

```python
# Parsed object
name='Science Fair' date='Friday' participants=['Alice', 'Bob']

# Full response includes 'parsed' field with structured data
{
  "choices": [
    {
      "message": {
        "content": "{\n  \"name\": \"Science Fair\",\n  \"date\": \"Friday\",\n  \"participants\": [\"Alice\", \"Bob\"]\n}",
        "parsed": {
          "name": "Science Fair",
          "date": "Friday",
          "participants": ["Alice", "Bob"]
        }
      }
    }
  ]
}
```

## Function Calling with Structured Outputs

Enable structured outputs for function calling by setting `strict: true`.

> **Important:** Structured outputs are not supported with parallel function calls. Set `parallel_tool_calls` to `false`.

```python
from enum import Enum
from typing import Union
from pydantic import BaseModel
import openai

class GetDeliveryDate(BaseModel):
    order_id: str

# Create tools with structured outputs
tools = [openai.pydantic_function_tool(GetDeliveryDate)]

messages = [
    {"role": "system", "content": "You are a helpful customer support assistant. Use the supplied tools to assist the user."},
    {"role": "user", "content": "Hi, can you tell me the delivery date for my order #12345?"}
]

response = client.chat.completions.create(
    model="YOUR_MODEL_DEPLOYMENT_NAME",
    messages=messages,
    tools=tools,
    parallel_tool_calls=False  # Required for structured outputs
)

# Access function call details
tool_call = response.choices[0].message.tool_calls[0]
print(f"Function: {tool_call.function.name}")
print(f"Arguments: {tool_call.function.arguments}")
```

### Advanced Function Example

```python
from enum import Enum
from typing import Optional, List

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class CreateTask(BaseModel):
    title: str
    description: str
    priority: Priority
    assignee: str
    due_date: Optional[str] = None
    tags: List[str] = []

class UpdateTaskStatus(BaseModel):
    task_id: str
    status: str
    notes: Optional[str] = None

# Multiple function tools
tools = [
    openai.pydantic_function_tool(CreateTask),
    openai.pydantic_function_tool(UpdateTaskStatus)
]
```

## Schema Requirements and Limitations

### Supported JSON Schema Types

- **String**
- **Number**
- **Boolean**
- **Integer**
- **Object**
- **Array**
- **Enum**
- **anyOf** (not at root level)

### Critical Requirements

#### 1. All Fields Must Be Required

```python
# ✅ Correct: All fields are required
class UserProfile(BaseModel):
    name: str
    email: str
    age: int

# ❌ Incorrect: Optional fields not allowed
class UserProfile(BaseModel):
    name: str
    email: str
    age: Optional[int] = None  # This will cause issues
```

#### 2. Emulating Optional Fields with Union Types

```python
from typing import Union

class UserProfile(BaseModel):
    name: str
    email: str
    age: Union[int, None]  # Use Union with None instead of Optional
```

#### 3. additionalProperties Must Be False

When defining raw JSON schemas, always set `additionalProperties: false`:

```json
{
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "number"}
    },
    "additionalProperties": false,
    "required": ["name", "age"]
}
```

#### 4. Nesting Limitations

- Maximum 100 object properties total
- Maximum 5 levels of nesting depth

### Unsupported Keywords

| Type | Unsupported Keywords |
|------|---------------------|
| String | `minLength`, `maxLength`, `pattern`, `format` |
| Number | `minimum`, `maximum`, `multipleOf` |
| Objects | `patternProperties`, `unevaluatedProperties`, `propertyNames`, `minProperties`, `maxProperties` |
| Arrays | `unevaluatedItems`, `contains`, `minContains`, `maxContains`, `minItems`, `maxItems`, `uniqueItems` |

## Advanced Examples

### Using anyOf for Complex Types

```python
from typing import Union
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

class Address(BaseModel):
    number: str
    street: str
    city: str

class DatabaseItem(BaseModel):
    item: Union[User, Address]

# Usage
completion = client.beta.chat.completions.parse(
    model="YOUR_MODEL_DEPLOYMENT_NAME",
    messages=[
        {"role": "user", "content": "Create a user named John who is 30 years old"}
    ],
    response_format=DatabaseItem,
)
```

### Recursive Schemas

```python
from typing import Optional, List

class UIComponent(BaseModel):
    type: str
    label: str
    children: List['UIComponent'] = []
    attributes: List[dict] = []

# Enable forward references
UIComponent.model_rebuild()

# Usage for dynamic UI generation
completion = client.beta.chat.completions.parse(
    model="YOUR_MODEL_DEPLOYMENT_NAME",
    messages=[
        {"role": "user", "content": "Create a login form with username, password fields and a submit button"}
    ],
    response_format=UIComponent,
)
```

### Complex Data Extraction

```python
from typing import List, Optional
from enum import Enum

class DocumentType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    REPORT = "report"

class LineItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    total: float

class DocumentAnalysis(BaseModel):
    document_type: DocumentType
    document_number: str
    date: str
    total_amount: float
    line_items: List[LineItem]
    vendor_name: str
    vendor_address: Optional[str] = None

# Extract structured data from documents
completion = client.beta.chat.completions.parse(
    model="YOUR_MODEL_DEPLOYMENT_NAME",
    messages=[
        {"role": "system", "content": "Analyze the document and extract all relevant information."},
        {"role": "user", "content": "Invoice #INV-2024-001 from ABC Corp..."}
    ],
    response_format=DocumentAnalysis,
)
```

## Best Practices

### 1. Schema Design

```python
# ✅ Use descriptive field names and types
class ProductReview(BaseModel):
    product_id: str
    reviewer_name: str
    rating: int  # 1-5 scale
    review_text: str
    review_date: str
    is_verified_purchase: bool

# ✅ Use enums for controlled vocabularies
class ReviewSentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
```

### 2. Error Handling

```python
try:
    completion = client.beta.chat.completions.parse(
        model="YOUR_MODEL_DEPLOYMENT_NAME",
        messages=messages,
        response_format=YourSchema,
    )
    
    if completion.choices[0].message.parsed:
        result = completion.choices[0].message.parsed
        # Process the structured result
    else:
        # Handle case where parsing failed
        print("Failed to parse response into schema")
        
except Exception as e:
    print(f"API call failed: {e}")
```

### 3. Validation and Type Checking

```python
from pydantic import BaseModel, Field, validator

class EmailData(BaseModel):
    email: str = Field(..., description="Valid email address")
    subject: str = Field(..., min_length=1, max_length=200)
    priority: int = Field(..., ge=1, le=5)
    
    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v
```

### 4. Environment Configuration

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Environment variables
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")

# Validate required environment variables
required_vars = [AZURE_OPENAI_ENDPOINT, MODEL_DEPLOYMENT_NAME]
if not all(required_vars):
    raise ValueError("Missing required environment variables")
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Schema Validation Errors

```python
# Problem: Optional fields causing validation errors
class BadSchema(BaseModel):
    name: str
    age: Optional[int] = None  # ❌ Will cause issues

# Solution: Use Union types
class GoodSchema(BaseModel):
    name: str
    age: Union[int, None]  # ✅ Correct approach
```

#### 2. Nested Depth Exceeded

```python
# ❌ Too deeply nested (over 5 levels)
class TooDeep(BaseModel):
    level1: 'Level1'

class Level1(BaseModel):
    level2: 'Level2'
# ... continues to Level6+

# ✅ Flatten the structure
class Flattened(BaseModel):
    data: List[dict]  # Use simple structures when possible
```

#### 3. Function Calling Issues

```python
# ❌ Parallel function calls with structured outputs
response = client.chat.completions.create(
    model="YOUR_MODEL_DEPLOYMENT_NAME",
    messages=messages,
    tools=tools,
    parallel_tool_calls=True  # Will cause errors
)

# ✅ Disable parallel function calls
response = client.chat.completions.create(
    model="YOUR_MODEL_DEPLOYMENT_NAME",
    messages=messages,
    tools=tools,
    parallel_tool_calls=False  # Required for structured outputs
)
```

### Debugging Tips

1. **Check API Version**: Ensure you're using `2024-10-21` or later
2. **Validate Schema**: Test your Pydantic models independently
3. **Review Logs**: Check the full response for error details
4. **Simplify First**: Start with simple schemas and add complexity gradually

### Performance Considerations

- **Token Usage**: Structured outputs may use slightly more tokens
- **Response Time**: Complex schemas may increase response time
- **Rate Limits**: Follow Azure OpenAI rate limiting guidelines

## Example: Complete Application

```python
import os
from typing import List, Union
from enum import Enum
from pydantic import BaseModel
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Schema definitions
class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Task(BaseModel):
    title: str
    description: str
    priority: TaskPriority
    estimated_hours: Union[int, None]

class ProjectPlan(BaseModel):
    project_name: str
    total_estimated_hours: int
    tasks: List[Task]

# Client setup
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), 
    "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_ad_token_provider=token_provider,
    api_version="2024-10-21"
)

# Main function
def create_project_plan(requirements: str) -> ProjectPlan:
    completion = client.beta.chat.completions.parse(
        model=os.getenv("MODEL_DEPLOYMENT_NAME"),
        messages=[
            {
                "role": "system", 
                "content": "Create a detailed project plan with tasks based on the requirements."
            },
            {
                "role": "user", 
                "content": requirements
            },
        ],
        response_format=ProjectPlan,
    )
    
    return completion.choices[0].message.parsed

# Usage
if __name__ == "__main__":
    requirements = "Build a web application for task management with user authentication"
    plan = create_project_plan(requirements)
    
    print(f"Project: {plan.project_name}")
    print(f"Total Hours: {plan.total_estimated_hours}")
    for task in plan.tasks:
        print(f"- {task.title} ({task.priority}) - {task.estimated_hours}h")
```

---

## Additional Resources

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Pydantic Documentation](https://docs.pydantic.dev/latest/)
- [JSON Schema Specification](https://json-schema.org/docs)
- [OpenAI Python Library](https://github.com/openai/openai-python)

---

*Last Updated: June 2025*
*API Version: 2024-10-21*
