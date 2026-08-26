# 🃏 MTG Deck Upgrade Assistant

> **[English below](#english-version)**

Un'applicazione AI per aiutare i giocatori di Magic: The Gathering Commander a scoprire le carte più interessanti dai nuovi set e valutarne l'impatto sul proprio mazzo.

---

## 🎯 Problema

Quando esce una nuova espansione di MTG, i giocatori Commander devono revisionare manualmente centinaia di carte nuove per trovare quelle rilevanti per i loro mazzi. È un processo lento e soggetto a errori.

## 💡 Soluzione

MTG Deck Upgrade Assistant automatizza questo processo:
1. Scarica e cachea localmente tutti i set e le carte da Scryfall API
2. Permette di esplorare le carte con filtri avanzati (colore, rarità, tipo, testo oracle, mana value)
3. Supporta la selezione multipla di set
4. Integra un **AI Deck Advisor** che, dato un commander, analizza le carte disponibili e suggerisce le più sinergiche

## 🏗️ Architettura

```
┌──────────────────────────────────────────────────────────┐
│                      FastAPI Backend                     │
│                                                          │
│  ┌────────────┐    ┌─────────────┐    ┌───────────────┐  │
│  │  API Layer │    │  Services   │    │   Scryfall    │  │
│  │  (routes)  │───▶│  (business  │───▶│  Client       │  │
│  │            │    │   logic)    │    │  (httpx)      │  │
│  └────────────┘    └──────┬──────┘    └───────────────┘  │
│                           │                              │
│                    ┌──────▼──────┐                       │
│                    │ Repository  │                       │
│                    │(data access)│                       │
│                    └──────┬──────┘                       │
│                           │                              │
│                    ┌──────▼──────┐                       │
│                    │   SQLite    │                       │
│                    │ (aiosqlite) │                       │
│                    └─────────────┘                       │
└──────────────────────────────────────────────────────────┘
```

## 🛠️ Stack Tecnologico

| Layer        | Tecnologia                          |
|--------------|-------------------------------------|
| Linguaggio   | Python 3.9+                         |
| Framework    | FastAPI                             |
| Database     | SQLite (async via aiosqlite)        |
| ORM          | SQLAlchemy 2.x                      |
| HTTP Client  | httpx (async)                       |
| Validazione  | Pydantic v2                         |
| Template     | Jinja2 + HTMX (vanilla JS)          |
| AI           | LiteLLM (Groq, Gemini, OpenAI, Ollama) |
| Data Source  | Scryfall REST API                   |
| Testing      | pytest + pytest-asyncio             |

## 🚀 Quick Start

### Prerequisiti
- Python 3.9+

### Setup

```bash
# Clona il repository
git clone https://github.com/YOUR_USERNAME/mtg-deck-upgrade-assistant.git
cd mtg-deck-upgrade-assistant

# Crea l'ambiente virtuale
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Installa le dipendenze
pip install -r requirements.txt

# Crea il file .env
cp .env.example .env

# Avvia l'applicazione
uvicorn app.main:app --reload
```

L'app è disponibile su **http://localhost:8000**
Documentazione API: **http://localhost:8000/docs**

### Primi passi

1. Clicca **Sync Sets** per scaricare i set da Scryfall
2. Seleziona uno o più set dalla sidebar
3. Clicca sul set per scaricare le carte (`Download Cards`)
4. Filtra per colore identità, rarità, tipo, testo oracle
5. Apri il pannello **🧠 AI Deck Advisor**, inserisci la tua API key e chiedi consigli

## 📡 API Endpoints

| Method | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/sets` | Lista set con filtri |
| GET | `/api/sets/recent` | Set fisici più recenti |
| GET | `/api/sets/{code}` | Dettaglio singolo set |
| GET | `/api/sets/{code}/cards` | Carte di un set |
| GET | `/api/cards` | Carte con filtri, ordinamento e paginazione |
| GET | `/api/cards/{id}` | Dettaglio singola carta |
| POST | `/api/sync/sets` | Sincronizza set da Scryfall |
| POST | `/api/sync/sets/{code}/cards` | Sincronizza carte di un set |
| POST | `/api/ai/chat` | Chat con AI advisor |

## 🤖 AI Deck Advisor

Il pannello AI supporta più provider:

| Provider | Costo | Modello default |
|----------|-------|-----------------|
| **Groq** | Gratuito (rate limited) | qwen/qwen3.8-27b |
| **Google Gemini** | Gratuito | gemini-3.6-flash |
| **DeepSeek** | ~$0.001/1K token | deepseek-chat |
| **OpenAI** | A pagamento | gpt-4o-mini |
| **Ollama** | Locale, gratuito | llama3.1 |

Il sistema usa un approccio **RAG a due step**:
1. L'AI analizza la domanda e produce keyword di ricerca
2. Il DB viene interrogato con quelle keyword → solo le carte rilevanti vengono passate all'AI
3. L'AI genera i consigli basandosi esclusivamente sulle carte reali trovate

L'API key viene salvata in `localStorage` e non transita mai sul server in chiaro nei log.

## 🗺️ Roadmap

- [x] Phase 1 — Scryfall data ingestion & local caching
- [x] Phase 2 — UI con filtri avanzati e selezione multipla set
- [x] Phase 3 — AI Deck Advisor (multi-provider, RAG, Scryfall lookup)
- [ ] Phase 4 — Importazione decklist (incolla lista)
- [ ] Phase 5 — Analisi mazzo (curve, colori, strategia)
- [ ] Phase 6 — Semantic search (Qdrant + embeddings)
- [ ] Phase 7 — LangGraph recommendation agent

## 📁 Struttura del progetto

Vedi [ARCHITECTURE.md](ARCHITECTURE.md) per la documentazione dettagliata di ogni file.

## ⚠️ Disclaimer

Questo è un progetto fan non ufficiale, non affiliato con Wizards of the Coast, Hasbro o Scryfall. Magic: The Gathering è un marchio di Wizards of the Coast. I dati delle carte sono forniti da Scryfall API.

Questo progetto è stato realizzato con l'assistenza di GitHub Copilot (AI) a scopo puramente educativo e personale, senza alcun fine di lucro.

---

# English version

## 🃏 MTG Deck Upgrade Assistant

An AI-powered application to help Magic: The Gathering Commander players discover relevant cards from newly released sets and evaluate their impact on existing decks.

## 🎯 Problem

When a new MTG expansion releases, Commander players must manually review hundreds of new cards to find ones relevant to their decks. This is time-consuming and error-prone.

## 💡 Solution

MTG Deck Upgrade Assistant automates this by:
1. Downloading and caching all sets and cards from the Scryfall API
2. Allowing card exploration with advanced filters (color identity, rarity, type, oracle text, mana value)
3. Supporting multi-set selection
4. Integrating an **AI Deck Advisor** that, given a commander, analyzes available cards and suggests the most synergistic ones

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      FastAPI Backend                     │
│                                                          │
│  ┌────────────┐    ┌─────────────┐    ┌───────────────┐  │
│  │  API Layer │    │  Services   │    │   Scryfall    │  │
│  │  (routes)  │───▶│  (business  │───▶│  Client       │  │
│  │            │    │   logic)    │    │  (httpx)      │  │
│  └────────────┘    └──────┬──────┘    └───────────────┘  │
│                           │                              │
│                    ┌──────▼──────┐                       │
│                    │ Repository  │                       │
│                    │(data access)│                       │
│                    └──────┬──────┘                       │
│                           │                              │
│                    ┌──────▼──────┐                       │
│                    │   SQLite    │                       │
│                    │ (aiosqlite) │                       │
│                    └─────────────┘                       │
└──────────────────────────────────────────────────────────┘
```

## 🛠️ Tech Stack

| Layer        | Technology                              |
|--------------|-----------------------------------------|
| Language     | Python 3.9+                             |
| Framework    | FastAPI                                 |
| Database     | SQLite (async via aiosqlite)            |
| ORM          | SQLAlchemy 2.x                          |
| HTTP Client  | httpx (async)                           |
| Validation   | Pydantic v2                             |
| Templates    | Jinja2 + vanilla JS                     |
| AI           | LiteLLM (Groq, Gemini, OpenAI, Ollama)  |
| Data Source  | Scryfall REST API                       |
| Testing      | pytest + pytest-asyncio                 |

## 🚀 Quick Start

### Prerequisites
- Python 3.9+

```bash
git clone https://github.com/YOUR_USERNAME/mtg-deck-upgrade-assistant.git
cd mtg-deck-upgrade-assistant
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open **http://localhost:8000** — click **Sync Sets**, select a set, download its cards, then open the AI panel.

### First Steps

1. Click **Sync Sets** to download sets from Scryfall
2. Select one or more sets from the sidebar
3. Click a set to download its cards
4. Filter by color identity, rarity, type, oracle text
5. Open the **🧠 AI Deck Advisor** panel, enter your API key and ask for recommendations

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sets` | List sets with filters |
| GET | `/api/sets/recent` | Most recent physical sets |
| GET | `/api/sets/{code}` | Single set details |
| GET | `/api/sets/{code}/cards` | Cards in a set |
| GET | `/api/cards` | Cards with filters, sorting and pagination |
| GET | `/api/cards/{id}` | Single card details |
| POST | `/api/sync/sets` | Sync sets from Scryfall |
| POST | `/api/sync/sets/{code}/cards` | Sync cards for a set |
| POST | `/api/ai/chat` | Chat with AI advisor |

## 🤖 AI Deck Advisor

| Provider | Cost | Default model |
|----------|------|---------------|
| **Groq** | Free (rate limited) | qwen/qwen3.8-27b |
| **Google Gemini** | Free | gemini-3.6-flash |
| **DeepSeek** | ~$0.001/1K tokens | deepseek-chat |
| **OpenAI** | Paid | gpt-4o-mini |
| **Ollama** | Local, free | llama3.1 |

The system uses a **two-step RAG pipeline**:
1. AI analyzes the question and extracts search keywords
2. DB is queried with those keywords → only relevant cards are passed to the AI
3. AI generates recommendations based exclusively on real cards found

The API key is stored in `localStorage` and never logged server-side.

## 🗺️ Roadmap

- [x] Phase 1 — Scryfall data ingestion & local caching
- [x] Phase 2 — UI with advanced filters and multi-set selection
- [x] Phase 3 — AI Deck Advisor (multi-provider, RAG, Scryfall lookup)
- [ ] Phase 4 — Decklist import (paste list)
- [ ] Phase 5 — Deck analysis (curve, colors, strategy)
- [ ] Phase 6 — Semantic search (Qdrant + embeddings)
- [ ] Phase 7 — LangGraph recommendation agent

## 📁 Project structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation of every file.

## ⚠️ Disclaimer

Unofficial fan project. Not affiliated with Wizards of the Coast, Hasbro, or Scryfall. Magic: The Gathering is a trademark of Wizards of the Coast. Card data provided by the Scryfall API.

This project was built with the assistance of GitHub Copilot (AI) for educational and personal purposes only, with no commercial intent.


## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      FastAPI Backend                     │
│                                                          │
│  ┌────────────┐    ┌─────────────┐    ┌───────────────┐  │
│  │  API Layer │    │  Services   │    │   Scryfall    │  │
│  │  (routes)  │───▶│  (business  │───▶│  Client      │  │
│  │            │    │   logic)    │    │  (httpx)      │  │
│  └────────────┘    └──────┬──────┘    └───────────────┘  │
│                           │                              │
│                    ┌──────▼──────┐                       │
│                    │ Repository  │                       │
│                    │(data access)│                       │
│                    └──────┬──────┘                       │
│                           │                              │
│                    ┌──────▼──────┐                       │
│                    │   SQLite    │                       │
│                    │ (aiosqlite) │                       │
│                    └─────────────┘                       │
└──────────────────────────────────────────────────────────┘
```


## 🛠️ Tech Stack

| Layer       | Technology                    |
|-------------|-------------------------------|
| Language    | Python 3.12+                  |
| Framework   | FastAPI                       |
| Database    | SQLite (async via aiosqlite)  |
| ORM         | SQLAlchemy 2.x                |
| HTTP Client | httpx (async)                 |
| Validation  | Pydantic v2                   |
| Data Source  | Scryfall REST API             |
| Testing     | pytest                        |

## 🚀 Quick Start

### Prerequisites
- Python 3.12+

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/mtg-deck-upgrade-assistant.git
cd mtg-deck-upgrade-assistant

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Run the application
uvicorn app.main:app --reload
The API will be available at http://localhost:8000

Swagger docs: http://localhost:8000/docs
First Steps
Sync sets from Scryfall:

POST http://localhost:8000/api/sync/sets
View recent sets:

GET http://localhost:8000/api/sets/recent
Sync cards for a set:

POST http://localhost:8000/api/sync/sets/{set_code}/cards
Explore cards:

GET http://localhost:8000/api/cards?set=fdn&colors=W&colors=R&rarity=rare
📡 API Endpoints
Method	Endpoint	Description
GET	/api/sets	List sets with filters
GET	/api/sets/recent	Most recent physical sets
GET	/api/sets/{code}	Single set details
GET	/api/sets/{code}/cards	Cards in a set
GET	/api/cards	Cards with filters & sorting
GET	/api/cards/{id}	Single card details
POST	/api/sync/sets	Sync sets from Scryfall
POST	/api/sync/sets/{code}/cards	Sync cards for a set
📸 Screenshots
Coming soon

🗺️ Roadmap
 Phase 1 — Scryfall data ingestion & local caching
 Phase 2 — Deck import (paste decklist)
 Phase 3 — Deck analysis (colors, curve, strategy)
 Phase 4 — Card filtering based on deck requirements
 Phase 5 — Semantic search (Qdrant + embeddings)
 Phase 6 — LangGraph recommendation agent
 Phase 7 — LLM-powered explainable suggestions
⚠️ Disclaimer
This application is an unofficial fan project and is not affiliated with, endorsed by, or sponsored by Wizards of the Coast, Hasbro, or Scryfall. Magic: The Gathering is a trademark of Wizards of the Coast. Card data is provided by the Scryfall API.