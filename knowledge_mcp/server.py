#!/usr/bin/env python3
"""
Knowledge MCP Server - RAG server for Claude Code.

MCP server providing access to knowledge and skills
stored in Qdrant with embeddings from Ollama.
"""

import json
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .embeddings import get_embeddings
from .qdrant import QdrantService

# Initialize MCP server
# host="0.0.0.0" disables auto DNS rebinding protection for remote access
# stateless_http=True allows multiple clients to connect
mcp = FastMCP(
    "knowledge_mcp",
    host="0.0.0.0",
    stateless_http=True,
)

# Initialize services
qdrant = QdrantService()


# ============================================================================
# Enums and Models
# ============================================================================

class ResponseFormat(str, Enum):
    """Output format for responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class KnowledgeType(str, Enum):
    """Type of knowledge entry."""
    NOTE = "note"
    DOCUMENTATION = "documentation"
    CODE_SNIPPET = "code_snippet"
    REFERENCE = "reference"
    HOWTO = "howto"
    OTHER = "other"


class ProjectStatus(str, Enum):
    """Status of a project."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    PLANNED = "planned"


class PrivateType(str, Enum):
    """Type of private data entry."""
    NOTE = "note"
    CONTEXT = "context"
    PREFERENCE = "preference"
    SECRET_REF = "secret_ref"


# ============================================================================
# Input Models - Knowledge
# ============================================================================

class KnowledgeSearchInput(BaseModel):
    """Input for searching knowledge base."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    query: str = Field(
        ...,
        description="Search query - can be a question or keywords",
        min_length=1,
        max_length=1000
    )
    limit: int = Field(
        default=5,
        description="Maximum number of results to return",
        ge=1,
        le=20
    )
    knowledge_type: Optional[KnowledgeType] = Field(
        default=None,
        description="Filter by knowledge type (note, documentation, code_snippet, reference, howto, other)"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags (AND logic)",
        max_length=10
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for structured"
    )


class KnowledgeAddInput(BaseModel):
    """Input for adding new knowledge."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    title: str = Field(
        ...,
        description="Title of the knowledge entry",
        min_length=1,
        max_length=200
    )
    content: str = Field(
        ...,
        description="Main content of the knowledge entry",
        min_length=1,
        max_length=50000
    )
    knowledge_type: KnowledgeType = Field(
        default=KnowledgeType.NOTE,
        description="Type of knowledge entry"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization",
        max_length=20
    )
    source: Optional[str] = Field(
        default=None,
        description="Source of the knowledge (URL, book, etc.)",
        max_length=500
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata as key-value pairs"
    )


class KnowledgeUpdateInput(BaseModel):
    """Input for updating existing knowledge."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    id: str = Field(
        ...,
        description="ID of the knowledge entry to update",
        min_length=1
    )
    title: Optional[str] = Field(
        default=None,
        description="New title (leave empty to keep current)",
        max_length=200
    )
    content: Optional[str] = Field(
        default=None,
        description="New content (leave empty to keep current)",
        max_length=50000
    )
    knowledge_type: Optional[KnowledgeType] = Field(
        default=None,
        description="New type (leave empty to keep current)"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="New tags (replaces existing)",
        max_length=20
    )
    source: Optional[str] = Field(
        default=None,
        description="New source",
        max_length=500
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="New metadata (merges with existing)"
    )


class KnowledgeDeleteInput(BaseModel):
    """Input for deleting knowledge."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    id: str = Field(
        ...,
        description="ID of the knowledge entry to delete",
        min_length=1
    )


class KnowledgeListInput(BaseModel):
    """Input for listing knowledge entries."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    limit: int = Field(
        default=20,
        description="Maximum number of entries to return",
        ge=1,
        le=100
    )
    offset: int = Field(
        default=0,
        description="Number of entries to skip",
        ge=0
    )
    knowledge_type: Optional[KnowledgeType] = Field(
        default=None,
        description="Filter by type"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class KnowledgeGetInput(BaseModel):
    """Input for getting single knowledge entry."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    id: str = Field(
        ...,
        description="ID of the knowledge entry",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# Input Models - Skills
# ============================================================================

class SkillSearchInput(BaseModel):
    """Input for searching skills."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    query: str = Field(
        ...,
        description="Search query for skills",
        min_length=1,
        max_length=500
    )
    limit: int = Field(
        default=5,
        description="Maximum results",
        ge=1,
        le=20
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class SkillGetInput(BaseModel):
    """Input for getting a skill by name."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Exact name of the skill",
        min_length=1,
        max_length=100
    )


