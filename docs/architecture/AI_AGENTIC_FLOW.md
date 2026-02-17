# Agentic AI Architecture — Dynamic Retrieval Flow
**Status:** PROPOSED  
**Date:** 2026-02-17  

---

## 🚀 Concept: "Agentic Reasoning" over "Context Stuffing"

Instead of pre-loading the AI with a massive, stale context of all patient data (Reports + Profile + Appointments + Doctors), we shift to an **Agentic Workflow**.

The AI starts with a minimal **"Anchor Context"** and uses **Retrieval Tools** to fetch information dynamically *only when needed*. This mimics how a human receptionist works: they don't memorize every patient's file; they look up the specific details required for the task at hand.

### Key Benefits
1.  **Zero Stale Data**: Fetches real-time data from DB at the moment of request.
2.  **Scalable**: Context size stays small, regardless of how many reports/appointments a patient has.
3.  **Faster Initial Load**: No expensive pre-computation of context on every chat message.
4.  **Token Efficient**: We don't pay for tokens to describe irrelevent reports.

---

## 1. The "Anchor Context" (Always Present)
This is the *only* data injected into the system prompt on every request. It provides the essential "grounding" for the AI to function intelligibly.

```text
CURRENT_TIME: 2026-02-17T20:30:00+05:30 (Monday)
USER_ID: 12345
USER_ROLE: "patient"
LANGUAGE: "English" (or detected language)
```
*   **Why Time?** Essential to resolve "tomorrow", "next week", "morning".
*   **Why ID?** Essential for tool arguments.

---

## 2. The Retrieval Toolset
We expose lightweight "getter" tools that the AI can call to fetch context.

| Tool Name | Purpose | Returns |
| :--- | :--- | :--- |
| `get_my_profile()` | "What is my blood group?" | Name, Age, Gender, Blood Group, Allergies |
| `list_my_doctors()` | "Book with Dr. Dacchu" | List of {Name, ID, Specialization} |
| `list_my_appointments()` | "When is my next visit?" | List of upcoming appointments |
| `get_report_list()` | "Show my latest report" | List of recent report metadata (ID, Date, Name) | (Existing tool, refined) |

---

## 3. Agentic Workflow Examples

### Scenario A: "Book with my doctor tomorrow"
**Old Way (Context Stuffing):**
*   AI sees *nothing* about doctors/time.
*   **AI:** "Who is your doctor? What date is tomorrow?" (Fail)

**New Way (Agentic):**
1.  **User:** "Book with my doctor tomorrow."
2.  **AI (Context):** Sees `CURRENT_TIME: 2026-02-17`. Knows "tomorrow" = `2026-02-18`.
3.  **AI (Reasoning):** "I need to know who 'my doctor' is."
4.  **AI (Action):** Calls `list_my_doctors()`.
5.  **Tool Output:** `[{"name": "Dr. Dacchu", "id": "doc-123", "role": "Gynecologist"}]`
6.  **AI (Reasoning):** "User has only 1 doctor, Dr. Dacchu. I will proceed."
7.  **AI (Action):** Calls `create_appointment(doctor_id="doc-123", date="2026-02-18")`.
8.  **Tool Output:** `{"success": True, "appointment_id": "apt-999"}`
9.  **AI (Response):** "I've booked an appointment with Dr. Dacchu for tomorrow, Feb 18th."

### Scenario B: "Is Dr. Sharma free?"
1.  **User:** "Is Dr. Sharma free?"
2.  **AI (Reasoning):** "I need to find 'Dr. Sharma' in the user's list."
3.  **AI (Action):** Calls `list_my_doctors(search="Sharma")`.
4.  **Tool Output:** `[{"name": "Dr. Priya Sharma", "id": "doc-456"}]`
5.  **AI (Reasoning):** "Found Dr. Priya Sharma. Now I check slots."
6.  **AI (Action):** Calls `get_booked_slots(doctor_id="doc-456", date="2026-02-17")`.
7.  **Tool Output:** `{"booked": ["10:00", "14:00"], "available": ["11:00", ...]}`
8.  **AI (Response):** "Dr. Priya Sharma has openings at 11:00 AM today."

---

## 4. Addressing "Context Gaps" (from `AI_CONTEXT_GAPS.md`)

| Gap | Solution in Agentic Flow |
| :--- | :--- |
| **Unknown Date** | Solved by **Anchor Context** (System Prompt injection of `datetime.now()`). |
| **"My Doctor"** | Solved by **Retrieval Tool** (`list_my_doctors`). AI fetches key, then act. |
| **Ambiguous Name** | Solved by **Retrieval Tool**. If `list_my_doctors` returns 2 matches, AI asks user to clarify. |
| **Patient Profile** | Solved by `get_my_profile`. AI calls it if user asks "What is my blood type?". |
| **Stale Reports** | Solved by `get_report_list()`. AI fetches the *latest* list directly from DB. |

---

## 5. Implementation Roadmap

1.  **Update `generate_chat_response`**:
    *   Inject `CURRENT_TIME` into the System Prompt.
    *   Remove the "heavy" report context building code.
2.  **Enhance Tool Defs**:
    *   Ensure `list_my_doctors`, `list_my_appointments` are exposed to Gemini.
    *   Add `get_my_profile` tool (simple DB fetch).
3.  **Smarter System Prompt**:
    *   Explicit instruction: *"If you lack information (like doctor name, ID, or patient stats), DO NOT ASK THE USER yet. rigorous Check your available tools to find that information first."*

---
**Verdict:** This architecture is robust, scalable, and solves the "Cold Start" problem without the overhead of massive context windows. It empowers the AI to "think" before acting.
