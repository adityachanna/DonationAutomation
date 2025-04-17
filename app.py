import os
import sqlite3
from contextlib import contextmanager
from typing import List, Optional

# Email imports
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
# LangChain Schema Output Parsers can be useful, but not strictly needed for this basic JSON parsing
# from langchain.schema.output_parser import StrOutputParser
# from langchain_core.output_parsers.json import JsonOutputParser # More robust JSON parsing

# --- Configuration & Setup ---
load_dotenv()

DATABASE_URL = "relief_campaign.db"
EXAMPLE_DONATION_LINK = "https://www.example-relief-fund.org/donate/flood-support" # <-- Added Example Donation Link

# Email Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_SMTP_PORT = os.getenv("EMAIL_SMTP_PORT")

# Basic check if email config is present
EMAIL_CONFIGURED = all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT])
if not EMAIL_CONFIGURED:
    print("⚠️ WARNING: Email configuration missing in .env file. Email sending will be disabled.")
    print("           Required: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT")

# Initialize FastAPI app
app = FastAPI(
    title="Simplified Relief Campaign API",
    description="Manages contacts and uses AI for outreach via Email/WhatsApp (simulated). Includes example contacts and donation link.",
)

# Initialize LangChain with Gemini
try:
    google_api_key = os.getenv("GEMINI_API_KEY")
    if not google_api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
    # Using gemini-1.5-flash as it's generally available and capable
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=google_api_key)
    print("✅ Gemini LLM Initialized (gemini-2.0-flash)")
except Exception as e:
    print(f"❌ Error initializing Gemini LLM: {e}")
    print("   Please ensure GOOGLE_API_KEY is set correctly in your .env file.")
    llm = None # Set LLM to None if initialization fails

# --- Database Setup (Simplified SQLite) ---

