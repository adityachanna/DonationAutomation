# Flood Relief Campaign Automation API (FastAPI with Gemini)

## Overview

This application provides an API backend built with **FastAPI** to manage contacts and automate outreach campaigns for flood relief fundraising. It leverages the **CrewAI** framework integrated with **Google's Gemini 2 Flash** language model (via LangChain) to research flood situations, generate personalized donation requests (Email or WhatsApp), and optionally verify incoming requests. Contacts are stored in a local SQLite database. This version uses Pydantic for data validation and FastAPI's features for improved developer experience and automatic API documentation.

## Features

*   **Contact Management:** Add individual contacts or bulk import from CSV with validation.
*   **AI-Powered Research (Gemini):** Uses a CrewAI agent with the Gemini model to search for recent flood news (via potentially unreliable Google News RSS) and extract content from relevant URLs.
*   **AI-Powered Communication (Gemini):** Uses a CrewAI agent with the Gemini model to draft empathetic and personalized donation request messages (Email or WhatsApp) based on research.
*   **Multi-Channel Outreach:** Supports sending messages via Email (simulated placeholder) and WhatsApp (using Twilio).
*   **Request Verification (Gemini):** Includes an endpoint using a CrewAI agent with the Gemini model to analyze donation requests and provide an authenticity score.
*   **Campaign Execution:** Run outreach campaigns targeting specific regions and contacts via email or WhatsApp, driven by Gemini-generated content.
*   **Modern API Interface:** FastAPI provides automatic interactive documentation (Swagger UI at `/docs`, ReDoc at `/redoc`).
*   **Data Validation:** Uses Pydantic models for robust request and response validation.
*   **Database Storage:** Uses SQLite for persistent contact storage.
*   **Logging:** Basic logging for monitoring and debugging.
*   **Async Capable:** Uses `async def` endpoints (core AI/DB calls may still be blocking).

## Setup and Configuration

1.  **Clone Repository & Navigate:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-directory>
    ```

2.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate # Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    Create/update `requirements.txt`:
    ```txt
    # requirements.txt
    fastapi
    uvicorn[standard]
    requests
    beautifulsoup4
    crewai
    # langchain-openai # Removed or keep if needed elsewhere
    langchain-google-genai # Added for Gemini
    python-dotenv
    twilio
    pandas
    lxml
    # openai # Removed if not needed
    pydantic[email]
    ```
    Install:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Variables:**
    Create a `.env` file in the root directory:
    ```dotenv
    # .env
    # OPENAI_API_KEY="your_openai_api_key_here" # Optional
    GOOGLE_API_KEY="your_google_ai_api_key_here" # REQUIRED for Gemini
    TWILIO_ACCOUNT_SID="your_twilio_account_sid" # REQUIRED for WhatsApp
    TWILIO_AUTH_TOKEN="your_twilio_auth_token" # REQUIRED for WhatsApp
    TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886" # Your Twilio sender number
    DONATION_LINK="https://your-actual-donation-link.org" # REQUIRED for campaign messages
    ```
    *   `GOOGLE_API_KEY`: Your API key from Google AI Studio (required).
    *   `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`: Your Twilio credentials (required for WhatsApp).
    *   `TWILIO_WHATSAPP_NUMBER`: The Twilio WhatsApp number to send messages *from*.
    *   `DONATION_LINK`: The actual URL for the donation call-to-action in messages.

5.  **Database Initialization:**
    The database (`contacts_workflow.db`) is created automatically on first run via `init_db()`.

## Core Components

*   **Database (`contacts_workflow.db`):** Stores contact info (schema defined in `init_db`).
*   **Pydantic Models:** Define API data structures for validation (e.g., `ContactCreate`, `CampaignRunPayload`).
*   **CrewAI Agents & LLM:**
    *   Uses `langchain_google_genai.ChatGoogleGenerativeAI` to interact with the **Gemini Pro model**.
    *   Agents (`research_agent`, `email_writer_agent`, `verification_agent`) leverage the Gemini LLM for their tasks.
*   **CrewAI Tools:** `WebResearchTool` for searching news and extracting URL content (still relies on potentially unreliable web scraping).
*   **Communication Functions:** `send_email` (placeholder), `send_whatsapp` (uses Twilio).

## API Endpoints (FastAPI)

Base URL: `http://localhost:8000`
Interactive Docs: `http://localhost:8000/docs`

*(Refer to the interactive docs `/docs` for detailed request/response schemas defined by Pydantic models)*

1.  **Add Contact:** `POST /contacts`
2.  **Import Contacts:** `POST /contacts/import` (CSV upload)
3.  **Verify Request:** `POST /verify` (AI-powered authenticity check)
4.  **Run Campaign:** `POST /campaigns/run` (Initiates research & outreach)
5.  **Root:** `GET /` (Basic info)
6.  **Health Check:** `GET /health` (Checks API and DB status)

## Running the Application

1.  Ensure `.env` is correctly configured with `GOOGLE_API_KEY`, Twilio keys, and `DONATION_LINK`.
2.  Activate virtual environment: `source venv/bin/activate`.
3.  Run with Uvicorn (for development):
    ```bash
    uvicorn main_fastapi:app --host 0.0.0.0 --port 8000 --reload
    ```
4.  Access the API at `http://localhost:8000` and docs at `http://localhost:8000/docs`.

## Potential Improvements & Considerations

*   **Async Operations:** Address blocking calls (`crew.kickoff`, DB, `requests`) using `asyncio.run_in_executor` or fully async libraries (`httpx`, `aiosqlite`) for better performance under load.
*   **Background Tasks:** Use FastAPI's `BackgroundTasks` or a task queue (Celery, ARQ) for long-running jobs like `/campaigns/run` and `/contacts/import`.
*   **(Same as before)** Implement real email sending.
*   **(Same as before)** Web scraping reliability is a concern. Use official APIs if available.
*   **Prompt Engineering:** Prompts within `create_tasks` might need tuning specifically for optimal Gemini performance and output formatting (especially the JSON for `/verify`).
*   **(Same as before)** Use a robust phone number validation library (`phonenumbers`).
*   **(Same as before)** Implement API authentication/authorization.
*   **(Same as before)** Add automated tests (`pytest`, `TestClient`).
*   **Gemini Costs/Quotas:** Be mindful of Google AI API usage costs and rate limits associated with the Gemini model.
