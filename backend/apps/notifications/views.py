"""/notifications: the user's own notifications (the bell and the notification page)."""

from django.http import Http404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "data", "is_read", "created_at"]

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None


def mine(request):
    return Notification.objects.filter(tenant=request.tenant, user=request.user)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = mine(self.request)
        if self.request.query_params.get("unread") == "1":
            qs = qs.filter(read_at__isnull=True)
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread_count"] = mine(request).filter(read_at__isnull=True).count()
        return response


class NotificationReadView(APIView):
    def post(self, request, notification_id: int):
        updated = (
            mine(request)
            .filter(pk=notification_id, read_at__isnull=True)
            .update(read_at=timezone.now())
        )
        if not updated and not mine(request).filter(pk=notification_id).exists():
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationReadAllView(APIView):
    def post(self, request):
        mine(request).filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)
