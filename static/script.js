// API base URL
const API_BASE_URL = window.location.origin;

// DOM elements
const inputText = document.getElementById('inputText');
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

// Proofread text function
async function proofreadText() {
    const text = inputText.value.trim();
    
    if (!text) {
        showToast('Please enter some text to proofread', 'error');
        return;
    }
    
    // Show loading state
    setLoadingState(true);
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
        displayResults(data);
        
    } catch (error) {
        console.error('Error:', error);
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

// Display results
function displayResults(data) {
    originalText.textContent = data.original_text;
    correctedText.textContent = data.corrected_text;
    
    // Clear previous mistakes
    mistakesList.innerHTML = '';
    
    // Display mistakes if any
    if (data.mistakes && data.mistakes.length > 0) {
        data.mistakes.forEach(mistake => {
            if (mistake.trim()) {
                const li = document.createElement('li');
                li.textContent = mistake;
                mistakesList.appendChild(li);
            }
        });
        mistakesBox.style.display = 'block';
    } else {
        mistakesBox.style.display = 'none';
    }
    
    resultsSection.style.display = 'block';
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Show error
function showError(message) {
    errorMessage.textContent = message;
    errorSection.style.display = 'block';
    errorSection.scrollIntoView({ behavior: 'smooth' });
}

// Hide results
function hideResults() {
    resultsSection.style.display = 'none';
}

// Hide error
function hideError() {
    errorSection.style.display = 'none';
}

// Clear results
function clearResults() {
    hideResults();
    inputText.value = '';
    inputText.focus();
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
    
    document.body.appendChild(toast);
    
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

// Tab switching functionality
function showTab(tabId) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab content
    document.getElementById(tabId).classList.add('active');
    
    // Add active class to clicked button
    event.target.classList.add('active');
    
    // Clear results when switching tabs
    hideResults();
    hideDocxResults();
    hideError();
}

// File upload functionality
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const fileUploadArea = document.getElementById('fileUploadArea');
    const selectedFileDiv = document.getElementById('selectedFile');
    const fileName = document.getElementById('fileName');
    const proofreadFileBtn = document.getElementById('proofreadFileBtn');
    
    // File input change handler
    fileInput.addEventListener('change', function(e) {
        handleFileSelection(e.target.files[0]);
    });
    
    // Drag and drop functionality
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
async function proofreadFile() {
    if (!selectedFile) {
        showToast('Please select a DOCX file first', 'error');
        return;
    }
    
    // Show loading state
    setFileLoadingState(true);
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
        displayDocxResults(data);
        
    } catch (error) {
        console.error('Error:', error);
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
    document.getElementById('originalFilename').textContent = data.original_filename;
    document.getElementById('mistakesCount').textContent = data.mistakes_count;
    
    // Store download filename
    currentDownloadFilename = data.download_filename;
    
    // Clear previous mistakes
    const docxMistakesList = document.getElementById('docxMistakesList');
    docxMistakesList.innerHTML = '';
    
    // Display mistakes if any
    if (data.mistakes && data.mistakes.length > 0) {
        data.mistakes.forEach(mistake => {
            if (mistake.trim()) {
                const li = document.createElement('li');
                li.textContent = mistake;
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
    currentDownloadFilename = null;
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    inputText.focus();
    
    // Add keyboard shortcut hint
    const hint = document.createElement('div');
    hint.style.fontSize = '0.8rem';
    hint.style.color = '#666';
    hint.style.marginTop = '0.5rem';
    hint.textContent = 'Tip: Press Ctrl+Enter to proofread quickly';
    inputText.parentNode.appendChild(hint);
});
