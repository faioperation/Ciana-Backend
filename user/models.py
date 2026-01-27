import time

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.validators import RegexValidator


# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        """
        Creates and saves a regular user with the given email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('role', Users.Role.USER)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_admin(self, email, full_name, password=None, **extra_fields):
        """
        Creates and saves a normal admin user with read-only access.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_superuser', False)
        extra_fields['role'] = Users.Role.ADMIN
        
        return self.create_user(email, full_name, password, **extra_fields)

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        """
        Creates and saves a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields['role'] = Users.Role.SUPERUSER 

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, full_name, password, **extra_fields)


# Custom User Model
class Users(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model where email is used for authentication
    instead of username.
    """
    class Role(models.TextChoices):
        USER = 'USER', 'User'
        ADMIN = 'ADMIN', 'Admin'
        SUPERUSER = 'SUPERUSER', 'Superuser'

    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )

    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True)
    contact_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True
    )
    image = models.ImageField(
        upload_to='user_images/',
        blank=True,
        null=True
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        help_text='User role determines their access level'
    )

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()  # connect custom manager

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    # Helper methods for role checking
    @property
    def is_normal_admin(self):
        """Check if user is a normal admin (not superuser)"""
        return self.role == self.Role.ADMIN and not self.is_superuser
    
    @property
    def is_super_admin(self):
        """Check if user is a superuser"""
        return self.role == self.Role.SUPERUSER and self.is_superuser
    
    def has_read_permission(self):
        """Check if user has read permission"""
        return self.role in [self.Role.ADMIN, self.Role.SUPERUSER]
    
    def has_write_permission(self):
        """Check if user has write permission"""
        return self.role == self.Role.SUPERUSER and self.is_superuser
    
    def get_full_name(self):
        return self.full_name
    
    def get_short_name(self):
        return self.email
    
    def __str__(self):
        return self.email
    