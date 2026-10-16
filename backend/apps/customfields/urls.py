from rest_framework.routers import SimpleRouter

from .views import CustomFieldViewSet

router = SimpleRouter(trailing_slash=False)
router.register("custom-fields", CustomFieldViewSet, basename="custom-fields")

urlpatterns = router.urls
