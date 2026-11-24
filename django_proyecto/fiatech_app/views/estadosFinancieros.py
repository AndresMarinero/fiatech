from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
# Asumo que tus modelos están en esta ruta
from fiatech_app.models.contaGeneral import *
# Asumo que tus modelos están en esta ruta
from fiatech_app.models.estadosFinancieros import *
from django.db import transaction
from django.db.models import Sum, Q, Case, When, Value, DecimalField
from decimal import Decimal


def financiero(request):
    return render(request, 'EstadosFinancieros/estadoFinanciero.html')

# --- SIN CAMBIOS EN ESTA VISTA ---
def ajustes_contables(request):

    # Obtener el período ACTIVO por defecto
    periodo_activo = PeriodoContable.objects.filter(
        estado='ACTIVO'
    ).first()

    # Obtener el período seleccionado
    periodo_id = request.GET.get('periodo_id')

    if periodo_id:
        periodo_seleccionado = get_object_or_404(
            PeriodoContable,
            id=periodo_id
        )
    else:
        periodo_seleccionado = periodo_activo

    # Obtener ajustes del período seleccionado
    if periodo_seleccionado:

        ajustes = Transaccion.objects.filter(
            periodo=periodo_seleccionado,
            es_ajuste=True
        ).select_related('cuenta').order_by('fecha', 'id')

        # Calcular totales
        total_debe = ajustes.aggregate(
            total=Sum('debe')
        )['total'] or Decimal('0')

        total_haber = ajustes.aggregate(
            total=Sum('haber')
        )['total'] or Decimal('0')

    else:

        ajustes = Transaccion.objects.none()
        total_debe = Decimal('0')
        total_haber = Decimal('0')

    # Obtener todos los períodos para consultar
    periodos = PeriodoContable.objects.all().order_by('-año')

    # Permitir ajustes únicamente en períodos ACTIVOS
    puede_ajustar = (
        periodo_seleccionado is not None
        and periodo_seleccionado.estado == 'ACTIVO'
    )

    # Permitir generar estados definitivos en períodos CERRADOS
    puede_generar_estados = (
        periodo_seleccionado is not None
        and periodo_seleccionado.estado == 'CERRADO'
    )

    context = {
        'periodo_activo': periodo_activo,
        'periodo_seleccionado': periodo_seleccionado,
        'ajustes': ajustes,
        'total_debe': total_debe,
        'total_haber': total_haber,
        'periodos': periodos,

        'cuentas': Cuenta.objects.filter(
            activa=True,
            nivel=3
        ).order_by('codigo'),

        'puede_ajustar': puede_ajustar,
        'puede_generar_estados': puede_generar_estados,
    }

    return render(
        request,
        'EstadosFinancieros/ajustesContables.html',
        context
    )

