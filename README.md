# Relief Campaign API Documentation

This document provides detailed information about the API endpoints available in the Relief Campaign system.

## Base URL

When running locally, the API is available at:
```
http://127.0.0.1:8000
```

## Authentication

Currently, this API does not implement authentication. For production use, consider adding OAuth2 or API key authentication.

## Endpoints

### Contacts

#### Create Contact

Creates a new contact in the database.

- **URL:** `/contacts/`
- **Method:** `POST`
- **Request Body:**

```json
{
  "name": "string",
  "email": "string",
  "phone": "string"
}
```

Notes:
- Either `email` or `phone` must be provided
- Both `email` and `phone` must be unique

- **Success Response:**
  - **Status Code:** 201 (Created)
  - **Response Body:**
  ```json
  {
    "id": 1,
    "name": "string",
    "email": "string",
    "phone": "string"
  }
  ```

- **Error Responses:**
  - **Status Code:** 400 (Bad Request)
    - If contact validation fails
    - If email or phone already exists
  - **Status Code:** 500 (Internal Server Error)
    - If there's a server-side issue

#### Get Contact

Retrieves a specific contact by ID.

- **URL:** `/contacts/{contact_id}`
- **Method:** `GET`
- **URL Parameters:**
  - `contact_id`: ID of the contact to retrieve

- **Success Response:**
  - **Status Code:** 200 (OK)
  - **Response Body:**
  ```json
  {
    "id": 1,
    "name": "string",
    "email": "string",
    "phone": "string"
  }
  ```

- **Error Response:**
  - **Status Code:** 404 (Not Found)
    - If contact with the specified ID doesn't exist

### Campaign

#### Trigger Campaign

Initiates a flood relief campaign with AI-generated content.

- **URL:** `/campaign/trigger/`
- **Method:** `POST`
- **Request Body:**

```json
{
  "flood_location": "string",
  "target_contact_ids": [integer],
  "email_subject": "string"
}
```

Notes:
- `flood_location` should be a city or region name
- `target_contact_ids` is an array of contact IDs to message
- `email_subject` can include `{location}` as a placeholder

- **Success Response:**
  - **Status Code:** 200 (OK)
  - **Response Body:**
  ```json
  {
    "status": "Campaign trigger processed",
    "flood_location": "string",
    "ai_research_summary": "string",
    "ai_message_template_used": "string",
    "ai_verification": "string",
    "donation_link_included": "string",
    "contacts_target_ids": [integer],
    "contacts_found_in_db": integer,
    "emails_sent_successfully": integer,
    "emails_failed_or_skipped_config": integer,
    "contacts_skipped_no_email": integer,
    "ai_error_details": "string"
  }
  ```

- **Error Responses:**
  - **Status Code:** 503 (Service Unavailable)
    - If LLM service is unavailable
  - **Status Code:** 500 (Internal Server Error)
    - For other server-side errors

## Models

### ContactBase

Base model for contact information.

```json
{
  "name": "string",
  "email": "string",
  "phone": "string"
}
```

### ContactResponse

Contact model returned in responses.

```json
{
  "id": 0,
  "name": "string",
  "email": "string",
  "phone": "string"
}
```

### CampaignRequest

Model for triggering a campaign.

```json
{
  "flood_location": "string",
  "target_contact_ids": [integer],
  "email_subject": "string"
}
```

## Example Requests

### Create a New Contact

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/contacts/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "Jane Smith",
  "email": "jane.smith@example.com",
  "phone": "555-555-5555"
}'
```

### Trigger a Campaign

```bash
{
  "status": "Campaign trigger processed",
  "flood_location": "Odissa",
  "ai_research_summary": "Odissa has been struck by severe flooding following torrential monsoon rains, leading to widespread displacement and damage to homes and infrastructure across the state.",
  "ai_message_template_used": "The people of Odissa are facing immense hardship due to the recent devastating floods. Your support can provide crucial aid, including food, clean water, and medical assistance, to those who have lost everything. Please donate now to help us reach those most in need. [Donation Link]",
  "ai_verification": "Given the widespread flooding and displacement reported, relief efforts are undoubtedly necessary.",
  "donation_link_included": "https://www.example-relief-fund.org/donate/flood-support",
  "contacts_target_ids": [
    1,
    2
  ],
  "contacts_found_in_db": 2,
  "emails_sent_successfully": 0,
  "emails_failed_or_skipped_config": 2,
  "contacts_skipped_no_email": 0,
  "ai_error_details": null
}
```

## Error Handling

The API follows standard HTTP status codes for error responses:

- **400**: Bad Request - Client-side error (e.g., validation failure)
- **404**: Not Found - Resource doesn't exist
- **500**: Internal Server Error - Server-side error
- **503**: Service Unavailable - External dependency unavailable

Error responses include a detail message:

```json
{
  "detail": "Error message describing the issue"
}
```
