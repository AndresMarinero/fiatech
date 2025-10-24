from django.urls import path
from ChivoBits_app.views import contaGeneral

urlpatterns = [
    path('libroMayor/', contaGeneral.libro, name='libroMayor'),
    path('catalogoCuentas/', contaGeneral.catalogo_cuentas, name='catalogoCuentas'),
]