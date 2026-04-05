# Jarvis - Personal AI Assistant

A Python-powered personal assistant inspired by Iron Man's Jarvis. Features a web dashboard, real API integrations, and AI-powered conversations via Claude.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure your API keys
cp .env.example .env

# Start the web server
python run_server.py

# Or use the CLI version
python -m jarvis
```

Open **http://localhost:8000** for the web dashboard, or **http://localhost:8000/docs** for the full API documentation.

## Features

### Core Modules (CLI + API)
| Module | Capabilities |
|--------|-------------|
| **System Monitor** | CPU, memory, disk, uptime diagnostics |
| **Task Manager** | Persistent todo list with CRUD operations |
| **Smart Home Sim** | Control simulated lights, thermostat, locks, music, security |
| **Calculator** | Basic and scientific math |
| **Date/Time** | Current time, date, and calculations |
| **Web Search** | Search link generation |
| **Knowledge** | Q&A, jokes, help system |

### API Integrations
| Integration | What It Does | API Key Needed |
|-------------|-------------|----------------|
| **Claude AI** | Real AI conversations, study help, essay feedback, code explanation | `ANTHROPIC_API_KEY` |
| **Weather** | Current weather + 5-day forecast for any city | `OPENWEATHER_API_KEY` (free) |
| **News** | Top headlines by category, search articles | `NEWS_API_KEY` (free) |
| **Gmail** | Read inbox, send emails, search, unread count | `GMAIL_ACCESS_TOKEN` |
| **Spotify** | Play/pause/skip, search, playlists, top tracks | `SPOTIFY_ACCESS_TOKEN` |
| **Home Assistant** | Real smart home control (lights, thermostat, scenes) | `HOME_ASSISTANT_TOKEN` |

### College Student Tools (no API key needed)
| Tool | Description |
|------|-------------|
| **Pomodoro Timer** | Focus sessions with work/break cycles |
| **GPA Calculator** | Calculate semester and cumulative GPA |
| **Dictionary** | Word definitions, phonetics, synonyms |
| **Flashcards** | Create and study flashcard decks by subject |
| **Class Schedule** | Manage your weekly class schedule |
| **Budget Tracker** | Track expenses by category with budget warnings |
| **Tip Calculator** | Calculate tip and split bills |
| **Currency Converter** | Real-time exchange rates |
| **Unit Converter** | km/miles, kg/lbs, celsius/fahrenheit, etc. |
| **Translator** | Translate text between languages |
| **Motivational Quotes** | Daily and random quotes |
| **Countdown** | Days until any event |
| **Random Facts** | Fun facts to brighten your day |

## API Endpoints

Full interactive docs at `/docs` when running. Key endpoints:

```
POST /api/chat              - Chat with Jarvis (basic)
POST /api/ai/chat           - Chat with Claude AI
POST /api/ai/study-help     - Get study help on any subject
POST /api/ai/explain-code   - Explain code simply

GET  /api/weather/current/{city}
GET  /api/news/top?category=technology
GET  /api/email/inbox

POST /api/spotify/play
POST /api/spotify/pause
GET  /api/spotify/now-playing
GET  /api/spotify/search/{query}

POST /api/home/turn-on
POST /api/home/turn-off

POST /api/study/pomodoro/start
POST /api/study/gpa/calculate
GET  /api/study/dictionary/{word}
GET  /api/study/schedule/today

POST /api/finance/expense/add
GET  /api/finance/expense/summary
GET  /api/finance/currency/{amount}/{from}/{to}
GET  /api/finance/tip/{amount}

GET  /api/utils/quote
POST /api/utils/translate
GET  /api/utils/convert/{value}/{from}/{to}

GET  /api/system/status
GET  /api/health
```

## Project Structure

```
jarvis/
  api/
    server.py              # FastAPI web server
    routes/
      ai.py                # Claude AI chat
      weather.py           # Weather API
      email.py             # Gmail integration
      news.py              # News API
      spotify.py           # Spotify control
      home_assistant.py    # Home Assistant
      study.py             # Pomodoro, GPA, dictionary, flashcards, schedule
      finance.py           # Budget, currency, tips
      utilities.py         # Translate, quotes, converter, facts, countdown
      system.py            # System monitor + tasks API
      chat.py              # Basic chat endpoint
  core/
    brain.py               # NLP command router
    assistant.py           # Main orchestrator
    plugin_base.py         # Plugin interface
  plugins/                 # CLI plugins (7 modules)
  templates/
    dashboard.html         # Web dashboard
  static/
    css/style.css          # Iron Man themed UI
    js/jarvis.js           # Frontend logic
  config/
    settings.py            # Configuration
  __main__.py              # CLI entry point
run_server.py              # Web server launcher
.env.example               # API key template
```

## Deployment - Access From Anywhere

### Option 1: Local Network (easiest)
```bash
./deploy.sh local
# Open http://your-computer-ip:8000 from any device on your WiFi
```

### Option 2: ngrok Tunnel (instant public URL)
```bash
# Install ngrok: https://ngrok.com/download
./deploy.sh ngrok
# Gives you a public URL like https://abc123.ngrok.io
# Share this URL — access Jarvis from anywhere in the world
```

### Option 3: Docker
```bash
./deploy.sh docker
# Or manually:
docker compose up --build
```

### Option 4: Render (free cloud hosting)
1. Push this repo to GitHub
2. Go to [render.com](https://render.com) and connect your repo
3. Render auto-detects `render.yaml` and deploys
4. Add your API keys in the Render dashboard under Environment
5. Get a free URL like `https://jarvis-ai.onrender.com`

### Option 5: Railway (free cloud hosting)
1. Go to [railway.app](https://railway.app)
2. Click "New Project" > "Deploy from GitHub"
3. Select this repo — Railway auto-detects `railway.json`
4. Add env vars in the Railway dashboard
5. Get a public URL automatically

### Option 6: Heroku
```bash
heroku create jarvis-ai
heroku config:set ANTHROPIC_API_KEY=your_key_here
git push heroku main
```

### Stop Jarvis
```bash
./deploy.sh stop
```

## Setup API Keys

All integrations work in **graceful degradation** mode — Jarvis runs without any API keys and enables features as you add them.

1. Copy `.env.example` to `.env`
2. Add your API keys (all are free tier):
   - **Claude AI**: https://console.anthropic.com
   - **Weather**: https://openweathermap.org/api
   - **News**: https://newsapi.org
   - **Spotify**: https://developer.spotify.com/dashboard
   - **Gmail**: https://developers.google.com/gmail/api/quickstart/python
   - **Home Assistant**: https://www.home-assistant.io
