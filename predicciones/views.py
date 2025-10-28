from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Avg, Sum, Q
from django.conf import settings
from openai import OpenAI
from django.contrib.auth import get_user_model
from .models import Prediccion, TipoArbol, Comuna, Region, DatoClimatico, AnalisisPrediccion
from .forms import PrediccionForm, AnalisisPrediccionForm
from .services.fastapi_client import ping as ms_ping, echo as ms_echo
import os, json, requests

User = get_user_model()

# ==========================================
# CONFIGURACIÓN DE IA
# ==========================================
OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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"
)

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ==========================================
# VISTAS DE IA
# ==========================================
def ia_chat_page(request):
    return render(request, "ia_chat.html")


def ia_consulta(request):
    """Endpoint que recibe un texto y devuelve una respuesta de IA desde OpenRouter."""
    pregunta = request.GET.get("q") or request.POST.get("q")
    if not pregunta:
        return JsonResponse({"error": "Debe incluir el parámetro 'q'."}, status=400)

    try:
        chat = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": pregunta}]
        )
        respuesta = chat.choices[0].message.content
        return JsonResponse({"input": pregunta, "respuesta": respuesta})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def obtener_datos_clima(comuna):
    """Obtiene datos climáticos (simulados)."""
    try:
        lat = comuna.latitud or -33.4489
        lon = comuna.longitud or -70.6693
        api_key = getattr(settings, 'ACCUWEATHER_API_KEY', 'demo_key')
        return {
            'temperatura': 18.5,
            'humedad': 65,
            'descripcion': 'Parcialmente nublado',
            'icono': '02d'
        }
    except Exception:
        return None


# ==========================================
# DASHBOARD PRINCIPAL
# ==========================================
def dashboard(request):
    total_predicciones = Prediccion.objects.count()
    predicciones_completadas = Prediccion.objects.filter(estado='completada').count()
    predicciones_recientes = Prediccion.objects.select_related(
        'tipo_arbol', 'comuna__region'
    ).order_by('-fecha_creacion')[:5]

    stats_por_arbol = list(Prediccion.objects.filter(
        estado='completada'
    ).values('tipo_arbol__tipo').annotate(
        total=Count('id'),
        promedio_produccion=Avg('produccion_por_hectarea'),
        promedio_confiabilidad=Avg('confiabilidad'),
        promedio_roi=Avg('roi_proyectado'),
        promedio_agua=Avg('consumo_agua_por_hectarea')
    ).order_by('-total')[:5])

    stats_por_region = list(Prediccion.objects.filter(
        estado='completada'
    ).values('comuna__region__nombre').annotate(
        total=Count('id'),
        total_hectareas=Sum('hectareas'),
        produccion_total=Sum('produccion_total'),
        inversion_total=Sum('inversion_estimada')
    ).order_by('-total')[:5])

    santiago = Comuna.objects.filter(nombre__icontains='Santiago').first()
    datos_clima = obtener_datos_clima(santiago) if santiago else None

    context = {
        'total_predicciones': total_predicciones,
        'predicciones_completadas': predicciones_completadas,
        'predicciones_recientes': predicciones_recientes,
        'stats_por_arbol': json.dumps(stats_por_arbol),
        'stats_por_region': json.dumps(stats_por_region),
        'datos_clima': datos_clima,
        'comuna_clima': santiago,
        'tasa_completado': round(
            (predicciones_completadas / total_predicciones * 100)
            if total_predicciones > 0 else 0, 1
        )
    }
    return render(request, 'predicciones/dashboard.html', context)


# ==========================================
# PREDICCIONES
# ==========================================
def nueva_prediccion(request):
    """Vista para crear una nueva predicción."""
    if request.method == 'POST':
        form = PrediccionForm(request.POST)
        if form.is_valid():
            prediccion = form.save(commit=False)
            prediccion.usuario = User.objects.first()  # usuario genérico para demo
            prediccion.estado = 'procesando'
            prediccion.save()
            prediccion.calcular_prediccion()
            messages.success(request, 'Predicción creada exitosamente.')
            return redirect('prediccion_detalle', pk=prediccion.pk)
    else:
        form = PrediccionForm()

    context = {
        'form': form,
        'tipos_arboles': TipoArbol.objects.all(),
        'comunas': Comuna.objects.select_related('region').all(),
    }
    return render(request, 'predicciones/prediccion_form.html', context)


