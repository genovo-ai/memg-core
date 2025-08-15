"""
Default template for MEMG - Maintains backward compatibility with current system
"""

from .base import EntityTypeDefinition, MemoryTemplate, RelationshipTypeDefinition

# Optimized entity types - reduced redundancy, added critical missing types
DEFAULT_ENTITY_TYPES = [
    # Technology Types (Core tech stack)
    EntityTypeDefinition(
        name="TECHNOLOGY",
        description="Programming languages, frameworks, platforms, and technical systems",
        category="TECHNOLOGY",
        extraction_hints=[
            "programming language",
            "framework",
            "platform",
            "technology stack",
            "runtime",
        ],
    ),
    EntityTypeDefinition(
        name="LIBRARY",
        description="Code libraries, packages, modules, dependencies, and databases",
        category="TECHNOLOGY",
        extraction_hints=[
            "library",
            "package",
            "module",
            "dependency",
            "npm",
            "pip",
            "database",
            "storage",
        ],
    ),
    EntityTypeDefinition(
        name="TOOL",
        description="Development tools, IDEs, build systems, and utilities",
        category="TECHNOLOGY",
        extraction_hints=[
            "tool",
            "IDE",
            "editor",
            "build system",
            "utility",
            "CLI",
            "compiler",
        ],
    ),
    # System Types (Architecture & components)
    EntityTypeDefinition(
        name="SERVICE",
        description="Services, APIs, microservices, components, and system services",
        category="SYSTEM",
        extraction_hints=[
            "service",
            "API",
            "microservice",
            "web service",
            "endpoint",
            "component",
            "module",
        ],
    ),
    EntityTypeDefinition(
        name="ARCHITECTURE",
        description="Architectural patterns, system designs, protocols, and structural concepts",
        category="SYSTEM",
        extraction_hints=[
            "architecture",
            "pattern",
            "design",
            "structure",
            "protocol",
            "standard",
            "interface",
        ],
    ),
    # Critical Issue Types (Problems & conflicts)
    EntityTypeDefinition(
        name="ERROR",
        description="Errors, exceptions, bugs, failures, and technical issues",
        category="CRITICAL",
        extraction_hints=[
            "error",
            "exception",
            "bug",
            "failure",
            "crash",
            "issue",
            "broken",
            "failing",
        ],
    ),
    EntityTypeDefinition(
        name="CONFLICT",
        description="Version conflicts, dependency conflicts, merge conflicts, and \
        compatibility issues",
        category="CRITICAL",
        extraction_hints=[
            "conflict",
            "version conflict",
            "dependency conflict",
            "merge conflict",
            "compatibility",
            "incompatible",
        ],
    ),
    EntityTypeDefinition(
        name="VULNERABILITY",
        description="Security vulnerabilities, CVEs, attack vectors, and security concerns",
        category="CRITICAL",
        extraction_hints=[
            "vulnerability",
            "security",
            "CVE",
            "exploit",
            "attack",
            "breach",
            "unsafe",
        ],
    ),
    EntityTypeDefinition(
        name="PERFORMANCE",
        description="Performance issues, bottlenecks, slow queries, and optimization needs",
        category="CRITICAL",
        extraction_hints=[
            "performance",
            "slow",
            "bottleneck",
            "optimization",
            "latency",
            "memory leak",
            "timeout",
        ],
    ),
    # Solution Types
    EntityTypeDefinition(
        name="SOLUTION",
        description="Solutions, fixes, resolutions, workarounds, and problem-solving approaches",
        category="SOLUTION",
        extraction_hints=[
            "solution",
            "fix",
            "resolution",
            "workaround",
            "answer",
            "patch",
            "hotfix",
        ],
    ),
    EntityTypeDefinition(
        name="DEPRECATION",
        description="Deprecated APIs, legacy code, sunset warnings, and migration paths",
        category="SOLUTION",
        extraction_hints=[
            "deprecated",
            "legacy",
            "sunset",
            "migration",
            "upgrade",
            "obsolete",
            "end-of-life",
        ],
    ),
    # Domain Types (Concepts & methods)
    EntityTypeDefinition(
        name="METHOD",
        description="Methods, procedures, algorithms, techniques, concepts, and approaches",
        category="DOMAIN",
        extraction_hints=[
            "method",
            "procedure",
            "algorithm",
            "technique",
            "approach",
            "concept",
            "principle",
            "strategy",
        ],
    ),
    EntityTypeDefinition(
        name="CONFIGURATION",
        description="Configuration files, settings, parameters, and environment setup",
        category="DOMAIN",
        extraction_hints=[
            "configuration",
            "config",
            "settings",
            "parameters",
            "environment",
            "setup",
            "deployment",
        ],
    ),
    # Task Management Types (Project management & workflow)
    EntityTypeDefinition(
        name="TICKET",
        description="Individual work items, user stories, bugs, tasks, and issues",
        category="TASK_MANAGEMENT",
        extraction_hints=[
            "ticket",
            "story",
            "user story",
            "bug",
            "task",
            "issue",
            "work item",
            "feature request",
            "defect",
        ],
    ),
    EntityTypeDefinition(
        name="EPIC",
        description="Large initiatives, features, projects, and collections of related work",
        category="TASK_MANAGEMENT",
        extraction_hints=[
            "epic",
            "feature",
            "project",
            "initiative",
            "theme",
            "program",
            "large feature",
            "major work",
        ],
    ),
    EntityTypeDefinition(
        name="MILESTONE",
        description="Project milestones, releases, deadlines, and significant events",
        category="TASK_MANAGEMENT",
        extraction_hints=[
            "milestone",
            "release",
            "version",
            "deadline",
            "target date",
            "delivery",
            "launch",
            "go-live",
        ],
    ),
    EntityTypeDefinition(
        name="SPRINT",
        description="Time-boxed development cycles, iterations, and work periods",
        category="TASK_MANAGEMENT",
        extraction_hints=[
            "sprint",
            "iteration",
            "cycle",
            "timebox",
            "development cycle",
            "work period",
            "scrum sprint",
        ],
    ),
    EntityTypeDefinition(
        name="BOARD",
        description="Project boards, workspaces, kanban boards, and work organization",
        category="TASK_MANAGEMENT",
        extraction_hints=[
            "board",
            "workspace",
            "project board",
            "kanban board",
            "scrum board",
            "work board",
            "team board",
        ],
    ),
]

