from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from ChivoBits_app.models.contaGeneral import *
from ChivoBits_app.models.estadosFinancieros import *
from django.db import transaction
from django.db.models import Sum, Q, Case, When, Value, DecimalField
from decimal import Decimal


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


def ajustes_contables(request):
    # Obtener periodo activo por defecto
    periodo_activo = PeriodoContable.objects.filter(estado='ACTIVO').first()

    # Si no hay periodo activo, redirigir a creación de periodo
    if not periodo_activo:
        messages.warning(
            request, 'No hay un período contable activo. Debe crear uno primero.')
        # O donde tengas la creación de periodos
        return redirect('libro_mayor')

    # Obtener ajustes del periodo seleccionado (por defecto el activo)
    periodo_id = request.GET.get('periodo_id')
    if periodo_id:
        periodo_seleccionado = get_object_or_404(
            PeriodoContable, id=periodo_id)
    else:
        periodo_seleccionado = periodo_activo

    # Obtener todos los ajustes del periodo seleccionado
    ajustes = Transaccion.objects.filter(
        periodo=periodo_seleccionado,
        es_ajuste=True
    ).select_related('cuenta').order_by('fecha', 'id')

    # Calcular totales
    total_debe = ajustes.aggregate(total=Sum('debe'))['total'] or 0
    total_haber = ajustes.aggregate(total=Sum('haber'))['total'] or 0

    # Obtener todos los periodos para el selector
    periodos = PeriodoContable.objects.all().order_by('-año')

    context = {
        'periodo_activo': periodo_activo,
        'periodo_seleccionado': periodo_seleccionado,
        'ajustes': ajustes,
        'total_debe': total_debe,
        'total_haber': total_haber,
        'periodos': periodos,
        'cuentas': Cuenta.objects.filter(activa=True).order_by('codigo'),
        'puede_ajustar': periodo_seleccionado.estado == 'ACTIVO',
    }
    return render(request, 'EstadosFinancieros/ajustesContables.html', context)


def crear_ajuste(request):
    if request.method == 'POST':
        try:
            import json
            from decimal import Decimal

            # Parsear JSON si viene como JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                fecha = data.get('fecha')
                descripcion = data.get('descripcion')
                cuentas_afectadas = data.get('cuentas_afectadas', [])
            else:
                # Mantener compatibilidad con FormData
                fecha = request.POST.get('fecha')
                descripcion = request.POST.get('descripcion')
                cuentas_afectadas = []  # No disponible en FormData tradicional

            print("=== INICIANDO CREAR AJUSTE ===")
            print(f"Usuario: {request.user}")
            print(f"Fecha: {fecha}, Descripción: {descripcion}")
            print(f"Cuentas afectadas: {cuentas_afectadas}")

            periodo_activo = PeriodoContable.objects.filter(
                estado='ACTIVO').first()
            if not periodo_activo:
                print("ERROR: No hay período activo")
                return JsonResponse({
                    'success': False,
                    'message': 'No hay un período contable activo.'
                })

            if periodo_activo.estado == 'CERRADO':
                print("ERROR: Período cerrado")
                return JsonResponse({
                    'success': False,
                    'message': 'No se pueden hacer ajustes en períodos cerrados.'
                })

            if not fecha or not descripcion:
                print("ERROR: Campos obligatorios faltantes")
                return JsonResponse({
                    'success': False,
                    'message': 'Fecha y descripción son obligatorios.'
                })

            if not cuentas_afectadas or len(cuentas_afectadas) < 2:
                print("ERROR: Se requieren al menos 2 cuentas")
                return JsonResponse({
                    'success': False,
                    'message': 'Se requieren al menos 2 cuentas para un ajuste contable.'
                })

            # Verificar que el ajuste esté balanceado
            total_debe = sum(Decimal(
                str(cuenta['monto'])) for cuenta in cuentas_afectadas if cuenta['tipo'] == 'debe')
            total_haber = sum(Decimal(str(
                cuenta['monto'])) for cuenta in cuentas_afectadas if cuenta['tipo'] == 'haber')

            if total_debe != total_haber:
                print("ERROR: Ajuste desbalanceado")
                return JsonResponse({
                    'success': False,
                    'message': f'El ajuste no está balanceado. DEBE: {total_debe}, HABER: {total_haber}'
                })

            # Crear el ajuste con todas las cuentas
            with transaction.atomic():
                for cuenta_data in cuentas_afectadas:
                    cuenta = get_object_or_404(
                        Cuenta, id=cuenta_data['cuenta_id'])
                    monto = Decimal(str(cuenta_data['monto']))
                    tipo = cuenta_data['tipo']

                    print(
                        f"Creando movimiento - Cuenta: {cuenta.codigo}, Tipo: {tipo}, Monto: {monto}")

                    # Crear transacción para cada cuenta
                    transaccion = Transaccion.objects.create(
                        fecha=fecha,
                        cuenta=cuenta,
                        descripcion=descripcion,
                        debe=monto if tipo == 'debe' else Decimal('0'),
                        haber=monto if tipo == 'haber' else Decimal('0'),
                        es_ajuste=True,
                        periodo=periodo_activo,
                        usuario=request.user if request.user.is_authenticated else None
                    )

                    # Actualizar saldo de la cuenta
                    if tipo == 'debe':
                        cuenta.saldo += monto
                    else:
                        cuenta.saldo -= monto
                    cuenta.save()

                    print(
                        f"Saldo actualizado - {cuenta.codigo}: {cuenta.saldo}")

            print("=== AJUSTE CREADO EXITOSAMENTE ===")
            return JsonResponse({'success': True})

        except Exception as e:
            print(f"ERROR EXCEPCIÓN: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error al crear el ajuste: {str(e)}'
            })

    print("Método no permitido")
    return JsonResponse({'success': False, 'message': 'Método no permitido.'})


