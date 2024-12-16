from datetime import datetime, timedelta

from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import connection, transaction
from django.db.transaction import commit
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView

from main.forms import AddServiceForm, AddCategoryForm, AddSpecializationForm, AddUserForm, AddDoctorForm, \
    AddPromocodeForm, AddUserForClientForm, AddReviewForm, AddOrderForm
from main.models import Services, ServiceCategories, Specializations, Doctors, Promocodes, Clients, ClientLogs, Reviews, \
    Orders

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
                            d_office_phone TEXT,
                            d_user_id INTEGER
                        ) RETURNS TEXT AS $$
                        DECLARE
                            existing_client_count INTEGER;
                        BEGIN
                            IF NOT (d_office_phone ~ '^80\d{2} \d{3}-\d{2}-\d{2}$') THEN
                                RETURN 'Invalid office_phone format';
                            END IF;

                            SELECT COUNT(*) INTO existing_client_count
                            FROM main_clients
                            WHERE user_id = d_user_id;
                            
                            IF existing_client_count > 0 THEN
                                RETURN 'User is already associated with a client';
                            END IF;

                            RETURN 'OK';
                        END;
                        $$ LANGUAGE plpgsql;
                        ''')
doctor_validation_query = "SELECT validate_doctor_data(%s, %s);"
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
plpgsql_client_validation = (r'''
                        CREATE OR REPLACE FUNCTION validate_client_data(
                            cl_birth_date DATE,
                            cl_address TEXT
                        ) RETURNS TEXT AS $$
                        BEGIN
                            IF cl_birth_date > CURRENT_DATE - INTERVAL '18 years' THEN
                                RETURN 'User must be at least 18 years old';
                            END IF;

                            IF NOT (cl_address ~ '^ул\. [А-Яа-я]+\, д\. (\d+|\d+\/\d+)\, кв\. \d+$') THEN
                                RETURN 'Invalid address format';
                            END IF;

                            RETURN 'OK';
                        END;
                        $$ LANGUAGE plpgsql;
                        ''')
client_validation_query = "SELECT validate_client_data(%s, %s);"
plpgsql_review_validation = ('''
                        CREATE OR REPLACE FUNCTION validate_review_data(
                            r_rating INTEGER
                        ) RETURNS TEXT AS $$
                        BEGIN
                            IF r_rating < 1 OR r_rating > 5 THEN
                                RETURN 'Rating can be from 1 to 5';
                            END IF;

                            RETURN 'OK';
                        END;
                        $$ LANGUAGE plpgsql;
                        ''')
review_validation_query = "SELECT validate_review_data(%s);"
insert_review_query = ("""
                INSERT INTO main_reviews (client_id, doctor_id, text, rating, created_at)
                VALUES (%s, %s, %s, %s, NOW());
                """)
insert_order_query = ("""
                INSERT INTO main_orders (doctor_id, client_id, promocode_id, appointment_date, total_price)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """)

class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

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

class AddService(SuperUserRequiredMixin, CreateView):
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

class UpdateService(SuperUserRequiredMixin, UpdateView):
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

class DeleteService(SuperUserRequiredMixin, DeleteView):
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

class AddCategory(SuperUserRequiredMixin, CreateView):
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

class UpdateCategory(SuperUserRequiredMixin, UpdateView):
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

class DeleteCategory(SuperUserRequiredMixin, DeleteView):
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

class AddSpecialization(SuperUserRequiredMixin, CreateView):
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

class UpdateSpecialization(SuperUserRequiredMixin, UpdateView):
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

class DeleteSpecialization(SuperUserRequiredMixin, DeleteView):
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

class AddUserForDoctor(SuperUserRequiredMixin, CreateView):
    form_class = AddUserForm
    template_name = 'main/users_form.html'
    success_url = reverse_lazy('doctors')
    extra_context = {
        'title': 'Добавление пользователя',
        'h1_content': 'Форма пользователя',
        'submit_content': 'Отправить',
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

        user = form.save(commit=False)
        user.set_password(form.cleaned_data.get('password'))

        return super().form_valid(form)

class AddDoctor(SuperUserRequiredMixin, CreateView):
    form_class = AddDoctorForm
    template_name = 'main/doctors_form.html'
    success_url = reverse_lazy('doctors')
    extra_context = {
        'title': 'Добавление врача',
    }

    def form_valid(self, form):
        office_phone = form.cleaned_data.get('office_phone')
        user = form.cleaned_data.get('user')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_doctor_validation)

            with connection.cursor() as cursor:
                cursor.execute(doctor_validation_query, [office_phone, user.pk])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        return super().form_valid(form)

class UpdateDoctor(SuperUserRequiredMixin, UpdateView):
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
    
class DeleteDoctor(SuperUserRequiredMixin, DeleteView):
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

class AddPromocode(SuperUserRequiredMixin, CreateView):
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

class DeletePromocode(SuperUserRequiredMixin, DeleteView):
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

class LoginUser(LoginView):
    form_class = AuthenticationForm
    template_name = 'main/login.html'
    extra_context = {
        'title': 'Авторизация',
    }

def logout_user(request):
    logout(request)
    return redirect('home')

class RegisterUser(AddUserForDoctor):
    form_class = AddUserForClientForm
    success_url = reverse_lazy('login')
    extra_context = {
        'title': 'Регистрация',
        'h1_content': 'Регистрация',
        'submit_content': 'Зарегистрироваться'
    }

    def form_valid(self, form):
        super().form_valid(form)
        if form.errors:
            return self.form_invalid(form)

        birth_date = form.cleaned_data.get('birth_date')
        address = form.cleaned_data.get('address')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_client_validation)

            with connection.cursor() as cursor:
                cursor.execute(client_validation_query, [birth_date, address])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        user = form.save(commit=False)
        client = Clients(
            user=user,
            birth_date=birth_date,
            address=address
        )
        client.save()

        return HttpResponseRedirect(str(self.success_url))

class ClientLogsList(SuperUserRequiredMixin, ListView):
    model = ClientLogs

    def get_queryset(self):
        return ClientLogs.objects.raw('''
            SELECT
                cll.id,
                cll.action,
                cll.created_at,
                u.username,
                u.first_name,
                u.last_name,
                u.patronymic
            FROM main_clientlogs cll
            JOIN main_clients cl ON cl.id = cll.client_id
            JOIN main_user u ON u.id = cl.user_id
            ORDER BY cll.created_at DESC;
        ''')

class ReviewsList(LoginRequiredMixin, ListView):
    model = Reviews

    def get_queryset(self):
        ss = Reviews.objects.raw('''
            SELECT
                r.id,
                r.rating,
                r.text,
                r.created_at,
                u.username,
                u2.first_name,
                u2.last_name,
                u2.patronymic
            FROM main_reviews r
            INNER JOIN main_clients cl ON cl.id = r.client_id
            INNER JOIN main_user u ON u.id = cl.user_id
            INNER JOIN main_doctors d ON d.id = r.doctor_id
            INNER JOIN main_user u2 ON u2.id = d.user_id
            ORDER BY r.created_at DESC;
        ''')
        return ss

class AddReview(CreateView):
    form_class = AddReviewForm
    template_name = 'main/reviews_form.html'
    success_url = reverse_lazy('reviews')
    extra_context = {
        'title': 'Добавление отзыва',
    }

    def form_valid(self, form):
        rating = form.cleaned_data.get('rating')

        try:
            with connection.cursor() as cursor:
                cursor.execute(plpgsql_review_validation)

            with connection.cursor() as cursor:
                cursor.execute(review_validation_query, [rating])
                validation_result = cursor.fetchone()[0]

            if validation_result != 'OK':
                form.add_error(None, validation_result)
                return self.form_invalid(form)

        except Exception as e:
            form.add_error(None, f"Database error: {e}")
            return self.form_invalid(form)

        review = form.save(commit=False)
        try:
            review.client = self.request.user.client
        except Exception:
            form.add_error(None, "Только клиенты могут оставить отзыв!!!")
            return self.form_invalid(form)

        try:
            with connection.cursor() as cursor:
                cursor.execute(insert_review_query, [review.client.pk, review.doctor.pk, review.text, review.rating])
        except Exception as e:
            form.add_error(None, f"Database insertion error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class DeleteReview(SuperUserRequiredMixin, DeleteView):
    model = Reviews
    success_url = reverse_lazy('reviews')

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = Reviews.objects.raw('''
                        SELECT
                            r.id,
                            r.client_id,
                            r.doctor_id,
                            r.rating,
                            r.text,
                            r.created_at
                        FROM main_reviews r
                        WHERE r.id = %s;
                    ''', [pk])
            review = next(iter(raw_object), None)
            if not review:
                raise Http404('Объект review не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для delete: {e}')
        return review

    def get(self, request, *args, **kwargs):
        review = self.get_object()
        review_id = review.pk
        delete_query = '''DELETE FROM main_reviews WHERE id = %s'''

        try:
            with connection.cursor() as cursor:
                cursor.execute(delete_query, [review_id])
        except Exception as e:
            return Http404(f'Database delete error: {e}')

        return HttpResponseRedirect(str(self.success_url))

class OrdersList(LoginRequiredMixin, ListView):
    model = Orders
    template_name = 'main/orders_list.html'

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'client') or user.is_superuser:
            sql = ('''
                    SELECT
                        o.id,
                        u.first_name,
                        u.last_name,
                        u.patronymic,
                        p.discount,
                        o.total_price,
                        o.appointment_date,
                        STRING_AGG(s.title, ', ') AS services
                    FROM main_orders o
                    LEFT JOIN main_promocodes p ON p.id = o.promocode_id
                    INNER JOIN main_doctors d ON d.id = o.doctor_id
                    INNER JOIN main_user u ON u.id = d.user_id
                    INNER JOIN main_orders_services os ON os.orders_id = o.id
                    INNER JOIN main_services s ON s.id = os.services_id
                    WHERE (%s OR o.client_id = %s)
                    GROUP BY o.id, u.first_name, u.last_name, u.patronymic, p.discount, o.total_price, o.appointment_date
                    ORDER BY o.appointment_date DESC;
                    ''')
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql, [user.is_superuser, user.client.pk if not user.is_superuser else None])
                    orders = cursor.fetchall()
            except Exception as e:
                raise Http404(f'Ошибка при попытке получения выборки заказов: {e}')
            order_list = []
            for order in orders:
                order_dict = {
                    'id': order[0],
                    'pk': order[0],
                    'first_name': order[1],
                    'last_name': order[2],
                    'patronymic': order[3],
                    'discount': str(order[4]) + '%' if order[4] else 'Нет',
                    'total_price': order[5],
                    'appointment_date': order[6],
                    'services': order[7],
                }
                order_list.append(order_dict)
            return order_list

        return Orders.objects.none()

class AddOrder(CreateView):
    form_class = AddOrderForm
    template_name = 'main/orders_form.html'
    success_url = reverse_lazy('orders')
    extra_context = {
        'title': 'Оформление заказа',
    }

    def form_valid(self, form):
        services = form.cleaned_data.get('services')
        order = form.save(commit=False)
        order.total_price = sum(service.price for service in services)
        try:
            order.client = self.request.user.client
        except Exception:
            form.add_error(None, "Только клиенты могут оставить отзыв!!!")
            return self.form_invalid(form)

        next_day_10am = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT appointment_date, COUNT(os.services_id)
                FROM main_orders o
                LEFT JOIN main_orders_services os ON o.id = os.orders_id
                WHERE doctor_id = %s AND appointment_date >= %s
                GROUP BY o.appointment_date
                ORDER BY o.appointment_date DESC
                LIMIT 1;
            """, [order.doctor.pk, next_day_10am])
            result = cursor.fetchone()

        if result:
            last_appointment_date, service_count = result
            service_count = int(service_count)

            new_appointment_time = last_appointment_date + timedelta(hours=service_count)

            if new_appointment_time.hour >= 18:
                order.appointment_date = (last_appointment_date + timedelta(days=1)).replace(hour=10, minute=0,
                                                                                             second=1)
            else:
                order.appointment_date = new_appointment_time
        else:
            order.appointment_date = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=1)

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(insert_order_query, [order.doctor.pk, order.client.pk, order.promocode.pk if order.promocode else None, order.appointment_date, order.total_price])

                    order_id = cursor.fetchone()[0]

                    for service in services:
                        cursor.execute('''
                                        INSERT INTO main_orders_services (orders_id, services_id)
                                        VALUES (%s, %s);
                                    ''', [order_id, service.pk])
        except Exception as e:
            form.add_error(None, f"Database insertion error: {e}")
            return self.form_invalid(form)

        return HttpResponseRedirect(str(self.success_url))

class DeleteOrder(SuperUserRequiredMixin, DeleteView):
    model = Orders
    success_url = reverse_lazy('orders')

    def get_object(self, queryset=None):
        try:
            pk = self.kwargs.get('pk')
            raw_object = Orders.objects.raw('''
                        SELECT *
                        FROM main_orders o
                        WHERE o.id = %s;
                    ''', [pk])
            order = next(iter(raw_object), None)
            if not order:
                raise Http404('Объект order не был найден')
        except Exception as e:
            raise Http404(f'Ошибка получения объекта для delete: {e}')
        return order

    def get(self, request, *args, **kwargs):
        order = self.get_object()
        order_id = order.pk
        delete_query = '''DELETE FROM main_orders WHERE id = %s'''

        try:
            with connection.cursor() as cursor:
                cursor.execute(delete_query, [order_id])
        except Exception as e:
            return Http404(f'Database delete error: {e}')

        return HttpResponseRedirect(str(self.success_url))