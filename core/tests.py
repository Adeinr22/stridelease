from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .auth_forms import SignUpForm
from .dsa import LeaseExpiryTree, PaymentHistory, RenewalQueue
from .models import Lease, Payment, Property, Tenant, Unit


class DataStructureTests(TestCase):
    def test_expiry_tree_returns_leases_in_date_order(self):
        tree = LeaseExpiryTree()
        tree.insert(date(2027, 3, 1), "later")
        tree.insert(date(2027, 1, 1), "earlier")
        tree.insert(date(2027, 2, 1), "middle")

        self.assertEqual(tree.in_order(), ["earlier", "middle", "later"])

    def test_payment_history_traverses_in_both_directions(self):
        history = PaymentHistory()
        history.append("first")
        history.append("second")
        history.append("third")

        self.assertEqual(list(history.chronological()), ["first", "second", "third"])
        self.assertEqual(list(history.newest_first()), ["third", "second", "first"])

    def test_renewal_queue_is_fifo_and_empty_safe(self):
        queue = RenewalQueue()
        queue.enqueue("first")
        queue.enqueue("second")

        self.assertEqual(queue.dequeue(), "first")
        self.assertEqual(queue.dequeue(), "second")
        self.assertIsNone(queue.dequeue())


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="manager", password="safe-test-password")
        self.client.force_login(self.user)
        self.property = Property.objects.create(
            owner=self.user,
            name="Harbor House",
            address="10 Market Street",
        )
        self.unit = Unit.objects.create(
            property=self.property,
            unit_number="4A",
            sq_ft=1200,
            status=Unit.Status.VACANT,
        )
        self.tenant = Tenant.objects.create(owner=self.user, company_name="Northstar Studio")
        self.lease = Lease.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            start_date=date.today() - timedelta(days=365),
            end_date=date.today() + timedelta(days=34),
            monthly_rent=Decimal("2500.00"),
        )

    def test_dashboard_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_renders_live_portfolio_and_payment_data(self):
        Payment.objects.create(
            lease=self.lease,
            payment_date=date.today(),
            amount=Decimal("2500.00"),
            status=Payment.Status.PAID,
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Harbor House")
        self.assertContains(response, "Northstar Studio")
        self.assertContains(response, "$2500")
        self.assertContains(response, "100")

    def test_lease_can_be_updated_and_renewal_reminder_queued(self):
        updated = self.client.post(
            reverse("edit_record", args=["leases", self.lease.pk]),
            {
                "unit": self.unit.pk,
                "tenant": self.tenant.pk,
                "start_date": (date.today() - timedelta(days=365)).isoformat(),
                "end_date": (date.today() + timedelta(days=400)).isoformat(),
                "monthly_rent": "2750.00",
                "cam_share_pct": "0.00",
                "status": Lease.Status.ACTIVE,
            },
        )
        self.assertRedirects(updated, reverse("records", args=["leases"]))
        self.lease.refresh_from_db()
        self.assertEqual(self.lease.monthly_rent, Decimal("2750.00"))

        queued = self.client.post(reverse("queue_renewal", args=[self.lease.pk]))
        self.assertEqual(queued.status_code, 302)
        self.assertEqual(self.lease.notices.count(), 1)

    def test_lease_end_date_must_not_precede_start_date(self):
        response = self.client.post(
            reverse("records", args=["leases"]),
            {
                "unit": self.unit.pk,
                "tenant": self.tenant.pk,
                "start_date": "2027-01-02",
                "end_date": "2027-01-01",
                "monthly_rent": "2500.00",
                "cam_share_pct": "0.00",
                "status": Lease.Status.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lease.objects.count(), 1)
        self.assertContains(response, "must be on or after")

    def test_empty_create_submission_shows_required_field_errors(self):
        response = self.client.post(reverse("records", args=["properties"]), data={})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].is_bound)
        self.assertIn("name", response.context["form"].errors)

    def test_linked_tenant_cannot_be_deleted(self):
        response = self.client.post(reverse("delete_record", args=["tenants", self.tenant.pk]))

        self.assertRedirects(response, reverse("records", args=["tenants"]))
        self.assertTrue(Tenant.objects.filter(pk=self.tenant.pk).exists())

    def test_user_cannot_view_another_users_records(self):
        other_user = get_user_model().objects.create_user(username="another-manager")
        other_property = Property.objects.create(
            owner=other_user,
            name="Private Plaza",
            address="20 Other Street",
        )

        property_list = self.client.get(reverse("records", args=["properties"]))
        dashboard = self.client.get(reverse("dashboard"))
        private_detail = self.client.get(
            reverse("edit_record", args=["properties", other_property.pk])
        )

        self.assertContains(property_list, "Harbor House")
        self.assertNotContains(property_list, "Private Plaza")
        self.assertNotContains(dashboard, "Private Plaza")
        self.assertEqual(private_detail.status_code, 404)

    def test_lease_form_rejects_another_users_unit_and_tenant(self):
        other_user = get_user_model().objects.create_user(username="another-manager")
        other_property = Property.objects.create(
            owner=other_user,
            name="Private Plaza",
            address="20 Other Street",
        )
        other_unit = Unit.objects.create(
            property=other_property,
            unit_number="2B",
            sq_ft=1000,
        )
        other_tenant = Tenant.objects.create(owner=other_user, company_name="Secret Company")

        response = self.client.post(
            reverse("records", args=["leases"]),
            {
                "unit": other_unit.pk,
                "tenant": other_tenant.pk,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=30)).isoformat(),
                "monthly_rent": "1000.00",
                "cam_share_pct": "0.00",
                "status": Lease.Status.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lease.objects.count(), 1)
        self.assertIn("unit", response.context["form"].errors)
        self.assertIn("tenant", response.context["form"].errors)

    def test_notifications_endpoint_returns_only_this_users_alerts(self):
        other_user = get_user_model().objects.create_user(username="another-manager")
        other_property = Property.objects.create(
            owner=other_user,
            name="Private Plaza",
            address="20 Other Street",
        )
        other_unit = Unit.objects.create(
            property=other_property,
            unit_number="2B",
            sq_ft=1000,
        )
        other_tenant = Tenant.objects.create(owner=other_user, company_name="Secret Company")
        Lease.objects.create(
            unit=other_unit,
            tenant=other_tenant,
            start_date=date.today(),
            end_date=date.today(),
            monthly_rent=Decimal("1000.00"),
        )

        response = self.client.get(reverse("notifications"))
        alerts = response.json()["notifications"]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("Northstar Studio" in alert["title"] for alert in alerts))
        self.assertFalse(any("Secret Company" in alert["title"] for alert in alerts))

    def test_switch_account_logs_out_and_returns_to_login(self):
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class SignUpTests(TestCase):
    def test_registration_creates_account_and_signs_user_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-manager",
                "first_name": "Avery",
                "last_name": "Chen",
                "email": "avery@example.com",
                "password1": "M!ghty-Long-Passphrase-984",
                "password2": "M!ghty-Long-Passphrase-984",
            },
        )

        user = get_user_model().objects.get(username="new-manager")
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(user.email, "avery@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_registration_rejects_duplicate_email(self):
        get_user_model().objects.create_user(
            username="existing",
            email="avery@example.com",
            password="another-safe-password",
        )

        form = SignUpForm(
            {
                "username": "new-manager",
                "first_name": "Avery",
                "last_name": "Chen",
                "email": "AVERY@example.com",
                "password1": "M!ghty-Long-Passphrase-984",
                "password2": "M!ghty-Long-Passphrase-984",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_login_page_offers_public_account_registration(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, reverse("signup"))
