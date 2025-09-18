#!/usr/bin/env python3
"""
ADK Personal Assistant with memg-core Memory

A smart personal assistant with persistent memory for preferences and behavioral guidelines.
"""
import os
from dotenv import load_dotenv

if load_dotenv():
    print("Found and loaded .env file.")
else:
    print(
        "Did not find any .env file. Will use environment variables for Gemini API key."
    )

from google.adk.agents import Agent
from google.genai import types
from .agent_tools.memory import TOOLS

generate_content_config = types.GenerateContentConfig(
    temperature=0.0,
    thinking_config=None,
)

root_agent = Agent(
    name="personal_assistant",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    generate_content_config=generate_content_config,
    description="Smart personal assistant with persistent memory for user preferences and behavioral guidelines.",
    instruction=(
        "You are a helpful personal assistant with persistent memory.\n\n"
        "MEMORY SYSTEM:\n"
        "- Notes: Store user preferences and information (add_note)\n"
        "- Instructions: Store behavioral guidelines for yourself (add_instruction, update_instruction)\n\n"
        "BEHAVIOR:\n"
        "- Search memory first when answering questions (search_memory)\n"
        "- Check your instructions regularly (get_instructions)\n"
        "- Be proactive about remembering user preferences\n"
        "- Keep instructions concise and under 10 total"
    ),
    tools=TOOLS,
)
