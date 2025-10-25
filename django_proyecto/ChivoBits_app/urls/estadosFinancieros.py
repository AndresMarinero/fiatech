from django.urls import path
from ChivoBits_app.views import estadosFinancieros

urlpatterns = [
    path('estadosFinancieros/', estadosFinancieros.financiero, name='estadosFinancieros'),
    path('estadoResultados/', estadosFinancieros.estadoResultados, name='estadoResultados'),
    path('estadoCapital/', estadosFinancieros.estadoCapital, name='estadoCapital'),

    path('ajustesContables/', estadosFinancieros.ajustes_contables, name='ajustes_contables'),
    path('ajustes/crear/', estadosFinancieros.crear_ajuste, name='crear_ajuste'),
    path('ajustes/cerrar-periodo/', estadosFinancieros.cerrar_periodo, name='cerrar_periodo'),
    path('balanceComprobacion/', estadosFinancieros.balance_comprobacion, name='balance_comprobacion'),

    path('estado-resultados/', estadosFinancieros.estado_resultados, name='estado_resultados'),

]