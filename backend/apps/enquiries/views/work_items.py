"""/api/v1/enquiries/{id}/notes | calls | followups | attachments."""

from django.http import FileResponse, Http404, HttpResponseRedirect
from django.utils.translation import gettext as _
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import services
from ..models import Attachment, CallLog, Enquiry, FollowUp, Note
from ..selectors import visible_enquiries
from ..serializers import (
    AttachmentSerializer,
    CallSerializer,
    FollowUpSerializer,
    FollowUpUpdateSerializer,
    NoteCreateSerializer,
    NoteSerializer,
)


class EnquiryChildMixin:
    """Resolves the parent enquiry with the same visibility rules as the enquiry itself."""

    _enquiry: Enquiry | None = None

    @property
    def enquiry(self) -> Enquiry:
        if self._enquiry is None:
            enquiry = (
                visible_enquiries(self.request.membership)
                .filter(pk=self.kwargs["enquiry_id"])
                .first()
            )
            if enquiry is None:
                raise Http404
            self._enquiry = enquiry
        return self._enquiry


class NoteListView(EnquiryChildMixin, generics.ListAPIView):
    serializer_class = NoteSerializer

    def get_queryset(self):
        return Note.objects.filter(enquiry=self.enquiry).select_related("author")

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, enquiry_id: int):
        s = NoteCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        note = services.add_note(
            enquiry=self.enquiry,
            membership=request.membership,
            body=s.validated_data["body"],
            audio=s.validated_data.get("audio"),
            audio_duration_seconds=s.validated_data.get("audio_duration_seconds"),
        )
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class NoteAudioView(EnquiryChildMixin, APIView):
    """Voice notes are private: streamed after the same visibility check as the enquiry."""

    def get(self, request, enquiry_id: int, note_id: int):
        note = Note.objects.filter(enquiry=self.enquiry, pk=note_id).exclude(audio="").first()
        if note is None:
            raise Http404
        if hasattr(note.audio.storage, "bucket_name"):
            return HttpResponseRedirect(note.audio.url)
        return FileResponse(note.audio.open("rb"), content_type=note.audio_content_type)


class CallListView(EnquiryChildMixin, generics.ListAPIView):
    serializer_class = CallSerializer

    def get_queryset(self):
        return CallLog.objects.filter(enquiry=self.enquiry).select_related("user")

    def post(self, request, enquiry_id: int):
        s = CallSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        call = services.log_call(
            enquiry=self.enquiry, membership=request.membership, data=s.validated_data
        )
        return Response(CallSerializer(call).data, status=status.HTTP_201_CREATED)


class FollowUpListView(EnquiryChildMixin, generics.ListAPIView):
    serializer_class = FollowUpSerializer

    def get_queryset(self):
        return FollowUp.objects.filter(enquiry=self.enquiry).select_related("assignee", "auto_call")

    def post(self, request, enquiry_id: int):
        s = FollowUpSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        followup = services.schedule_followup(
            enquiry=self.enquiry, membership=request.membership, data=s.validated_data
        )
        return Response(FollowUpSerializer(followup).data, status=status.HTTP_201_CREATED)


class FollowUpDetailView(EnquiryChildMixin, APIView):
    def patch(self, request, enquiry_id: int, followup_id: int):
        followup = (
            FollowUp.objects.filter(enquiry=self.enquiry, pk=followup_id)
            .select_related("enquiry", "assignee")
            .first()
        )
        if followup is None:
            raise Http404
        s = FollowUpUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if "done" in s.validated_data:
            followup = services.set_followup_done(
                followup=followup, membership=request.membership, done=s.validated_data["done"]
            )
        if "due_at" in s.validated_data:
            followup = services.reschedule_followup(
                followup=followup, membership=request.membership, due_at=s.validated_data["due_at"]
            )
        if "auto_call" in s.validated_data:
            services.set_followup_auto_call(
                followup=followup,
                membership=request.membership,
                enabled=s.validated_data["auto_call"],
            )
            followup.refresh_from_db()
        return Response(FollowUpSerializer(followup).data)


class AttachmentListView(EnquiryChildMixin, generics.ListAPIView):
    serializer_class = AttachmentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Attachment.objects.filter(enquiry=self.enquiry).select_related("uploaded_by")

    def post(self, request, enquiry_id: int):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": [_("Choose a file.")]})
        attachment = services.add_attachment(
            enquiry=self.enquiry, membership=request.membership, upload=upload
        )
        return Response(AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


class AttachmentDownloadView(EnquiryChildMixin, APIView):
    """Files are private. Local storage streams the file; S3 redirects to a signed URL."""

    def get(self, request, enquiry_id: int, attachment_id: int):
        attachment = Attachment.objects.filter(enquiry=self.enquiry, pk=attachment_id).first()
        if attachment is None:
            raise Http404
        storage = attachment.file.storage
        if hasattr(storage, "bucket_name"):
            return HttpResponseRedirect(attachment.file.url)
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.file_name,
            content_type=attachment.content_type,
        )
