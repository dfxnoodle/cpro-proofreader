import os
import json
import time
import tempfile
import re
from typing import Optional
from io import BytesIO
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from openai import AzureOpenAI
from dotenv import load_dotenv
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
from word_revisions import create_word_track_changes_docx
from text_preprocessor import ChineseNumberProtector
import xml.etree.ElementTree as ET

# Load environment variables
load_dotenv()

app = FastAPI(title="Proof Reader API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/styling_guides", StaticFiles(directory="styling_guides"), name="styling_guides")

# Initialize Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview"
)

# Assistant configuration
ASSISTANT_CONFIG_FILE = "assistant_config.json"

def get_or_create_assistant():
    """Get existing assistant or create a new one if it doesn't exist"""
    assistant_id = None
    
    # Try to load existing assistant ID
    if os.path.exists(ASSISTANT_CONFIG_FILE):
        try:
            with open(ASSISTANT_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                assistant_id = config.get("assistant_id")
        except Exception as e:
            print(f"Error loading assistant config: {e}")
    
    # Check if the assistant still exists
    if assistant_id:
        try:
            assistant = client.beta.assistants.retrieve(assistant_id)
            print(f"Using existing assistant: {assistant_id}")
            return assistant
        except Exception as e:
            print(f"Existing assistant {assistant_id} not found, creating new one: {e}")
            assistant_id = None
    
    # Create new assistant if none exists or existing one is invalid
    print("Creating new assistant...")
    model_name = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")
    print(f"Using model: {model_name}")
    assistant = client.beta.assistants.create(
        model=model_name,
        name="Styling_guide",
        instructions="""
        You are CUHK's official style-guide proof-reader.  
        When the user sends a passage of text, do **one job only**: correct its style, spelling, punctuation, and terminology so that it complies with the style guides stored in the vector store (English and Chinese versions).
        
        Return your response as a JSON object that strictly follows the required schema.
        
        ***IMPORTANT Notes:
        1. Always follow the styling guide in the vector store
        2. Do not answer any question except doing proof-reading
        3. For Chinese text, always make sure the output content is in Chinese with traditional Chinese characters without altering the original canonical forms of glyphs
        4. For English text, always use British English spelling and grammar rules
        5. The vector store contains YAML-front-matter chunks with keys `id`, `file`, `section`, `lang`, and `source`.  Always rely on those chunks for authoritative guidance.
        6. Always cite your sources when making corrections. Include specific references directly in each mistake description (e.g., "Changed X to Y. (CUHK English Style Guide, Section 2.1: Grammar Rules)")
        7. Include ALL corrections and issues found, no matter how minor.
        8. Citations should be embedded within each mistake description, not in a separate citations array.
        """,
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": ["vs_GENF8IR41N6uP60Jx9CuLgbs"]}},
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "ProofreadingResponse",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "corrected_text": {
                            "type": "string",
                            "description": "The corrected version of the text"
                        },
                        "mistakes": {
                            "type": "array",
                            "description": "List of mistakes found and how they were corrected with style guide references included (with original quotes)",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "corrected_text",
                        "mistakes",
                    ],
                    "additionalProperties": False
                }
            }
        },
        temperature=0.1,
        top_p=0.5
    )
    
    # Save the assistant ID for future use
    try:
        config = {"assistant_id": assistant.id}
        with open(ASSISTANT_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        print(f"Saved new assistant ID: {assistant.id}")
    except Exception as e:
        print(f"Error saving assistant config: {e}")
    
    return assistant

# Global variable to store the assistant (lazy initialization)
assistant = None

def get_assistant():
    """Get the assistant, creating it if it doesn't exist yet (lazy initialization)"""
    global assistant
    if assistant is None:
        assistant = get_or_create_assistant()
    return assistant

def wait_for_run_completion(client, thread_id, run_id, max_timeout=120):
    """Wait for a run to complete with timeout"""
    timeout_counter = 0
    run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
    
    while run.status in ['queued', 'in_progress', 'cancelling'] and timeout_counter < max_timeout:
        time.sleep(1)
        timeout_counter += 1
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
    
    if timeout_counter >= max_timeout:
        raise HTTPException(status_code=408, detail="Request timeout - AI processing took too long")
    
    return run

class ProofReadRequest(BaseModel):
    text: str

class ProofReadResponse(BaseModel):
    original_text: str
    corrected_text: str
    mistakes: list
    status: str

class ExportToWordRequest(BaseModel):
    original_text: str
    corrected_text: str
    mistakes: list

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page"""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/proofread", response_model=ProofReadResponse)
async def proofread_text(request: ProofReadRequest):
    """
    Proofread the provided text using Azure OpenAI Assistant
    """
    try:
        # Step 1: Protect Chinese numbers and dates (comprehensive protection)
        number_protector = ChineseNumberProtector()
        protected_text, protection_instructions = number_protector.protect_chinese_numbers(request.text)
        
        # Create a thread
        thread = client.beta.threads.create()
        
        # Build message content with protection instructions
        message_content = protected_text + "\n\n###Please proofread the above essay according to the styling guide in the vector store###."
        if protection_instructions:
            message_content += protection_instructions
        
        # Add user message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message_content
        )
        
        # Run the thread
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=get_assistant().id
        )
        
        # Wait for completion with timeout
        run = wait_for_run_completion(client, thread.id, run.id)
        
        if run.status == 'completed':
            # Get the assistant's response
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # Extract the assistant's response
            assistant_response = ""
            for message in messages.data:
                if message.role == "assistant":
                    assistant_response = message.content[0].text.value
                    break
            
            # Debug: Log the raw AI response to understand the format
            print("=== RAW AI RESPONSE (TEXT) ===")
            print(assistant_response)
            print("=== END RAW AI RESPONSE (TEXT) ===")
            
            # Parse the JSON response
            mistakes = []
            corrected_text = request.text  # Default to original if parsing fails
            
            try:
                # Try to parse as JSON first
                response_data = json.loads(assistant_response)
                corrected_text = response_data.get("corrected_text", request.text)
                mistakes = response_data.get("mistakes", [])
                
                # Debug: Log parsed JSON data
                print(f"=== PARSED JSON (TEXT) ===")
                print(f"Corrected text length: {len(corrected_text)}")
                print(f"Number of mistakes: {len(mistakes)}")
                for i, mistake in enumerate(mistakes):
                    print(f"{i+1}: {mistake}")
                print(f"Citations (embedded in mistakes): N/A - now embedded")
                print(f"=== END PARSED JSON (TEXT) ===")
                
            except json.JSONDecodeError:
                print("Failed to parse JSON, falling back to text parsing")
                # Simple fallback: extract any numbered lines as mistakes
                lines = assistant_response.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line[0].isdigit() or '錯誤' in line or '修正' in line or '改為' in line):
                        mistakes.append(line)
                
                # Try to find corrected text in response
                if "corrected text" in assistant_response.lower():
                    # Extract text after any corrected text marker
                    markers = ["corrected text:", "修正後：", "修正版本："]
                    for marker in markers:
                        if marker in assistant_response.lower():
                            start_idx = assistant_response.lower().find(marker) + len(marker)
                            # Take next 500 chars or until double newline
                            remaining = assistant_response[start_idx:start_idx+500]
                            if '\n\n' in remaining:
                                corrected_text = remaining[:remaining.find('\n\n')].strip()
                            else:
                                corrected_text = remaining.strip()
                            break
            
            # Step 2: Restore protected Chinese numbers in the corrected text
            corrected_text = number_protector.restore_chinese_numbers(corrected_text)
            
            # Also restore numbers in mistake descriptions if they contain markers
            restored_mistakes = []
            for mistake in mistakes:
                restored_mistake = number_protector.restore_chinese_numbers(mistake)
                restored_mistakes.append(restored_mistake)
            
            # Show mistakes as they are returned from the AI without filtering
            
            return ProofReadResponse(
                original_text=request.text,
                corrected_text=corrected_text,
                mistakes=restored_mistakes,
                status="completed"
            )
        
        elif run.status == 'requires_action':
            return ProofReadResponse(
                original_text=request.text,
                corrected_text="",
                mistakes=["Assistant requires additional action"],
                status="requires_action"
            )
        
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Assistant run failed with status: {run.status}"
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "proof-reader"}

@app.post("/export-to-word")
async def export_to_word(request: ExportToWordRequest):
    """
    Export corrected text to a Word document with track changes
    """
    try:
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"corrected_document_{timestamp}.docx"
        
        # Create DOCX with track changes
        docx_buffer = create_tracked_changes_docx(
            request.original_text, 
            request.corrected_text, 
            request.mistakes
        )
        
        # Save to temp directory
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'wb') as f:
            f.write(docx_buffer.getvalue())
        
        return {
            "filename": filename,
            "download_url": f"/download-docx/{filename}",
            "message": "Word document created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Word document: {str(e)}")

def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX file with proper spacing preservation"""
    try:
        doc = Document(BytesIO(file_content))
        text_content = []
        
        for paragraph in doc.paragraphs:
            # Simply use paragraph.text which should preserve the original spacing
            # The issue might be elsewhere in the pipeline
            paragraph_text = paragraph.text.strip()
            
            if paragraph_text:
                text_content.append(paragraph_text)
        
        return '\n'.join(text_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading DOCX file: {str(e)}")

def create_tracked_changes_docx(original_text: str, corrected_text: str, mistakes: list) -> BytesIO:
    """Create a DOCX file with proper Word track changes"""
    return create_word_track_changes_docx(original_text, corrected_text, mistakes)

class DocxProofReadResponse(BaseModel):
    original_filename: str
    mistakes_count: int
    mistakes: list
    status: str
    download_filename: str

@app.post("/proofread-docx", response_model=DocxProofReadResponse)
async def proofread_docx(file: UploadFile = File(...)):
    """
    Upload a DOCX file, proofread it, and prepare a corrected version with track changes
    """
    # Validate file type
    if not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only DOCX files are supported")
    
    try:
        # Read the uploaded file
        file_content = await file.read()
        
        # Extract text from DOCX
        extracted_text = extract_text_from_docx(file_content)
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="No text found in the DOCX file")
        
        # Step 1: Protect Chinese numbers and dates (comprehensive protection)
        number_protector = ChineseNumberProtector()
        protected_text, protection_instructions = number_protector.protect_chinese_numbers(extracted_text)
        
        # Create a thread
        thread = client.beta.threads.create()
        
        # Build message content with protection instructions
        message_content = protected_text + "\n\n###Please proofread the above essay according to the styling guide in the vector store###."
        if protection_instructions:
            message_content += protection_instructions
        
        # Add user message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message_content
        )
        
        # Run the thread
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=get_assistant().id
        )
        
        # Wait for completion with timeout
        run = wait_for_run_completion(client, thread.id, run.id)
        
        if run.status == 'completed':
            # Get the assistant's response with citations
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # Extract the assistant's response
            assistant_response = ""
            for message in messages.data:
                if message.role == "assistant":
                    assistant_response = message.content[0].text.value
                    break
            
            # Debug: Log the raw AI response to understand the format
            print("=== RAW AI RESPONSE (DOCX) ===")
            print(assistant_response)
            print("=== END RAW AI RESPONSE (DOCX) ===")
            
            # Parse the response to extract mistakes and corrections
            mistakes = []
            corrected_text = extracted_text  # Default to original if parsing fails
            
            try:
                # Try to parse as JSON first
                response_data = json.loads(assistant_response)
                corrected_text = response_data.get("corrected_text", extracted_text)
                mistakes = response_data.get("mistakes", [])
                
                # Debug: Log parsed JSON data
                print(f"=== PARSED JSON (DOCX) ===")
                print(f"Corrected text length: {len(corrected_text)}")
                print(f"Number of mistakes: {len(mistakes)}")
                for i, mistake in enumerate(mistakes):
                    print(f"{i+1}: {mistake}")
                print(f"=== END PARSED JSON (DOCX) ===")
                
            except json.JSONDecodeError:
                print("Failed to parse JSON, falling back to text parsing")
                # Simple fallback: extract any numbered lines as mistakes
                lines = assistant_response.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line[0].isdigit() or '錯誤' in line or '修正' in line or '改為' in line):
                        mistakes.append(line)
                
                # Try to find corrected text in response
                if "corrected text" in assistant_response.lower():
                    # Extract text after any corrected text marker
                    markers = ["corrected text:", "修正後：", "修正版本："]
                    for marker in markers:
                        if marker in assistant_response.lower():
                            start_idx = assistant_response.lower().find(marker) + len(marker)
                            # Take next 500 chars or until double newline
                            remaining = assistant_response[start_idx:start_idx+500]
                            if '\n\n' in remaining:
                                corrected_text = remaining[:remaining.find('\n\n')].strip()
                            else:
                                corrected_text = remaining.strip()
                            break
            
            # Step 2: Restore protected Chinese numbers in the corrected text
            corrected_text = number_protector.restore_chinese_numbers(corrected_text)
            
            # Also restore numbers in mistake descriptions if they contain markers
            restored_mistakes = []
            for mistake in mistakes:
                restored_mistake = number_protector.restore_chinese_numbers(mistake)
                restored_mistakes.append(restored_mistake)
            
            # Show mistakes as they are returned from the AI without filtering
            
            # Create DOCX with track changes (using original extracted_text as baseline)
            corrected_docx = create_tracked_changes_docx(extracted_text, corrected_text, restored_mistakes)
            
            # Generate filename for the corrected document
            original_name = file.filename.rsplit('.', 1)[0]
            download_filename = f"{original_name}_corrected.docx"
            
            # Save the corrected file temporarily
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, download_filename)
            
            with open(temp_path, 'wb') as f:
                f.write(corrected_docx.getvalue())
            
            return DocxProofReadResponse(
                original_filename=file.filename,
                mistakes_count=len(restored_mistakes),
                mistakes=restored_mistakes,
                status="completed",
                download_filename=download_filename
            )
        
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Assistant run failed with status: {run.status}"
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/style-guides")
async def get_style_guides():
    """
    Get list of available style guide files
    """
    try:
        style_guides_dir = "styling_guides"
        if not os.path.exists(style_guides_dir):
            return {"files": []}
        
        files = []
        for filename in os.listdir(style_guides_dir):
            if filename.endswith(('.pdf', '.doc', '.docx', '.zip', '.md', '.json')):
                # Clean up the display name
                display_name = filename.replace('.pdf', '').replace('.doc', '').replace('.docx', '').replace('.zip', '').replace('.md', '').replace('.json', '')
                display_name = display_name.replace('%20', ' ')  # Handle URL encoding
                
                files.append({
                    "filename": filename,
                    "display_name": display_name,
                    "download_url": f"/styling_guides/{filename}"
                })
        
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-docx/{filename}")
async def download_corrected_docx(filename: str):
    """
    Download the corrected DOCX file
    """
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

