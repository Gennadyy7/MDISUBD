from django import forms

from main.models import Services, ServiceCategories, Specializations, User, Doctors, Promocodes, Reviews, Orders


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

class AddUserForClientForm(forms.ModelForm):
    birth_date = forms.DateField(
        required=True,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
    )
    address = forms.CharField(
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder': 'ул. Иваново, д. 111/11, кв. 11',})
    )
    class Meta:
        model = User
        fields = ['username', 'password', 'first_name', 'last_name', 'patronymic', 'email', 'phone', 'birth_date', 'address']
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

class AddReviewForm(forms.ModelForm):
    class Meta:
        model = Reviews
        fields = ['doctor', 'rating', 'text']

class AddOrderForm(forms.ModelForm):
    class Meta:
        model = Orders
        fields = ['doctor', 'services', 'promocode']
        labels = {
            'services': 'Services'
        }

    def clean_services(self):
        services = self.cleaned_data.get('services')
        doctor = self.cleaned_data.get('doctor')
        doctor_specialization = doctor.specialization.service_category
        if services:
            service_categories = {service.category for service in services}
            if len(service_categories) > 1:
                raise forms.ValidationError("All services must belong to the same category.")
            if doctor_specialization not in service_categories:
                raise forms.ValidationError("All services must match the doctor's specialization category.")
        return services