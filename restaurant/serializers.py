from rest_framework import serializers
from restaurant import models as restaurant_models
from django.db.models import F, Case, When, IntegerField, Prefetch
from reservation.models import Reservation


class TableSerializer(serializers.ModelSerializer):


    class Meta:
        model = restaurant_models.Table
        fields = ["id",
                  "restaurant",
                  "number",
                  "capacity",
                  "table_type",
                  ]