def cerrar_periodo(request):
    if request.method == 'POST':
        try:
            periodo_activo = PeriodoContable.objects.filter(
                estado='ACTIVO').first()
            if not periodo_activo:
                messages.error(request, 'No hay un período contable activo.')
                return redirect('ajustes_contables')

            # Verificar que el periodo esté balanceado
            if not periodo_activo.puede_cerrar:
                messages.error(request,
                               'No se puede cerrar el período. Las transacciones no están balanceadas (DEBE ≠ HABER).')
                return redirect('ajustes_contables')

            # Calcular totales para estados financieros
            ventas_totales = calcular_ventas_totales(periodo_activo)
            gastos_totales = calcular_gastos_totales(periodo_activo)
            utilidad_neta = ventas_totales - gastos_totales

            # Cerrar el periodo
            periodo_activo.estado = 'CERRADO'
            periodo_activo.save()

            # Crear registros en todos los estados financieros
            balance_comprobacion = BalanceComprobacion.objects.create(
                año=periodo_activo.año,
                usuario=request.user if request.user.is_authenticated else None
            )

            estado_resultados = EstadoResultados.objects.create(
                año=periodo_activo.año,
                usuario=request.user if request.user.is_authenticated else None,
                ingresos_totales=ventas_totales,  # Se guarda como ingresos_totales en el modelo
                gastos_totales=gastos_totales,
                utilidad_neta=utilidad_neta
            )

            messages.success(
                request, f'Período {periodo_activo.año} cerrado exitosamente. Utilidad neta: ${utilidad_neta:.2f}')
            return redirect('balance_comprobacion')

        except Exception as e:
            messages.error(request, f'Error al cerrar el período: {str(e)}')
            return redirect('balance_comprobacion')
    
    return redirect('balance_comprobacion')


