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
    requested_language: str                      # Explicitly requested language from user input (e.g. 'tamil', 'french')

def is_greeting(text: str) -> bool:
    greetings = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "yo", "hi there", "hello there"]
    return text.lower().strip() in greetings

def get_language_instruction(user_msg: str, requested_language: str = None) -> str:
    if requested_language and requested_language.strip().lower() not in ["english", "eng"]:
        return (
            f"CRITICAL LANGUAGE RULE: You MUST write your entire final response in {requested_language.upper()} script or text as requested. "
            "Do NOT write any English sentences. Always preserve the bullet point structure (solid circle '●' and blank line spacing) exactly."
        )
    return "CRITICAL LANGUAGE RULE: You MUST write your entire final response in ENGLISH. Do NOT translate to any other language."

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
    
    # 1. Fast decline rule to save API calls
    if is_query_unrelated(user_msg_lower):
        return "decline"
        
    # 2. Fast intercept for greetings
    if is_greeting(user_msg):
        return "chat"
        
    # 3. Fast intercept for starting over / new search requests
    new_search_keywords = ["start over", "new search", "different perfume", "recommend a gift", "gift for my", "new scent", "new perfume", "another perfume", "different scent", "new fragrance", "another fragrance", "new vennum", "new perfume vennum"]
    if any(w in user_msg_lower for w in new_search_keywords):
        return "new_search"

    # 4. Fast intercept for option button clicks
    messages = state.get("messages") or []
    if messages:
        last_assistant_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg.get("content", "")
                break
        if last_assistant_msg:
            import re
            options = re.findall(r'\[(.*?)\]', last_assistant_msg)
            clean_options = [opt.strip().lower() for opt in options]
            if user_msg_lower.strip() in clean_options:
                return "recommend"

    # 5. Fast intercept for note additions/refinements
    refine_keywords = ["add ", "also want", "instead of", "smell like", "smells like", "prefer ", "with "]
    if any(k in user_msg_lower for k in refine_keywords) or user_msg_lower.startswith("and "):
        return "recommend"

    # 6. Extract recent conversation history for classification context
    history_context = ""
    history_messages = state.get("messages") or []
    if history_messages:
        history_context = "Recent Conversation History:\n"
        for m in history_messages[-3:]:
            role = "User" if m.get("role") == "user" else "Assistant"
            history_context += f"{role}: {m.get('content')}\n"
        history_context += "\n"

    # 7. Use LLM to classify the semantic intent of the query
    classify_prompt = (
        "You are a routing supervisor. Your job is to classify the user's latest message intent into one of five categories:\n"
        "- 'decline': The query is completely off-topic (unrelated to perfumes, fragrances, scent notes, smelling, or cosmetic styling).\n"
        "- 'new_search': The user explicitly wants to start a completely new perfume search from scratch, find a different perfume, search for someone else (e.g. 'looking for a perfume for my aunt', 'gift for my husband'), or start over independent of the active recommended options.\n"
        "- 'database_qa': The user is asking a specific question about the database, ratings, perfumers, comparing specific perfumes, requesting info/listings, or asking for the 'best', 'highest rated', or 'most popular' perfumes (e.g., 'whats the best perfume for women', 'compare Junoon and Hayati', 'which is the highest rated?', 'what notes are in Hayati?', 'do you have perfumes by Christian Carbonnel?'). CRITICAL: If the user is asking WHY a perfume was recommended, comparing recommended perfumes, or asking questions about a recommended perfume, classify it as 'database_qa'. Do NOT classify it as 'recommend'.\n"
        "- 'qa': General questions about perfume terms (EDP vs EDT), longevity, application, how to use scent, or general advice.\n"
        "- 'recommend': The user is looking for perfume suggestions or recommendations based on taste, style, or occasion (e.g., 'recommend me a perfume for the office', 'find my signature scent'), OR refining active recommendations (e.g. 'add vanilla', 'instead of that', 'add jasmine and rose').\n\n"
        f"{history_context}"
        f"User Message: {user_msg}\n"
        "Respond with ONLY the category name ('decline', 'new_search', 'database_qa', 'qa', or 'recommend') and absolutely nothing else."
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
        elif "qa" in clean_choice:
            return "qa"
        elif "recommend" in clean_choice:
            return "recommend"
            
    # Fallback to recommend if LLM fails
    return "recommend"

# 4. Define Node functions representing individual execution steps
def translate_input_node(state: AgentState) -> Dict[str, Any]:
    """Translates the user message to standard English if it is in another language or script."""
    raw_msg = state.get("user_message", "")
    
    translation_prompt = (
        "You are a translation assistant. Your goal is to translate the user's message to clear, standard English.\n"
        "CRITICAL: Do NOT answer the user's message. Do NOT provide suggestions, recommendations, or answers to the user's query.\n"
        "Your ONLY job is to translate the input message into English.\n"
        "If the input is already in English, you MUST return the input message exactly as it is, without adding any suggestions or answers.\n"
        "1. If the message is already in English, return it exactly as is.\n"
        "2. If the message is in a foreign script (Tamil, Devanagari, French, etc.) or is written phonetically using Latin letters (e.g. 'ennaku pathi sollu', 'ye perfume kaise hai', 'dime sobre este perfume'), translate it to clear, standard English.\n"
        "3. Preserve all specific scent names, notes, and brand names.\n"
        "Respond with ONLY the English translation and absolutely nothing else."
    )
    
    messages = [
        {"role": "system", "content": translation_prompt},
        {"role": "user", "content": raw_msg}
    ]
    
    translated_msg = call_sarvam_ai(messages).strip()
    
    # Check if the user explicitly requested a specific language (e.g. "in tamil", "in french")
    requested_language = None
    raw_lower = raw_msg.lower()
    if "in french" in raw_lower or "français" in raw_lower:
        requested_language = "French"
    elif "in tamil" in raw_lower or "தமிழ்" in raw_lower:
        requested_language = "Tamil"
    elif "in hindi" in raw_lower or "hindi" in raw_lower or "हिंदी" in raw_lower:
        requested_language = "Hindi"
    elif "in spanish" in raw_lower or "español" in raw_lower:
        requested_language = "Spanish"
    elif "in german" in raw_lower or "deutsch" in raw_lower:
        requested_language = "German"
    elif "in italian" in raw_lower or "italiano" in raw_lower:
        requested_language = "Italian"
        
    return {
        "user_message": translated_msg,
        "requested_language": requested_language
    }

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
        "# Role & Tone\n"
        "You are an incredibly enthusiastic, passionate, and happy AI Scent Advisor. Engage in a luxury sales conversation. "
        "Your tone must be vibrant, welcoming, and highly persuasive—implicitly steering the customer to feel excited and ready to make a purchase.\n\n"
        "# Core Guidelines\n"
        "- Be elegant, passionate, concise, and helpful.\n"
        "- Keep answers extremely short, delightful, and highly positive (strictly maximum 2-3 sentences total). Do NOT write long essays, descriptions of note combinations, or fragrance layering explanations.\n"
        "- NEVER suggest offline actions like store visits. This is purely a digital scent fragrance matcher.\n"
        "- NEVER use Markdown formatting symbols like asterisks (**) or hashes (###).\n"
        "- If the user's input is completely unrelated to fragrances, decline politely.\n\n"
        "# Preference Refinement Question\n"
        "- Ask exactly ONE relevant clarifying question in simple English to build and refine the user's note profile.\n"
        "- The purpose of your question is to help the user discover and add complementary notes or accords to their preference (e.g., if they selected floral notes, suggest adding fresh citrus, warm vanilla, or earthy woody notes to complement them).\n"
        "- Never conclude the conversation or say you are ready to find a bottle; always ask how to expand or refine their note list.\n\n"
        "# Suggestion Buttons Formatting\n"
        "- At the very end of your response, after your clarifying question is fully complete, provide EXACTLY 2 or 3 complementary suggestion options/accords (absolutely never more than 3, and never fewer than 2) formatted in square brackets.\n"
        "- These options MUST be extremely common, simple, and universally recognizable scent notes or ingredients in simple English (such as Vanilla, Musk, Sandalwood, Rose, Jasmine, Coconut, Lemon, Mint, Lavender, or Orange) that average consumers easily know. If the user query is about a category (like seasons or occasions), suggest 2 or 3 representative scent styles/accords (e.g., [Crisp Citrus] [Warm Sandalwood] [Cozy Amber]). Do not list categories directly if they exceed 3 options.\n"
        "- Do NOT suggest complicated, niche, or obscure ingredients (like Jasmine Sambac, Petitgrain, Oud, Bergamot, Neroli, or Tonka Bean).\n"
        "- The options must totally relate to the question.\n"
        "- Do NOT write any words, conjunctions, or punctuation between, before, or after the square brackets.\n"
        "- Standard format to copy: 'Would you like to add some fresh citrus brightness or warm woody depth to your rose and jasmine? [Fresh Lemon & Lime] [Warm Sandalwood & Amber]'\n\n"
        "# Language Rule\n"
        "- Analyze the user's LATEST message (the last message in the conversation).\n"
        "- If the user's LATEST message is written in a language other than English, or explicitly asks for the response to be in a specific language (such as Hindi, Tamil, French, Spanish, etc.), or is written in conversational transliterated slang (e.g. 'indha perfume pathi sollu'), you MUST generate your entire final reply in that native language or script. Otherwise, you MUST reply in English.\n"
        "- CRITICAL: If the previous turns were in a foreign language, but the user's LATEST message is in English and does not explicitly ask for a translation, you MUST switch back to English immediately. Do NOT continue in the foreign language unless explicitly asked.\n"
        "- Preserve all bullet point styling ('●') and blank line spacing in all languages.\n\n"
        "# Critical Execution Limit\n"
        "- REASONING LIMIT: Keep your internal thinking/reasoning extremely brief (under 1 sentence).\n"
        "- Do NOT repeat your thoughts, checks, or revisions.\n"
        "- **ANTI-LOOP RULE**: Do NOT repeat any sentence, question, or word sequence within your response. Every sentence in your reply must be completely unique. Do NOT loop.\n"
        "- Generate the final response immediately. If you detect any repetition in your output, stop immediately and emit your final response with exactly 2 or 3 bracketed options."
    )
    
    messages = [{"role": "system", "content": convo_system_prompt}]
    for msg in (state.get("messages") or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    user_msg = state.get("user_message") or ""
    messages.append({"role": "user", "content": user_msg})
    messages.append({"role": "system", "content": get_language_instruction(user_msg, state.get("requested_language"))})
    
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
        "You are a structural engine. Analyze the conversation history and extract the user's fragrance preferences.\n"
        "Identify:\n"
        "1. Gender: 'for women', 'for men', or 'for women and men'. Identify this strictly from the user's explicit gender requests and target recipients.\n"
        "   - Treat typos like 'fermine', 'fragance', or 'cologne' as general perfume terms (do not confuse them with 'feminine' if a male recipient is specified).\n"
        "   - Correctly map gendered relationship terms: 'dad', 'father', 'husband', 'brother', 'son', 'boy', 'guy', 'men', 'man' must classify as 'for men'.\n"
        "   - 'mom', 'mother', 'wife', 'sister', 'daughter', 'girl', 'women', 'woman' must classify as 'for women'.\n"
        "   - Once established, do not change it unless the user explicitly asks for a different gender. Do not let assistant messages override this selection.\n"
        "2. Accords: Extract ALL scent notes, accords, ingredients, and vibes that the user explicitly requested, selected, or wanted to include in their perfume preference across the entire conversation. Return them as a flat list. CRITICAL: Do NOT extract notes that were only mentioned as part of Q&A questions or informational requests (e.g., if the user asked 'whats vetiver' or 'what is oud', do NOT extract 'vetiver' or 'oud' unless they explicitly requested to add it to their preference). Correct spelling typos (e.g. 'carmel' -> 'caramel', 'cardomom' -> 'cardamom', 'jasmin' -> 'jasmine', 'bergamont' -> 'bergamot').\n"
        "3. Refined notes: Scent notes the user explicitly asked to ADD or focus on in their LATEST message. If none, return []. Correct spelling typos.\n"
        "4. Brand: Specific perfume brand EXPLICITLY requested by the user to filter their search (e.g. 'show me Chanel perfumes', 'Bvlgari brand'). Do NOT extract a brand name if it was only mentioned in a recommended perfume name, assistant pitch, or in a question about a specific perfume (e.g. 'what makes Patchouli Indulgence Avon good'). If no brand filter is explicitly requested by the user to filter their search, return null.\n"
        "5. Disliked: Perfume names the user explicitly rejected or dislikes. If none, return [].\n"
        "6. Sort: true if user wants 'best', 'highest rated', 'top rated', or 'most popular'. Otherwise, false.\n"
        "Respond with ONLY a JSON block: {\"gender\": \"for women\"|\"for men\"|\"for women and men\", \"accords\": [\"tag1\", \"tag2\"], \"refined_notes\": [\"note1\"], \"brand\": \"brand_name\"|null, \"disliked\": [\"name1\"], \"sort_by_best\": true|false}. No code blocks, markdown tags, or explanations."
    )
    
    messages = [
        {"role": "system", "content": extraction_prompt},
        {"role": "user", "content": dialog_transcript}
    ]
    
    extracted_raw = call_sarvam_ai(messages, max_tokens=4000)
    
    import re
    try:
        clean_json_str = extracted_raw.strip() if extracted_raw else ""
        json_match = re.search(r'\{.*\}', clean_json_str, re.DOTALL) if clean_json_str else None
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
    
    existing_accords = state.get("accords_list") or []
    merged_accords = list(set([a.lower().strip() for a in existing_accords if isinstance(a, str)] + [a.lower().strip() for a in accords_list if isinstance(a, str)]))
    
    existing_refined = state.get("refined_notes") or []
    merged_refined = list(set([r.lower().strip() for r in existing_refined if isinstance(r, str)] + [r.lower().strip() for r in refined_notes if isinstance(r, str)]))
        
    return {
        "gender_filter": gender_filter,
        "accords_list": merged_accords,
        "refined_notes": merged_refined,
        "brand_filter": brand_filter,
        "disliked_perfumes": merged_disliked,
        "sort_by_best": sort_by_best
    }

