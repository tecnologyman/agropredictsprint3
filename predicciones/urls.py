from django.urls import path
from . import views

urlpatterns = [
    # === PRINCIPALES ===
    path('', views.dashboard, name='home'),  # ← raíz de la app al dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # === PREDICCIONES ===
    path('nueva/', views.nueva_prediccion, name='nueva_prediccion'),
    path('prediccion/<int:pk>/', views.prediccion_detalle, name='prediccion_detalle'),
    path('predicciones/', views.lista_predicciones, name='lista_predicciones'),
    path('prediccion/<int:pk>/eliminar/', views.eliminar_prediccion, name='eliminar_prediccion'),

    # === ANÁLISIS ===
    path('analisis/', views.analisis_prediccion, name='analisis_prediccion'),
    path('analisis/<int:pk>/', views.analisis_prediccion_detalle, name='analisis_prediccion_detalle'),

    # === COMPARACIÓN ===
    path('comparacion/', views.comparacion_predicciones, name='comparacion_predicciones'),

    # === APIs ===
    path('api/comunas/', views.api_comunas_por_region, name='api_comunas'),

    # === IA ===
    path('ia/', views.ia_consulta, name='ia_consulta'),
    path('ia/chat/', views.ia_chat_page, name='ia_chat_page'),

    # === MICRO SERVICIOS ===
    path('ms/ping/', views.ms_ping_view, name='ms_ping'),
    path('ms/echo/', views.ms_echo_view, name='ms_echo'),

    # === CALCULADORAS ===
    path('calculadoras/', views.calculadoras_agricolas, name='calculadoras_agricolas'),
    path('calculadoras/fertilizacion/', views.calculadora_fertilizacion, name='calculadora_fertilizacion'),
    path('calculadoras/agua/', views.calculadora_agua, name='calculadora_agua'),
    path('calculadoras/roi/', views.calculadora_roi, name='calculadora_roi'),
    path('calculadoras/siembra/', views.calculadora_siembra, name='calculadora_siembra'),
    path('calculadoras/balance-hidrico/', views.calculadora_balance_hidrico, name='calculadora_balance_hidrico'),
]
