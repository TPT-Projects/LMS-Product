from rest_framework.routers import SimpleRouter

from .views import ContactViewSet

router = SimpleRouter(trailing_slash=False)
router.register("contacts", ContactViewSet, basename="contacts")

urlpatterns = router.urls
