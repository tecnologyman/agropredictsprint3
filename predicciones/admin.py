from django.contrib import admin
from .models import Region, Comuna, TipoArbol, Prediccion

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    list_filter = ('nombre',)
    search_fields = ('nombre', 'codigo')
    ordering = ('nombre',)

@admin.register(Comuna)
class ComunaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'region', 'codigo')
    list_filter = ('region',)
    search_fields = ('nombre', 'codigo', 'region__nombre')
    ordering = ('region__nombre', 'nombre')

@admin.register(TipoArbol)
class TipoArbolAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'nombre_cientifico', 'rendimiento_base')
    list_filter = ('tipo',)
    search_fields = ('tipo', 'nombre_cientifico')
    ordering = ('tipo',)

@admin.register(Prediccion)
class PrediccionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'tipo_arbol', 'comuna', 'usuario', 'hectareas', 
        'produccion_por_hectarea', 'confiabilidad', 'estado', 'fecha_creacion'
    )
    list_filter = ('estado', 'tipo_arbol', 'comuna__region', 'fecha_creacion')
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name',
        'tipo_arbol__tipo', 'comuna__nombre'
    )
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    ordering = ('-fecha_creacion',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('usuario', 'tipo_arbol', 'comuna', 'estado')
        }),
        ('Datos del Cultivo', {
            'fields': ('hectareas', 'edad_arboles', 'densidad_plantacion')
        }),
        ('Condiciones', {
            'fields': ('tipo_riego', 'tipo_suelo', 'fertilizacion')
        }),
        ('Resultados', {
            'fields': ('produccion_total', 'produccion_por_hectarea', 'confiabilidad')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalcular_predicciones']
    
    def recalcular_predicciones(self, request, queryset):
        """Acción personalizada para recalcular predicciones"""
        count = 0
        for prediccion in queryset:
            prediccion.calcular_prediccion()
            count += 1
        
        self.message_user(
            request, 
            f'Se recalcularon {count} predicciones exitosamente.'
        )
    
    recalcular_predicciones.short_description = "Recalcular predicciones seleccionadas"