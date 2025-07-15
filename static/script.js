// API base URL
const API_BASE_URL = window.location.origin || 'http://localhost:8005';

// DOM elements
let inputText = document.getElementById('inputText');
const proofreadBtn = document.getElementById('proofreadBtn');
const btnText = document.getElementById('btnText');
const spinner = document.getElementById('spinner');
const resultsSection = document.getElementById('resultsSection');
const errorSection = document.getElementById('errorSection');
const originalText = document.getElementById('originalText');
const correctedText = document.getElementById('correctedText');
const mistakesList = document.getElementById('mistakesList');
const mistakesBox = document.getElementById('mistakesBox');
const errorMessage = document.getElementById('errorMessage');

// Global variables for file handling
let selectedFile = null;
let currentDownloadFilename = null;
let currentCitations = [];

// Proofread text function
async function proofreadText() {
    const text = inputText.value.trim();
    
    if (!text) {
        showToast('Please enter some text to proofread', 'error');
        return;
    }
    
    // Show loading state
    setLoadingState(true);
    showLoadingState('Processing your text...', 'Please wait while we analyze your content for style and grammar compliance.');
    hideResults();
    hideError();
    
    try {
        const response = await fetch(`${API_BASE_URL}/proofread`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: text })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to proofread text');
        }
        
        const data = await response.json();
        hideLoadingState();
        currentCitations = data.citations || [];
        displayResults(data);
        
    } catch (error) {
        console.error('Error:', error);
        hideLoadingState();
        showError(error.message);
    } finally {
        setLoadingState(false);
    }
}

// Set loading state
function setLoadingState(loading) {
    proofreadBtn.disabled = loading;
    if (loading) {
        proofreadBtn.classList.add('processing');
        btnText.textContent = 'Processing...';
        spinner.classList.remove('hidden');
    } else {
        proofreadBtn.classList.remove('processing');
        btnText.textContent = 'Proofread Text';
        spinner.classList.add('hidden');
    }
}

// Helper function to parse mistake text and extract sources
function parseMistakeText(mistakeText) {
    // Remove leading numbers and dashes (e.g., "1. ", "2. ", "- ")
    let cleanText = mistakeText.replace(/^[\d\-]\.\s*/, '').replace(/^-\s*/, '');
    
    // Check if this contains Chinese characters - if so, return as-is without filtering
    const containsChinese = /[\u4e00-\u9fff]/.test(cleanText);
    if (containsChinese) {
        return {
            text: cleanText.trim(),
            sources: []
        };
    }
    
    // Check if this is a standalone citation first (before applying regex)
    if (cleanText.match(/^(CUHK\s+Style\s+Guide|All\s+corrections\s+are\s+based|CUHK\s+樣式指南|所有修正|中大.*指南)/i)) {
        return {
            text: '', // Empty text since this is just a citation
            sources: [cleanText.trim()]
        };
    }
    
    // More conservative regex - only match clear citation patterns for English content
    // Only captures text clearly in parentheses or at the end as standalone references
    const sourceRegex = /\((?:[^)]*(?:see|style\s+guide|CUHK|capitalisation|capitalization|spelling|punctuation|grammar|possessive|formal\s+writing|section|guide)[^)]*)\)|(?:\s*(?:CUHK\s+[^.]*(?:Style\s+Guide|指南)[^.]*\.|All\s+corrections\s+are\s+based[^.]*\.)\s*)$/gi;
    
    // Find and extract source references
    let sources = cleanText.match(sourceRegex) || [];
    
    // Clean up sources by removing leading whitespace
    sources = sources.map(source => source.trim());
    
    // Only remove source references from the main text if we actually found clear citations
    if (sources.length > 0) {
        cleanText = cleanText.replace(sourceRegex, '').trim();
    }
    
    // Clean up any trailing periods, commas, or extra whitespace
    cleanText = cleanText.replace(/[.,。，]\s*$/, '').replace(/\s+/g, ' ').trim();
    
    const result = {
        text: cleanText,
        sources: sources
    };
    
    return result;
}