# Optimized relationship types - reduced redundancy, added critical relationships
DEFAULT_RELATIONSHIP_TYPES = [
    # Core relationships (structure & usage)
    RelationshipTypeDefinition(
        name="USES",
        description="Entity uses or depends on another entity",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="PART_OF",
        description="Entity is a component or part of another entity",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="RELATES_TO",
        description="General relationship between entities",
        directionality="BIDIRECTIONAL",
    ),
    # Critical problem relationships
    RelationshipTypeDefinition(
        name="CAUSES",
        description="Entity causes another entity (error causation, triggers)",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="FIXES",
        description="Entity fixes or resolves another entity",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="CONFLICTS_WITH",
        description="Entity conflicts with another entity (version conflicts, incompatibilities)",
        directionality="BIDIRECTIONAL",
    ),
    # Evolution & replacement relationships
    RelationshipTypeDefinition(
        name="REPLACES",
        description="Entity replaces or supersedes another entity",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="SIMILAR_TO",
        description="Entities are similar, comparable, or alternatives",
        directionality="BIDIRECTIONAL",
    ),
    # Task Management Relationships (Project workflow & dependencies)
    RelationshipTypeDefinition(
        name="BELONGS_TO",
        description="Task belongs to epic, milestone, board, or sprint",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="BLOCKS",
        description="Task blocks another task from completion",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="DEPENDS_ON",
        description="Task depends on completion of another task",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="IMPLEMENTS",
        description="Task implements a feature, requirement, or solution",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="SUBTASK_OF",
        description="Task is a subtask or child of a larger task",
        directionality="DIRECTIONAL",
    ),
    RelationshipTypeDefinition(
        name="LINKED_TO_CODE",
        description="Task is linked to specific code location or file",
        directionality="DIRECTIONAL",
    ),
]

# Default extraction prompts
DEFAULT_EXTRACTION_PROMPTS = {
    "entity_extraction": """
You are an AI assistant specialized in extracting structured information from text.
Your task is to identify entities and relationships from the given content.

Focus on extracting:
- TECHNOLOGY: Programming languages, frameworks, platforms, runtimes
- LIBRARY: Packages, modules, dependencies, databases, storage systems
- TOOL: IDEs, compilers, build systems, utilities, CLIs
- SERVICE: APIs, microservices, components, endpoints
- ARCHITECTURE: Design patterns, protocols, standards, interfaces
- ERROR: Bugs, exceptions, failures, crashes, broken functionality
- CONFLICT: Version conflicts, dependency issues, merge conflicts, incompatibilities
- VULNERABILITY: Security issues, CVEs, exploits, attack vectors
- PERFORMANCE: Bottlenecks, slow queries, optimization needs, memory leaks
- SOLUTION: Fixes, patches, resolutions, workarounds, hotfixes
- DEPRECATION: Legacy code, deprecated APIs, migration paths, obsolete features
- METHOD: Algorithms, procedures, techniques, concepts, strategies
- CONFIGURATION: Config files, settings, environment setup, deployment parameters
- TICKET: Individual work items, user stories, bugs, tasks, issues
- EPIC: Large initiatives, features, projects, collections of related work
- MILESTONE: Project milestones, releases, deadlines, significant events
- SPRINT: Time-boxed development cycles, iterations, work periods
- BOARD: Project boards, workspaces, kanban boards, work organization

For relationships, focus on:
- USES: Dependencies and usage patterns
- CAUSES: Error causation and trigger chains
- FIXES: Solutions resolving problems
- CONFLICTS_WITH: Incompatibilities and version conflicts
- REPLACES: Deprecation and migration relationships
- PART_OF: Component hierarchies
- SIMILAR_TO: Alternatives and comparable options
- BELONGS_TO: Tasks belong to epics, milestones, boards, or sprints
- BLOCKS: Tasks blocking other tasks from completion
- DEPENDS_ON: Task dependencies and prerequisites
- IMPLEMENTS: Tasks implementing features or requirements
- SUBTASK_OF: Task hierarchies and parent-child relationships
- LINKED_TO_CODE: Tasks linked to specific code locations

For each entity, provide:
- name: Clear, concise entity name
- type: One of the predefined entity types above
- description: Brief description of the entity
- confidence: Your confidence in this extraction (0.0 to 1.0)

Prioritize critical issues like conflicts, vulnerabilities, and performance problems.
"""
}

# Create the default template
DEFAULT_TEMPLATE = MemoryTemplate(
    name="default",
    display_name="Default Template",
    description="Default MEMG template maintaining backward compatibility with current system",
    version="1.0.0",
    entity_types=DEFAULT_ENTITY_TYPES,
    relationship_types=DEFAULT_RELATIONSHIP_TYPES,
    extraction_prompts=DEFAULT_EXTRACTION_PROMPTS,
    search_filters={},
    metadata={
        "created_by": "MEMG Core Team",
        "compatibility": "v0.3.0",
        "use_cases": ["general", "technical_documentation", "problem_solving"],
    },
)
