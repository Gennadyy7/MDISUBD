from django.db import connection
from django.db.transaction import commit
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView

from main.forms import AddServiceForm, AddCategoryForm, AddSpecializationForm, AddUserForm, AddDoctorForm, \
    AddPromocodeForm
from main.models import Services, ServiceCategories, Specializations, Doctors, Promocodes

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
validation_query = "SELECT validate_service_data(%s, %s, %s);"
insert_query = ("""
                INSERT INTO main_services (title, description, price, category_id)
                VALUES (%s, %s, %s, %s);
                """)
update_query = ("""
                UPDATE main_services
                SET title = %s, description = %s, price = %s, category_id = %s
                WHERE id = %s;
                """)
insert_category_query = ("""
                INSERT INTO main_servicecategories (name, specialization_id)
                VALUES (%s, %s);
                """)
update_category_query = ("""
                UPDATE main_servicecategories
                SET name = %s, specialization_id = %s
                WHERE id = %s;
                """)
insert_specialization_query = ("""
                INSERT INTO main_specializations (name, description)
                VALUES (%s, %s);
                """)
update_specialization_query = ("""
                UPDATE main_specializations
                SET name = %s, description = %s
                WHERE id = %s;
                """)
plpgsql_user_validation = (r'''
                        CREATE OR REPLACE FUNCTION validate_user_data(
                            u_email TEXT,
                            u_phone TEXT
                        ) RETURNS TEXT AS $$
                        BEGIN
                            IF NOT (u_email ~ '^[A-Za-z0-9_]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}$') THEN
                                RETURN 'Invalid email format';
                            END IF;
                            
                            IF NOT (u_phone ~ '^\+375 \(\d{2}\) \d{3}-\d{2}-\d{2}$') THEN
                                RETURN 'Invalid phone format';
                            END IF;
                            
                            RETURN 'OK';
                        END;
                        $$ LANGUAGE plpgsql;
                        ''')
user_validation_query = "SELECT validate_user_data(%s, %s);"
plpgsql_doctor_validation = (r'''
                        CREATE OR REPLACE FUNCTION validate_doctor_data(
                            d_office_phone TEXT
                        ) RETURNS TEXT AS $$
                        BEGIN
                            IF NOT (d_office_phone ~ '^80\d{2} \d{3}-\d{2}-\d{2}$') THEN
                                RETURN 'Invalid office_phone format';
                            END IF;

                            RETURN 'OK';
                        END;
                        $$ LANGUAGE plpgsql;
                        ''')
doctor_validation_query = "SELECT validate_doctor_data(%s);"
plpgsql_promocode_validation = ('''
                        CREATE OR REPLACE FUNCTION validate_promocode_data(
                            pr_discount INTEGER,
                            pr_expiration_date DATE
                        ) RETURNS TEXT AS $$
                        BEGIN
                            IF pr_discount < 1 OR pr_discount > 100 THEN
                                RETURN 'Discount must be between 1% and 100%';
                            END IF;
                            
                            IF pr_expiration_date <= CURRENT_DATE THEN
                                RETURN 'Expiration date must be at least one day in the future';
                            END IF;

                            RETURN 'OK';
                        END;
                        $$ LANGUAGE plpgsql;
                        ''')