// Function to find citation by reference text or index
function findCitationByReference(referenceText) {
    // More permissive check for citation patterns - includes Chinese keywords
    const citationKeywords = ['see', 'style guide', 'Style Guide', 'CUHK', 'capitalisation', 'capitalization',
                             'spelling', 'punctuation', 'grammar', 'possessive', 'formal writing', 
                             'Section', 'all corrections are based', 'guide', 'reference',
                             '參見', '樣式', '指南', '中大', '拼寫', '標點', '語法', '格式', '正式', 
                             '寫作', '部分', '章節', '所有修正', '修訂', '更正'];
    
    // Check if reference text contains any citation keywords
    const hasCitationKeyword = citationKeywords.some(keyword => 
        referenceText.toLowerCase().includes(keyword.toLowerCase()) || 
        referenceText.includes(keyword)
    );
    
    if (hasCitationKeyword) {
        // For citation format, create a synthetic citation object
        let fileName = 'Style Guide';
        let categoryHint = '';
        let sectionInfo = '';
        
        // Try to determine which style guide and category based on content
        if (referenceText.toLowerCase().includes('english') || 
            (referenceText.includes('CUHK') && !referenceText.includes('中文') && !referenceText.includes('Chinese'))) {
            fileName = 'CUHK English Style Guide';
        } else if (referenceText.toLowerCase().includes('chinese') || 
                   referenceText.includes('中文') || 
                   referenceText.includes('中大') ||
                   referenceText.includes('樣式指南')) {
            fileName = 'CUHK Chinese Style Guide';
        }
        
        // Extract section information if present
        const sectionMatch = referenceText.match(/Section\s+([\d.]+)|部分\s*([\d.]+)|章節\s*([\d.]+)/i);
        if (sectionMatch) {
            sectionInfo = `Section ${sectionMatch[1] || sectionMatch[2] || sectionMatch[3]}`;
        }
        
        // Determine category hint for better user understanding (English and Chinese)
        if (referenceText.toLowerCase().includes('capitalisation') || 
            referenceText.toLowerCase().includes('capitalization') ||
            referenceText.toLowerCase().includes('title case') ||
            referenceText.includes('大小寫') ||
            referenceText.includes('標題格式')) {
            categoryHint = 'Capitalisation and Title Case';
        } else if (referenceText.toLowerCase().includes('spelling') || 
                   referenceText.includes('拼寫') ||
                   referenceText.includes('拼字')) {
            categoryHint = 'Spelling';
        } else if (referenceText.toLowerCase().includes('punctuation') || 
                   referenceText.includes('標點') ||
                   referenceText.includes('標點符號')) {
            categoryHint = 'Punctuation';
        } else if (referenceText.toLowerCase().includes('grammar') || 
                   referenceText.includes('語法') ||
                   referenceText.includes('文法')) {
            categoryHint = 'Grammar';
        } else if (referenceText.toLowerCase().includes('apostrophe') || 
                   referenceText.toLowerCase().includes('possessive') ||
                   referenceText.includes('撇號') ||
                   referenceText.includes('所有格')) {
            categoryHint = 'Apostrophe Usage';
        } else if ((referenceText.toLowerCase().includes('date') && referenceText.toLowerCase().includes('time')) ||
                   (referenceText.includes('日期') && referenceText.includes('時間'))) {
            categoryHint = 'Date and Time Format';
        } else if (referenceText.toLowerCase().includes('institution') || 
                   referenceText.toLowerCase().includes('department') ||
                   referenceText.includes('機構') ||
                   referenceText.includes('部門')) {
            categoryHint = 'Institutional Names and Departments';
        } else if (referenceText.toLowerCase().includes('formal writing') || 
                   referenceText.toLowerCase().includes('etc') ||
                   referenceText.includes('正式寫作') ||
                   referenceText.includes('正式文體')) {
            categoryHint = 'Formal Writing Conventions';
        }
        
        // Clean up the reference text for display
        let cleanReference = referenceText
            .replace(/^\(/, '')
            .replace(/\)$/, '')
            .replace(/^see\s+/, 'See ')
            .replace(/^參見\s*/, '參見 ')
            .replace(/^-\s*/, '')
            .trim();
        
        return {
            text: cleanReference,
            file_name: fileName,
            category: categoryHint,
            section: sectionInfo,
            index: -1 // Special index for GPT-4.1 format
        };
    }
    
    return null;
}

