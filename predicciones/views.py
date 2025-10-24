from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Avg, Sum, Q
from .models import Prediccion, TipoArbol, Comuna, Region, DatoClimatico, AnalisisPrediccion
from .forms import PrediccionForm, AnalisisPrediccionForm
import requests
from django.conf import settings
from openai import OpenAI
import os
from .services.fastapi_client import ping as ms_ping, echo as ms_echo
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)


def ia_chat_page(request):
    return render(request, "ia_chat.html")

def ia_consulta(request):
    """
    Endpoint que recibe un texto y devuelve una respuesta de IA desde OpenRouter.
    """
    pregunta = request.GET.get("q") or request.POST.get("q")
    if not pregunta:
        return JsonResponse({"error": "Debe incluir el parámetro 'q'."}, status=400)

    try:
        chat = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[
                {"role": "user", "content": pregunta}
            ]
        )
        respuesta = chat.choices[0].message.content
        return JsonResponse({
            "input": pregunta,
            "respuesta": respuesta
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")  # redirige a tu página principal
        else:
            messages.error(request, "Usuario o contraseña incorrectos")

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("login")

def home_redirect(request):
    """Redirige la raíz según el estado de autenticación"""
    if request.user.is_authenticated:
        return redirect('dashboard')   # <- nombre de tu vista del dashboard
    return redirect('login')



def obtener_datos_clima(comuna):
    """Obtiene datos climáticos de AccuWeather API"""
    try:
        # Si no hay coordenadas, usar Santiago como default
        lat = comuna.latitud or -33.4489
        lon = comuna.longitud or -70.6693
        
        # URL de ejemplo - necesitarás registrarte en AccuWeather para obtener API key
        api_key = getattr(settings, 'ACCUWEATHER_API_KEY', 'demo_key')
        
        # Simulación de datos climáticos (reemplazar con API real)
        datos_clima = {
            'temperatura': 18.5,
            'humedad': 65,
            'descripcion': 'Parcialmente nublado',
            'icono': '02d'
        }
        
        return datos_clima
    except Exception as e:
        return None

def dashboard(request):
    """Vista principal del dashboard con widget climático y datos para gráficos"""
    
    # Estadísticas generales
    total_predicciones = Prediccion.objects.count()
    predicciones_completadas = Prediccion.objects.filter(estado='completada').count()
    
    # Predicciones recientes
    predicciones_recientes = Prediccion.objects.select_related(
        'tipo_arbol', 'comuna__region'
    ).order_by('-fecha_creacion')[:5]
    
    # Estadísticas por tipo de árbol con nuevas métricas
    stats_por_arbol = list(Prediccion.objects.filter(
        estado='completada'
    ).values(
        'tipo_arbol__tipo'
    ).annotate(
        total=Count('id'),
        promedio_produccion=Avg('produccion_por_hectarea'),
        promedio_confiabilidad=Avg('confiabilidad'),
        promedio_roi=Avg('roi_proyectado'),
        promedio_agua=Avg('consumo_agua_por_hectarea')
    ).order_by('-total')[:5])
    
    # Estadísticas por región
    stats_por_region = list(Prediccion.objects.filter(
        estado='completada'
    ).values(
        'comuna__region__nombre'
    ).annotate(
        total=Count('id'),
        total_hectareas=Sum('hectareas'),
        produccion_total=Sum('produccion_total'),
        inversion_total=Sum('inversion_estimada')
    ).order_by('-total')[:5])
    
    # Obtener datos climáticos para Santiago (default)
    santiago = Comuna.objects.filter(nombre__icontains='Santiago').first()
    datos_clima = obtener_datos_clima(santiago) if santiago else None
    
    context = {
        'total_predicciones': total_predicciones,
        'predicciones_completadas': predicciones_completadas,
        'predicciones_recientes': predicciones_recientes,
        'stats_por_arbol': json.dumps(stats_por_arbol),  # Convertir a JSON
        'stats_por_region': json.dumps(stats_por_region),  # Convertir a JSON
        'datos_clima': datos_clima,
        'comuna_clima': santiago,
        'tasa_completado': round((predicciones_completadas / total_predicciones * 100) if total_predicciones > 0 else 0, 1)
    }
    
    return render(request, 'predicciones/dashboard.html', context)


@login_required
def nueva_prediccion(request):
    """Vista para crear una nueva predicción (siempre del usuario logueado)"""
    if request.method == 'POST':
        form = PrediccionForm(request.POST)
        if form.is_valid():
            prediccion = form.save(commit=False)
            prediccion.usuario = request.user  # fuerza propiedad
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


@login_required
def prediccion_detalle(request, pk):
    """Detalle de una predicción (solo si es mía) + análisis con mis datos"""
    prediccion = get_object_or_404(Prediccion, pk=pk, usuario=request.user)

    analisis, created = AnalisisPrediccion.objects.get_or_create(
        prediccion=prediccion,
        defaults={
            'categoria_rentabilidad': prediccion.get_rentabilidad_categoria(),
            'recomendacion': generar_recomendacion_automatica(prediccion)
        }
    )

    # Comparar con MIS otras especies en la misma región
    otras_especies = Prediccion.objects.filter(
        usuario=request.user,
        comuna__region=prediccion.comuna.region,
        estado='completada'
    ).exclude(id=prediccion.id).values(
        'tipo_arbol__tipo',
        'tipo_arbol__id'
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


@login_required
def lista_predicciones(request):
    """Lista solo mis predicciones"""
    predicciones_list = Prediccion.objects.select_related(
        'tipo_arbol', 'comuna__region', 'usuario'
    ).filter(usuario=request.user).order_by('-fecha_creacion')

    # Filtros
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


# NUEVA VISTA: Análisis de Predicción
from django.contrib.auth.decorators import login_required

@login_required
def analisis_prediccion(request):
    """Vista para análisis detallado de predicciones (solo mis predicciones)"""
    if request.method == 'POST':
        form = AnalisisPrediccionForm(request.POST, user=request.user)
        if form.is_valid():
            prediccion_id = form.cleaned_data['prediccion'].id
            return redirect('analisis_prediccion_detalle', pk=prediccion_id)
    else:
        form = AnalisisPrediccionForm(user=request.user)
    
    # SOLO mis predicciones completadas para mostrar como “recientes”
    predicciones_disponibles = Prediccion.objects.filter(
        usuario=request.user, estado='completada'
    ).select_related('tipo_arbol', 'comuna').order_by('-fecha_creacion')[:10]
    
    context = {
        'form': form,
        'predicciones_disponibles': predicciones_disponibles,
    }
    return render(request, 'predicciones/analisis_prediccion.html', context)


def analisis_prediccion_detalle(request, pk):
    """Vista detallada del análisis de una predicción específica"""
    prediccion = get_object_or_404(Prediccion, pk=pk)
    
    # Análisis comparativo con misma especie en diferentes regiones
    misma_especie_otras_regiones = Prediccion.objects.filter(
        tipo_arbol=prediccion.tipo_arbol,
        estado='completada'
    ).exclude(id=prediccion.id).values(
        'comuna__region__nombre'
    ).annotate(
        promedio_roi=Avg('roi_proyectado'),
        promedio_produccion=Avg('produccion_por_hectarea'),
        promedio_inversion=Avg('inversion_estimada')
    ).order_by('-promedio_roi')
    
    # Análisis de alternativas en la misma región
    alternativas_region = Prediccion.objects.filter(
        comuna__region=prediccion.comuna.region,
        estado='completada'
    ).exclude(tipo_arbol=prediccion.tipo_arbol).values(
        'tipo_arbol__tipo',
        'tipo_arbol__id'
    ).annotate(
        promedio_roi=Avg('roi_proyectado'),
        promedio_produccion=Avg('produccion_por_hectarea'),
        total_predicciones=Count('id')
    ).order_by('-promedio_roi')[:5]
    
    # Análisis de riesgo-beneficio
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

# NUEVA VISTA: Comparación de Predicciones
from django.http import Http404

@login_required
def comparacion_predicciones(request):
    """Comparar múltiples predicciones (solo las mías)"""
    prediccion_ids = request.GET.getlist('predicciones')

    if prediccion_ids:
        # Filtramos por mis IDs
        predicciones = Prediccion.objects.filter(
            usuario=request.user,
            id__in=prediccion_ids,
            estado='completada'
        ).select_related('tipo_arbol', 'comuna__region')

        # Validación: si pidieron IDs que no son míos, los bloqueamos
        if len(set(map(int, prediccion_ids))) != predicciones.count():
            raise Http404("Una o más predicciones no existen o no te pertenecen.")
    else:
        # Por defecto: mis 5 más recientes
        predicciones = Prediccion.objects.filter(
            usuario=request.user,
            estado='completada'
        ).select_related('tipo_arbol', 'comuna__region').order_by('-fecha_creacion')[:5]

    comparacion_data = []
    for p in predicciones:
        comparacion_data.append({
            'prediccion': p,
            'roi_por_hectarea': (p.roi_proyectado or 0) / p.hectareas if p.hectareas else 0,
            'inversion_por_hectarea': (p.inversion_estimada or 0) / p.hectareas if p.hectareas else 0,
            'eficiencia_agua': (p.produccion_por_hectarea or 0) / (p.consumo_agua_por_hectarea or 1) if p.consumo_agua_por_hectarea else 0,
        })

    todas_predicciones = Prediccion.objects.filter(
        usuario=request.user, estado='completada'
    ).select_related('tipo_arbol', 'comuna').order_by('-fecha_creacion')

    context = {
        'comparacion_data': comparacion_data,
        'todas_predicciones': todas_predicciones,
        'prediccion_ids_selected': prediccion_ids,
    }
    return render(request, 'predicciones/comparacion_predicciones.html', context)


def api_comunas_por_region(request):
    """API para obtener comunas por región"""
    region_id = request.GET.get('region_id')
    if region_id:
        comunas = Comuna.objects.filter(region_id=region_id).values('id', 'nombre')
        return JsonResponse({'comunas': list(comunas)})
    return JsonResponse({'comunas': []})

def eliminar_prediccion(request, pk):
    """Vista para eliminar una predicción"""
    if request.method == 'POST':
        prediccion = get_object_or_404(Prediccion, pk=pk)
        prediccion.delete()
        messages.success(request, 'Predicción eliminada exitosamente.')
        return redirect('lista_predicciones')
    
    return redirect('lista_predicciones')

# FUNCIONES AUXILIARES
def generar_recomendacion_automatica(prediccion):
    """Genera recomendación automática basada en análisis"""
    roi = prediccion.roi_proyectado or 0
    
    if roi >= 50:
        return f"Excelente oportunidad de inversión. El {prediccion.tipo_arbol} en {prediccion.comuna} muestra un ROI excepcional del {roi:.1f}%. Se recomienda proceder con la inversión."
    elif roi >= 30:
        return f"Buena oportunidad de inversión. ROI atractivo del {roi:.1f}%. Considere evaluar riesgos climáticos y de mercado antes de proceder."
    elif roi >= 15:
        return f"Oportunidad moderada. ROI del {roi:.1f}% es aceptable pero evalúe alternativas. Considere diversificar con otras especies."
    elif roi >= 0:
        return f"Oportunidad de bajo retorno. ROI del {roi:.1f}% es marginal. Evalúe cuidadosamente antes de invertir o considere alternativas."
    else:
        return f"No recomendado. ROI negativo del {roi:.1f}%. Busque alternativas más rentables o reconsidere parámetros del proyecto."

def calcular_tiempo_recuperacion(prediccion):
    """Calcula tiempo estimado de recuperación de inversión"""
    if not prediccion.inversion_estimada or not prediccion.produccion_por_hectarea:
        return "No disponible"
    
    ingresos_anuales = (prediccion.produccion_por_hectarea * 
                       prediccion.hectareas * 
                       (prediccion.tipo_arbol.precio_promedio_ton or 0))
    
    costos_anuales = (prediccion.tipo_arbol.costo_mantenimiento_anual * 
                     prediccion.hectareas)
    
    ganancia_anual_neta = ingresos_anuales - costos_anuales
    
    if ganancia_anual_neta > 0:
        anos_recuperacion = prediccion.inversion_estimada / ganancia_anual_neta
        return f"{anos_recuperacion:.1f} años"
    
    return "No se recupera"

def clasificar_riesgo_inversion(prediccion):
    """Clasifica el riesgo de la inversión"""
    roi = prediccion.roi_proyectado or 0
    confiabilidad = prediccion.confiabilidad or 0
    
    if roi >= 30 and confiabilidad >= 85:
        return "Bajo"
    elif roi >= 15 and confiabilidad >= 75:
        return "Medio"
    elif roi >= 0 and confiabilidad >= 65:
        return "Alto"
    else:
        return "Muy Alto"
    
@login_required
def ms_ping_view(request):
    """Pinga el microservicio FastAPI y devuelve su respuesta"""
    try:
        data = ms_ping()
        return JsonResponse({"ok": True, "upstream": data})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=502)
    
@login_required
def ms_echo_view(request):
    """Envía un texto a /echo y retorna lo que FastAPI responde"""
    msg = request.GET.get("msg", "Hola desde Django")
    try:
        data = ms_echo(msg)
        return JsonResponse({"ok": True, "sent": msg, "upstream": data})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=502)
    
     # ==========================================
# VISTAS PARA CALCULADORAS AGRÍCOLAS
# ==========================================

def calculadoras_agricolas(request):
    """Vista principal de calculadoras agrícolas"""
    calculadoras = [
        {
            'nombre': 'Calculadora de Fertilización NPK',
            'descripcion': 'Calcula las dosis exactas de fertilizantes NPK basado en análisis de suelo y requerimientos del cultivo',
            'icono': 'fas fa-leaf',
            'url': 'calculadora_fertilizacion',
            'categoria': 'Nutrición'
        },
        {
            'nombre': 'Calculadora de Riego',
            'descripcion': 'Determina la lámina de riego y frecuencia basado en evapotranspiración y tipo de suelo',
            'icono': 'fas fa-tint',
            'url': 'calculadora_agua',
            'categoria': 'Agua'
        },
        {
            'nombre': 'Calculadora de ROI Agrícola',
            'descripcion': 'Calcula el retorno de inversión y tiempo de recuperación para proyectos agrícolas',
            'icono': 'fas fa-chart-line',
            'url': 'calculadora_roi',
            'categoria': 'Economía'
        },
        {
            'nombre': 'Calculadora de Densidad de Siembra',
            'descripcion': 'Determina la densidad óptima de siembra y cantidad de semilla por hectárea',
            'icono': 'fas fa-seedling',
            'url': 'calculadora_siembra',
            'categoria': 'Siembra'
        },
        {
            'nombre': 'Balance Hídrico de Cultivos',
            'descripcion': 'Calcula el balance hídrico considerando precipitación, evapotranspiración y reserva de agua del suelo',
            'icono': 'fas fa-cloud-rain',
            'url': 'calculadora_balance_hidrico',
            'categoria': 'Agua'
        }
    ]
    
    context = {
        'calculadoras': calculadoras
    }
    
    return render(request, 'calculadoras/index.html', context)


def calculadora_fertilizacion(request):
    """Calculadora de fertilización NPK basada en el método de fertilización razonada"""
    resultado = None
    
    if request.method == 'POST':
        # Datos del cultivo
        rendimiento_esperado = float(request.POST.get('rendimiento_esperado', 0))
        cultivo = request.POST.get('cultivo')
        superficie = float(request.POST.get('superficie', 1))
        
        # Análisis de suelo
        nitrogeno_suelo = float(request.POST.get('nitrogeno_suelo', 0))
        fosforo_suelo = float(request.POST.get('fosforo_suelo', 0))  # P2O5 mg/kg
        potasio_suelo = float(request.POST.get('potasio_suelo', 0))   # K mg/kg
        
        # Fertilizantes a usar
        formula_npk = request.POST.get('formula_npk', '15-15-15').split('-')
        n_fertilizante = float(formula_npk[0]) / 100
        p_fertilizante = float(formula_npk[1]) / 100
        k_fertilizante = float(formula_npk[2]) / 100
        
        # Coeficientes de extracción por cultivo (kg/ton producida)
        # Basado en estudios de INIA y literatura agronómica
        coeficientes_extraccion = {
            'papa': {'N': 3.5, 'P2O5': 1.5, 'K2O': 5.5},
            'maiz': {'N': 20, 'P2O5': 8, 'K2O': 18},
            'trigo': {'N': 28, 'P2O5': 12, 'K2O': 25},
            'tomate': {'N': 3.0, 'P2O5': 1.2, 'K2O': 4.5},
            'palto': {'N': 15, 'P2O5': 3, 'K2O': 20},
        }
        
        # Usar papa como default
        coef = coeficientes_extraccion.get(cultivo, coeficientes_extraccion['papa'])
        
        # Cálculo de extracción del cultivo
        extraccion_n = rendimiento_esperado * coef['N']
        extraccion_p = rendimiento_esperado * coef['P2O5'] 
        extraccion_k = rendimiento_esperado * coef['K2O']
        
        # Disponibilidad del suelo (conversión mg/kg a kg/ha)
        # Profundidad efectiva 30 cm, densidad aparente 1.3 g/cm³
        factor_conversion = 3900 / 1000000  # Para convertir mg/kg a kg/ha en 30cm
        
        disponible_n = nitrogeno_suelo * factor_conversion
        disponible_p = fosforo_suelo * factor_conversion * 0.8  # Eficiencia del P
        disponible_k = potasio_suelo * factor_conversion * 0.9  # Eficiencia del K
        
        # Requerimiento neto
        req_n = max(0, extraccion_n - disponible_n)
        req_p = max(0, extraccion_p - disponible_p) 
        req_k = max(0, extraccion_k - disponible_k)
        
        # Cálculo de fertilizante NPK
        # Se calcula por el nutriente más limitante
        dosis_por_n = req_n / n_fertilizante if n_fertilizante > 0 else 0
        dosis_por_p = req_p / p_fertilizante if p_fertilizante > 0 else 0
        dosis_por_k = req_k / k_fertilizante if k_fertilizante > 0 else 0
        
        dosis_npk = max(dosis_por_n, dosis_por_p, dosis_por_k)
        
        # Aporte real de nutrientes con esta dosis
        aporte_n = dosis_npk * n_fertilizante
        aporte_p = dosis_npk * p_fertilizante
        aporte_k = dosis_npk * k_fertilizante
        
        # Fertilizantes adicionales si es necesario
        falta_n = max(0, req_n - aporte_n)
        falta_p = max(0, req_p - aporte_p)
        falta_k = max(0, req_k - aporte_k)
        
        # Urea para N faltante (46% N)
        urea_adicional = falta_n / 0.46 if falta_n > 0 else 0
        
        # Superfosfato triple para P faltante (46% P2O5)
        superfosfato_adicional = falta_p / 0.46 if falta_p > 0 else 0
        
        # Muriato de potasio para K faltante (60% K2O)
        muriato_adicional = falta_k / 0.60 if falta_k > 0 else 0
        
        resultado = {
            'extraccion': {
                'N': round(extraccion_n, 1),
                'P2O5': round(extraccion_p, 1),
                'K2O': round(extraccion_k, 1)
            },
            'disponible': {
                'N': round(disponible_n, 1),
                'P2O5': round(disponible_p, 1),
                'K2O': round(disponible_k, 1)
            },
            'requerimiento': {
                'N': round(req_n, 1),
                'P2O5': round(req_p, 1),
                'K2O': round(req_k, 1)
            },
            'dosis_npk_ha': round(dosis_npk, 1),
            'dosis_npk_total': round(dosis_npk * superficie, 1),
            'fertilizantes_adicionales': {
                'urea': round(urea_adicional, 1),
                'superfosfato': round(superfosfato_adicional, 1),
                'muriato': round(muriato_adicional, 1)
            },
            'aporte_real': {
                'N': round(aporte_n, 1),
                'P2O5': round(aporte_p, 1), 
                'K2O': round(aporte_k, 1)
            },
            'costo_estimado': round((dosis_npk * superficie * 0.5) + 
                                 (urea_adicional * superficie * 0.4) +
                                 (superfosfato_adicional * superficie * 0.6) +
                                 (muriato_adicional * superficie * 0.3))
        }
    
    context = {
        'resultado': resultado,
        'cultivos': ['papa', 'maiz', 'trigo', 'tomate', 'palto']
    }
    
    return render(request, 'calculadoras/fertilizacion.html', context)


def calculadora_agua(request):
    """Calculadora de lámina de riego basada en ET0 y coeficiente de cultivo"""
    resultado = None
    if request.method == 'POST':
        et0 = float(request.POST.get('et0', 0))  # ET0 (mm/día)
        kc = float(request.POST.get('kc', 1))    # Coeficiente cultivo
        eficiencia = float(request.POST.get('eficiencia', 0.7))  # Eficiencia riego
        frecuencia = int(request.POST.get('frecuencia', 7))     # días entre riegos
        
        # Lámina diaria de agua requerida (mm)
        lamina_diaria = et0 * kc
        # Lámina por evento (mm)
        lamina_evento = lamina_diaria * frecuencia / eficiencia
        
        # Convertir mm a m3/ha: 1 mm = 10 m3/ha
        volumen_evento = lamina_evento * 10
        
        resultado = {
            'lamina_diaria': round(lamina_diaria,1),
            'lamina_evento': round(lamina_evento,1),
            'volumen_evento': round(volumen_evento,1)
        }
    return render(request, 'calculadoras/agua.html', {'resultado': resultado})


def calculadora_roi(request):
    """Calculadora de ROI y periodo de recuperación"""
    resultado = None
    if request.method == 'POST':
        inversion = float(request.POST.get('inversion',0))
        beneficio_anual = float(request.POST.get('beneficio_anual',0))
        
        roi = (beneficio_anual / inversion) * 100 if inversion>0 else 0
        payback = inversion / beneficio_anual if beneficio_anual>0 else None
        
        resultado = {'roi': round(roi,1), 'payback': round(payback,1) if payback else None}
    return render(request,'calculadoras/roi.html', {'resultado': resultado})


def calculadora_siembra(request):
    """Calculadora de densidad de siembra"""
    resultado = None
    if request.method=='POST':
        densidad_planta = float(request.POST.get('densidad_planta',3000)) # plantas/ha ideal
        supervivencia = float(request.POST.get('supervivencia',0.9))     # tasa supervivencia
        
        # Plantas a sembrar = densidad_planta / supervivencia
        plantas_necesarias = densidad_planta / supervivencia
        
        resultado={'plantas_necesarias': int(round(plantas_necesarias,0))}
    return render(request,'calculadoras/siembra.html', {'resultado': resultado})


def calculadora_balance_hidrico(request):

    resultado = None
    if request.method=='POST':
        precipitacion = float(request.POST.get('precipitacion',0))   # mm
        etc = float(request.POST.get('etc',0))                         # mm
        infiltracion = float(request.POST.get('infiltracion',0))       # mm
        
        balance = precipitacion - etc - infiltracion
        
        resultado={'balance': round(balance,1)}
    return render(request,'calculadoras/balance_hidrico.html',{'resultado':resultado})