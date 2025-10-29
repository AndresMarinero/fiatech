from django.urls import path
from ChivoBits_app.views import costos

urlpatterns = [
    path('costo/', costos.costo, name='costo'),
    path('ucp/', costos.ucp, name='ucp'),
    path('CDM/', costos.CDM, name='CDM'),
    path('cif/', costos.cif, name='cif'),
]