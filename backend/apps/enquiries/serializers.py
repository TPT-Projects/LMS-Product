from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.customfields import services as custom_fields
from apps.statuses.serializers import StatusRefSerializer
from common.phones import normalize_phone

from .models import Attachment, CallLog, CallOutcome, Enquiry, FollowUp, Note, Source
from .services import BULK_ACTIONS


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()


def user_ref(user) -> dict | None:
    return {"id": user.pk, "full_name": user.full_name, "email": user.email} if user else None


# --- read ------------------------------------------------------------------------
class EnquiryListSerializer(serializers.ModelSerializer):
    status = StatusRefSerializer()
    primary_owner = serializers.SerializerMethodField()
    secondary_owners = serializers.SerializerMethodField()
    next_followup_at = serializers.DateTimeField(read_only=True, allow_null=True)
    next_followup = serializers.SerializerMethodField()
    last_call = serializers.SerializerMethodField()
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Enquiry
        fields = [
            "id",
            "name",
            "phone",
            "phone_e164",
            "email",
            "status",
            "primary_owner",
            "source",
            "campaign_name",
            "adset_name",
            "ad_name",
            "form_id",
            "is_repeat",
            "contact_id",
            "secondary_owners",
            "next_followup_at",
            "next_followup",
            "last_call",
            "custom_fields",
            "created_at",
            "updated_at",
        ]

    def get_primary_owner(self, obj):
        return user_ref(obj.primary_owner)

    def get_secondary_owners(self, obj):
        return [user_ref(o.user) for o in obj.secondary_owners.all()]

    def get_next_followup(self, obj):
        """The earliest open follow-up, for the Action badge."""
        if getattr(obj, "next_followup_at", None) is None:
            return None
        return {
            "id": getattr(obj, "next_followup_id", None),
            "title": getattr(obj, "next_followup_title", ""),
            "auto_call_status": getattr(obj, "next_followup_call_status", None),
            "due_at": obj.next_followup_at,
        }

    def get_last_call(self, obj):
        """The latest call and its outcome (connected, no_answer, ...), for the Action badge."""
        if getattr(obj, "last_call_at", None) is None:
            return None
        return {"at": obj.last_call_at, "outcome": obj.last_call_outcome}

    def get_custom_fields(self, obj):
        return custom_fields.current_values(obj)


class EnquiryDetailSerializer(EnquiryListSerializer):
    secondary_owners = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta(EnquiryListSerializer.Meta):
        fields = [
            *EnquiryListSerializer.Meta.fields,
            "leadgen_id",
            "created_by",
            "contact",
            "permissions",
        ]

    def get_created_by(self, obj):
        return user_ref(obj.created_by)

    def get_contact(self, obj):
        c = obj.contact
        return {
            "id": c.pk,
            "name": c.name,
            "phone_e164": c.phone_e164,
            "email": c.email_lower,
            "enquiry_count": c.enquiries.filter(deleted_at__isnull=True).count(),
        }

    def get_permissions(self, obj):
        return self.context.get("permissions", {})


# --- write -------------------------------------------------------------------------
class EnquiryCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    status_id = serializers.IntegerField(required=False, allow_null=True)
    primary_owner_id = serializers.IntegerField(required=False, allow_null=True)
    secondary_owner_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list, max_length=20
    )
    campaign_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    adset_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    ad_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    form_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    custom_fields = serializers.DictField(required=False, default=dict)
    note = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs["phone"].strip() and not attrs["email"].strip():
            raise serializers.ValidationError({"phone": [_("Enter a phone number or an email.")]})
        if attrs["phone"].strip():
            country = self.context["request"].tenant.default_country
            if normalize_phone(attrs["phone"], country) is None:
                raise serializers.ValidationError({"phone": [_("Enter a valid phone number.")]})
        return attrs


