#!/usr/bin/env python3
"""
Import skills from SKILL.md files into the knowledge base.

Usage:
    python import_skills.py /path/to/skills/directory
    python import_skills.py /path/to/single/SKILL.md
"""

import asyncio
import sys
import os
import re
from pathlib import Path
from typing import Optional

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from knowledge_mcp.config import settings
from knowledge_mcp.embeddings import get_embeddings
from knowledge_mcp.qdrant import QdrantService


def parse_skill_md(content: str, filename: str) -> dict:
    """Parse SKILL.md file into skill dict."""
    
    # Extract frontmatter if present
    name = None
    description = None
    tags = []
    
    # Try to parse YAML frontmatter
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        content = content[frontmatter_match.end():]
        
        # Parse simple YAML
        for line in frontmatter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                
                if key == 'name':
                    name = value
                elif key == 'description':
                    description = value
                elif key == 'tags':
                    # Handle both [tag1, tag2] and tag1, tag2 formats
                    tags = [t.strip().strip('"\'') for t in value.strip('[]').split(',')]
    
    # Fallback name from filename
    if not name:
        name = Path(filename).stem.lower().replace('_', '-').replace(' ', '-')
        if name == 'skill':
            name = Path(filename).parent.name.lower().replace('_', '-').replace(' ', '-')
    
    # Fallback description from first paragraph
    if not description:
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                description = line[:200]
                break
        if not description:
            description = f"Skill imported from {filename}"
    
    return {
        'name': name,
        'description': description,
        'prompt': content.strip(),
        'tags': [t for t in tags if t],  # Filter empty tags
        'version': '1.0.0',
        'examples': []
    }


async def import_skill(qdrant: QdrantService, skill_data: dict) -> bool:
    """Import a single skill into Qdrant."""
    
    try:
        # Generate ID
        skill_id = f"s-{skill_data['name']}"
        
        # Check if exists
        existing = await qdrant.get_by_field(
            collection="skills",
            field="name",
            value=skill_data['name']
        )
        
        if existing:
            print(f"  ⚠️  Skill '{skill_data['name']}' already exists, skipping")
            return False
        
        # Generate embedding
        text_for_embedding = f"{skill_data['name']}\n{skill_data['description']}\n{skill_data['prompt']}"
        embedding = await get_embeddings(text_for_embedding)
        
        # Prepare payload
        from datetime import datetime
        payload = {
            "id": skill_id,
            **skill_data,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Upsert
        await qdrant.upsert(
            collection="skills",
            id=skill_id,
            vector=embedding,
            payload=payload
        )
        
        print(f"  ✅ Imported '{skill_data['name']}'")
        return True
        
    except Exception as e:
        print(f"  ❌ Error importing '{skill_data['name']}': {e}")
        return False


async def main():
    if len(sys.argv) < 2:
        print("Usage: python import_skills.py <path>")
        print("  path: Directory containing SKILL.md files or single SKILL.md file")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    
    if not path.exists():
        print(f"Error: Path '{path}' does not exist")
        sys.exit(1)
    
    # Collect files to import
    files = []
    if path.is_file():
        files = [path]
    else:
        # Find all SKILL.md files
        files = list(path.rglob("SKILL.md"))
        if not files:
            # Also try .md files in the directory
            files = list(path.glob("*.md"))
    
    if not files:
        print(f"No SKILL.md files found in '{path}'")
        sys.exit(1)
    
    print(f"Found {len(files)} skill file(s) to import")
    print(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")
    print(f"Ollama: {settings.ollama_host}")
    print()
    
    # Initialize Qdrant
    qdrant = QdrantService()
    await qdrant.ensure_collections()
    
    # Import each file
    imported = 0
    for file in files:
        print(f"Processing: {file}")
        
        try:
            content = file.read_text()
            skill_data = parse_skill_md(content, str(file))
            
            if await import_skill(qdrant, skill_data):
                imported += 1
                
        except Exception as e:
            print(f"  ❌ Error reading '{file}': {e}")
    
    print()
    print(f"Done! Imported {imported} of {len(files)} skills")


if __name__ == "__main__":
    asyncio.run(main())
