from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path("auth/register/",            views.register_view,        name="register"),
    path("auth/login/",               views.login_view,           name="login"),
    path("auth/logout/",              views.logout_view,          name="logout"),
    path("auth/me/",                  views.me_view,              name="me"),
    path("auth/token/refresh/",       TokenRefreshView.as_view(), name="token_refresh"),

    # Research
    path("research/",                 views.create_research,      name="create_research"),
    path("research/list/",            views.list_research,        name="list_research"),
    path("research/<int:pk>/",        views.research_detail,      name="research_detail"),
    path("research/<int:pk>/stream/", views.stream_research,      name="stream_research"),
]
