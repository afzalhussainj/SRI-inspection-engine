from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path(
        "public/inspections/<str:inspection_id>/links/<str:link_uuid>/",
        views.get_form_fields,
        name="get_form_fields",
    ),
    path(
        "public/inspections/<str:inspection_id>/links/<str:link_uuid>/submit/",
        views.submit_form,
        name="submit_form",
    ),
    path(
        "public/inspections/<str:inspection_id>/links/<str:link_uuid>/pdf/",
        views.get_submission_pdf,
        name="get_submission_pdf",
    ),
]
