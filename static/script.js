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
        data.mistakes.forEach(mistake => {
            const li = document.createElement('li');
            li.textContent = mistake;
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
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('docxResultsSection').style.display = 'none';
    document.getElementById('initial-state').style.display = 'flex';
    document.getElementById('inputText').value = '';
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
                mistakes: mistakes
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
});