// Function to show citation popup
function showCitationPopup(citation) {
    // Remove existing popup if any
    const existingPopup = document.querySelector('.citation-popup');
    if (existingPopup) {
        existingPopup.remove();
    }
    
    // Create popup
    const popup = document.createElement('div');
    popup.className = 'citation-popup';
    
    // Format content based on citation type
    let popupContent = '';
    if (citation.index === -1) {
        // GPT-4.1 format
        popupContent = `
            <div class="citation-popup-content">
                <div class="citation-popup-header">
                    <h4>Style Guide Reference</h4>
                    <button class="citation-close-btn" onclick="closeCitationPopup()">×</button>
                </div>
                <div class="citation-popup-body">
                    <p><strong>Reference:</strong> ${citation.text}</p>
                    <p><strong>Source:</strong> ${citation.file_name}</p>
                    ${citation.section ? `<p><strong>Section:</strong> ${citation.section}</p>` : ''}
                    ${citation.category ? `<p><strong>Category:</strong> ${citation.category}</p>` : ''}
                </div>
            </div>
        `;
    } else {
        // Fallback format (if any citations still use old structure)
        popupContent = `
            <div class="citation-popup-content">
                <div class="citation-popup-header">
                    <h4>Citation</h4>
                    <button class="citation-close-btn" onclick="closeCitationPopup()">×</button>
                </div>
                <div class="citation-popup-body">
                    <p><strong>Reference:</strong> ${citation.text}</p>
                    ${citation.file_name ? `<p><strong>Source:</strong> ${citation.file_name}</p>` : ''}
                </div>
            </div>
        `;
    }
    
    popup.innerHTML = popupContent;
    document.body.appendChild(popup);
    
    // Add click outside to close
    popup.addEventListener('click', (e) => {
        if (e.target === popup) {
            closeCitationPopup();
        }
    });
    
    // Add keyboard support
    const handleKeyPress = (e) => {
        if (e.key === 'Escape') {
            closeCitationPopup();
            document.removeEventListener('keydown', handleKeyPress);
        }
    };
    document.addEventListener('keydown', handleKeyPress);
}

// Function to close citation popup
function closeCitationPopup() {
    const popup = document.querySelector('.citation-popup');
    if (popup) {
        popup.remove();
    }
}

// Create issue list item with sources
function createIssueListItem(mistakeText) {
    const parsed = parseMistakeText(mistakeText);
    const li = document.createElement('li');
    
    // Check if this is a standalone citation (no mistake text)
    if (!parsed.text && parsed.sources.length > 0) {
        // This is just a citation reference
        li.className = 'citation-only';
        
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'issue-sources citation-standalone';
        
        parsed.sources.forEach(source => {
            const sourceBtn = document.createElement('button');
            sourceBtn.className = 'issue-source-btn citation-standalone-btn';
            
            // Truncate very long text for display while keeping full text in title
            let displayText = source;
            const maxLength = 80; // Maximum characters to display
            if (source.length > maxLength) {
                displayText = source.substring(0, maxLength) + '...';
            }
            
            sourceBtn.textContent = displayText;
            
            // Add title attribute for tooltip on hover
            sourceBtn.title = source;
            
            const citation = findCitationByReference(source);
            if (citation) {
                sourceBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    showCitationPopup(citation);
                });
                sourceBtn.style.cursor = 'pointer';
            }
            
            sourcesDiv.appendChild(sourceBtn);
        });
        
        li.appendChild(sourcesDiv);
        return li;
    }
    
    // Fallback: if parsing removed all text but original has content, show original
    if (!parsed.text && mistakeText.trim()) {
        const textDiv = document.createElement('div');
        textDiv.className = 'issue-text';
        textDiv.textContent = mistakeText.trim();
        li.appendChild(textDiv);
        return li;
    }
    
    // Additional safety check: if parsed text is very short compared to original, use original
    if (parsed.text && mistakeText.trim() && 
        parsed.text.length < mistakeText.trim().length * 0.3 && 
        mistakeText.trim().length > 20) {
        const textDiv = document.createElement('div');
        textDiv.className = 'issue-text';
        textDiv.textContent = mistakeText.trim();
        li.appendChild(textDiv);
        return li;
    }
    
    // Regular mistake with text and optional sources
    const textDiv = document.createElement('div');
    textDiv.className = 'issue-text';
    textDiv.textContent = parsed.text;
    
    // Create sources container
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'issue-sources';
    
    // Add source chips
    parsed.sources.forEach(source => {
        const sourceBtn = document.createElement('button');
        sourceBtn.className = 'issue-source-btn';
        
        // Truncate very long text for display while keeping full text in title
        let displayText = source;
        const maxLength = 80; // Maximum characters to display
        if (source.length > maxLength) {
            displayText = source.substring(0, maxLength) + '...';
        }
        
        sourceBtn.textContent = displayText;
        
        // Add title attribute for tooltip on hover (especially useful for long text)
        sourceBtn.title = source;
        
        // Find corresponding citation and add click handler
        const citation = findCitationByReference(source);
        if (citation) {
            sourceBtn.addEventListener('click', (e) => {
                e.preventDefault();
                showCitationPopup(citation);
            });
            sourceBtn.style.cursor = 'pointer';
        } else {
            sourceBtn.style.cursor = 'default';
            sourceBtn.title = source + ' (Citation details not available)';
        }
        
        sourcesDiv.appendChild(sourceBtn);
    });
    
    li.appendChild(textDiv);
    if (parsed.sources.length > 0) {
        li.appendChild(sourcesDiv);
    }
    
    return li;
}