def balance_comprobacion(request):
    # Obtener el período seleccionado
    periodo_id = request.POST.get('periodo_id') or request.GET.get('periodo_id')
    
    if periodo_id:
        try:
            periodo_actual = PeriodoContable.objects.get(id=periodo_id)
        except PeriodoContable.DoesNotExist:
            periodo_actual = PeriodoContable.objects.filter(estado='ACTIVO').first()
            messages.warning(request, "El período seleccionado no existe. Se mostró el período activo.")
    else:
        periodo_actual = PeriodoContable.objects.filter(estado='ACTIVO').first()
    
    # Obtener TODAS las cuentas activas (no solo nivel 3)
    todas_cuentas = Cuenta.objects.filter(activa=True).order_by('codigo')
    
    # Preparar datos para la tabla
    datos_cuentas = []
    totales = {
        'balance_debe': Decimal('0'),
        'balance_haber': Decimal('0'),
        'ajuste_debe': Decimal('0'),
        'ajuste_haber': Decimal('0'),
        'balance_ajustado_debe': Decimal('0'),
        'balance_ajustado_haber': Decimal('0')
    }
    
    for cuenta in todas_cuentas:
        if periodo_actual:
            # Obtener transacciones regulares (no ajustes)
            transacciones_regulares = Transaccion.objects.filter(
                cuenta=cuenta,
                periodo=periodo_actual,
                es_ajuste=False
            )
            
            # Obtener transacciones de ajuste
            transacciones_ajuste = Transaccion.objects.filter(
                cuenta=cuenta,
                periodo=periodo_actual,
                es_ajuste=True
            )
            
            # Calcular saldos regulares
            balance_debe = transacciones_regulares.aggregate(
                total=Sum('debe')
            )['total'] or Decimal('0')
            
            balance_haber = transacciones_regulares.aggregate(
                total=Sum('haber')
            )['total'] or Decimal('0')
            
            # Calcular ajustes
            ajuste_debe = transacciones_ajuste.aggregate(
                total=Sum('debe')
            )['total'] or Decimal('0')
            
            ajuste_haber = transacciones_ajuste.aggregate(
                total=Sum('haber')
            )['total'] or Decimal('0')
            
            # APLICAR FÓRMULA EXACTA
            if balance_debe > balance_haber:  # La cuenta tiene saldo DEUDOR
                saldo_deudor = balance_debe - balance_haber
                # FÓRMULA: Saldo Deudor + Ajuste DEBE - Ajuste HABER
                resultado = saldo_deudor + ajuste_debe - ajuste_haber
                if resultado > 0:
                    balance_ajustado_debe = resultado
                    balance_ajustado_haber = Decimal('0')
                else:  # Si el resultado es negativo o cero
                    balance_ajustado_debe = Decimal('0')
                    balance_ajustado_haber = abs(resultado) if resultado < 0 else Decimal('0')
                    
            elif balance_haber > balance_debe:  # La cuenta tiene saldo ACREEDOR
                saldo_acreedor = balance_haber - balance_debe
                # FÓRMULA: Saldo Acreedor + Ajuste HABER - Ajuste DEBE
                resultado = saldo_acreedor + ajuste_haber - ajuste_debe
                if resultado > 0:
                    balance_ajustado_debe = Decimal('0')
                    balance_ajustado_haber = resultado
                else:  # Si el resultado es negativo o cero
                    balance_ajustado_debe = abs(resultado) if resultado < 0 else Decimal('0')
                    balance_ajustado_haber = Decimal('0')
                    
            else:  # Saldo cero (balance_debe = balance_haber)
                # Si no hay saldo inicial, los ajustes determinan la posición
                neto_ajustes = ajuste_debe - ajuste_haber
                if neto_ajustes > 0:
                    balance_ajustado_debe = neto_ajustes
                    balance_ajustado_haber = Decimal('0')
                elif neto_ajustes < 0:
                    balance_ajustado_debe = Decimal('0')
                    balance_ajustado_haber = abs(neto_ajustes)
                else:
                    balance_ajustado_debe = Decimal('0')
                    balance_ajustado_haber = Decimal('0')
            
        else:
            # Sin período seleccionado, mostrar ceros
            balance_debe = Decimal('0')
            balance_haber = Decimal('0')
            ajuste_debe = Decimal('0')
            ajuste_haber = Decimal('0')
            balance_ajustado_debe = Decimal('0')
            balance_ajustado_haber = Decimal('0')
        
        # Solo mostrar cuentas que tengan movimientos
        if balance_debe > 0 or balance_haber > 0 or ajuste_debe > 0 or ajuste_haber > 0 or balance_ajustado_debe > 0 or balance_ajustado_haber > 0:
            datos_cuenta = {
                'id': cuenta.id,
                'codigo': cuenta.codigo,
                'nombre': cuenta.nombre,
                'tipo': cuenta.tipo,
                'balance_debe': balance_debe,
                'balance_haber': balance_haber,
                'ajuste_debe': ajuste_debe,
                'ajuste_haber': ajuste_haber,
                'balance_ajustado_debe': balance_ajustado_debe,
                'balance_ajustado_haber': balance_ajustado_haber,
            }
            
            # Sumar a totales
            totales['balance_debe'] += balance_debe
            totales['balance_haber'] += balance_haber
            totales['ajuste_debe'] += ajuste_debe
            totales['ajuste_haber'] += ajuste_haber
            totales['balance_ajustado_debe'] += balance_ajustado_debe
            totales['balance_ajustado_haber'] += balance_ajustado_haber
            
            datos_cuentas.append(datos_cuenta)
    
    # Obtener todos los períodos disponibles
    periodos = PeriodoContable.objects.all().order_by('-año')
    
    context = {
        'cuentas': datos_cuentas,
        'totales': totales,
        'periodos': periodos,
        'periodo_actual': periodo_actual,
        'fecha_balance': periodo_actual.fecha_fin.strftime("%d de %B de %Y") if periodo_actual else None
    }
    
    return render(request, 'EstadosFinancieros/balanceComprobacion.html', context)