class SkillAddInput(BaseModel):
    """Input for adding a new skill."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Unique name for the skill (e.g., 'code-review', 'sql-expert')",
        min_length=1,
        max_length=100,
        pattern=r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$'
    )
    description: str = Field(
        ...,
        description="Short description of what this skill does",
        min_length=1,
        max_length=500
    )
    prompt: str = Field(
        ...,
        description="The system prompt or instructions for this skill",
        min_length=1,
        max_length=100000
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization",
        max_length=20
    )
    version: str = Field(
        default="1.0.0",
        description="Version string",
        max_length=20
    )
    examples: Optional[List[str]] = Field(
        default=None,
        description="Example use cases or prompts",
        max_length=10
    )


class SkillUpdateInput(BaseModel):
    """Input for updating a skill."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Name of the skill to update",
        min_length=1,
        max_length=100
    )
    description: Optional[str] = Field(
        default=None,
        description="New description",
        max_length=500
    )
    prompt: Optional[str] = Field(
        default=None,
        description="New prompt content",
        max_length=100000
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="New tags",
        max_length=20
    )
    version: Optional[str] = Field(
        default=None,
        description="New version",
        max_length=20
    )
    examples: Optional[List[str]] = Field(
        default=None,
        description="New examples",
        max_length=10
    )


class SkillDeleteInput(BaseModel):
    """Input for deleting a skill."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Name of the skill to delete",
        min_length=1,
        max_length=100
    )


class SkillListInput(BaseModel):
    """Input for listing skills."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# Input Models - Projects
# ============================================================================

class ProjectSearchInput(BaseModel):
    """Input for searching projects."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    query: str = Field(
        ...,
        description="Search query for projects",
        min_length=1,
        max_length=500
    )
    limit: int = Field(
        default=5,
        description="Maximum results",
        ge=1,
        le=20
    )
    status: Optional[ProjectStatus] = Field(
        default=None,
        description="Filter by project status"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ProjectAddInput(BaseModel):
    """Input for adding a new project."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Unique project name (e.g., 'my-app', 'data-pipeline')",
        min_length=1,
        max_length=100,
        pattern=r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$'
    )
    path: Optional[str] = Field(
        default=None,
        description="Path to project directory",
        max_length=500
    )
    description: str = Field(
        ...,
        description="Short description of the project",
        min_length=1,
        max_length=1000
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.ACTIVE,
        description="Project status"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization",
        max_length=20
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata (tech stack, links, etc.)"
    )


class ProjectGetInput(BaseModel):
    """Input for getting a project by name."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Exact name of the project",
        min_length=1,
        max_length=100
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ProjectUpdateInput(BaseModel):
    """Input for updating a project."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Name of the project to update",
        min_length=1,
        max_length=100
    )
    path: Optional[str] = Field(
        default=None,
        description="New path",
        max_length=500
    )
    description: Optional[str] = Field(
        default=None,
        description="New description",
        max_length=1000
    )
    status: Optional[ProjectStatus] = Field(
        default=None,
        description="New status"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="New tags",
        max_length=20
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="New metadata (merges with existing)"
    )