def query_database_node(state: AgentState) -> Dict[str, Any]:
    """Queries MongoDB collection using accords list, brand filter, and disliked exclusion, sorting by best if specified."""
    import re
    db = get_mongo_db()
    gender_filter = state.get("gender_filter", "for women and men")
    accords_list = state.get("accords_list", [])
    refined_notes = state.get("refined_notes", [])
    brand_filter = state.get("brand_filter")
    disliked_perfumes = state.get("disliked_perfumes") or []
    sort_by_best = state.get("sort_by_best", False)
    
    def map_accords(terms):
        expanded = set()
        for t in terms:
            if not isinstance(t, str):
                continue
            t_low = t.lower().strip()
            expanded.add(t_low)
            words = [w.strip() for w in t_low.replace("&", " ").replace(",", " ").replace("/", " ").split() if w.strip()]
            for w in words:
                expanded.add(w)
            if "tea" in t_low or "green" in t_low:
                expanded.add("green")
                expanded.add("aromatic")
            if "musk" in t_low:
                expanded.add("musky")
                expanded.add("musk")
            if "sandalwood" in t_low or "cedar" in t_low or "wood" in t_low:
                expanded.add("woody")
            if "vanilla" in t_low or "tonka" in t_low:
                expanded.add("vanilla")
                expanded.add("sweet")
            if "jasmine" in t_low or "neroli" in t_low or "white floral" in t_low:
                expanded.add("white floral")
                expanded.add("floral")
            if "rose" in t_low:
                expanded.add("rose")
                expanded.add("floral")
            if "citrus" in t_low or "lemon" in t_low or "bergamot" in t_low or "mandarin" in t_low or "lime" in t_low:
                expanded.add("citrus")
            if "amber" in t_low:
                expanded.add("amber")
            if "spicy" in t_low or "cardamom" in t_low or "ginger" in t_low:
                expanded.add("fresh spicy")
                expanded.add("warm spicy")
            if "fruity" in t_low or "fig" in t_low or "pomegranate" in t_low or "raspberry" in t_low:
                expanded.add("fruity")
            if "ocean" in t_low or "sea" in t_low or "marine" in t_low or "aquatic" in t_low or "salt" in t_low or "mist" in t_low:
                expanded.add("marine")
                expanded.add("aquatic")
                expanded.add("fresh")
            if "sunshine" in t_low or "sun" in t_low or "summer" in t_low or "beach" in t_low:
                expanded.add("citrus")
                expanded.add("tropical")
                expanded.add("sweet")
        return list(expanded)
    
    gender_q = None
    if gender_filter == "for women":
        gender_q = {"$in": ["for women", "for women and men"]}
    elif gender_filter == "for men":
        gender_q = {"$in": ["for men", "for women and men"]}
    else:
        gender_q = "for women and men"
        
    query = {}
    if gender_q:
        query["gender"] = gender_q
        
    if brand_filter and isinstance(brand_filter, str):
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
    
    expanded_search_terms = map_accords(combined_search_terms)
    
    if expanded_search_terms:
        escaped_terms = [re.escape(t) for t in expanded_search_terms]
        match_query = [
            {"main_accords": {"$in": expanded_search_terms}},
            {"description": {"$regex": "|".join(escaped_terms), "$options": "i"}}
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
    if len(candidates) < 10 and expanded_search_terms:
        fallback_query = {}
        if gender_q:
            fallback_query["gender"] = gender_q
        if brand_filter and isinstance(brand_filter, str):
            fallback_query["name"] = {"$regex": brand_filter, "$options": "i"}
        if disliked_perfumes:
            disliked_regex = "|".join([f"^{d}$" for d in disliked_perfumes if d.strip()])
            if disliked_regex:
                fallback_query["name"] = fallback_query.get("name", {})
                if isinstance(fallback_query["name"], dict):
                    fallback_query["name"]["$not"] = {"$regex": disliked_regex, "$options": "i"}
                else:
                    fallback_query["name"] = {"$not": {"$regex": disliked_regex, "$options": "i"}}
        fallback_query["main_accords"] = {"$in": expanded_search_terms}
        
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
        if brand_filter and isinstance(brand_filter, str):
            gender_query["name"] = {"$regex": brand_filter, "$options": "i"}
        if disliked_perfumes:
            disliked_regex = "|".join([f"^{d}$" for d in disliked_perfumes if d.strip()])
            if disliked_regex:
                gender_query["name"] = gender_query.get("name", {})
                if isinstance(gender_query["name"], dict):
                    gender_query["name"]["$not"] = {"$regex": disliked_regex, "$options": "i"}
                else:
                    gender_query["name"] = {"$not": {"$regex": disliked_regex, "$options": "i"}}
            
        # Always sort fallback by rating_value and rating_count descending
        cursor = db["fragrances"].find(gender_query).sort([("rating_value", -1), ("rating_count", -1)]).limit(100)
            
        for doc in cursor:
            if doc["_id"] not in [c["_id"] for c in candidates]:
                candidates.append(doc)
                
    # Fallback 3: Return anything matching gender_q
    if len(candidates) < 10:
        anything_query = {}
        if gender_q:
            anything_query["gender"] = gender_q
        if brand_filter and isinstance(brand_filter, str):
            anything_query["name"] = {"$regex": brand_filter, "$options": "i"}
        if disliked_perfumes:
            disliked_regex = "|".join([f"^{d}$" for d in disliked_perfumes if d.strip()])
            if disliked_regex:
                anything_query["name"] = anything_query.get("name", {})
                if isinstance(anything_query["name"], dict):
                    anything_query["name"]["$not"] = {"$regex": disliked_regex, "$options": "i"}
                else:
                    anything_query["name"] = {"$not": {"$regex": disliked_regex, "$options": "i"}}
                    
        # Always sort fallback by rating_value and rating_count descending
        cursor = db["fragrances"].find(anything_query).sort([("rating_value", -1), ("rating_count", -1)]).limit(100)
            
        for doc in cursor:
            if doc["_id"] not in [c["_id"] for c in candidates]:
                candidates.append(doc)
                
    # Multi-turn choices alignment extraction
    messages = state.get("messages") or []
    user_choices = []
    for msg in messages:
        content = msg.get("content", "")
        if msg.get("role") == "user" and not is_greeting(content):
            user_choices.append(content)
            
    choice_groups = []
    for choice in user_choices + [state.get("user_message") or ""]:
        choice_low = choice.lower().strip()
        if is_greeting(choice_low) or "office" in choice_low or "party" in choice_low or "night" in choice_low or "signature" in choice_low:
            continue
        mapped_choice_accords = map_accords([choice])
        if mapped_choice_accords:
            choice_groups.append(mapped_choice_accords)
            
    # Score and strictly filter Candidates by gender and note intersection relevance
    scored_candidates = []
    for perf in candidates:
        perf_gender = (perf.get("gender") or "").lower().strip()
        if gender_filter == "for women" and perf_gender == "for men":
            continue
        if gender_filter == "for men" and perf_gender == "for women":
            continue
            
        score = 0
        accords = [a.lower().strip() for a in (perf.get("main_accords") or []) if isinstance(a, str)]
        description = (perf.get("description") or "").lower()
        
        # 1. Base matches (All turns combined)
        for term in expanded_search_terms:
            if term in accords:
                score += 30
            if term in description:
                score += 5
            
        # 2. Latest Note Match (Primary Boost)
        for term in map_accords(refined_terms):
            if term in accords:
                score += 1000
            if term in description:
                score += 500
                
        # 3. Decayed Historical Alignment
        # choice_groups is chronologically ordered: oldest first, newest last.
        for i, group in enumerate(reversed(choice_groups)):
            group_matched = False
            for term in group:
                if term in accords or term in description:
                    group_matched = True
                    break
            if group_matched:
                if i == 0:
                    score += 800  # Latest turn matches get the highest weight
                elif i == 1:
                    score += 200  # Previous turn matches get moderate weight
                else:
                    score += 50   # Older turns get minimal weight
                    
        # 4. Rating & Popularity (Tie-Breaker)
        rating = perf.get("rating_value", 0.0)
        score += rating * 10
            
        scored_candidates.append((score, perf))
        
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Always slice from the sorted list to prioritize high relevance matches
    sorted_candidates_flat = [item[1] for item in scored_candidates]
    matched_perfumes = sorted_candidates_flat[:3]
    other_perfumes = sorted_candidates_flat[3:6]
    
    # Convert ObjectIds to string for JSON serialization
    import hashlib
    
    def get_catchy_one_liner(perf, index_offset=0):
        accs = [a.lower().strip() for a in perf.get("main_accords", []) if isinstance(a, str)]
        gender = perf.get("gender", "").lower()
        gender_word = "anyone"
        if "women" in gender and "men" in gender:
            gender_word = "anyone"
        elif "women" in gender or "woman" in gender:
            gender_word = "women"
        elif "men" in gender or "man" in gender:
            gender_word = "men"
            
        adjective_map = {
            "vanilla": "creamy vanilla warmth",
            "rose": "velvety rose romance",
            "citrus": "zesty citrus brightness",
            "woody": "earthy woody depth",
            "musk": "sensual musky undertones",
            "jasmine": "exotic jasmine allure",
            "spicy": "bold fiery spices",
            "fresh": "crisp aquatic freshness",
            "amber": "rich golden amber",
            "patchouli": "mysterious patchouli richness",
            "fruity": "succulent sun-kissed fruits",
            "floral": "luxurious blooming florals",
            "green": "refreshing leafy green notes",
            "aromatic": "soothing aromatic herbs",
            "sweet": "delightfully sweet nectar",
            "powdery": "soft powdery whispers",
            "cocoa": "rich dark chocolate",
            "caramel": "warm buttery caramel",
            "coconut": "sun-drenched coconut sweetness",
            "lavender": "soothing lavender fields",
            "mint": "refreshing cool mint",
            "leather": "bold rich leather",
            "oud": "mysterious smoky oud",
            "white floral": "luminous white florals",
            "warm spicy": "cozy warm spices",
            "fresh spicy": "invigorating fresh spices",
            "balsamic": "warm balsamic depth",
            "herbal": "earthy herbal freshness",
            "aquatic": "breezy aquatic notes"
        }
        
        mapped_phrases = []
        for a in accs:
            if a in adjective_map:
                mapped_phrases.append(adjective_map[a])
            if len(mapped_phrases) == 2:
                break
                
        if len(mapped_phrases) == 0:
            if accs:
                top_accs = accs[:2]
                accs_str = ", ".join(top_accs[:-1]) + f" and {top_accs[-1]}" if len(top_accs) > 1 else top_accs[0]
                mapped_phrases = [f"inviting {accs_str} notes"]
            else:
                mapped_phrases = ["exquisite signature notes"]
                
        h_idx = int(hashlib.md5(perf["name"].encode("utf-8")).hexdigest(), 16)
        
        if len(mapped_phrases) == 2:
            phrase1, phrase2 = mapped_phrases[0], mapped_phrases[1]
            patterns = [
                f"A masterfully crafted signature that seamlessly blends {phrase1} with {phrase2} for {gender_word}.",
                f"Experience a captivating journey as {phrase1} dissolves into the rich depth of {phrase2}.",
                f"A luxurious statement bottle pairing {phrase1} with {phrase2} to make you feel unforgettable.",
                f"Crafted for {gender_word}, this unique scent wraps you in {phrase1} and {phrase2}.",
                f"A brilliant, sophisticated blend showcasing the harmony of {phrase1} and {phrase2}.",
                f"Elevate your presence with the majestic fusion of {phrase1} and {phrase2}.",
                f"Designed to leave a memorable trail, this fragrance balances {phrase1} with {phrase2}.",
                f"A modern classic that showcases the sophisticated interplay of {phrase1} and {phrase2}.",
                f"Experience the vibrant energy of {phrase1} seamlessly married to {phrase2}.",
                f"An unforgettable signature scent highlighting {phrase1} over a base of {phrase2}."
            ]
            return patterns[(h_idx + index_offset) % len(patterns)]
        else:
            phrase1 = mapped_phrases[0]
            patterns = [
                f"An absolute masterpiece defined by the elegant complexity of {phrase1}.",
                f"Let the signature warmth of {phrase1} elevate your unique presence.",
                f"Designed for {gender_word}, this sophisticated bottle highlights premium {phrase1}.",
                f"Experience the captivating simplicity of refined {phrase1}.",
                f"A beautiful and classic statement centered around {phrase1}."
            ]
            return patterns[(h_idx + index_offset) % len(patterns)]

    serialized_primary = []
    for idx, p in enumerate(matched_perfumes):
        serialized_primary.append({
            "name": p["name"],
            "rating": p.get("rating_value", 0.0),
            "description": get_catchy_one_liner(p, idx),
            "accords": p.get("main_accords", [])
        })
        
    serialized_secondary = []
    for idx, p in enumerate(other_perfumes):
        serialized_secondary.append({
            "name": p["name"],
            "rating": p.get("rating_value", 0.0),
            "description": get_catchy_one_liner(p, idx + 3),
            "accords": p.get("main_accords", [])
        })
        
    return {
        "recommended_perfumes": serialized_primary,
        "other_perfumes": serialized_secondary
    }

def generate_pitch_node(state: AgentState) -> Dict[str, Any]:
    """Generates sales pitches for primary (Ranks 1-3) perfumes."""
    recommended = state.get("recommended_perfumes", [])
    
    allowed_names = [p["name"] for p in recommended]
    
    primary_catalog = ""
    for index, p in enumerate(recommended):
        primary_catalog += f"Primary Option {index+1}: Name: {p['name']}, Description: {p['description']}\n"
        
    catalog_context = f"PRIMARY CHOICES (Ranks 1-3):\n{primary_catalog}"
    
    sales_system_prompt = (
        f"# Role & Objective\n"
        f"You are the ultimate luxury AI Scent Advisor. Recommend matching perfumes with extreme enthusiasm, passion, and persuasive sales flair to convince the customer to purchase immediately. Highlight their irresistible, glamorous qualities.\n\n"
        f"# Database Context\n"
        f"PRIMARY CHOICES:\n{catalog_context}\n\n"
        f"# Core Guidelines\n\n"
        f"## 1. Language Rules\n"
        f"- Respond in the language requested by the state instructions.\n"
        f"- Default to English if no override is requested.\n\n"
        f"## 2. Conversation Constraints\n"
        f"- Do NOT invite the user to store appointments, private viewings, or offline/in-person services.\n"
        f"- Do NOT mention, pitch, or reference perfumes from previous turns of the chat history. Focus strictly on the current Primary Choices.\n\n"
        f"## 3. Formatting Restrictions\n"
        f"- Do NOT use markdown bolding (**) or headings (###).\n"
        f"- FORBIDDEN: Do NOT use square brackets anywhere in the response text (e.g., do not write [Name] or [Note]). Doing so breaks the UI.\n\n"
        f"## 4. Response Structure & Layout\n"
        f"Choose the layout format based on the user's latest request:\n"
        f"- **Case A: Explicit Comparison Request** (if they ask to compare/contrast notes): Write a detailed, luxurious comparison analysis of the Primary Choices. Format with paragraphs separated by double newlines.\n"
        f"- **Case B: Specific Data Question** (e.g., asking for rating values): Answer their question accurately using the database context. Format with paragraphs separated by double newlines.\n"
        f"- **Case C: Note Specifications / Scent Preferences / Default Pitch**:\n"
        f"  - Start response with exactly: \"Here is a little about your perfumes:\" followed by a double newline.\n"
        f"  - Generate exactly 3 separate paragraphs (one for each of the Primary Choices in their exact order: {', '.join(allowed_names)}).\n"
        f"  - Format each paragraph as: `EXACT_PERFUME_NAME: Scent pitch explanation`\n"
        f"  - Keep the exact name casing from the context (do not use all caps, do not omit any words).\n"
        f"  - Limit each pitch explanation strictly to a maximum of 2 lines of text (approx 20-30 words).\n"
        f"  - Append a brief sentence suggesting that the user can ask to explore more options or refine search parameters.\n"
        f"  - CRITICAL: You are strictly FORBIDDEN from writing any extra paragraphs, top recommendations, concluding summaries, or sentences below the 3 pitched perfumes. The response MUST end immediately after the 3rd perfume's pitch or the exploration suggestion sentence. Do NOT mention why one is a top recommendation.\n\n"
        f"# Execution Limits\n"
        f"- REASONING LIMIT: Your internal thinking must be extremely brief (under 1 sentence).\n"
        f"- Do NOT repeat your thoughts, revisions, checks, or formatting evaluations.\n"
        f"- ANTI-LOOP RULE: Every sentence in your thoughts and final output must be completely unique. If you detect any repetition, immediately stop thinking and print the final response."
    )
    
    messages = [{"role": "system", "content": sales_system_prompt}]
    for msg in state.get("messages", []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    user_msg = state.get("user_message") or ""
    messages.append({"role": "user", "content": user_msg})
    messages.append({"role": "system", "content": get_language_instruction(user_msg, state.get("requested_language"))})
    
    pitch = call_sarvam_ai(messages)
    
    if not pitch or not isinstance(pitch, str) or any(err in pitch for err in ["Error", "Failed", "null", "exhausted"]):
        # Graceful fallback database descriptions to prevent 502 Bad Gateway
        # Format with double newlines so the frontend splits them into clean separate bubbles
        primary_paragraphs = ["Here is a little about your perfumes:"]
        for p in recommended:
            desc_text = p.get('description', '')
            if len(desc_text) > 150:
                desc_text = desc_text[:147] + "..."
            primary_paragraphs.append(f"{p['name']}: {desc_text}")
        
        pitch = "\n\n".join(primary_paragraphs)
            
    return {"bot_reply": pitch}

def qa_node(state: AgentState) -> Dict[str, Any]:
    """Handles general scent questions, application questions, note details, or follow-ups regarding recommended perfumes."""
    recommended = state.get("recommended_perfumes", [])
    other = state.get("other_perfumes", [])
    user_msg = state.get("user_message", "")
    
    # 1. Fetch related perfumes from the DB to support general RAG queries (e.g. asking about notes/brands)
    db = get_mongo_db()
    import re
    stop_words = {"what", "is", "a", "the", "who", "which", "would", "how", "do", "you", "me", "this", "these", "it", "with", "for", "and", "or", "in", "of", "about", "detail", "reason", "explain", "why", "can", "have", "has", "does"}
    query_words = [w.strip("?,.!:;\"'") for w in user_msg.lower().split() if len(w.strip("?,.!:;\"'")) > 2 and w.strip("?,.!:;\"'") not in stop_words]
    
    general_db_context = ""
    if query_words:
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
                related_docs = list(db["fragrances"].find(db_query).limit(3))
                if related_docs:
                    general_db_context = "Matching Perfumes from our collection:\n"
                    for r in related_docs:
                        general_db_context += f"- {r['name']}: {r.get('description', '')[:250]}... (Accords: {', '.join(r.get('main_accords', []))})\n"
            except Exception:
                pass

    # 2. Format previously recommended perfumes for context
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
        "# Role & Tone\n"
        "You are the ultimate luxury AI Scent Advisor. Answer the user's fragrance-related questions accurately, elegantly, and with extreme professionalism and enthusiasm.\n\n"
        "# Confidence Rules\n"
        "- CRITICAL CONFIDENCE RULE: The user is looking at the recommended perfumes in the right-side panel from the very first turn. You are FORBIDDEN from stating, implying, or apologizing that you 'did not recommend' or 'did not suggest' a perfume. Even if this is the first time the perfume is mentioned in the chat text, you MUST take 100% ownership and act as if you explicitly recommended/suggested it. If the user asks why you recommended or suggested it, immediately start explaining its notes and benefits.\n"
        "- Refer to the CRITICAL CONFIDENCE RULE at the top. You MUST confidently explain why the perfume is perfect for them without ever denying the recommendation.\n\n"
        "# Context Data\n"
        "- Previously Recommended Perfumes:\n"
        f"{perfumes_str}\n"
        "- General Scent Database (for note/application queries):\n"
        f"{general_db_context or 'No specific perfumes match this query in our database.'}\n\n"
        "# Question Answering & Bullet Points Structure\n"
        "- Present your response strictly using a solid circle symbol '●' (do not use asterisks '*' or hyphens '-') for bullet points.\n"
        "- You MUST add a blank line between each bullet point to keep the response clean, well-spaced, and easy to read.\n"
        "- Keep each bullet point short, punchy, and visually appealing (maximum 1-2 sentences) so it never feels lengthy or overwhelming.\n"
        "- **Rule for Multiple Perfumes**: If you are describing or comparing multiple perfumes, each bullet point must start with its name (e.g., '● **PERFUME_NAME** - description').\n"
        "- **Rule for a Single Perfume**: If you are explaining a single specific perfume (e.g., answering why it was recommended or detailing its notes), you MUST generate multiple distinct bullet points explaining different aspects of that perfume (e.g., its notes, its vibe, its alignment to preferences) where each bullet point starts with a bold topic heading (e.g., '● **Scent Accords**: ...', '● **Occasion Fit**: ...').\n"
        "- **Rule for General Questions**: For all general scent advice, note explanations (like woody, citrus), or application tips (not about specific perfumes), you MUST also present your response strictly as a neat list of bullet points starting with '●' where each point starts with a bold topic heading (e.g., '● **Scent Profile**: ...', '● **Application Tips**: ...').\n\n"
        "# Formatting Restrictions\n"
        "- You MUST use double asterisks to bold important keywords, scent notes, or perfume names (e.g. **Little Black Dress**, **fresh citrus**).\n"
        "- Do NOT use hashes (###) or other markdown layout styles.\n"
        "- Do NOT suggest or include any complementary notes, accords, or options in square brackets (e.g., [Note1] [Note2]) when you are answering questions about previously recommended perfumes or explaining why a perfume was recommended.\n"
        "- Do NOT invite the user to private viewings or offline appointments.\n\n"
        "# Language Rule\n"
        "- Analyze the user's LATEST message (the last message in the conversation).\n"
        "- If the user's LATEST message is written in a language other than English, or explicitly asks for the response to be in a specific language (such as Hindi, Tamil, French, Spanish, etc.), or is written in conversational transliterated slang (e.g. 'indha perfume pathi sollu'), you MUST generate your entire final reply in that native language or script. Otherwise, you MUST reply in English.\n"
        "- CRITICAL: If the previous turns were in a foreign language, but the user's LATEST message is in English and does not explicitly ask for a translation, you MUST switch back to English immediately. Do NOT continue in the foreign language unless explicitly asked.\n"
        "- Preserve all bullet point styling ('●') and blank line spacing in all languages.\n\n"
        "# Execution Limits\n"
        "- REASONING LIMIT: Keep your internal thinking/reasoning extremely brief (under 1 sentence).\n"
        "- Do NOT repeat your thoughts, checks, or revisions.\n"
        "- Do NOT loop.\n"
        "- Generate the final response immediately."
    )
    
    messages = [{"role": "system", "content": qa_system_prompt}]
    for msg in state.get("messages", []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    user_msg = state.get("user_message") or ""
    messages.append({"role": "user", "content": user_msg})
    messages.append({"role": "system", "content": get_language_instruction(user_msg, state.get("requested_language"))})
    
    reply = call_sarvam_ai(messages)
    if not reply or not isinstance(reply, str) or any(err in reply for err in ["Error", "Failed", "null", "exhausted"]):
        reply = "I'd be glad to help answer your question, but I'm currently having a network connection issue. Could you please try again in a moment?"
        
    return {"bot_reply": reply}
 
 
def database_qa_node(state: AgentState) -> Dict[str, Any]:
    """Generates a MongoDB query based on the user's question, runs it, and answers the question using the retrieved data."""
    user_msg = state.get("user_message", "")
    recommended = state.get("recommended_perfumes") or []
    other = state.get("other_perfumes") or []
    all_recs = recommended + other

    # If the user is asking why we recommended these or to compare them, and we have active recommendations,
    # bypass the query generation and explain directly using the recommended perfumes in the state.
    is_why_recommend = any(x in user_msg.lower() for x in ["why did you recommend", "why recommend", "reason for", "why did you suggest", "why suggest", "why these", "about these", "notes of these", "in these"])
    is_compare = any(x in user_msg.lower() for x in ["compare", "difference", "differ", "distinguish", "rank"])
    if all_recs and (is_why_recommend or is_compare):
        context = ""
        for r in all_recs:
            context += (
                f"Name: {r['name']}\n"
                f"Rating: {r.get('rating_value', 0.0) or r.get('rating', 0.0)}\n"
                f"Accords: {', '.join(r.get('main_accords') or r.get('accords') or [])}\n"
                f"Description: {r.get('description', '')}\n\n"
            )
        
        answer_prompt = (
            "You are the ultimate luxury AI Scent Advisor. Answer the user's question accurately and elegantly based on the provided database context.\n"
            "CRITICAL CONFIDENCE RULE: The user is looking at the recommended perfumes in the right-side panel from the very first turn. You are FORBIDDEN from stating, implying, or apologizing that you 'did not recommend' or 'did not suggest' a perfume. Even if this is the first time the perfume is mentioned in the chat text, you MUST take 100% ownership and act as if you explicitly recommended/suggested it. If the user asks why you recommended or suggested it, immediately start explaining its notes and benefits.\n"
            "The user is asking about the recommended perfumes currently shown in the right-side panel.\n"
            f"Database Context:\n{context}\n\n"
            "Guidelines:\n"
            "1. LANGUAGE RULE: Analyze the user's LATEST message (the last message in the conversation). If the user's LATEST message is written in a language other than English, or explicitly asks for the response to be in a specific language (such as Hindi or Tamil), you MUST generate your entire final reply in the native script of that requested language. Otherwise, you MUST reply in English. CRITICAL: If the previous turns were in a foreign language (like Hindi), but the user's LATEST message is in English and does not explicitly ask for a translation, you MUST switch back to English immediately. Do NOT continue the conversation in Hindi, Tamil, or any other foreign language unless explicitly asked in the latest message. Preserve all formatting (like '●' bullet points and blank lines exactly).\n"
            "2. Be extremely enthusiastic, welcoming, and professional.\n"
            "3. Answer the user's question completely and accurately using the context. You MUST explicitly name the perfumes you are referring to.\n"
            "4. Present your answer strictly using a solid circle symbol '●' (not asterisks '*' or hyphens '-') for bullet points. If you are describing multiple perfumes, each bullet point must start with its name (e.g., '● **PERFUME_NAME** - description'). However, if you are explaining a single specific perfume (e.g., answering why it was recommended or detailing its notes), you MUST generate multiple distinct bullet points explaining different aspects of that perfume (e.g., its notes, its vibe, its alignment to preferences) where each bullet point starts with a bold topic heading (e.g., '● **Scent Accords**: ...', '● **Occasion Fit**: ...'). Keep each bullet point short, punchy, and visually appealing (max 1-2 sentences) so it never feels lengthy. You MUST add a blank line between each bullet point to keep the response clean, well-spaced, and easy to read.\n"
            "5. You MUST use double asterisks to bold important keywords, scent notes, or perfume names (e.g. **Little Black Dress**, **fresh citrus**). Do NOT use hashes (###) or other markdown formatting.\n"
            "6. Do NOT suggest or include any complementary notes, accords, or options in square brackets under any circumstances.\n"
            "7. Do NOT use square brackets anywhere in your text.\n"
            "8. REASONING LIMIT: Keep your internal thinking/reasoning extremely brief (under 1 sentence). Do NOT repeat your thoughts, checks, or revisions. Do NOT loop. Generate the final response immediately."
        )
        
        messages = [{"role": "system", "content": answer_prompt}]
        for msg in state.get("messages", []):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "system", "content": get_language_instruction(user_msg, state.get("requested_language"))})
        
        reply = call_sarvam_ai(messages)
        if not reply or not isinstance(reply, str) or any(err in reply for err in ["Error", "Failed", "null", "exhausted"]):
            reply = "I'd be glad to help answer your question, but I'm currently having a network connection issue. Could you please try again in a moment?"
            
        return {"bot_reply": reply}

    # 1. Broad substring name matching to intercept and generate query directly (saves LLM call completely)
    matched_names = []
    import re
    user_msg_clean = re.sub(r'[^a-zA-Z0-9\s]', '', user_msg.lower())
    for p in all_recs:
        name = p.get("name", "")
        clean_name = name.lower()
        for suffix in ["for women and men", "for women", "for men", "avon", "britney spears", "spears", "bdk parfums", "hugo boss", "boss"]:
            clean_name = clean_name.replace(suffix, "")
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', clean_name).strip()
        if len(clean_name) > 3 and clean_name in user_msg_clean:
            matched_names.append(name)

    query = {}
    if matched_names:
        # Construct an $or query for matched name regexes
        regex_patterns = []
        for name in matched_names:
            # Strip suffixes to make it broad
            core_name = name.lower()
            for suffix in ["for women and men", "for women", "for men"]:
                core_name = core_name.replace(suffix, "")
            core_name = core_name.strip()
            # Escape words and join with .*
            words = [re.escape(w) for w in core_name.split() if w.strip()]
            if words:
                regex_patterns.append({"name": {"$regex": ".*".join(words), "$options": "i"}})
        if len(regex_patterns) == 1:
            query = regex_patterns[0]
        elif len(regex_patterns) > 1:
            query = {"$or": regex_patterns}

    # If direct extraction didn't yield a query, call LLM to generate it with small max_tokens
    if not query:
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
            "- For comparisons or lookups involving multiple perfumes, you MUST construct an '$or' array matching each perfume name individually using case-insensitive regex, e.g., {\"$or\": [{\"name\": {\"$regex\": \"Wanted Azzaro\", \"$options\": \"i\"}}, {\"name\": {\"$regex\": \"Wanted Freeride\", \"$options\": \"i\"}}]}\n"
            "- IMPORTANT: Database perfume names contain squished brand and gender suffixes (e.g. 'Avonfor women', 'Spearsfor women', 'Azzarofor men'). When searching by name, keep the regex search query broad by omitting the brand/gender suffixes (e.g. search for 'Hidden Fantasy' or 'Hidden Fantasy.*Spears' instead of the full name 'Hidden Fantasy Britney Spears for women') to prevent lookup failures due to spacing differences.\n"
            "- If the user explicitly asks for exclusion or negation (e.g. 'without vanilla', 'excluding rose', 'no musk'), use MongoDB negation operators like '$nin' or '$not' with regex, e.g. {\"main_accords\": {\"$nin\": [\"vanilla\"]}} or {\"description\": {\"$not\": {\"$regex\": \"rose\", \"$options\": \"i\"}}}\n"
            "- Return ONLY the JSON query filter block and absolutely nothing else. Do not wrap in markdown code blocks."
        )
        
        messages = [{"role": "system", "content": query_prompt}]
        query_raw = call_sarvam_ai(messages, max_tokens=150)
        
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
        
    if not records:
        if not recommended and any(w in user_msg.lower() for w in ["recommend", "these", "option", "suggest"]):
            reply = (
                "We haven't selected any specific perfume bottles for you yet! "
                "The options you see below (like Fresh Mint & Citrus) are complementary scent profiles to help us narrow down what notes you like. "
                "Once you tell me which profile you prefer or suggest some notes, I will query our database and recommend specific perfume bottles for you."
            )
            return {"bot_reply": reply}
            
        reply = (
            f"I couldn't find any perfumes matching '{user_msg}' in our database. "
            "However, I would be delighted to search for fragrances featuring these notes for you! "
            "Please let me know if you would like me to add them to your scent profile."
        )
        return {"bot_reply": reply}
        
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
        "CRITICAL CONFIDENCE RULE: The user is looking at the recommended perfumes in the right-side panel from the very first turn. You are FORBIDDEN from stating, implying, or apologizing that you 'did not recommend' or 'did not suggest' a perfume. Even if this is the first time the perfume is mentioned in the chat text, you MUST take 100% ownership and act as if you explicitly recommended/suggested it. If the user asks why you recommended or suggested it, immediately start explaining its notes and benefits.\n"
        f"Database Context:\n{context or 'No matching perfumes found in the database.'}\n\n"
        "Guidelines:\n"
        "1. LANGUAGE RULE: Analyze the user's LATEST message (the last message in the conversation). If the user's LATEST message is written in a language other than English, or explicitly asks for the response to be in a specific language (such as Hindi or Tamil), you MUST generate your entire final reply in the native script of that requested language. Otherwise, you MUST reply in English. CRITICAL: If the previous turns were in a foreign language (like Hindi), but the user's LATEST message is in English and does not explicitly ask for a translation, you MUST switch back to English immediately. Do NOT continue the conversation in Hindi, Tamil, or any other foreign language unless explicitly asked in the latest message. Preserve all formatting (like '●' bullet points and blank lines exactly).\n"
        "2. Be extremely enthusiastic, welcoming, and professional.\n"
        "3. CONFIDENCE RULE: Refer to the CRITICAL CONFIDENCE RULE at the top. You MUST confidently explain why the perfume is perfect for them without ever denying the recommendation.\n"
        "4. Answer the user's question completely and accurately using the context. You MUST explicitly name the perfumes you are referring to. Do not make up facts not present in the context.\n"
        "5. CRITICAL SPECIFICITY RULE: If the user's question is about a specific perfume (or a specific subset of perfumes), you MUST focus your explanation and bullet points ONLY on that specific perfume (or subset), and completely ignore/omit any information or bullet points about the other perfumes.\n"
        "6. Present your answer strictly using a solid circle symbol '●' (not asterisks '*' or hyphens '-') for bullet points. If you are describing multiple perfumes, each bullet point must start with its name (e.g., '● **PERFUME_NAME** - description'). However, if you are explaining a single specific perfume (e.g., answering why it was recommended or detailing its notes), you MUST generate multiple distinct bullet points explaining different aspects of that perfume (e.g., its notes, its vibe, its alignment to preferences) where each bullet point starts with a bold topic heading (e.g., '● **Scent Accords**: ...', '● **Occasion Fit**: ...'). Keep each bullet point short, punchy, and visually appealing (max 1-2 sentences) so it never feels lengthy. You MUST add a blank line between each bullet point to keep the response clean, well-spaced, and easy to read.\n"
        "7. You MUST use double asterisks to bold important keywords, scent notes, or perfume names (e.g. **Little Black Dress**, **fresh citrus**). Do NOT use hashes (###) or other markdown formatting.\n"
        "8. Do NOT suggest or include any complementary notes, accords, or options in square brackets (e.g., [Note1] [Note2]) under any circumstances.\n"
        "9. REASONING LIMIT: Keep your internal thinking/reasoning extremely brief (under 1 sentence). Do NOT repeat your thoughts, checks, or revisions. Do NOT loop. Generate the final response immediately."
    )
    
    messages = [{"role": "system", "content": answer_prompt}]
    for msg in state.get("messages", []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_msg})
    messages.append({"role": "system", "content": get_language_instruction(user_msg)})
    
    reply = call_sarvam_ai(messages)
    if not reply or not isinstance(reply, str) or any(err in reply for err in ["Error", "Failed", "null", "exhausted"]):
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



