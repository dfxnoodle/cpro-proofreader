# Assistant ID Management

This implementation now includes assistant ID persistence to avoid creating new assistants on every startup.

## How it works

1. **First Run**: When the application starts for the first time, it creates a new OpenAI assistant and saves the assistant ID to `assistant_config.json`

2. **Subsequent Runs**: The application checks for an existing `assistant_config.json` file and attempts to reuse the stored assistant ID

3. **Validation**: If the stored assistant ID is invalid or the assistant no longer exists, a new one is created automatically

4. **Lazy Initialization**: The assistant is only created when first needed (when an API endpoint is called), not at application startup. This ensures the server can start even if Azure OpenAI credentials are missing or incorrect.

## Configuration File

The `assistant_config.json` file contains:
```json
{
  "assistant_id": "asst_xxxxxxxxxxxxxxxxxxxxx"
}
```

## Administrative Endpoints

### Get Assistant Information
```
GET /admin/assistant-info
```
Returns current assistant ID and configuration status.

### Reset Assistant
```
DELETE /admin/reset-assistant
```
Forces creation of a new assistant by removing the config file and creating a fresh assistant.

## Benefits

- **Performance**: Eliminates unnecessary assistant creation on each startup
- **Consistency**: Maintains the same assistant across sessions
- **Cost Efficiency**: Reduces API calls to OpenAI
- **Reliability**: Automatic fallback if the stored assistant becomes invalid

## Notes

- The `assistant_config.json` file is automatically added to `.gitignore` to prevent committing API-generated IDs
- If you need to reset the assistant, use the admin endpoint or manually delete the `assistant_config.json` file

## Setup and Troubleshooting

### Virtual Environment Issues

If you encounter virtual environment errors like:
```
error: Project virtual environment directory `/path/.venv` cannot be used because it is not a valid Python environment
```

Fix it by recreating the virtual environment:
```bash
rm -rf .venv
uv sync
```

### Environment Configuration

1. Copy the environment template:
   ```bash
   cp .env.template .env
   ```

2. Fill in your Azure OpenAI credentials in `.env`:
   ```bash
   AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key-here
   ```

3. Start the application:
   ```bash
   uv run uvicorn main:app --reload
   ```

### Testing

Run the test script to validate the assistant management logic:
```bash
python3 test_assistant_management.py
```

### Behavior Without Credentials

The application will start successfully even if Azure OpenAI credentials are not configured. However, when you try to use the proofreading endpoints (`/proofread` or `/proofread-docx`), you will get an error. This allows you to:

1. Start the server and test the UI
2. Check the health endpoint (`/health`)
3. View assistant information (`/admin/assistant-info`)
4. Set up credentials later without restarting the server
