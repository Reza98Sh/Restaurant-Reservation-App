from rest_framework.routers import DefaultRouter
from django.urls import path, include

from reservation import views

router = DefaultRouter()


urlpatterns = [
    path(
        "availability/",
        views.TableAvailabilityView.as_view(),
        name="table-availability",
    ),
    path(
        "",
        include(
            [
                path(
                    "",
                    views.ReserveTableView.as_view(),
                    name="create-reservation",
                ),
                path(
                    "<int:pk>/cancel/",
                    views.CancelReservationView.as_view(),
                    name="cancel-reservation",
                ),
            ]
        ),
    ),
    path(
        "payment/",
        include(
            [
                path(
                    "verify/",
                    views.PaymentVerifyView.as_view(),
                    name="payment-verification",
                ),
                path(
                    "history/",
                    views.PaymentListView.as_view(),
                    name="user-payments"

                )
            ]
        ),
    ),
]