def calcular_ventas_totales(periodo):
    """
    Calcula las ventas totales (ingresos por servicios de software)
    """
    from django.db.models import Sum
    from decimal import Decimal
    
    # Buscar cuentas de ingresos (grupo 51 en el catálogo)
    cuentas_ventas = Cuenta.objects.filter(
        codigo__startswith='51'  # Ingresos por servicios
    )
    
    ventas = Transaccion.objects.filter(
        periodo=periodo,
        cuenta__in=cuentas_ventas,
        es_ajuste=False
    ).aggregate(total=Sum('haber'))['total'] or Decimal('0')
    
    return ventas

def calcular_gastos_totales(periodo):
    """
    Calcula los gastos totales (grupos 42 y 43)
    """
    from django.db.models import Sum
    from decimal import Decimal
    
    # Buscar cuentas de gastos (grupos 42 y 43)
    cuentas_gastos = Cuenta.objects.filter(
        codigo__startswith='42'  # Costos indirectos
    ) | Cuenta.objects.filter(
        codigo__startswith='43'  # Gastos
    )
    
    gastos = Transaccion.objects.filter(
        periodo=periodo,
        cuenta__in=cuentas_gastos,
        es_ajuste=False
    ).aggregate(total=Sum('debe'))['total'] or Decimal('0')
    
    return gastos

