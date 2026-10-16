from zoneinfo import available_timezones

import phonenumbers
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Tenant


def validate_timezone(value: str) -> str:
    if value not in available_timezones():
        raise serializers.ValidationError(_("Unknown timezone."))
    return value


def validate_country(value: str) -> str:
    value = value.upper()
    if value not in phonenumbers.SUPPORTED_REGIONS:
        raise serializers.ValidationError(_("Unknown country code."))
    return value


class WorkspaceSerializer(serializers.ModelSerializer):
    timezone = serializers.CharField(validators=[validate_timezone])
    default_country = serializers.CharField(validators=[validate_country])

    class Meta:
        model = Tenant
        fields = ["id", "name", "timezone", "dedupe_key", "default_country", "plan", "created_at"]
        read_only_fields = ["id", "plan", "created_at"]