# --- SIN CAMBIOS EN ESTA VISTA ---
# (Nota: La lógica de cuenta.saldo += / -= monto es simplista y fallará
# si no se tiene en cuenta la naturaleza (deudora/acreedora) de la cuenta,
# pero no afecta a la LECTURA de los reportes, que es el problema actual)
def crear_ajuste(request):
    if request.method == 'POST':
        try:
            import json
            from decimal import Decimal

            # Parsear JSON si viene como JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                periodo_id = data.get('periodo_id')
                fecha = data.get('fecha')
                descripcion = data.get('descripcion')
                cuentas_afectadas = data.get('cuentas_afectadas', [])
            else:
                # Mantener compatibilidad con FormData
                periodo_id = request.POST.get('periodo_id')
                fecha = request.POST.get('fecha')
                descripcion = request.POST.get('descripcion')
                cuentas_afectadas = []  # El formulario actual utiliza JSON

            print("=== INICIANDO CREAR AJUSTE ===")
            print(f"Usuario: {request.user}")
            print(f"Fecha: {fecha}, Descripción: {descripcion}")
            print(f"Cuentas afectadas: {cuentas_afectadas}")

            # Obtener el período seleccionado desde el formulario
            # Obtener el período seleccionado
            if not periodo_id:
                return JsonResponse({
                    'success': False,
                    'message': 'No se recibió el período contable.'
                }, status=400)

            try:
                periodo_activo = PeriodoContable.objects.get(
                    id=periodo_id
                )
            except (PeriodoContable.DoesNotExist, ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'message': 'El período seleccionado no existe.'
                }, status=400)

            # Verificar que permita realizar ajustes
            if periodo_activo.estado != 'ACTIVO':
                return JsonResponse({
                    'success': False,
                    'message': (
                        'Solo se pueden registrar ajustes '
                        'en períodos contables activos.'
                    )
                }, status=400)
            # --- FIN CORRECIÓN ---
            # (Lo dejo como estaba para no alterar tu flujo, pero la validación es extraña)

            from datetime import date

            try:
                fecha_ajuste = date.fromisoformat(fecha)
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'message': 'La fecha del ajuste no es válida.'
                }, status=400)

            if not (
                periodo_activo.fecha_inicio
                <= fecha_ajuste
                <= periodo_activo.fecha_fin
            ):
                return JsonResponse({
                    'success': False,
                    'message': (
                        'La fecha del ajuste debe estar dentro '
                        'del período contable seleccionado.'
                    )
                }, status=400)

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

            # Crear el ajuste con todas las cuentas; todas las líneas comparten número.
            with transaction.atomic():
                ultimo = (Transaccion.objects.filter(periodo=periodo_activo)
                          .order_by('-numero_transaccion').first())
                numero = ultimo.numero_transaccion + 1 if ultimo else 1
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
                        usuario=request.user if request.user.is_authenticated and isinstance(request.user, Usuario) else None,
                        numero_transaccion=numero
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

# --- SIN CAMBIOS EN ESTA VISTA ---
def cerrar_periodo(request):
    if request.method == 'POST':
        try:
            periodo_id = request.POST.get('periodo_id')
            periodo_activo = (get_object_or_404(PeriodoContable, pk=periodo_id)
                              if periodo_id else PeriodoContable.objects.filter(estado='ACTIVO').first())
            if not periodo_activo or periodo_activo.estado != 'ACTIVO':
                messages.error(request, 'El período seleccionado no está activo.')
                return redirect('libro_mayor')  # Redirigir al libro mayor

            # Verificar que el periodo esté balanceado
            if not periodo_activo.puede_cerrar:
                messages.error(request,
                              'No se puede cerrar el período. Las transacciones no están balanceadas (DEBE ≠ HABER).')
                return redirect('libro_mayor')

            # Cerrar el periodo (ACTIVO → CERRADO)
            periodo_activo.estado = 'CERRADO'
            periodo_activo.save()

            messages.success(
                request, f'Período {periodo_activo.año} cerrado exitosamente. Ya puede generar los estados financieros definitivos.')
            return redirect('ajustes_contables')

        except Exception as e:
            messages.error(request, f'Error al cerrar el período: {str(e)}')
            return redirect('libro_mayor')

    return redirect('libro_mayor')

# --- MODIFICADO PARA USAR LA LÓGICA CORRECTA DE CÁLCULO ---
def calcular_totales_balance_general(periodo):
    """Calcula activos netos, pasivos y patrimonio desde los movimientos del período."""
    datos = _obtener_datos_balance_general(periodo)
    return {
        'activos': datos['activos_netos'],
        'pasivos': datos['pasivos_netos'],
        'patrimonio': datos['patrimonio_neto'],
        'cuadra': datos['balance_cuadra'],
    }



