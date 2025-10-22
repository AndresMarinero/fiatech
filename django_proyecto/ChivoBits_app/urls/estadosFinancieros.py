from django.urls import path
from ChivoBits_app.views import estadosFinancieros

urlpatterns = [
    path('estadosFinancieros/', estadosFinancieros.financiero, name='estadosFinancieros'),
    path('ajustesContables/', estadosFinancieros.ajustesContables, name='ajustesContables'),
    path('balanceComprobacion/', estadosFinancieros.balanceComprobacion, name='balanceComprobacion'),
    path('estadoResultados/', estadosFinancieros.estadoResultados, name='estadoResultados'),
    path('estadoCapital/', estadosFinancieros.estadoCapital, name='estadoCapital'),
]