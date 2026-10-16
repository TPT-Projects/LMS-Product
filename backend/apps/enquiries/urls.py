from django.urls import path
from rest_framework.routers import SimpleRouter

from .views.enquiries import EnquiryViewSet
from .views.work_items import (
    AttachmentDownloadView,
    AttachmentListView,
    CallListView,
    FollowUpDetailView,
    FollowUpListView,
    NoteAudioView,
    NoteListView,
)

router = SimpleRouter(trailing_slash=False)
router.register("enquiries", EnquiryViewSet, basename="enquiries")

child = "enquiries/<int:enquiry_id>"
urlpatterns = [
    path(f"{child}/notes", NoteListView.as_view(), name="enquiry-notes"),
    path(f"{child}/notes/<int:note_id>/audio", NoteAudioView.as_view(), name="enquiry-note-audio"),
    path(f"{child}/calls", CallListView.as_view(), name="enquiry-calls"),
    path(f"{child}/followups", FollowUpListView.as_view(), name="enquiry-followups"),
    path(
        f"{child}/followups/<int:followup_id>",
        FollowUpDetailView.as_view(),
        name="enquiry-followup",
    ),
    path(f"{child}/attachments", AttachmentListView.as_view(), name="enquiry-attachments"),
    path(
        f"{child}/attachments/<int:attachment_id>/download",
        AttachmentDownloadView.as_view(),
        name="enquiry-attachment-download",
    ),
    *router.urls,
]