def generar_estados_financieros(request):
    """Genera los registros definitivos solo después del cierre del período."""
    if request.method != 'POST':
        return redirect('ajustes_contables')

    periodo_id = request.POST.get('periodo_id')
    if not periodo_id:
        messages.error(request, 'Seleccione un período para generar los estados.')
        return redirect('ajustes_contables')

    try:
        with transaction.atomic():
            periodo = get_object_or_404(
                PeriodoContable.objects.select_for_update(), pk=periodo_id
            )
            if periodo.estado != 'CERRADO':
                messages.error(request, 'Solo pueden generarse estados definitivos de períodos CERRADOS.')
                return redirect('ajustes_contables')

            if not periodo.puede_cerrar:
                messages.error(request, 'Los movimientos del período no están balanceados.')
                return redirect('ajustes_contables')

            if (BalanceComprobacion.objects.filter(año=periodo.año).exists() or
                    EstadoResultados.objects.filter(año=periodo.año).exists() or
                    BalanceGeneral.objects.filter(año=periodo.año).exists()):
                messages.error(request, 'Ya existen registros financieros definitivos para este año. Revise antes de continuar.')
                return redirect('ajustes_contables')

            ingresos = calcular_ventas_totales(periodo, incluir_ajustes=True)
            gastos = calcular_gastos_totales(periodo, incluir_ajustes=True)
            utilidad = ingresos - gastos
            usuario = None
            # El modelo Usuario del proyecto podría ser independiente del auth.User.
            # Evitar asignar un tipo de usuario incompatible.
            if request.user.is_authenticated and isinstance(request.user, Usuario):
                usuario = request.user

            # Validar el balance antes de crear cualquier registro definitivo.
            resumen = calcular_totales_balance_general(periodo)
            if not resumen['cuadra']:
                messages.error(request, 'No se puede finalizar: el balance general no cuadra.')
                return redirect('ajustes_contables')

            BalanceComprobacion.objects.create(año=periodo.año, usuario=usuario)
            EstadoResultados.objects.create(
                año=periodo.año, usuario=usuario,
                ingresos_totales=ingresos, gastos_totales=gastos, utilidad_neta=utilidad
            )
            BalanceGeneral.objects.create(
                año=periodo.año, usuario=usuario,
                activos_totales=resumen['activos'],
                pasivos_totales=resumen['pasivos'],
                patrimonio_total=resumen['patrimonio']
            )
            periodo.estado = 'FINALIZADO'
            periodo.save(update_fields=['estado'])

        messages.success(request, f'Estados definitivos del período {periodo.año} generados correctamente.')
        return redirect(f"{reverse('balance_comprobacion')}?periodo_id={periodo.pk}")
    except Exception as exc:
        messages.error(request, f'No se pudieron generar los estados definitivos: {exc}')
        return redirect('ajustes_contables')



