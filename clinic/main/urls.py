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

    path('specializations/', views.SpecializationsList.as_view(), name='specializations'),
    path('specializations/add/', views.AddSpecialization.as_view(), name='add_specialization'),
    path('specializations/update/<int:pk>/', views.UpdateSpecialization.as_view(), name='update_specialization'),
    path('specializations/delete/<int:pk>/', views.DeleteSpecialization.as_view(), name='delete_specialization'),

    path('doctors/', views.DoctorsList.as_view(), name='doctors'),
    path('doctors/add/user/', views.AddUserForDoctor.as_view(), name='add_user_for_doctor'),
    path('doctors/add/doctor/', views.AddDoctor.as_view(), name='add_doctor'),
    path('doctors/update/<int:pk>/', views.UpdateDoctor.as_view(), name='update_doctor'),
    path('doctors/delete/<int:pk>/', views.DeleteDoctor.as_view(), name='delete_doctor'),

    path('promocodes/', views.PromocodesList.as_view(), name='promocodes'),
    path('promocodes/add/', views.AddPromocode.as_view(), name='add_promocode'),
    path('promocodes/delete/<int:pk>/', views.DeletePromocode.as_view(), name='delete_promocode'),

    path('login/', views.LoginUser.as_view(), name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register/', views.RegisterUser.as_view(), name='register'),

    path('client_logs/', views.ClientLogsList.as_view(), name='client_logs'),

    path('reviews/', views.ReviewsList.as_view(), name='reviews'),
    path('reviews/add/', views.AddReview.as_view(), name='add_review'),
    path('reviews/delete/<int:pk>/', views.DeleteReview.as_view(), name='delete_review'),

    path('orders/', views.OrdersList.as_view(), name='orders'),
]