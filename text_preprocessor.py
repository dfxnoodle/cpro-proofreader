#!/usr/bin/env python3
"""
Text preprocessor for protecting specific patterns from AI modification.
Handles Chinese date patterns and other patterns that should be preserved.
"""

import re
import uuid
from typing import Dict, List, Tuple


class TextPreprocessor:
    """
    Preprocessor that protects specific text patterns from AI modification
    by replacing them with unique markers and restoring them after processing.
    """
    
    def __init__(self):
        self.protected_patterns: Dict[str, str] = {}
        self.marker_prefix = "PROTECTED_PATTERN_"
        
        # Define patterns to protect
        self.patterns = {
            # Date patterns
            'chinese_date': re.compile(r'\d{4}年\d{1,2}月\d{1,2}日'),
            'chinese_year': re.compile(r'\d{4}年'),
            'chinese_month_day': re.compile(r'\d{1,2}月\d{1,2}日'),
            
            # Chinese-Arabic number combinations
            'standalone_numbers': re.compile(r'\b\d{2,}\b'),  # Standalone numbers 2+ digits
            'chinese_num_units': re.compile(r'\d+(?:個|位|名|人|次|項|件|份|張|頁|章|節|條|款|段|行|字|億|萬|千|百|十)'),
            'chinese_ordinals': re.compile(r'第\d+(?:個|位|名|次|項|件|份|張|頁|章|節|條|款|段|行|屆|期|年|月|日|號|樓|層)'),
            'chinese_measurements': re.compile(r'\d+(?:米|公尺|厘米|公分|毫米|公釐|公斤|千克|克|噸|升|毫升|度|攝氏度|華氏度)'),
            'chinese_percentages': re.compile(r'\d+(?:\.\d+)?%'),
            'chinese_money': re.compile(r'\d+(?:\.\d+)?(?:元|港元|美元|英鎊|歐元|日圓|人民幣|新台幣)'),
            'chinese_time': re.compile(r'\d{1,2}(?:時|點|分|秒)'),
            'phone_numbers': re.compile(r'\d{4}-?\d{4}|\d{8,11}'),  # Phone patterns
            
            # Academic and reference patterns
            'page_numbers': re.compile(r'(?:第|頁)\s*\d+(?:-\d+)?(?:\s*(?:頁|頁面))?'),
            'chapter_sections': re.compile(r'(?:第|章節|部分)\s*\d+(?:\.\d+)*(?:\s*(?:章|節|部分|條))?'),
            'footnote_refs': re.compile(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+|\d+'),  # Superscript footnotes
            'citation_years': re.compile(r'\(\d{4}[a-z]?\)'),  # Citation years like (2024)
            
            # Technical patterns
            'version_numbers': re.compile(r'v?\d+\.\d+(?:\.\d+)?'),
            'isbn': re.compile(r'ISBN[\s-]*(?:\d{1,5}[\s-]*){4}\d{1,5}'),
            'doi': re.compile(r'(?:doi:|DOI:)\s*10\.\d+\/[^\s]+', re.IGNORECASE),
            'urls': re.compile(r'https?://[^\s]+'),
            'email': re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        }
    
    def protect_text(self, text: str) -> str:
        """
        Replace protected patterns with unique markers.
        
        Args:
            text: Original text
            
        Returns:
            Text with protected patterns replaced by markers
        """
        protected_text = text
        self.protected_patterns.clear()
        
        # Process each pattern type
        for pattern_name, pattern_regex in self.patterns.items():
            matches = pattern_regex.finditer(protected_text)
            
            # Replace each match with a unique marker
            for match in reversed(list(matches)):  # Reverse to preserve positions
                original_text = match.group()
                marker = self._generate_marker()
                
                # Store the mapping
                self.protected_patterns[marker] = original_text
                
                # Replace in text
                start, end = match.span()
                protected_text = protected_text[:start] + marker + protected_text[end:]
                
                print(f"Protected {pattern_name}: '{original_text}' -> {marker}")
        
        return protected_text
    
    def restore_text(self, text: str) -> str:
        """
        Restore protected patterns from markers.
        
        Args:
            text: Text with markers
            
        Returns:
            Text with original patterns restored
        """
        restored_text = text
        
        # Replace all markers with original text
        for marker, original_text in self.protected_patterns.items():
            if marker in restored_text:
                restored_text = restored_text.replace(marker, original_text)
                print(f"Restored: {marker} -> '{original_text}'")
        
        return restored_text
    
    def get_protection_instructions(self) -> str:
        """
        Generate instructions for the AI to not modify protected patterns.
        
        Returns:
            Instruction text to add to AI prompt
        """
        if not self.protected_patterns:
            return ""
        
        instructions = f"""
        
***CRITICAL PROTECTION INSTRUCTIONS:
This text contains {len(self.protected_patterns)} protected patterns marked with {self.marker_prefix}* markers.
DO NOT modify, translate, or change these markers in ANY way.
These markers represent important information like dates, ISBN numbers, DOI references, etc.
Keep ALL markers exactly as they appear in the input text.
Example markers in this text: {list(self.protected_patterns.keys())[:3]}...
"""
        return instructions
    
    def _generate_marker(self) -> str:
        """Generate a unique marker for a protected pattern."""
        return f"{self.marker_prefix}{uuid.uuid4().hex[:8].upper()}"
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about protected patterns.
        
        Returns:
            Dictionary with pattern counts
        """
        stats = {}
        for marker, original in self.protected_patterns.items():
            # Identify pattern type by testing against regex patterns
            for pattern_name, pattern_regex in self.patterns.items():
                if pattern_regex.match(original):
                    stats[pattern_name] = stats.get(pattern_name, 0) + 1
                    break
        
        return stats


class ChineseNumberProtector:
    """
    Comprehensive protector for Chinese-Arabic number combinations.
    Protects dates, standalone numbers, measurements, and other mixed patterns.
    """
    
    def __init__(self):
        # Date patterns
        self.cn_date_pattern = re.compile(r'\d{4}年\d{1,2}月\d{1,2}日')
        self.cn_year_pattern = re.compile(r'\d{4}年')
        self.cn_month_day_pattern = re.compile(r'\d{1,2}月\d{1,2}日')
        
        # Number combination patterns
        self.standalone_numbers = re.compile(r'\b\d{2,}\b')  # 2+ digit standalone numbers
        self.chinese_num_units = re.compile(r'\d+(?:個|位|名|人|次|項|件|份|張|頁|章|節|條|款|段|行|字|億|萬|千|百|十)')
        self.chinese_ordinals = re.compile(r'第\d+(?:個|位|名|次|項|件|份|張|頁|章|節|條|款|段|行|屆|期|年|月|日|號|樓|層)')
        self.chinese_measurements = re.compile(r'\d+(?:\.\d+)?(?:米|公尺|厘米|公分|毫米|公釐|公斤|千克|克|噸|升|毫升|度|攝氏度|華氏度)')
        self.chinese_percentages = re.compile(r'\d+(?:\.\d+)?%')
        self.chinese_money = re.compile(r'\d+(?:\.\d+)?(?:元|港元|美元|英鎊|歐元|日圓|人民幣|新台幣)')
        self.chinese_time = re.compile(r'\d{1,2}(?:時|點|分|秒)')
        self.page_numbers = re.compile(r'(?:第|頁)\s*\d+(?:-\d+)?(?:\s*(?:頁|頁面))?')
        self.footnote_refs = re.compile(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+')
        
        self.protected_patterns: Dict[str, str] = {}
    
    def protect_chinese_numbers(self, text: str) -> Tuple[str, str]:
        """
        Protect Chinese-Arabic number combinations and return protected text with instructions.
        
        Args:
            text: Original text
            
        Returns:
            Tuple of (protected_text, additional_instructions)
        """
        protected_text = text
        self.protected_patterns.clear()
        
        # All patterns to protect (order matters - more specific patterns first)
        patterns_to_protect = [
            ('chinese_date', self.cn_date_pattern),
            ('chinese_measurements', self.chinese_measurements),
            ('chinese_money', self.chinese_money),
            ('chinese_ordinals', self.chinese_ordinals),
            ('chinese_num_units', self.chinese_num_units),
            ('chinese_percentages', self.chinese_percentages),
            ('chinese_time', self.chinese_time),
            ('page_numbers', self.page_numbers),
            ('footnote_refs', self.footnote_refs),
            ('chinese_year', self.cn_year_pattern),
            ('chinese_month_day', self.cn_month_day_pattern),
            ('standalone_numbers', self.standalone_numbers),  # Most general, goes last
        ]
        
        protected_count = 0
        for pattern_name, pattern in patterns_to_protect:
            matches = list(pattern.finditer(protected_text))
            
            # Replace matches with markers (reverse order to preserve positions)
            for match in reversed(matches):
                number_text = match.group()
                
                # Skip if this text is already protected (avoid double protection)
                if 'CHINESE_NUM_' in number_text:
                    continue
                    
                marker = f"CHINESE_NUM_{uuid.uuid4().hex[:6].upper()}"
                
                # Store mapping
                self.protected_patterns[marker] = number_text
                
                # Replace in text
                start, end = match.span()
                protected_text = protected_text[:start] + marker + protected_text[end:]
                protected_count += 1
                
                print(f"Protected {pattern_name}: '{number_text}' -> {marker}")
        
        # Generate instructions if any patterns were protected
        instructions = ""
        if protected_count > 0:
            instructions = f"""
            
***CHINESE NUMBER PROTECTION:
This text contains {protected_count} Chinese-Arabic number combinations that have been marked with CHINESE_NUM_* markers.
DO NOT modify, translate, or convert these markers. They represent numbers that should remain in Arabic numerals (e.g., 140個, 2024年3月15日, 第5章).
NEVER convert Arabic numbers to Chinese characters (e.g., do NOT change 140 to 一百四十).
Keep all CHINESE_NUM_* markers exactly as they appear.
"""
        
        return protected_text, instructions
    
    def restore_chinese_numbers(self, text: str) -> str:
        """
        Restore Chinese-Arabic number combinations from markers.
        
        Args:
            text: Text with markers
            
        Returns:
            Text with original numbers restored
        """
        restored_text = text
        restoration_count = 0
        
        print(f"DEBUG: Starting restoration with {len(self.protected_patterns)} protected patterns")
        
        for marker, original_text in self.protected_patterns.items():
            if marker in restored_text:
                restored_text = restored_text.replace(marker, original_text)
                restoration_count += 1
                print(f"Restored Chinese number: {marker} -> '{original_text}'")
            else:
                print(f"Marker not found in text: {marker} (was: '{original_text}')")
        
        print(f"DEBUG: Restoration complete. Restored {restoration_count} markers out of {len(self.protected_patterns)} patterns")
        
        # Check for any remaining CHINESE_NUM_ markers that weren't restored
        remaining_markers = re.findall(r'CHINESE_NUM_[A-F0-9]{6}', restored_text)
        if remaining_markers:
            print(f"WARNING: Found {len(remaining_markers)} unrestore markers: {remaining_markers}")
        
        return restored_text


# Keep the original ChineseDateProtector for backward compatibility
class ChineseDateProtector(ChineseNumberProtector):
    """
    Specialized protector for Chinese date patterns.
    This extends ChineseNumberProtector for backward compatibility.
    """
    
    def protect_chinese_dates(self, text: str) -> Tuple[str, str]:
        """Backward compatibility method - delegates to protect_chinese_numbers"""
        return self.protect_chinese_numbers(text)
    
    def restore_chinese_dates(self, text: str) -> str:
        """Backward compatibility method - delegates to restore_chinese_numbers"""
        return self.restore_chinese_numbers(text)


def test_chinese_number_protector():
    """Test function for comprehensive Chinese number protection."""
    
    print("🧪 Testing Comprehensive Chinese Number Protection")
    print("=" * 60)
    
    protector = ChineseNumberProtector()
    
    # Test text with various Chinese-Arabic number combinations
    test_text = """
    中大很榮幸獲得大學校董會主席查逸超教授、校長段崇智教授，與大學校董和
    職員、學生、校友、多位立法會議員等約140位大學成員及友好一起出席升旗
    儀式。會議員等約一百四十位大學成員及友好一起出席儀式。
    
    會議於2024年3月15日舉行，預計有300人參加。
    費用為500元，時間是下午3時30分。
    會議室在第5樓第301號房間。
    
    根據第2章第3.1節的規定，請參考第15頁的內容。
    成功率達到95.5%，溫度保持在25度。
    
    註腳參考¹²³和版本v2.1的更新。
    """
    
    print("Original text:")
    print(test_text)
    print("\n" + "="*60)
    
    # Protect numbers
    protected_text, instructions = protector.protect_chinese_numbers(test_text)
    
    print("Protected text:")
    print(protected_text)
    print("\nInstructions:")
    print(instructions)
    print("\n" + "="*60)
    
    # Simulate AI processing that might try to convert numbers
    ai_processed = protected_text
    ai_processed = ai_processed.replace("中大很榮幸", "中文大學很榮幸")
    ai_processed = ai_processed.replace("升旗儀式", "升旗典禮")
    ai_processed = ai_processed.replace("會議室", "會議廳")
    
    print("AI processed text (numbers should remain as markers):")
    print(ai_processed)
    print("\n" + "="*60)
    
    # Restore numbers
    final_text = protector.restore_chinese_numbers(ai_processed)
    
    print("Final restored text:")
    print(final_text)
    
    # Verify key numbers are preserved
    key_numbers = ['140', '300', '500', '2024年3月15日', '第5樓', '95.5%', '25度']
    print(f"\n✅ Verification - Key numbers preserved:")
    for num in key_numbers:
        if num in final_text:
            print(f"   ✓ '{num}' - preserved")
        else:
            print(f"   ✗ '{num}' - missing or changed")


def test_specific_case():
    """Test the specific case mentioned in the user's request"""
    
    print("\n\n🎯 Testing Specific Case: 140 -> 一百四十 conversion")
    print("=" * 60)
    
    protector = ChineseNumberProtector()
    
    # Test the specific problematic text
    problematic_text = "多位立法會議員等約140位大學成員及友好一起出席升旗儀式"
    
    print(f"Original: {problematic_text}")
    
    # Protect
    protected, instructions = protector.protect_chinese_numbers(problematic_text)
    print(f"Protected: {protected}")
    
    # Simulate AI that would normally convert 140 to 一百四十
    # With protection, it should keep the marker intact
    ai_result = protected.replace("升旗儀式", "升旗典禮")  # Normal correction
    print(f"AI processed: {ai_result}")
    
    # Restore
    final = protector.restore_chinese_numbers(ai_result)
    print(f"Final: {final}")
    
    # Verify 140 is preserved
    if "140" in final and "一百四十" not in final:
        print("✅ SUCCESS: 140 preserved in Arabic numerals!")
    else:
        print("❌ FAILED: Number conversion not prevented")


def test_chinese_date_protector():
    """Test function for Chinese date protection."""
    
    # Keep the original test but use the new comprehensive protector
    protector = ChineseNumberProtector()
    
    # Test text with Chinese dates
    test_text = """
    這份報告發表於2024年3月15日，參考了2023年的數據。
    會議將在2024年12月舉行，詳見2024年1月1日的通知。
    根據2022年研究顯示...
    """
    
    print("\n\n📅 Testing Chinese Date Protection (Original Test)")
    print("=" * 60)
    print("Original text:")
    print(test_text)
    print("\n" + "="*50)
    
    # Protect dates
    protected_text, instructions = protector.protect_chinese_numbers(test_text)
    
    print("Protected text:")
    print(protected_text)
    print("\nInstructions:")
    print(instructions)
    print("\n" + "="*50)
    
    # Simulate AI processing (dates should remain as markers)
    ai_processed = protected_text.replace("這份報告", "此報告")
    
    print("AI processed text (with markers intact):")
    print(ai_processed)
    print("\n" + "="*50)
    
    # Restore dates
    final_text = protector.restore_chinese_numbers(ai_processed)
    
    print("Final restored text:")
    print(final_text)


if __name__ == "__main__":
    test_chinese_number_protector()
    test_specific_case()
    test_chinese_date_protector()