def balance_comprobacion(request):
    periodo_id = request.POST.get('periodo_id') or request.GET.get('periodo_id')
    if periodo_id:
        periodo_actual = get_object_or_404(PeriodoContable, pk=periodo_id)
    else:
        periodo_actual = (PeriodoContable.objects.filter(estado='ACTIVO').first()
                          or PeriodoContable.objects.filter(estado='CERRADO').first()
                          or PeriodoContable.objects.filter(estado='FINALIZADO').first())

    # Obtener TODAS las cuentas activas (no solo nivel 3)
    todas_cuentas = Cuenta.objects.all().order_by('codigo')

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

            # Calcular saldos regulares - CORRECCIÓN: CALCULAR SALDO NETO
            total_debe_regulares = transacciones_regulares.aggregate(
                total=Sum('debe')
            )['total'] or Decimal('0')

            total_haber_regulares = transacciones_regulares.aggregate(
                total=Sum('haber')
            )['total'] or Decimal('0')

            # CALCULAR SALDO NETO PARA BALANCE DE COMPROBACIÓN
            saldo_neto = total_debe_regulares - total_haber_regulares

            if saldo_neto > 0:
                balance_debe = saldo_neto
                balance_haber = Decimal('0')
            elif saldo_neto < 0:
                balance_debe = Decimal('0')
                balance_haber = abs(saldo_neto)
            else:
                balance_debe = Decimal('0')
                balance_haber = Decimal('0')

            # Calcular ajustes
            ajuste_debe = transacciones_ajuste.aggregate(
                total=Sum('debe')
            )['total'] or Decimal('0')

            ajuste_haber = transacciones_ajuste.aggregate(
                total=Sum('haber')
            )['total'] or Decimal('0')

            # APLICAR FÓRMULA EXACTA PARA BALANCE AJUSTADO
            if balance_debe > 0:  # La cuenta tiene saldo DEUDOR
                saldo_deudor = balance_debe
                # FÓRMULA: Saldo Deudor + Ajuste DEBE - Ajuste HABER
                resultado = saldo_deudor + ajuste_debe - ajuste_haber
                if resultado > 0:
                    balance_ajustado_debe = resultado
                    balance_ajustado_haber = Decimal('0')
                else:  # Si el resultado es negativo o cero
                    balance_ajustado_debe = Decimal('0')
                    balance_ajustado_haber = abs(
                        resultado) if resultado < 0 else Decimal('0')

            elif balance_haber > 0:  # La cuenta tiene saldo ACREEDOR
                saldo_acreedor = balance_haber
                # FÓRMULA: Saldo Acreedor + Ajuste HABER - Ajuste DEBE
                resultado = saldo_acreedor + ajuste_haber - ajuste_debe
                if resultado > 0:
                    balance_ajustado_debe = Decimal('0')
                    balance_ajustado_haber = resultado
                else:  # Si el resultado es negativo o cero
                    balance_ajustado_debe = abs(
                        resultado) if resultado < 0 else Decimal('0')
                    balance_ajustado_haber = Decimal('0')

            else:  # Saldo cero
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
        'fecha_balance': periodo_actual.fecha_fin.strftime("%d de %B de %Y") if periodo_actual else None,
        # ENVIAR EL ESTADO DEL PERIODO AL TEMPLATE
        'estado_periodo': periodo_actual.estado if periodo_actual else None,
    }

    return render(request, 'EstadosFinancieros/balanceComprobacion.html', context)


# --- MODIFICADO PARA CALCULAR SALDO NETO ---
def calcular_ventas_totales(periodo, incluir_ajustes=False):
    """
    Calcula las ventas totales (ingresos por servicios de software)
    Calcula el saldo neto (Haber - Debe)
    """
    from django.db.models import Sum
    from decimal import Decimal

    cuentas_ventas = Cuenta.objects.filter(
        Q(codigo__startswith='5') | Q(tipo='INGRESO')
    )

    # --- INICIO DE MODIFICACIÓN ---
    query = Transaccion.objects.filter(
        periodo=periodo,
        cuenta__in=cuentas_ventas
    )
    
    if not incluir_ajustes:
        query = query.filter(es_ajuste=False)

    ventas_agg = query.aggregate(
        total_debe=Sum('debe'),
        total_haber=Sum('haber')
    )
    
    total_debe = ventas_agg['total_debe'] or Decimal('0')
    total_haber = ventas_agg['total_haber'] or Decimal('0')

    return total_haber - total_debe
    # --- FIN DE MODIFICACIÓN ---


# --- MODIFICADO PARA CALCULAR SALDO NETO ---
def calcular_gastos_totales(periodo, incluir_ajustes=False):
    """
    Calcula los gastos totales (grupos 41, 42 y 43)
    Calcula el saldo neto (Debe - Haber)
    """
    from django.db.models import Sum
    from decimal import Decimal

    cuentas_gastos = Cuenta.objects.filter(
        Q(codigo__startswith='4') | Q(tipo='GASTO')
    )

    # --- INICIO DE MODIFICACIÓN ---
    query = Transaccion.objects.filter(
        periodo=periodo,
        cuenta__in=cuentas_gastos
    )
    
    if not incluir_ajustes:
        query = query.filter(es_ajuste=False)
        
    gastos_agg = query.aggregate(
        total_debe=Sum('debe'),
        total_haber=Sum('haber')
    )
    
    total_debe = gastos_agg['total_debe'] or Decimal('0')
    total_haber = gastos_agg['total_haber'] or Decimal('0')

    return total_debe - total_haber
    # --- FIN DE MODIFICACIÓN ---


