from rest_framework.routers import DefaultRouter

from django.urls import path, include
from restaurant import views

router = DefaultRouter()


urlpatterns = [
    # path(
    #     "table",
    #     include(
    #         [
    #             path(
    #                 "",
    #                 views.AvailableTablesView.as_view(),
    #                 name="table-list",
    #             ),
    #         ]
    #     ),
    # ),
]
