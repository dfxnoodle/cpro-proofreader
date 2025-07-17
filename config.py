"""
Shared constants and configurations for the CUHK Proofreader API
"""

import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Assistant configuration files
ASSISTANT_CONFIG_FILE = "assistant_config.json"
ENGLISH_ASSISTANT_CONFIG_FILE = "english_assistant_config.json"
CHINESE_ASSISTANT_CONFIG_FILE = "chinese_assistant_config.json"

# Initialize Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview"
)
