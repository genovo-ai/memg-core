# ADK + memg-core Integration

Google ADK agents with memg-core persistent memory integration.

## 🎯 What's Here

- **Personal Assistant**: Smart assistant with persistent memory (`personal_assistant/`)
- **Direct Integration**: Uses `MemgClient` without MCP overhead
- **Production Ready**: Error handling, logging, and proper configuration

## 🚀 Quick Start

1. **Install dependencies**:
   ```bash
   cd experiments/adk
   pip install -r requirements.txt
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Add your Google API key to .env
   ```

3. **Run the agent**:
   ```bash
   adk web
   # Open http://localhost:8000
   # Select "personal_assistant"
   ```

## 📁 Projects

### Personal Assistant (`personal_assistant/`)
Smart assistant with persistent memory for notes and instructions.

**Features:**
- Store user preferences and behavioral guidelines
- Semantic search across memories
- Graph relationships between memories
- Update and manage instructions

**Memory Types:**
- **Notes**: User preferences (`content`, `category`)
- **Instructions**: AI behavioral guidelines (`summary`, `details`)

## 🛠️ Integration Pattern

```python
# Initialize memg-core client
memg_client = MemgClient(yaml_path="schema.yaml", db_path="./db")

# ADK tool function
def add_note(content: str, category: str = None) -> Dict[str, Any]:
    try:
        payload = {"content": content}
        if category:
            payload["category"] = category
        hrid = memg_client.add_memory("note", payload, "adk_user")
        return {"status": "success", "hrid": hrid}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ADK agent
root_agent = Agent(
    name="personal_assistant",
    model="gemini-2.5-flash",
    tools=[add_note, search_memory, ...]
)
```

## 🔧 Configuration

**Environment Variables:**
```bash
GOOGLE_API_KEY=your_api_key_here
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

**Get API Key:** https://aistudio.google.com/app/apikey

## 📚 Learn More

- **ADK Documentation**: https://google.github.io/adk-docs/
- **memg-core Repository**: See main README for core concepts
- **MCP Integration**: `../mcp/` for MCP server patterns
