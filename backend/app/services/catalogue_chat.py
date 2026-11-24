"""Local catalogue retrieval, constrained model interpretation and temporary chat state."""
import json
from collections import Counter, OrderedDict
from datetime import date
from functools import lru_cache
from math import log, sqrt
import os
import re
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

import httpx
from pydantic import BaseModel, Field
from typing import Literal

from .chat_translation import translate
from .eligibility_engine import evaluate_scheme
from ..models.domain import RuleReviewState, RuleStatus

MODEL = os.getenv("SCHEME_CHAT_MODEL", "qwen2.5-coder:7b")
EMBED = os.getenv("SCHEME_EMBED_MODEL", "nomic-embed-text")
BASE = os.getenv("SCHEME_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
STATES = ("Punjab", "Haryana", "Himachal Pradesh", "Chandigarh")
FIELDS = ("location.state", "education.student_status", "agriculture.farmer_status")
TOPICS = {"benefit": "summary", "documents": "documents_required", "apply": "application_steps", "eligibility": "eligibility_text"}
STOP = set("a an the to in of my i am for what do need is show me schemes scheme documents apply help from want and can with".split())
sessions = OrderedDict()
lock = Lock()


class Intent(BaseModel):
    query: str = Field(max_length=400)
    topic: Literal["benefit", "documents", "apply", "eligibility"]
    language: Literal["en", "hi", "pa"]
    profile_update_only: bool = False
    state: str = ""
    student: Literal["yes", "no", ""] = ""
    farmer: Literal["yes", "no", ""] = ""
    marital_status: Literal["single", "married", "widowed", "divorced", ""] = ""
    # Only an explicitly annual household amount belongs in this field.
    annual_household_income: str = Field(default="", max_length=14)
    date_of_birth: str = Field(default="", max_length=10)


def local_model(path, payload, timeout=45):
    response = httpx.post(f"{BASE}/api/{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def interpret(message, previous):
    instructions = ("Extract search intent into English keywords. Preserve the requested scheme name. "
                    "For follow-ups use the previous search. Choose the language of the latest message. "
                    "Set profile_update_only when the message just gives or corrects a personal fact without asking a new scheme question. Only extract personal facts explicitly asserted by the speaker in the latest message. "
                    "For hypothetical people or schemes mentioning a state leave personal facts empty. "
                    "Use English state names. Return date_of_birth only for an explicit complete birth date. Never infer it from age. Return annual_household_income only if explicitly stated as annual family or household income in INR. Leave unspecified facts empty.")
    payload = {"model": MODEL, "stream": False, "format": Intent.model_json_schema(),
               "options": {"temperature": 0, "num_predict": 180},
               "messages": [{"role": "system", "content": instructions},
                            {"role": "user", "content": json.dumps({"previous_search": previous, "message": message}, ensure_ascii=False)}]}
    try:
        return Intent.model_validate_json(local_model("chat", payload)["message"]["content"]), True
    except (ValueError, KeyError, httpx.HTTPError):
        topic = next((key for key in TOPICS if key in message.lower()), "benefit")
        return Intent(query=message[:400], topic=topic, language="en"), False


@lru_cache(maxsize=2)
def vectors(docs):
    items = []
    for start in range(0, len(docs), 16):
        items.extend(local_model("embed", {"model": EMBED, "input": ["search_document: " + d for d in docs[start:start+16]]})["embeddings"])
    return items


def tokens(value):
    return {word.rstrip("s") for word in re.findall(r"\w+", value.lower()) if word not in STOP}


# Common names appearing in public queries and different scripts.
ALIASES = {
    "IN-PMKISAN-UMANG": ("pm kisan", "pm-kisan", "पीएम किसान", "पीएम-किसान", "पीएमकिसान", "पी एम किसान", "ਪੀਐਮ ਕਿਸਾਨ", "ਪੀਐਮ-ਕਿਸਾਨ"),
    "HR-OASA-002": ("old age samman", "वृद्धावस्था पेंशन", "बुढ़ापा पेंशन", "ਬੁਢਾਪਾ ਪੈਨਸ਼ਨ"),
}
REGION_TERMS = {
    "Haryana": ("haryana", "हरियाणा", "ਹਰਿਆਣਾ"),
    "Punjab": ("punjab", "पंजाब", "ਪੰਜਾਬ"),
    "Chandigarh": ("chandigarh", "चंडीगढ़", "ਚੰਡੀਗੜ੍ਹ"),
    "Himachal Pradesh": ("himachal", "हिमाचल", "ਹਿਮਾਚਲ"),
}


def retrieve(records, query, state="", original=""):
    docs = tuple(f"{s.name} {s.jurisdiction} {s.category} {s.summary or ''}" for s in records)
    terms = tokens(query)
    sets = [tokens(d) for d in docs]
    counts = Counter(term for words in sets for term in words)
    scores = [sum(log(1 + len(docs) / counts[t]) for t in terms & words) for words in sets]
    mode = "keyword"
    try:
        embedded = vectors(docs)
        q = local_model("embed", {"model": EMBED, "input": "search_query: " + query})["embeddings"][0]
        for i, vector in enumerate(embedded):
            cosine = sum(a*b for a,b in zip(q, vector)) / max(1e-9, sqrt(sum(a*a for a in q)*sum(b*b for b in vector)))
            scores[i] += max(0, cosine - 0.45) * 10
        mode = "hybrid"
    except (ValueError, KeyError, IndexError, httpx.HTTPError):
        pass
    phrase = (original + " " + query).casefold()
    requested = next((region for region, terms in REGION_TERMS.items() if any(t in phrase for t in terms)), state)
    for i, scheme in enumerate(records):
        alias_hit = any(term in phrase for term in ALIASES.get(scheme.scheme_id, ()))
        if scheme.scheme_id == "HR-OASA-002" and requested != "Haryana":
            alias_hit = False
        if alias_hit or scheme.name.casefold() in phrase or scheme.scheme_id.casefold() in phrase:
            scores[i] += 40
        if requested and requested.casefold() in scheme.jurisdiction.casefold():
            scores[i] += 1 if scores[i] > 0.7 else 0
    candidates = [
        i for i, record in enumerate(records)
        if not requested or requested.casefold() in record.jurisdiction.casefold()
        or re.match(r"^(?:(?:urban|rural) )?india\b", record.jurisdiction.strip(), re.I)
    ]
    ranked = sorted(candidates, key=lambda i: -scores[i])
    floor = max(0.7, scores[ranked[0]] * 0.55) if ranked else 0.7
    return [records[i] for i in ranked if scores[i] >= floor][:3], mode


def session_for(token):
    with lock:
        now = monotonic()
        while sessions and (now - next(iter(sessions.values()))["seen"] > 1800 or (not token and len(sessions) >= 256)):
            sessions.popitem(last=False)
        if token and token not in sessions:
            raise KeyError("Conversation expired")
        if not token:
            token = token_urlsafe(32)
            sessions[token] = {"query": "", "language": "en", "focus": "", "facts": {}, "pending": {}, "history": [], "seen": now, "lock": Lock()}
        state = sessions[token]
        state["seen"] = now
        sessions.move_to_end(token)
        return token, state


PROMPTS = {
    "en": ("Which state or Union Territory do you live in?", "Which scheme would you like to explore?", "Catalogue references", "Confirm each profile detail below."),
    "hi": ("आप किस राज्य या केंद्र शासित प्रदेश में रहते हैं?", "आप किस योजना के बारे में जानना चाहते हैं?", "योजना के स्रोत", "नीचे अपनी जानकारी की पुष्टि करें।"),
    "pa": ("ਤੁਸੀਂ ਕਿਸ ਰਾਜ ਜਾਂ ਕੇਂਦਰ ਸ਼ਾਸਿਤ ਪ੍ਰਦੇਸ਼ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?", "ਤੁਸੀਂ ਕਿਸ ਯੋਜਨਾ ਬਾਰੇ ਜਾਣਨਾ ਚਾਹੁੰਦੇ ਹੋ?", "ਯੋਜਨਾ ਦੇ ਸਰੋਤ", "ਹੇਠਾਂ ਆਪਣੇ ਵੇਰਵਿਆਂ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ।"),
}


def eligibility_hint(scheme, confirmed):
    profile = {}
    for path, value in confirmed.items():
        section, field = path.split(".", 1)
        if path == "household.family_income":
            field = "household_annual_income"
        profile.setdefault(section, {})[field] = value
    category, review, _, assessment, _ = evaluate_scheme(scheme, profile)
    if review != RuleReviewState.REVIEWED:
        return None
    unknown = next((item.description for item in assessment.conditions if item.status == RuleStatus.UNKNOWN), None)
    return {"category": category.value, "next_condition": unknown}


def answer(body, records):
    token, state = session_for(body.session)
    with state["lock"]:
        if body.decision:
            field = body.field
            if field not in state["pending"] or body.value != state["pending"][field]:
                raise ValueError("This detail is no longer pending.")
            value = state["pending"].pop(field)
            if body.decision == "confirm":
                old = state["facts"].get(field)
                if old and old != value:
                    state["history"].append({"field": field, "previous": old, "current": value})
                    state["history"] = state["history"][-24:]
                state["facts"][field] = value
            notices = {"en": ("Profile detail updated.", "Suggestion dismissed."), "hi": ("जानकारी की पुष्टि हो गई।", "सुझाव हटा दिया गया।"), "pa": ("ਵੇਰਵੇ ਦੀ ਪੁਸ਼ਟੀ ਹੋ ਗਈ ਹੈ।", "ਸੁਝਾਅ ਹਟਾ ਦਿੱਤਾ ਗਿਆ ਹੈ।")}
            result = {"text": notices[state["language"]][0 if body.decision == "confirm" else 1], "references": []}
        else:
            intent, modeled = interpret(body.message, state["query"])
            # Preserve clear first-person assertions when the model concentrates on the search terms.
            explicit_state = re.search(r"\b(?:i (?:live in|am from)|i am (?:a |an )?[^.?!]{1,32} from) (punjab|haryana|himachal pradesh|chandigarh)\b", body.message, re.I)
            state_value = explicit_state.group(1).title() if explicit_state else intent.state
            farmer = "yes" if re.search(r"\bi am (?:a |an )?farmer\b", body.message, re.I) else intent.farmer
            student = "yes" if re.search(r"\bi am (?:a |an )?student\b", body.message, re.I) else intent.student
            suggestions = dict(zip(FIELDS, (state_value if state_value in STATES else "", student, farmer)))
            suggestions["personal.marital_status"] = intent.marital_status
            income = intent.annual_household_income.replace(",", "")
            if re.fullmatch(r"\d{1,12}", income):
                suggestions["household.family_income"] = income
            try:
                dob = date.fromisoformat(intent.date_of_birth)
                if 1900 <= dob.year and dob <= date.today():
                    suggestions["personal.date_of_birth"] = dob.isoformat()
            except ValueError:
                pass
            for key, val in suggestions.items():
                if val and val == state["facts"].get(key):
                    state["pending"].pop(key, None)
                elif val:
                    state["pending"][key] = val
            if re.search(r"documents?|paperwork|दस्तावे[जज़]|काग[जज़]|ਦਸਤਾਵੇ[ਜਜ਼]|ਕਾਗਜ਼", body.message, re.I):
                intent.topic = "documents"
            query = intent.query.strip() or body.message
            if not tokens(query) and state["query"]:
                query = state["query"]
            followup = body.message.casefold().strip(" ?.।!")
            generic = re.fullmatch(r"(?:which documents(?: do i need)?|what documents(?: do i need)?|how (?:do i|to) apply|where (?:do i|to) apply|कौन से दस्तावेज़?(?: चाहिए)?|क्या दस्तावेज़? चाहिए|आवेदन कैसे करूँ|कैसे आवेदन करूँ|ਕਿਹੜੇ ਦਸਤਾਵੇਜ਼(?: ਚਾਹੀਦੇ ਹਨ)?|ਅਰਜ਼ੀ ਕਿਵੇਂ ਦੇਵਾਂ)", followup)
            focused = next((r for r in records if r.scheme_id == state["focus"]), None)
            state_only = re.fullmatch(r"(?:actually[, ]+)?i (?:live in|am from) (?:punjab|haryana|himachal pradesh|chandigarh)", followup)
            personal_turn = bool(state_only or (intent.profile_update_only and any(suggestions.values())))
            if focused and personal_turn:
                matches, mode = [], "profile_update"
            elif generic and focused:
                matches, mode = [focused], "followup"
                if re.search("apply|आवेदन|ਅਰਜ਼ੀ", followup):
                    intent.topic = "apply"
            else:
                matches, mode = retrieve(records, query, state["facts"].get("location.state", ""), body.message)
            if mode != "profile_update":
                state["query"] = matches[0].name if matches else query
                state["focus"] = matches[0].scheme_id if matches else ""
            refs = [{"id": s.scheme_id, "name": s.name, "excerpt": getattr(s, TOPICS[intent.topic]) or s.summary,
                     "source": s.source_url, "checked": s.last_checked,
                     "assessment": eligibility_hint(s, state["facts"]) if state["facts"] else None} for s in matches]
            if any("\u0a00" <= ch <= "\u0a7f" for ch in body.message):
                intent.language = "pa"
            elif any("\u0900" <= ch <= "\u097f" for ch in body.message):
                intent.language = "hi"
            if intent.topic == "documents":
                for item, scheme in zip(refs, matches):
                    if scheme.conditional_documents:
                        item["conditional"] = scheme.conditional_documents
            if generic and not re.search(r"[\u0900-\u097f\u0a00-\u0a7f]", body.message):
                intent.language = state["language"]
            state["language"] = intent.language
            if intent.language != "en":
                for ref in refs:
                    for field in ("excerpt", "conditional"):
                        if ref.get(field):
                            try:
                                ref[field + "_translation"] = translate(ref[field], intent.language, MODEL, local_model)
                            except (ValueError, KeyError, httpx.HTTPError):
                                ref["translation_incomplete"] = True
            prompts = PROMPTS[intent.language]
            prompt = prompts[3] if state["pending"] else prompts[0] if "location.state" not in state["facts"] else prompts[1]
            lead = prompts[2] if refs else ""
            if refs and not state["pending"] and intent.language == "en" and state["facts"]:
                assessment = refs[0].get("assessment") or {}
                condition = assessment.get("next_condition")
                if condition:
                    prompt = "The next eligibility detail to confirm is whether this condition applies to you: " + condition
            # The model interprets the request; last-checked policy wording is rendered verbatim.
            # This also retains exceptions, income periods and application qualifications.
            if refs:
                titles = {
                    "en": {"documents": "Documents listed for", "apply": "Application steps for", "eligibility": "Eligibility criteria for", "benefit": "Benefit recorded for"},
                    "hi": {"documents": "सूचीबद्ध दस्तावेज़", "apply": "आवेदन के चरण", "eligibility": "पात्रता की शर्तें", "benefit": "योजना का लाभ"},
                    "pa": {"documents": "ਲੋੜੀਂਦੇ ਦਸਤਾਵੇਜ਼", "apply": "ਅਰਜ਼ੀ ਦੇ ਕਦਮ", "eligibility": "ਯੋਗਤਾ ਦੀਆਂ ਸ਼ਰਤਾਂ", "benefit": "ਯੋਜਨਾ ਦਾ ਲਾਭ"},
                }
                lead = titles[intent.language][intent.topic] + " · " + refs[0]["name"] + "."
            result = {"text": (lead + " " + prompt).strip(), "references": refs,
                      "retrieval": mode, "model_available": modeled}
        return {**result, "language": state["language"], "session": token, "pending": dict(state["pending"]), "facts": dict(state["facts"]), "changes": list(state["history"])}
