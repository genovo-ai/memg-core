# Personal Assistant with memg-core

A smart personal assistant built with Google ADK and memg-core for persistent memory.

## 🎯 What It Does

- **Notes**: Store user preferences and everyday information
- **Instructions**: Save behavioral guidelines for the AI
- **Search**: Find memories using semantic similarity
- **Relationships**: Connect related memories automatically

## 📁 Structure

```
personal_assistant/
├── agent.py                    # ADK agent definition
├── agent_tools/
│   ├── memory.py              # Memory tool functions
│   └── personal_assistant.yaml # Memory schema
└── README.md                  # This file
```

## 🚀 Quick Start

1. **Install dependencies** (from parent `adk/` folder):
   ```bash
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

## 💬 Example Usage

```
User: "Remember I prefer dark mode in all apps"
Assistant: ✅ Note saved with ID: NOTE_ABC123

User: "What are my UI preferences?"
Assistant: I found: "I prefer dark mode in all apps" (Score: 0.92)

User: "Always be concise in your responses"
Assistant: ✅ Instruction saved with ID: INSTRUCTION_DEF456
```

## 🛠️ Available Tools

- `add_note(content, category)` - Store preferences and information
- `add_instruction(summary, details)` - Save AI behavioral guidelines
- `search_memory(query)` - Find relevant memories with graph expansion
- `get_instructions()` - Get all behavioral instructions
- `update_instruction(hrid, summary, details)` - Update existing instructions
- `delete_memory(hrid)` - Remove memories
- `add_relation(from_hrid, to_hrid)` - Connect related memories

## 🧠 Memory Types

### Notes
- **Purpose**: User preferences, observations, everyday information
- **Fields**: `content` (anchor), `category`
- **Example**: "User prefers coffee over tea"

### Instructions
- **Purpose**: Long-term behavioral guidelines for the AI
- **Fields**: `summary` (anchor), `details`
- **Example**: "Always be helpful and concise"

## 🔗 Relationships

All memory types can connect via `RELATED_TO` relationships, enabling the AI to discover related context automatically through graph traversal.
