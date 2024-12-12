from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Clients, Doctors, Specializations, ServiceCategories, Services, Reviews, Promocodes, Orders, \
    ClientLogs

admin.site.register(User, UserAdmin)
admin.site.register(Clients)
admin.site.register(Doctors)
admin.site.register(Specializations)
admin.site.register(ServiceCategories)
admin.site.register(Services)
admin.site.register(Reviews)
admin.site.register(Promocodes)
admin.site.register(Orders)
admin.site.register(ClientLogs)