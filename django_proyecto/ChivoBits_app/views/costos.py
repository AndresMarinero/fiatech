from django.shortcuts import redirect, render


def costo(request):
    return render(request, 'Costos/costo.html')
def ucp(request):
    return render(request, 'costos/UCP.html')
def CDM(request):
    return render(request, 'costos/CDM.html')
def cif(request):
    return render(request, 'costos/CIF.html')