import json
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from .utils import get_mongo_db, call_sarvam_ai
from django.conf import settings

# 1. Define the shared conversational State tracking structure
class AgentState(TypedDict):
    messages: List[Dict[str, str]]               # Chronological chat history
    user_message: str                            # The latest message from the user
    user_turns: int                              # Completed turn counter
    recommended_perfumes: List[Dict[str, Any]]   # Current recommendations (Ranks 1-3)
    other_perfumes: List[Dict[str, Any]]         # Alternative recommendations (Ranks 4-6)
    accords_list: List[str]                      # Extracted notes/accords
    refined_notes: List[str]                     # Refined/added notes from the latest user message
    gender_filter: str                           # Extracted gender filter
    brand_filter: str                            # Extracted brand filter (e.g. Chanel, Armaf)
    disliked_perfumes: List[str]                 # Perfume names the user dislikes
    sort_by_best: bool                           # True if they want top-rated
    bot_reply: str                               # The output chat text to return to the UI

def is_greeting(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "yo", "hi there", "hello there"]
    return text.lower().strip() in greetings

# 2. Helper function to check if a query is unrelated to fragrances
def is_query_unrelated(text: str) -> bool:
    unrelated_keywords = ["what is google", "whats google", "what is a chocolate", "whats chocolate", "how to code", "write a python script", "solve math"]
    normalized = text.lower().strip()
    for kw in unrelated_keywords:
        if kw in normalized:
            return True
    return False

# 3. Router logic (Conditional Edge) to determine which Node executes next
def router_edge(state: AgentState) -> str:
    user_msg = (state.get("user_message") or "").strip()
    recommended = state.get("recommended_perfumes") or []
    has_recommended = len(recommended) > 0
    print(f"[DEBUG router_edge] user_message: '{user_msg}', user_turns: {state.get('user_turns', 0)}")
    
    user_msg_lower = user_msg.lower()
    
    # Fast decline rule to save API calls
    if is_query_unrelated(user_msg_lower):
        return "decline"
        
    # Intercept queries about database ratings, comparative questions, or general listings
    db_qa_keywords = ["whole collection", "entire collection", "whole sollection", "entire sollection", "highest rated", "top rated", "best perfume", "best fragrance", "most popular", "all perfumes", "compare", "difference between"]
    if any(k in user_msg_lower for k in db_qa_keywords):
        return "database_qa"

    # Intercept questions about recommendations, explanations of why we recommended a perfume, or fragrance questions
    qa_keywords = ["why", "explain", "how come", "what notes", "longevity", "how long", "how to apply", "edp", "edt"]
    if any(k in user_msg_lower for k in qa_keywords):
        return "qa"
        
    classify_prompt = (
        "You are a routing supervisor. Your job is to classify the user's latest message intent into one of five categories:\n"
        "- 'decline': The query is completely off-topic (unrelated to perfumes, fragrances, scent notes, smelling, or cosmetic styling).\n"
        "- 'new_search': The user explicitly wants to start a completely new perfume search from scratch or find a new scent for a different person/occasion/style, completely independent of the active recommended options.\n"
        "- 'database_qa': The user is asking a specific question about the fragrance database, ratings, perfumers, comparing specific perfumes, requesting info/listings, or asking for the 'best', 'highest rated', or 'most popular' perfumes (e.g., 'whats the best perfume for women', 'compare Junoon and Hayati', 'which is the highest rated?', 'what notes are in Hayati?', 'do you have perfumes by Christian Carbonnel?').\n"
        "- 'general_qa': General questions about perfume terms (EDP vs EDT), longevity, application, how to use scent, or general advice.\n"
        "- 'scent_matching': The user is looking for perfume suggestions or recommendations based on taste, style, or occasion (e.g., 'recommend me a perfume for the office', 'find my signature scent'), OR sending simple greetings/conversation starters, OR refining active recommendations (e.g. 'add vanilla', 'instead of that').\n\n"
        f"User Message: {user_msg}\n"
        "Respond with ONLY the category name ('decline', 'new_search', 'database_qa', 'general_qa', or 'scent_matching') and absolutely nothing else."
    )
    
    messages = [
        {"role": "system", "content": classify_prompt}
    ]
    
    classification = call_sarvam_ai(messages)
    
    if classification and isinstance(classification, str):
        clean_choice = classification.strip().lower()
        if "decline" in clean_choice:
            return "decline"
        elif "new_search" in clean_choice:
            return "new_search"
        elif "database_qa" in clean_choice:
            return "database_qa"
        elif "general_qa" in clean_choice:
            return "qa"
        elif "scent_matching" in clean_choice:
            user_msg_lower = user_msg.lower()
            is_refining = has_recommended and ("add " in user_msg_lower or "with " in user_msg_lower or "change " in user_msg_lower or "instead " in user_msg_lower or "dislike" in user_msg_lower or "don't like" in user_msg_lower or "do not like" in user_msg_lower)
            if state.get("user_turns", 0) >= 2 or is_refining:
                return "recommend"
            return "chat"
            
    # Reliable fast-fallback rule parser if LLM fails or times out
    import re
    user_msg_lower = user_msg.lower()
    
    new_search_keywords = ["start over", "new search", "different perfume", "recommend a gift", "gift for my"]
    if any(w in user_msg_lower for w in new_search_keywords):
        return "new_search"
        
    # Check if the user message is related to perfumes/scents using the MongoDB dataset
    db = get_mongo_db()
    stop_words = {"what", "is", "a", "the", "who", "which", "would", "how", "do", "you", "me", "this", "these", "it", "with", "for", "and", "or", "in", "of", "about", "detail", "reason", "explain", "why", "can", "have", "has", "does"}
    query_words = [w.strip("?,.!:;\"'") for w in user_msg_lower.split() if len(w.strip("?,.!:;\"'")) > 2 and w.strip("?,.!:;\"'") not in stop_words]
    
    # Also support single-word fragrance topics in case they are not in the database description
    scent_topics = {"longevity", "concentration", "projection", "sillage", "notes", "accord", "accords", "perfume", "fragrance", "edp", "edt", "cologne", "parfum"}
    
    is_related = False
    if any(w in scent_topics for w in query_words):
        is_related = True
    elif query_words:
        # Run a quick check in the database to see if any word matches main_accords or name/description
        escaped_words = [re.escape(w) for w in query_words if w]
        if escaped_words:
            regex_pattern = "|".join([f"\\b{w}\\b" for w in escaped_words])
            db_query = {
                "$or": [
                    {"main_accords": {"$in": query_words}},
                    {"name": {"$regex": regex_pattern, "$options": "i"}},
                    {"description": {"$regex": regex_pattern, "$options": "i"}}
                ]
            }
            try:
                is_related = db["fragrances"].find_one(db_query) is not None
            except Exception:
                is_related = False
                
    is_greet = is_greeting(user_msg_lower)
    
    # If the query has nothing to do with fragrances, brands, or notes in the database, and is not a greeting, decline it
    if not is_related and not is_greet:
        return "decline"
        
    q_words = ["why", "reason", "explain", "detail", "more about", "tell me about", "which is", "recommend option", "which of these", "what is", "how do", "is it", "difference", "how long", "can i", "what notes", "does it have"]
    is_asking_qa = any(w in user_msg_lower for w in q_words) or (has_recommended and ("first" in user_msg_lower or "second" in user_msg_lower or "third" in user_msg_lower))
    
    if is_asking_qa:
        # Check if the question is database-related or general advice
        db_keywords = ["rating", "rated", "compare", "perfume", "fragrance", "database", "brand", "best in", "highest in", "review", "review count", "how many"]
        if any(w in user_msg_lower for w in db_keywords):
            return "database_qa"
        return "qa"
        
    direct_req_words = ["compare", "differ", "contrasting", "versus"]
    is_direct_recommendation = any(w in user_msg_lower for w in direct_req_words)
    is_refining = has_recommended and ("add " in user_msg_lower or "with " in user_msg_lower or "change " in user_msg_lower or "instead " in user_msg_lower or "dislike" in user_msg_lower or "don't like" in user_msg_lower or "do not like" in user_msg_lower)
    
    if state.get("user_turns", 0) >= 2 or is_refining or is_direct_recommendation:
        return "recommend"
        
    return "chat"

