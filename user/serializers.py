from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying user information.
    """
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    is_normal_admin = serializers.BooleanField(read_only=True)
    is_super_admin = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'contact_number',
            'image',
            'role',
            'role_display',
            'is_active',
            'is_staff',
            'is_superuser',
            'is_normal_admin',
            'is_super_admin',
            'date_joined',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'date_joined',
            'updated_at',
            'is_staff',
            'is_superuser',
            'role_display',
            'is_normal_admin',
            'is_super_admin'
        ]


class AdminCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new admin users by superuser.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'email',
            'full_name',
            'contact_number',
            'image',
            'password',
            'password_confirm'
        ]
    
    def validate(self, attrs):
        """
        Check that the two password fields match.
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs
    
    def validate_email(self, value):
        """
        Check that email is not already registered.
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data):
        """
        Create a new admin user using the custom manager.
        """
        # Remove password_confirm as it's not needed for user creation
        validated_data.pop('password_confirm')
        
        # Extract password
        password = validated_data.pop('password')
        
        # Create admin user using custom manager
        user = User.objects.create_admin(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=password,
            contact_number=validated_data.get('contact_number', ''),
            image=validated_data.get('image', None)
        )
        
        return user


class AdminUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating admin user information.
    Password update is optional.
    """
    class Meta:
        model = User
        fields = [
            'full_name',
            'contact_number',
            'image',
        ]
        extra_kwargs = {
            'full_name': {'required': False},
            'contact_number': {'required': False},
            'image': {'required': False},
        }
    
    def update(self, instance, validated_data):
        """
        Update admin user, handling password separately if provided.
        """
        
        # Update regular fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class AdminListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing admin users.
    """
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'contact_number',
            'image',
            'role',
            'role_display',
            'is_active',
            'date_joined'
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
    """
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """
        Check that the new password fields match.
        """
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "New password fields didn't match."
            })
        return attrs
    
    def validate_old_password(self, value):
        """
        Check that the old password is correct.
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user's own profile information.
    """
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'contact_number',
            'image',
            'role',
            'role_display',
            'is_active',
            'permissions',
            'date_joined'
        ]
        read_only_fields = fields
    
    def get_permissions(self, obj):
        """
        Return user permissions based on their role.
        """
        return {
            'can_read': obj.has_read_permission(),
            'can_write': obj.has_write_permission(),
            'is_normal_admin': obj.is_normal_admin,
            'is_super_admin': obj.is_super_admin
        }
    

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        validate_password(attrs['new_password'])
        return attrs
    