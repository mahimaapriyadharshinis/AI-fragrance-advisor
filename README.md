# AI Scent Advisor

The AI Scent Advisor is an interactive, conversational web application designed to guide users in finding their perfect fragrance. Integrating a Django backend with MongoDB and the Sarvam AI large language model using a compiled LangGraph state machine workflow, the system facilitates a structured, multi-turn dialogue to determine user preferences before matching and recommending fragrances from a curated catalog.

## Features

- **State Machine Dialogue Management**: Implements a compiled LangGraph state machine to handle chat routing, intent extraction, database queries, Q&A, and recommendation states dynamically based on conversation turns and user request types.
- **Dynamic Intent Extraction and Accord Mapping**: Analyzes dialogue transcripts to extract target demographics (gender), brand parameters, and fragrance accords. Maps user-inputted note keywords to broader fragrance categories (e.g. mapping citrus notes to citrus accords) for database matching.
- **Custom Database Q&A Node**: Supports natural language queries about the fragrance collection. Generates MongoDB query filters dynamically to answer database-specific questions (such as top-rated perfumes, review counts, and comparisons) with support for relaxed regex mapping to bypass database name spacing inconsistencies.
- **General Fragrance Q&A Node**: Answers general questions about fragrance terminology, sillage, longevity, concentration classifications (such as Eau de Parfum vs. Eau de Toilette), and styling tips using expert knowledge.
- **Multi-Language Script and Transition Rules**: Detects non-English inputs (such as Hindi or Tamil scripts) and outputs responses in the corresponding script, with automatic switchback to English if the user inputs their next message in English.
- **Dynamic Prompt-Pill Generation**: Extracts bracketed selection suggestions from the model response text and renders them on the frontend as clickable prompt buttons.
- **Exception Safety and State Continuity**: Recovers gracefully from model timeouts, network exceptions, or empty reasoning completions without disrupting the session or resetting the user turn counters.
- **Aesthetic Glassmorphic UI**: Design layout displaying the chat workspace and recommended products side-by-side.

## Tech Stack

- **Backend**: Python 3.13, Django 6.0, Django REST Framework, LangGraph, PyMongo
- **Frontend**: HTML5, Vanilla CSS3, Javascript (ES6)
- **Database**: MongoDB (Atlas/Local)
- **AI Integrations**: Sarvam AI API (sarvam-30b model)

## Project Structure

```text
fragrance_project/
│
├── chatbot/                # Django Application containing core logic
│   ├── graph.py            # LangGraph workflow state machine, routing, and nodes
│   ├── urls.py             # API Endpoint Routing
│   ├── utils.py            # MongoDB client connection, CSV data ingestion, and Sarvam API wrapper
│   └── views.py            # API request handlers wrapping the state graph
│
├── data/                   # Raw fragrance dataset
│   └── fragrances.csv      # CSV containing perfume details
│
├── fragrance_project/      # Main Django project configurations
│   ├── settings.py         # App configurations, static paths, & database definitions
│   └── urls.py             # Main router mapping API and homepage views
│
├── static/                 # Static Assets
│   ├── css/index.css       # Layout styles and custom variables
│   └── js/index.js         # Frontend request pipeline and dynamic DOM renderers
│
└── templates/              # HTML Templates
    └── index.html          # Core user interface entry point
```

## Installation

### Prerequisites

- Python 3.10+
- MongoDB instance (Local or Atlas Cluster)
- Sarvam AI API Credentials

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/fragrance-advisor-project.git
   cd fragrance-advisor-project
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory and add the following variables:
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=false
   SARVAM_API_KEY=your_sarvam_api_key_here
   ```

5. **Ingest Fragrance Data**:
   Ensure the database is running and start the Django server:
   ```bash
   python manage.py runserver
   ```
   Submit an HTTP POST request to `http://127.0.0.1:8000/api/ingest/` to load the fragrance dataset from `data/fragrances.csv` into MongoDB.

## Running the Application

Start the Django development server:
```bash
python manage.py runserver
```

Open a web browser and navigate to `http://127.0.0.1:8000/` to access the application interface.