# 4. Define Node functions representing individual execution steps

def decline_node(state: AgentState) -> Dict[str, Any]:
    """Politely declines unrelated queries."""
    decline_reply = (
        "I am an AI Scent Advisor dedicated exclusively to helping you find your perfect fragrance, "
        "so I cannot answer unrelated questions. Let me know what kind of scent or vibe you are looking for!"
    )
    return {
        "bot_reply": decline_reply,
        "recommended_perfumes": []  # Hide recommendations on decline
    }

def clarifying_chat_node(state: AgentState) -> Dict[str, Any]:
    """Generates clarifying questions with creative, contextually-related options."""
    # Increment turns ONLY if it is not a greeting
    user_msg = state.get("user_message", "")
    is_greet = is_greeting(user_msg)
    turns = state.get("user_turns", 0)
    if not is_greet:
        turns += 1
    print(f"[DEBUG clarifying_chat_node] user_message: '{user_msg}', is_greet: {is_greet}, old_turns: {state.get('user_turns', 0)} -> new_turns: {turns}")

    convo_system_prompt = (
        "You are an incredibly enthusiastic, passionate, and happy AI Scent Advisor. Engage in a luxury sales conversation. "
        "Your tone must be vibrant, welcoming, and highly persuasive—implicitly steering the customer to feel excited and ready to make a purchase. "
        "Follow these conversational guidelines strictly:\n"
        "1. Be elegant, passionate, concise, and helpful.\n"
        "2. Keep answers short, delightful, and highly positive (max 3 sentences per reply). Show genuine excitement to find their perfect match.\n"
        "3. Ask exactly ONE relevant clarifying question in simple English to build and refine the user's note profile. "
        "The purpose of your question is to help the user discover and add complementary notes or accords to their preference (e.g., if they selected floral notes, suggest adding fresh citrus, warm vanilla, or earthy woody notes to complement them). "
        "Never conclude the conversation or say you are ready to find a bottle; always ask how to expand or refine their note list. "
        "At the very end of your response, after your clarifying question is fully complete, provide 2 to 3 complementary suggestion options/accords formatted in square brackets (e.g., [Vanilla & Amber] [Woody Cedarwood]). "
        "These options MUST be specific scent notes, accords, or ingredients in simple English that are designed to complement and refine their current selection. "
        "The options must totally relate to the question. "
        "Do NOT write any words, conjunctions, or punctuation between, before, or after the square brackets. "
        "Example format: 'Would you like to add some fresh citrus brightness or warm woody depth to your rose and jasmine? [Fresh Bergamot & Lime] [Warm Sandalwood & Amber]'\n"
        "4. NEVER suggest offline actions like store visits. This is purely a digital scent fragrance matcher.\n"
        "5. NEVER use Markdown formatting symbols like asterisks (**) or hashes (###).\n"
        "6. If the user's input is completely unrelated to fragrances, decline politely."
    )
    
    messages = [{"role": "system", "content": convo_system_prompt}]
    for msg in (state.get("messages") or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": (state.get("user_message") or "")})
    
    reply = call_sarvam_ai(messages)
    if not reply or not isinstance(reply, str) or "Error from Sarvam API" in reply or "Connection Failed" in reply:
        # Fallback question on connection issues to keep conversation alive
        reply = (
            "I am currently experiencing a minor connection hiccup with our olfactory advisor network, "
            "but I'd still love to help you find your signature scent! "
            "Could you share if you generally prefer fresh and citrusy notes, or deeper woody notes? [Fresh Citrus & Mint] [Warm Vanilla & Cedar]"
        )
    return {"bot_reply": reply, "user_turns": turns}

def extract_intent_node(state: AgentState) -> Dict[str, Any]:
    """Analyzes history to extract gender, accords, refined notes, brand filter, dislikes, and sorting."""
    dialog_transcript = ""
    for msg in (state.get("messages") or []):
        dialog_transcript += f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}\n"
    dialog_transcript += f"USER: {(state.get('user_message') or '')}\n"
    
    extraction_prompt = (
        "You are a structural engine. You MUST carefully analyze the entire conversation history transcript and extract the user's fragrance preferences.\n"
        "Analyze all user messages and choices made throughout the conversation.\n"
        "Identify:\n"
        "1. The target gender: 'for women', 'for men', or 'for women and men'. Identify this strictly from the user's explicit gender requests (e.g., 'for a woman', 'for my dad', 'mens perfume', 'perfume for a woman'). Once the user establishes the target gender early in the conversation (e.g., 'looking for a woman's perfume'), do NOT change it unless the user explicitly requests a change to a different gender. NEVER let recommendations or assistant responses in the chat history override the user's original gender selection.\n"
        "2. Scent accords: Extract ALL scent notes, ingredients, accords, and vibe keywords mentioned or selected by the user across the ENTIRE conversation (such as vanilla, cedarwood, rose, vetiver, ginger, sweet, floral, woody, fresh, office, warm, etc.). Do not miss any notes from previous turns. Return them as a flat list of strings. Correct any spelling typos or abbreviations (e.g. change 'carmel' to 'caramel', 'cardomom' to 'cardamom', 'sollection' to 'collection', 'jasmin' to 'jasmine', 'bergamont' to 'bergamot') so that they match correct standard ingredient spellings.\n"
        "3. Refined notes: Extract any specific scent notes, ingredients, or accords that the user explicitly asked to ADD, include, or focus on in their LATEST message (e.g., if the user says 'add vanilla scent also', extract ['vanilla']). If none, return an empty list. Correct any spelling typos in these notes to standard spellings (e.g., change 'carmel' to 'caramel', 'cardomom' to 'cardamom').\n"
        "4. Brand: Extract specific perfume brand requested by user if any (e.g. 'Chanel', 'Armaf', 'Al Haramain Perfumes', 'Ariana Grande'). If no brand is requested, return null.\n"
        "5. Disliked perfumes: Extract a list of perfume names the user explicitly rejected or dislikes in this turn or previous turns. If none, return an empty list.\n"
        "6. Sort by best: Return true if user explicitly wants the 'best', 'highest rated', 'top rated', or 'most popular' perfumes. Otherwise return false.\n"
        "Respond with ONLY a JSON block: {\"gender\": \"for women\"|\"for men\"|\"for women and men\", \"accords\": [\"tag1\", \"tag2\"], \"refined_notes\": [\"note1\"], \"brand\": \"brand_name\"|null, \"disliked\": [\"name1\"], \"sort_by_best\": true|false}. No code blocks or explanations."
    )
    
    messages = [
        {"role": "system", "content": extraction_prompt},
        {"role": "user", "content": dialog_transcript}
    ]
    
    extracted_raw = call_sarvam_ai(messages)
    
    import re
    try:
        clean_json_str = extracted_raw.strip()
        json_match = re.search(r'\{.*\}', clean_json_str, re.DOTALL)
        if json_match:
            clean_json_str = json_match.group(0)
        else:
            if "```" in clean_json_str:
                clean_json_str = clean_json_str.split("```")[1]
                if clean_json_str.startswith("json"):
                    clean_json_str = clean_json_str[4:]
        filters = json.loads(clean_json_str.strip())
        gender_filter = filters.get("gender", "for women and men")
        accords_list = filters.get("accords", [])
        refined_notes = filters.get("refined_notes", [])
        brand_filter = filters.get("brand")
        new_disliked = filters.get("disliked", [])
        sort_by_best = filters.get("sort_by_best", False)
    except Exception as e:
        print(f"[ERROR extract_intent_node] JSON parsing failed: {e}. Raw: {extracted_raw}")
        gender_filter = "for women and men"
        accords_list = []
        refined_notes = []
        brand_filter = None
        new_disliked = []
        sort_by_best = False
        
    existing_disliked = state.get("disliked_perfumes") or []
    merged_disliked = list(set(existing_disliked + [d.strip() for d in new_disliked if d.strip()]))
        
    return {
        "gender_filter": gender_filter,
        "accords_list": accords_list,
        "refined_notes": refined_notes,
        "brand_filter": brand_filter,
        "disliked_perfumes": merged_disliked,
        "sort_by_best": sort_by_best
    }

