from django import forms

from main.models import Services, ServiceCategories, Specializations, User, Doctors


class AddServiceForm(forms.ModelForm):
    class Meta:
        model = Services
        fields = ['title', 'description', 'price', 'category']

class AddCategoryForm(forms.ModelForm):
    class Meta:
        model = ServiceCategories
        fields = ['name', 'specialization']

class AddSpecializationForm(forms.ModelForm):
    class Meta:
        model = Specializations
        fields = ['name', 'description']

class AddUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'password', 'first_name', 'last_name', 'patronymic', 'email', 'phone']
        widgets = {
            'password': forms.PasswordInput(),
        }

class AddDoctorForm(forms.ModelForm):
    class Meta:
        model = Doctors
        fields = '__all__'