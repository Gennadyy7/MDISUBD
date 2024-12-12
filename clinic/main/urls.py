from django.urls import path
from . import views

urlpatterns = [
    path('', views.Index.as_view(), name='home'),
    path('services/', views.ServicesList.as_view(), name='services'),
]