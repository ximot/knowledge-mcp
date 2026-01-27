# Knowledge MCP Server

Centralny serwer RAG (Retrieval-Augmented Generation) dla Claude Code. Przechowuje wiedzę i skille w bazie wektorowej Qdrant z embeddingami z Ollama.

## Architektura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Mac mini M4    │     │  AMD Workstation│     │  Laptop/inne    │
│  Claude Code    │     │  Claude Code    │     │  Claude Code    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │ MCP (stdio/SSE)
                                 ▼
                    ┌────────────────────────┐
                    │   ai.ximot.net         │
                    │   Knowledge MCP        │
                    │   ─────────────────    │
                    │   Qdrant + Ollama      │
                    │   nomic-embed-text     │
                    └────────────────────────┘
```

## Funkcje

### Knowledge (Baza wiedzy)
- `knowledge_search` - Semantyczne wyszukiwanie w bazie wiedzy
- `knowledge_add` - Dodawanie nowych wpisów
- `knowledge_get` - Pobieranie wpisu po ID
- `knowledge_update` - Aktualizacja istniejącego wpisu
- `knowledge_delete` - Usuwanie wpisu
- `knowledge_list` - Lista wszystkich wpisów z paginacją

### Skills (Prompty/Instrukcje)
- `skill_search` - Wyszukiwanie skillów
- `skill_get` - Pobieranie skilla po nazwie
- `skill_add` - Dodawanie nowego skilla
- `skill_update` - Aktualizacja skilla
- `skill_delete` - Usuwanie skilla
- `skill_list` - Lista wszystkich skillów

## Wymagania

- Python 3.11+
- Qdrant (localhost:6333 lub remote)
- Ollama z modelem `nomic-embed-text`

## Instalacja

### 1. Klonowanie i instalacja zależności

```bash
cd /opt
git clone <repo> knowledge-mcp
cd knowledge-mcp
pip install -r requirements.txt
```

### 2. Konfiguracja środowiska

Utwórz plik `.env` lub ustaw zmienne środowiskowe:

```bash
# Qdrant
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
# export QDRANT_API_KEY=your-key  # jeśli używasz auth
# export QDRANT_HTTPS=true        # jeśli używasz HTTPS

# Ollama
export OLLAMA_HOST=http://localhost:11434
export EMBEDDING_MODEL=nomic-embed-text

# Vector size dla nomic-embed-text to 768
export VECTOR_SIZE=768
```

### 3. Uruchomienie Qdrant (jeśli nie masz)

```bash
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v /data/qdrant:/qdrant/storage \
  --restart unless-stopped \
  qdrant/qdrant
```

### 4. Sprawdź czy Ollama ma model

```bash
ollama pull nomic-embed-text
```

## Uruchomienie

### Tryb stdio (domyślny dla Claude Code)

```bash
python -m knowledge_mcp.server
```

### Tryb HTTP (dla zdalnego dostępu)

Zmodyfikuj `server.py` - zmień ostatnią linię:

```python
mcp.run(transport="streamable_http", port=8080)
```

## Konfiguracja Claude Code

Dodaj do `~/.claude/claude_desktop_config.json`:

### Lokalny serwer (stdio)

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "python",
      "args": ["-m", "knowledge_mcp.server"],
      "cwd": "/opt/knowledge-mcp",
      "env": {
        "QDRANT_HOST": "localhost",
        "OLLAMA_HOST": "http://localhost:11434"
      }
    }
  }
}
```

### Zdalny serwer (przez SSH tunnel)

Na każdej maszynie klienckiej ustaw SSH tunnel:

```bash
# Tunnel do Qdrant i Ollama
ssh -L 6333:localhost:6333 -L 11434:localhost:11434 user@ai.ximot.net -N
```

Potem użyj konfiguracji lokalnej powyżej.

### Zdalny serwer (HTTP)

Uruchom serwer HTTP:

```bash
cd /opt/knowledge-mcp
source .venv/bin/activate
MCP_PORT=8765 python knowledge_mcp/http_server.py
```

Konfiguracja Claude Code (w `~/.claude/settings.json` lub w projekcie `.claude/settings.json`):

```json
{
  "mcpServers": {
    "knowledge": {
      "url": "http://ai.ximot.net:8765/mcp"
    }
  }
}
```

**Uwaga:** Serwer obsługuje wielu klientów jednocześnie (stateless mode).

## Przykłady użycia

### Dodawanie wiedzy

```
Dodaj do bazy wiedzy:
- Tytuł: "Konfiguracja Proxmox HA"
- Treść: [twoja dokumentacja]
- Typ: documentation
- Tagi: proxmox, ha, cluster
```

### Wyszukiwanie

```
Znajdź w bazie wiedzy informacje o konfiguracji HA w Proxmox
```

### Dodawanie skilla

```
Dodaj skill "code-reviewer" z promptem:
"Jesteś doświadczonym code reviewerem. Analizuj kod pod kątem..."
```

### Używanie skilla

```
Pobierz skill "code-reviewer" i użyj go do review mojego kodu
```

## Struktura kolekcji

### Knowledge
```json
{
  "id": "k-abc123",
  "title": "Tytuł wpisu",
  "content": "Pełna treść...",
  "knowledge_type": "documentation",
  "tags": ["tag1", "tag2"],
  "source": "https://...",
  "metadata": {},
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:00:00"
}
```

### Skills
```json
{
  "id": "s-code-reviewer",
  "name": "code-reviewer",
  "description": "Code review expert",
  "prompt": "System prompt...",
  "tags": ["coding", "review"],
  "version": "1.0.0",
  "examples": ["Example 1", "Example 2"],
  "created_at": "2025-01-01T00:00:00"
}
```

## Troubleshooting

### "Connection refused" do Qdrant
- Sprawdź czy kontener działa: `docker ps | grep qdrant`
- Sprawdź logi: `docker logs qdrant`

### Błędy embeddingów
- Sprawdź czy Ollama działa: `curl http://localhost:11434/api/tags`
- Sprawdź czy model jest pobrany: `ollama list`

### Serwer MCP nie startuje
- Sprawdź Python version: `python --version` (wymaga 3.11+)
- Sprawdź instalację: `pip list | grep mcp`

## Licencja

MIT