// Display results
function displayResults(data) {
    // Hide initial state and show results
    document.getElementById('initial-state').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';
    
    // Populate content
    document.getElementById('originalText').textContent = data.original_text;
    document.getElementById('correctedText').textContent = data.corrected_text;
    
    // Handle mistakes
    if (data.mistakes && data.mistakes.length > 0) {
        const mistakesBox = document.getElementById('mistakesBox');
        const mistakesList = document.getElementById('mistakesList');
        
        mistakesList.innerHTML = '';
        data.mistakes.forEach((mistake, index) => {
            const li = createIssueListItem(mistake);
            mistakesList.appendChild(li);
        });
        
        mistakesBox.style.display = 'block';
    } else {
        document.getElementById('mistakesBox').style.display = 'none';
    }
}

// Show error
function showError(message) {
    errorMessage.textContent = message;
    errorSection.style.display = 'flex';
}

// Hide results
function hideResults() {
    resultsSection.style.display = 'none';
}

// Hide error
function hideError() {
    errorSection.style.display = 'none';
}

// Show loading state
function showLoadingState(title = 'Processing...', message = 'Please wait while we process your request.') {
    document.getElementById('initial-state').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('docxResultsSection').style.display = 'none';
    document.getElementById('loadingTitle').textContent = title;
    document.getElementById('loadingMessage').textContent = message;
    document.getElementById('loading-state').style.display = 'flex';
}

// Hide loading state
function hideLoadingState() {
    document.getElementById('loading-state').style.display = 'none';
}

// Clear results
function clearResults() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('docxResultsSection').style.display = 'none';
    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('initial-state').style.display = 'flex';
    document.getElementById('inputText').value = '';
    currentCitations = [];
    clearFile();
}

// Clear error
function clearError() {
    hideError();
}

// Copy to clipboard
async function copyToClipboard() {
    const textToCopy = correctedText.textContent;
    
    if (!textToCopy) {
        showToast('No text to copy', 'error');
        return;
    }
    
    try {
        await navigator.clipboard.writeText(textToCopy);
        showToast('Text copied to clipboard!');
    } catch (error) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = textToCopy;
        document.body.appendChild(textArea);
        textArea.select();
        
        try {
            document.execCommand('copy');
            showToast('Text copied to clipboard!');
        } catch (fallbackError) {
            showToast('Failed to copy text', 'error');
        }
        
        document.body.removeChild(textArea);
    }
}

// Show toast notification
function showToast(message, type = 'success') {
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    // Get or create toast container
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    
    toastContainer.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// Handle Enter key in textarea (Ctrl+Enter to submit)
if (inputText) {
    inputText.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'Enter') {
            event.preventDefault();
            proofreadText();
        }
    });

    // Auto-resize textarea
    inputText.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.max(150, this.scrollHeight) + 'px';
    });
}

// Tab switching functions for new UI
function showInputTab(tabName) {
    // Remove active class from all input tabs and panels
    document.querySelectorAll('.input-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.input-panel').forEach(panel => panel.classList.remove('active'));
    
    // Add active class to selected tab and panel
    event.target.classList.add('active');
    document.getElementById(tabName + '-input-panel').classList.add('active');
    
    // Clear any existing results and errors
    hideResults();
    hideDocxResults();
    hideError();
    hideLoadingState();
    
    // Show initial state when switching tabs
    document.getElementById('initial-state').style.display = 'flex';
}

