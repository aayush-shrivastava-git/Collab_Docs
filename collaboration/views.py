
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Avg
from django.db.models import Max, Min
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from django.contrib.auth import get_user_model

from .models import (
    Workspace,
    WorkspaceMember,
    Document,
    DocumentVersion,
    Comment,
    Tag,
    AuditLog,
)
from .serializers import (
    UserCreateSerializer,
    UserReadSerializer,
    WorkspaceSerializer,
    WorkspaceMemberSerializer,
    DocumentSerializer,
    DocumentVersionSerializer,
    CommentSerializer,
    TagSerializer,
    AuditLogSerializer,
)

User = get_user_model()


def write_audit(actor, action, model_name, object_id, details=None):
    """Create an audit entry inside the caller's transaction."""
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        details=details or {},
    )


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("username")
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserReadSerializer

    def get_queryset(self):
        return User.objects.all().order_by("username")

    def list(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use the user detail endpoint to retrieve a user."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return (
            Workspace.objects
            .select_related("owner")
            .annotate(
                document_count=Count("documents", distinct=True),
                member_count=Count("members", distinct=True),
            )
            .order_by("-created_at")
        )

    @transaction.atomic
    def perform_create(self, serializer):
        workspace = serializer.save()

        try:
            # Nested atomic creates a savepoint so IntegrityError
            # can be handled without breaking the outer transaction.
            with transaction.atomic():
                WorkspaceMember.objects.create(
                    workspace=workspace,
                    user=workspace.owner,
                    role=WorkspaceMember.Role.ADMIN,
                )
        except IntegrityError:
            raise ValidationError({
                "owner": "Workspace owner membership could not be created."
            })

        write_audit(
            actor=workspace.owner,
            action=AuditLog.Action.CREATED,
            model_name="Workspace",
            object_id=workspace.id,
            details={"name": workspace.name},
        )

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        workspace = self.get_object()

        if request.method == "GET":
            members = (
                WorkspaceMember.objects
                .filter(workspace=workspace)
                .select_related("user", "workspace")
                .order_by("joined_at")
            )
            return Response(
                WorkspaceMemberSerializer(members, many=True).data
            )

        user_id = request.data.get("user")

        if user_id and WorkspaceMember.objects.filter(
                workspace=workspace,
                user_id=user_id,
        ).exists():
            return Response(
                {"detail": "User is already a member of this workspace."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = WorkspaceMemberSerializer(data={
            **request.data,
            "workspace": str(workspace.id),
        })
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                with transaction.atomic():
                    member = serializer.save()

                write_audit(
                    actor=workspace.owner,
                    action=AuditLog.Action.MEMBER_ADDED,
                    model_name="WorkspaceMember",
                    object_id=member.id,
                    details={
                        "workspace_id": str(workspace.id),
                        "user_id": str(member.user_id),
                        "role": member.role,
                    },
                )
        except IntegrityError:
            return Response(
                {"detail": "User is already a member of this workspace."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            WorkspaceMemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        workspace = self.get_object()

        documents = Document.objects.filter(workspace=workspace)
        members = WorkspaceMember.objects.filter(workspace=workspace)

        return Response({
            "workspace_id": str(workspace.id),
            "workspace_name": workspace.name,
            "is_active": workspace.is_active,
            "member_count": members.count(),
            "document_count": documents.count(),
            "documents_by_status": list(
                documents.values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            ),
        })


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "put", "head", "options"]

    def get_queryset(self):
        queryset = (
            Document.objects
            .select_related("workspace", "created_by", "updated_by")
            .prefetch_related("tags")
            .annotate(
                version_count=Count("versions", distinct=True),
                comment_count=Count("comments", distinct=True),
            )
        )

        params = self.request.query_params

        workspace = params.get("workspace")
        if workspace:
            queryset = queryset.filter(workspace_id=workspace)

        creator = params.get("created_by")
        if creator:
            queryset = queryset.filter(created_by_id=creator)

        status_values = params.get("status__in")
        if status_values:
            queryset = queryset.filter(
                status__in=[
                    value.strip() for value in status_values.split(",")
                ]
            )
        elif params.get("status"):
            queryset = queryset.filter(status=params["status"])

        tag = params.get("tag")
        if tag:
            queryset = queryset.filter(tags__id=tag)

        search = params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(content__icontains=search)
            )

        created_after = params.get("created_after")
        if created_after:
            dt = parse_datetime(created_after)
            if dt is None:
                raise ValidationError({
                    "created_after": "Provide a valid ISO datetime."
                })
            queryset = queryset.filter(created_at__gte=dt)

        created_before = params.get("created_before")
        if created_before:
            dt = parse_datetime(created_before)
            if dt is None:
                raise ValidationError({
                    "created_before": "Provide a valid ISO datetime."
                })
            queryset = queryset.filter(created_at__lte=dt)

        return queryset.distinct().order_by("-updated_at")

    def _create_version(self, document):
        version_number = document.versions.count() + 1
        DocumentVersion.objects.create(
            document=document,
            version_number=version_number,
            content=document.content,
            saved_by=document.updated_by or document.created_by,
        )

    @transaction.atomic
    def perform_create(self, serializer):
        document = serializer.save()
        self._create_version(document)

    @transaction.atomic
    def perform_update(self, serializer):
        document = serializer.save()
        self._create_version(document)

    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, pk=None):
        document = self.get_object()
        versions = (
            DocumentVersion.objects
            .filter(document=document)
            .select_related("document", "saved_by")
            .order_by("-version_number")
        )
        return Response(
            DocumentVersionSerializer(versions, many=True).data
        )

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        document = self.get_object()

        version_stats = document.versions.aggregate(
            total_versions=Count("id"),
            latest_version=Max("version_number"),
            earliest_version=Min("version_number"),
        )
        comment_stats = document.comments.aggregate(
            total_comments=Count("id"),
            unique_commenters=Count("author", distinct=True),
        )

        return Response({
            "document_id": str(document.id),
            "title": document.title,
            "versions": version_stats,
            "comments": comment_stats,
            "tag_count": document.tags.count(),
        })

    @action(detail=True, methods=["post"], url_path="tags")
    def tags(self, request, pk=None):
        document = self.get_object()
        tag_ids = request.data.get("tag_ids")

        if not isinstance(tag_ids, list) or not tag_ids:
            return Response(
                {"detail": "Provide a non-empty tag_ids list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            found_ids = set(
                Tag.objects.filter(id__in=tag_ids).values_list(
                    "id", flat=True
                )
            )
            requested_ids = set()
            try:
                requested_ids = {str(tag_id) for tag_id in tag_ids}
            except (TypeError, ValueError):
                pass

            if len(found_ids) != len(requested_ids):
                return Response(
                    {"detail": "One or more tags do not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            document.tags.add(*found_ids)

            write_audit(
                actor=document.updated_by or document.created_by,
                action=AuditLog.Action.TAG_ADDED,
                model_name="Document",
                object_id=document.id,
                details={"tag_ids": sorted(requested_ids)},
            )

        return Response(
            DocumentSerializer(
                self.get_queryset().get(pk=document.pk)
            ).data,
            status=status.HTTP_200_OK,
        )


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = (
            Comment.objects
            .select_related("document", "author", "parent")
            .annotate(reply_count=Count("replies", distinct=True))
        )

        document = self.request.query_params.get("document")
        if document:
            queryset = queryset.filter(document_id=document)

        author = self.request.query_params.get("author")
        if author:
            queryset = queryset.filter(author_id=author)

        return queryset.order_by("created_at")

    def perform_create(self, serializer):
        serializer.save()


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Tag.objects.annotate(
            document_count=Count("documents", distinct=True)
        ).order_by("name")


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor").all()

        actor = self.request.query_params.get("actor")
        if actor:
            queryset = queryset.filter(actor_id=actor)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            dt = parse_datetime(date_from)
            if dt is None:
                raise ValidationError({
                    "date_from": "Provide a valid ISO datetime."
                })
            queryset = queryset.filter(timestamp__gte=dt)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            dt = parse_datetime(date_to)
            if dt is None:
                raise ValidationError({
                    "date_to": "Provide a valid ISO datetime."
                })
            queryset = queryset.filter(timestamp__lte=dt)

        model_name = self.request.query_params.get("model_name")
        if model_name:
            queryset = queryset.filter(model_name__icontains=model_name)

        return queryset.order_by("-timestamp")