# --- MODIFICADO PARA CALCULAR SALDOS NETOS (CORRIGE ERROR 4311) ---
def estado_resultados(request):
    periodo_id = request.POST.get('periodo_id') or request.GET.get('periodo_id')
    if periodo_id:
        periodo_actual = get_object_or_404(PeriodoContable, pk=periodo_id)
    else:
        periodo_actual = (PeriodoContable.objects.filter(estado='ACTIVO').first()
                          or PeriodoContable.objects.filter(estado='CERRADO').first()
                          or PeriodoContable.objects.filter(estado='FINALIZADO').first())

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

        # Buscar cuentas de INGRESO (grupo 5)
        cuentas_ingresos = Cuenta.objects.filter(
            Q(codigo__startswith='5') | Q(tipo='INGRESO')
        )

        # Buscar cuentas de GASTO (grupo 4)
        cuentas_gastos = Cuenta.objects.filter(
            Q(codigo__startswith='4') | Q(tipo='GASTO')
        )

        # --- INICIO DE MODIFICACIÓN: Calcular ingresos netos ---
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
            
            # Saldo neto de ingreso (Haber - Debe)
            monto_neto = saldo_haber - saldo_debe

            if monto_neto != 0: # Mostrar si hay saldo (positivo o negativo)
                ingresos.append({
                    'codigo': cuenta.codigo,
                    'nombre': cuenta.nombre,
                    'monto': monto_neto
                })
                total_ingresos += monto_neto
        # --- FIN DE MODIFICACIÓN ---

        # --- INICIO DE MODIFICACIÓN: Calcular gastos netos ---
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

            # Saldo neto de gasto (Debe - Haber)
            # Esto maneja el caso de 4311 - Otros Gastos (saldo acreedor)
            monto_neto = saldo_debe - saldo_haber

            if monto_neto != 0: # Mostrar si hay saldo (positivo o negativo)
                gastos.append({
                    'codigo': cuenta.codigo,
                    'nombre': cuenta.nombre,
                    'monto': monto_neto
                })
                total_gastos += monto_neto
        # --- FIN DE MODIFICACIÓN ---

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


# --- MODIFICADO PARA CALCULAR SALDOS NETOS (CORRIGE ERROR 4311) ---
def _saldos_cuentas_balance(periodo):
    """Devuelve los saldos netos por cuenta; positivo = DEBE, negativo = HABER."""
    if periodo is None:
        return []

    movimientos = (
        Transaccion.objects.filter(periodo=periodo)
        .values('cuenta_id')
        .annotate(debe_total=Sum('debe'), haber_total=Sum('haber'))
    )
    cuentas = Cuenta.objects.in_bulk(item['cuenta_id'] for item in movimientos)
    saldos = []
    for item in movimientos:
        cuenta = cuentas.get(item['cuenta_id'])
        if cuenta is None:
            continue
        debe = item['debe_total'] or Decimal('0.00')
        haber = item['haber_total'] or Decimal('0.00')
        neto = debe - haber
        if neto != 0:
            saldos.append((cuenta, neto))
    return sorted(saldos, key=lambda par: par[0].codigo)


def _tipo_cuenta_balance(cuenta):
    """Prioriza la clasificación explícita del catálogo y usa el código como respaldo."""
    tipo = (cuenta.tipo or '').upper()
    if tipo in ('ACTIVO', 'PASIVO', 'PATRIMONIO', 'INGRESO', 'GASTO'):
        return tipo
    codigo = str(cuenta.codigo)
    if codigo.startswith('1'):
        return 'ACTIVO'
    if codigo.startswith('2'):
        return 'PASIVO'
    if codigo.startswith('3'):
        return 'PATRIMONIO'
    if codigo.startswith('4'):
        return 'GASTO'
    if codigo.startswith('5'):
        return 'INGRESO'
    return None


