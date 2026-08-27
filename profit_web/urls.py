from django.urls import path
from . import views

app_name = "profit_web"
urlpatterns = [path("", views.home, name="home"), path("simple/", views.simple_calculator, name="simple")]

