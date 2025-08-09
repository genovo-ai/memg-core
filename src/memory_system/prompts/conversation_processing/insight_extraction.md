You are extracting high-value professional insights from conversations. Focus on creating COHESIVE, CONTEXT-RICH insights that capture complete understanding rather than fragmenting information.

PRINCIPLES FOR INSIGHT EXTRACTION:

1. COHESIVE CONTEXT
- Combine related information into unified insights
- Maintain relationships between connected concepts
- Include relevant context and rationale
- Preserve the "story" behind decisions and preferences

2. MEANINGFUL SCOPE
- Each insight should be a complete, self-contained understanding
- Include enough context to be independently valuable
- Avoid splitting naturally connected information
- Capture the full picture of a preference or approach

3. RICH TECHNICAL DETAIL
- Include specific technologies, versions, and configurations
- Capture complete technical stacks, not isolated components
- Document full workflows, not just individual steps
- Preserve technical rationale and trade-off decisions

4. HOLISTIC UNDERSTANDING
Instead of fragmenting like this:
❌ "Uses Python for backend"
❌ "Prefers X web framework"
❌ "Implements async endpoints"

Create cohesive insights like this:
✅ "Builds backend services using Python with a lightweight async web framework, leveraging async endpoints for high-performance APIs. Chose this stack for its strong typing support, async capabilities, and automatic OpenAPI documentation generation."

FOCUS AREAS:

1. TECHNICAL ECOSYSTEM
- Complete technology stacks and how they work together
- Full development and deployment workflows
- Comprehensive testing and quality approaches
- End-to-end architectural decisions

2. PROFESSIONAL METHODOLOGY
- Complete problem-solving approaches
- Full project organization strategies
- Comprehensive development practices
- End-to-end workflow preferences

3. DOMAIN EXPERTISE
- Complete understanding of specific domains
- Full context of experience areas
- Comprehensive skill sets
- Deep knowledge areas with context

4. WORKING PREFERENCES
- Complete picture of work style
- Full context of tool choices
- Comprehensive quality standards
- Detailed rationale for preferences

Extract 3-4 COMPREHENSIVE insights as JSON. Each insight should be:
- COMPLETE (capture full context and relationships)
- COHESIVE (maintain natural connections)
- VALUABLE (include specific details and rationale)

```json
{
  "conversation_id": "string",
  "title": "actual conversation title from the conversation",
  "insights": [
    {
      "content": "Rich, detailed insight that maintains complete context. Include the full picture: what they do, how they do it, why they chose this approach, and how it connects to their broader technical ecosystem. Preserve relationships between tools, practices, and preferences.",
      "category": "technology|methodology|preference|skill|experience|domain_knowledge",
      "confidence": 0.8
    }
  ],
  "summary": "Comprehensive 3-4 sentence summary capturing the complete technical context, key decisions with rationale, problems solved with approach, and how this conversation connects to their broader technical profile."
}
```

Remember:
- Keep related information together
- Maintain context and relationships
- Include complete rationale and background
- Create self-contained, valuable insights
