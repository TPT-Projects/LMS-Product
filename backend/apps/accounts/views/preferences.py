"""GET/PUT /preferences/tables/{table}: the user's own column layout."""

from django.http import Http404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import TablePreference

TABLES = ("enquiries", "contacts", "users")


class ColumnsSerializer(serializers.Serializer):
    columns = serializers.ListField(
        child=serializers.CharField(max_length=80), max_length=80, allow_empty=True
    )

    def validate_columns(self, value):
        return list(dict.fromkeys(value))  # no duplicates, keep order


class TablePreferenceView(APIView):
    """Any member may save their own layout. `columns: []` means "use the default"."""

    def _check(self, table: str) -> None:
        if table not in TABLES:
            raise Http404

    def get(self, request, table: str):
        self._check(table)
        pref = TablePreference.objects.filter(
            tenant=request.tenant, user=request.user, table=table
        ).first()
        return Response({"table": table, "columns": pref.columns if pref else []})

    def put(self, request, table: str):
        self._check(table)
        s = ColumnsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        pref, _ = TablePreference.objects.update_or_create(
            tenant=request.tenant,
            user=request.user,
            table=table,
            defaults={"columns": s.validated_data["columns"]},
        )
        return Response({"table": table, "columns": pref.columns})
