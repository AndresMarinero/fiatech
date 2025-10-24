from django.shortcuts import redirect, render
from ChivoBits_app.models.contaGeneral import Cuenta


def libro(request):
    return render(request, 'ContaGeneral/libroMayor.html')


def catalogo_cuentas(request):
    # Obtener todas las cuentas ordenadas por código
    cuentas = Cuenta.objects.all().order_by('codigo')

    # Calcular estadísticas
    total_cuentas = cuentas.count()
    cuentas_activo = cuentas.filter(tipo='ACTIVO').count()
    cuentas_pasivo = cuentas.filter(tipo='PASIVO').count()
    cuentas_patrimonio = cuentas.filter(tipo='PATRIMONIO').count()
    cuentas_ingreso = cuentas.filter(tipo='INGRESO').count()
    cuentas_gasto = cuentas.filter(tipo='GASTO').count()

    context = {
        'cuentas': cuentas,
        'total_cuentas': total_cuentas,
        'cuentas_activo': cuentas_activo,
        'cuentas_pasivo': cuentas_pasivo,
        'cuentas_patrimonio': cuentas_patrimonio,
        'cuentas_ingreso': cuentas_ingreso,
        'cuentas_gasto': cuentas_gasto
    }
    return render(request, 'ContaGeneral/catalogoCuentas.html', context)
