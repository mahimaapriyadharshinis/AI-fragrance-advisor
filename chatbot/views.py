import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .utils import get_mongo_db, import_csv_to_mongodb, call_sarvam_ai

# Administrative endpoint to trigger MongoDB ingestion
class IngestDataView(APIView):
    def post(self, request):
        result = import_csv_to_mongodb()
        if result["status"] == "success":
            return Response({"message": f"Successfully loaded {result['count']} fragrances into MongoDB."}, status=status.HTTP_200_OK)
        return Response({"error": result["message"]}, status=status.HTTP_400_BAD_REQUEST)

# Core Conversational Recommendation Endpoint
class ChatbotView(APIView):
    def post(self, request):
        user_message = request.data.get("message", "")
        chat_history = request.data.get("history", []) # Expected: [{"role": "user"|"assistant", "content": "..."}]
        
        if not user_message:
            return Response({"error": "Message body is empty"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Count user inputs safely to cap conversations at 3 turns to respect client time
        user_turns = 0
        if isinstance(chat_history, list):
            for msg in chat_history:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_turns += 1
        
        # System instructions guiding standard interaction
        convo_system_prompt = (
            "You are an incredibly enthusiastic, passionate, and happy AI Scent Advisor. Engage in a luxury sales conversation. "
            "Your tone must be vibrant, welcoming, and highly persuasive—implicitly steering the customer to feel excited and ready to make a purchase. "
            "Follow these conversational guidelines strictly:\n"
            "1. Be elegant, passionate, concise, and helpful.\n"
            "2. Keep answers short, delightful, and highly positive (max 3 sentences per reply). Show genuine excitement to find their perfect match.\n"
            "3. Ask exactly ONE relevant clarifying question to refine their preference. At the very end of your response, after your clarifying question is fully complete, provide 2 to 3 highly creative and related suggestion options formatted in square brackets (e.g., [Option A] [Option B]). The options should NOT be a simple repeat of words inside your question, but should be distinct, appealing scent vibes, styles, or preferences related to the question context to give the user more paths (e.g., if asking about settings like casual vs formal, suggest: [Sophisticated office vibe] [Charming evening gala]; or if asking about scent notes, suggest appealing scent combinations). Do NOT write any words, conjunctions (like 'or'), or punctuation between, before, or after the square brackets. Example format: 'Would you prefer something light and floral, or rich and deep? [Light and floral] [Rich and deep]'\n"
            "4. NEVER suggest offline actions like scheduling private viewings, store visits, or custom appointments. This is purely a digital scent fragrance matcher.\n"
            "5. NEVER use Markdown formatting symbols like asterisks (**), hashes (###), or dashes (---).\n"
            "6. If the user's input is completely unrelated to perfumes, fragrances, scent matching, smells, or body care (such as general knowledge questions like 'what is google' or 'what is a chocolate'), you MUST decline politely. Respond with: 'I am an AI Scent Advisor dedicated exclusively to helping you find your perfect fragrance, so I cannot answer unrelated questions. Let me know what kind of scent or vibe you are looking for!'"
        )

        db = get_mongo_db()
        
        # Turn limits control: if they've answered 2 questions already (this is the 3rd user turn), we deliver recommendations!
        if user_turns >= 2:
            # --- STAGE 1: INTENT EXTRACTION VIA SARVAM ---
            # Construct dialog string to parse intent
            dialog_transcript = ""
            for item in chat_history:
                dialog_transcript += f"{item['role'].upper()}: {item['content']}\n"
            dialog_transcript += f"USER: {user_message}\n"

            extraction_prompt = (
                "You are a structural engine. You MUST carefully analyze the entire conversation history transcript and extract the user's fragrance preferences.\n"
                "Analyze all user messages and choices made throughout the conversation.\n"
                "Identify:\n"
                "1. The target gender: 'for women', 'for men', or 'for women and men'.\n"
                "2. Scent accords: Extract ALL scent notes, ingredients, accords, and vibe keywords mentioned or selected by the user across the ENTIRE conversation (such as vanilla, cedarwood, rose, vetiver, ginger, sweet, floral, woody, fresh, office, warm, etc.). Do not miss any notes from previous turns. Return them as a flat list of strings.\n"
                "Respond with ONLY a JSON block: {\"gender\": \"for women\"|\"for men\"|\"for women and men\", \"accords\": [\"tag1\", \"tag2\"]}. No code blocks or explanations."
            )
            
            messages = [
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": dialog_transcript}
            ]
            
            extracted_raw = call_sarvam_ai(messages)
            
            try:
                # Strip out any potential block decoration (e.g. ```json )
                clean_json_str = extracted_raw.strip()
                if "```" in clean_json_str:
                    clean_json_str = clean_json_str.split("```")[1]
                    if clean_json_str.startswith("json"):
                        clean_json_str = clean_json_str[4:]
                filters = json.loads(clean_json_str.strip())
                gender_filter = filters.get("gender", "for women and men")
                accords_list = filters.get("accords", [])
            except Exception:
                gender_filter = "for women and men"
                accords_list = []

            # --- STAGE 2: DATABASE MATCHING ---
            query = {}
            if gender_filter and gender_filter != "for women and men":
                query["gender"] = gender_filter
            
            # Match based on scent notes (accords) or dialogue description keywords
            # Find document matches where accords intersect or match details
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
            
            if search_terms:
                query["$or"] = [
                    {"main_accords": {"$in": search_terms}},
                    {"description": {"$regex": "|".join(search_terms), "$options": "i"}}
                ]
                
            # Fetch candidate products matching the criteria (up to 200)
            candidates = list(db["fragrances"].find(query).limit(200))
            
            # Fallback 1: Try finding perfumes matching accords only (no description regex)
            if len(candidates) < 10 and search_terms:
                fallback_query = {}
                if gender_filter and gender_filter != "for women and men":
                    fallback_query["gender"] = gender_filter
                fallback_query["main_accords"] = {"$in": search_terms}
                
                cursor = db["fragrances"].find(fallback_query).limit(100)
                for doc in cursor:
                    if doc["_id"] not in [c["_id"] for c in candidates]:
                        candidates.append(doc)
            
            # Fallback 2: Search for description regex without main_accords, or filter by gender only
            if len(candidates) < 10:
                gender_query = {}
                if gender_filter and gender_filter != "for women and men":
                    gender_query["gender"] = gender_filter
                
                cursor = db["fragrances"].find(gender_query).limit(100)
                for doc in cursor:
                    if doc["_id"] not in [c["_id"] for c in candidates]:
                        candidates.append(doc)
            
            # Fallback 3: If still under 10, just grab anything from the collection
            if len(candidates) < 10:
                cursor = db["fragrances"].find({}).limit(100)
                for doc in cursor:
                    if doc["_id"] not in [c["_id"] for c in candidates]:
                        candidates.append(doc)

            # --- STAGE 2.5: RELEVANCE SCORING & RANKING ---
            scored_candidates = []
            for perf in candidates:
                score = 0
                accords = [a.lower().strip() for a in perf.get("main_accords", []) if isinstance(a, str)]
                description = perf.get("description", "").lower()
                
                for term in search_terms:
                    # 20 points for each matching accord
                    if term in accords:
                        score += 20
                    # 2 points for every occurrence of the keyword in the description
                    score += description.count(term) * 2
                
                scored_candidates.append((score, perf))
            
            # Sort by score descending to get the best matches first
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            matched_perfumes = [item[1] for item in scored_candidates[:3]]
            other_perfumes = [item[1] for item in scored_candidates[3:6]]
            other_names = [perf['name'] for perf in other_perfumes]
            other_names_str = ", ".join(other_names) if other_names else "other options in our collection"
            
            # --- STAGE 3: CONVERSATIONAL CONVERSION PITCH GENERATION ---
            primary_catalog = ""
            for index, perf in enumerate(matched_perfumes):
                primary_catalog += f"Primary Option {index+1}: Name: {perf['name']}, Accords: {perf['main_accords']}, Description: {perf['description']}\n"
                
            secondary_catalog = ""
            for index, perf in enumerate(other_perfumes):
                secondary_catalog += f"Secondary Option {index+4}: Name: {perf['name']}, Accords: {perf['main_accords']}, Description: {perf['description']}\n"

            catalog_context = f"PRIMARY CHOICES (Ranks 1-3):\n{primary_catalog}\nSECONDARY CHOICES (Ranks 4-6):\n{secondary_catalog}"
            
            serialized_products = []
            allowed_names = []
            for perf in matched_perfumes:
                allowed_names.append(perf['name'])
                serialized_products.append({
                    "name": perf["name"],
                    "rating": perf["rating_value"],
                    "description": perf["description"]
                })

            sales_system_prompt = (
                f"You are the ultimate luxury AI Scent Advisor. Recommend these matching perfumes with extreme enthusiasm, passion, and persuasive sales flair to convince the customer to purchase immediately. Highlight the irresistible, glamorous qualities of each scent, making them sound absolutely essential, luxurious, and perfect for the customer's desires.\n"
                f"Scent Catalog Database Context:\n{catalog_context}\n"
                f"Guidelines:\n"
                f"1. If the user's request is completely unrelated to perfumes, fragrances, scent matching, smells, or body care (such as general knowledge questions like 'what is google' or 'what is a chocolate'), you MUST decline politely. Respond ONLY with: 'I am an AI Scent Advisor dedicated exclusively to helping you find your perfect fragrance, so I cannot answer unrelated questions. Let me know what kind of scent or vibe you are looking for!' and do NOT list or mention the catalog perfumes.\n"
                f"2. Write your response in exactly TWO parts, separated by the exact word '[NEXT_MESSAGE]' on a new line.\n"
                f"3. PART 1 (before '[NEXT_MESSAGE]'): Pitch exactly the 3 Primary Option perfumes: {', '.join(allowed_names)}. For each of these 3 perfumes, write a separate, distinct paragraph (1 to 2 highly persuasive sentences) explaining why it is absolutely perfect for the customer. Do NOT mix them into a single paragraph.\n"
                f"4. PART 2 (after '[NEXT_MESSAGE]'): Introduce the 3 Secondary Option perfumes: {', '.join(other_names)}. Write a highly enthusiastic, manipulative follow-up sales pitch explaining why they should also consider buying these 3 alternative suggestions. Write a separate, distinct paragraph (1 to 2 highly persuasive sentences) for each of these 3 alternative perfumes.\n"
                f"5. Keep all paragraphs short, elegant, extremely persuasive, and highly appealing. Make sure your response is fully complete and does not cut off mid-sentence.\n"
                f"6. Do NOT invite the user to private viewings, store appointments, or offline services.\n"
                f"7. Do NOT use markdown symbols like asterisks (**) or hashes (###).\n"
                f"8. Suggest that the user can ask to explore more options or refine their search parameters if they wish."
            )

            rec_messages = [
                {"role": "system", "content": sales_system_prompt},
                {"role": "user", "content": f"Please write the enthusiastic sales pitches for the matching perfumes based on the customer's request history:\n{dialog_transcript}"}
            ]
            
            final_recommendation_pitch = call_sarvam_ai(rec_messages)
            if not final_recommendation_pitch:
                final_recommendation_pitch = "Connection Failed: No response received from external advisor API."
                
            if "Error from Sarvam API" in final_recommendation_pitch or "Connection Failed" in final_recommendation_pitch:
                # Fallback to database descriptions directly to guarantee 200 OK and prevent 502 Gateway errors
                fallback_reply = "I have curated these three exquisite fragrances that match your preferences perfectly:\n\n"
                for index, perf in enumerate(matched_perfumes):
                    fallback_reply += f"{perf['name']}\n{perf['description']}\n\n"
                
                fallback_reply += "[NEXT_MESSAGE]\nYou should also explore these three captivating alternative selections with similar notes:\n\n"
                for index, perf in enumerate(other_perfumes):
                    fallback_reply += f"{perf['name']}\n{perf['description']}\n\n"
                
                return Response({
                    "bot_reply": fallback_reply,
                    "recommended_products": serialized_products
                }, status=status.HTTP_200_OK)

            # If the advisor declined the request, do not return any recommended products so the side panel stays hidden
            if "I am an AI Scent Advisor" in final_recommendation_pitch:
                serialized_products = []

            return Response({
                "bot_reply": final_recommendation_pitch,
                "recommended_products": serialized_products
            }, status=status.HTTP_200_OK)

        else:
            # Under 2 questions: generate next interactive conversation turn
            messages = [{"role": "system", "content": convo_system_prompt}]
            for msg in chat_history:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            messages.append({"role": "user", "content": user_message})
            
            bot_reply = call_sarvam_ai(messages)
            if not bot_reply:
                bot_reply = "Connection Failed: No response received from external advisor API."
                
            if "Error from Sarvam API" in bot_reply or "Connection Failed" in bot_reply:
                # Friendly fallback conversational question to keep UI functional and prevent 502s
                fallback_bot_reply = (
                    "I am currently experiencing a minor connection hiccup with our olfactory advisor network, "
                    "but I'd still love to help you find your signature scent! "
                    "Could you share if you generally prefer fresh and citrusy notes, or deeper woody notes? [Fresh & citrusy] [Deeper woody]"
                )
                return Response({
                    "bot_reply": fallback_bot_reply,
                    "recommended_products": []
                }, status=status.HTTP_200_OK)
            
            return Response({
                "bot_reply": bot_reply,
                "recommended_products": []
            }, status=status.HTTP_200_OK)