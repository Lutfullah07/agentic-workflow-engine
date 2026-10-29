# Agentic Workflow Engine

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b)
![Gemini](https://img.shields.io/badge/LLM-Gemini%20API-4285f4)

Describe an automation in plain English and get back a workflow plan, a list of triggers, or a ready-to-use API payload.

I built this to get hands-on with LLM APIs and workflow tools like n8n, Make and Zapier. The examples lean towards eCommerce customer support: order status, ticket triage, refunds.

![App screenshot](screenshots/home.png)
![Generated workflow](screenshots/result.png)


## Try it

Run it locally, paste a Gemini API key in the sidebar, and click one of these starters:

| Starter | What you get |
|---|---|
| Order-status bot | A workflow for answering "where is my order?" on WhatsApp |
| Ticket triage | A pipeline that scores support tickets and escalates urgent ones |
| Refund payload | A webhook JSON payload for a refund event |

Or type your own, for example:

> What is the difference between n8n, Make and Zapier, and which one suits customer support automation?

## How it works

```
Your prompt
    |
    v
Mode picks a system prompt (Direct / Pipeline / Payload)
    |
    v
App asks Gemini which models your key can use   (cached for an hour)
    |
    v
Best available model is picked from a preference list
    |
    v
generateContent call  --- fails (404 / 400 / 5xx)? ---> try the next model
    |
    v
Reply shown in the chat, with the model name under it
```

1. The sidebar mode decides the system prompt. For example, Workflow Pipeline asks for trigger, steps, data mapping, error handling and scaling notes.
2. The app calls the `models` endpoint with your key and keeps only models that support `generateContent`.
3. It picks the first match from a short preference list, then falls back to any other Flash model if none match.
4. The last 12 messages are sent with the system prompt, so follow-up questions have context.
5. If a model call returns 404, 400 or a server error, the app tries the next model instead of crashing. Rate limits (429) and blocked responses show a clear error message.
## Modes

| Mode | Best for | Output |
|---|---|---|
| Direct Prompt | Quick questions | Normal answer |
| Workflow Pipeline | Designing an automation | Trigger, steps, data mapping, error handling, scaling |
| API Payload | Webhook testing | JSON only |

## Run it

```bash
pip install -r requirements.txt
streamlit run main.py
```

Get a free Gemini API key at https://aistudio.google.com/apikey and paste it into the sidebar.
The key stays in your browser session only. It is not saved and not in the code.

<details>
<summary>Why does it pick the model automatically?</summary>

My first version hard-coded `gemini-pro` and kept failing with a 404, because Google retires old models and the names stop working.

Now the app asks the API which models your key can use, picks the best one, and falls back to the next one if a call fails. The model used is shown under every reply.
</details>

<details>
<summary>Project layout</summary>

```
main.py            the whole app (UI + Gemini calls)
requirements.txt   dependencies
README.md          this file
```
</details>

## Built with

Python, Streamlit, and the Gemini API (called with `requests`).

## Next

- [ ] Send generated payloads to a real n8n or Make webhook
- [ ] Add a small knowledge base so answers come from real FAQ data
- [ ] Write tests for the model fallback