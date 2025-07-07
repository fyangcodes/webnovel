"""
URL configuration for webnovel project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Admin interface
    path("admin/", admin.site.urls),
    # Custom accounts app URLs (includes authentication)
    path("accounts/", include("accounts.urls", namespace="accounts")),
    # App URLs
    path("", RedirectView.as_view(url="/books/", permanent=False)),
    path("books/", include("books.urls", namespace="books")),
    path("collaboration/", include("collaboration.urls", namespace="collaboration")),
    path("llm/", include("llm_integration.urls", namespace="llm_integration")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
