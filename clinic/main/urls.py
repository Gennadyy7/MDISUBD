from django.urls import path
from . import views

urlpatterns = [
    path('', views.Index.as_view(), name='home'),

    path('services/', views.ServicesList.as_view(), name='services'),
    path('services/add/', views.AddService.as_view(), name='add_service'),
    path('services/update/<int:pk>/', views.UpdateService.as_view(), name='update_service'),
    path('services/delete/<int:pk>/', views.DeleteService.as_view(), name='delete_service'),

    path('categories/', views.CategoriesList.as_view(), name='categories'),
    path('categories/add/', views.AddCategory.as_view(), name='add_category'),
    path('categories/update/<int:pk>/', views.UpdateCategory.as_view(), name='update_category'),
    path('categories/delete/<int:pk>/', views.DeleteCategory.as_view(), name='delete_category'),
]