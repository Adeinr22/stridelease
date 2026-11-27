from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .auth_forms import SignUpForm
from .dsa import LeaseExpiryTree, PaymentHistory, RenewalQueue
from .forms import LeaseForm, PaymentForm, PropertyForm, TenantForm, UnitForm
from .models import ActionLog, Lease, Payment, Property, RenewalNotice, Tenant, Unit

RECORD_CONFIG = {
    "properties": ("Properties", Property, PropertyForm, "property"),
    "units": ("Units", Unit, UnitForm, "unit"),
    "tenants": ("Tenants", Tenant, TenantForm, "tenant"),
    "leases": ("Leases", Lease, LeaseForm, "lease"),
    "payments": ("Payments", Payment, PaymentForm, "payment"),
}


def owned_records(kind, user):
    models = {
        "properties": Property.objects.filter(owner=user),
        "units": Unit.objects.filter(property__owner=user),
        "tenants": Tenant.objects.filter(owner=user),
        "leases": Lease.objects.filter(unit__property__owner=user, tenant__owner=user),
        "payments": Payment.objects.filter(
            lease__unit__property__owner=user,
            lease__tenant__owner=user,
        ),
    }
    return models[kind]


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account is ready. Welcome to Stridelease!")
        return redirect("dashboard")
    return render(request, "signup.html", {"form": form})


