# AI Tool Calling — Context Gaps & Improvement Plan
**Generated:** 2026-02-17  
**Status:** Analysis & Proposals

---

## Why Tool Calls Fail (Root Cause)

The AI prompt sent to Gemini currently contains **only report data** as context. It has **zero knowledge** of:

| Missing Context | Impact |
|---|---|
| Patient's assigned doctors (names, IDs) | Can't resolve "my doctor", "Dr. Dacchu" |
| Today's date / current time | Can't resolve "tomorrow", "next Monday" |
| Patient's existing appointments | Can't avoid double-booking or know "my next appointment" |
| Patient's profile (name, age, allergies) | Can't personalize responses |
| Detected language of input | Can't auto-reply in the same language |

**Current `_build_context()` output:**
```
=== Report: blood_test.pdf ===
Raw Text: (report text)
Extracted Data: {lab values...}
```

**What it SHOULD include:**
```
TODAY: 2026-02-17 (Monday), IST timezone
PATIENT: Rahul, Age 28, Blood Group O+, Allergies: None
ASSIGNED DOCTORS:
  - Dr. Dacchu (Gynecologist, ID: abc-123)
  - Dr. Priya Sharma (Endocrinologist, ID: def-456)
UPCOMING APPOINTMENTS:
  - Dr. Priya Sharma on 2026-02-20 at 10:30 AM (Follow-up)
REPORTS:
  === Report: blood_test.pdf ===
  ...
```

---

## 🔴 Failure Scenarios

### 1. **"Book with my doctor"** — No Doctor Context
**User says:** _"I am free tomorrow at 12:30. Can you book an appointment with my doctor?"_

**What happens:** Gemini has NO idea who the patient's doctors are. It responds with text like "I'd be happy to help! Could you tell me your doctor's name?" instead of calling the tool.

**Root cause:** `_build_context()` doesn't inject the patient's assigned doctor list.

**Fix:** Include assigned doctors in the context so Gemini can:
- Resolve "my doctor" (if only one doctor assigned)
- Suggest from a list (if multiple doctors assigned)
- Match partial names like "Dacchu" to the actual DB entry

---

### 2. **"Dr. Dacchu" vs DB entry "Dacchu"** — Name Mismatch
**User says:** _"Book a consultation with Dr. Dacchu"_

**What happens:** The `find_doctor_by_name_or_id()` function uses `ILIKE '%Dacchu%'` which WOULD match "Dacchu" in the DB. But Gemini might not even call the tool because it doesn't know if "Dr. Dacchu" exists.

**Root cause:** Without the doctor list in context, Gemini can't be confident enough to call the tool. Even if it does, "Dr. Dacchu" as a full name search would still work via ILIKE — but **Gemini might pass a different name variation** (e.g., `doctor_name_or_id: "Dr. Dacchu"` vs `"Dacchu"`).

**Fix:** With doctors injected into context, Gemini sees: `Dr. Dacchu (Gynecologist, ID: abc-123)` and passes the exact name.

---

### 3. **"Tomorrow at 12:30"** — No Date Reference
**User says:** _"Book tomorrow at 12:30"_

