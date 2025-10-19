from django.shortcuts import redirect, render


def costo(request):
    return render(request, 'Costos/costo.html')