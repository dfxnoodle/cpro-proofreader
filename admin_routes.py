"""
Admin routes for the CUHK Proofreader API
Handles administrative functions like assistant management
Note: Main assistant removed since first pass now uses direct chat completion
"""

import os
import json
from fastapi import APIRouter, HTTPException
from config import (
    client,
    ENGLISH_ASSISTANT_CONFIG_FILE,
    CHINESE_ASSISTANT_CONFIG_FILE
)

# Create admin router
admin_router = APIRouter(prefix="/admin", tags=["admin"])

def get_assistant_globals():
    """Get the current assistant instances from main module (excluding main assistant)"""
    import main
    return main.english_assistant, main.chinese_assistant

def set_assistant_globals(eng_assist=None, chin_assist=None):
    """Set the assistant instances in main module (excluding main assistant)"""
    import main
    if eng_assist is not None:
        main.english_assistant = eng_assist
    if chin_assist is not None:
        main.chinese_assistant = chin_assist

def get_assistant_creators():
    """Get the assistant creation functions from main module (excluding main assistant)"""
    import main
    return (
        main.get_or_create_english_assistant,
        main.get_or_create_chinese_assistant
    )

@admin_router.delete("/reset-assistant")
async def reset_assistant():
    """
    Administrative endpoint to reset language-specific assistants (creates new ones)
    Note: Main assistant not included since first pass now uses direct chat completion
    """
    try:
        # Get assistant creation functions (excluding main assistant)
        get_or_create_english_assistant, get_or_create_chinese_assistant = get_assistant_creators()
        
        # Remove language-specific config files if they exist
        config_files = [ENGLISH_ASSISTANT_CONFIG_FILE, CHINESE_ASSISTANT_CONFIG_FILE]
        for config_file in config_files:
            if os.path.exists(config_file):
                os.remove(config_file)
        
        # Reset language-specific assistant instances in main module
        set_assistant_globals(None, None)
        
        # Create new language-specific assistants (they will be created on next use due to lazy initialization)
        new_english_assistant = get_or_create_english_assistant()
        new_chinese_assistant = get_or_create_chinese_assistant()
        
        return {
            "message": "Language-specific assistants reset successfully (main assistant not needed - first pass uses chat completion)",
            "english_assistant_id": new_english_assistant.id,
            "chinese_assistant_id": new_chinese_assistant.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset assistants: {str(e)}")

@admin_router.delete("/reset-assistant/{assistant_type}")
async def reset_specific_assistant(assistant_type: str):
    """
    Administrative endpoint to reset a specific assistant
    assistant_type: 'english' or 'chinese' (main assistant not available)
    """
    try:
        # Get assistant creation functions
        get_or_create_english_assistant, get_or_create_chinese_assistant = get_assistant_creators()
        
        if assistant_type == "main":
            return {
                "message": "Main assistant no longer available - first pass now uses direct chat completion for better performance",
                "note": "Use 'english' or 'chinese' to reset language-specific assistants"
            }
        elif assistant_type == "english":
            # Remove English config file
            if os.path.exists(ENGLISH_ASSISTANT_CONFIG_FILE):
                os.remove(ENGLISH_ASSISTANT_CONFIG_FILE)
            
            # Reset English assistant
            set_assistant_globals(eng_assist=None)
            new_assistant = get_or_create_english_assistant()
            
            return {
                "message": "English assistant reset successfully",
                "assistant_id": new_assistant.id
            }
        elif assistant_type == "chinese":
            # Remove Chinese config file
            if os.path.exists(CHINESE_ASSISTANT_CONFIG_FILE):
                os.remove(CHINESE_ASSISTANT_CONFIG_FILE)
            
            # Reset Chinese assistant
            set_assistant_globals(chin_assist=None)
            new_assistant = get_or_create_chinese_assistant()
            
            return {
                "message": "Chinese assistant reset successfully",
                "assistant_id": new_assistant.id
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail="Invalid assistant type. Use 'english' or 'chinese' (main assistant no longer available)"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset {assistant_type} assistant: {str(e)}")

@admin_router.get("/assistant-info")
async def get_assistant_info():
    """
    Administrative endpoint to get information about all assistants
    """
    try:
        def get_single_assistant_info(assistant_instance, config_file, assistant_type):
            if assistant_instance:
                return {
                    "id": assistant_instance.id,
                    "name": assistant_instance.name,
                    "model": assistant_instance.model,
                    "status": "active"
                }
            elif os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                        assistant_id = config.get("assistant_id")
                        if assistant_id:
                            # Try to retrieve the assistant
                            assistant = client.beta.assistants.retrieve(assistant_id)
                            return {
                                "id": assistant.id,
                                "name": assistant.name,
                                "model": assistant.model,
                                "status": "available (not loaded)"
                            }
                except:
                    pass
            return {"status": "not created"}
        
        # Get current assistant instances
        english_assistant, chinese_assistant = get_assistant_globals()
        
        return {
            "main_assistant": {
                "status": "removed - first pass now uses direct chat completion for better performance"
            },
            "english_assistant": get_single_assistant_info(
                english_assistant, 
                ENGLISH_ASSISTANT_CONFIG_FILE, 
                "english"
            ),
            "chinese_assistant": get_single_assistant_info(
                chinese_assistant, 
                CHINESE_ASSISTANT_CONFIG_FILE, 
                "chinese"
            )
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get assistant info: {str(e)}")
