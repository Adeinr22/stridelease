from django import forms

from .models import Lease, Payment, Property, Tenant, Unit


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"
        if user is not None:
            if "property" in self.fields:
                self.fields["property"].queryset = Property.objects.filter(owner=user)
            if "unit" in self.fields:
                self.fields["unit"].queryset = Unit.objects.filter(property__owner=user)
            if "tenant" in self.fields:
                self.fields["tenant"].queryset = Tenant.objects.filter(owner=user)
            if "lease" in self.fields:
                self.fields["lease"].queryset = Lease.objects.filter(
                    unit__property__owner=user,
                    tenant__owner=user,
                )


class PropertyForm(StyledModelForm):
    class Meta:
        model = Property
        fields = ["name", "address"]


class UnitForm(StyledModelForm):
    class Meta:
        model = Unit
        fields = ["property", "unit_number", "floor", "sq_ft", "base_tax_rate", "status"]


class TenantForm(StyledModelForm):
    class Meta:
        model = Tenant
        fields = ["company_name", "contact_name", "email", "phone"]


class LeaseForm(StyledModelForm):
    class Meta:
        model = Lease
        fields = ["unit", "tenant", "start_date", "end_date", "monthly_rent", "cam_share_pct", "status"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        fields = ["lease", "payment_date", "amount", "status", "notes"]
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"})}
