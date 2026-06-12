from django.urls import path
from .views import IngestDataView, ChatbotView

urlpatterns = [
    path('ingest/', IngestDataView.as_view(), name='ingest_data'),
    path('chat/', ChatbotView.as_view(), name='chat_handler'),
]