def estado_resultados(request):
    # Obtener el período seleccionado
    periodo_id = request.POST.get('periodo_id') or request.GET.get('periodo_id')
    
    if periodo_id:
        try:
            periodo_actual = PeriodoContable.objects.get(id=periodo_id)
        except PeriodoContable.DoesNotExist:
            periodo_actual = PeriodoContable.objects.filter(estado='CERRADO').first()
            messages.warning(request, "El período seleccionado no existe.")
    else:
        periodo_actual = PeriodoContable.objects.filter(estado='CERRADO').first()

    # Inicializar datos
    ingresos = []
    gastos = []
    total_ingresos = Decimal('0')
    total_gastos = Decimal('0')
    utilidad_bruta = Decimal('0')
    fecha_inicio = ""
    fecha_fin = ""

    if periodo_actual:
        # Obtener fechas del período
        fecha_inicio = periodo_actual.fecha_inicio
        fecha_fin = periodo_actual.fecha_fin
        
        # Buscar cuentas de INGRESO (grupo 51)
        cuentas_ingresos = Cuenta.objects.filter(
            Q(codigo__startswith='51') | Q(tipo='INGRESO')
        )
        
        # Buscar cuentas de GASTO (grupos 42, 43 y 41 si existen)
        cuentas_gastos = Cuenta.objects.filter(
            Q(codigo__startswith='41') | Q(codigo__startswith='42') | 
            Q(codigo__startswith='43') | Q(tipo='GASTO')
        )
        
        # Calcular ingresos
        for cuenta in cuentas_ingresos:
            transacciones = Transaccion.objects.filter(
                cuenta=cuenta,
                periodo=periodo_actual
            ).aggregate(
                total_debe=Sum('debe'),
                total_haber=Sum('haber')
            )
            
            saldo_haber = transacciones['total_haber'] or Decimal('0')
            saldo_debe = transacciones['total_debe'] or Decimal('0')
            
            # Para cuentas de ingreso, el saldo está en el HABER
            if saldo_haber > 0:
                ingresos.append({
                    'codigo': cuenta.codigo,
                    'nombre': cuenta.nombre,
                    'monto': saldo_haber
                })
                total_ingresos += saldo_haber
        
        # Calcular gastos
        for cuenta in cuentas_gastos:
            transacciones = Transaccion.objects.filter(
                cuenta=cuenta,
                periodo=periodo_actual
            ).aggregate(
                total_debe=Sum('debe'),
                total_haber=Sum('haber')
            )
            
            saldo_debe = transacciones['total_debe'] or Decimal('0')
            saldo_haber = transacciones['total_haber'] or Decimal('0')
            
            # Para cuentas de gasto, el saldo está en el DEBE
            if saldo_debe > 0:
                gastos.append({
                    'codigo': cuenta.codigo,
                    'nombre': cuenta.nombre,
                    'monto': saldo_debe
                })
                total_gastos += saldo_debe
        
        # Calcular utilidad bruta
        utilidad_bruta = total_ingresos - total_gastos
    
    # Obtener todos los períodos disponibles
    periodos = PeriodoContable.objects.all().order_by('-año')
    
    context = {
        'ingresos': ingresos,
        'gastos': gastos,
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
        'utilidad_bruta': utilidad_bruta,
        'periodo_actual': periodo_actual,
        'periodos': periodos,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }
    
    return render(request, 'EstadosFinancieros/estadoResultados.html', context)

