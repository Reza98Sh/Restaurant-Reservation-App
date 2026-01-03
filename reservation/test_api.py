
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import date, time, timedelta
from users.models import CustomUser
from restaurant.models import Table

from reservation.models import Reservation, PaymentRecord, WaitlistEntry


class TableAvailabilityAPITest(APITestCase):
    """API tests for table availability endpoint"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test client and data"""
        from restaurant.models import Restaurant

        self.client = APIClient()
        self.restaurant = Restaurant.objects.first()
        self.test_date = date.today() + timedelta(days=1)
        self.url = reverse('table-availability')

    def test_get_availability_success(self):
        """Test successful availability check"""
        response = self.client.get(self.url, {
            'restaurant': self.restaurant.id,
            'date': self.test_date.isoformat(),
            'start_time': '12:00',
            'end_time': '14:00',
            'number_of_people': 2
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('query', response.data)



    def test_get_availability_invalid_date(self):
        """Test availability check with invalid date format"""
        response = self.client.get(self.url, {
            'restaurant': self.restaurant.id,
            'date': 'invalid-date',
            'start_time': '12:00',
            'end_time': '14:00',
            'number_of_people': 2
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReserveTableAPITest(APITestCase):
    """API tests for reservation creation endpoint"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test client and data"""
        from users.models import CustomUser
        from restaurant.models import Table

        self.client = APIClient()
        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.test_date = date.today() + timedelta(days=1)
        self.url = reverse('create-reservation')

        # Authenticate user
        self.client.force_authenticate(user=self.user)

    def test_create_reservation_success(self):
        """Test successful reservation creation"""
        data = {
            'table': self.table.id,
            'date': self.test_date.isoformat(),
            'start_time': '12:00',
            'end_time': '14:00',
            'guest_count': 2
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('reservation', response.data)
        self.assertIn('detail', response.data)

    def test_create_reservation_unauthenticated(self):
        """Test reservation creation without authentication"""
        self.client.force_authenticate(user=None)

        data = {
            'table': self.table.id,
            'date': self.test_date.isoformat(),
            'start_time': '12:00',
            'end_time': '14:00',
            'guest_count': 2
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)



    def test_create_reservation_conflict(self):
        """Test reservation creation with time conflict"""
        # Create first reservation
        Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.CONFIRMED
        )

        # Try to create overlapping reservation
        data = {
            'table': self.table.id,
            'date': self.test_date.isoformat(),
            'start_time': '13:00',
            'end_time': '15:00',
            'guest_count': 2
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CancelReservationAPITest(APITestCase):
    """API tests for reservation cancellation endpoint"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test client and data"""
        from users.models import CustomUser
        from restaurant.models import Table

        self.client = APIClient()
        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.test_date = date.today() + timedelta(days=1)

        # Create a reservation to cancel
        self.reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.CONFIRMED
        )
        self.url = reverse('cancel-reservation', kwargs={'pk': self.reservation.id})# Authenticate user
        self.client.force_authenticate(user=self.user)

    def test_cancel_reservation_success(self):
        """Test successful reservation cancellation"""
        data = {'reason': 'Change of plans'}

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CANCELLED)

    def test_cancel_reservation_unauthenticated(self):
        """Test cancellation without authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PaymentAPITest(APITestCase):
    """API tests for payment endpoints"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test client and data"""
        from users.models import CustomUser
        from restaurant.models import Table

        self.client = APIClient()
        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.test_date = date.today() + timedelta(days=1)

        # Create reservation with payment
        self.reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.PENDING
        )

        self.payment = PaymentRecord.objects.create(
            reservation=self.reservation,
            amount=100000,
            status=PaymentRecord.Status.PENDING
        )

        # Authenticate user
        self.client.force_authenticate(user=self.user)

    def test_payment_list(self):
        """Test getting payment history"""
        url = reverse('user-payments')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_payment_detail(self):
        """Test getting payment detail"""
        url = reverse('payment-detail', kwargs={'pk': self.payment.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_payment_verify(self):
        """Test payment verification"""
        url = reverse('payment-verification')

        data = {
            'payment_id': self.payment.id,
            'ref_id': 'TEST_REF_123'
        }

        response = self.client.post(url, data, format='json')

        # Assuming verification logic is implemented
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])



class CancelReservationWithWaitlistAPITest(APITestCase):
    """Integration API test: cancel reservation triggers waitlist"""

    fixtures = ["users.json", "restaurant.json", "tables.json"]

    def setUp(self):
        self.users = list(CustomUser.objects.all()[:3])
        self.user1 = self.users[0]
        self.user2 = self.users[1] if len(self.users) > 1 else self.user1
        self.table = Table.objects.first()
        self.future_date = date.today() + timedelta(days=1)

        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)

    def test_cancel_reservation_converts_waitlist_entry(self):
        """
        Scenario:
        - User1 has CONFIRMED reservation
        - User2 is in WAITLIST
        - User1 cancels via API
        - WaitlistEntry is converted to new PENDING reservation
        """

        # Create confirmed reservation for user1
        reservation = Reservation.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.CONFIRMED,
        )

        # Create waitlist entry for user2
        waitlist_entry = WaitlistEntry.objects.create(
            user=self.user2,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        url = reverse("cancel-reservation", args=[reservation.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        reservation.refresh_from_db()
        waitlist_entry.refresh_from_db()

        # Original reservation cancelled
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)

        # Waitlist entry converted
        self.assertEqual(waitlist_entry.status, WaitlistEntry.Status.CONVERTED)
        self.assertIsNotNone(waitlist_entry.reservation)

        # New reservation correctness
        new_reservation = waitlist_entry.reservation
        self.assertEqual(new_reservation.user, self.user2)
        self.assertEqual(new_reservation.table, self.table)
        self.assertEqual(new_reservation.status, Reservation.Status.PENDING)

    def test_cancel_reservation_no_waitlist(self):
        """Cancel reservation via API when no waitlist exists"""

        reservation = Reservation.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(18, 0),
            end_time=time(20, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.CONFIRMED,
        )

        url = reverse("cancel-reservation", args=[reservation.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)

        # No pending reservations should exist
        self.assertEqual(
            Reservation.objects.filter(
                table=self.table,
                date=self.future_date,
                status=Reservation.Status.PENDING,
            ).count(),
            0,
        )

    def test_cancel_requires_authentication(self):
        """Unauthenticated users cannot cancel reservations"""

        reservation = Reservation.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.CONFIRMED,
        )

        self.client.force_authenticate(user=None)
        url = reverse("cancel-reservation", args=[reservation.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)