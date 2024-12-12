from django.shortcuts import render
from django.views.generic import TemplateView, ListView

from main.models import Services


class Index(TemplateView):
    template_name = 'main/index.html'

class ServicesList(ListView):
    model = Services

    def get_queryset(self):
        return Services.objects.raw('''
            SELECT
                s.id,
                s.title,
                s.description,
                s.price,
                s.category_id,
                c.name AS category_name
            FROM main_services s
            INNER JOIN main_servicecategories c ON s.category_id = c.id
            ORDER BY c.name, s.title;
        ''')