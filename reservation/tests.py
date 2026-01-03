
from django.test import TestCase
from django.utils import timezone
from datetime import date, time, timedelta

from reservation.models import Reservation, PaymentRecord, PaymentRecord, WaitlistEntry
from reservation.services.reservation import ReservationService
from reservation.services.availability import TableAvailabilityService
from users.models import CustomUser
from restaurant.models import Table

from reservation.services.waitlist import WaitlistService

class ReservationModelTest(TestCase):
    """Unit tests for Reservation model"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test data"""
        from users.models import CustomUser
        from restaurant.models import Table

        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.test_date = date.today() + timedelta(days=1)

    def test_reservation_creation(self):
        """Test basic reservation creation"""
        reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.PENDING
        )

        self.assertIsNotNone(reservation.id)
        self.assertEqual(reservation.status, Reservation.Status.PENDING)

    def test_duration_minutes_calculation(self):
        """Test duration calculation property"""
        reservation = Reservation(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000
        )

        # 2 hours = 120 minutes
        self.assertEqual(reservation.duration_minutes, 120)

    def test_confirm_reservation(self):
        """Test reservation confirmation"""
        reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.PENDING
        )

        reservation.confirm()
        reservation.refresh_from_db()

        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)

    def test_cancel_reservation(self):
        """Test reservation cancellation"""
        reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            status=Reservation.Status.CONFIRMED
        )

        reservation.cancel(reason="Test cancellation")
        reservation.refresh_from_db()

        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)
        self.assertEqual(reservation.cancellation_reason, "Test cancellation")

    def test_payment_deadline(self):
        """Test payment deadline setting"""
        reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000
        )

        reservation.set_payment_deadline(minutes=15)
        reservation.refresh_from_db()

        self.assertIsNotNone(reservation.payment_deadline)
        # Check deadline is approximately 15 minutes from now
        expected_deadline = timezone.now() + timedelta(minutes=15)
        self.assertAlmostEqual(
            reservation.payment_deadline.timestamp(),
            expected_deadline.timestamp(),
            delta=5  # 5 seconds tolerance
        )

    def test_is_payment_expired(self):
        """Test payment expiration check"""
        reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
            payment_deadline=timezone.now() - timedelta(minutes=1)  # Already expired
        )

        self.assertTrue(reservation.is_payment_expired())


class PaymentRecordModelTest(TestCase):
    """Unit tests for PaymentRecord model"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test data"""
        from users.models import CustomUser
        from restaurant.models import Table

        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.test_date = date.today() + timedelta(days=1)

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

    def test_payment_creation(self):
        """Test payment record creation"""
        payment = PaymentRecord.objects.create(
            reservation=self.reservation,
            amount=100000,
            status=PaymentRecord.Status.PENDING
        )

        self.assertIsNotNone(payment.id)
        self.assertEqual(payment.status, PaymentRecord.Status.PENDING)

    def test_payment_verify(self):
        """Test payment verification"""
        payment = PaymentRecord.objects.create(
            reservation=self.reservation,
            amount=100000,
            status=PaymentRecord.Status.PENDING
        )

        payment.verify(ref_id="TEST_REF_123")
        payment.refresh_from_db()
        self.reservation.refresh_from_db()

        self.assertEqual(payment.status, PaymentRecord.Status.VERIFIED)
        self.assertEqual(payment.ref_id, "TEST_REF_123")
        self.assertIsNotNone(payment.verified_at)
        # Reservation should be confirmed
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)

    def test_payment_fail(self):
        """Test payment failure"""
        payment = PaymentRecord.objects.create(
            reservation=self.reservation,
            amount=100000,
            status=PaymentRecord.Status.PENDING
        )

        payment.fail()
        payment.refresh_from_db()

        self.assertEqual(payment.status, PaymentRecord.Status.FAILED)


class ReservationServiceTest(TestCase):
    """Unit tests for ReservationService"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test data"""
        from users.models import CustomUser
        from restaurant.models import Table

        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.test_date = date.today() + timedelta(days=1)





    def test_validate_guest_count_valid(self):
        """Test guest count validation - valid case"""
        is_valid, message = ReservationService.validate_guest_count(
            table=self.table,
            guest_count=2
        )

        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_validate_guest_count_exceeds(self):
        """Test guest count validation - exceeds capacity"""
        is_valid, message = ReservationService.validate_guest_count(
            table=self.table,
            guest_count=100  # Assuming table capacity is less than 100
        )

        self.assertFalse(is_valid)
        self.assertIn("exceeds", message)

    def test_create_reservation_success(self):
        """Test successful reservation creation"""
        reservation, message = ReservationService.create_reservation(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2
        )

        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertIn("successfully", message)
        # Check payment record was created
        self.assertTrue(reservation.payments.exists())

    def test_create_reservation_conflict(self):
        """Test reservation creation with conflict"""
        # Create existing reservation
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
        reservation, message = ReservationService.create_reservation(
            user=self.user,
            table=self.table,
            date=self.test_date,
            start_time=time(13, 0),
            end_time=time(15, 0),
            guest_count=2
        )

        self.assertIsNone(reservation)
        self.assertIn("already reserved", message)


