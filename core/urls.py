from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications, name="notifications"),
    path("<str:kind>/<int:record_id>/edit/", views.edit_record, name="edit_record"),
    path("<str:kind>/<int:record_id>/delete/", views.delete_record, name="delete_record"),
    path("<str:kind>/", views.records, name="records"),
    path("leases/<int:lease_id>/queue-renewal/", views.queue_renewal, name="queue_renewal"),
]
