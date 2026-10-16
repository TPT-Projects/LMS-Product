from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import Status


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = ["id", "name", "order", "color", "is_default", "is_closed", "is_won"]
        read_only_fields = ["id"]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        qs = Status.objects.filter(tenant=self.context["request"].tenant, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(_("A status with this name already exists."))
        return value

    def validate(self, attrs):
        if attrs.get("is_won") and attrs.get("is_closed") is False:
            raise serializers.ValidationError({"is_won": [_("A won status must also be closed.")]})
        if attrs.get("is_won"):
            attrs["is_closed"] = True
        if self.instance and self.instance.is_default and attrs.get("is_default") is False:
            raise serializers.ValidationError(
                {"is_default": [_("Choose another default status instead.")]}
            )
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        if self.validated_data.get("is_default"):
            # Only one default per workspace.
            Status.objects.filter(tenant=self.context["request"].tenant, is_default=True).update(
                is_default=False
            )
        return super().save(**kwargs)


class StatusRefSerializer(serializers.ModelSerializer):
    """Compact status used inside enquiry payloads."""

    class Meta:
        model = Status
        fields = ["id", "name", "color", "is_closed"]
