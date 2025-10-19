from django.shortcuts import redirect, render


def financiero(request):
    return render(request, 'EstadosFinancieros/estadoFinanciero.html')
