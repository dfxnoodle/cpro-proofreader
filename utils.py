"""
Utility functions for the CUHK Proofreader API
Handles common operations like JSON parsing with robust error handling
"""

import json
import re
from typing import Tuple, List, Dict, Any

def clean_marker_references_from_mistakes(mistakes: List[str], number_protector) -> List[str]:
    """
    Clean up Chinese number protection marker references from mistakes array
    
    Args:
        mistakes: List of mistake descriptions
        number_protector: ChineseNumberProtector instance with protected patterns
    
    Returns:
        Cleaned list of mistakes with marker references removed or replaced
    """
    cleaned_mistakes = []
    
    for mistake in mistakes:
        cleaned_mistake = mistake
        
        # Replace marker references with actual values
        for marker, original_value in number_protector.protected_patterns.items():
            if marker in cleaned_mistake:
                # Replace marker references in the mistake description
                cleaned_mistake = cleaned_mistake.replace(f"標記 {marker}", f"原文中的數字 '{original_value}'")
                cleaned_mistake = cleaned_mistake.replace(f"Marker {marker}", f"Original number '{original_value}'")
                cleaned_mistake = cleaned_mistake.replace(marker, original_value)
        
        # Only include the mistake if it's not just about marker replacement
        if not ("標記" in mistake and "應替換為" in mistake and any(marker in mistake for marker in number_protector.protected_patterns.keys())):
            cleaned_mistakes.append(cleaned_mistake)
        else:
            # If it's just a marker replacement note, convert it to a meaningful correction
            if "CHINESE_NUM_" in mistake:
                # Extract the original and corrected values for a better description
                for marker, original_value in number_protector.protected_patterns.items():
                    if marker in mistake:
                        # Create a more meaningful mistake description
                        meaningful_mistake = f"數字格式已根據CUHK編輯指引進行調整：原文的數字表達已按照規範修正"
                        cleaned_mistakes.append(meaningful_mistake)
                        break
    
    return cleaned_mistakes

def parse_assistant_response(response_text: str, default_text: str = "") -> Tuple[str, List[str]]:
    """
    Robustly parse assistant response with multiple fallback strategies
    
    Args:
        response_text: The raw response from the AI assistant
        default_text: Default text to return if parsing fails completely
    
    Returns:
        Tuple of (corrected_text, mistakes_list)
    """
    
    # Try to parse as pure JSON
    try:
        response_data = json.loads(response_text.strip())
        corrected_text = response_data.get("corrected_text", default_text)
        mistakes = response_data.get("mistakes", [])
        print("✓ Successfully parsed response as pure JSON")
        return corrected_text, mistakes
    except json.JSONDecodeError:
        print("⚠ Pure JSON parsing failed, trying fallback strategies...")
    
    # Text parsing fallback
    print("🔄 JSON parsing failed, using text parsing fallback")
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
