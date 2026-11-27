from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Property(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "properties"

    def __str__(self):
        return self.name


class Unit(models.Model):
    class Status(models.TextChoices):
        VACANT = "VACANT", "Vacant"
        OCCUPIED = "OCCUPIED", "Occupied"
        EXPIRING = "EXPIRING", "Expiring"
        OVERDUE = "OVERDUE", "Overdue"

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    unit_number = models.CharField(max_length=32)
    floor = models.CharField(max_length=32, blank=True)
    sq_ft = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    base_tax_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.VACANT)

    class Meta:
        ordering = ["property__name", "unit_number"]
        constraints = [
            models.UniqueConstraint(fields=["property", "unit_number"], name="unique_property_unit")
        ]

    def __str__(self):
        return f"{self.property.name} · {self.unit_number}"


class Tenant(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenants",
        null=True,
        blank=True,
    )
    company_name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name


class Lease(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRING_SOON = "EXPIRING_SOON", "Expiring soon"
        EXPIRED = "EXPIRED", "Expired"
        RENEWED = "RENEWED", "Renewed"

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="leases")
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="leases")
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    cam_share_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["end_date"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The lease end date must be on or after its start date."})

    def __str__(self):
        return f"{self.tenant.company_name} · {self.unit}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PAID = "PAID", "Paid"
        PENDING = "PENDING", "Pending"
        OVERDUE = "OVERDUE", "Overdue"

    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name="payments")
    payment_date = models.DateField()
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PAID)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]


class RenewalNotice(models.Model):
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name="notices")
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    action_type = models.CharField(max_length=40, default="renewal_reminder")
    payload_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["queued_at"]


class ActionLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=80)
    payload_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