def query_database_node(state: AgentState) -> Dict[str, Any]:
    """Queries MongoDB collection using accords list, brand filter, and disliked exclusion, sorting by best if specified."""
    db = get_mongo_db()
    gender_filter = state.get("gender_filter", "for women and men")
    accords_list = state.get("accords_list", [])
    refined_notes = state.get("refined_notes", [])
    brand_filter = state.get("brand_filter")
    disliked_perfumes = state.get("disliked_perfumes") or []
    sort_by_best = state.get("sort_by_best", False)
    
    gender_q = None
    if gender_filter == "for women":
        gender_q = {"$in": ["for women", "for women and men"]}
    elif gender_filter == "for men":
        gender_q = {"$in": ["for men", "for women and men"]}
        
    query = {}
    if gender_q:
        query["gender"] = gender_q
        
    if brand_filter:
        query["name"] = {"$regex": brand_filter, "$options": "i"}
        
    if disliked_perfumes:
        disliked_regex = "|".join([f"^{d}$" for d in disliked_perfumes if d.strip()])
        if disliked_regex:
            if "name" in query:
                query["$and"] = [
                    {"name": query["name"]},
                    {"name": {"$not": {"$regex": disliked_regex, "$options": "i"}}}
                ]
                del query["name"]
            else:
                query["name"] = {"$not": {"$regex": disliked_regex, "$options": "i"}}
        
    flat_accords = []
    if isinstance(accords_list, list):
        for item in accords_list:
            if isinstance(item, list):
                for subitem in item:
                    if isinstance(subitem, str):
                        flat_accords.append(subitem)
            elif isinstance(item, str):
                flat_accords.append(item)
    elif isinstance(accords_list, str):
        flat_accords.append(accords_list)
        
    search_terms = [a.lower().strip() for a in flat_accords if isinstance(a, str) and a.strip()]
    refined_terms = [r.lower().strip() for r in refined_notes if isinstance(r, str) and r.strip()]
    combined_search_terms = list(set(search_terms + refined_terms))
    
    if combined_search_terms:
        match_query = [
            {"main_accords": {"$in": combined_search_terms}},
            {"description": {"$regex": "|".join(combined_search_terms), "$options": "i"}}
        ]
        if "$and" in query:
            query["$and"].append({"$or": match_query})
        else:
            query["$or"] = match_query
            
    if sort_by_best:
        cursor = db["fragrances"].find(query).sort([("rating_value", -1), ("rating_count", -1)]).limit(100)
    else:
        cursor = db["fragrances"].find(query).limit(200)
        
    candidates = list(cursor)
    
    # Fallback 1: Match accords only
    if len(candidates) < 10 and combined_search_terms:
        fallback_query = {}
        if gender_q:
            fallback_query["gender"] = gender_q
        if brand_filter:
            fallback_query["name"] = {"$regex": brand_filter, "$options": "i"}
        if disliked_perfumes:
            disliked_regex = "|".join([f"^{d}$" for d in disliked_perfumes if d.strip()])
            if disliked_regex:
                fallback_query["name"] = fallback_query.get("name", {})
                if isinstance(fallback_query["name"], dict):
                    fallback_query["name"]["$not"] = {"$regex": disliked_regex, "$options": "i"}
                else:
                    fallback_query["name"] = {"$not": {"$regex": disliked_regex, "$options": "i"}}
        fallback_query["main_accords"] = {"$in": combined_search_terms}
        
        if sort_by_best:
            cursor = db["fragrances"].find(fallback_query).sort([("rating_value", -1), ("rating_count", -1)]).limit(100)
        else:
            cursor = db["fragrances"].find(fallback_query).limit(100)
            
        for doc in cursor:
            if doc["_id"] not in [c["_id"] for c in candidates]:
                candidates.append(doc)
                
    # Fallback 2: Match gender filter only
    if len(candidates) < 10:
        gender_query = {}
        if gender_q:
            gender_query["gender"] = gender_q
        if brand_filter:
            gender_query["name"] = {"$regex": brand_filter, "$options": "i"}
        if disliked_perfumes:
            disliked_regex = "|".join([f"^{d}$" for d in disliked_perfumes if d.strip()])
            if disliked_regex:
                gender_query["name"] = gender_query.get("name", {})
                if isinstance(gender_query["name"], dict):
                    gender_query["name"]["$not"] = {"$regex": disliked_regex, "$options": "i"}
                else:
                    gender_query["name"] = {"$not": {"$regex": disliked_regex, "$options": "i"}}
            
        if sort_by_best:
            cursor = db["fragrances"].find(gender_query).sort([("rating_value", -1), ("rating_count", -1)]).limit(100)
        else:
            cursor = db["fragrances"].find(gender_query).limit(100)
            
        for doc in cursor:
            if doc["_id"] not in [c["_id"] for c in candidates]:
                candidates.append(doc)
                
    # Fallback 3: Return anything matching gender_q
    if len(candidates) < 10:
        anything_query = {}
        if gender_q:
            anything_query["gender"] = gender_q
        if brand_filter:
            anything_query["name"] = {"$regex": brand_filter, "$options": "i"}
        if disliked_perfumes:
            disliked_regex = "|".join([f"^{d}$" for d in disliked_perfumes if d.strip()])
            if disliked_regex:
                anything_query["name"] = anything_query.get("name", {})
                if isinstance(anything_query["name"], dict):
                    anything_query["name"]["$not"] = {"$regex": disliked_regex, "$options": "i"}
                else:
                    anything_query["name"] = {"$not": {"$regex": disliked_regex, "$options": "i"}}
                    
        if sort_by_best:
            cursor = db["fragrances"].find(anything_query).sort([("rating_value", -1), ("rating_count", -1)]).limit(100)
        else:
            cursor = db["fragrances"].find(anything_query).limit(100)
            
        for doc in cursor:
            if doc["_id"] not in [c["_id"] for c in candidates]:
                candidates.append(doc)
                
    # Score and strictly filter Candidates by gender and note intersection relevance
    scored_candidates = []
    for perf in candidates:
        # Enforce strict gender check to prevent leaks in fallback queries
        perf_gender = (perf.get("gender") or "").lower().strip()
        if gender_filter == "for women" and perf_gender == "for men":
            continue
        if gender_filter == "for men" and perf_gender == "for women":
            continue
            
        score = 0
        accords = [a.lower().strip() for a in (perf.get("main_accords") or []) if isinstance(a, str)]
        description = (perf.get("description") or "").lower()
        
        for term in search_terms:
            if term in accords:
                score += 20
            score += description.count(term) * 2
            
        # Heavy score boost for explicitly added/refined notes in the latest turn
        for term in refined_terms:
            if term in accords:
                score += 250
            if term in description:
                score += 150
            
        scored_candidates.append((score, perf))
        
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Always slice from the sorted list to prioritize high relevance matches
    sorted_candidates_flat = [item[1] for item in scored_candidates]
    matched_perfumes = sorted_candidates_flat[:3]
    other_perfumes = sorted_candidates_flat[3:6]
    
    # Convert ObjectIds to string for JSON serialization
    serialized_primary = []
    for p in matched_perfumes:
        serialized_primary.append({
            "name": p["name"],
            "rating": p.get("rating_value", 0.0),
            "description": p.get("description", ""),
            "accords": p.get("main_accords", [])
        })
        
    serialized_secondary = []
    for p in other_perfumes:
        serialized_secondary.append({
            "name": p["name"],
            "rating": p.get("rating_value", 0.0),
            "description": p.get("description", ""),
            "accords": p.get("main_accords", [])
        })
        
    return {
        "recommended_perfumes": serialized_primary,
        "other_perfumes": serialized_secondary
    }