def estado_capital(request):
    # Obtener el período seleccionado (igual que en estado_resultados)
    periodo_id = request.POST.get('periodo_id') or request.GET.get('periodo_id')
    
    if periodo_id:
        try:
            periodo_actual = PeriodoContable.objects.get(id=periodo_id)
        except PeriodoContable.DoesNotExist:
            periodo_actual = PeriodoContable.objects.filter(estado='CERRADO').first()
            messages.warning(request, "El período seleccionado no existe.")
    else:
        periodo_actual = PeriodoContable.objects.filter(estado='CERRADO').first()

    # Inicializar datos
    capital_inicial = Decimal('0')
    utilidad_bruta = Decimal('0')
    reservas_actuales = Decimal('0')

    if periodo_actual:
        # Obtener año del período
        año = periodo_actual.año
        
        # 1. OBTENER CAPITAL SOCIAL INICIAL (cuenta 3101)
        try:
            cuenta_capital = Cuenta.objects.get(codigo='3101')
            transacciones_capital = Transaccion.objects.filter(
                cuenta=cuenta_capital,
                periodo=periodo_actual
            ).aggregate(
                total_debe=Sum('debe'),
                total_haber=Sum('haber')
            )
            
            # Para capital social, el saldo está en el HABER (crédito natural)
            saldo_haber = transacciones_capital['total_haber'] or Decimal('0')
            saldo_debe = transacciones_capital['total_debe'] or Decimal('0')
            capital_inicial = saldo_haber - saldo_debe
            
        except Cuenta.DoesNotExist:
            capital_inicial = Decimal('0')
        
        # 2. OBTENER RESERVAS ACTUALES (cuenta 3102)
        try:
            cuenta_reservas = Cuenta.objects.get(codigo='3102')
            transacciones_reservas = Transaccion.objects.filter(
                cuenta=cuenta_reservas,
                periodo=periodo_actual
            ).aggregate(
                total_debe=Sum('debe'),
                total_haber=Sum('haber')
            )
            
            # Para reservas, el saldo está en el HABER (crédito natural)
            saldo_haber = transacciones_reservas['total_haber'] or Decimal('0')
            saldo_debe = transacciones_reservas['total_debe'] or Decimal('0')
            reservas_actuales = saldo_haber - saldo_debe
            
        except Cuenta.DoesNotExist:
            reservas_actuales = Decimal('0')
        
        # 3. OBTENER UTILIDAD BRUTA (del estado de resultados del mismo periodo)
        # Buscar cuentas de INGRESO (grupo 51)
        cuentas_ingresos = Cuenta.objects.filter(
            Q(codigo__startswith='51') | Q(tipo='INGRESO')
        )
        
        # Buscar cuentas de GASTO (grupos 41, 42, 43)
        cuentas_gastos = Cuenta.objects.filter(
            Q(codigo__startswith='41') | Q(codigo__startswith='42') | 
            Q(codigo__startswith='43') | Q(tipo='GASTO')
        )
        
        total_ingresos = Decimal('0')
        total_gastos = Decimal('0')
        
        # Calcular ingresos totales
        for cuenta in cuentas_ingresos:
            transacciones = Transaccion.objects.filter(
                cuenta=cuenta,
                periodo=periodo_actual
            ).aggregate(
                total_haber=Sum('haber')
            )
            saldo_haber = transacciones['total_haber'] or Decimal('0')
            total_ingresos += saldo_haber
        
        # Calcular gastos totales
        for cuenta in cuentas_gastos:
            transacciones = Transaccion.objects.filter(
                cuenta=cuenta,
                periodo=periodo_actual
            ).aggregate(
                total_debe=Sum('debe')
            )
            saldo_debe = transacciones['total_debe'] or Decimal('0')
            total_gastos += saldo_debe
        
        # Calcular utilidad bruta
        utilidad_bruta = total_ingresos - total_gastos
        
        # Si hay pérdida, establecer en 0
        if utilidad_bruta < 0:
            utilidad_bruta = Decimal('0')
    
    else:
        # Si no hay período, mostrar ceros
        año = 2024
        capital_inicial = Decimal('0')
        utilidad_bruta = Decimal('0')
        reservas_actuales = Decimal('0')
    
    # CÁLCULOS DEL ESTADO DE CAPITAL
    reinversion = utilidad_bruta * Decimal('0.60')  # 60% para reinversión
    reservas_utilidad = utilidad_bruta * Decimal('0.40')  # 40% para reservas
    
    capital_final = capital_inicial + reinversion
    reservas_totales = reservas_actuales + reservas_utilidad
    
    incremento_capital = reinversion
    porcentaje_incremento = (incremento_capital / capital_inicial * 100) if capital_inicial > 0 else 0
    
    # Obtener todos los períodos disponibles
    periodos = PeriodoContable.objects.all().order_by('-año')
    
    context = {
        'año': año,
        'capital_inicial': capital_inicial,
        'utilidad_ejercicio': utilidad_bruta,  # Se usa utilidad_bruta del estado de resultados
        'reinversion': reinversion,
        'reservas_utilidad': reservas_utilidad,
        'reservas_actuales': reservas_actuales,
        'reservas_totales': reservas_totales,
        'capital_final': capital_final,
        'incremento_capital': incremento_capital,
        'porcentaje_incremento': porcentaje_incremento,
        'periodo_actual': periodo_actual,
        'periodos': periodos,
    }
    
    return render(request, 'EstadosFinancieros/estadoCapital.html', context)