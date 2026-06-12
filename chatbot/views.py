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
            "You are a helpful and elegant AI Scent Advisor. "
            "You must engage in a high-end, friendly conversation with the user to discover their perfect scent.\n"
            "Follow these conversational guidelines strictly:\n"
            "1. Be elegant, concise, and helpful.\n"
            "2. Keep answers short and delightful (max 3 sentences per reply). Do not overwhelm the customer.\n"
            "3. Ask exactly ONE relevant clarifying question to refine their preference. "
            "At the end of your question, provide 2 to 3 suggestions formatted in square brackets that the user can choose from. "
            "For example: 'Would you prefer something light and floral, or rich and deep? [Light and floral] [Rich and deep]'\n"
            "4. NEVER suggest offline actions like scheduling private viewings, store visits, or custom appointments. This is purely a digital scent fragrance matcher."
            "5. NEVER use Markdown formatting symbols like asterisks (**), hashes (###), or dashes (---)."
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
                "You are a structural engine. Extract preferences from dialog. "
                "Respond with ONLY a JSON block: "
                "{\"gender\": \"for women\"|\"for men\"|\"for women and men\", \"accords\": [\"tag1\", \"tag2\"]}. "
                "No code blocks or explanations."
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
            if accords_list:
                # To match elements inside a list field, MongoDB queries the scalar or uses '$in' with a list of values.
                # Standard syntax is {"field": {"$in": accords_list}} where accords_list is a list of strings.
                query["main_accords"] = {"$in": [a.lower().strip() for a in accords_list]}
                
            matched_cursor = db["fragrances"].find(query).sort("rating_value", -1).limit(3)
            matched_perfumes = list(matched_cursor)
            
            # --- STAGE 3: CONVERSATIONAL CONVERSION PITCH GENERATION ---
            catalog_context = ""
            serialized_products = []
            for index, perf in enumerate(matched_perfumes):
                catalog_context += f"Option {index+1}: Name: {perf['name']}, Accords: {perf['main_accords']}, Description: {perf['description']}\n"
                serialized_products.append({
                    "name": perf["name"],
                    "rating": perf["rating_value"],
                    "description": perf["description"]
                })

            sales_system_prompt = (
                f"You are the AI Scent Advisor. Recommend these matching perfumes clearly and persuasively using the catalog:\n{catalog_context}\n"
                f"Guidelines:\n"
                f"1. You MUST limit choices exclusively to the provided dataset catalog. Do NOT hallucinate, invent, or suggest any perfume names not explicitly listed in the catalog above.\n"
                f"2. For each recommendation, state the exact Name of the perfume very clearly.\n"
                f"3. Keep the pitch short, elegant, and persuasive.\n"
                f"4. Do NOT invite the user to private viewings, store appointments, or offline services. This is strictly a digital matchmaker.\n"
                f"5. Do NOT use markdown symbols like asterisks (**) or hashes (###).\n"
                f"6. Suggest that the user can ask to explore more options or refine their search parameters if they wish."
            )

            rec_messages = [
                {"role": "system", "content": sales_system_prompt},
                {"role": "user", "content": f"Explain why the matching perfumes from the catalog fit the preferences: {accords_list}."}
            ]
            
            final_recommendation_pitch = call_sarvam_ai(rec_messages)
            if not final_recommendation_pitch:
                final_recommendation_pitch = "Connection Failed: No response received from external advisor API."
                
            if "Error from Sarvam API" in final_recommendation_pitch or "Connection Failed" in final_recommendation_pitch:
                return Response({"error": final_recommendation_pitch}, status=status.HTTP_502_BAD_GATEWAY)

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
                return Response({"error": bot_reply}, status=status.HTTP_502_BAD_GATEWAY)
            
            return Response({
                "bot_reply": bot_reply,
                "recommended_products": []
            }, status=status.HTTP_200_OK)