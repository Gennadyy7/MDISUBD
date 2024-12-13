from django import forms

from main.models import Services, ServiceCategories


class AddServiceForm(forms.ModelForm):
    class Meta:
        model = Services
        fields = ['title', 'description', 'price', 'category']

class AddCategoryForm(forms.ModelForm):
    class Meta:
        model = ServiceCategories
        fields = ['name', 'specialization']