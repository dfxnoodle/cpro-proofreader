import os
import json
import time
import tempfile
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
        
        CORRECTED TEXT:
        [The corrected version of the text]
        
        MISTAKES:
        [List each mistake on a separate line, describing what was wrong and how it was corrected]
        
        ***IMPORTANT Notes:
        1. Always follow the styling guide in the vector store
        2. Do not answer any question except doing proof-reading
        3. For Chinese text, always make sure the output content is in Chinese with traditional Chinese characters
        4. For English text, always use British English spelling and grammar rules
        5. The vector store contains YAML-front-matter chunks with keys `id`, `file`, `section`, `lang`, and `source`.  Always rely on those chunks for authoritative guidance.
        6. Always cite your sources when making corrections. Include specific references to the style guide sections that support your corrections.
        """,
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": ["vs_GENF8IR41N6uP60Jx9CuLgbs"]}},
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

def extract_citations_from_message(client, message):
    """Extract citations from a message"""
    citations = []
    try:
        if hasattr(message.content[0].text, 'annotations') and message.content[0].text.annotations:
            annotations = message.content[0].text.annotations
            for index, annotation in enumerate(annotations):
                # Use the recommended approach from OpenAI docs
                if file_citation := getattr(annotation, "file_citation", None):
                    try:
                        cited_file = client.files.retrieve(file_citation.file_id)
                        citation_data = {
                            'text': annotation.text if hasattr(annotation, 'text') else '',
                            'file_name': cited_file.filename if cited_file else '',
                            'index': index
                        }
                        citations.append(citation_data)
                    except Exception as e:
                        # Add citation without file details if retrieval fails
                        citation_data = {
                            'text': annotation.text if hasattr(annotation, 'text') else '',
                            'file_name': 'Unknown file',
                            'index': index
                        }
                        citations.append(citation_data)
    except Exception as e:
        # Log error but don't crash
        pass
    
    return citations

def clean_gpt41_mistakes(mistakes_list: list) -> list:
    """
    Clean and filter the mistakes list for GPT-4.1 response format
    GPT-4.1 includes meta-comments and source references that should be filtered
    """
    cleaned_mistakes = []
    
    for mistake in mistakes_list:
        if not mistake or not mistake.strip():
            continue
            
        mistake_lower = mistake.lower().strip()
        
        # Skip meta-instructions that aren't actual mistakes
        if any(skip_phrase in mistake_lower for skip_phrase in [
            'please proofread', 'according to the styling guide', 
            'the instruction to proofread', 'was disregarded',
            'the sentence was not an essay', 'no other spelling',
            'no mistakes were found', 'complies with the style'
        ]):
            continue
        
        # Skip standalone "Sources:" headers but keep actual source references that contain corrections
        if mistake.strip() in ['Sources:', '【參考來源】', 'Reference:', 'Citation:']:
            continue
            
        # Keep actual corrections and meaningful references
        if any(keyword in mistake_lower for keyword in [
            'corrected to', 'changed to', 'was incorrect', 'spelling error',
            'grammar', 'punctuation', 'subject-verb agreement', 'possessive',
            '更正為', '修正為', '語法', '拼字', '標點', 'style guide',
            'reference:', '【參考來源：', 'section:'
        ]):
            cleaned_mistakes.append(mistake.strip())
        elif mistake.strip().startswith(('-', '•', '1.', '2.', '3.', '4.', '5.')):
            # Include numbered or bulleted corrections if they contain meaningful content
            if any(keyword in mistake_lower for keyword in [
                'corrected', 'changed', 'error', '錯誤', '修正', '調整'
            ]):
                cleaned_mistakes.append(mistake.strip())
    
    return cleaned_mistakes

class ProofReadRequest(BaseModel):
    text: str

class ProofReadResponse(BaseModel):
    original_text: str
    corrected_text: str
    mistakes: list
    citations: list
    status: str

class ExportToWordRequest(BaseModel):
    original_text: str
    corrected_text: str
    mistakes: list
    citations: list = []

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
        # Create a thread
        thread = client.beta.threads.create()
        
        # Add user message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=request.text + "\n\n###Please proofread the above essay according to the styling guide in the vector store###."
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
            
            # Extract the assistant's response and citations
            assistant_response = ""
            citations = []
            for message in messages.data:
                if message.role == "assistant":
                    assistant_response = message.content[0].text.value
                    citations = extract_citations_from_message(client, message)
                    break
            
            # Parse the response to extract mistakes and corrections
            mistakes = []
            corrected_text = request.text  # Default to original if no corrections found
            
            # Parse the structured response
            if "CORRECTED TEXT:" in assistant_response and "MISTAKES:" in assistant_response:
                # Split the response into sections
                sections = assistant_response.split("MISTAKES:")
                if len(sections) >= 2:
                    # Extract corrected text
                    corrected_section = sections[0].replace("CORRECTED TEXT:", "").strip()
                    corrected_text = corrected_section
                    
                    # Extract mistakes
                    mistakes_section = sections[1].strip()
                    if mistakes_section:
                        # Split mistakes by lines and filter out empty lines
                        mistake_lines = [line.strip() for line in mistakes_section.split('\n') if line.strip()]
                        mistakes = mistake_lines
            else:
                # Enhanced fallback parsing for different response formats
                # Try to extract corrected text even if format is different
                if "CORRECTED TEXT:" in assistant_response:
                    # Extract text after "CORRECTED TEXT:" marker
                    corrected_start = assistant_response.find("CORRECTED TEXT:") + len("CORRECTED TEXT:")
                    # Find the end (either at MISTAKES: or end of response)
                    mistakes_start = assistant_response.find("MISTAKES:")
                    if mistakes_start != -1:
                        corrected_text = assistant_response[corrected_start:mistakes_start].strip()
                    else:
                        corrected_text = assistant_response[corrected_start:].strip()
                elif "corrected text is:" in assistant_response.lower():
                    # Handle format like "The corrected text is: [text]"
                    start_idx = assistant_response.lower().find("corrected text is:") + len("corrected text is:")
                    # Extract until end of first sentence or paragraph
                    remaining = assistant_response[start_idx:].strip()
                    # Find the end of the corrected text (before any explanation)
                    end_markers = [". The main", ". The issues", "\n\nThe", "\n\nMain"]
                    end_idx = len(remaining)
                    for marker in end_markers:
                        marker_idx = remaining.find(marker)
                        if marker_idx != -1:
                            end_idx = min(end_idx, marker_idx + 1)  # Include the period
                    corrected_text = remaining[:end_idx].strip()
                elif "corrected version:" in assistant_response.lower():
                    # Handle format like "Here is the corrected version:"
                    start_idx = assistant_response.lower().find("corrected version:") + len("corrected version:")
                    remaining = assistant_response[start_idx:].strip()
                    # Look for the text in the next few lines
                    lines = remaining.split('\n')
                    corrected_lines = []
                    for line in lines:
                        line = line.strip()
                        if line and not any(marker in line.lower() for marker in ['main corrections', 'corrections made', 'issues', 'mistakes']):
                            corrected_lines.append(line)
                        elif corrected_lines:  # Stop when we hit explanation text
                            break
                    if corrected_lines:
                        corrected_text = ' '.join(corrected_lines)
                
                # Extract mistakes with more flexible parsing
                response_lines = assistant_response.split('\n')
                for line in response_lines:
                    line_lower = line.lower().strip()
                    if any(keyword in line_lower for keyword in ['mistake', 'error', 'issue', 'problem', 'correction', 'fixed']):
                        if line.strip() and not line.strip().startswith('MISTAKES:'):
                            mistakes.append(line.strip())
            
            # Clean up mistakes for GPT-4.1 format (remove meta-comments and standalone sources)
            mistakes = clean_gpt41_mistakes(mistakes)
            
            return ProofReadResponse(
                original_text=request.text,
                corrected_text=corrected_text,
                mistakes=mistakes,
                citations=citations,
                status="completed"
            )
        
        elif run.status == 'requires_action':
            return ProofReadResponse(
                original_text=request.text,
                corrected_text="",
                mistakes=["Assistant requires additional action"],
                citations=[],
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
            request.mistakes,
            request.citations
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

def create_tracked_changes_docx(original_text: str, corrected_text: str, mistakes: list, citations: list = None) -> BytesIO:
    """Create a DOCX file with proper Word track changes"""
    return create_word_track_changes_docx(original_text, corrected_text, mistakes, citations)

class DocxProofReadResponse(BaseModel):
    original_filename: str
    mistakes_count: int
    mistakes: list
    citations: list
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
        
        # Create a thread
        thread = client.beta.threads.create()
        
        # Add user message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=extracted_text + "\n\n###Please proofread the above essay according to the styling guide in the vector store###."
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
            
            # Extract the assistant's response and citations
            assistant_response = ""
            citations = []
            for message in messages.data:
                if message.role == "assistant":
                    assistant_response = message.content[0].text.value
                    citations = extract_citations_from_message(client, message)
                    break
            
            # Parse the response to extract mistakes and corrections
            mistakes = []
            corrected_text = extracted_text  # Default to original if no corrections found
            
            # Parse the structured response
            if "CORRECTED TEXT:" in assistant_response and "MISTAKES:" in assistant_response:
                # Split the response into sections
                sections = assistant_response.split("MISTAKES:")
                if len(sections) >= 2:
                    # Extract corrected text
                    corrected_section = sections[0].replace("CORRECTED TEXT:", "").strip()
                    corrected_text = corrected_section
                    
                    # Extract mistakes
                    mistakes_section = sections[1].strip()
                    if mistakes_section:
                        # Split mistakes by lines and filter out empty lines
                        mistake_lines = [line.strip() for line in mistakes_section.split('\n') if line.strip()]
                        mistakes = mistake_lines
            else:
                # Enhanced fallback parsing for different response formats
                # Try to extract corrected text even if format is different
                if "CORRECTED TEXT:" in assistant_response:
                    # Extract text after "CORRECTED TEXT:" marker
                    corrected_start = assistant_response.find("CORRECTED TEXT:") + len("CORRECTED TEXT:")
                    # Find the end (either at MISTAKES: or end of response)
                    mistakes_start = assistant_response.find("MISTAKES:")
                    if mistakes_start != -1:
                        corrected_text = assistant_response[corrected_start:mistakes_start].strip()
                    else:
                        corrected_text = assistant_response[corrected_start:].strip()
                elif "corrected text is:" in assistant_response.lower():
                    # Handle format like "The corrected text is: [text]"
                    start_idx = assistant_response.lower().find("corrected text is:") + len("corrected text is:")
                    # Extract until end of first sentence or paragraph
                    remaining = assistant_response[start_idx:].strip()
                    # Find the end of the corrected text (before any explanation)
                    end_markers = [". The main", ". The issues", "\n\nThe", "\n\nMain"]
                    end_idx = len(remaining)
                    for marker in end_markers:
                        marker_idx = remaining.find(marker)
                        if marker_idx != -1:
                            end_idx = min(end_idx, marker_idx + 1)  # Include the period
                    corrected_text = remaining[:end_idx].strip()
                elif "corrected version:" in assistant_response.lower():
                    # Handle format like "Here is the corrected version:"
                    start_idx = assistant_response.lower().find("corrected version:") + len("corrected version:")
                    remaining = assistant_response[start_idx:].strip()
                    # Look for the text in the next few lines
                    lines = remaining.split('\n')
                    corrected_lines = []
                    for line in lines:
                        line = line.strip()
                        if line and not any(marker in line.lower() for marker in ['main corrections', 'corrections made', 'issues', 'mistakes']):
                            corrected_lines.append(line)
                        elif corrected_lines:  # Stop when we hit explanation text
                            break
                    if corrected_lines:
                        corrected_text = ' '.join(corrected_lines)
                
                # Extract mistakes with more flexible parsing
                response_lines = assistant_response.split('\n')
                for line in response_lines:
                    line_lower = line.lower().strip()
                    if any(keyword in line_lower for keyword in ['mistake', 'error', 'issue', 'problem', 'correction', 'fixed']):
                        if line.strip() and not line.strip().startswith('MISTAKES:'):
                            mistakes.append(line.strip())
            
            # Clean mistakes for GPT-4.1 format
            cleaned_mistakes = clean_gpt41_mistakes(mistakes)
            
            # Create DOCX with track changes
            corrected_docx = create_tracked_changes_docx(extracted_text, corrected_text, cleaned_mistakes, citations)
            
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
                mistakes_count=len(cleaned_mistakes),
                mistakes=cleaned_mistakes,
                citations=citations,
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
            if filename.endswith(('.pdf', '.doc', '.docx', '.zip', '.md')):
                # Clean up the display name
                display_name = filename.replace('.pdf', '').replace('.doc', '').replace('.docx', '').replace('.zip', '').replace('.md', '')
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