def init_db():
    """Initialize the SQLite database, create tables, and add example contacts if they don't exist."""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        phone TEXT UNIQUE -- Keep phone for potential future WhatsApp use
    )
    """)
    conn.commit() # Commit table creation first

    # --- Add Example Contacts (if they don't exist) ---
    example_contacts = [
        {"name": "Aditya Chan", "email": "adityachannadelhi@gmail.com", "phone": "111-111-1111"},
        {"name": "King Chan", "email": "kingchananacok@gmail.com", "phone": "222-222-2222"},
        {"name": "Test User NoEmail", "email": None, "phone": "333-333-3333"}
    ]

    added_count = 0
    for contact in example_contacts:
        # Check if email exists (if provided) OR phone exists (if email is not provided)
        check_value = contact['email'] if contact['email'] else contact['phone']
        column_to_check = "email" if contact['email'] else "phone"

        if check_value: # Only proceed if we have an email or phone to check/insert
            cursor.execute(f"SELECT id FROM contacts WHERE {column_to_check} = ?", (check_value,))
            existing = cursor.fetchone()
            if not existing:
                try:
                    cursor.execute(
                        "INSERT INTO contacts (name, email, phone) VALUES (?, ?, ?)",
                        (contact['name'], contact['email'], contact['phone'])
                    )
                    conn.commit()
                    added_count += 1
                    print(f"   -> Added example contact: {contact['name']} ({contact['email'] or contact['phone']})")
                except sqlite3.IntegrityError:
                     # Should not happen due to the check, but handle just in case
                     print(f"   -> Warning: Integrity error attempting to add {contact['name']}, likely race condition or logic issue.")
                     conn.rollback()
            # else: # Uncomment for verbose logging
            #     print(f"   -> Example contact '{contact['name']}' already exists.")

    if added_count > 0:
        print(f"✅ Added {added_count} new example contacts to the database.")
    else:
        print("✅ Example contacts already exist or none to add.")

    conn.close()

@contextmanager
def get_db_conn():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

# Call init_db() on startup
print("Initializing Database...")
init_db()
print("Database Initialization Complete.")


# --- Pydantic Models (Data Validation) ---

class ContactBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactResponse(ContactBase):
    id: int

    class Config:
        from_attributes = True # Updated for Pydantic v2+

class CampaignRequest(BaseModel):
    flood_location: str = Field(..., examples=["Houston, Texas"])
    target_contact_ids: List[int] = Field(..., examples=[[1, 2]]) # Updated example IDs
    email_subject: str = Field("Urgent: Support Needed for {location} Flood Relief", examples=["Help Needed: {location} Floods"])


# --- Database Operations ---

def db_create_contact(conn: sqlite3.Connection, contact: ContactCreate) -> int:
    """Creates a new contact in the database."""
    if not contact.email and not contact.phone:
         raise ValueError("At least one of email or phone must be provided.")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO contacts (name, email, phone) VALUES (?, ?, ?)",
            (contact.name, contact.email, contact.phone)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        # Provide more specific feedback based on UNIQUE constraints
        error_detail = str(e).lower()
        if "unique constraint failed: contacts.email" in error_detail:
             raise ValueError(f"Contact with email '{contact.email}' already exists.")
        elif "unique constraint failed: contacts.phone" in error_detail:
             raise ValueError(f"Contact with phone '{contact.phone}' already exists.")
        else:
             raise ValueError(f"Contact with email '{contact.email}' or phone '{contact.phone}' might already exist (Integrity Error).") # Fallback
    except Exception as e:
        conn.rollback()
        raise e


def db_get_contact_by_id(conn: sqlite3.Connection, contact_id: int) -> Optional[dict]:
    """Retrieves a contact by its ID."""
    conn.row_factory = sqlite3.Row # Return results as dictionary-like objects
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, phone FROM contacts WHERE id = ?", (contact_id,))
    row = cursor.fetchone()
    conn.row_factory = None # Reset row factory
    if row:
        return dict(row)
    return None

def db_get_contacts_by_ids(conn: sqlite3.Connection, contact_ids: List[int]) -> List[dict]:
    """Retrieves multiple contacts by their IDs."""
    if not contact_ids:
        return []
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(contact_ids))
    query = f"SELECT id, name, email, phone FROM contacts WHERE id IN ({placeholders})"
    cursor.execute(query, contact_ids)
    rows = cursor.fetchall()
    conn.row_factory = None
    return [dict(row) for row in rows]

# --- AI Workflow Function ---

async def generate_outreach_content(location: str) -> dict:
    """
    Uses Gemini to research the flood and generate an outreach message body.
    """
    if not llm:
         return {
             "error": "LLM not initialized. Check API Key.",
             "research_summary": "N/A",
             "message_template": f"Default message: Please donate to help flood victims in {location}. [Donation Link] (AI generation failed)", # Ensure default includes placeholder
             "verification": "N/A",
         }

    prompt_template = PromptTemplate.from_template(
        """
        You are an assistant for a relief organization helping flood victims in {location}.
        1. Briefly summarize the recent flood situation in {location} (1-2 sentences). Assume a significant event occurred requiring aid.
        2. Based on the situation, write an empathetic email body (2-4 sentences) asking for donations. Address the reader generally (e.g., start directly with the appeal or use "Dear friend,"). Mention the location. Crucially, include the exact placeholder text "[Donation Link]" where the donation link should go.
        3. Provide a brief verification statement (1 sentence) confirming that relief efforts are likely needed based on the summary (e.g., "Relief efforts are appropriate given the situation.").

        Return the response strictly as a JSON object with keys 'research_summary', 'message_template' (this is the email body including '[Donation Link]'), and 'verification'. Ensure the entire response is a single, valid JSON object.

        Example Output for "City X":
        {{
          "research_summary": "Recent heavy rains have caused significant flooding and displacement in City X, impacting numerous homes and infrastructure.",
          "message_template": "The recent devastating floods in City X have left many families in urgent need of assistance. Your contribution can provide essential supplies like food, water, and temporary shelter during this critical time. Please consider donating today to support the relief efforts. [Donation Link]",
          "verification": "Based on reports of widespread flooding and displacement, relief efforts are urgently needed."
        }}
        ---
        Location: {location}
        Respond ONLY with the JSON object. Do not include markdown formatting like ```json ... ```.
        """
    )
    # Consider using langchain_core.output_parsers.JsonOutputParser for robustness
    chain = prompt_template | llm

    try:
        response = await chain.ainvoke({"location": location})
        content = response.content.strip()

        # Attempt to parse the JSON
        import json
        try:
            # Basic cleanup (sometimes LLMs add markdown fences)
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed_content = json.loads(content)
            # Validate keys and placeholder presence
            if not all(k in parsed_content for k in ["research_summary", "message_template", "verification"]):
                 raise ValueError("LLM JSON response missing required keys.")
            if "[Donation Link]" not in parsed_content.get("message_template", ""):
                 print(f"⚠️ Warning: LLM response 'message_template' did not contain the '[Donation Link]' placeholder. Raw content: {content}")
                 # Optionally, force add it, or use a default message entirely
                 # parsed_content["message_template"] += " [Donation Link]" # Example fix
                 raise ValueError("LLM message_template missing '[Donation Link]' placeholder.")

            return parsed_content
        except (json.JSONDecodeError, ValueError) as json_e:
             print(f"⚠️ Warning: Could not parse LLM JSON response or validation failed: {json_e}")
             print(f"   Raw LLM Output: {content}")
             # Provide a fallback structure but indicate the issue
             return {
                 "error": f"LLM response format error: {json_e}",
                 "research_summary": "Parsing failed.",
                 "message_template": f"Default message: Please donate to help flood victims in {location}. [Donation Link] (AI generation failed)", # Default includes placeholder
                 "verification": "Parsing failed.",
             }

    except Exception as e:
        print(f"❌ Error during LLM call: {e}")
        return {
            "error": str(e),
            "research_summary": "Error during generation.",
            "message_template": f"Default message: Please donate to help flood victims in {location}. [Donation Link] (AI generation failed)", # Default includes placeholder
            "verification": "Error during generation.",
        }


# --- Email Sending Function ---

def send_email(to_email: str, subject: str, body: str) -> bool:
    """Sends an email using configured SMTP settings."""
    if not EMAIL_CONFIGURED:
        print(f"  -> Skipping email to {to_email}: Email not configured.")
        return False

    if not to_email:
         print(f"  -> Skipping email: No 'to_email' address provided.")
         return False


    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = to_email
    msg.set_content(body) # Use set_content for plain text

    try:
        print(f"  -> Attempting to send email to {to_email} via {EMAIL_SMTP_SERVER}:{EMAIL_SMTP_PORT}...")
        # Ensure port is integer
        smtp_port = int(EMAIL_SMTP_PORT)
        # Use SMTP_SSL for ports like 465, otherwise use standard SMTP with starttls
        if smtp_port == 465:
             server = smtplib.SMTP_SSL(EMAIL_SMTP_SERVER, smtp_port)
        else:
             server = smtplib.SMTP(EMAIL_SMTP_SERVER, smtp_port)
             server.ehlo() # Identify client to server
             server.starttls() # Secure the connection
             server.ehlo() # Re-identify after starting TLS

        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email successfully sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
         print(f"❌ SMTP Authentication Error sending email to {to_email}: {e.status_code} {e.detail}")
         print("   Check EMAIL_SENDER and EMAIL_PASSWORD (Use App Password for Gmail/Google Workspace).")
         return False
    except smtplib.SMTPServerDisconnected:
        print(f"❌ SMTP Server Disconnected unexpectedly for {to_email}. Check server/port/TLS settings.")
        return False
    except ConnectionRefusedError:
         print(f"❌ Connection Refused sending email to {to_email}. Check EMAIL_SMTP_SERVER and EMAIL_SMTP_PORT.")
         return False
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {type(e).__name__} - {e}")
        return False

# --- API Endpoints ---

@app.post("/contacts/", response_model=ContactResponse, status_code=201)
def create_contact(contact: ContactCreate):
    """Creates a new contact. Requires name and at least email or phone."""
    try:
        with get_db_conn() as conn:
            contact_id = db_create_contact(conn, contact)
            # Fetch the newly created contact data using the ID
            created_contact_data = db_get_contact_by_id(conn, contact_id)
            if created_contact_data:
                 # Use Pydantic model for response validation
                 return ContactResponse(**created_contact_data)
            else:
                 # This case should ideally not happen if insert was successful
                 raise HTTPException(status_code=500, detail="Failed to retrieve created contact after insert.")
    except ValueError as e: # Catch specific validation errors from db_create_contact
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating contact: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/contacts/{contact_id}", response_model=ContactResponse)
def get_contact(contact_id: int):
    """Retrieves a specific contact by ID."""
    with get_db_conn() as conn:
        contact_data = db_get_contact_by_id(conn, contact_id)
    if contact_data:
        return ContactResponse(**contact_data)
    else:
        raise HTTPException(status_code=404, detail="Contact not found")


@app.post("/campaign/trigger/")
async def trigger_campaign(request: CampaignRequest):
    """
    Triggers the AI workflow for a flood location, generates personalized emails
    with a donation link, and sends them to specified contact IDs.
    """
    print(f"\n--- Triggering Campaign ---")
    print(f"Location: {request.flood_location}")
    print(f"Target Contact IDs: {request.target_contact_ids}")
    print(f"Email Subject Template: '{request.email_subject}'")
    print(f"Using Donation Link: {EXAMPLE_DONATION_LINK}")

    # 1. Get AI-generated content
    print("\n1. Generating AI Content...")
    if not llm:
        raise HTTPException(status_code=503, detail="LLM service is not available. Cannot generate campaign content.")

    ai_content = await generate_outreach_content(request.flood_location)
    ai_error = ai_content.get("error")
    message_body_template = ai_content.get("message_template") # This should contain [Donation Link]

    if ai_error:
         print(f"⚠️ AI content generation failed or had issues: {ai_error}")
         # Decide if we proceed with default or fail - here we proceed with default
         print("   -> Proceeding with default message template due to AI error.")
         # Ensure the default template is defined and includes the placeholder if needed
         if not message_body_template or "[Donation Link]" not in message_body_template:
              message_body_template = f"Default message: Please donate to help flood victims in {request.flood_location}. [Donation Link] (AI generation failed)"

    print(f"   -> AI Research Summary: {ai_content.get('research_summary', 'N/A')}")
    print(f"   -> AI Message Template: {message_body_template}") # Show template before personalization
    print(f"   -> AI Verification: {ai_content.get('verification', 'N/A')}")


    # 2. Retrieve contacts from DB
    print("\n2. Retrieving Target Contacts...")
    contacts_to_message = []
    if request.target_contact_ids:
        with get_db_conn() as conn:
            contacts_to_message = db_get_contacts_by_ids(conn, request.target_contact_ids)
        print(f"   -> Found {len(contacts_to_message)} matching contacts in DB.")
    else:
        print("   -> No target contact IDs provided.")


    if not contacts_to_message:
        print("Warning: No target contacts found or specified. No messages will be sent.")

    # 3. Send messages
    print("\n3. Sending Outreach Messages...")
    sent_count = 0
    failed_count = 0
    skipped_no_email = 0

    for contact in contacts_to_message:
        contact_id = contact['id']
        contact_name = contact['name']
        contact_email = contact.get('email') # Use .get for safety
        contact_phone = contact.get('phone')

        print(f"Processing Contact ID: {contact_id} ({contact_name})")

        if contact_email:
            # Personalize subject
            subject = request.email_subject.format(location=request.flood_location)

            # Personalize body: Add greeting and replace donation link placeholder
            personalized_body = f"Dear {contact_name},\n\n{message_body_template}"
            final_body = personalized_body.replace("[Donation Link]", EXAMPLE_DONATION_LINK)

            # Display final body for debugging (optional)
            # print(f"   -> Final Email Body for {contact_email}:\n{final_body}\n--------------------")

            if send_email(contact_email, subject, final_body):
                sent_count += 1
            else:
                failed_count += 1
        else:
            print(f"  -> Skipping email for contact ID {contact_id} ({contact_name}): No email address found.")
            skipped_no_email += 1

        # Simulate WhatsApp/SMS sending (if phone exists)
        if contact_phone:
            # In a real app, you'd format a specific SMS/WhatsApp message here
            # For now, just simulate based on the email content concept
            sms_body_template = ai_content.get("message_template", f"Support needed for {request.flood_location} relief.") # Could use a shorter AI template for SMS
            sms_body = f"Hi {contact_name}, {sms_body_template}".replace("[Donation Link]", EXAMPLE_DONATION_LINK) # Replace link here too
            print(f"  -> SIMULATING WhatsApp/SMS to {contact_phone}: \"{sms_body[:70]}...\"") # Show truncated message


    print("\n--- Campaign Processing Complete ---")

    return {
        "status": "Campaign trigger processed",
        "flood_location": request.flood_location,
        "ai_research_summary": ai_content.get("research_summary", "N/A"),
        "ai_message_template_used": message_body_template, # Show the template before personalization
        "ai_verification": ai_content.get("verification", "N/A"),
        "donation_link_included": EXAMPLE_DONATION_LINK, # Confirm link used
        "contacts_target_ids": request.target_contact_ids,
        "contacts_found_in_db": len(contacts_to_message),
        "emails_sent_successfully": sent_count,
        "emails_failed_or_skipped_config": failed_count,
        "contacts_skipped_no_email": skipped_no_email,
        "ai_error_details": ai_error # Include AI error in response if exists
    }


# --- Run the App ---
if __name__ == "__main__":
    import uvicorn
    print("\n--- Server Startup Checks ---")
    if not llm:
         print("🛑 FATAL: LLM failed to initialize. API started but /campaign/trigger/ will fail.")
         print("   Please check your GEMINI_API_KEY and network connection.\n")
         # Optionally exit: import sys; sys.exit(1)
    else:
        print("✅ LLM Initialized.")

    if not EMAIL_CONFIGURED:
         print("⚠️ WARNING: Email configuration is missing or incomplete in .env.")
         print("   API will run, but emails cannot be sent.")
         print("   Check: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT.\n")
    else:
        print("✅ Email Configuration Loaded.")
        # Quick SMTP check (optional, can slow startup)
        # try:
        #     print("   -> Performing quick SMTP connection test...")
        #     smtp_port = int(EMAIL_SMTP_PORT)
        #     server = smtplib.SMTP(EMAIL_SMTP_SERVER, smtp_port, timeout=5)
        #     server.starttls()
        #     server.quit()
        #     print("   -> SMTP connection test successful.")
        # except Exception as smtp_e:
        #     print(f"   -> SMTP connection test failed: {smtp_e}. Check settings.")


    print("\n🚀 Starting FastAPI server...")
    print(f"   Database file: {DATABASE_URL}")
    print(f"   Default example contacts should have IDs 1 (Aditya) and 2 (King) if DB was empty.")
    print(f"   Test campaign targeting IDs [1, 2].")
    print(f"   Access Swagger UI at http://127.0.0.1:8000/docs")
    print(f"   Access ReDoc UI at http://127.0.0.1:8000/redoc")
    print("---")
    uvicorn.run(app, host="127.0.0.1", port=8000)
