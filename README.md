# Styling Guide Proof-reader

A FastAPI backend with HTML/CSS/JS frontend for proofreading text using Azure OpenAI Assistant, managed with `uv`.

## Features

- 📝 Text proofreading using Azure OpenAI Assistant
- 🎨 Modern, responsive web interface
- ⚡ Real-time error detection and correction
- 📋 Copy corrected text to clipboard
- 🔄 Clear results and start over
- 📱 Mobile-friendly design

## Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure OpenAI account and API key
- GPT-4o model deployment

## Installation

### 1. Install uv (if not already installed)

**On macOS and Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**On Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Or using pip:**
```bash
pip install uv
```

### 2. Project Setup

1. **Navigate to the project directory:**
   ```bash
   cd /home/dinochlai/styling-guide-demo
   ```

2. **Install dependencies using uv:**
   ```bash
   uv sync
   ```

3. **Configure environment variables:**
   The `.env` file should already contain your Azure OpenAI credentials:
   ```
   AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key-here
   ```

4. **Update the model name (if needed):**
   In `main.py`, line 31, replace `"gpt-4o"` with your actual model deployment name.

## Running the Application

### Start the server using uv:

```bash
uv run python main.py
```

Or using uvicorn directly:
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Access the application:
Open your web browser and navigate to: `http://localhost:8000`

## Development with uv

### Adding dependencies:
```bash
uv add package_name
```

### Adding development dependencies:
```bash
uv add --dev package_name
```

### Running with specific Python version:
```bash
uv run --python 3.11 python main.py
```

### Create a virtual environment:
```bash
uv venv
```

### Activate the virtual environment:
```bash
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows
```

## API Endpoints

### `POST /proofread`
Proofread text using the Azure OpenAI Assistant.

**Request Body:**
```json
{
  "text": "Your text to be proofread"
}
```

**Response:**
```json
{
  "original_text": "Original input text",
  "corrected_text": "Assistant's proofreading response",
  "mistakes": ["List of identified mistakes"],
  "status": "completed"
}
```

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "proof-reader"
}
```

## Project Structure

```
styling-guide-demo/
├── main.py                 # FastAPI backend
├── pyproject.toml          # Project configuration and dependencies (uv)
├── .env                   # Environment variables
├── README.md              # This file
└── static/                # Frontend files
    ├── index.html         # Main HTML page
    ├── styles.css         # CSS styles
    └── script.js          # JavaScript functionality
```

## Usage

1. Enter or paste your text in the textarea
2. Click "Proofread Text" or press Ctrl+Enter
3. View the results including:
   - Original text
   - Assistant's proofreading response
   - List of identified mistakes (if any)
4. Copy the corrected text to clipboard if needed
5. Clear results to start over

## Customization

### Assistant Instructions
You can modify the assistant's behavior by editing the `instructions` parameter in `main.py`:

```python
instructions="""1. Proof read user's input message only following the styling guide. 
2. List the mistake below and the correction of it
***Do not answer any question except doing proof-reading***"""
```

### Styling
Customize the appearance by editing `static/styles.css`. The interface uses:
- Modern gradient backgrounds
- Responsive design
- Smooth animations
- Toast notifications

### Functionality
Add new features by modifying `static/script.js` and adding corresponding API endpoints in `main.py`.

## Troubleshooting

### Common Issues

1. **uv command not found:**
   - Make sure uv is installed and in your PATH
   - Restart your terminal after installation

2. **Import errors when starting the server:**
   - Run `uv sync` to ensure all dependencies are installed

3. **Azure OpenAI connection errors:**
   - Verify your endpoint URL and API key in `.env`
   - Ensure your Azure OpenAI resource is properly configured
   - Check that your model deployment name is correct

4. **Assistant creation fails:**
   - Verify your API key has the necessary permissions
   - Check that you're using a supported API version

5. **Frontend not loading:**
   - Ensure the `static` directory and all files exist
   - Check browser console for JavaScript errors

### Environment Variables

Make sure your `.env` file contains:
```
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_KEY=your-actual-api-key
```

## Production Deployment

For production deployment with uv:

1. **Build the project:**
   ```bash
   uv build
   ```

2. **Install in production environment:**
   ```bash
   uv sync --no-dev
   ```

3. **Run with production server:**
   ```bash
   uv run gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

Consider also:
- Setting up proper environment variable management
- Implementing proper logging and monitoring
- Adding rate limiting and authentication
- Using a reverse proxy like Nginx

## Benefits of using uv

- **Fast:** uv is 10-100x faster than pip
- **Reliable:** Built-in dependency resolution
- **Cross-platform:** Works on Windows, macOS, and Linux
- **Modern:** Built in Rust with modern Python packaging standards
- **Compatible:** Works with existing Python projects and requirements.txt files
