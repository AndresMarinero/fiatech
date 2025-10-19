from django.shortcuts import redirect, render


def libro(request):
    return render(request, 'ContaGeneral/libroMayor.html')