def generate_pitch_node(state: AgentState) -> Dict[str, Any]:
    """Generates split-bubble sales pitches for primary (Ranks 1-3) and secondary (Ranks 4-5) perfumes."""
    recommended = state.get("recommended_perfumes", [])
    other = (state.get("other_perfumes") or [])[:2] # Only Ranks 4 and 5
    
    allowed_names = [p["name"] for p in recommended]
    other_names = [p["name"] for p in other]
    
    primary_catalog = ""
    for index, p in enumerate(recommended):
        primary_catalog += f"Primary Option {index+1}: Name: {p['name']}, Description: {p['description']}\n"
        
    secondary_catalog = ""
    for index, p in enumerate(other):
        secondary_catalog += f"Secondary Option {index+4}: Name: {p['name']}, Description: {p['description']}\n"
        
    catalog_context = f"PRIMARY CHOICES (Ranks 1-3):\n{primary_catalog}\nSECONDARY CHOICES (Ranks 4-5):\n{secondary_catalog}"
    
    sales_system_prompt = (
        f"You are the ultimate luxury AI Scent Advisor. Recommend these matching perfumes with extreme enthusiasm, passion, and persuasive sales flair to convince the customer to purchase immediately. Highlight the irresistible, glamorous qualities of each scent, making them sound absolutely essential, luxurious, and perfect for the customer's desires.\n"
        f"Scent Catalog Database Context:\n{catalog_context}\n"
        f"Guidelines:\n"
        f"1. Write your response in exactly TWO parts, separated by the exact word '[NEXT_MESSAGE]' on a new line.\n"
        f"2. PART 1 (before '[NEXT_MESSAGE]'): \n"
        f"   - If the user explicitly asks to compare, contrast, or explain differences between the recommended perfumes in their latest request, write a detailed, luxurious comparison analysis of the Primary Option perfumes (e.g. how their notes differ, who would prefer one over the other, and their unique qualities). Still separate your analysis into distinct, readable paragraphs separated by double newlines.\n"
        f"   - If the user is asking a specific question about the database data, notes, or descriptions of these perfumes, answer their question accurately and beautifully based on the Scent Catalog Database Context. Structure your answer in distinct, readable paragraphs separated by double newlines.\n"
        f"   - Otherwise, pitch exactly the 3 Primary Option perfumes: {', '.join(allowed_names)}. For each of these 3 perfumes, write a separate, distinct paragraph (1 to 2 highly persuasive sentences) explaining why it is absolutely perfect for the customer. You MUST start each paragraph with the name of the perfume in all caps followed by a colon (e.g. 'PERFUME NAME: explanation'). You MUST insert a double newline (\\n\\n) between each of the 3 paragraphs so they render separately. Do NOT mix them into a single paragraph.\n"
        f"3. PART 2 (after '[NEXT_MESSAGE]'): Introduce the 2 Secondary Option perfumes: {', '.join(other_names)}. Write a short, highly enthusiastic follow-up sales pitch in a single, unified paragraph, encouraging them to consider these 2 alternatives. Do NOT write detailed paragraphs or detailed descriptions for each alternative; simply mention them by name in one short paragraph.\n"
        f"4. Keep all paragraphs short, elegant, extremely persuasive, and highly appealing. Keep your internal reasoning/thinking extremely concise (under 2 sentences) so that you do not hit output length limits, and make sure your response is fully complete and does not cut off mid-sentence.\n"
        f"5. Do NOT invite the user to private viewings, store appointments, or offline services.\n"
        f"6. Do NOT use markdown symbols like asterisks (**) or hashes (###).\n"
        f"7. Suggest that the user can ask to explore more options or refine their search parameters if they wish.\n"
        f"8. CRITICAL: You MUST write pitches ONLY for the 3 Primary Option perfumes: {', '.join(allowed_names)}. Do NOT pitch the user's message selection (like 'Warm Vanilla & Amber') if it is not one of the 3 Primary Option perfumes. Avoid repeating any perfume names or descriptions. Do NOT get stuck in repetition loops listing the same perfumes multiple times.\n"
        f"9. LANGUAGE RULE: Analyze the user's LATEST message (the last message in the conversation). If the user's LATEST message is written in a language other than English, or explicitly asks for the response to be in a specific language, you MUST generate your entire final reply in that requested language. You MUST write in the native script of that language (e.g. Devanagari for Hindi 'हिंदी', Tamil script for Tamil 'தமிழ்', Arabic script for Arabic, Cyrillic for Russian, etc.). Do NOT use transliterated English characters. Otherwise, if the user's LATEST message is in English and does not request a translation, you MUST reply in English. Preserve all formatting (like '[NEXT_MESSAGE]') exactly."
    )
    
    messages = [{"role": "system", "content": sales_system_prompt}]
    for msg in state.get("messages", []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": state.get("user_message", "")})
    
    pitch = call_sarvam_ai(messages)
    
    if not pitch or not isinstance(pitch, str) or "Error from Sarvam API" in pitch or "Connection Failed" in pitch:
        # Graceful fallback database descriptions to prevent 502 Bad Gateway
        # Format with double newlines so the frontend splits them into clean separate bubbles
        primary_paragraphs = []
        for p in recommended:
            desc_text = p.get('description', '')
            primary_paragraphs.append(f"{p['name']}\n{desc_text}")
        
        pitch = "\n\n".join(primary_paragraphs)
         
        pitch += "\n\n[NEXT_MESSAGE]\nYou should also explore these captivating alternative selections with similar notes:\n\n"
        pitch += f"{', '.join(other_names)}"
            
    return {"bot_reply": pitch}

def qa_node(state: AgentState) -> Dict[str, Any]:
    """Handles general scent questions, application questions, note details, or follow-ups regarding recommended perfumes."""
    recommended = state.get("recommended_perfumes", [])
    other = state.get("other_perfumes", [])
    
    perfumes_str = ""
    for idx, p in enumerate(recommended):
        accords_list = p.get("accords", [])
        accords_str = ", ".join(accords_list) if isinstance(accords_list, list) else str(accords_list)
        perfumes_str += f"Option {idx+1}: {p['name']} - Main Accords: {accords_str} - Description: {p['description']}\n"
    for idx, p in enumerate(other):
        accords_list = p.get("accords", [])
        accords_str = ", ".join(accords_list) if isinstance(accords_list, list) else str(accords_list)
        perfumes_str += f"Option {idx+4}: {p['name']} - Main Accords: {accords_str} - Description: {p['description']}\n"
        
    qa_system_prompt = (
        "You are the ultimate luxury AI Scent Advisor. Answer the user's fragrance-related questions accurately and elegantly.\n"
        "If they are asking about previously recommended perfumes (such as why a perfume was recommended or explaining a choice), use the provided context to give a clear, specific explanation by explicitly mapping the perfume's actual Main Accords and Description notes to the user's desired preferences. Present this explanation strictly as a neat, luxury-styled list of bullet points (maximum 3 bullet points) where each bullet point starts with the solid circle symbol '●' (do not use asterisks '*' or hyphens '-'), is rich and highly descriptive, and elegantly details how specific accords (like vanilla, woody, etc.) map directly to their request. You MUST add a blank line between each bullet point to ensure they are spaced out nicely and are not grouped close together.\n"
        "If they are asking about previously recommended perfumes, use this context:\n"
        f"{perfumes_str}\n"
        "If they are asking general questions about scent notes, longevity, perfume application, classifications (e.g., Vetiver, EDP vs EDT), or general styling advice, answer them accurately and beautifully using your expert fragrance knowledge.\n"
        "Guidelines:\n"
        "1. Be extremely enthusiastic, welcoming, and professional.\n"
        "2. Answer the question completely and accurately. Present your response strictly using a solid circle symbol '●' (do not use asterisks '*' or hyphens '-') for bullet points (maximum 3 bullet points) where each bullet point is rich, descriptive, and elegantly detailed. You MUST add a blank line between each bullet point to keep the response clean, well-spaced, and easy to read.\n"
        "3. Keep your internal reasoning/thinking extremely concise (under 2 sentences) to prevent cut-offs.\n"
        "4. Do NOT invite the user to private viewings or offline appointments.\n"
        "5. Do NOT use markdown symbols like asterisks (**) or hashes (###).\n"
        "6. If suggesting complementary notes or accords, format them simply in square brackets (e.g., [Woody Cedarwood] [Fresh Mint]).\n"
        "7. LANGUAGE RULE: Analyze the user's LATEST message (the last message in the conversation). If the user's LATEST message is written in a language other than English, or explicitly asks for the response to be in a specific language, you MUST generate your entire final reply in that requested language. You MUST write in the native script of that language (e.g. Devanagari for Hindi 'हिंदी', Tamil script for Tamil 'தமிழ்', Arabic script for Arabic, Cyrillic for Russian, etc.). Do NOT use transliterated English characters. Otherwise, if the user's LATEST message is in English and does not request a translation, you MUST reply in English. Preserve all formatting (like '●' bullet points and blank lines exactly)."
    )
    
    messages = [{"role": "system", "content": qa_system_prompt}]
    for msg in state.get("messages", []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": state.get("user_message", "")})
    
    reply = call_sarvam_ai(messages)
    if not reply or not isinstance(reply, str) or "Error from Sarvam API" in reply or "Connection Failed" in reply:
        reply = "I'd be glad to help answer your question, but I'm currently having a network connection issue. Could you please try again in a moment?"
        
    return {"bot_reply": reply}
 
 
def database_qa_node(state: AgentState) -> Dict[str, Any]:
    """Generates a MongoDB query based on the user's question, runs it, and answers the question using the retrieved data."""
    user_msg = state.get("user_message", "")
    
    query_prompt = (
        "You are an expert MongoDB query generator for a fragrance database.\n"
        "The collection is named 'fragrances'. The schema is:\n"
        "- name: string (e.g. 'Junoon Al Haramain Perfumesfor women')\n"
        "- gender: string ('for women', 'for men', 'for women and men')\n"
        "- rating_value: float (0.0 to 5.0)\n"
        "- rating_count: integer\n"
        "- main_accords: list of strings (e.g. ['powdery', 'rose', 'vanilla'])\n"
        "- perfumers: list of strings (e.g. ['Christian Carbonnel'])\n"
        "- description: string (detailed text about notes, nose, year, etc.)\n\n"
        "Based on the user's question, construct a MongoDB query filter JSON to fetch the relevant documents to answer the question.\n"
        f"User question: {user_msg}\n"
        "Guidelines:\n"
        "- For name, description, or perfumer searches, use case-insensitive regex, e.g. {\"name\": {\"$regex\": \"Hayati\", \"$options\": \"i\"}}\n"
        "- If the user explicitly asks for exclusion or negation (e.g. 'without vanilla', 'excluding rose', 'no musk'), use MongoDB negation operators like '$nin' or '$not' with regex, e.g. {\"main_accords\": {\"$nin\": [\"vanilla\"]}} or {\"description\": {\"$not\": {\"$regex\": \"rose\", \"$options\": \"i\"}}}\n"
        "- Return ONLY the JSON query filter block and absolutely nothing else. Do not wrap in markdown code blocks."
    )
    
    messages = [{"role": "system", "content": query_prompt}]
    query_raw = call_sarvam_ai(messages)
    
    query = {}
    try:
        clean_json = query_raw.strip()
        if "```" in clean_json:
            clean_json = clean_json.split("```")[1]
            if clean_json.startswith("json"):
                clean_json = clean_json[4:]
        query = json.loads(clean_json.strip())
    except Exception:
        # Fallback keyword and gender extraction if LLM fails or returns invalid/null JSON
        query = {}
        msg_lower = user_msg.lower()
        if "women and men" in msg_lower or "unisex" in msg_lower or "both" in msg_lower:
            query["gender"] = "for women and men"
        elif "women" in msg_lower or "woman" in msg_lower:
            query["gender"] = "for women"
        elif "men" in msg_lower or "man" in msg_lower:
            query["gender"] = "for men"
            
        stop_words = {"compare", "notes", "give", "best", "these", "women", "woman", "mens", "perfume", "perfumes", "fragrance", "fragrances", "select", "rating", "rated", "highest", "which", "would", "what", "about", "detail", "details", "for", "whats", "what's", "tell", "show", "list", "find", "search", "some", "top", "most", "popular"}
        keywords = [w.strip("?,.!:;\"'") for w in user_msg.split() if len(w) > 3 and w.lower().strip("?,.!:;\"'") not in stop_words]
        if keywords:
            regex_str = "|".join(keywords)
            query["$or"] = [
                {"name": {"$regex": regex_str, "$options": "i"}},
                {"description": {"$regex": regex_str, "$options": "i"}}
            ]
            
    # Clean and sanitize the query parameters to match MongoDB exactly
    print(f"[DEBUG database_qa_node] Generated raw query: {query}")
    if isinstance(query, dict):
        if "gender" in query:
            g_val = str(query["gender"]).lower()
            if "women and men" in g_val or "unisex" in g_val or "both" in g_val:
                query["gender"] = "for women and men"
            elif "women" in g_val or "woman" in g_val:
                query["gender"] = "for women"
            elif "men" in g_val or "man" in g_val:
                query["gender"] = "for men"
        # Clean both name and description from general query or superlative words ONLY if they consist entirely of query keywords
        bad_words = {"top", "best", "highest", "rated", "perfume", "perfumes", "fragrance", "fragrances", "woman", "women", "man", "men", "whats", "what's", "show", "list", "collection", "and", "for", "the"}
        
        def is_junk_regex(val):
            import re
            words = re.findall(r'\b\w+\b', val.lower())
            if not words:
                return True
            return all(w in bad_words for w in words)

        if "name" in query:
            name_val = str(query["name"]["$regex"]) if isinstance(query["name"], dict) and "$regex" in query["name"] else str(query["name"])
            if is_junk_regex(name_val):
                del query["name"]
        if "description" in query:
            desc_val = str(query["description"]["$regex"]) if isinstance(query["description"], dict) and "$regex" in query["description"] else str(query["description"])
            if is_junk_regex(desc_val):
                del query["description"]
            
    db = get_mongo_db()
    try:
        is_best_query = any(w in user_msg.lower() for w in ["best", "popular", "most loved"])
        is_top_query = any(w in user_msg.lower() for w in ["top", "highest"])
        
        if is_best_query:
            # For 'best' queries, require a minimum of 100 ratings to filter out single-vote 5.0 ratings, then sort by rating & popularity
            best_query = query.copy()
            best_query["rating_count"] = {"$gte": 100}
            cursor = db["fragrances"].find(best_query).sort([("rating_value", -1), ("rating_count", -1)]).limit(3)
            records = list(cursor)
            # If no results match the filter threshold, fallback to query without the rating count restriction
            if not records:
                cursor = db["fragrances"].find(query).sort([("rating_value", -1), ("rating_count", -1)]).limit(3)
                records = list(cursor)
        elif is_top_query:
            # For 'top rated', sort purely by rating value (direct 5.0s are returned first)
            cursor = db["fragrances"].find(query).sort([("rating_value", -1)]).limit(3)
            records = list(cursor)
        else:
            cursor = db["fragrances"].find(query).limit(3)
            records = list(cursor)
    except Exception:
        records = []
        
    context = ""
    for r in records:
        desc = r.get('description', '')
        if len(desc) > 300:
            desc = desc[:300] + "..."
        context += (
            f"Name: {r['name']}\n"
            f"Gender: {r['gender']}\n"
            f"Rating: {r.get('rating_value', 0.0)} ({r.get('rating_count', 0)} ratings)\n"
            f"Accords: {', '.join(r.get('main_accords', []))}\n"
            f"Perfumers: {', '.join(r.get('perfumers', []))}\n"
            f"Description: {desc}\n\n"
        )
        
    answer_prompt = (
        "You are the ultimate luxury AI Scent Advisor. Answer the user's question accurately and elegantly based on the provided database context.\n"
        f"Database Context:\n{context or 'No matching perfumes found in the database.'}\n\n"
        "Guidelines:\n"
        "1. Be extremely enthusiastic, welcoming, and professional.\n"
        "2. Answer the user's question completely and accurately using the context. You MUST explicitly name the perfumes you are referring to. Do not make up facts not present in the context.\n"
        "3. Present your answer strictly using a solid circle symbol '●' (not asterisks '*' or hyphens '-') for bullet points (maximum 4 bullet points). Each bullet point must explicitly mention the name of the perfume first (e.g., '● PERFUME_NAME - description'), and be rich, highly detailed, and elegantly descriptive. You MUST add a blank line between each bullet point to keep the response clean, well-spaced, and easy to read.\n"
        "4. Do NOT use markdown symbols like asterisks (*) or hashes (#) except for the '●' bullet point marker.\n"
        "5. LANGUAGE RULE: Analyze the user's LATEST message (the last message in the conversation). If the user's LATEST message is written in a language other than English, or explicitly asks for the response to be in a specific language, you MUST generate your entire final reply in that requested language. You MUST write in the native script of that language (e.g. Devanagari for Hindi 'हिंदी', Tamil script for Tamil 'தமிழ்', Arabic script for Arabic, Cyrillic for Russian, etc.). Do NOT use transliterated English characters. Otherwise, if the user's LATEST message is in English and does not request a translation, you MUST reply in English. Preserve all formatting (like '●' bullet points and blank lines exactly)."
    )
    
    messages = [{"role": "system", "content": answer_prompt}]
    for msg in state.get("messages", []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_msg})
    
    reply = call_sarvam_ai(messages)
    if not reply or not isinstance(reply, str) or "Error from Sarvam API" in reply or "Connection Failed" in reply:
        reply = "I'd be glad to help answer your question, but I'm currently having a network connection issue. Could you please try again in a moment?"
        
    return {"bot_reply": reply}


def new_search_node(state: AgentState) -> Dict[str, Any]:
    """Resets the state turn count and active recommendations for a brand new search loop."""
    return {
        "messages": [],
        "user_turns": 0,
        "recommended_perfumes": [],
        "other_perfumes": [],
        "brand_filter": None,
        "accords_list": [],
        "refined_notes": [],
        "gender_filter": "for women and men"
    }


# 5. Build and Compile the LangGraph state machine
builder = StateGraph(AgentState)

# Register the nodes
builder.add_node("decline", decline_node)
builder.add_node("chat", clarifying_chat_node)
builder.add_node("extract_intent", extract_intent_node)
builder.add_node("db_query", query_database_node)
builder.add_node("generate_pitch", generate_pitch_node)
builder.add_node("qa", qa_node)
builder.add_node("database_qa", database_qa_node)
builder.add_node("new_search", new_search_node)

# Define entry route mapping
builder.set_conditional_entry_point(
    router_edge,
    {
        "decline": "decline",
        "chat": "chat",
        "qa": "qa",
        "recommend": "extract_intent",
        "new_search": "new_search",
        "database_qa": "database_qa"
    }
)

# Connect recommendation nodes in sequential order
builder.add_edge("extract_intent", "db_query")
builder.add_edge("db_query", "generate_pitch")
builder.add_edge("new_search", "chat")

# Set endpoints
builder.add_edge("decline", END)
builder.add_edge("chat", END)
builder.add_edge("qa", END)
builder.add_edge("database_qa", END)
builder.add_edge("generate_pitch", END)

# Compile the compiled executable graph
scent_advisor_graph = builder.compile()