// Copy functions for new UI
function copyOriginal() {
    const originalText = document.getElementById('originalText').textContent;
    navigator.clipboard.writeText(originalText).then(() => {
        showToast('Original text copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy text', 'error');
    });
}

function copyResult() {
    const correctedText = document.getElementById('correctedText').textContent;
    navigator.clipboard.writeText(correctedText).then(() => {
        showToast('Corrected text copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy text', 'error');
    });
}

async function exportToWord() {
    // Get the texts
    const correctedText = document.getElementById('correctedText').textContent;
    const originalTextContent = document.getElementById('originalText').textContent;
    
    if (!correctedText) {
        showToast('No corrected text to export', 'error');
        return;
    }
    
    // Show loading toast
    showToast('Creating Word document...', 'info');
    
    try {
        // Get the mistakes from the current results
        const mistakesList = document.getElementById('mistakesList');
        const mistakes = [];
        if (mistakesList) {
            const mistakeItems = mistakesList.querySelectorAll('li');
            mistakeItems.forEach(item => {
                mistakes.push(item.textContent);
            });
        }
        
        const response = await fetch(`${API_BASE_URL}/export-to-word`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                original_text: originalTextContent,
                corrected_text: correctedText,
                mistakes: mistakes,
                citations: currentCitations || []
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to create Word document');
        }
        
        const data = await response.json();
        
        // Download the file
        const downloadUrl = `${API_BASE_URL}${data.download_url}`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showToast('Word document downloaded successfully!', 'success');
        
    } catch (error) {
        console.error('Error exporting to Word:', error);
        showToast('Failed to create Word document: ' + error.message, 'error');
    }
}

// Get appropriate icon based on file extension
function getFileIcon(filename) {
    const extension = filename.split('.').pop().toLowerCase();
    switch (extension) {
        case 'pdf':
            return '📄';
        case 'doc':
        case 'docx':
            return '📝';
        case 'zip':
            return '🗜️';
        case 'md':
            return '📋';
        default:
            return '📄';
    }
}

// Load style guides dynamically
async function loadStyleGuides() {
    try {
        const response = await fetch(`${API_BASE_URL}/style-guides`);
        if (!response.ok) {
            console.error('Failed to load style guides');
            return;
        }
        
        const data = await response.json();
        const styleGuideFiles = document.querySelector('.style-guide-files');
        
        if (!styleGuideFiles) {
            console.error('Style guide files container not found');
            return;
        }
        
        // Clear existing content
        styleGuideFiles.innerHTML = '';
        
        if (data.files && data.files.length > 0) {
            data.files.forEach(file => {
                const fileItem = document.createElement('a');
                fileItem.href = file.download_url;
                fileItem.className = 'style-guide-item';
                fileItem.download = true;
                
                fileItem.innerHTML = `
                    <span class="file-icon">${getFileIcon(file.filename)}</span>
                    <span class="file-name">${file.display_name}</span>
                    <br>
                `;
                
                styleGuideFiles.appendChild(fileItem);
            });
        } else {
            styleGuideFiles.innerHTML = '<p class="no-files">No style guides available</p>';
        }
    } catch (error) {
        console.error('Error loading style guides:', error);
    }
}

// File upload functionality
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const fileUploadArea = document.getElementById('fileUploadArea');
    const selectedFileDiv = document.getElementById('selectedFile');
    const fileName = document.getElementById('fileName');
    const proofreadFileBtn = document.getElementById('proofreadFileBtn');
    const chooseFilesBtn = document.querySelector('.choose-files-btn');
    
    // File input change handler
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            handleFileSelection(e.target.files[0]);
        });
    }
    
    // Choose files button click handler
    if (chooseFilesBtn) {
        chooseFilesBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fileInput.click();
        });
    }
    
    // Drag and drop functionality
    if (fileUploadArea) {
        fileUploadArea.addEventListener('click', function() {
            fileInput.click();
        });
        
        fileUploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            fileUploadArea.classList.add('dragover');
        });
        
        fileUploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            fileUploadArea.classList.remove('dragover');
        });
        
        fileUploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            fileUploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelection(files[0]);
            }
        });
    }
});

