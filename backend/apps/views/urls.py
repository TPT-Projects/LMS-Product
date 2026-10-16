from rest_framework.routers import SimpleRouter

from .views import SavedViewViewSet

router = SimpleRouter(trailing_slash=False)
router.register("views", SavedViewViewSet, basename="views")

urlpatterns = router.urls
