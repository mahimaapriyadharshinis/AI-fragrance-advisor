<p align="center">
  <img src="static/pixel_banner.gif" alt="AI Scent Advisor Animated Pixel Art Banner" width="100%">
</p>
<p align="center">
  <img src="static/title_banner.gif" alt="AI Scent Advisor Pixel Title Banner" width="100%">
</p>

<p align="center" style="color: #504B5A; font-family: monospace; font-size: 1.1em;">
  An enterprise-grade, state-managed conversational recommendation system that guides users to their perfect fragrance using LangGraph state machines, MongoDB, and the Sarvam AI large language model.
</p>

<div style="height: 3px; background-color: #D8B4F8; border: none; margin: 25px 0;"></div>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Conversational System Overview</h2>

<blockquote style="border-left: 4px solid #F7C8E0; background-color: #FAF7F5; padding: 12px 18px; margin: 15px 0; color: #504B5A; font-family: monospace;">
  The AI Scent Advisor is an interactive, multi-turn conversational web application designed to narrow down user preferences for fragrances. Built with a Django backend and MongoDB Atlas, it implements a compiled state machine workflow via LangGraph to route dialogue turns, extract accords, query the product database, handle general scent queries, and format matching recommendations.
</blockquote>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Olfactory Navigation Challenges</h2>

<div style="background-color: #FAF7F5; border: 1px solid #D8B4F8; padding: 15px; border-radius: 4px; color: #504B5A; font-family: monospace;">
  Navigating the world of perfumery is overwhelming due to thousands of choices and complex olfactory terminology (e.g., sillage, dry-down, base notes). Users frequently struggle to find fragrances because:
  <ul>
    <li>Search engines rely on exact keyword matches rather than semantic scent preferences.</li>
    <li>Off-the-shelf LLMs lack real-time catalog access, leading to hallucinations of non-existent or discontinued perfumes.</li>
    <li>Conversational context easily drifts or breaks during complex, multi-turn queries.</li>
  </ul>
</div>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Advisor Objectives</h2>

<div style="background-color: #FAF7F5; border: 1px solid #F7C8E0; padding: 15px; border-radius: 4px; color: #504B5A; font-family: monospace; margin-top: 15px;">
  <ul>
    <li>Design a structured state-machine dialog tree to handle user interactions without losing track of current filters (gender, brand, disliked ingredients).</li>
    <li>Implement a semantic accord-mapping translator that maps simple terms (e.g., orange, lemon) to standardized accords (e.g., Citrus).</li>
    <li>Develop a database query interface translating natural language requests into complex MongoDB parameters.</li>
    <li>Provide a robust exception-handling layer ensuring context continuity during LLM timeouts or network disruptions.</li>
  </ul>
</div>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Core System Features</h2>

<div style="color: #504B5A; font-family: monospace; margin: 15px 0;">
  <ul>
    <li><strong>LangGraph State Orchestration</strong>: Structured routing via compiled state transitions.</li>
    <li><strong>Dynamic Accord Ingestion</strong>: Auto-translates custom inputs to catalog categories.</li>
    <li><strong>Resilient Fallback Middleware</strong>: Preserves turn counters and state variables if model services fail.</li>
    <li><strong>Multilingual Localization</strong>: Detects regional scripts (Tamil, Hindi) and switches UI text automatically.</li>
    <li><strong>Interactive Prompt-Pills</strong>: Auto-extracts bracketed keywords from text and displays them as clickable buttons.</li>
    <li><strong>Side-by-Side Glassmorphic Workspace</strong>: Split layout for conversational chat and matching catalog products.</li>
  </ul>
</div>

<div style="height: 3px; background-color: #D8B4F8; border: none; margin: 25px 0;"></div>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Olfactory Tech Stack</h2>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-2C1E38?style=flat-square&labelColor=D8B4F8" alt="Python">
  <img src="https://img.shields.io/badge/Django-6.0-2C1E38?style=flat-square&labelColor=F7C8E0" alt="Django">
  <img src="https://img.shields.io/badge/DRF-API-2C1E38?style=flat-square&labelColor=D8B4F8" alt="DRF">
  <img src="https://img.shields.io/badge/LangGraph-Orchestration-2C1E38?style=flat-square&labelColor=F7C8E0" alt="LangGraph">
  <img src="https://img.shields.io/badge/Sarvam_AI-LLM-2C1E38?style=flat-square&labelColor=D8B4F8" alt="Sarvam AI">
  <img src="https://img.shields.io/badge/MongoDB-Atlas-2C1E38?style=flat-square&labelColor=F7C8E0" alt="MongoDB">
  <br>
  <img src="https://img.shields.io/badge/HTML5-Structure-2C1E38?style=flat-square&labelColor=D8B4F8" alt="HTML5">
  <img src="https://img.shields.io/badge/CSS3-Style-2C1E38?style=flat-square&labelColor=F7C8E0" alt="CSS3">
  <img src="https://img.shields.io/badge/JavaScript-ES6-2C1E38?style=flat-square&labelColor=D8B4F8" alt="JavaScript">
</p>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Graph Architecture & State Routing</h2>

```mermaid
graph TD
    Start([User Input]) --> Router{router_edge}
    
    Router -->|Greeting / Standard Chat| ChatNode[chat]
    Router -->|Off-topic / Out-of-bounds| DeclineNode[decline]
    Router -->|Start Over / New Search| NewSearchNode[new_search]
    Router -->|Note Refinement / Search| RecommendNode[recommend]
    Router -->|Database-specific Q&A| DBQANode[db_qa]
    Router -->|General Fragrance Q&A| GeneralQANode[general_qa]
    
    ChatNode --> EndNode([Format Output & Save State])
    DeclineNode --> EndNode
    NewSearchNode --> EndNode
    RecommendNode --> EndNode
    DBQANode --> EndNode
    GeneralQANode --> EndNode
```

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Repository Layout</h2>