@app.delete("/admin/reset-assistant")
async def reset_assistant():
    """
    Administrative endpoint to reset the assistant (creates a new one)
    """
    global assistant
    try:
        # Remove the config file if it exists
        if os.path.exists(ASSISTANT_CONFIG_FILE):
            os.remove(ASSISTANT_CONFIG_FILE)
        
        # Create a new assistant
        assistant = get_or_create_assistant()
        
        return {
            "message": "Assistant reset successfully",
            "new_assistant_id": assistant.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset assistant: {str(e)}")

@app.get("/admin/assistant-info")
async def get_assistant_info():
    """
    Administrative endpoint to get current assistant information
    """
    try:
        current_assistant = assistant  # Check if already loaded
        if current_assistant is None and os.path.exists(ASSISTANT_CONFIG_FILE):
            # Assistant not loaded yet but config exists
            with open(ASSISTANT_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                assistant_id = config.get("assistant_id")
        else:
            assistant_id = current_assistant.id if current_assistant else None
            
        return {
            "assistant_id": assistant_id,
            "assistant_name": current_assistant.name if current_assistant else None,
            "assistant_loaded": current_assistant is not None,
            "config_file_exists": os.path.exists(ASSISTANT_CONFIG_FILE)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get assistant info: {str(e)}")
