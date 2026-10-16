from django.utils.text import slugify
from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import CustomField, FieldType

CHOICE_TYPES = (FieldType.DROPDOWN, FieldType.MULTI_SELECT)


class CustomFieldSerializer(serializers.ModelSerializer):
    key = serializers.SlugField(max_length=64, required=False)
    options = serializers.ListField(
        child=serializers.CharField(max_length=200), required=False, max_length=200
    )

    class Meta:
        model = CustomField
        fields = ["id", "key", "label", "type", "options", "is_required", "is_active", "order"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        tenant = self.context["request"].tenant
        if self.instance:
            # Changing key or type would orphan stored values: not allowed.
            for locked in ("key", "type"):
                if locked in attrs and attrs[locked] != getattr(self.instance, locked):
                    raise serializers.ValidationError({locked: [_("This cannot be changed.")]})
        else:
            attrs["key"] = (attrs.get("key") or slugify(attrs["label"]).replace("-", "_"))[:64]
            if not attrs["key"]:
                raise serializers.ValidationError({"key": [_("Enter a key.")]})
            if CustomField.objects.filter(tenant=tenant, key=attrs["key"]).exists():
                raise serializers.ValidationError({"key": [_("A field with this key exists.")]})

        field_type = attrs.get("type", self.instance.type if self.instance else None)
        options = attrs.get("options", self.instance.options if self.instance else [])
        options = list(dict.fromkeys(o.strip() for o in options if o.strip()))
        if field_type in CHOICE_TYPES:
            if not options:
                raise serializers.ValidationError({"options": [_("Add at least one option.")]})
            attrs["options"] = options
        else:
            attrs["options"] = []
        return attrs