def prediccion_detalle(request, pk):
    """Detalle de una predicción."""
    prediccion = get_object_or_404(Prediccion, pk=pk)
    analisis, created = AnalisisPrediccion.objects.get_or_create(
        prediccion=prediccion,
        defaults={
            'categoria_rentabilidad': prediccion.get_rentabilidad_categoria(),
            'recomendacion': generar_recomendacion_automatica(prediccion)
        }
    )

    otras_especies = Prediccion.objects.filter(
        comuna__region=prediccion.comuna.region,
        estado='completada'
    ).exclude(id=prediccion.id).values(
        'tipo_arbol__tipo', 'tipo_arbol__id'
    ).annotate(
        promedio_roi=Avg('roi_proyectado'),
        promedio_produccion=Avg('produccion_por_hectarea')
    ).order_by('-promedio_roi')[:3]

    context = {
        'prediccion': prediccion,
        'analisis': analisis,
        'otras_especies': otras_especies,
    }
    return render(request, 'predicciones/prediccion_detalle.html', context)


def lista_predicciones(request):
    """Lista general de predicciones (público)."""
    predicciones_list = Prediccion.objects.select_related(
        'tipo_arbol', 'comuna__region'
    ).order_by('-fecha_creacion')

    tipo_arbol = request.GET.get('tipo_arbol')
    estado = request.GET.get('estado')
    region = request.GET.get('region')

    if tipo_arbol:
        predicciones_list = predicciones_list.filter(tipo_arbol__pk=tipo_arbol)
    if estado:
        predicciones_list = predicciones_list.filter(estado=estado)
    if region:
        predicciones_list = predicciones_list.filter(comuna__region__pk=region)

    paginator = Paginator(predicciones_list, 10)
    page_number = request.GET.get('page')
    predicciones = paginator.get_page(page_number)

    context = {
        'predicciones': predicciones,
        'tipos_arboles': TipoArbol.objects.all(),
        'regiones': Region.objects.all(),
        'estados': Prediccion.ESTADO_CHOICES,
        'filtros': {'tipo_arbol': tipo_arbol, 'estado': estado, 'region': region}
    }
    return render(request, 'predicciones/prediccion_lista.html', context)


# ==========================================
# ANÁLISIS DE PREDICCIÓN
# ==========================================
def analisis_prediccion(request):
    if request.method == 'POST':
        form = AnalisisPrediccionForm(request.POST)
        if form.is_valid():
            prediccion_id = form.cleaned_data['prediccion'].id
            return redirect('analisis_prediccion_detalle', pk=prediccion_id)
    else:
        form = AnalisisPrediccionForm()

    predicciones_disponibles = Prediccion.objects.filter(
        estado='completada'
    ).select_related('tipo_arbol', 'comuna').order_by('-fecha_creacion')[:10]

    context = {
        'form': form,
        'predicciones_disponibles': predicciones_disponibles,
    }
    return render(request, 'predicciones/analisis_prediccion.html', context)


def analisis_prediccion_detalle(request, pk):
    prediccion = get_object_or_404(Prediccion, pk=pk)

    misma_especie_otras_regiones = Prediccion.objects.filter(
        tipo_arbol=prediccion.tipo_arbol, estado='completada'
    ).exclude(id=prediccion.id).values('comuna__region__nombre').annotate(
        promedio_roi=Avg('roi_proyectado'),
        promedio_produccion=Avg('produccion_por_hectarea'),
        promedio_inversion=Avg('inversion_estimada')
    ).order_by('-promedio_roi')

    alternativas_region = Prediccion.objects.filter(
        comuna__region=prediccion.comuna.region, estado='completada'
    ).exclude(tipo_arbol=prediccion.tipo_arbol).values(
        'tipo_arbol__tipo', 'tipo_arbol__id'
    ).annotate(
        promedio_roi=Avg('roi_proyectado'),
        promedio_produccion=Avg('produccion_por_hectarea'),
        total_predicciones=Count('id')
    ).order_by('-promedio_roi')[:5]

    analisis_riesgo = {
        'roi_esperado': prediccion.roi_proyectado or 0,
        'inversion_requerida': prediccion.inversion_estimada or 0,
        'tiempo_recuperacion': calcular_tiempo_recuperacion(prediccion),
        'categoria_riesgo': clasificar_riesgo_inversion(prediccion)
    }

    context = {
        'prediccion': prediccion,
        'misma_especie_otras_regiones': misma_especie_otras_regiones,
        'alternativas_region': alternativas_region,
        'analisis_riesgo': analisis_riesgo,
    }
    return render(request, 'predicciones/analisis_prediccion_detalle.html', context)


