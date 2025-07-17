"""
Admin routes for the CUHK Proofreader API
Handles administrative functions like assistant management
"""

import os
import json
from fastapi import APIRouter, HTTPException
from config import (
    client,
    ASSISTANT_CONFIG_FILE,
    ENGLISH_ASSISTANT_CONFIG_FILE,
    CHINESE_ASSISTANT_CONFIG_FILE
)

# Create admin router
admin_router = APIRouter(prefix="/admin", tags=["admin"])

def get_assistant_globals():
    """Get the current assistant instances from main module"""
    import main
    return main.assistant, main.english_assistant, main.chinese_assistant

def set_assistant_globals(main_assist=None, eng_assist=None, chin_assist=None):
    """Set the assistant instances in main module"""
    import main
    if main_assist is not None:
        main.assistant = main_assist
    if eng_assist is not None:
        main.english_assistant = eng_assist
    if chin_assist is not None:
        main.chinese_assistant = chin_assist

def get_assistant_creators():
    """Get the assistant creation functions from main module"""
    import main
    return (
        main.get_or_create_assistant,
        main.get_or_create_english_assistant,
        main.get_or_create_chinese_assistant
    )

@admin_router.delete("/reset-assistant")
async def reset_assistant():
    """
    Administrative endpoint to reset all assistants (creates new ones)
    """
    try:
        # Get assistant creation functions
        get_or_create_assistant, get_or_create_english_assistant, get_or_create_chinese_assistant = get_assistant_creators()
        
        # Remove all config files if they exist
        config_files = [ASSISTANT_CONFIG_FILE, ENGLISH_ASSISTANT_CONFIG_FILE, CHINESE_ASSISTANT_CONFIG_FILE]
        for config_file in config_files:
            if os.path.exists(config_file):
                os.remove(config_file)
        
        # Reset all assistant instances in main module
        set_assistant_globals(None, None, None)
        
        # Create new assistants (they will be created on next use due to lazy initialization)
        new_assistant = get_or_create_assistant()
        new_english_assistant = get_or_create_english_assistant()
        new_chinese_assistant = get_or_create_chinese_assistant()
        
        return {
            "message": "All assistants reset successfully",
            "main_assistant_id": new_assistant.id,
            "english_assistant_id": new_english_assistant.id,
            "chinese_assistant_id": new_chinese_assistant.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset assistants: {str(e)}")

@admin_router.delete("/reset-assistant/{assistant_type}")
async def reset_specific_assistant(assistant_type: str):
    """
    Administrative endpoint to reset a specific assistant
    assistant_type: 'main', 'english', or 'chinese'
    """
    try:
        # Get assistant creation functions
        get_or_create_assistant, get_or_create_english_assistant, get_or_create_chinese_assistant = get_assistant_creators()
        
        if assistant_type == 'main':
            if os.path.exists(ASSISTANT_CONFIG_FILE):
                os.remove(ASSISTANT_CONFIG_FILE)
            set_assistant_globals(main_assist=None)
            new_assistant = get_or_create_assistant()
            return {
                "message": "Main assistant reset successfully",
                "assistant_id": new_assistant.id,
                "assistant_type": "main"
            }
        elif assistant_type == 'english':
            if os.path.exists(ENGLISH_ASSISTANT_CONFIG_FILE):
                os.remove(ENGLISH_ASSISTANT_CONFIG_FILE)
            set_assistant_globals(eng_assist=None)
            new_assistant = get_or_create_english_assistant()
            return {
                "message": "English assistant reset successfully",
                "assistant_id": new_assistant.id,
                "assistant_type": "english"
            }
        elif assistant_type == 'chinese':
            if os.path.exists(CHINESE_ASSISTANT_CONFIG_FILE):
                os.remove(CHINESE_ASSISTANT_CONFIG_FILE)
            set_assistant_globals(chin_assist=None)
            new_assistant = get_or_create_chinese_assistant()
            return {
                "message": "Chinese assistant reset successfully",
                "assistant_id": new_assistant.id,
                "assistant_type": "chinese"
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid assistant_type. Use 'main', 'english', or 'chinese'")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset {assistant_type} assistant: {str(e)}")

@admin_router.get("/assistant-info")
async def get_assistant_info():
    """
    Administrative endpoint to get current assistant information for all assistants
    """
    try:
        # Get current assistant instances
        assistant, english_assistant, chinese_assistant = get_assistant_globals()
        
        # Helper function to get assistant info
        def get_single_assistant_info(assistant_instance, config_file, assistant_type):
            if assistant_instance is None and os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    assistant_id = config.get("assistant_id")
            else:
                assistant_id = assistant_instance.id if assistant_instance else None
            
            return {
                "assistant_id": assistant_id,
                "assistant_name": assistant_instance.name if assistant_instance else None,
                "assistant_loaded": assistant_instance is not None,
                "config_file_exists": os.path.exists(config_file),
                "assistant_type": assistant_type
            }
        
        # Get info for all assistants
        main_info = get_single_assistant_info(assistant, ASSISTANT_CONFIG_FILE, "main")
        english_info = get_single_assistant_info(english_assistant, ENGLISH_ASSISTANT_CONFIG_FILE, "english")
        chinese_info = get_single_assistant_info(chinese_assistant, CHINESE_ASSISTANT_CONFIG_FILE, "chinese")
            
        return {
            "main_assistant": main_info,
            "english_assistant": english_info,
            "chinese_assistant": chinese_info,
            "two_stage_system": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get assistant info: {str(e)}")
