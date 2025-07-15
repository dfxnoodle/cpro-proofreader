#!/usr/bin/env python3

def debug_filter_logic():
    mistake = "Corrected 'centre' to 'center' to follow American spelling conventions."
    mistake_lower = mistake.lower().strip()

    print(f'Testing filters for: {mistake}')
    print(f'mistake_lower: {mistake_lower}')
    print()

    # Check general reference filters
    general_refs = [
        'all corrections are based on', 'all changes are based on',
        'corrections are made according to', 'following the style guide',
        'based on the cuhk english style guide', 'based on the style guide',
        'reference to the style guide', 'according to the style guide'
    ]

    print("=== Checking general reference filters ===")
    matched_filter = False
    for ref in general_refs:
        if ref in mistake_lower:
            print(f'✗ MATCHED filter: "{ref}"')
            matched_filter = True
        else:
            print(f'✓ No match for: "{ref}"')

    print()
    
    # Check preservation keywords
    keywords = [
        'corrected to', 'changed to', 'was incorrect', 'spelling error',
        'grammar', 'punctuation', 'subject-verb agreement', 'possessive'
    ]

    print("=== Checking preservation keywords ===")
    matched_keyword = False
    for keyword in keywords:
        if keyword in mistake_lower:
            print(f'✓ MATCHED keyword: "{keyword}"')
            matched_keyword = True
        else:
            print(f'✗ No match for: "{keyword}"')

    print()
    print(f"Final result: matched_filter={matched_filter}, matched_keyword={matched_keyword}")
    
    if matched_filter:
        print("❌ This would be FILTERED OUT because it matches a general reference filter")
    elif matched_keyword:
        print("✅ This would be PRESERVED because it matches a preservation keyword")
    else:
        print("❓ This doesn't match any criteria - unclear what would happen")

if __name__ == "__main__":
    debug_filter_logic()
