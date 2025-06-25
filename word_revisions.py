#!/usr/bin/env python3
"""
Word revisions module for creating DOCX files with track changes.
Handles proper spacing preservation to avoid words sticking together.
"""

import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
from typing import List, Tuple, Union
from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import RGBColor
import difflib


class WordRevisionGenerator:
    """Generates Word documents with track changes, preserving proper spacing."""
    
    def __init__(self):
        self.revision_id = 0
        self.author = "Proofreader"
        self.date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def create_document_with_revisions(self, original_text: str, corrected_text: str, mistakes: List[str]) -> BytesIO:
        """
        Create a DOCX document with track changes showing the differences between original and corrected text.
        
        Args:
            original_text: The original text
            corrected_text: The corrected text
            mistakes: List of mistake descriptions
            
        Returns:
            BytesIO: The generated DOCX file as bytes
        """
        # Create a new document
        doc = Document()
        
        # Enable track changes in document settings
        self._enable_track_changes(doc)
        
        # Add a title
        title = doc.add_heading("Document with Track Changes", level=1)
        
        # Generate word-level differences
        changes = self._generate_word_diff(original_text, corrected_text)
        
        # Create paragraph with proper Word track changes
        para = doc.add_paragraph()
        
        for change_type, text in changes:
            if change_type == 'equal':
                # Unchanged text - add normally
                para.add_run(text)
            elif change_type == 'delete':
                # Add deleted text using Word's native deletion tracking
                self._add_deletion_to_paragraph(para, text)
            elif change_type == 'insert':
                # Add inserted text using Word's native insertion tracking
                self._add_insertion_to_paragraph(para, text)
        
        # Add corrections summary at the bottom
        if mistakes:
            # Add separator
            doc.add_paragraph("─" * 50)
            
            mistakes_para = doc.add_paragraph()
            mistakes_para.add_run("Corrections Made:").bold = True
            for mistake in mistakes:
                # Use regular paragraph without numbered style to avoid duplication
                mistake_para = doc.add_paragraph(f"• {mistake}")
        
        # Save to BytesIO
        doc_bytes = BytesIO()
        doc.save(doc_bytes)
        doc_bytes.seek(0)
        
        return doc_bytes
    
    def _generate_word_diff(self, original: str, corrected: str) -> List[Tuple[str, str]]:
        """
        Generate word-level differences between original and corrected text.
        Preserves spacing to avoid words sticking together.
        
        Args:
            original: Original text
            corrected: Corrected text
            
        Returns:
            List of tuples (change_type, text) where change_type is 'equal', 'delete', or 'insert'
        """
        # Tokenize the text while preserving spaces
        original_tokens = self._tokenize_with_spaces(original)
        corrected_tokens = self._tokenize_with_spaces(corrected)
        
        # Use difflib to find differences
        matcher = difflib.SequenceMatcher(None, original_tokens, corrected_tokens)
        
        changes = []
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == 'equal':
                # Unchanged tokens
                text = ''.join(original_tokens[i1:i2])
                if text:
                    changes.append(('equal', text))
            elif op == 'delete':
                # Deleted tokens
                text = ''.join(original_tokens[i1:i2])
                if text:
                    changes.append(('delete', text))
            elif op == 'insert':
                # Inserted tokens
                text = ''.join(corrected_tokens[j1:j2])
                if text:
                    changes.append(('insert', text))
            elif op == 'replace':
                # Replaced tokens - treat as delete + insert
                deleted_text = ''.join(original_tokens[i1:i2])
                if deleted_text:
                    changes.append(('delete', deleted_text))
                inserted_text = ''.join(corrected_tokens[j1:j2])
                if inserted_text:
                    changes.append(('insert', inserted_text))
        
        return changes
    
    def _tokenize_with_spaces(self, text: str) -> List[str]:
        """
        Tokenize text while preserving spaces and punctuation.
        Each token is either a word, a space, or punctuation.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of tokens preserving all spacing and punctuation
        """
        if not text:
            return []
        
        tokens = []
        current_token = ""
        
        for char in text:
            if char.isalnum() or char in "'-":
                # Part of a word
                current_token += char
            else:
                # Not part of a word (space, punctuation, etc.)
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                if char:  # Don't add empty characters
                    tokens.append(char)
        
        # Add any remaining token
        if current_token:
            tokens.append(current_token)
        
        return tokens
    
    def _enable_track_changes(self, doc):
        """
        Enable track changes in the document settings.
        
        Args:
            doc: The Document object
        """
        # Access the document settings
        settings = doc.settings
        
        # Add track changes setting to the XML
        settings_xml = settings._element
        
        # Create the track changes element if it doesn't exist
        track_changes = settings_xml.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}trackRevisions')
        if track_changes is None:
            track_changes_xml = f'''<w:trackRevisions {nsdecls('w')}/>'''
            track_changes_element = parse_xml(track_changes_xml)
            settings_xml.append(track_changes_element)
    
    def _add_deletion_to_paragraph(self, paragraph, text):
        """
        Add deleted text to paragraph using Word's native deletion tracking.
        
        Args:
            paragraph: The paragraph to add to
            text: The deleted text
        """
        self.revision_id += 1
        
        # Create deletion XML with red strikethrough (Word's default for deletions)
        del_xml = f'''
        <w:del {nsdecls('w')} w:id="{self.revision_id}" w:author="{self.author}" w:date="{self.date}">
            <w:r>
                <w:rPr>
                    <w:color w:val="FF0000"/>
                    <w:strike w:val="true"/>
                </w:rPr>
                <w:delText>{self._escape_xml(text)}</w:delText>
            </w:r>
        </w:del>
        '''
        
        # Parse and add to paragraph
        del_element = parse_xml(del_xml)
        paragraph._element.append(del_element)
    
    def _add_insertion_to_paragraph(self, paragraph, text):
        """
        Add inserted text to paragraph using Word's native insertion tracking.
        
        Args:
            paragraph: The paragraph to add to
            text: The inserted text
        """
        self.revision_id += 1
        
        # Create insertion XML with green color for better visibility of corrections
        ins_xml = f'''
        <w:ins {nsdecls('w')} w:id="{self.revision_id}" w:author="{self.author}" w:date="{self.date}">
            <w:r>
                <w:rPr>
                    <w:color w:val="008000"/>
                </w:rPr>
                <w:t xml:space="preserve">{self._escape_xml(text)}</w:t>
            </w:r>
        </w:ins>
        '''
        
        # Parse and add to paragraph
        ins_element = parse_xml(ins_xml)
        paragraph._element.append(ins_element)
    
    def _escape_xml(self, text):
        """
        Escape XML special characters in text.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text safe for XML
        """
        if not text:
            return ""
        
        # Replace XML special characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")
        
        return text

    def _create_revision_element(self, text: str, revision_type: str) -> OxmlElement:
        """
        Create a Word revision element with proper XML structure.
        
        Args:
            text: The text content
            revision_type: Type of revision ('insert' or 'delete')
            
        Returns:
            OxmlElement: The revision element
        """
        self.revision_id += 1
        
        if revision_type == 'insert':
            # Create insertion revision - green color for better visibility of corrections
            ins_xml = f'''
            <w:ins {nsdecls('w')} w:id="{self.revision_id}" w:author="{self.author}" w:date="{self.date}">
                <w:r>
                    <w:rPr>
                        <w:color w:val="008000"/>
                    </w:rPr>
                    <w:t>{text}</w:t>
                </w:r>
            </w:ins>
            '''
            return parse_xml(ins_xml)
        
        elif revision_type == 'delete':
            # Create deletion revision - red strikethrough
            del_xml = f'''
            <w:del {nsdecls('w')} w:id="{self.revision_id}" w:author="{self.author}" w:date="{self.date}">
                <w:r>
                    <w:rPr>
                        <w:color w:val="FF0000"/>
                        <w:strike w:val="true"/>
                    </w:rPr>
                    <w:t>{text}</w:t>
                </w:r>
            </w:del>
            '''
            return parse_xml(del_xml)
        
        return None