class TableAvailabilityServiceTest(TestCase):
    """Unit tests for TableAvailabilityService"""

    fixtures = ['users.json', 'restaurant.json', 'tables.json']

    def setUp(self):
        """Set up test data"""
        from users.models import CustomUser
        from restaurant.models import Table

        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.test_date = date.today() + timedelta(days=1)

    def test_round_up_to_even(self):
        """Test round up to even number"""
        self.assertEqual(TableAvailabilityService.round_up_to_even(3), 4)
        self.assertEqual(TableAvailabilityService.round_up_to_even(4), 4)
        self.assertEqual(TableAvailabilityService.round_up_to_even(5), 6)
        self.assertEqual(TableAvailabilityService.round_up_to_even(1), 2)

    def test_check_specific_table_availability(self):
        """Test specific table availability check"""
        is_available = TableAvailabilityService.check_specific_table_availability(
            table=self.table,
            check_date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0)
        )

        self.assertTrue(is_available)

    def test_get_available_tables(self):
        """Test getting available tables"""
        from restaurant.models import Restaurant

        restaurant = Restaurant.objects.first()

        tables = TableAvailabilityService.get_available_tables(
            restaurant_id=restaurant.id,
            check_date=self.test_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            party_size=2
        )

        self.assertIsNotNone(tables)
        # Should return queryset
        self.assertTrue(hasattr(tables, 'count'))