**What happens:** Gemini doesn't know today's date. It might:
- Guess a date (possibly wrong)
- Pass "tomorrow" as a string (which `safe_parse_date` can't parse)
- Not call the tool at all

**Root cause:** The system prompt has no reference to the current date/time.

**Fix:** Inject `TODAY: 2026-02-17 (Monday), IST timezone` into the context. Gemini can then correctly resolve "tomorrow" → "2026-02-18".

---

### 4. **"Cancel my next appointment"** — No Appointment Context
**User says:** _"Cancel my next appointment"_

**What happens:** Gemini doesn't know the patient's appointments. It can't call `cancel_appointment` because it doesn't have an appointment ID.

**Root cause:** Context doesn't include upcoming appointments.

**Fix:** Inject upcoming appointments (next 5) into context with IDs, so Gemini can resolve "my next appointment" to a specific ID.

---

### 5. **User speaks Kannada, gets English response**
**User says (in Kannada):** _"ನನ್ನ ವರದಿಗಳನ್ನು ತೋರಿಸಿ"_ (Show me my reports)

**What happens:** The transcription detects Kannada and translates to English for processing. The AI responds in English. The response is then translated back to the `language` parameter from the request — BUT the `language` param is set by the **frontend dropdown**, not auto-detected.

**Problems:**
- Text chat has NO language detection at all — always responds in English
- Voice chat relies on a frontend dropdown, not the detected language
- If user switches languages mid-conversation, the dropdown doesn't update

**Fix:** Auto-detect input language and reply in the same language, regardless of the channel (text or voice).

---

### 6. **"Is Dr. Sharma available at 2 PM?"** — Tool Not Called
**User says:** _"Is Dr. Sharma available at 2 PM tomorrow?"_

**What happens:** Gemini should call `get_booked_slots` to check, but without knowing today's date or the doctor list, it might just respond with generic text.

**Fix:** With date context + doctor list, Gemini confidently calls `get_booked_slots(doctor_name_or_id="Dr. Sharma", date="2026-02-18")`.

---

### 7. **"What's my health summary?"** — Incomplete Patient Data
**User says:** _"Give me a summary of my health"_

**What happens:** Gemini only sees report data. It can't mention the patient's allergies, medications, blood group, or medical history because that data isn't in the context.

**Fix:** Inject patient profile data (from the `Patient` table) into the context.

---

## 🟢 Proposed Improvements

### Improvement 1: Enriched Patient Context (CRITICAL)

Update `_build_context()` to inject:

```python
# 1. Current datetime
context_parts.append(f"TODAY: {datetime.now(IST).strftime('%Y-%m-%d %A')}, IST timezone")

# 2. Patient profile
patient = db.query(Patient).filter(Patient.user_id == patient_id).first()
context_parts.append(f"""
PATIENT PROFILE:
- Name: {patient.name}
- Age: {calculate_age(patient.date_of_birth)}
- Gender: {patient.gender}
- Blood Group: {patient.blood_group}
- Allergies: {patient.allergies or 'None'}
- Current Medications: {patient.current_medications or 'None'}
""")

# 3. Assigned doctors
doctors = get_doctors(patient_id, db)
doctor_lines = [f"  - {d.name} ({d.specialisation}, ID: {d.user_id})" for d in doctors.doctors]
context_parts.append(f"ASSIGNED DOCTORS:\n" + "\n".join(doctor_lines))

# 4. Upcoming appointments (next 5)
appointments = get_patient_appointments(db, patient_id, start_date=date.today())
apt_lines = [f"  - {a.doctor_name} on {a.start_time} ({a.type.value}), ID: {a.id}" for a in appointments[:5]]
context_parts.append(f"UPCOMING APPOINTMENTS:\n" + "\n".join(apt_lines))
```

**Impact:** Fixes scenarios #1, #2, #3, #4, #6, #7

---

### Improvement 2: Auto-Language Detection & Response (HIGH)

Currently: Voice uses a frontend dropdown. Text always responds in English.

**Proposed flow:**
1. Detect the input language from the user's message (Gemini can do this natively)
2. Store `detected_language` in the chat session
3. Process tools in English internally (tool calling, logging)
4. Translate the final response back to the detected language
5. If text chat, detect language from the message directly
6. If voice chat, use the transcription's `detected_language`

**Implementation:**
- Add `detected_language` field to the chat prompt
- Update `CHAT_RESPONSE_PROMPT` to include: "Respond in the same language the user is speaking. If user speaks Kannada, respond in Kannada. Tool calling parameters should always be in English."
- For voice: already have `transcription.detected_language` — use it instead of the dropdown
- For text chat: add a language detection step before generating the response

**Impact:** Fixes scenario #5 — seamless multilingual experience

---

### Improvement 3: Smarter System Prompt (HIGH)

Update `CHAT_RESPONSE_PROMPT` to:

```
You are a helpful medical AI assistant for a healthcare app used in India.

IMPORTANT RULES:
- TODAY is {today} ({day_name}), timezone: IST (Asia/Kolkata)
- When the user says "tomorrow", calculate {today + 1 day}
- When referring to a doctor, use the exact name from ASSIGNED DOCTORS
- If the user says "my doctor" and has only ONE assigned doctor, use that doctor
- If "my doctor" but MULTIPLE doctors, ask which one
- If the user says "cancel my next appointment", use the first UPCOMING APPOINTMENT ID
- RESPOND IN THE SAME LANGUAGE THE USER SPEAKS
- Tool parameters (dates, names, IDs) should always be in English
- Medical disclaimers should always be included
```

---

### Improvement 4: Tool Call Feedback Loop (MEDIUM)

Currently: If Gemini doesn't call a tool, we just return the text response. The user might have intended a tool action.

**Proposed improvement:**
- After getting a text response, check if the user's message matches tool intent patterns:
  - "book", "schedule", "appointment" → should have called `create_appointment`
  - "cancel" → should have called `cancel_appointment`
  - "reports", "results", "lab" → should have called `get_latest_reports`
- If mismatch detected, retry with a stronger prompt hint

---

### Improvement 5: Conversation-Level Language Memory (LOW)

- Store `preferred_language` per chat session in MongoDB
- First message sets the language, subsequent messages inherit it
- User can switch language mid-conversation and it updates
- Eliminates need for the frontend language dropdown for voice

---

## 📊 Priority Summary

| # | Improvement | Priority | Scenarios Fixed |
|---|---|---|---|
| 1 | Enriched patient context | 🔴 CRITICAL | #1, #2, #3, #4, #6, #7 |
| 2 | Auto-language detection | 🟡 HIGH | #5 |
| 3 | Smarter system prompt | 🟡 HIGH | #1, #3, #4 |
| 4 | Tool call feedback loop | 🟠 MEDIUM | All (fallback) |
| 5 | Language memory per chat | 🟢 LOW | #5 |

---

## 🛠️ Implementation Order

1. **Enriched context** → Fixes 6 out of 7 scenarios in one shot
2. **Updated system prompt** → Makes Gemini smarter with date/doctor resolution
3. **Auto-language detection** → Seamless Kannada/Hindi support
4. **Tool fallback** → Safety net for edge cases
5. **Language memory** → Polish for multilingual conversation flow

---

**End of Analysis**