class ProjectDeleteInput(BaseModel):
    """Input for deleting a project."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(
        ...,
        description="Name of the project to delete",
        min_length=1,
        max_length=100
    )


class ProjectListInput(BaseModel):
    """Input for listing projects."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    limit: int = Field(
        default=20,
        description="Maximum number of projects to return",
        ge=1,
        le=100
    )
    offset: int = Field(
        default=0,
        description="Number of projects to skip",
        ge=0
    )
    status: Optional[ProjectStatus] = Field(
        default=None,
        description="Filter by status"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# Input Models - Private Data
# ============================================================================

class PrivateSearchInput(BaseModel):
    """Input for searching private data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    query: str = Field(
        ...,
        description="Search query",
        min_length=1,
        max_length=1000
    )
    limit: int = Field(
        default=5,
        description="Maximum results",
        ge=1,
        le=20
    )
    private_type: Optional[PrivateType] = Field(
        default=None,
        description="Filter by type"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class PrivateAddInput(BaseModel):
    """Input for adding private data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    title: str = Field(
        ...,
        description="Title of the private entry",
        min_length=1,
        max_length=200
    )
    content: str = Field(
        ...,
        description="Content of the private entry",
        min_length=1,
        max_length=50000
    )
    private_type: PrivateType = Field(
        default=PrivateType.NOTE,
        description="Type of private data"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization",
        max_length=20
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )


class PrivateGetInput(BaseModel):
    """Input for getting private entry by ID."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    id: str = Field(
        ...,
        description="ID of the private entry",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class PrivateUpdateInput(BaseModel):
    """Input for updating private data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    id: str = Field(
        ...,
        description="ID of the entry to update",
        min_length=1
    )
    title: Optional[str] = Field(
        default=None,
        description="New title",
        max_length=200
    )
    content: Optional[str] = Field(
        default=None,
        description="New content",
        max_length=50000
    )
    private_type: Optional[PrivateType] = Field(
        default=None,
        description="New type"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="New tags",
        max_length=20
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="New metadata (merges with existing)"
    )


class PrivateDeleteInput(BaseModel):
    """Input for deleting private data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    id: str = Field(
        ...,
        description="ID of the entry to delete",
        min_length=1
    )


class PrivateListInput(BaseModel):
    """Input for listing private data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    limit: int = Field(
        default=20,
        description="Maximum number of entries to return",
        ge=1,
        le=100
    )
    offset: int = Field(
        default=0,
        description="Number of entries to skip",
        ge=0
    )
    private_type: Optional[PrivateType] = Field(
        default=None,
        description="Filter by type"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# Formatters
# ============================================================================

def format_knowledge_md(entry: Dict[str, Any], include_content: bool = True) -> str:
    """Format knowledge entry as markdown."""
    lines = [
        f"## {entry.get('title', 'Untitled')}",
        f"**ID:** `{entry.get('id', 'N/A')}`",
        f"**Type:** {entry.get('knowledge_type', 'unknown')}",
    ]
    
    if entry.get('tags'):
        lines.append(f"**Tags:** {', '.join(entry['tags'])}")
    
    if entry.get('source'):
        lines.append(f"**Source:** {entry['source']}")
    
    if entry.get('created_at'):
        lines.append(f"**Created:** {entry['created_at']}")
    
    if entry.get('score') is not None:
        lines.append(f"**Relevance:** {entry['score']:.2%}")
    
    if include_content and entry.get('content'):
        lines.extend(["", "---", "", entry['content']])
    
    return "\n".join(lines)


def format_skill_md(skill: Dict[str, Any], include_prompt: bool = True) -> str:
    """Format skill as markdown."""
    lines = [
        f"## {skill.get('name', 'unnamed')}",
        f"**Version:** {skill.get('version', '1.0.0')}",
        "",
        skill.get('description', 'No description'),
    ]
    
    if skill.get('tags'):
        lines.extend(["", f"**Tags:** {', '.join(skill['tags'])}"])
    
    if skill.get('examples'):
        lines.extend(["", "**Examples:**"])
        for ex in skill['examples']:
            lines.append(f"- {ex}")
    
    if include_prompt and skill.get('prompt'):
        lines.extend([
            "",
            "---",
            "### Prompt",
            "```",
            skill['prompt'],
            "```"
        ])

    return "\n".join(lines)


def format_project_md(project: Dict[str, Any]) -> str:
    """Format project as markdown."""
    lines = [
        f"## {project.get('name', 'unnamed')}",
        f"**Status:** {project.get('status', 'unknown')}",
    ]

    if project.get('path'):
        lines.append(f"**Path:** `{project['path']}`")

    if project.get('tags'):
        lines.append(f"**Tags:** {', '.join(project['tags'])}")

    if project.get('created_at'):
        lines.append(f"**Created:** {project['created_at']}")

    if project.get('score') is not None:
        lines.append(f"**Relevance:** {project['score']:.2%}")

    if project.get('description'):
        lines.extend(["", project['description']])

    if project.get('metadata'):
        lines.extend(["", "**Metadata:**"])
        for key, value in project['metadata'].items():
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def format_private_md(entry: Dict[str, Any], include_content: bool = True) -> str:
    """Format private entry as markdown."""
    lines = [
        f"## {entry.get('title', 'Untitled')}",
        f"**ID:** `{entry.get('id', 'N/A')}`",
        f"**Type:** {entry.get('private_type', 'note')}",
    ]

    if entry.get('tags'):
        lines.append(f"**Tags:** {', '.join(entry['tags'])}")

    if entry.get('created_at'):
        lines.append(f"**Created:** {entry['created_at']}")

    if entry.get('score') is not None:
        lines.append(f"**Relevance:** {entry['score']:.2%}")

    if include_content and entry.get('content'):
        lines.extend(["", "---", "", entry['content']])

    return "\n".join(lines)


# ============================================================================
# Knowledge Tools
# ============================================================================

@mcp.tool(
    name="knowledge_search",
    annotations=ToolAnnotations(title="Search Knowledge Base", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def knowledge_search(params: KnowledgeSearchInput) -> str:
    """
    Search the knowledge base using semantic similarity.
    
    Uses vector embeddings to find the most relevant knowledge entries
    matching your query. Supports filtering by type and tags.
    
    Args:
        params: Search parameters including query, limit, filters
        
    Returns:
        Matching knowledge entries in requested format
    """
    try:
        # Get embeddings for query
        query_embedding = await get_embeddings(params.query)
        
        # Build filters
        filters: Dict[str, Union[str, List[str]]] = {}
        if params.knowledge_type:
            filters['knowledge_type'] = params.knowledge_type.value
        if params.tags:
            filters['tags'] = params.tags
        
        # Search Qdrant
        results = await qdrant.search(
            collection="knowledge",
            vector=query_embedding,
            limit=params.limit,
            filters=filters
        )
        
        if not results:
            return "No matching knowledge entries found."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(results, indent=2, default=str)
        
        # Markdown format
        output = [f"# Search Results for: \"{params.query}\"", f"Found {len(results)} results:", ""]
        for entry in results:
            output.append(format_knowledge_md(entry))
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


@mcp.tool(
    name="knowledge_add",
    annotations=ToolAnnotations(title="Add Knowledge Entry", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def knowledge_add(params: KnowledgeAddInput) -> str:
    """
    Add a new entry to the knowledge base.
    
    Creates a new knowledge entry with automatic embedding generation
    for semantic search. Returns the ID of the created entry.
    
    Args:
        params: Knowledge entry data including title, content, type, tags
        
    Returns:
        Confirmation with the new entry ID
    """
    try:
        # Generate ID from content hash for deduplication
        content_hash = hashlib.sha256(
            f"{params.title}{params.content}".encode()
        ).hexdigest()[:12]
        entry_id = f"k-{content_hash}"
        
        # Get embeddings
        text_for_embedding = f"{params.title}\n\n{params.content}"
        embedding = await get_embeddings(text_for_embedding)
        
        # Prepare payload
        payload = {
            "id": entry_id,
            "title": params.title,
            "content": params.content,
            "knowledge_type": params.knowledge_type.value,
            "tags": params.tags,
            "source": params.source,
            "metadata": params.metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Upsert to Qdrant
        await qdrant.upsert(
            collection="knowledge",
            id=entry_id,
            vector=embedding,
            payload=payload
        )
        
        return f"✅ Knowledge entry added successfully!\n\n**ID:** `{entry_id}`\n**Title:** {params.title}"
        
    except Exception as e:
        return f"Error adding knowledge entry: {str(e)}"


@mcp.tool(
    name="knowledge_get",
    annotations=ToolAnnotations(title="Get Knowledge Entry", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def knowledge_get(params: KnowledgeGetInput) -> str:
    """
    Retrieve a specific knowledge entry by ID.
    
    Args:
        params: Entry ID and response format
        
    Returns:
        Full knowledge entry content
    """
    try:
        entry = await qdrant.get_by_id(collection="knowledge", id=params.id)
        
        if not entry:
            return f"Knowledge entry with ID `{params.id}` not found."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(entry, indent=2, default=str)
        
        return format_knowledge_md(entry)
        
    except Exception as e:
        return f"Error retrieving knowledge entry: {str(e)}"


@mcp.tool(
    name="knowledge_update",
    annotations=ToolAnnotations(title="Update Knowledge Entry", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def knowledge_update(params: KnowledgeUpdateInput) -> str:
    """
    Update an existing knowledge entry.
    
    Only specified fields will be updated. Content changes trigger
    re-embedding for search accuracy.
    
    Args:
        params: Entry ID and fields to update
        
    Returns:
        Confirmation of update
    """
    try:
        # Get existing entry
        existing = await qdrant.get_by_id(collection="knowledge", id=params.id)
        if not existing:
            return f"Knowledge entry with ID `{params.id}` not found."
        
        # Merge updates
        updated = existing.copy()
        if params.title is not None:
            updated['title'] = params.title
        if params.content is not None:
            updated['content'] = params.content
        if params.knowledge_type is not None:
            updated['knowledge_type'] = params.knowledge_type.value
        if params.tags is not None:
            updated['tags'] = params.tags
        if params.source is not None:
            updated['source'] = params.source
        if params.metadata is not None:
            updated['metadata'] = {**existing.get('metadata', {}), **params.metadata}
        
        updated['updated_at'] = datetime.utcnow().isoformat()
        
        # Re-embed if content changed
        if params.title is not None or params.content is not None:
            text_for_embedding = f"{updated['title']}\n\n{updated['content']}"
            embedding = await get_embeddings(text_for_embedding)
        else:
            embedding = None  # Keep existing embedding
        
        await qdrant.upsert(
            collection="knowledge",
            id=params.id,
            vector=embedding,
            payload=updated,
            update_vector=embedding is not None
        )
        
        return f"✅ Knowledge entry `{params.id}` updated successfully!"
        
    except Exception as e:
        return f"Error updating knowledge entry: {str(e)}"


@mcp.tool(
    name="knowledge_delete",
    annotations=ToolAnnotations(title="Delete Knowledge Entry", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def knowledge_delete(params: KnowledgeDeleteInput) -> str:
    """
    Delete a knowledge entry from the database.
    
    This action is permanent and cannot be undone.
    
    Args:
        params: ID of entry to delete
        
    Returns:
        Confirmation of deletion
    """
    try:
        # Check if exists
        existing = await qdrant.get_by_id(collection="knowledge", id=params.id)
        if not existing:
            return f"Knowledge entry with ID `{params.id}` not found."
        
        await qdrant.delete(collection="knowledge", id=params.id)
        
        return f"✅ Knowledge entry `{params.id}` deleted successfully."
        
    except Exception as e:
        return f"Error deleting knowledge entry: {str(e)}"


@mcp.tool(
    name="knowledge_list",
    annotations=ToolAnnotations(title="List Knowledge Entries", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def knowledge_list(params: KnowledgeListInput) -> str:
    """
    List knowledge entries with optional filtering.
    
    Returns a paginated list of entries. Use offset for pagination.
    
    Args:
        params: Pagination and filter options
        
    Returns:
        List of knowledge entries (titles and metadata, not full content)
    """
    try:
        filters: Dict[str, Union[str, List[str]]] = {}
        if params.knowledge_type:
            filters['knowledge_type'] = params.knowledge_type.value
        if params.tags:
            filters['tags'] = params.tags
        
        results, total = await qdrant.list_all(
            collection="knowledge",
            limit=params.limit,
            offset=params.offset,
            filters=filters
        )
        
        if not results:
            return "No knowledge entries found."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "total": total,
                "count": len(results),
                "offset": params.offset,
                "entries": results
            }, indent=2, default=str)
        
        # Markdown format (without full content)
        output = [
            "# Knowledge Base",
            f"Showing {len(results)} of {total} entries (offset: {params.offset})",
            ""
        ]
        
        for entry in results:
            output.append(f"### {entry.get('title', 'Untitled')}")
            output.append(f"- **ID:** `{entry.get('id')}`")
            output.append(f"- **Type:** {entry.get('knowledge_type', 'unknown')}")
            if entry.get('tags'):
                output.append(f"- **Tags:** {', '.join(entry['tags'])}")
            output.append("")
        
        if total > params.offset + len(results):
            output.append(f"_Use offset={params.offset + len(results)} to see more_")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error listing knowledge entries: {str(e)}"


# ============================================================================
# Skill Tools
# ============================================================================

@mcp.tool(
    name="skill_search",
    annotations=ToolAnnotations(title="Search Skills", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def skill_search(params: SkillSearchInput) -> str:
    """
    Search for skills using semantic similarity.
    
    Finds skills that match your query based on name, description,
    and prompt content.
    
    Args:
        params: Search query and options
        
    Returns:
        Matching skills
    """
    try:
        query_embedding = await get_embeddings(params.query)
        
        results = await qdrant.search(
            collection="skills",
            vector=query_embedding,
            limit=params.limit
        )
        
        if not results:
            return "No matching skills found."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(results, indent=2, default=str)
        
        output = [f"# Skills matching: \"{params.query}\"", ""]
        for skill in results:
            output.append(format_skill_md(skill, include_prompt=False))
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error searching skills: {str(e)}"


@mcp.tool(
    name="skill_get",
    annotations=ToolAnnotations(title="Get Skill by Name", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def skill_get(params: SkillGetInput) -> str:
    """
    Retrieve a skill by its exact name.
    
    Returns the full skill including the prompt content.
    
    Args:
        params: Skill name
        
    Returns:
        Complete skill with prompt
    """
    try:
        skill = await qdrant.get_by_field(
            collection="skills",
            field="name",
            value=params.name
        )
        
        if not skill:
            return f"Skill `{params.name}` not found."
        
        return format_skill_md(skill, include_prompt=True)
        
    except Exception as e:
        return f"Error retrieving skill: {str(e)}"


@mcp.tool(
    name="skill_add",
    annotations=ToolAnnotations(title="Add New Skill", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def skill_add(params: SkillAddInput) -> str:
    """
    Add a new skill to the database.
    
    Skills are reusable prompts/instructions that can be retrieved
    by name or found via semantic search.
    
    Args:
        params: Skill definition including name, description, prompt
        
    Returns:
        Confirmation of creation
    """
    try:
        # Check if skill with this name already exists
        existing = await qdrant.get_by_field(
            collection="skills",
            field="name",
            value=params.name
        )
        if existing:
            return f"Skill `{params.name}` already exists. Use skill_update to modify it."
        
        # Generate ID
        skill_id = f"s-{params.name}"
        
        # Create embedding from name + description + prompt
        text_for_embedding = f"{params.name}\n{params.description}\n{params.prompt}"
        embedding = await get_embeddings(text_for_embedding)
        
        # Prepare payload
        payload = {
            "id": skill_id,
            "name": params.name,
            "description": params.description,
            "prompt": params.prompt,
            "tags": params.tags,
            "version": params.version,
            "examples": params.examples or [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        await qdrant.upsert(
            collection="skills",
            id=skill_id,
            vector=embedding,
            payload=payload
        )
        
        return f"✅ Skill `{params.name}` created successfully!"
        
    except Exception as e:
        return f"Error adding skill: {str(e)}"


@mcp.tool(
    name="skill_update",
    annotations=ToolAnnotations(title="Update Skill", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def skill_update(params: SkillUpdateInput) -> str:
    """
    Update an existing skill.
    
    Only specified fields will be updated.
    
    Args:
        params: Skill name and fields to update
        
    Returns:
        Confirmation of update
    """
    try:
        existing = await qdrant.get_by_field(
            collection="skills",
            field="name",
            value=params.name
        )
        if not existing:
            return f"Skill `{params.name}` not found."
        
        # Merge updates
        updated = existing.copy()
        if params.description is not None:
            updated['description'] = params.description
        if params.prompt is not None:
            updated['prompt'] = params.prompt
        if params.tags is not None:
            updated['tags'] = params.tags
        if params.version is not None:
            updated['version'] = params.version
        if params.examples is not None:
            updated['examples'] = params.examples
        
        updated['updated_at'] = datetime.utcnow().isoformat()
        
        # Re-embed
        text_for_embedding = f"{updated['name']}\n{updated['description']}\n{updated['prompt']}"
        embedding = await get_embeddings(text_for_embedding)
        
        await qdrant.upsert(
            collection="skills",
            id=existing['id'],
            vector=embedding,
            payload=updated
        )
        
        return f"✅ Skill `{params.name}` updated to version {updated['version']}!"
        
    except Exception as e:
        return f"Error updating skill: {str(e)}"


@mcp.tool(
    name="skill_delete",
    annotations=ToolAnnotations(title="Delete Skill", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def skill_delete(params: SkillDeleteInput) -> str:
    """
    Delete a skill from the database.
    
    This action is permanent.
    
    Args:
        params: Skill name to delete
        
    Returns:
        Confirmation of deletion
    """
    try:
        existing = await qdrant.get_by_field(
            collection="skills",
            field="name",
            value=params.name
        )
        if not existing:
            return f"Skill `{params.name}` not found."
        
        await qdrant.delete(collection="skills", id=existing['id'])
        
        return f"✅ Skill `{params.name}` deleted successfully."
        
    except Exception as e:
        return f"Error deleting skill: {str(e)}"


@mcp.tool(
    name="skill_list",
    annotations=ToolAnnotations(title="List All Skills", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def skill_list(params: SkillListInput) -> str:
    """
    List all available skills.
    
    Returns skill names and descriptions (not full prompts).
    
    Args:
        params: Optional tag filter and format
        
    Returns:
        List of skills
    """
    try:
        filters: Dict[str, Union[str, List[str]]] = {}
        if params.tags:
            filters['tags'] = params.tags
        
        results, total = await qdrant.list_all(
            collection="skills",
            limit=100,
            offset=0,
            filters=filters
        )
        
        if not results:
            return "No skills found."
        
        if params.response_format == ResponseFormat.JSON:
            # Remove prompt from list view
            for r in results:
                r.pop('prompt', None)
            return json.dumps({
                "total": total,
                "skills": results
            }, indent=2, default=str)
        
        output = [f"# Available Skills ({total})", ""]
        for skill in results:
            output.append(f"### `{skill.get('name')}`")
            output.append(f"{skill.get('description', 'No description')}")
            if skill.get('tags'):
                output.append(f"Tags: {', '.join(skill['tags'])}")
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error listing skills: {str(e)}"


# ============================================================================
# Project Tools
# ============================================================================

@mcp.tool(
    name="project_search",
    annotations=ToolAnnotations(title="Search Projects", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def project_search(params: ProjectSearchInput) -> str:
    """
    Search for projects using semantic similarity.

    Finds projects matching your query based on name and description.

    Args:
        params: Search query and options

    Returns:
        Matching projects
    """
    try:
        query_embedding = await get_embeddings(params.query)

        filters: Dict[str, Union[str, List[str]]] = {}
        if params.status:
            filters['status'] = params.status.value
        if params.tags:
            filters['tags'] = params.tags

        results = await qdrant.search(
            collection="projects",
            vector=query_embedding,
            limit=params.limit,
            filters=filters
        )

        if not results:
            return "No matching projects found."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(results, indent=2, default=str)

        output = [f"# Projects matching: \"{params.query}\"", ""]
        for project in results:
            output.append(format_project_md(project))
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"Error searching projects: {str(e)}"


@mcp.tool(
    name="project_add",
    annotations=ToolAnnotations(title="Add Project", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def project_add(params: ProjectAddInput) -> str:
    """
    Add a new project to the database.

    Projects store metadata about your development projects.

    Args:
        params: Project data including name, path, description

    Returns:
        Confirmation of creation
    """
    try:
        # Check if project with this name already exists
        existing = await qdrant.get_by_field(
            collection="projects",
            field="name",
            value=params.name
        )
        if existing:
            return f"Project `{params.name}` already exists. Use project_update to modify it."

        project_id = f"p-{params.name}"

        text_for_embedding = f"{params.name}\n{params.description}"
        embedding = await get_embeddings(text_for_embedding)

        payload = {
            "id": project_id,
            "name": params.name,
            "path": params.path,
            "description": params.description,
            "status": params.status.value,
            "tags": params.tags,
            "metadata": params.metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        await qdrant.upsert(
            collection="projects",
            id=project_id,
            vector=embedding,
            payload=payload
        )

        return f"Project `{params.name}` created successfully!"

    except Exception as e:
        return f"Error adding project: {str(e)}"


@mcp.tool(
    name="project_get",
    annotations=ToolAnnotations(title="Get Project by Name", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def project_get(params: ProjectGetInput) -> str:
    """
    Retrieve a project by its exact name.

    Args:
        params: Project name and response format

    Returns:
        Complete project info
    """
    try:
        project = await qdrant.get_by_field(
            collection="projects",
            field="name",
            value=params.name
        )

        if not project:
            return f"Project `{params.name}` not found."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(project, indent=2, default=str)

        return format_project_md(project)

    except Exception as e:
        return f"Error retrieving project: {str(e)}"


@mcp.tool(
    name="project_update",
    annotations=ToolAnnotations(title="Update Project", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def project_update(params: ProjectUpdateInput) -> str:
    """
    Update an existing project.

    Only specified fields will be updated.

    Args:
        params: Project name and fields to update

    Returns:
        Confirmation of update
    """
    try:
        existing = await qdrant.get_by_field(
            collection="projects",
            field="name",
            value=params.name
        )
        if not existing:
            return f"Project `{params.name}` not found."

        updated = existing.copy()
        if params.path is not None:
            updated['path'] = params.path
        if params.description is not None:
            updated['description'] = params.description
        if params.status is not None:
            updated['status'] = params.status.value
        if params.tags is not None:
            updated['tags'] = params.tags
        if params.metadata is not None:
            updated['metadata'] = {**existing.get('metadata', {}), **params.metadata}

        updated['updated_at'] = datetime.utcnow().isoformat()

        # Re-embed if description changed
        if params.description is not None:
            text_for_embedding = f"{updated['name']}\n{updated['description']}"
            embedding = await get_embeddings(text_for_embedding)
        else:
            embedding = None

        await qdrant.upsert(
            collection="projects",
            id=existing['id'],
            vector=embedding,
            payload=updated,
            update_vector=embedding is not None
        )

        return f"Project `{params.name}` updated successfully!"

    except Exception as e:
        return f"Error updating project: {str(e)}"


@mcp.tool(
    name="project_delete",
    annotations=ToolAnnotations(title="Delete Project", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def project_delete(params: ProjectDeleteInput) -> str:
    """
    Delete a project from the database.

    This action is permanent.

    Args:
        params: Project name to delete

    Returns:
        Confirmation of deletion
    """
    try:
        existing = await qdrant.get_by_field(
            collection="projects",
            field="name",
            value=params.name
        )
        if not existing:
            return f"Project `{params.name}` not found."

        await qdrant.delete(collection="projects", id=existing['id'])

        return f"Project `{params.name}` deleted successfully."

    except Exception as e:
        return f"Error deleting project: {str(e)}"


@mcp.tool(
    name="project_list",
    annotations=ToolAnnotations(title="List Projects", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def project_list(params: ProjectListInput) -> str:
    """
    List all projects with optional filtering.

    Args:
        params: Pagination and filter options

    Returns:
        List of projects
    """
    try:
        filters: Dict[str, Union[str, List[str]]] = {}
        if params.status:
            filters['status'] = params.status.value
        if params.tags:
            filters['tags'] = params.tags

        results, total = await qdrant.list_all(
            collection="projects",
            limit=params.limit,
            offset=params.offset,
            filters=filters
        )

        if not results:
            return "No projects found."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "total": total,
                "count": len(results),
                "offset": params.offset,
                "projects": results
            }, indent=2, default=str)

        output = [
            "# Projects",
            f"Showing {len(results)} of {total} projects (offset: {params.offset})",
            ""
        ]

        for project in results:
            output.append(f"### `{project.get('name')}`")
            output.append(f"- **Status:** {project.get('status', 'unknown')}")
            if project.get('path'):
                output.append(f"- **Path:** `{project['path']}`")
            if project.get('tags'):
                output.append(f"- **Tags:** {', '.join(project['tags'])}")
            output.append(f"- {project.get('description', 'No description')[:100]}...")
            output.append("")

        if total > params.offset + len(results):
            output.append(f"_Use offset={params.offset + len(results)} to see more_")

        return "\n".join(output)

    except Exception as e:
        return f"Error listing projects: {str(e)}"


# ============================================================================
# Private Data Tools
# ============================================================================

@mcp.tool(
    name="private_search",
    annotations=ToolAnnotations(title="Search Private Data", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def private_search(params: PrivateSearchInput) -> str:
    """
    Search private data using semantic similarity.

    Finds private entries matching your query.

    Args:
        params: Search query and options

    Returns:
        Matching private entries
    """
    try:
        query_embedding = await get_embeddings(params.query)

        filters: Dict[str, Union[str, List[str]]] = {}
        if params.private_type:
            filters['private_type'] = params.private_type.value
        if params.tags:
            filters['tags'] = params.tags

        results = await qdrant.search(
            collection="private",
            vector=query_embedding,
            limit=params.limit,
            filters=filters
        )

        if not results:
            return "No matching private entries found."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(results, indent=2, default=str)

        output = [f"# Private entries matching: \"{params.query}\"", ""]
        for entry in results:
            output.append(format_private_md(entry))
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"Error searching private data: {str(e)}"


@mcp.tool(
    name="private_add",
    annotations=ToolAnnotations(title="Add Private Entry", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def private_add(params: PrivateAddInput) -> str:
    """
    Add a new private entry.

    Private entries are personal notes and context separate from the public knowledge base.

    Args:
        params: Private entry data

    Returns:
        Confirmation with the new entry ID
    """
    try:
        content_hash = hashlib.sha256(
            f"{params.title}{params.content}".encode()
        ).hexdigest()[:12]
        entry_id = f"priv-{content_hash}"

        text_for_embedding = f"{params.title}\n\n{params.content}"
        embedding = await get_embeddings(text_for_embedding)

        payload = {
            "id": entry_id,
            "title": params.title,
            "content": params.content,
            "private_type": params.private_type.value,
            "tags": params.tags,
            "metadata": params.metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        await qdrant.upsert(
            collection="private",
            id=entry_id,
            vector=embedding,
            payload=payload
        )

        return f"Private entry added successfully!\n\n**ID:** `{entry_id}`\n**Title:** {params.title}"

    except Exception as e:
        return f"Error adding private entry: {str(e)}"


@mcp.tool(
    name="private_get",
    annotations=ToolAnnotations(title="Get Private Entry", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def private_get(params: PrivateGetInput) -> str:
    """
    Retrieve a specific private entry by ID.

    Args:
        params: Entry ID and response format

    Returns:
        Full private entry content
    """
    try:
        entry = await qdrant.get_by_id(collection="private", id=params.id)

        if not entry:
            return f"Private entry with ID `{params.id}` not found."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(entry, indent=2, default=str)

        return format_private_md(entry)

    except Exception as e:
        return f"Error retrieving private entry: {str(e)}"


@mcp.tool(
    name="private_update",
    annotations=ToolAnnotations(title="Update Private Entry", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def private_update(params: PrivateUpdateInput) -> str:
    """
    Update an existing private entry.

    Only specified fields will be updated.

    Args:
        params: Entry ID and fields to update

    Returns:
        Confirmation of update
    """
    try:
        existing = await qdrant.get_by_id(collection="private", id=params.id)
        if not existing:
            return f"Private entry with ID `{params.id}` not found."

        updated = existing.copy()
        if params.title is not None:
            updated['title'] = params.title
        if params.content is not None:
            updated['content'] = params.content
        if params.private_type is not None:
            updated['private_type'] = params.private_type.value
        if params.tags is not None:
            updated['tags'] = params.tags
        if params.metadata is not None:
            updated['metadata'] = {**existing.get('metadata', {}), **params.metadata}

        updated['updated_at'] = datetime.utcnow().isoformat()

        # Re-embed if content changed
        if params.title is not None or params.content is not None:
            text_for_embedding = f"{updated['title']}\n\n{updated['content']}"
            embedding = await get_embeddings(text_for_embedding)
        else:
            embedding = None

        await qdrant.upsert(
            collection="private",
            id=params.id,
            vector=embedding,
            payload=updated,
            update_vector=embedding is not None
        )

        return f"Private entry `{params.id}` updated successfully!"

    except Exception as e:
        return f"Error updating private entry: {str(e)}"


@mcp.tool(
    name="private_delete",
    annotations=ToolAnnotations(title="Delete Private Entry", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def private_delete(params: PrivateDeleteInput) -> str:
    """
    Delete a private entry from the database.

    This action is permanent.

    Args:
        params: ID of entry to delete

    Returns:
        Confirmation of deletion
    """
    try:
        existing = await qdrant.get_by_id(collection="private", id=params.id)
        if not existing:
            return f"Private entry with ID `{params.id}` not found."

        await qdrant.delete(collection="private", id=params.id)

        return f"Private entry `{params.id}` deleted successfully."

    except Exception as e:
        return f"Error deleting private entry: {str(e)}"


@mcp.tool(
    name="private_list",
    annotations=ToolAnnotations(title="List Private Entries", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def private_list(params: PrivateListInput) -> str:
    """
    List private entries with optional filtering.

    Args:
        params: Pagination and filter options

    Returns:
        List of private entries (titles and metadata, not full content)
    """
    try:
        filters: Dict[str, Union[str, List[str]]] = {}
        if params.private_type:
            filters['private_type'] = params.private_type.value
        if params.tags:
            filters['tags'] = params.tags

        results, total = await qdrant.list_all(
            collection="private",
            limit=params.limit,
            offset=params.offset,
            filters=filters
        )

        if not results:
            return "No private entries found."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "total": total,
                "count": len(results),
                "offset": params.offset,
                "entries": results
            }, indent=2, default=str)

        output = [
            "# Private Data",
            f"Showing {len(results)} of {total} entries (offset: {params.offset})",
            ""
        ]

        for entry in results:
            output.append(f"### {entry.get('title', 'Untitled')}")
            output.append(f"- **ID:** `{entry.get('id')}`")
            output.append(f"- **Type:** {entry.get('private_type', 'note')}")
            if entry.get('tags'):
                output.append(f"- **Tags:** {', '.join(entry['tags'])}")
            output.append("")

        if total > params.offset + len(results):
            output.append(f"_Use offset={params.offset + len(results)} to see more_")

        return "\n".join(output)

    except Exception as e:
        return f"Error listing private entries: {str(e)}"


# ============================================================================
# Startup
# ============================================================================


def main():
    """Run the MCP server in stdio mode."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()