# AI Scent Advisor

The AI Scent Advisor is an interactive, conversational web application designed to guide users in finding their perfect fragrance. Integrating a Django backend with MongoDB and the Sarvam AI large language model, the system facilitates a structured, multi-turn dialogue to determine user preferences before matching and recommending fragrances from a curated catalog.

## Features

- **Multi-Turn Conversational Discovery**: Engages users in a structured clarification dialogue (up to 3 turns) to capture detailed scent preferences such as accords, gender categories, and desired aesthetics.
- **Dynamic Choice Buttons**: Automatically parses option recommendations from the AI's responses and displays them as clickable buttons on the frontend.
- **Intent Extraction**: Utilizes the Sarvam AI model to parse natural language dialogues into structured database queries.
- **Database Matching**: Queries a local MongoDB instance to match fragrance characteristics (main accords, gender) against a catalog of nearly 2,000 scents, sorting recommendations by rating value.
- **Clean Dashboard UI**: Features a modern, split-screen, glassmorphic layout displaying the interactive chat interface on the left and recommended products side-by-side on the right.

## Tech Stack

- **Backend**: Python 3.13, Django 6.0, Django REST Framework
- **Frontend**: HTML5, Vanilla CSS3, Javascript (ES6)
- **Database**: MongoDB (Atlas/Local)
- **AI Integrations**: Sarvam AI API (sarvam-30b model)

## Project Structure

```text
fragrance_project/
│
├── chatbot/                # Django Application containing core logic
│   ├── urls.py             # API Endpoint Routing
│   ├── utils.py            # MongoDB helper queries & Sarvam API callers
│   └── views.py            # Request handlers & Conversational turn managers
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
   Ensure the database is running and call the ingestion command:
   ```bash
   python manage.py runserver
   ```
   Submit a POST request to `http://127.0.0.1:8000/api/ingest/` to load the fragrance dataset from `data/fragrances.csv` into MongoDB.

## Running the Application

Start the Django development server:
```bash
python manage.py runserver
```

Open a web browser and navigate to `http://127.0.0.1:8000/` to access the application.
