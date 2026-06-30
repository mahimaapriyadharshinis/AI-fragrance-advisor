<p align="center">
  <img src="static/pixel_banner.gif" alt="AI Scent Advisor Animated Pixel Art Banner" width="100%">
</p>
<p align="center">
  <img src="static/title_banner.gif" alt="AI Scent Advisor Pixel Title Banner" width="100%">
</p>

<p align="center" style="color: #504B5A; font-family: monospace; font-size: 1.1em;">
  An enterprise-grade, state-managed conversational recommendation system that guides users to their perfect fragrance using LangGraph state machines, MongoDB, and the Sarvam AI large language model.
</p>

<p align="center"><img src="https://raw.githubusercontent.com/mahimaapriyadharshinis/fragrance-advisor-project/main/static/divider.gif" alt="themed divider" width="100%"></p>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Project Overview</h2>

<blockquote style="border-left: 4px solid #F7C8E0; background-color: #FAF7F5; padding: 12px 18px; margin: 15px 0; color: #504B5A; font-family: monospace;">
  The AI Scent Advisor is an interactive, multi-turn conversational web application designed to narrow down user preferences for fragrances. Built with a Django backend and MongoDB Atlas, it implements a compiled state machine workflow via LangGraph to route dialogue turns, extract accords, query the product database, handle general scent queries, and format matching recommendations.
</blockquote>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">User Interface & Aesthetics</h2>

<div style="background-color: #FAF7F5; border: 1px solid #F7C8E0; padding: 15px; border-radius: 4px; color: #504B5A; font-family: monospace; margin-bottom: 15px;">
  To complement the sensory experience of perfumery, this repository features custom pixel-art animations and design styling:
  <ul>
    <li><strong>Calm Lavender & Rose Gradient Palette</strong>: Visual highlights match a calm Warm Cream, Soft Lavender, and pastel Rose color theme.</li>
    <li><strong>Animated Store Scenario Banner</strong>: A pixel-art storefront animation showing a customer interacting with fragrance bottles, testing rose mist spray, and triggering interactive feedback.</li>
    <li><strong>Multi-Colored Neon Scanner Title</strong>: High-contrast title typography where characters glow bright white as a neon scent scanner sweeps across.</li>
    <li><strong>Glowing Sparkle Dividers</strong>: Animated horizontal separator lines displaying a glowing white shimmer wave to break up sections gracefully on GitHub pages.</li>
  </ul>
</div>

<p align="center"><img src="https://raw.githubusercontent.com/mahimaapriyadharshinis/fragrance-advisor-project/main/static/divider.gif" alt="themed divider" width="100%"></p>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">System Technology Stack</h2>

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

<p align="center"><img src="https://raw.githubusercontent.com/mahimaapriyadharshinis/fragrance-advisor-project/main/static/divider.gif" alt="themed divider" width="100%"></p>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">Installation & Deployment Guide</h2>

### Environment Configuration (.env)

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
   Start the Django server, then run an HTTP POST request targeting `/api/ingest/` (using Postman or curl) to load `data/fragrances.csv` into MongoDB.
   ```bash
   python manage.py runserver
   ```

4. **Dialogue Execution**
   Navigate to `http://127.0.0.1:8000/` in a web browser to chat with the Scent Advisor to refine your choices.

<p align="center"><img src="https://raw.githubusercontent.com/mahimaapriyadharshinis/fragrance-advisor-project/main/static/divider.gif" alt="themed divider" width="100%"></p>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">API Architecture & Integration</h2>

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

<p align="center"><img src="https://raw.githubusercontent.com/mahimaapriyadharshinis/fragrance-advisor-project/main/static/divider.gif" alt="themed divider" width="100%"></p>

<h2 style="color: #2C1E38; border-left: 4px solid #D8B4F8; padding-left: 10px;">State Management & Data Pipeline</h2>

### MongoDB Document Schema

Fragrance entities are stored inside the `fragrances` collection within MongoDB:

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

### LangGraph State Machine Routing

- **Core Model**: Sarvam AI API (Sarvam-30b model wrapper).
- **Orchestration**: LangGraph StateGraph compiling nodes into a structured workflow:
  - `translate_input`: Translates incoming user messages to standard English if typed in regional languages (like Tamil or Hindi) before state routing.
  - `chat`: Directs the user to a clarifying dialogue to narrow down fragrance profiles.
  - `decline`: Gracefully handles out-of-scope or off-topic queries.
  - `new_search`: Flushes active filter states to begin a fresh recommendation query.
  - `extract_intent`: Maps user input to extract target brand, note preferences, accords, and gender target filters.
  - `db_query`: Queries MongoDB collections matching extracted filters to find matching perfumes.
  - `generate_pitch`: Creates a tailored marketing pitch for the top recommended perfumes.
  - `qa`: Resolves general fragrance terminology and olfactory classifications.
  - `database_qa`: Handles specific questions about metrics, ratings, or perfume brands within the database.

```mermaid
graph TD
    classDef startEnd fill:#FAF7F5,stroke:#2C1E38,stroke-width:2px,color:#2C1E38,font-family:monospace;
    classDef nodeStyle fill:#FAF7F5,stroke:#D8B4F8,stroke-width:2px,color:#2C1E38,font-family:monospace;
    classDef decStyle fill:#FAF7F5,stroke:#F7C8E0,stroke-width:2px,color:#2C1E38,font-family:monospace;

    Start([User Input]):::startEnd --> TransNode[translate_input]:::nodeStyle
    TransNode --> Router{router_edge}:::decStyle
    
    Router -->|decline| DeclineNode[decline]:::nodeStyle
    Router -->|chat| ChatNode[chat]:::nodeStyle
    Router -->|qa| QANode[qa]:::nodeStyle
    Router -->|recommend| ExtractNode[extract_intent]:::nodeStyle
    Router -->|new_search| NewSearchNode[new_search]:::nodeStyle
    Router -->|database_qa| DBQANode[database_qa]:::nodeStyle
    
    ExtractNode --> DBQueryNode[db_query]:::nodeStyle
    DBQueryNode --> PostRouter{post_query_router}:::decStyle
    PostRouter -->|pitch| PitchNode[generate_pitch]:::nodeStyle
    PostRouter -->|chat| ChatNode
    
    NewSearchNode --> ChatNode
    
    DeclineNode --> EndNode([Format Output & Save State]):::startEnd
    ChatNode --> EndNode
    QANode --> EndNode
    DBQANode --> EndNode
    PitchNode --> EndNode
```