def comparacion_predicciones(request):
    """Comparación libre (sin restricción de usuario)."""
    prediccion_ids = request.GET.getlist('predicciones')

    if prediccion_ids:
        predicciones = Prediccion.objects.filter(
            id__in=prediccion_ids, estado='completada'
        ).select_related('tipo_arbol', 'comuna__region')
    else:
        predicciones = Prediccion.objects.filter(
            estado='completada'
        ).select_related('tipo_arbol', 'comuna__region').order_by('-fecha_creacion')[:5]

    comparacion_data = []
    for p in predicciones:
        comparacion_data.append({
            'prediccion': p,
            'roi_por_hectarea': (p.roi_proyectado or 0) / p.hectareas if p.hectareas else 0,
            'inversion_por_hectarea': (p.inversion_estimada or 0) / p.hectareas if p.hectareas else 0,
            'eficiencia_agua': (p.produccion_por_hectarea or 0) / (p.consumo_agua_por_hectarea or 1)
        })

    context = {
        'comparacion_data': comparacion_data,
        'todas_predicciones': Prediccion.objects.filter(estado='completada')
    }
    return render(request, 'predicciones/comparacion_predicciones.html', context)


# ==========================================
# API AUXILIAR
# ==========================================
def api_comunas_por_region(request):
    region_id = request.GET.get('region_id')
    comunas = Comuna.objects.filter(region_id=region_id).values('id', 'nombre') if region_id else []
    return JsonResponse({'comunas': list(comunas)})


def eliminar_prediccion(request, pk):
    if request.method == 'POST':
        prediccion = get_object_or_404(Prediccion, pk=pk)
        prediccion.delete()
        messages.success(request, 'Predicción eliminada exitosamente.')
    return redirect('lista_predicciones')


# ==========================================
# FUNCIONES DE ANÁLISIS Y RIESGO
# ==========================================
def generar_recomendacion_automatica(prediccion):
    roi = prediccion.roi_proyectado or 0
    if roi >= 50:
        return f"Excelente oportunidad: ROI {roi:.1f}%."
    elif roi >= 30:
        return f"Buena oportunidad: ROI {roi:.1f}%."
    elif roi >= 15:
        return f"Oportunidad moderada: ROI {roi:.1f}%."
    elif roi >= 0:
        return f"Retorno bajo: ROI {roi:.1f}%."
    else:
        return f"No recomendado: ROI negativo ({roi:.1f}%)."


def calcular_tiempo_recuperacion(prediccion):
    if not prediccion.inversion_estimada or not prediccion.produccion_por_hectarea:
        return "No disponible"
    ingresos = (prediccion.produccion_por_hectarea *
                prediccion.hectareas *
                (prediccion.tipo_arbol.precio_promedio_ton or 0))
    costos = (prediccion.tipo_arbol.costo_mantenimiento_anual * prediccion.hectareas)
    ganancia = ingresos - costos
    if ganancia > 0:
        return f"{prediccion.inversion_estimada / ganancia:.1f} años"
    return "No se recupera"


def clasificar_riesgo_inversion(prediccion):
    roi = prediccion.roi_proyectado or 0
    confiabilidad = prediccion.confiabilidad or 0
    if roi >= 30 and confiabilidad >= 85:
        return "Bajo"
    elif roi >= 15 and confiabilidad >= 75:
        return "Medio"
    elif roi >= 0 and confiabilidad >= 65:
        return "Alto"
    return "Muy Alto"


# ==========================================
# MICRO SERVICIOS
# ==========================================
def ms_ping_view(request):
    try:
        data = ms_ping()
        return JsonResponse({"ok": True, "upstream": data})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=502)


def ms_echo_view(request):
    msg = request.GET.get("msg", "Hola desde Django")
    try:
        data = ms_echo(msg)
        return JsonResponse({"ok": True, "sent": msg, "upstream": data})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=502)


# ==========================================
# CALCULADORAS AGRÍCOLAS
# ==========================================
def calculadoras_agricolas(request):
    calculadoras = [
        {'nombre': 'Fertilización NPK', 'descripcion': 'Cálculo NPK', 'icono': 'fas fa-leaf', 'url': 'calculadora_fertilizacion', 'categoria': 'Nutrición'},
        {'nombre': 'Riego', 'descripcion': 'Cálculo lámina y frecuencia de riego', 'icono': 'fas fa-tint', 'url': 'calculadora_agua', 'categoria': 'Agua'},
        {'nombre': 'ROI Agrícola', 'descripcion': 'Retorno y recuperación de inversión', 'icono': 'fas fa-chart-line', 'url': 'calculadora_roi', 'categoria': 'Economía'},
        {'nombre': 'Densidad de Siembra', 'descripcion': 'Cantidad óptima de plantas', 'icono': 'fas fa-seedling', 'url': 'calculadora_siembra', 'categoria': 'Siembra'},
        {'nombre': 'Balance Hídrico', 'descripcion': 'Balance entre precipitación y evapotranspiración', 'icono': 'fas fa-cloud-rain', 'url': 'calculadora_balance_hidrico', 'categoria': 'Agua'}
    ]
    return render(request, 'calculadoras/index.html', {'calculadoras': calculadoras})


