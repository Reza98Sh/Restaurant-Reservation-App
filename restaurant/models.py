from django.db import models


class Restaurant(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=11)
    
    vip_price_per_seat  =  models.PositiveIntegerField()
    normal_price_per_seat = models.PositiveIntegerField()
    

    # Operating hours
    opening_time = models.TimeField(default='11:00')
    closing_time = models.TimeField(default='23:00')
    

class Table(models.Model):
    # We add a ForeignKey to Restaurant
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='tables')

    class TableType(models.TextChoices):
        NORMAL = 'NORMAL', 'Normal'
        VIP = 'VIP', 'VIP'

    number = models.PositiveIntegerField()
    table_type = models.CharField(max_length=10, choices=TableType.choices)
    capacity = models.PositiveIntegerField()

    class Meta:
        # Table number should be unique PER restaurant
        unique_together = ('restaurant', 'number')

    def __str__(self):
        return f"{self.restaurant.name} - {self.number}"