```text
fragrance_project/
├── chatbot/                    # Django application containing conversational logic
│   ├── graph.py                # LangGraph workflow state machine definition and nodes
│   ├── urls.py                 # REST API routing patterns
│   ├── utils.py                # Database helper clients, ingestion functions, and API adapters
│   └── views.py                # Django views wrapping graph execution
├── data/                       # Dataset directory
│   └── fragrances.csv          # Catalog containing fragrance names, brands, and notes
├── fragrance_project/          # Root configurations
│   ├── settings.py             # Security, static files, and application definitions
│   └── urls.py                 # Main URL router mapping view assets
├── static/                     # Assets assets
│   ├── pixel_banner.gif        # Header retro visual banner
│   ├── title_banner.gif        # Header title gradient banner
│   ├── css/index.css           # Glassmorphic visual stylesheet
│   └── js/index.js             # Async communication interface
├── templates/                  # Base document markups
│   └── index.html              # Primary viewport containing layout columns
├── manage.py                   # Administrative entry point
└── requirements.txt            # System dependencies manifest
```

<div style="height: 3px; background-color: #D8B4F8; border: none; margin: 25px 0;"></div>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">System Deployment Guide</h2>

### Setup Prerequisites

- Python 3.10+
- MongoDB instance (Local community edition or MongoDB Atlas URL)
- Sarvam AI API Access Key

### Environment Variables (.env)

Create a file named `.env` in the root folder of the project:

```env
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=false
SARVAM_API_KEY=your_sarvam_api_key_here
```

### Installation Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/mahimaapriyadharshinis/fragrance-advisor-project.git
   cd fragrance-advisor-project
   ```

2. **Initialize Environment & Install Packages**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Ingest Fragrance Database**
   Start the Django local development server:
   ```bash
   python manage.py runserver
   ```
   Execute a HTTP POST request targeting `/api/ingest/` (using Postman or curl) to parse and load `data/fragrances.csv` into MongoDB.

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Ingestion & Dialogue Execution</h2>

1. Start the Django backend server:
   ```bash
   python manage.py runserver
   ```
2. Navigate to `http://127.0.0.1:8000/` in a web browser.
3. Chat with the Scent Advisor to refine your choices. You can click on the dynamic prompt pills (bracketed suggestions) to choose pre-configured paths, or type raw messages detailing the brands and scent notes you prefer or dislike.

<div style="height: 3px; background-color: #D8B4F8; border: none; margin: 25px 0;"></div>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Conversational API Reference</h2>

### Chatbot Dialogue Endpoint

- **URL**: `/api/chat/`
- **Method**: `POST`
- **Payload**:
  ```json
  {
    "message": "I want a citrus fragrance from Chanel",
    "history": [],
    "recommended_perfumes": [],
    "other_perfumes": [],
    "brand_filter": null,
    "disliked_perfumes": [],
    "sort_by_best": false,
    "user_turns": 0
  }
  ```
- **Response**:
  ```json
  {
    "bot_reply": "I found several options containing Citrus notes for you. Would you like to view [Chanel Bleu]?",
    "recommended_products": [
      {
        "name": "Bleu de Chanel",
        "brand": "Chanel",
        "notes": "citrus, grapefruit, mint",
        "rating": 4.8
      }
    ],
    "other_products": [],
    "brand_filter": "Chanel",
    "disliked_perfumes": [],
    "sort_by_best": false,
    "user_turns": 1
  }
  ```

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">MongoDB Document Schema & Data Pipelines</h2>

Fragrance entities are stored inside the `fragrances` collection within MongoDB.

```json
{
  "_id": "ObjectId",
  "name": "String",
  "brand": "String",
  "notes": "String",
  "rating": "Double",
  "gender": "String",
  "accords": "Array [String]"
}
```

**Data Flow Sequence**:
1. User input is validated at `/api/chat/`.
2. State is loaded into the `AgentState` struct.
3. LangGraph determines intent and targets the correct node.
4. Queries search the database utilizing regex filters matching target criteria.
5. Search results are filtered to exclude items in `disliked_perfumes`.
6. Recommended matches are set in the state, and the response is serialized back to the frontend.

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">LangGraph Workflow & Sarvam AI Model Configuration</h2>

- **Core Model**: Sarvam AI API (Sarvam-30b model wrapper).
- **Orchestration**: LangGraph StateGraph compiling nodes into a structured workflow:
  - `chat`: Greets users and handles conversational dialogue.
  - `decline`: Catches out-of-scope or unrelated inputs.
  - `new_search`: Flushes state variables to start fresh recommendations.
  - `recommend`: Maps notes, extracts gender/brand profiles, and Queries MongoDB.
  - `db_qa`: Parses natural-language questions about catalog data and rating metrics.
  - `general_qa`: Resolves terminology and general scent classification concerns.

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Sample Dialogue Scenarios</h2>

- **Input**: "I hate sweet fragrances and want something fresh."
- **State Updated**: `disliked_perfumes` appended with "sweet".
- **Output**: "No problem! I have excluded sweet fragrances from your advisor search. How about a fresh wood or green tea scent?"

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Benchmark Performance</h2>

- **Context Retention**: Maintains user preferences up to 8 conversation turns without losing tracking variables.
- **Latency**: Under 1.5 seconds average latency per conversational cycle utilizing Sarvam AI streaming endpoints.

<div style="height: 3px; background-color: #D8B4F8; border: none; margin: 25px 0;"></div>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Project Acknowledgements</h2>

- Sarvam AI Team for model API support.
- LangGraph developers for state-management frameworks.

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Project License</h2>