def create_word_track_changes_docx(original_text: str, corrected_text: str, mistakes: List[str]) -> BytesIO:
    """
    Create a Word document with track changes showing differences between original and corrected text.
    This is the main function called by the FastAPI application.
    
    Args:
        original_text: The original text
        corrected_text: The corrected text  
        mistakes: List of mistake descriptions
        
    Returns:
        BytesIO: The generated DOCX file as bytes
    """
    generator = WordRevisionGenerator()
    return generator.create_document_with_revisions(original_text, corrected_text, mistakes)


# Alternative implementation with more sophisticated tracking
class AdvancedWordRevisionGenerator(WordRevisionGenerator):
    """Advanced version with better character-level tracking for complex cases."""
    
    def create_document_with_revisions(self, original_text: str, corrected_text: str, mistakes: List[str]) -> BytesIO:
        """
        Create a DOCX document with advanced track changes and better spacing handling.
        """
        # Use the parent method but with enhanced diff generation
        return super().create_document_with_revisions(original_text, corrected_text, mistakes)
    
    def _generate_word_diff(self, original: str, corrected: str) -> List[Tuple[str, str]]:
        """
        Enhanced word diff that handles edge cases better.
        """
        # Handle the case where text has no spaces (all stuck together)
        if ' ' not in original and ' ' in corrected:
            return self._handle_spacing_insertion(original, corrected)
        
        # Handle normal case with existing implementation
        return super()._generate_word_diff(original, corrected)
    
    def _handle_spacing_insertion(self, original: str, corrected: str) -> List[Tuple[str, str]]:
        """
        Handle the special case where spaces need to be inserted into stuck-together text.
        
        Args:
            original: Text without proper spacing
            corrected: Text with proper spacing
            
        Returns:
            List of change tuples
        """
        changes = []
        
        # Use character-level diffing for this case
        original_chars = list(original)
        corrected_chars = list(corrected)
        
        matcher = difflib.SequenceMatcher(None, original_chars, corrected_chars)
        
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == 'equal':
                text = ''.join(original_chars[i1:i2])
                if text:
                    changes.append(('equal', text))
            elif op == 'delete':
                text = ''.join(original_chars[i1:i2])
                if text:
                    changes.append(('delete', text))
            elif op == 'insert':
                text = ''.join(corrected_chars[j1:j2])
                if text:
                    changes.append(('insert', text))
            elif op == 'replace':
                # For replace, check if we're just adding spaces
                deleted = ''.join(original_chars[i1:i2])
                inserted = ''.join(corrected_chars[j1:j2])
                
                # If the inserted text contains the deleted text plus spaces, handle specially
                if deleted in inserted and ' ' in inserted:
                    # Mark original as deleted and new as inserted
                    changes.append(('delete', deleted))
                    changes.append(('insert', inserted))
                else:
                    # Regular replace
                    if deleted:
                        changes.append(('delete', deleted))
                    if inserted:
                        changes.append(('insert', inserted))
        
        return changes


# For testing with the advanced generator
def create_word_track_changes_docx_advanced(original_text: str, corrected_text: str, mistakes: List[str]) -> BytesIO:
    """
    Create a Word document using the advanced revision generator.
    """
    generator = AdvancedWordRevisionGenerator()
    return generator.create_document_with_revisions(original_text, corrected_text, mistakes)
