# 📐 Architettura del Progetto / Project Architecture

> **[English below](#english-version)**

---

## 🇮🇹 Versione Italiana

### Struttura delle cartelle

```
mtg-deck-upgrade-assistant/
├── app/
│   ├── main.py                  # Entry point FastAPI
│   ├── config.py                # Configurazione (env vars, settings)
│   ├── api/                     # Route HTTP (controller layer)
│   │   ├── router.py            # Router principale che aggrega tutti i sotto-router
│   │   ├── sets.py              # Endpoint /api/sets/*
│   │   ├── cards.py             # Endpoint /api/cards/*
│   │   ├── sync.py              # Endpoint /api/sync/* (trigger sincronizzazione)
│   │   ├── ai.py                # Endpoint /api/ai/chat
│   │   └── dependencies.py      # Dipendenze condivise (es. get_db)
│   ├── clients/                 # Client HTTP verso servizi esterni
│   │   ├── scryfall_client.py   # Client asincrono per Scryfall REST API
│   │   └── llm_client.py        # Client LLM multi-provider via LiteLLM
│   ├── database/                # Configurazione database
│   │   └── session.py           # Engine SQLAlchemy + init_db + get_db
│   ├── models/                  # ORM models (SQLAlchemy)
│   │   ├── base.py              # DeclarativeBase
│   │   ├── set_model.py         # Modello MTGSet (tabella "sets")
│   │   └── card_model.py        # Modello MTGCard (tabella "cards")
│   ├── schemas/                 # Pydantic schemas per request/response
│   ├── services/                # Business logic
│   │   ├── set_service.py       # Logica sincronizzazione e query dei set
│   │   ├── card_service.py      # Logica query e filtro delle carte
│   │   └── ai_service.py        # AI Deck Advisor (RAG pipeline)
│   ├── templates/
│   │   └── index.html           # UI principale (Jinja2 + JS vanilla)
│   └── static/
│       └── css/
│           └── style.css        # Stile dell'interfaccia
├── migrations/                  # Migrazioni Alembic (opzionale)
├── tests/                       # Test pytest
├── requirements.txt             # Dipendenze Python
├── .env.example                 # Template variabili d'ambiente
├── README.md                    # Documentazione principale
└── ARCHITECTURE.md              # Questo file
```

---

### Descrizione dei file principali

#### `app/main.py`
Entry point dell'applicazione FastAPI. Configura:
- Il lifespan (inizializzazione DB all'avvio)
- Il middleware CORS
- Il mount dei file statici (`/static`)
- I template Jinja2
- L'inclusione del router API
- Le route di pagina HTML (`/`) e health check (`/health`)

#### `app/config.py`
Configurazione centralizzata tramite `pydantic-settings`. Legge le variabili d'ambiente dal file `.env`. Espone un singleton `get_settings()` con i parametri dell'app (nome, versione, URL del DB, log level, ecc.).

#### `app/api/router.py`
Router principale FastAPI che aggrega tutti i sotto-router con i rispettivi prefissi:
- `/api/sets` → `sets.router`
- `/api/cards` → `cards.router`
- `/api/sync` → `sync.router`
- `/api/ai` → `ai.router`

#### `app/api/sets.py`
Endpoint per la gestione dei set MTG:
- `GET /api/sets` — lista con filtri (tipo, anno, fisici/digitali)
- `GET /api/sets/recent` — set fisici recenti, ordinati per data
- `GET /api/sets/{code}` — dettaglio singolo set
- `GET /api/sets/{code}/cards` — carte di un set con paginazione

#### `app/api/cards.py`
Endpoint per l'esplorazione delle carte con filtri avanzati:
- `GET /api/cards` — filtri per set (multipli), nome, tipo, rarità, **color identity** (logica Commander: `ci ⊆ selection`), testo oracle (OR tra termini separati da virgola), mana value min/max
- Deduplicazione per nome (mostra solo la prima stampa)
- Ordinamento e paginazione

#### `app/api/sync.py`
Endpoint per triggerare la sincronizzazione dei dati da Scryfall:
- `POST /api/sync/sets` — scarica e salva tutti i set
- `POST /api/sync/sets/{code}/cards` — scarica e salva tutte le carte di un set
- `POST /api/sync/sets/{code}/cards/family` — scarica il set principale **e tutti i sotto-set** (`parent_set_code == code`): Commander decks, promos, tokens, art series
- `DELETE /api/sync/sets/{code}/cards` — cancella le carte di un set (e sotto-set) dal DB

#### `app/api/decks.py` *(nuovo in v0.3)*
Endpoint per l'analisi Commander via EDHREC:
- `GET /api/decks/commander?name=X` — aggrega statistiche da EDHREC (main + tutti i temi: tribal, combo, budget, token, sacrifice, ecc.) in parallelo; arricchisce con dati Scryfall batch per immagini, type_line e oracle_text; supporta partner commanders (`name=Malcolm + Kediss`)

#### `app/api/ai.py`
Endpoint per il chatbot AI:
- `POST /api/ai/chat` — riceve messaggio, set selezionati, commander, provider, API key, history, e `visible_cards` (carte visibili a schermo)
- Supporta `set_codes` (lista) e `set_code` (legacy singolo)

#### `app/clients/scryfall_client.py`
Client HTTP asincrono per le Scryfall REST API. Gestisce:
- Rate limiting (rispetto dei limiti Scryfall: 100ms tra richieste)
- Paginazione automatica (`has_more` + `next_page`)
- Retry su errori temporanei
- `get_sets()`, `get_cards_by_set(set_code)`, `search_cards(query)`

#### `app/clients/archidekt_client.py` *(client EDHREC in v0.3)*
Client asincrono per l'API JSON pubblica di EDHREC. Aggrega il commander principale + 20+ temi in parallelo. Supporta partner commanders con `+`. Batch Scryfall `/cards/collection` per immagini e metadati.

#### `app/clients/llm_client.py`
Client LLM provider-agnostico basato su **LiteLLM**. Supporta:
- **Groq** — gratuito, modello `qwen/qwen3.8-27b`
- **Google Gemini** — gratuito, modello `gemini-3.6-flash`
- **DeepSeek** — economico, modello `deepseek-chat`
- **OpenAI** — `gpt-4o-mini`
- **Ollama** — locale, nessuna API key

Espone il dizionario `PROVIDERS` usato dalla UI per i dropdown e i link alle API key.

#### `app/database/session.py`
Configurazione del database SQLite asincrono:
- `AsyncEngine` SQLAlchemy con `aiosqlite`
- `AsyncSessionLocal` — factory delle sessioni
- `init_db()` — crea le tabelle al primo avvio
- `get_db()` — dependency FastAPI per iniettare la sessione nelle route

#### `app/models/set_model.py`
ORM model per la tabella `sets`. Campi principali: `scryfall_id`, `code`, `name`, `released_at`, `set_type`, `card_count`, `digital`, `icon_svg_uri`, **`parent_set_code`** (FK verso il set genitore, usato per trovare i sotto-set). Usa `Optional[T]` per compatibilità Python 3.9.

#### `app/models/card_model.py`
ORM model per la tabella `cards`. Campi principali: `scryfall_id`, `oracle_id`, `name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `color_identity`, `keywords`, `set_code` (FK → sets.code), `rarity`, `image_uris`, `prices`, `legalities`, `raw_data`, **`edhrec_rank`** (rank EDHRec per ordinamento Commander).

#### `app/services/ai_service.py`
Cuore dell'AI Deck Advisor. Implementa una pipeline contestuale a più step:

1. **Step 0** — Lookup del commander su Scryfall con cache in memoria
2. **Se `visible_cards` è presente**: usa le carte visibili a schermo direttamente, salta il RAG
3. **Altrimenti — Step 1** *(LLM call leggera)*: estrae keyword e tipi da cercare
4. **Step 2**: query al DB con quelle keyword; fallback a top-30 per rarità se vuoto
5. **Step 3** *(LLM call principale)*: invia il contesto e genera le raccomandazioni

Gestione automatica della temperatura (Gemini 3.x richiede 1.0). Cache in-memory per commander lookup.
2. **Step 1** *(LLM call leggera)* — dato il messaggio, estrae keyword e tipi di carte da cercare (es. `{"keywords": ["human", "attack"], "types": ["creature"]}`)
3. **Step 2** — Query al DB con quelle keyword (oracle text OR logic); fallback a top-60 per rarità se non trova nulla
4. **Step 3** *(LLM call principale)* — invia al modello il contesto (commander + carte filtrate) e genera i consigli

Il sistema garantisce che l'AI lavori **solo con carte reali presenti nel DB**, evitando allucinazioni.

#### `app/templates/index.html`
Interfaccia utente single-page in HTML + JavaScript vanilla (no framework):
- **Sidebar**: lista set con sync, filtro per tipo, selezione multipla (toggle)
- **Barra filtri**: nome, testo oracle (OR), tipo, rarità, color identity (checkbox), mana value, paginazione, slider dimensione carte
- **Griglia carte**: immagini con lazy loading, click → Scryfall
- **AI Chat Panel**: provider selector, API key (salvata in localStorage), messaggi user/AI/error, streaming status

#### `app/static/css/style.css`
Tema dark personalizzato. Componenti: header, layout sidebar+content, set-item, filters-bar, card-grid, card-item, chat-panel, chat-toggle, mana symbols, paginazione.

---

### Flusso dati

```
Browser → FastAPI route → Service → SQLAlchemy query → SQLite
                        ↘ ScryfallClient → Scryfall API
                        ↘ LLMClient → LiteLLM → Provider AI
```

---

## 🇬🇧 English Version

### Folder structure

```
mtg-deck-upgrade-assistant/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Configuration (env vars, settings)
│   ├── api/                     # HTTP routes (controller layer)
│   │   ├── router.py            # Main router aggregating all sub-routers
│   │   ├── sets.py              # /api/sets/* endpoints
│   │   ├── cards.py             # /api/cards/* endpoints
│   │   ├── sync.py              # /api/sync/* endpoints (sync trigger)
│   │   ├── ai.py                # /api/ai/chat endpoint
│   │   └── dependencies.py      # Shared dependencies (e.g. get_db)
│   ├── clients/                 # HTTP clients for external services
│   │   ├── scryfall_client.py   # Async Scryfall REST API client
│   │   └── llm_client.py        # Multi-provider LLM client via LiteLLM
│   ├── database/                # Database configuration
│   │   └── session.py           # SQLAlchemy engine + init_db + get_db
│   ├── models/                  # ORM models (SQLAlchemy)
│   │   ├── base.py              # DeclarativeBase
│   │   ├── set_model.py         # MTGSet model (table "sets")
│   │   └── card_model.py        # MTGCard model (table "cards")
│   ├── schemas/                 # Pydantic schemas for request/response
│   ├── services/                # Business logic
│   │   ├── set_service.py       # Set sync and query logic
│   │   ├── card_service.py      # Card query and filter logic
│   │   └── ai_service.py        # AI Deck Advisor (RAG pipeline)
│   ├── templates/
│   │   └── index.html           # Main UI (Jinja2 + vanilla JS)
│   └── static/
│       └── css/
│           └── style.css        # Interface styles
├── migrations/                  # Alembic migrations (optional)
├── tests/                       # pytest tests
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── README.md                    # Main documentation
└── ARCHITECTURE.md              # This file
```

---

### Key files description

#### `app/main.py`
FastAPI application entry point. Configures lifespan (DB init on startup), CORS middleware, static files mount, Jinja2 templates, API router inclusion, HTML page routes and health check.

#### `app/config.py`
Centralized configuration via `pydantic-settings`. Reads environment variables from `.env`. Exposes a `get_settings()` singleton with app parameters.

#### `app/api/router.py`
Main FastAPI router aggregating all sub-routers with their prefixes: `/api/sets`, `/api/cards`, `/api/sync`, `/api/ai`.

#### `app/api/sets.py`
MTG set management endpoints: list with filters, recent physical sets, single set detail, cards in a set with pagination.

#### `app/api/cards.py`
Card exploration endpoint with advanced filters:
- Multiple set codes (`set=hob&set=sos`)
- Name, type, rarity, oracle text (OR logic between comma-separated terms)
- **Color identity** (Commander logic: `identity ⊆ selection` — excludes cards with colors outside selection)
- Mana value range, deduplication by name, sorting, pagination

#### `app/api/sync.py`
Triggers data synchronization from Scryfall: sync all sets, sync cards for a specific set.

#### `app/api/ai.py`
AI chatbot endpoint. Receives message, selected set codes, commander, provider, API key, conversation history. Supports both `set_codes` (list) and legacy `set_code` (single).

#### `app/clients/scryfall_client.py`
Async HTTP client for Scryfall REST API. Handles rate limiting (100ms between requests), automatic pagination, retries, `get_sets()`, `get_cards_by_set()`, `search_cards()`.

#### `app/clients/llm_client.py`
Provider-agnostic LLM client based on **LiteLLM**. Supports Groq (free), Google Gemini (free), DeepSeek (cheap), OpenAI, and Ollama (local). Exposes the `PROVIDERS` dictionary used by the UI for dropdowns and API key links.

#### `app/database/session.py`
Async SQLite database configuration with aiosqlite. Provides `init_db()` (creates tables on first run) and `get_db()` (FastAPI dependency for session injection).

#### `app/models/set_model.py`
ORM model for the `sets` table. Key fields: `scryfall_id`, `code`, `name`, `released_at`, `set_type`, `card_count`, `digital`, `icon_svg_uri`. Uses `Optional[T]` for Python 3.9 compatibility.

#### `app/models/card_model.py`
ORM model for the `cards` table. Key fields: `scryfall_id`, `oracle_id`, `name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `color_identity`, `keywords`, `set_code` (FK → sets.code), `rarity`, `image_uris`, `prices`, `legalities`, `raw_data`.

#### `app/services/ai_service.py`
Cuore dell'AI Deck Advisor. Implementa una pipeline contestuale a più step:

1. **Step 0** — Lookup del commander su Scryfall con cache in memoria (non ripete la chiamata)
2. **Se l'utente ha carte visibili a schermo** (`visible_cards`): le usa direttamente come contesto, saltando il RAG
3. **Altrimenti — Step 1** *(LLM call leggera)*: estrae keyword e tipi da cercare (`{"keywords": [...], "types": [...]}`)
4. **Step 2**: query al DB con quelle keyword (oracle text OR logic); fallback a top-30 per rarità se non trova nulla
5. **Step 3** *(LLM call principale)*: invia il contesto e genera le raccomandazioni

Gestione automatica della temperatura per modello (Gemini 3.x richiede 1.0). Cache in-memory per i lookup commander.

#### `app/templates/index.html`
Single-page UI in HTML + vanilla JavaScript (no framework):
- **Sidebar**: set list with sync, type filter, multi-select toggle
- **Filter bar**: name, oracle text (OR), type, rarity, color identity checkboxes, mana value, pagination, card size slider
- **Card grid**: lazy-loaded images, hover reveals ○/✓ (select) and ↗ (open Scryfall), click to select
- **Floating export bar**: appears when cards are selected, exports `.txt` compatible with EDHREC/Moxfield/Archidekt
- **AI Chat Panel**: provider selector, API key (localStorage), thinking indicator, wide mode

#### `app/static/css/style.css`
Custom dark theme. Components: header, sidebar+content layout, set-item, filters-bar, card-grid, card-item, chat-panel, chat-toggle button, mana symbols, pagination.

---

### Data flow

```
Browser → FastAPI route → Service → SQLAlchemy query → SQLite
                        ↘ ScryfallClient → Scryfall API
                        ↘ LLMClient → LiteLLM → AI Provider
```