@login_required
def dashboard(request):
    today = timezone.localdate()
    active_leases = Lease.objects.filter(
        status__in=[Lease.Status.ACTIVE, Lease.Status.EXPIRING_SOON],
        end_date__gte=today,
        unit__property__owner=request.user,
        tenant__owner=request.user,
    )
    expiry_tree = LeaseExpiryTree()
    for lease in active_leases.select_related("unit__property", "tenant"):
        expiry_tree.insert(lease.end_date, lease)
    expiring = []
    for lease in expiry_tree.in_order():
        days_until = (lease.end_date - today).days
        if 0 <= days_until <= 90:
            lease.days_until = days_until
            expiring.append(lease)

    month_payments = Payment.objects.filter(
        payment_date__year=today.year,
        payment_date__month=today.month,
        status=Payment.Status.PAID,
        lease__unit__property__owner=request.user,
        lease__tenant__owner=request.user,
    )
    monthly_collected = month_payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    monthly_expected = active_leases.aggregate(total=Sum("monthly_rent"))["total"] or Decimal("0.00")
    unit_count = Unit.objects.filter(property__owner=request.user).count()
    occupied_count = active_leases.values("unit_id").distinct().count()
    recent_payments = list(
        Payment.objects.select_related("lease__tenant", "lease__unit__property")
        .filter(lease__unit__property__owner=request.user, lease__tenant__owner=request.user)
        .order_by("payment_date", "created_at")[:8]
    )
    payment_history = PaymentHistory()
    for payment in recent_payments:
        payment_history.append(payment)

    renewal_queue = RenewalQueue()
    for notice in RenewalNotice.objects.filter(
        sent_at__isnull=True,
        lease__unit__property__owner=request.user,
        lease__tenant__owner=request.user,
    ).select_related("lease__tenant"):
        renewal_queue.enqueue(notice)

    chart_labels = []
    chart_values = []
    for month_offset in range(5, -1, -1):
        month_index = today.year * 12 + today.month - 1 - month_offset
        first_day = today.replace(year=month_index // 12, month=month_index % 12 + 1, day=1)
        next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        total = Payment.objects.filter(
            payment_date__gte=first_day,
            payment_date__lt=next_month,
            status=Payment.Status.PAID,
            lease__unit__property__owner=request.user,
            lease__tenant__owner=request.user,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        chart_labels.append(first_day.strftime("%b"))
        chart_values.append(float(total))

    context = {
        "active_page": "dashboard",
        "monthly_collected": monthly_collected,
        "monthly_expected": monthly_expected,
        "occupancy": round(occupied_count * 100 / unit_count) if unit_count else 0,
        "occupied_count": occupied_count,
        "unit_count": unit_count,
        "expiring_leases": expiring[:5],
        "recent_payments": list(payment_history.newest_first())[:5],
        "renewal_queue": list(renewal_queue),
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "today": today,
    }
    return render(request, "dashboard.html", context)


@login_required
def records(request, kind):
    if kind not in RECORD_CONFIG:
        return redirect("dashboard")
    title, model, form_class, singular = RECORD_CONFIG[kind]
    form = form_class(
        request.POST if request.method == "POST" else None,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        if kind in ("properties", "tenants"):
            record.owner = request.user
        record.save()
        ActionLog.objects.create(
            user=request.user,
            action_type=f"{singular}.created",
            payload_snapshot={"id": record.pk, "label": str(record)},
        )
        messages.success(request, f"{singular.title()} saved.")
        return redirect("records", kind=kind)

    items = owned_records(kind, request.user)
    if kind == "units":
        items = items.select_related("property")
    elif kind == "leases":
        items = items.select_related("tenant", "unit__property")
    elif kind == "payments":
        items = items.select_related("lease__tenant", "lease__unit__property")
    return render(
        request,
        "records.html",
        {
            "active_page": kind,
            "title": title,
            "kind": kind,
            "items": items[:100],
            "form": form,
            "singular": singular,
        },
    )


@login_required
def edit_record(request, kind, record_id):
    if kind not in RECORD_CONFIG:
        return redirect("dashboard")
    title, model, form_class, singular = RECORD_CONFIG[kind]
    record = get_object_or_404(owned_records(kind, request.user), pk=record_id)
    form = form_class(
        request.POST if request.method == "POST" else None,
        instance=record,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        if kind in ("properties", "tenants"):
            record.owner = request.user
        record.save()
        ActionLog.objects.create(
            user=request.user,
            action_type=f"{singular}.updated",
            payload_snapshot={"id": record.pk, "label": str(record)},
        )
        messages.success(request, f"{singular.title()} updated.")
        return redirect("records", kind=kind)
    return render(
        request,
        "record_edit.html",
        {"active_page": kind, "kind": kind, "title": title, "singular": singular, "form": form},
    )


@login_required
def delete_record(request, kind, record_id):
    if kind not in RECORD_CONFIG or kind == "payments":
        return redirect("dashboard")
    title, model, _, singular = RECORD_CONFIG[kind]
    record = get_object_or_404(owned_records(kind, request.user), pk=record_id)
    dependencies = {
        "properties": lambda: record.units.exists(),
        "units": lambda: record.leases.exists(),
        "tenants": lambda: record.leases.exists(),
        "leases": lambda: record.payments.exists(),
    }
    if request.method == "POST":
        if dependencies[kind]():
            messages.error(request, f"This {singular} has linked records and can’t be deleted yet.")
            return redirect("records", kind=kind)
        label = str(record)
        record.delete()
        ActionLog.objects.create(
            user=request.user,
            action_type=f"{singular}.deleted",
            payload_snapshot={"label": label},
        )
        messages.success(request, f"{singular.title()} deleted.")
        return redirect("records", kind=kind)
    return render(
        request,
        "record_delete.html",
        {"active_page": kind, "kind": kind, "title": title, "singular": singular, "record": record},
    )


@login_required
def queue_renewal(request, lease_id):
    lease = get_object_or_404(
        owned_records("leases", request.user).select_related("tenant", "unit"),
        pk=lease_id,
    )
    if request.method == "POST":
        RenewalNotice.objects.get_or_create(
            lease=lease,
            sent_at__isnull=True,
            defaults={
                "payload_snapshot": {
                    "tenant": lease.tenant.company_name,
                    "unit": lease.unit.unit_number,
                    "end_date": lease.end_date.isoformat(),
                }
            },
        )
        messages.success(request, "Renewal reminder added to the action queue.")
    return redirect(reverse("records", kwargs={"kind": "leases"}))


@login_required
def notifications(request):
    today = timezone.localdate()
    cutoff = today + timedelta(days=90)
    alerts = []

    expiring_leases = Lease.objects.filter(
        unit__property__owner=request.user,
        tenant__owner=request.user,
        status__in=[Lease.Status.ACTIVE, Lease.Status.EXPIRING_SOON],
        end_date__gte=today,
        end_date__lte=cutoff,
    ).select_related("tenant", "unit__property")
    for lease in expiring_leases:
        days_left = (lease.end_date - today).days
        alerts.append(
            {
                "type": "lease",
                "title": f"Lease expiring: {lease.tenant.company_name}",
                "message": f"{lease.unit.property.name}, unit {lease.unit.unit_number} · {days_left} day(s) left",
                "url": reverse("records", kwargs={"kind": "leases"}),
                "date": lease.end_date.isoformat(),
            }
        )

    overdue_payments = Payment.objects.filter(
        lease__unit__property__owner=request.user,
        lease__tenant__owner=request.user,
    ).filter(
        Q(status=Payment.Status.OVERDUE)
        | Q(status=Payment.Status.PENDING, payment_date__lt=today)
    ).select_related("lease__tenant", "lease__unit__property")
    for payment in overdue_payments[:10]:
        alerts.append(
            {
                "type": "payment",
                "title": f"Overdue payment: {payment.lease.tenant.company_name}",
                "message": f"{payment.lease.unit.property.name}, unit {payment.lease.unit.unit_number} · ${payment.amount:.2f}",
                "url": reverse("records", kwargs={"kind": "payments"}),
                "date": payment.payment_date.isoformat(),
            }
        )

    renewal_notices = RenewalNotice.objects.filter(
        sent_at__isnull=True,
        lease__unit__property__owner=request.user,
        lease__tenant__owner=request.user,
    ).select_related("lease__tenant", "lease__unit__property")
    for notice in renewal_notices[:10]:
        alerts.append(
            {
                "type": "renewal",
                "title": f"Renewal reminder queued: {notice.lease.tenant.company_name}",
                "message": f"{notice.lease.unit.property.name}, unit {notice.lease.unit.unit_number}",
                "url": reverse("records", kwargs={"kind": "leases"}),
                "date": notice.queued_at.date().isoformat(),
            }
        )

    alerts.sort(key=lambda alert: alert["date"])
    return JsonResponse({"notifications": alerts[:20], "alert_count": len(alerts[:20])})