def _obtener_datos_balance_general(periodo):
    """Construye el balance sin inventar capitalizaciones ni reservas.

    Las cuentas de resultado no se incluyen dos veces: su saldo se incorpora
    al patrimonio como resultado del ejercicio, mientras que las cuentas
    patrimoniales se muestran por sus saldos contabilizados.
    """
    cero = Decimal('0.00')
    datos = {
        'activos': [], 'pasivos': [], 'patrimonio': [],
        'total_debe_activos': cero, 'total_haber_activos': cero,
        'total_debe_pasivos': cero, 'total_haber_pasivos': cero,
        'total_debe_patrimonio': cero, 'total_haber_patrimonio': cero,
        'total_debe': cero, 'total_haber': cero,
        'activos_netos': cero, 'pasivos_netos': cero,
        'patrimonio_neto': cero, 'resultado_ejercicio': cero,
        'balance_cuadra': True,
    }
    if periodo is None:
        return datos

    # Obtener el resultado desde los movimientos, incluidos los ajustes.
    # La clasificación del catálogo se utiliza en todo el balance para evitar
    # inconsistencias por prefijos y para no duplicar cuentas.
    ingresos = cero
    gastos = cero
    for cuenta, saldo_deudor in _saldos_cuentas_balance(periodo):
        tipo = _tipo_cuenta_balance(cuenta)
        if tipo == 'INGRESO':
            ingresos -= saldo_deudor
            continue
        if tipo == 'GASTO':
            gastos += saldo_deudor
            continue
        if tipo not in ('ACTIVO', 'PASIVO', 'PATRIMONIO'):
            continue

        # En el balance se respetan saldos de naturaleza contraria.
        # Una depreciación acumulada acreedora se presenta en HABER dentro
        # de activos y disminuye los activos netos (incluida la 1208).
        es_deudor = saldo_deudor > 0
        monto = abs(saldo_deudor)
        fila = {
            'codigo': cuenta.codigo,
            'nombre': cuenta.nombre,
            'saldo': monto,
            'es_deudor': es_deudor,
            'es_acreedor': not es_deudor,
            'debe': monto if es_deudor else cero,
            'haber': monto if not es_deudor else cero,
            'es_contra_activo': tipo == 'ACTIVO' and not es_deudor,
        }
        if tipo == 'ACTIVO':
            datos['activos'].append(fila)
            if es_deudor:
                datos['total_debe_activos'] += monto
            else:
                datos['total_haber_activos'] += monto
        elif tipo == 'PASIVO':
            datos['pasivos'].append(fila)
            if es_deudor:
                datos['total_debe_pasivos'] += monto
            else:
                datos['total_haber_pasivos'] += monto
        else:
            datos['patrimonio'].append(fila)
            if es_deudor:
                datos['total_debe_patrimonio'] += monto
            else:
                datos['total_haber_patrimonio'] += monto

    utilidad = ingresos - gastos
    datos['resultado_ejercicio'] = utilidad
    if utilidad != 0:
        es_acreedor = utilidad > 0
        monto = abs(utilidad)
        datos['patrimonio'].append({
            'codigo': 'RESULTADO',
            'nombre': 'Utilidad del ejercicio' if es_acreedor else 'Pérdida del ejercicio',
            'saldo': monto,
            'es_deudor': not es_acreedor,
            'es_acreedor': es_acreedor,
            'debe': cero if es_acreedor else monto,
            'haber': monto if es_acreedor else cero,
        })
        if es_acreedor:
            datos['total_haber_patrimonio'] += monto
        else:
            datos['total_debe_patrimonio'] += monto

    datos['total_debe'] = (datos['total_debe_activos'] +
                           datos['total_debe_pasivos'] +
                           datos['total_debe_patrimonio'])
    datos['total_haber'] = (datos['total_haber_activos'] +
                            datos['total_haber_pasivos'] +
                            datos['total_haber_patrimonio'])
    datos['activos_netos'] = (datos['total_debe_activos'] -
                              datos['total_haber_activos'])
    datos['pasivos_netos'] = (datos['total_haber_pasivos'] -
                              datos['total_debe_pasivos'])
    datos['patrimonio_neto'] = (datos['total_haber_patrimonio'] -
                                datos['total_debe_patrimonio'])
    datos['balance_cuadra'] = abs(
        datos['activos_netos'] - datos['pasivos_netos'] - datos['patrimonio_neto']
    ) <= Decimal('0.01')
    return datos


