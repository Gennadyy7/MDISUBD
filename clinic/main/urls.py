from django.urls import path
from . import views

urlpatterns = [
    path('', views.Index.as_view(), name='home'),
    path('services/', views.ServicesList.as_view(), name='services'),
    path('services/add/', views.AddService.as_view(), name='add_service'),
    path('services/update/<int:pk>/', views.UpdateService.as_view(), name='update_service'),
]