#!/usr/bin/env python3
"""
Demo script showing the Chinese number protection in action.
Shows how the system prevents AI from converting Arabic numerals to Chinese characters.
"""

from text_preprocessor import ChineseNumberProtector

def demo_protection():
    """Demonstrate the protection system with clear before/after examples"""
    
    print("🛡️  Chinese Number Protection Demo")
    print("=" * 60)
    print()
    
    # Initialize protector
    protector = ChineseNumberProtector()
    
    # Example problematic text
    demo_text = """
中大很榮幸獲得大學校董會主席查逸超教授、校長段崇智教授，與大學校董和
職員、學生、校友、多位立法會議員等約140位大學成員及友好一起出席升旗
儀式。會議於2024年3月15日下午3時30分舉行，預計有300人參加。
費用為500元，成功率達到95.5%，會議室在第5樓。
"""
    
    print("📄 ORIGINAL TEXT:")
    print(demo_text)
    
    print("\n❌ PROBLEM (Without Protection):")
    print("   AI might convert: 140 → 一百四十")
    print("   AI might convert: 300 → 三百")
    print("   AI might convert: 500 → 五百")
    print("   AI might convert: 2024 → 二零二四")
    print("   This causes incorrect Chinese formatting!")
    
    print("\n🛡️  SOLUTION (With Protection):")
    
    # Step 1: Protect
    protected_text, instructions = protector.protect_chinese_numbers(demo_text)
    print("   Step 1: Replace numbers with protective markers")
    print(f"   → 140位 becomes CHINESE_NUM_XXXXXX")
    print(f"   → 2024年3月15日 becomes CHINESE_NUM_YYYYYY")
    print(f"   → {len(protector.protected_patterns)} patterns protected")
    
    # Step 2: Send to AI (simulated)
    print("\n   Step 2: Send protected text to AI with instructions")
    print("   → AI sees markers instead of numbers")
    print("   → AI cannot convert what it cannot see")
    
    # Step 3: AI processes (simulated)
    ai_result = protected_text.replace("很榮幸", "深感榮幸")
    ai_result = ai_result.replace("升旗儀式", "升旗典禮")
    
    print("\n   Step 3: AI makes normal corrections but preserves markers")
    print("   → Style corrections: 很榮幸 → 深感榮幸")
    print("   → Style corrections: 升旗儀式 → 升旗典禮")
    print("   → Number markers remain untouched")
    
    # Step 4: Restore
    final_text = protector.restore_chinese_numbers(ai_result)
    
    print("\n   Step 4: Restore original numbers from markers")
    print("   → CHINESE_NUM_XXXXXX becomes 140位")
    print("   → CHINESE_NUM_YYYYYY becomes 2024年3月15日")
    
    print("\n✅ FINAL RESULT:")
    print(final_text)
    
    print("\n🎯 KEY BENEFITS:")
    print("   ✓ Numbers stay in Arabic numerals (140, not 一百四十)")
    print("   ✓ Dates remain consistent (2024年3月15日)")
    print("   ✓ AI still makes proper style corrections")
    print("   ✓ No manual intervention required")
    print("   ✓ Works with any Chinese-Arabic number combination")
    
    print("\n📋 PROTECTED PATTERNS:")
    protected_patterns = [
        "Dates: 2024年3月15日, 2023年",
        "Numbers with units: 140位, 300人, 500元",
        "Ordinals: 第5樓, 第25頁",
        "Percentages: 95.5%",
        "Time: 3時30分",
        "Measurements: 25度",
        "ISBN/DOI references",
        "Footnote markers: ¹²³"
    ]
    
    for pattern in protected_patterns:
        print(f"   • {pattern}")
    
    print(f"\n🔧 INTEGRATION:")
    print("   The protection is automatically applied in:")
    print("   • /proofread endpoint (text input)")
    print("   • /proofread-docx endpoint (DOCX file input)")
    print("   • All AI processing workflows")

if __name__ == "__main__":
    demo_protection()
