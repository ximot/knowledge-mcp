# Knowledge MCP - REST API Documentation

Base URL: `http://192.168.1.9:8766`

## Endpoints

---

## Knowledge (Baza wiedzy)

### POST /api/knowledge - Dodaj wpis

**Request:**
```http
POST /api/knowledge
Content-Type: application/json
```

**Payload:**
```json
{
  "title": "Tytuł wpisu",
  "content": "Pełna treść wpisu w markdown...",
  "knowledge_type": "documentation",
  "tags": ["tag1", "tag2", "tag3"],
  "source": "https://example.com/source"
}
```

**Pola:**
| Pole | Typ | Wymagane | Opis |
|------|-----|----------|------|
| `title` | string | Tak | Tytuł wpisu (max 200 znaków) |
| `content` | string | Tak | Treść w markdown (max 50000 znaków) |
| `knowledge_type` | string | Nie | Typ: `note`, `documentation`, `code_snippet`, `reference`, `howto`, `other` (domyślnie: `note`) |
| `tags` | array/string | Nie | Lista tagów lub string oddzielony przecinkami |
| `source` | string | Nie | URL źródła |
| `metadata` | object | Nie | Dodatkowe dane jako key-value |

**Response (200):**
```json
{
  "success": true,
  "id": "k-abc123def456",
  "title": "Tytuł wpisu"
}
```

**Response (400):**
```json
{
  "error": "title and content are required"
}
```

---

### GET /api/knowledge - Lista/Wyszukiwanie

**Request:**
```http
GET /api/knowledge?q=search+query&limit=10&tags=homelab,docker
```

**Query params:**
| Param | Typ | Domyślnie | Opis |
|-------|-----|-----------|------|
| `q` | string | - | Zapytanie do wyszukiwania semantycznego |
| `limit` | int | 10 | Max liczba wyników |
| `tags` | string | - | Filtr tagów (przecinki) |

**Przykłady:**
```
# Lista wszystkich (limit 10)
GET /api/knowledge

# Wyszukiwanie semantyczne
GET /api/knowledge?q=jak skonfigurować backup

# Filtrowanie po tagach
GET /api/knowledge?tags=proxmox,homelab

# Kombinacja
GET /api/knowledge?q=docker&tags=homelab&limit=5
```

**Response (200):**
```json
{
  "results": [
    {
      "id": "k-abc123",
      "title": "Tytuł",
      "content": "Treść...",
      "knowledge_type": "documentation",
      "tags": ["tag1", "tag2"],
      "source": null,
      "metadata": {},
      "created_at": "2025-01-01T12:00:00",
      "updated_at": "2025-01-01T12:00:00",
      "score": 0.85
    }
  ],
  "count": 1
}
```

---

## Skills (Prompty/Instrukcje)

### POST /api/skills - Dodaj skill

**Request:**
```http
POST /api/skills
Content-Type: application/json
```

**Payload:**
```json
{
  "name": "code-reviewer",
  "description": "Expert code reviewer for quality analysis",
  "prompt": "You are an expert code reviewer. Analyze code for:\n1. Logic errors\n2. Security issues\n3. Performance\n...",
  "tags": ["coding", "review"],
  "version": "1.0.0",
  "examples": ["Review this Python function", "Check for security issues"]
}
```

**Pola:**
| Pole | Typ | Wymagane | Opis |
|------|-----|----------|------|
| `name` | string | Tak | Unikalna nazwa (lowercase, tylko `a-z0-9-`) |
| `description` | string | Tak | Krótki opis (max 500 znaków) |
| `prompt` | string | Tak | Pełny prompt/instrukcja (max 100000 znaków) |
| `tags` | array/string | Nie | Lista tagów |
| `version` | string | Nie | Wersja (domyślnie: `1.0.0`) |
| `examples` | array | Nie | Przykłady użycia |

**Response (200):**
```json
{
  "success": true,
  "id": "s-code-reviewer",
  "name": "code-reviewer"
}
```

**Response (409):**
```json
{
  "error": "Skill 'code-reviewer' already exists"
}
```

---

### GET /api/skills - Lista/Wyszukiwanie

**Request:**
```http
GET /api/skills?q=search&limit=10
```

**Query params:**
| Param | Typ | Domyślnie | Opis |
|-------|-----|-----------|------|
| `q` | string | - | Zapytanie do wyszukiwania |
| `limit` | int | 20 | Max liczba wyników |

**Response (200):**
```json
{
  "results": [
    {
      "id": "s-code-reviewer",
      "name": "code-reviewer",
      "description": "Expert code reviewer...",
      "tags": ["coding", "review"],
      "version": "1.0.0",
      "examples": [],
      "created_at": "2025-01-01T12:00:00",
      "updated_at": "2025-01-01T12:00:00",
      "score": 0.92
    }
  ],
  "count": 1
}
```

**Uwaga:** Lista nie zwraca pola `prompt` (dla oszczędności). Użyj MCP `skill_get` aby pobrać pełny prompt.

---

## Health Check

### GET /health

**Response:**
```json
{
  "status": "ok"
}
```

---

## n8n Examples

### Workflow: RSS → Knowledge

```
1. RSS Feed Trigger
   URL: https://example.com/feed.xml

2. HTTP Request
   Method: POST
   URL: http://192.168.1.9:8766/api/knowledge
   Body (JSON):
   {
     "title": "{{ $json.title }}",
     "content": "{{ $json.content }}",
     "knowledge_type": "reference",
     "tags": ["rss", "auto-import"],
     "source": "{{ $json.link }}"
   }
```

### Workflow: Webhook → Knowledge

```
1. Webhook
   Path: /add-knowledge

2. HTTP Request
   Method: POST
   URL: http://192.168.1.9:8766/api/knowledge
   Body (JSON):
   {
     "title": "{{ $json.body.title }}",
     "content": "{{ $json.body.content }}",
     "tags": "{{ $json.body.tags }}"
   }
```

### Workflow: Search Knowledge

```
1. Webhook
   Path: /search

2. HTTP Request
   Method: GET
   URL: http://192.168.1.9:8766/api/knowledge?q={{ $json.query }}&limit=5

3. Respond to Webhook
   Body: {{ $json.results }}
```

---

## cURL Examples

```bash
# Dodaj wiedzę
curl -X POST http://192.168.1.9:8766/api/knowledge \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Entry",
    "content": "This is test content",
    "tags": ["test"]
  }'

# Szukaj
curl "http://192.168.1.9:8766/api/knowledge?q=docker&limit=5"

# Lista skillów
curl http://192.168.1.9:8766/api/skills

# Dodaj skill
curl -X POST http://192.168.1.9:8766/api/skills \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-skill",
    "description": "My custom skill",
    "prompt": "You are an expert in..."
  }'
```