promocode_validation_query = "SELECT validate_promocode_data(%s, %s);"
insert_promocode_query = ("""
                INSERT INTO main_promocodes (code, discount, expiration_date, created_at)
                VALUES (%s, %s, %s, NOW());
                """)

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

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_function)

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
        try:
            with connection.cursor() as cursor:
                cursor.execute(insert_query, [service.title, service.description, service.price, service.category.pk])
        except Exception as e:
            form.add_error(None, f"Database insertion error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class UpdateService(UpdateView):
    model = Services
    form_class = AddServiceForm
    template_name = 'main/services_form.html'
    success_url = reverse_lazy('services')
    extra_context = {
        'title': 'Редактирование услуги',
    }

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = Services.objects.raw('''
                        SELECT
                            s.id,
                            s.title,
                            s.description,
                            s.price,
                            s.category_id
                        FROM main_services s
                        WHERE s.id = %s;
                    ''', [pk])
            service = next(iter(raw_object), None)
            if not service:
                raise Http404('Объект service не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для update: {e}')
        return service

    def form_valid(self, form):
        title = form.cleaned_data.get('title')
        description = form.cleaned_data.get('description')
        price = form.cleaned_data.get('price')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_function)

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
        try:
            with connection.cursor() as cursor:
                cursor.execute(update_query, [
                    service.title, service.description, service.price, service.category.pk, service.pk
                ])
        except Exception as e:
            form.add_error(None, f"Database update error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class DeleteService(DeleteView):
    model = Services
    success_url = reverse_lazy('services')

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = Services.objects.raw('''
                        SELECT
                            s.id,
                            s.title,
                            s.description,
                            s.price,
                            s.category_id
                        FROM main_services s
                        WHERE s.id = %s;
                    ''', [pk])
            service = next(iter(raw_object), None)
            if not service:
                raise Http404('Объект service не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для delete: {e}')
        return service

    def get(self, request, *args, **kwargs):
        service = self.get_object()
        service_id = service.pk
        delete_query = '''DELETE FROM main_services WHERE id = %s'''

        try:
            with connection.cursor() as cursor:
                cursor.execute(delete_query, [service_id])
        except Exception as e:
            return Http404(f'Database delete error: {e}')

        return HttpResponseRedirect(str(self.success_url))

class CategoriesList(ListView):
    model = ServiceCategories

    def get_queryset(self):
        ss = ServiceCategories.objects.raw('''
            SELECT
                sc.id,
                sc.name,
                sp.name AS specialization_name
            FROM main_servicecategories sc
            INNER JOIN main_specializations sp ON sc.specialization_id = sp.id
            ORDER BY sc.name;
        ''')
        return ss

class AddCategory(CreateView):
    form_class = AddCategoryForm
    template_name = 'main/categories_form.html'
    success_url = reverse_lazy('categories')
    extra_context = {
        'title': 'Добавление категории',
    }

    def form_valid(self, form):
        category = form.save(commit=False)
        try:
            with connection.cursor() as cursor:
                cursor.execute(insert_category_query, [category.name, category.specialization.pk])
        except Exception as e:
            form.add_error(None, f"Database insertion error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class UpdateCategory(UpdateView):
    model = ServiceCategories
    form_class = AddCategoryForm
    template_name = 'main/categories_form.html'
    success_url = reverse_lazy('categories')
    extra_context = {
        'title': 'Редактирование категории',
    }

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = ServiceCategories.objects.raw('''
                        SELECT
                            sc.id,
                            sc.name,
                            sc.specialization_id
                        FROM main_servicecategories sc
                        WHERE sc.id = %s;
                    ''', [pk])
            category = next(iter(raw_object), None)
            if not category:
                raise Http404('Объект category не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для update: {e}')
        return category

    def form_valid(self, form):
        category = form.save(commit=False)
        try:
            with connection.cursor() as cursor:
                cursor.execute(update_category_query, [category.name, category.specialization.pk, category.pk])
        except Exception as e:
            form.add_error(None, f"Database update error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class DeleteCategory(DeleteView):
    model = ServiceCategories
    success_url = reverse_lazy('categories')

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = ServiceCategories.objects.raw('''
                        SELECT
                            sc.id,
                            sc.name,
                            sc.specialization_id
                        FROM main_servicecategories sc
                        WHERE sc.id = %s;
                    ''', [pk])
            category = next(iter(raw_object), None)
            if not category:
                raise Http404('Объект category не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для delete: {e}')
        return category

    def get(self, request, *args, **kwargs):
        category = self.get_object()
        category_id = category.pk
        delete_query = '''DELETE FROM main_servicecategories WHERE id = %s'''

        try:
            with connection.cursor() as cursor:
                cursor.execute(delete_query, [category_id])
        except Exception as e:
            return Http404(f'Database delete error: {e}')

        return HttpResponseRedirect(str(self.success_url))

class SpecializationsList(ListView):
    model = Specializations

    def get_queryset(self):
        return Specializations.objects.raw('''
            SELECT
                sp.id,
                sp.name,
                sp.description
            FROM main_specializations sp
            ORDER BY sp.name;
        ''')

class AddSpecialization(CreateView):
    form_class = AddSpecializationForm
    template_name = 'main/specializations_form.html'
    success_url = reverse_lazy('specializations')
    extra_context = {
        'title': 'Добавление специализации',
    }

    def form_valid(self, form):
        specialization = form.save(commit=False)
        try:
            with connection.cursor() as cursor:
                cursor.execute(insert_specialization_query, [specialization.name, specialization.description])
        except Exception as e:
            form.add_error(None, f"Database insertion error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class UpdateSpecialization(UpdateView):
    model = Specializations
    form_class = AddSpecializationForm
    template_name = 'main/specializations_form.html'
    success_url = reverse_lazy('specializations')
    extra_context = {
        'title': 'Редактирование специализации',
    }

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = Specializations.objects.raw('''
                        SELECT
                            sp.id,
                            sp.name,
                            sp.description
                        FROM main_specializations sp
                        WHERE sp.id = %s;
                    ''', [pk])
            specialization = next(iter(raw_object), None)
            if not specialization:
                raise Http404('Объект specialization не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для update: {e}')
        return specialization

    def form_valid(self, form):
        specialization = form.save(commit=False)
        try:
            with connection.cursor() as cursor:
                cursor.execute(update_specialization_query, [specialization.name, specialization.description, specialization.pk])
        except Exception as e:
            form.add_error(None, f"Database update error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class DeleteSpecialization(DeleteView):
    model = Specializations
    success_url = reverse_lazy('specializations')

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = Specializations.objects.raw('''
                        SELECT
                            sp.id,
                            sp.name,
                            sp.description
                        FROM main_specializations sp
                        WHERE sp.id = %s;
                    ''', [pk])
            specialization = next(iter(raw_object), None)
            if not specialization:
                raise Http404('Объект specialization не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для delete: {e}')
        return specialization

    def get(self, request, *args, **kwargs):
        specialization = self.get_object()
        specialization_id = specialization.pk
        # delete_related_query = '''DELETE FROM main_servicecategories WHERE specialization_id = %s'''
        delete_query = '''DELETE FROM main_specializations WHERE id = %s'''

        try:
            with connection.cursor() as cursor:
                # cursor.execute(delete_related_query, [specialization_id])
                cursor.execute(delete_query, [specialization_id])
        except Exception as e:
            return Http404(f'Database delete error: {e}')

        return HttpResponseRedirect(str(self.success_url))

class DoctorsList(ListView):
    model = Doctors

class AddUserForDoctor(CreateView):
    form_class = AddUserForm
    template_name = 'main/users_form.html'
    success_url = reverse_lazy('doctors')
    extra_context = {
        'title': 'Добавление пользователя',
    }

    def form_valid(self, form):
        email = form.cleaned_data.get('email')
        phone = form.cleaned_data.get('phone')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_user_validation)

            with connection.cursor() as cursor:
                cursor.execute(user_validation_query, [email, phone])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        return super().form_valid(form)

class AddDoctor(CreateView):
    form_class = AddDoctorForm
    template_name = 'main/doctors_form.html'
    success_url = reverse_lazy('doctors')
    extra_context = {
        'title': 'Добавление врача',
    }

    def form_valid(self, form):
        office_phone = form.cleaned_data.get('office_phone')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_doctor_validation)

            with connection.cursor() as cursor:
                cursor.execute(doctor_validation_query, [office_phone])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        return super().form_valid(form)

class UpdateDoctor(UpdateView):
    model = Doctors
    form_class = AddDoctorForm
    template_name = 'main/doctors_form.html'
    success_url = reverse_lazy('doctors')
    extra_context = {
        'title': 'Редактирование врача',
    }

    def form_valid(self, form):
        office_phone = form.cleaned_data.get('office_phone')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_doctor_validation)

            with connection.cursor() as cursor:
                cursor.execute(doctor_validation_query, [office_phone])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        return super().form_valid(form)
    
class DeleteDoctor(DeleteView):
    model = Doctors
    success_url = reverse_lazy('doctors')

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.form_valid(None)

class PromocodesList(ListView):
    model = Promocodes

    def get_queryset(self):
        return Promocodes.objects.raw('''
            SELECT
                pr.id,
                pr.code,
                pr.discount,
                pr.expiration_date,
                pr.created_at
            FROM main_promocodes pr
            WHERE pr.expiration_date > CURRENT_DATE
            ORDER BY pr.code;
        ''')

class AddPromocode(CreateView):
    form_class = AddPromocodeForm
    template_name = 'main/promocodes_form.html'
    success_url = reverse_lazy('promocodes')
    extra_context = {
        'title': 'Добавление промокода',
    }

    def form_valid(self, form):
        discount = form.cleaned_data.get('discount')
        expiration_date = form.cleaned_data.get('expiration_date')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_promocode_validation)

            with connection.cursor() as cursor:
                cursor.execute(promocode_validation_query, [discount, expiration_date])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        promocode = form.save(commit=False)
        promocode.code = promocode.code.upper()
        try:
            with connection.cursor() as cursor:
                cursor.execute(insert_promocode_query, [promocode.code, promocode.discount, promocode.expiration_date])
        except Exception as e:
            form.add_error(None, f"Database insertion error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class DeletePromocode(DeleteView):
    model = Promocodes
    success_url = reverse_lazy('promocodes')

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = Services.objects.raw('''
                        SELECT
                            pr.id,
                            pr.code,
                            pr.discount,
                            pr.expiration_date,
                            pr.created_at
                        FROM main_promocodes pr
                        WHERE pr.id = %s;
                    ''', [pk])
            promocode = next(iter(raw_object), None)
            if not promocode:
                raise Http404('Объект promocode не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для delete: {e}')
        return promocode

    def get(self, request, *args, **kwargs):
        promocode = self.get_object()
        promocode_id = promocode.pk
        delete_query = '''DELETE FROM main_promocodes WHERE id = %s'''

        try:
            with connection.cursor() as cursor:
                cursor.execute(delete_query, [promocode_id])
        except Exception as e:
            return Http404(f'Database delete error: {e}')

        return HttpResponseRedirect(str(self.success_url))