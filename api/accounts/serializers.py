from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from api.workspaces.models import Workspace, WorkspaceMembership

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone', 'timezone', 'notification_preferences',
        )
        read_only_fields = ('id', 'email')


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default='')
    workspace_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    def _unique_username(self, email):
        base = slugify(email.split('@')[0])[:120] or 'user'
        candidate = base
        n = 2
        while User.objects.filter(username=candidate).exists():
            suffix = f'-{n}'
            candidate = f'{base[: 150 - len(suffix)]}{suffix}'
            n += 1
        return candidate

    def _unique_slug(self, name):
        base = slugify(name)[:240] or 'workspace'
        candidate = base
        n = 2
        while Workspace.objects.filter(slug=candidate).exists():
            suffix = f'-{n}'
            candidate = f'{base[: 255 - len(suffix)]}{suffix}'
            n += 1
        return candidate

    def create(self, validated_data):
        email = validated_data['email']
        workspace_name = (validated_data.get('workspace_name') or '').strip() or f"{email.split('@')[0]} workspace"
        with transaction.atomic():
            user = User.objects.create_user(
                username=self._unique_username(email),
                email=email,
                password=validated_data['password'],
                first_name=validated_data.get('first_name') or '',
                last_name=validated_data.get('last_name') or '',
                phone=validated_data.get('phone') or '',
            )
            workspace = Workspace.objects.create(
                name=workspace_name,
                slug=self._unique_slug(workspace_name),
                created_by=user,
            )
            WorkspaceMembership.objects.create(
                workspace=workspace,
                user=user,
                role=WorkspaceMembership.ROLE_ADMIN,
            )
        user._signup_workspace = workspace
        return user
