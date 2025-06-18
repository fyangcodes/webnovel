from django.urls import path
from . import views

app_name = "translations"

urlpatterns = [
    path("", views.TranslationDashboardView.as_view(), name="dashboard"),
    path(
        "chapter/<int:pk>/",
        views.ChapterTranslationView.as_view(),
        name="translate_chapter",
    ),
    path(
        "chapter/<int:chapter_id>/save/<str:language>/",
        views.save_translation,
        name="save_translation",
    ),
    path("history/<int:translation_id>/", views.translation_history, name="history"),
    path("compare/<int:history_id>/", views.compare_versions, name="compare_versions"),
]
