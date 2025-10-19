from django.urls import path
from ChivoBits_app.views import contaGeneral

urlpatterns = [
    path('conta-general/', contaGeneral.libro, name='conta_general'),
]