
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Workspace,
    WorkspaceMember,
    Document,
    DocumentVersion,
    Comment,
    Tag,
    AuditLog,
)

User = get_user_model()


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password",
            "first_name", "last_name",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "username", "email",
            "first_name", "last_name", "date_joined",
        ]
        read_only_fields = fields


class WorkspaceSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id", "name", "description", "owner",
            "is_active", "created_at", "updated_at",
            "document_count", "member_count",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "document_count", "member_count",
        ]

    def get_document_count(self, obj):
        return getattr(
            obj, "document_count", obj.documents.count()
        )

    def get_member_count(self, obj):
        return getattr(
            obj, "member_count", obj.members.count()
        )

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Workspace name cannot be empty."
            )
        return value


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username", read_only=True
    )

    class Meta:
        model = WorkspaceMember
        fields = [
            "id", "workspace", "user", "username",
            "role", "joined_at",
        ]
        read_only_fields = ["id", "joined_at", "username"]

    def validate(self, attrs):
        workspace = attrs.get(
            "workspace",
            getattr(self.instance, "workspace", None),
        )
        user = attrs.get(
            "user",
            getattr(self.instance, "user", None),
        )

        if workspace and user:
            existing = WorkspaceMember.objects.filter(
                workspace=workspace,
                user=user,
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise serializers.ValidationError({
                    "user": (
                        "This user is already a member "
                        "of this workspace."
                    )
                })

        return attrs


class TagSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["id", "name", "created_at", "document_count"]
        read_only_fields = ["id", "created_at", "document_count"]

    def validate_name(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError(
                "Tag name cannot be empty."
            )

        existing = Tag.objects.filter(name__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError(
                "A tag with this name already exists."
            )

        return value

    def get_document_count(self, obj):
        return getattr(
            obj, "document_count", obj.documents.count()
        )


class DocumentSerializer(serializers.ModelSerializer):
    version_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
    )

    class Meta:
        model = Document
        fields = [
            "id", "workspace", "title", "content",
            "status", "created_by", "updated_by", "tags",
            "created_at", "updated_at",
            "version_count", "comment_count",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "version_count", "comment_count",
        ]

    def validate(self, attrs):
        title = attrs.get(
            "title",
            getattr(self.instance, "title", ""),
        )

        if not title or not title.strip():
            raise serializers.ValidationError({
                "title": "Document title cannot be empty."
            })

        workspace = attrs.get(
            "workspace",
            getattr(self.instance, "workspace", None),
        )
        creator = attrs.get(
            "created_by",
            getattr(self.instance, "created_by", None),
        )

        if workspace and creator:
            is_member = WorkspaceMember.objects.filter(
                workspace=workspace,
                user=creator,
            ).exists()

            if not is_member:
                raise serializers.ValidationError({
                    "created_by": (
                        "The document creator must be a "
                        "member of the workspace."
                    )
                })

        return attrs

    def get_version_count(self, obj):
        return getattr(
            obj, "version_count", obj.versions.count()
        )

    def get_comment_count(self, obj):
        return getattr(
            obj, "comment_count", obj.comments.count()
        )


class DocumentVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentVersion
        fields = [
            "id", "document", "version_number",
            "content", "saved_by", "created_at",
        ]
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="author.username", read_only=True
    )
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "document", "author", "username",
            "content", "parent", "created_at",
            "updated_at", "reply_count",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "username", "reply_count",
        ]

    def validate(self, attrs):
        document = attrs.get(
            "document",
            getattr(self.instance, "document", None),
        )
        parent = attrs.get(
            "parent",
            getattr(self.instance, "parent", None),
        )

        if parent and document and parent.document_id != document.id:
            raise serializers.ValidationError({
                "parent": (
                    "Parent comment must belong to "
                    "the same document."
                )
            })

        if self.instance and parent == self.instance:
            raise serializers.ValidationError({
                "parent": "A comment cannot be its own parent."
            })

        return attrs

    def get_reply_count(self, obj):
        return getattr(
            obj, "reply_count", obj.replies.count()
        )


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source="actor.username",
        read_only=True,
        default=None,
    )

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_username",
            "action", "model_name", "object_id",
            "details", "timestamp",
        ]
        read_only_fields = fields
