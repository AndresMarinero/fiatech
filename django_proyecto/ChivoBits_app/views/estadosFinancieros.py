from django.shortcuts import redirect, render


def financiero(request):
    return render(request, 'EstadosFinancieros/estadoFinanciero.html')

def ajustesContables(request):
    return render(request, 'EstadosFinancieros/ajustesContables.html')

def balanceComprobacion(request):
    return render(request, 'EstadosFinancieros/balanceComprobacion.html')

def estadoResultados(request):
    return render(request, 'EstadosFinancieros/estadoResultados.html')

def estadoCapital(request):
    return render(request, 'EstadosFinancieros/estadoCapital.html')
