# config/celery.py

from celery import Celery
from celery.schedules import crontab
import os

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Load task modules from all registered Django apps
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule - Periodic Tasks
app.conf.beat_schedule = {

    # Task to expire reservations past their payment deadline
    # Runs every minute
    'expire-pending-reservations-by-deadline': {
        'task': 'reservation.tasks.expire_pending_reservations',
        'schedule': 60.0,  # Every 60 seconds
        'options': {
            'expires': 55,
        }
    },
    

}


# Use file-based scheduler instead of database scheduler
app.conf.beat_scheduler = 'celery.beat:PersistentScheduler'
app.conf.beat_schedule_filename = '/app/celerybeat-schedule'