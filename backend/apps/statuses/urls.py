from rest_framework.routers import SimpleRouter

from .views import StatusViewSet

router = SimpleRouter(trailing_slash=False)
router.register("statuses", StatusViewSet, basename="statuses")

urlpatterns = router.urls
