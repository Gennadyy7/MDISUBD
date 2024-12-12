from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    patronymic = models.CharField(max_length=150)
    email = models.EmailField(max_length=254, unique=True)
    phone = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f'{self.last_name}'

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

class Clients(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client')
    birth_date = models.DateField()
    address = models.CharField(max_length=255)

    def __str__(self):
        return f'Клиент {self.user}'

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'

class Specializations(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(max_length=2047)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Специализация врачей'
        verbose_name_plural = 'Специализации врачей'

class Doctors(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor')
    specialization = models.ForeignKey(Specializations, on_delete=models.CASCADE, related_name='doctors')
    office_phone  = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f'Врач {self.user}'

    class Meta:
        verbose_name = 'Врач'
        verbose_name_plural = 'Врачи'

class ServiceCategories(models.Model):
    name = models.CharField(max_length=150, unique=True)
    specialization = models.OneToOneField(Specializations, on_delete=models.CASCADE, related_name='service_category')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категория услуг'
        verbose_name_plural = 'Категории услуг'

class Services(models.Model):
    title = models.CharField(max_length=150, unique=True)
    description = models.TextField(max_length=2047)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(ServiceCategories, on_delete=models.CASCADE, related_name='services')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'

class Reviews(models.Model):
    client = models.ForeignKey(Clients, on_delete=models.CASCADE, related_name='reviews')
    doctor = models.ForeignKey(Doctors, on_delete=models.CASCADE, related_name='reviews')
    text = models.TextField(max_length=2047)
    rating = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Отзыв от {self.client} на {self.doctor}'

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'

class Promocodes(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount = models.PositiveSmallIntegerField()
    expiration_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'

class Orders(models.Model):
    client = models.ForeignKey(Clients, on_delete=models.CASCADE, related_name='orders')
    services = models.ManyToManyField(Services, verbose_name='Услуги')
    doctor = models.ForeignKey(Doctors, on_delete=models.CASCADE, related_name='orders')
    promocode = models.ForeignKey(Promocodes, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    appointment_date = models.DateTimeField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'Заказ №{self.pk} от {self.client}'

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

class ClientLogs(models.Model):
    client = models.ForeignKey(Clients, on_delete=models.CASCADE, related_name='logs')
    action = models.TextField(max_length=2047)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Лог №{self.pk} от {self.client}'

    class Meta:
        verbose_name = 'Пользовательский лог'
        verbose_name_plural = 'Пользовательские логи'