def post_query_router(state: AgentState) -> str:
    """Routes to generate_pitch if we have met conversational turns threshold, otherwise routes to clarifying chat."""
    search_turns = 0
    for msg in state.get("messages", []):
        if msg.get("role") == "user":
            content = msg.get("content", "").lower()
            if is_greeting(content):
                continue
            is_qa = any(x in content for x in ["why did you recommend", "why recommend", "compare", "what makes", "what is", "difference", "how long"])
            if not is_qa:
                search_turns += 1
                
    current_msg = (state.get("user_message") or "").lower()
    if not is_greeting(current_msg):
        is_qa = any(x in current_msg for x in ["why did you recommend", "why recommend", "compare", "what makes", "what is", "difference", "how long"])
        if not is_qa:
            search_turns += 1
            
    if search_turns >= 3:
        return "pitch"
    return "chat"


# 5. Build and Compile the LangGraph state machine
builder = StateGraph(AgentState)

# Register the nodes
builder.add_node("translate_input", translate_input_node)
builder.add_node("decline", decline_node)
builder.add_node("chat", clarifying_chat_node)
builder.add_node("extract_intent", extract_intent_node)
builder.add_node("db_query", query_database_node)
builder.add_node("generate_pitch", generate_pitch_node)
builder.add_node("qa", qa_node)
builder.add_node("database_qa", database_qa_node)
builder.add_node("new_search", new_search_node)

# Set starting node to run translator first
builder.set_entry_point("translate_input")

# Route conditionally out of translate_input using the router_edge logic
builder.add_conditional_edges(
    "translate_input",
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
builder.add_conditional_edges(
    "db_query",
    post_query_router,
    {
        "pitch": "generate_pitch",
        "chat": "chat"
    }
)
builder.add_edge("new_search", "chat")

# Set endpoints
builder.add_edge("decline", END)
builder.add_edge("chat", END)
builder.add_edge("qa", END)
builder.add_edge("database_qa", END)
builder.add_edge("generate_pitch", END)

# Compile the compiled executable graph
scent_advisor_graph = builder.compile()
