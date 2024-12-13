from django.db import connection
from django.db.transaction import commit
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView

from main.forms import AddServiceForm
from main.models import Services, ServiceCategories


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

class AddService(CreateView):
    form_class = AddServiceForm
    template_name = 'main/services_form.html'
    success_url = reverse_lazy('services')
    extra_context = {
        'title': 'Добавление услуги',
    }

    def form_valid(self, form):
        title = form.cleaned_data.get('title')
        description = form.cleaned_data.get('description')
        price = form.cleaned_data.get('price')

        plpgsql_function = ('''
                        CREATE OR REPLACE FUNCTION validate_service_data(
                            s_title TEXT,
                            s_description TEXT,
                            s_price NUMERIC
                        ) RETURNS TEXT AS $$
                        BEGIN
                            IF TRIM(s_title) IS NULL THEN
                                RETURN 'Title must not be empty or spaces only';
                            ELSIF TRIM(s_description) IS NULL THEN
                                RETURN 'Description must not be empty or spaces only';
                            ELSIF s_price < 0 THEN
                                RETURN 'Price must be a non-negative number';
                            END IF;
                            RETURN 'OK';
                        END;
                        $$ LANGUAGE plpgsql;
                    ''')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_function)

            validation_query = "SELECT validate_service_data(%s, %s, %s);"
            with connection.cursor() as cursor:
                cursor.execute(validation_query, [title, description, price])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        service = form.save(commit=False)
        insert_query = ("""
                INSERT INTO main_services (title, description, price, category_id)
                VALUES (%s, %s, %s, %s);
                """)
        try:
            with connection.cursor() as cursor:
                cursor.execute(insert_query, [service.title, service.description, service.price, service.category.pk])
        except Exception as e:
            form.add_error(None, f"Database insertion error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))