from django.urls import path, include

urlpatterns = [
    path('', include('fiatech_app.urls.usuario')),
    path('', include('fiatech_app.urls.contaGeneral')),
    path('', include('fiatech_app.urls.costos')),
    path('', include('fiatech_app.urls.estadosFinancieros')),
]