def estado_capital(request):
    periodo_id = request.POST.get('periodo_id') or request.GET.get('periodo_id')
    if periodo_id:
        periodo_actual = get_object_or_404(PeriodoContable, pk=periodo_id)
    else:
        periodo_actual = (PeriodoContable.objects.filter(estado='ACTIVO').first()
                          or PeriodoContable.objects.filter(estado='CERRADO').first()
                          or PeriodoContable.objects.filter(estado='FINALIZADO').first())

    cero = Decimal('0.00')
    capital_inicial = cero
    reservas_actuales = cero
    resultado_ejercicio = cero
    patrimonio_contabilizado = cero
    if periodo_actual:
        for cuenta, saldo_deudor in _saldos_cuentas_balance(periodo_actual):
            if _tipo_cuenta_balance(cuenta) != 'PATRIMONIO':
                continue
            saldo_acreedor = -saldo_deudor
            patrimonio_contabilizado += saldo_acreedor
            codigo = str(cuenta.codigo)
            nombre = (cuenta.nombre or '').lower()
            if codigo in ('301', '3101') or 'capital social' in nombre:
                capital_inicial += saldo_acreedor
            elif codigo == '3102' or 'reserva' in nombre:
                reservas_actuales += saldo_acreedor

        datos = _obtener_datos_balance_general(periodo_actual)
        resultado_ejercicio = datos['resultado_ejercicio']

    hay_perdida = resultado_ejercicio < 0
    # No se capitalizan utilidades ni se crean reservas sin asientos.
    # Se mantienen los nombres de contexto del HTML existente.
    reinversion = cero
    reservas_utilidad = cero
    reservas_totales = reservas_actuales
    capital_final = capital_inicial
    incremento_capital = cero
    porcentaje_incremento = cero
    patrimonio_final = patrimonio_contabilizado + resultado_ejercicio

    periodos = PeriodoContable.objects.all().order_by('-año')
    context = {
        'año': periodo_actual.año if periodo_actual else 'N/A',
        'capital_inicial': capital_inicial,
        'resultado_ejercicio': resultado_ejercicio,
        'reinversion': reinversion,
        'reservas_utilidad': reservas_utilidad,
        'reservas_actuales': reservas_actuales,
        'reservas_totales': reservas_totales,
        'capital_final': capital_final,
        'incremento_capital': incremento_capital,
        'porcentaje_incremento': porcentaje_incremento,
        'patrimonio_final': patrimonio_final,
        'periodo_actual': periodo_actual,
        'periodos': periodos,
        'hay_perdida': hay_perdida,
        'perdida_total': abs(resultado_ejercicio) if hay_perdida else cero,
    }
    return render(request, 'EstadosFinancieros/estadoCapital.html', context)



def balance_general(request):
    periodo_id = request.POST.get('periodo_id') or request.GET.get('periodo_id')
    if periodo_id:
        periodo_actual = get_object_or_404(PeriodoContable, pk=periodo_id)
    else:
        periodo_actual = (PeriodoContable.objects.filter(estado='ACTIVO').first()
                          or PeriodoContable.objects.filter(estado='CERRADO').first()
                          or PeriodoContable.objects.filter(estado='FINALIZADO').first())

    datos = _obtener_datos_balance_general(periodo_actual)
    periodos = PeriodoContable.objects.all().order_by('-año')
    context = {
        **datos,
        'periodo_actual': periodo_actual,
        'periodos': periodos,
        'fecha_inicio': periodo_actual.fecha_inicio if periodo_actual else '',
        'fecha_fin': periodo_actual.fecha_fin if periodo_actual else '',
    }
    return render(request, 'EstadosFinancieros/balanceGeneral.html', context)
