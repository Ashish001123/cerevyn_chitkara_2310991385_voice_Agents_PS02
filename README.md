# PS02 Voice Appointment Booking Agent

> **Cerevyn Solutions – Round 1 Technical Assessment**  
> **Candidate:** Ashish Khatri  
> **Roll Number:** 2310991385  
> **Problem ID:** PS02 (Voice Agents track)  
> **Branch:** Computer Science Engineering, Chitkara University  
> **Repository:** `Cerevyn-Chitkara-2310991385-PS02`


A voice agent that books and cancels appointments with three fictional service providers. It
collects the service, the customer's name and a preferred date and time through a short spoken
conversation. It reads availability from SQLite, offers real alternatives when a slot is taken,
asks for an explicit yes before any change, returns a booking ID, and cannot double-book a slot.

```
 audio ──► STT ──► dialogue manager ──► SQLite (slots, bookings, audit, sessions) ──► reply text ──► TTS ──► audio
          (faster-whisper |          (slot filling + explicit                                   (macOS say | pyttsx3 |
           Azure AI Speech)           confirmation state machine)                                Azure AI Speech)
```

## Requirement traceability

| Requirement | Where it is met |
|---|---|
| Three service providers, ≥12 slots, explicit dates, Asia/Kolkata | [data/seed.json](data/seed.json): 3 providers, 15 slots on 20–21 Oct 2026, every timestamp `+05:30` |
| Sample audio requests | [samples/requests.json](samples/requests.json) and 23 WAV files in [samples/audio/](samples/audio/) |
| Sample booking records | 2 seeded bookings in `data/seed.json`, plus the post-demo records in [samples/booking_records.json](samples/booking_records.json) |
| Actual speech-to-text and text-to-speech | [app/speech.py](app/speech.py): faster-whisper (local) or Azure AI Speech STT; macOS native synthesizer (fallback `say`), pyttsx3 or Azure Neural TTS |
| Collect service, name, date and time in a short conversation | [app/dialogue.py](app/dialogue.py) slot filling, with [app/nlu.py](app/nlu.py) extracting several fields from one utterance |
| Read availability from the DB; offer alternatives; never invent a slot | `Repository.find_slot`, `available_slots` and `alternatives` in [app/repository.py](app/repository.py). Alternatives are database rows only, stored as slot IDs in the dialogue state and re-read before use |
| Explicit confirmation before booking | `awaiting_booking_confirmation` step. Only an explicit yes reserves; an ambiguous reply re-asks and a no books nothing |
| Return a booking ID | `BKnnnnn`, read back to the caller and spelled digit by digit in speech |
| Prevent two requests reserving the same slot | `BEGIN IMMEDIATE` plus a conditional `UPDATE … WHERE status='available'`, plus a partial unique index on `bookings(slot_id) WHERE status='confirmed'` |
| Cancellation using booking ID and confirmation | `awaiting_cancel_confirmation` step, then `Repository.cancel_booking` frees the slot |
| Preserve dialogue state | `sessions.state` (JSON) is reloaded and saved every turn; every turn is stored in `dialogue_turns` with audio path and state snapshot |
| Audit record of booking changes | `booking_audit`: `SEEDED`, `BOOKED`, `CANCELLED`, `BOOK_REJECTED_SLOT_TAKEN`, with before/after JSON, written in the same transaction as the change |
| Demonstrate success, unavailable, missing info, cancellation, double booking | [scripts/run_demo.py](scripts/run_demo.py) produces [demo_output/report.md](demo_output/report.md) |
| Python, FastAPI, SQLite, STT, TTS | [app/main.py](app/main.py) and the modules above |
| Azure hosting design for API and speech | [docs/azure_hosting.md](docs/azure_hosting.md), [infra/main.bicep](infra/main.bicep), [Dockerfile](Dockerfile) |

## Quick start (macOS, Python 3.12+)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/init_db.py --reset            # create data/appointments.db from data/seed.json
python scripts/generate_sample_audio.py      # (re)create samples/audio/*.wav (already included)
python scripts/run_demo.py                   # full voice demo + consistency checks
pytest -q                                    # 184 tests
python scripts/eval_noise.py                 # noise / background-voice evaluation