def calculadora_fertilizacion(request):
    resultado = None
    if request.method == 'POST':
        rendimiento_esperado = float(request.POST.get('rendimiento_esperado', 0))
        cultivo = request.POST.get('cultivo')
        superficie = float(request.POST.get('superficie', 1))
        nitrogeno_suelo = float(request.POST.get('nitrogeno_suelo', 0))
        fosforo_suelo = float(request.POST.get('fosforo_suelo', 0))
        potasio_suelo = float(request.POST.get('potasio_suelo', 0))
        formula_npk = request.POST.get('formula_npk', '15-15-15').split('-')
        n_fert = float(formula_npk[0]) / 100
        p_fert = float(formula_npk[1]) / 100
        k_fert = float(formula_npk[2]) / 100

        coef = {'N': 3.5, 'P2O5': 1.5, 'K2O': 5.5}
        extr_n = rendimiento_esperado * coef['N']
        extr_p = rendimiento_esperado * coef['P2O5']
        extr_k = rendimiento_esperado * coef['K2O']
        factor = 3900 / 1000000
        disp_n = nitrogeno_suelo * factor
        disp_p = fosforo_suelo * factor * 0.8
        disp_k = potasio_suelo * factor * 0.9
        req_n = max(0, extr_n - disp_n)
        req_p = max(0, extr_p - disp_p)
        req_k = max(0, extr_k - disp_k)
        dosis = max(req_n / n_fert if n_fert > 0 else 0,
                    req_p / p_fert if p_fert > 0 else 0,
                    req_k / k_fert if k_fert > 0 else 0)
        resultado = {'dosis_npk_ha': round(dosis, 1),
                     'dosis_total': round(dosis * superficie, 1)}

    return render(request, 'calculadoras/fertilizacion.html', {'resultado': resultado})


def calculadora_agua(request):
    resultado = None
    if request.method == 'POST':
        et0 = float(request.POST.get('et0', 0))
        kc = float(request.POST.get('kc', 1))
        eficiencia = float(request.POST.get('eficiencia', 0.7))
        frecuencia = int(request.POST.get('frecuencia', 7))
        lamina_diaria = et0 * kc
        lamina_evento = lamina_diaria * frecuencia / eficiencia
        volumen_evento = lamina_evento * 10
        resultado = {'lamina_diaria': round(lamina_diaria, 1),
                     'lamina_evento': round(lamina_evento, 1),
                     'volumen_evento': round(volumen_evento, 1)}
    return render(request, 'calculadoras/agua.html', {'resultado': resultado})


def calculadora_roi(request):
    resultado = None
    if request.method == 'POST':
        inversion = float(request.POST.get('inversion', 0))
        beneficio = float(request.POST.get('beneficio_anual', 0))
        roi = (beneficio / inversion) * 100 if inversion > 0 else 0
        payback = inversion / beneficio if beneficio > 0 else None
        resultado = {'roi': round(roi, 1),
                     'payback': round(payback, 1) if payback else None}
    return render(request, 'calculadoras/roi.html', {'resultado': resultado})


def calculadora_siembra(request):
    resultado = None
    if request.method == 'POST':
        densidad = float(request.POST.get('densidad_planta', 3000))
        supervivencia = float(request.POST.get('supervivencia', 0.9))
        plantas = densidad / supervivencia
        resultado = {'plantas_necesarias': int(round(plantas, 0))}
    return render(request, 'calculadoras/siembra.html', {'resultado': resultado})


def calculadora_balance_hidrico(request):
    resultado = None
    if request.method == 'POST':
        precipitacion = float(request.POST.get('precipitacion', 0))
        etc = float(request.POST.get('etc', 0))
        infiltracion = float(request.POST.get('infiltracion', 0))
        balance = precipitacion - etc - infiltracion
        resultado = {'balance': round(balance, 1)}
    return render(request, 'calculadoras/balance_hidrico.html', {'resultado': resultado})