class WaitlistModelTest(TestCase):
    """Unit tests for WaitlistEntry model"""

    fixtures = ["users.json", "restaurant.json", "tables.json"]

    def setUp(self):
        self.user = CustomUser.objects.first()
        self.table = Table.objects.first()
        self.future_date = date.today() + timedelta(days=1)

    def test_waitlist_entry_creation(self):
        """Test basic waitlist entry creation"""
        entry = WaitlistEntry.objects.create(
            user=self.user,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.status, WaitlistEntry.Status.WAITING)

    def test_waitlist_notify(self):
        """Test notify method updates status and notified_at"""
        entry = WaitlistEntry.objects.create(
            user=self.user,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        entry.notify()
        entry.refresh_from_db()

        self.assertEqual(entry.status, WaitlistEntry.Status.NOTIFIED)
        self.assertIsNotNone(entry.notified_at)

    def test_waitlist_convert_to_reservation(self):
        """Test converting waitlist entry to reservation"""
        entry = WaitlistEntry.objects.create(
            user=self.user,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        # Create a reservation to link
        reservation = Reservation.objects.create(
            user=self.user,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
            price=100000,
        )

        entry.convert_to_reservation(reservation)
        entry.refresh_from_db()

        self.assertEqual(entry.status, WaitlistEntry.Status.CONVERTED)
        self.assertEqual(entry.reservation, reservation)

    def test_waitlist_expire(self):
        """Test expire method"""
        entry = WaitlistEntry.objects.create(
            user=self.user,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        entry.expire()
        entry.refresh_from_db()

        self.assertEqual(entry.status, WaitlistEntry.Status.EXPIRED)


class WaitlistServiceTest(TestCase):
    """Unit tests for WaitlistService"""

    fixtures = ["users.json", "restaurant.json", "tables.json"]

    def setUp(self):
        self.users = list(CustomUser.objects.all()[:3])
        self.user1 = self.users[0]
        self.user2 = self.users[1] if len(self.users) > 1 else self.user1
        self.table = Table.objects.first()
        self.future_date = date.today() + timedelta(days=1)

    def test_get_first_waiting_entry_empty(self):
        """Test when no waitlist entries exist"""
        entry = WaitlistService.get_first_waiting_entry(
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
        )

        self.assertIsNone(entry)

    def test_get_first_waiting_entry_exact_match(self):
        """Test finding waitlist entry with exact time match"""
        # Create waitlist entry
        waitlist_entry = WaitlistEntry.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        entry = WaitlistService.get_first_waiting_entry(
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.id, waitlist_entry.id)

    def test_get_first_waiting_entry_overlap(self):
        """Test finding waitlist entry with overlapping time"""
        # Waitlist entry: 12:00 - 14:00
        waitlist_entry = WaitlistEntry.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        # Search with overlapping time: 13:00 - 15:00
        entry = WaitlistService.get_first_waiting_entry(
            table=self.table,
            date=self.future_date,
            start_time=time(13, 0),
            end_time=time(15, 0),
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.id, waitlist_entry.id)

    def test_get_first_waiting_entry_no_overlap(self):
        """Test no match when times don't overlap"""
        # Waitlist entry: 12:00 - 14:00
        WaitlistEntry.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        # Search with non-overlapping time: 15:00 - 17:00
        entry = WaitlistService.get_first_waiting_entry(
            table=self.table,
            date=self.future_date,
            start_time=time(15, 0),
            end_time=time(17, 0),
        )

        self.assertIsNone(entry)

    def test_get_first_waiting_entry_fifo_order(self):
        """Test that first created entry is returned (FIFO)"""
        # Create first entry
        entry1 = WaitlistEntry.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        # Create second entry (different user, same time)
        WaitlistEntry.objects.create(
            user=self.user2,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 30),
            end_time=time(14, 30),
            guest_count=2,
        )

        entry = WaitlistService.get_first_waiting_entry(
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
        )

        # First created should be returned
        self.assertEqual(entry.id, entry1.id)

    def test_process_waitlist_notifies_entry(self):
        """Test that process_waitlist marks entry as notified"""
        waitlist_entry = WaitlistEntry.objects.create(
            user=self.user1,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        entry = WaitlistService.process_waitlist(
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
        )

        self.assertIsNotNone(entry)
        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistEntry.Status.NOTIFIED)


class CancelReservationWithWaitlistTest(TestCase):
    """Integration tests for cancellation triggering waitlist"""

    fixtures = ["users.json", "restaurant.json", "tables.json"]

    def setUp(self):
        self.users = list(CustomUser.objects.all()[:3])
        self.user1 = self.users[0]
        self.user2 = self.users[1] if len(self.users) > 1 else self.user1
        self.table = Table.objects.first()
        self.future_date = date.today() + timedelta(days=1)

    def test_cancel_reservation_creates_new_for_waitlist(self):
        """
        Main scenario:
        1. User1 has a confirmed reservation
        2. User2 is in waitlist for same slot
        3. User1 cancels
        4. User2 gets a new reservation created
        """
        # Step 1: Create confirmed reservation for user1
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

        # Step 2: Create waitlist entry for user2
        waitlist_entry = WaitlistEntry.objects.create(
            user=self.user2,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        # Step 3: Cancel reservation
        ReservationService.cancel_reservation(
            reservation=reservation,
            reason="Test cancellation",
        )

        # Step 4: Verify results
        reservation.refresh_from_db()
        waitlist_entry.refresh_from_db()

        # Original reservation should be cancelled
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)

        # Waitlist entry should be converted
        self.assertEqual(waitlist_entry.status, WaitlistEntry.Status.CONVERTED)

        # New reservation should exist for user2
        self.assertIsNotNone(waitlist_entry.reservation)
        new_reservation = waitlist_entry.reservation
        self.assertEqual(new_reservation.user, self.user2)
        self.assertEqual(new_reservation.table, self.table)
        self.assertEqual(new_reservation.status, Reservation.Status.PENDING)

    def test_cancel_reservation_no_waitlist(self):
        """Test cancellation when no one is in waitlist"""
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

        # No waitlist entries

        result = ReservationService.cancel_reservation(
            reservation=reservation,
            reason="No waitlist test",
        )

        self.assertTrue(result)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)

        # No new reservations should be created
        self.assertEqual(
            Reservation.objects.filter(
                table=self.table,
                date=self.future_date,
                status=Reservation.Status.PENDING,
            ).count(),
            0,
        )

    def test_cancel_reservation_waitlist_different_time(self):
        """Test cancellation doesn't match waitlist with different time"""
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

        # Waitlist for different time slot (no overlap)
        waitlist_entry = WaitlistEntry.objects.create(
            user=self.user2,
            table=self.table,
            date=self.future_date,
            start_time=time(18, 0),
            end_time=time(20, 0),
            guest_count=2,
        )

        ReservationService.cancel_reservation(reservation=reservation)

        waitlist_entry.refresh_from_db()

        # Waitlist should NOT be converted (different time)
        self.assertEqual(waitlist_entry.status, WaitlistEntry.Status.WAITING)

    def test_cancel_picks_first_waitlist_entry(self):
        """Test that first waitlist entry (FIFO) gets the slot"""
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

        # First waitlist entry
        entry1 = WaitlistEntry.objects.create(
            user=self.user2,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 0),
            end_time=time(14, 0),
            guest_count=2,
        )

        # Get third user or reuse
        user3 = self.users[2] if len(self.users) > 2 else self.user1

        # Second waitlist entry (created later)
        entry2 = WaitlistEntry.objects.create(
            user=user3,
            table=self.table,
            date=self.future_date,
            start_time=time(12, 30),
            end_time=time(14, 30),
            guest_count=2,
        )

        ReservationService.cancel_reservation(reservation=reservation)

        entry1.refresh_from_db()
        entry2.refresh_from_db()

        # First entry should be converted
        self.assertEqual(entry1.status, WaitlistEntry.Status.CONVERTED)
        self.assertIsNotNone(entry1.reservation)

        # Second entry should still be waiting
        self.assertEqual(entry2.status, WaitlistEntry.Status.WAITING)