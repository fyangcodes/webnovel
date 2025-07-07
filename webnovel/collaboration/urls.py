from django.urls import path
from . import views

app_name = 'collaboration'

urlpatterns = [
    # Translation assignments
    path('translation-assignments/', views.TranslationAssignmentListView.as_view(), name='translation_assignments'),
    path('translation-assignments/<int:pk>/', views.TranslationAssignmentDetailView.as_view(), name='translation_assignment_detail'),
    path('translation-assignments/<int:pk>/start/', views.start_translation_assignment, name='start_translation_assignment'),
    path('translation-assignments/<int:pk>/submit/', views.submit_translation_assignment, name='submit_translation_assignment'),
    path('translation-assignments/<int:pk>/approve/', views.approve_translation_assignment, name='approve_translation_assignment'),
    path('translation-assignments/<int:pk>/reject/', views.reject_translation_assignment, name='reject_translation_assignment'),
] 