function handleFileSelection(file) {
    if (!file) return;
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.docx')) {
        showToast('Please select a DOCX file', 'error');
        return;
    }
    
    selectedFile = file;
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('selectedFile').style.display = 'flex';
    document.getElementById('proofreadFileBtn').style.display = 'block';
    document.getElementById('fileUploadArea').style.display = 'none';
}

function clearFile() {
    selectedFile = null;
    document.getElementById('selectedFile').style.display = 'none';
    document.getElementById('proofreadFileBtn').style.display = 'none';
    document.getElementById('fileUploadArea').style.display = 'block';
    document.getElementById('fileInput').value = '';
}

// Proofread DOCX file function
// Proofread DOCX file function
async function proofreadFile() {
    if (!selectedFile) {
        showToast('Please select a DOCX file first', 'error');
        return;
    }
    
    // Show loading state
    setFileLoadingState(true);
    showLoadingState('Processing your document...', 'Please wait while we analyze your DOCX file for style and grammar compliance.');
    hideResults();
    hideDocxResults();
    hideError();
    
    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        const response = await fetch(`${API_BASE_URL}/proofread-docx`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to process DOCX file');
        }
        
        const data = await response.json();
        hideLoadingState();
        currentCitations = data.citations || [];
        displayDocxResults(data);
        
    } catch (error) {
        console.error('Error:', error);
        hideLoadingState();
        showError(error.message);
    } finally {
        setFileLoadingState(false);
    }
}

// Set file loading state
function setFileLoadingState(loading) {
    const proofreadFileBtn = document.getElementById('proofreadFileBtn');
    const fileBtnText = document.getElementById('fileBtnText');
    const fileSpinner = document.getElementById('fileSpinner');
    
    proofreadFileBtn.disabled = loading;
    if (loading) {
        proofreadFileBtn.classList.add('processing');
        fileBtnText.textContent = 'Processing...';
        fileSpinner.classList.remove('hidden');
    } else {
        proofreadFileBtn.classList.remove('processing');
        fileBtnText.textContent = 'Proofread Document';
        fileSpinner.classList.add('hidden');
    }
}

// Display DOCX results
function displayDocxResults(data) {
    // Hide initial state and show DOCX results
    document.getElementById('initial-state').style.display = 'none';
    
    document.getElementById('originalFilename').textContent = data.original_filename;
    document.getElementById('mistakesCount').textContent = data.mistakes_count;
    
    // Store download filename
    currentDownloadFilename = data.download_filename;
    
    // Clear previous mistakes
    const docxMistakesList = document.getElementById('docxMistakesList');
    docxMistakesList.innerHTML = '';
    
    // Display mistakes if any
    if (data.mistakes && data.mistakes.length > 0) {
        data.mistakes.forEach((mistake, index) => {
            if (mistake.trim()) {
                const li = createIssueListItem(mistake);
                docxMistakesList.appendChild(li);
            }
        });
        document.getElementById('docxMistakesBox').style.display = 'block';
    } else {
        document.getElementById('docxMistakesBox').style.display = 'none';
    }
    
    document.getElementById('docxResultsSection').style.display = 'block';
    
    // Scroll to results
    document.getElementById('docxResultsSection').scrollIntoView({ behavior: 'smooth' });
}

// Download corrected DOCX
async function downloadCorrectedDocx() {
    if (!currentDownloadFilename) {
        showToast('No file available for download', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/download-docx/${currentDownloadFilename}`);
        
        if (!response.ok) {
            throw new Error('Failed to download file');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = currentDownloadFilename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showToast('File downloaded successfully!', 'success');
        
    } catch (error) {
        console.error('Download error:', error);
        showToast('Failed to download file', 'error');
    }
}

// Hide DOCX results
function hideDocxResults() {
    document.getElementById('docxResultsSection').style.display = 'none';
}

// Clear DOCX results
function clearDocxResults() {
    hideDocxResults();
    clearFile();
    currentCitations = [];
    currentDownloadFilename = null;
    document.getElementById('initial-state').style.display = 'flex';
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Re-get inputText in case DOM wasn't ready
    if (!inputText) {
        inputText = document.getElementById('inputText');
    }
    
    // Focus on input text if it exists
    if (inputText) {
        inputText.focus();
    }
    
    // Load style guides on initial load
    loadStyleGuides();
});
