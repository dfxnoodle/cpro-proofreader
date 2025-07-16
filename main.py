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
    """Extract text from DOCX file with proper spacing preservation, including tables"""
    try:
        doc = Document(BytesIO(file_content))
        text_content = []
        
        # Process document elements in order (paragraphs and tables)
        for element in doc.element.body:
            if element.tag.endswith('}p'):  # Paragraph
                # Find corresponding paragraph object
                for para in doc.paragraphs:
                    if para._element == element:
                        paragraph_text = para.text.strip()
                        if paragraph_text:
                            text_content.append(paragraph_text)
                        break
            
            elif element.tag.endswith('}tbl'):  # Table
                # Find corresponding table object
                for table in doc.tables:
                    if table._element == element:
                        table_text = extract_table_text(table)
                        if table_text:
                            text_content.append(table_text)
                        break
        
        return '\n'.join(text_content)
    except Exception as e:
        # Fallback to simple paragraph extraction if the advanced method fails
        try:
            doc = Document(BytesIO(file_content))
            text_content = []
            
            # Extract paragraphs
            for paragraph in doc.paragraphs:
                paragraph_text = paragraph.text.strip()
                if paragraph_text:
                    text_content.append(paragraph_text)
            
            # Extract tables
            for table in doc.tables:
                table_text = extract_table_text(table)
                if table_text:
                    text_content.append(table_text)
            
            return '\n'.join(text_content)
        except Exception as fallback_e:
            raise HTTPException(status_code=400, detail=f"Error reading DOCX file: {str(e)}. Fallback error: {str(fallback_e)}")

def extract_table_text(table) -> str:
    """Extract text from a DOCX table with proper formatting"""
    try:
        table_content = []
        
        for row in table.rows:
            row_content = []
            for cell in row.cells:
                # Extract text from all paragraphs in the cell
                cell_paragraphs = []
                for paragraph in cell.paragraphs:
                    para_text = paragraph.text.strip()
                    if para_text:
                        cell_paragraphs.append(para_text)
                
                # Join paragraphs within a cell with space
                cell_text = ' '.join(cell_paragraphs) if cell_paragraphs else ""
                row_content.append(cell_text)
            
            # Join cells in a row with tab character for better structure
            if any(cell.strip() for cell in row_content):  # Only add non-empty rows
                table_content.append('\t'.join(row_content))
        
        # Join rows with newlines
        return '\n'.join(table_content)
    except Exception as e:
        # If table extraction fails, return empty string to avoid breaking the whole process
        print(f"Warning: Failed to extract table text: {str(e)}")
        return ""

def create_tracked_changes_docx(original_text: str, corrected_text: str, mistakes: list) -> BytesIO:
    """Create a DOCX file with proper Word track changes"""
    try:
        return create_word_track_changes_docx(original_text, corrected_text, mistakes)
    except Exception as e:
        # If the advanced track changes fail, create a simple document with corrections
        print(f"Warning: Advanced track changes failed, creating simple document: {str(e)}")
        return create_simple_corrections_docx(original_text, corrected_text, mistakes)

def create_simple_corrections_docx(original_text: str, corrected_text: str, mistakes: list) -> BytesIO:
    """Create a simple DOCX file with corrections when track changes fail"""
    try:
        doc = Document()
        
        # Add title
        title = doc.add_heading("Document Corrections", level=1)
        
        # Add original text section
        doc.add_heading("Original Text:", level=2)
        original_para = doc.add_paragraph(original_text)
        
        # Add corrected text section
        doc.add_heading("Corrected Text:", level=2)
        corrected_para = doc.add_paragraph(corrected_text)
        # Highlight corrected text in green
        for run in corrected_para.runs:
            run.font.color.rgb = RGBColor(0, 128, 0)  # Green color
        
        # Add mistakes section
        if mistakes:
            doc.add_heading("Corrections Made:", level=2)
            for i, mistake in enumerate(mistakes, 1):
                mistake_para = doc.add_paragraph(f"{i}. {mistake}")
        
        # Save to BytesIO
        doc_bytes = BytesIO()
        doc.save(doc_bytes)
        doc_bytes.seek(0)
        
        return doc_bytes
    except Exception as e:
        # Last resort: create minimal document
        print(f"Warning: Simple document creation failed, creating minimal document: {str(e)}")
        return create_minimal_docx(original_text, corrected_text, mistakes)

def create_minimal_docx(original_text: str, corrected_text: str, mistakes: list) -> BytesIO:
    """Create a minimal DOCX file as last resort"""
    try:
        doc = Document()
        doc.add_paragraph("Document Corrections")
        doc.add_paragraph("Original Text:")
        doc.add_paragraph(original_text)
        doc.add_paragraph("Corrected Text:")
        doc.add_paragraph(corrected_text)
        
        if mistakes:
            doc.add_paragraph("Corrections:")
            for mistake in mistakes:
                doc.add_paragraph(f"• {mistake}")
        
        doc_bytes = BytesIO()
        doc.save(doc_bytes)
        doc_bytes.seek(0)
        
        return doc_bytes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create any document format: {str(e)}")

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
        
        # Validate file size (limit to 50MB)
        if len(file_content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")
        
        # Validate that the file is actually a valid DOCX
        if not file_content.startswith(b'PK'):
            raise HTTPException(status_code=400, detail="Invalid DOCX file format.")
        
        # Extract text from DOCX with improved error handling
        try:
            extracted_text = extract_text_from_docx(file_content)
        except HTTPException:
            # Re-raise HTTP exceptions as they already have proper error messages
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to extract text from DOCX file. The file may be corrupted or contain unsupported elements: {str(e)}"
            )
        
        if not extracted_text.strip():
            raise HTTPException(
                status_code=400, 
                detail="No text found in the DOCX file. The document may be empty or contain only images/objects."
            )
        
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
            try:
                corrected_docx = create_tracked_changes_docx(extracted_text, corrected_text, restored_mistakes)
            except Exception as e:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to create corrected document. Error: {str(e)}"
                )
            
            # Generate filename for the corrected document
            original_name = file.filename.rsplit('.', 1)[0]
            download_filename = f"{original_name}_corrected.docx"
            
            # Save the corrected file temporarily
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, download_filename)
            
            try:
                with open(temp_path, 'wb') as f:
                    f.write(corrected_docx.getvalue())
            except Exception as e:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to save corrected document: {str(e)}"
                )
            
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
