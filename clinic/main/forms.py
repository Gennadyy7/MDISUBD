from django import forms

from main.models import Services, ServiceCategories, Specializations, User, Doctors, Promocodes


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
            'phone': forms.TextInput(attrs={'placeholder': '+375 (XX) XXX-XX-XX'})
        }

class AddDoctorForm(forms.ModelForm):
    class Meta:
        model = Doctors
        fields = '__all__'
        widgets = {
            'office_phone': forms.TextInput(attrs={'placeholder': '80XX XXX-XX-XX'})
        }

class AddPromocodeForm(forms.ModelForm):
    class Meta:
        model = Promocodes
        fields = ['code', 'discount', 'expiration_date']
        labels = {
            'discount': 'Discount, %',
        }
        widgets = {
            'expiration_date': forms.DateInput(format='%d-%m-%Y', attrs={'type': 'date'}),
        }