class EnquiryUpdateSerializer(serializers.Serializer):
    """Phone is not here on purpose: it is locked after creation (spec 6.6)."""

    name = serializers.CharField(max_length=200, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    status_id = serializers.IntegerField(required=False)
    primary_owner_id = serializers.IntegerField(required=False, allow_null=True)
    secondary_owner_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, max_length=20
    )
    campaign_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    adset_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ad_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    custom_fields = serializers.DictField(required=False)

    def validate(self, attrs):
        if "phone" in self.initial_data:
            raise serializers.ValidationError({"phone": [_("The phone number cannot be changed.")]})
        return attrs


class BulkActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=200)
    action = serializers.ChoiceField(choices=BULK_ACTIONS)
    value = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["action"] in ("set_status", "add_secondary_owner") and not isinstance(
            attrs.get("value"), int
        ):
            raise serializers.ValidationError({"value": [_("Choose a value.")]})
        if attrs["action"] == "assign" and not (
            attrs.get("value") is None or isinstance(attrs.get("value"), int)
        ):
            raise serializers.ValidationError({"value": [_("Choose a user.")]})
        return attrs


# --- work items -------------------------------------------------------------------
class NoteSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    body = serializers.CharField(
        max_length=5000, trim_whitespace=True, required=False, allow_blank=True, default=""
    )
    has_audio = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            "id",
            "body",
            "has_audio",
            "audio_content_type",
            "audio_duration_seconds",
            "author",
            "created_at",
        ]
        read_only_fields = ["id", "author", "created_at", "audio_content_type"]

    def get_author(self, obj):
        return user_ref(obj.author)

    def get_has_audio(self, obj) -> bool:
        return bool(obj.audio)


class NoteCreateSerializer(serializers.Serializer):
    """Text and/or a voice recording (multipart field `audio`)."""

    body = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")
    audio = serializers.FileField(required=False, allow_null=True)
    audio_duration_seconds = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=24 * 3600
    )


class CallSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    outcome = serializers.ChoiceField(choices=CallOutcome.choices)
    duration_seconds = serializers.IntegerField(min_value=0, max_value=24 * 3600, default=0)
    notes = serializers.CharField(max_length=5000, allow_blank=True, required=False, default="")

    class Meta:
        model = CallLog
        fields = ["id", "outcome", "duration_seconds", "notes", "called_at", "user", "provider"]
        read_only_fields = ["id", "user", "provider"]
        extra_kwargs = {"called_at": {"required": False}}

    def get_user(self, obj):
        return user_ref(obj.user)


class FollowUpSerializer(serializers.ModelSerializer):
    assignee = serializers.SerializerMethodField()
    assignee_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    is_done = serializers.BooleanField(read_only=True)
    # Exotel: "Auto-call with Exotel" for this one call (when the workspace has it on)
    auto_call = serializers.BooleanField(write_only=True, required=False, default=True)
    auto_call_status = serializers.SerializerMethodField()

    class Meta:
        model = FollowUp
        fields = [
            "id",
            "title",
            "due_at",
            "assignee",
            "assignee_id",
            "done_at",
            "is_done",
            "auto_call",
            "auto_call_status",
            "created_at",
        ]
        read_only_fields = ["id", "done_at", "created_at"]

    def get_assignee(self, obj):
        return user_ref(obj.assignee)

    def get_auto_call_status(self, obj) -> str | None:
        """Status of this call's Exotel auto-call (pending, started, ...) or None."""
        call = getattr(obj, "auto_call", None)
        return call.status if call is not None else None


class FollowUpUpdateSerializer(serializers.Serializer):
    done = serializers.BooleanField(required=False)
    auto_call = serializers.BooleanField(required=False)
    due_at = serializers.DateTimeField(required=False)  # reschedule


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "file_name", "size", "content_type", "uploaded_by", "created_at"]

    def get_uploaded_by(self, obj):
        return user_ref(obj.uploaded_by)


SOURCE_CHOICES = Source.choices
