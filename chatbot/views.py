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

from .graph import scent_advisor_graph

# Core Conversational Recommendation Endpoint
class ChatbotView(APIView):
    def post(self, request):
        user_message = request.data.get("message", "")
        chat_history = request.data.get("history", []) # Expected: [{"role": "user"|"assistant", "content": "..."}]
        
        # Trim history to the last 8 messages to prevent token limits and incomplete replies
        if len(chat_history) > 8:
            chat_history = chat_history[-8:]
            
        recommended_perfumes = request.data.get("recommended_perfumes", [])
        other_perfumes = request.data.get("other_perfumes", [])
        brand_filter = request.data.get("brand_filter", None)
        disliked_perfumes = request.data.get("disliked_perfumes", [])
        sort_by_best = request.data.get("sort_by_best", False)
        user_turns = request.data.get("user_turns", 0)
        
        if not user_message:
            return Response({"error": "Message body is empty"}, status=status.HTTP_400_BAD_REQUEST)

        # Build initial graph state inputs
        inputs = {
            "messages": chat_history,
            "user_message": user_message,
            "user_turns": user_turns,
            "recommended_perfumes": recommended_perfumes,
            "other_perfumes": other_perfumes,
            "accords_list": [],
            "refined_notes": [],
            "gender_filter": "for women and men",
            "brand_filter": brand_filter,
            "disliked_perfumes": disliked_perfumes,
            "sort_by_best": sort_by_best,
            "bot_reply": ""
        }

        try:
            # Invoke the LangGraph compiled state graph
            outputs = scent_advisor_graph.invoke(inputs)
        except Exception as e:
            # Print traceback details to console for debugging
            import traceback
            traceback.print_exc()
            # Safe system failure fallback
            return Response({
                "bot_reply": f"I am experiencing an issue processing the scent advisor graph. Detail: {str(e)}",
                "recommended_products": [],
                "other_products": [],
                "brand_filter": None,
                "disliked_perfumes": [],
                "sort_by_best": False,
                "user_turns": 0
            }, status=status.HTTP_200_OK)

        return Response({
            "bot_reply": outputs.get("bot_reply", ""),
            "recommended_products": outputs.get("recommended_perfumes", []),
            "other_products": outputs.get("other_perfumes", []),
            "brand_filter": outputs.get("brand_filter", None),
            "disliked_perfumes": outputs.get("disliked_perfumes", []),
            "sort_by_best": outputs.get("sort_by_best", False),
            "user_turns": outputs.get("user_turns", 0)
        }, status=status.HTTP_200_OK)