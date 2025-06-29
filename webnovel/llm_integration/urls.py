from django.urls import path
from . import views

app_name = "llm_integration"

urlpatterns = [
    # Add LLM-related URLs here as they are implemented
    # Example:
    # path("translate/<int:chapter_id>/", views.translate_chapter, name="translate_chapter"),
    path('dashboard/', views.llm_dashboard, name='dashboard'),
    path('metrics/api/', views.llm_metrics_api, name='metrics_api'),
    path('service-calls/', views.llm_service_calls, name='service_calls'),
] 