# live call: open http://localhost:8000, click Start call and just talk (you can interrupt)
APP_NOW=2026-10-11T09:00:00+05:30 uvicorn app.main:create_app --factory --port 8000
```

On first use, faster-whisper downloads the `small.en` model (about 460 MB) from Hugging Face. Set
`WHISPER_MODEL=base.en` for a smaller model.

`APP_NOW` fixes the clock at 11 Oct 2026 so the seeded 20–21 October 2026 slots stay in the future
whenever you run this. Leave it unset to use the real time.

### Using Azure AI Speech instead of local engines

```bash
export AZURE_SPEECH_KEY=<key> AZURE_SPEECH_REGION=centralindia   # SPEECH_PROVIDER=auto picks Azure
```

STT uses the short-audio REST API with locale `en-IN`, and TTS uses `en-IN-NeerjaNeural`. On Linux or
Windows without Azure, install `pyttsx3` for local TTS.

## Demo results

`python scripts/run_demo.py` uploads each sample WAV to `POST /sessions/{id}/voice`, so every turn
goes through real STT, the dialogue manager, SQLite and real TTS. The clock is fixed at
2026-10-11 09:00 IST.

| # | Scenario | What happens |
|---|---|---|
| 1 | Successful booking | "Haircut on October 20th at 10 AM, my name is Priya Sharma" → agent reads the slot back → "Yes, please" → booking ID |
| 2 | Unavailable slot | Dental checkup 20 Oct 10:00 is already booked (seed) → agent offers the 3 closest real slots → "The 11 AM one" → confirm → booked |
| 3 | Missing information | "I'd like to book an appointment" → agent asks for service, name, date, then time (listing open times from the DB). "Hmm, let me think" is **not** taken as consent → "Yes" → booked |
| 4 | Cancellation | "Cancel my booking" → asks for ID → "B K 2 4 0 1 7" → reads booking back → "Yes, cancel it" → cancelled, slot freed |
| 5 | Two attempts on the same slot | Sneha and Vikram both get to the confirmation prompt for physiotherapy 21 Oct 10:00. Sneha says yes first and gets it. Vikram's yes is rejected by the DB, audited, and he is offered alternatives and books another slot |
| 6 | Declined confirmation | "No, don't book it" → nothing booked |

Also included: a stress test where 20 threads reserve the same slot at once, giving exactly 1 success
and 19 audited rejections.

The run ends with 13 automated checks, all passing: database state per scenario, no slot with two
confirmed bookings, booked slots matching confirmed bookings, and every `BOOKED`/`CANCELLED` audit
row preceded by a yes/no prompt for that exact slot or booking. Outputs:

- `demo_output/report.md`: a transcript per turn (STT text, agent reply, dialogue step), booking records, audit log
- `demo_output/audio/*_reply.wav`: the agent's spoken replies
- `demo_output/report.json`, `booking_records.json`, `audit_log.json`

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions` | Start a call; returns `session_id`, greeting text and audio URL |
| `POST` | `/sessions/{id}/voice` | Multipart `audio` (wav/webm/ogg/mp3/m4a/flac). Returns `transcript`, `reply_text`, `reply_audio_url`, `state` |
| `POST` | `/sessions/{id}/text` | Same pipeline without STT: `{"text": "...", "speak": true}` |
| `GET` | `/sessions/{id}` | Current dialogue state and the full turn history |
| `GET` | `/slots?service=&date=` | Available slots, from the DB |
| `GET` | `/services` | Providers and services |
| `GET` | `/bookings`, `/bookings/{id}` | Booking records |
| `GET` | `/audit` | Audit trail of booking changes |
| `GET` | `/health` | Active STT/TTS engines |
| `WS` | `/ws/calls[?session_id=]` | Live full-duplex call: stream 16 kHz PCM16 mic audio in; receive `user_speech_start`, `barge_in`, `transcript`, `agent_text`, `agent_audio` (one WAV per sentence) and `timings` events |
| `GET` | `/` | Browser UI: live call with interruption, transcript with per-turn latency, live state and slot table |

## Design notes

**Slot consistency.** Checking availability never holds a slot; only the final, confirmed
reservation does. `reserve_slot` takes SQLite's write lock (`BEGIN IMMEDIATE`) and flips the slot
with `UPDATE … WHERE status='available'`. A row count other than 1 means someone else won, which is
recorded as `BOOK_REJECTED_SLOT_TAKEN`. The partial unique index is a second guard at the schema
level. Cancelling frees the slot in the same transaction as the audit row.

**Confirmation handling.** Changes happen only from the two confirmation steps, and only on an
explicit yes. Negation wins over affirmation ("no, don't book it"). Anything unclear re-asks without
changing anything. If the caller names a different date or time at the confirmation step, the agent
re-checks availability instead of treating it as yes. An offered alternative is re-read from the DB
when chosen, in case it was taken in the meantime.

**Dialogue state.** One JSON document per session holds `step`, `awaiting` (what was just asked,
which guides parsing of short answers like "2 PM" or "Karan Mehta"), the four booking fields, the
pending slot, and the offered alternatives. It is saved every turn, so a restarted server continues
the same conversation (`test_dialogue_state_survives_restart`).

**Language understanding** is rule-based ([app/nlu.py](app/nlu.py)), so it is deterministic and
testable. It handles "October 20th", "the 20th of October", `2026-10-20`, `20/10`, "tomorrow",
"next Tuesday", "10 a.m.", "half past 11", "2 o'clock", spelled-out numbers, STT near-misses for
service names, and booking IDs said as "BK24017", "B K 2 4 0 1 7" or "booking number 24,017".

## Call quality: real-time behaviour, noise and dates

**Live call pipeline** ([app/call.py](app/call.py), [app/turns.py](app/turns.py), `/ws/calls`):

```
mic ─► AudioWorklet (16 kHz PCM16, 32 ms frames) ─► WebSocket ─► Silero VAD per frame ─► turn detector
      ├─ 250 ms pause → speculative STT starts      ├─ 500 ms pause → end of turn → reuse speculative transcript
      └─ caller talks while agent speaks → barge_in: playback stops, remaining sentences are not synthesized
reply ─► split into sentences ─► TTS sentence 1 sent immediately, the rest follow while it plays
```

Measured on an Apple M5, streaming sample audio in real time, from the moment the caller stops talking
until the first reply audio arrives: **0.84 s** for a short answer ("Yes, please") and **1.17 s** for a
5.5-second request. The old upload-per-turn flow took about 2 s or more.

**Background voices and noise** ([app/speech.py](app/speech.py)): Silero VAD finds speech segments. A
segment is kept only if it is above an absolute level (about −40 dBFS) and within about 10 dB of the
caller's loudest segment. Whisper output is then filtered for low-confidence non-speech, looping
repetition, prompt echoes and known noise hallucinations ("Thank you.", "Thanks for watching").
While the agent is speaking, interrupting needs stronger and longer speech, so its own echo doesn't
cut it off. Results from `scripts/eval_noise.py` (in `docs/eval/`):

| Condition | Before | After |
|---|---|---|
| Background-only clips (distant chatter or fan) that produced a transcript | **5 / 10** (e.g. "I want to cancel my booking", "Yes, we can see it") | **0 / 10** |
| Field accuracy (service/date/time/yes-no/ID): clean, babble 20/10 dB, fan 10/5 dB | 100% | 100% |
| Field accuracy, three-voice babble at 5 dB | 100% | 94% (the failing clip yields no field, so the agent asks again) |

**Dates and times** ([app/temporal.py](app/temporal.py)) are a grammar that takes into account what
the agent just asked. It handles "the 20th at 10", a bare "20" after "which day?", "10 30", "10.30",
"1030", "two thirty", "quarter to three", "1400 hours" and "fourteen hundred". A four-digit number
is a year only if it is this year or next, so "20th October 1400" is 2 PM, not the year 1400. A bare
number is read as a date or time only when the agent asked for one. There are 54 tests in
[tests/test_temporal.py](tests/test_temporal.py).

**Replies** are short (7–32 words). The year and "IST" are spoken once, and every booking or
cancellation still reads back the exact slot and waits for a yes. Hinglish answers are understood:
"haan", "ji haan", "theek hai", "nahi", "mat karo".

Per-stage speed: STT is 0.65–0.9 s (Whisper `small.en`, greedy decoding, all cores, warmed up at
startup), dialogue about 5 ms, and TTS about 0.1 s per sentence (resident macOS synthesizer). Each
`/voice` response includes `timings_ms`, and each live-call reply sends a `timings` event.

## Project layout

```
app/            FastAPI app, dialogue manager, NLU, repository, speech engines, web UI
data/seed.json  providers, slots, sample bookings (Asia/Kolkata)
samples/        spoken request manifest, WAV files, booking records
scripts/        init_db.py, generate_sample_audio.py, run_demo.py, eval_noise.py
tests/          NLU, dates/times, repository/concurrency, dialogue, replies, speech guards, turn detection, live call, API
docs/           Azure hosting design, noise evaluation results, TDD evidence
infra/          Bicep for the core Azure resources
```

## Limitations

- Background voices are separated by loudness, not by recognising the caller's voice. A second
  person speaking as close to the mic as the caller will be transcribed. Very loud babble (5 dB)
  can still make the agent ask the caller to repeat.
- Long requests take about 1.2 s before the reply starts. That's limited by Whisper `small.en` on
  the CPU; Azure streaming STT or a larger GPU-backed model would cut it further. Live-call
  latency was measured with sample audio streamed in real time, not with a human over a network.
- The code runs on SQLite, which is right for a local single-instance deployment. The Azure design
  moves storage to Azure SQL for multiple replicas. That swap is described in the docs but not
  implemented.
- English only. Customer names are taken as transcribed, so STT may spell them differently (for
  example, "Priya Sarma" in the demo).
- The Azure STT/TTS classes follow the documented REST APIs but were not exercised here, because no
  Azure key was available. The local engines were used for every demo run. The Bicep template has not
  been compiled (no Azure CLI in this environment).

## Author Contributions & AI Assistance

- **Candidate Name:** Ashish Khatri (Roll No: 2310991385, Chitkara University)
- **Problem Statement:** PS02 – Voice Appointment Booking Agent
- **Original Contributions:**
  - Architecture and implementation of the conversational slot-filling dialogue manager state machine (`app/dialogue.py`).
  - Strict atomic reservation handling, optimistic locking, and audit log tracking on SQLite (`app/repository.py`, `app/db.py`).
  - Rule-based NLU & temporal date/time parsing handling colloquial and Hinglish expressions (`app/nlu.py`, `app/temporal.py`).
  - Full-duplex WebSocket live call streaming pipeline with Silero VAD turn detection, barge-in support, and AudioWorklet integration (`app/call.py`, `app/turns.py`, `app/static/index.html`).
  - Real-time web UI showing live dialogue state, available slots, and confirmed bookings table with automatic turn refresh.
  - Comprehensive test suite (184+ automated tests covering booking, cancellation, alternatives, concurrency, date parsing, and speech guards) and noise evaluation script.
  - Cloud hosting architecture documentation (`docs/azure-plan.md`, `docs/azure_hosting.md`) and Azure Bicep infrastructure specification (`infra/main.bicep`).
- **Reused Libraries & Frameworks:**
  - FastAPI & Uvicorn for asynchronous REST and WebSocket API.
  - Faster-Whisper (CTranslate2) & Silero VAD for on-device speech-to-text and speech segment detection.
  - macOS Native NSSpeechSynthesizer / `say` and pyttsx3 fallback for text-to-speech.
  - Pytest & Coverage for automated testing.
- **AI Assistance:**
  - Antigravity AI coding assistant used for rapid prototyping, drafting Azure architecture documentation diagrams, test case generation, and CI workflow setup.

