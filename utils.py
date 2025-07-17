"""
Utility functions for the CUHK Proofreader API
Handles common operations like JSON parsing with robust error handling
"""

import json
import re
from typing import Tuple, List, Dict, Any

def parse_assistant_response(response_text: str, default_text: str = "") -> Tuple[str, List[str]]:
    """
    Robustly parse assistant response with multiple fallback strategies
    
    Args:
        response_text: The raw response from the AI assistant
        default_text: Default text to return if parsing fails completely
    
    Returns:
        Tuple of (corrected_text, mistakes_list)
    """
    
    # Strategy 1: Try to parse as pure JSON
    try:
        response_data = json.loads(response_text.strip())
        corrected_text = response_data.get("corrected_text", default_text)
        mistakes = response_data.get("mistakes", [])
        print("✓ Successfully parsed response as pure JSON")
        return corrected_text, mistakes
    except json.JSONDecodeError:
        print("⚠ Pure JSON parsing failed, trying fallback strategies...")
    
    # Strategy 2: Try to extract JSON from markdown code blocks
    try:
        # Look for JSON in ```json blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        json_match = re.search(json_pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        if json_match:
            json_content = json_match.group(1)
            response_data = json.loads(json_content)
            corrected_text = response_data.get("corrected_text", default_text)
            mistakes = response_data.get("mistakes", [])
            print("✓ Successfully extracted JSON from markdown code block")
            return corrected_text, mistakes
    except (json.JSONDecodeError, AttributeError):
        print("⚠ Markdown JSON extraction failed")
    
    # Strategy 3: Try to find JSON object in the text (even if embedded)
    try:
        # Look for first { and last } to extract potential JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_content = response_text[start_idx:end_idx + 1]
            response_data = json.loads(json_content)
            corrected_text = response_data.get("corrected_text", default_text)
            mistakes = response_data.get("mistakes", [])
            print("✓ Successfully extracted embedded JSON object")
            return corrected_text, mistakes
    except json.JSONDecodeError:
        print("⚠ Embedded JSON extraction failed")
    
    # Strategy 4: Text parsing fallback
    print("🔄 All JSON strategies failed, using text parsing fallback")
    return parse_text_response(response_text, default_text)

def parse_text_response(response_text: str, default_text: str = "") -> Tuple[str, List[str]]:
    """
    Parse assistant response as plain text when JSON parsing fails
    
    Args:
        response_text: The raw response text
        default_text: Default text to return if no corrected text found
    
    Returns:
        Tuple of (corrected_text, mistakes_list)
    """
    
    mistakes = []
    corrected_text = default_text
    
    lines = response_text.split('\n')
    
    # Look for numbered mistakes or corrections
    for line in lines:
        line = line.strip()
        if line and (
            line[0].isdigit() or 
            '錯誤' in line or 
            '修正' in line or 
            '改為' in line or 
            'changed' in line.lower() or
            'corrected' in line.lower() or
            'mistake' in line.lower()
        ):
            mistakes.append(line)
    
    # Try to find corrected text using various markers
    corrected_text_markers = [
        "corrected text:",
        "修正後：",
        "修正版本：",
        "final text:",
        "corrected version:",
        "revised text:"
    ]
    
    for marker in corrected_text_markers:
        marker_idx = response_text.lower().find(marker.lower())
        if marker_idx != -1:
            # Get text after the marker
            start_idx = marker_idx + len(marker)
            remaining_text = response_text[start_idx:].strip()
            
            # Look for natural break points
            break_patterns = ['\n\n', '\n---', '\nMistakes:', '\n錯誤', '\n\n#']
            
            for pattern in break_patterns:
                break_idx = remaining_text.find(pattern)
                if break_idx != -1:
                    corrected_text = remaining_text[:break_idx].strip()
                    break
            else:
                # No break found, take reasonable amount of text
                corrected_text = remaining_text[:1000].strip()
            
            if corrected_text:
                print(f"✓ Found corrected text using marker: {marker}")
                break
    
    # If no corrected text found, try to use the original
    if not corrected_text:
        corrected_text = default_text
        print("⚠ No corrected text found in response, using default")
    
    return corrected_text, mistakes

def clean_response_text(response_text: str) -> str:
    """
    Clean up response text by removing common formatting issues
    
    Args:
        response_text: Raw response text
    
    Returns:
        Cleaned response text
    """
    
    # Remove leading/trailing whitespace
    cleaned = response_text.strip()
    
    # Remove any BOM or special characters at the beginning
    if cleaned.startswith('\ufeff'):
        cleaned = cleaned[1:]
    
    # Remove any markdown formatting that might interfere
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```\s*$', '', cleaned, flags=re.MULTILINE)
    
    return cleaned

def validate_json_structure(data: Dict[str, Any]) -> bool:
    """
    Validate that the parsed JSON has the expected structure
    
    Args:
        data: Parsed JSON data
    
    Returns:
        True if structure is valid, False otherwise
    """
    
    required_fields = ["corrected_text", "mistakes"]
    
    for field in required_fields:
        if field not in data:
            print(f"⚠ Missing required field: {field}")
            return False
    
    # Check types
    if not isinstance(data.get("corrected_text"), str):
        print("⚠ corrected_text is not a string")
        return False
    
    if not isinstance(data.get("mistakes"), list):
        print("⚠ mistakes is not a list")
        return False
    
    return True
