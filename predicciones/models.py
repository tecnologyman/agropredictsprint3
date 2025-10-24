from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import random
import requests
from django.conf import settings

class Region(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, unique=True)
    latitud = models.FloatField(null=True, blank=True)  # NUEVO
    longitud = models.FloatField(null=True, blank=True)  # NUEVO
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Región"
        verbose_name_plural = "Regiones"

class Comuna(models.Model):
    nombre = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='comunas')
    codigo = models.CharField(max_length=10, unique=True)
    latitud = models.FloatField(null=True, blank=True)  # NUEVO
    longitud = models.FloatField(null=True, blank=True)  # NUEVO
    
    def __str__(self):
        return f"{self.nombre}, {self.region.nombre}"
    
    class Meta:
        verbose_name = "Comuna"
        verbose_name_plural = "Comunas"

class TipoArbol(models.Model):
    TIPO_CHOICES = [
        ('palto', 'Palto'),
        ('naranjo', 'Naranjo'),
        ('limonero', 'Limonero'),
        ('manzano', 'Manzano'),
        ('cerezo', 'Cerezo'),
        ('nogal', 'Nogal'),
        ('almendro', 'Almendro'),
        ('olivo', 'Olivo'),
        ('durazno', 'Durazno'),
        ('peral', 'Peral'),
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, unique=True)
    nombre_cientifico = models.CharField(max_length=100, blank=True)
    rendimiento_base = models.FloatField(help_text="Toneladas por hectárea promedio")
    
    # NUEVOS CAMPOS PARA ANÁLISIS ECONÓMICO
    precio_promedio_ton = models.FloatField(
        default=0, 
        help_text="Precio promedio por tonelada en CLP"
    )
    costo_plantacion_hectarea = models.FloatField(
        default=0,
        help_text="Costo de plantación por hectárea en CLP"
    )
    costo_mantenimiento_anual = models.FloatField(
        default=0,
        help_text="Costo de mantenimiento anual por hectárea en CLP"
    )
    
    # NUEVOS CAMPOS PARA CONSUMO DE AGUA
    consumo_agua_m3_ton = models.FloatField(
        default=0,
        help_text="Metros cúbicos de agua por tonelada producida"
    )
    
    def calcular_roi_proyectado(self, hectareas, anos=5):
        """Calcula ROI proyectado a X años"""
        if self.precio_promedio_ton == 0 or self.rendimiento_base == 0:
            return 0
            
        # Ingresos anuales
        ingresos_anuales = (self.rendimiento_base * hectareas * self.precio_promedio_ton)
        
        # Costos
        costo_inicial = self.costo_plantacion_hectarea * hectareas
        costo_mantenimiento_total = self.costo_mantenimiento_anual * hectareas * anos
        costo_total = costo_inicial + costo_mantenimiento_total
        
        # Ingresos totales
        ingresos_totales = ingresos_anuales * anos
        
        # ROI
        if costo_total > 0:
            roi = ((ingresos_totales - costo_total) / costo_total) * 100
            return round(roi, 2)
        return 0
    
    def __str__(self):
        return self.get_tipo_display()
    
    class Meta:
        verbose_name = "Tipo de Árbol"
        verbose_name_plural = "Tipos de Árboles"

class Prediccion(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('completada', 'Completada'),
        ('error', 'Error'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='predicciones')
    tipo_arbol = models.ForeignKey(TipoArbol, on_delete=models.CASCADE)
    comuna = models.ForeignKey(Comuna, on_delete=models.CASCADE)
    
    # Datos del cultivo
    hectareas = models.FloatField(validators=[MinValueValidator(0.1)])
    edad_arboles = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    densidad_plantacion = models.IntegerField(
        help_text="Número de árboles por hectárea",
        validators=[MinValueValidator(50), MaxValueValidator(2000)]
    )
    
    # Condiciones
    tipo_riego = models.CharField(max_length=20, choices=[
        ('goteo', 'Goteo'),
        ('aspersion', 'Aspersión'),
        ('gravedad', 'Gravedad'),
        ('micro_aspersion', 'Microaspersión'),
    ])
    
    tipo_suelo = models.CharField(max_length=20, choices=[
        ('arcilloso', 'Arcilloso'),
        ('arenoso', 'Arenoso'),
        ('franco', 'Franco'),
        ('limoso', 'Limoso'),
    ])
    
    fertilizacion = models.CharField(max_length=20, choices=[
        ('organica', 'Orgánica'),
        ('quimica', 'Química'),
        ('mixta', 'Mixta'),
        ('ninguna', 'Ninguna'),
    ])
    
    # Resultados de la predicción
    produccion_total = models.FloatField(null=True, blank=True, help_text="Toneladas totales")
    produccion_por_hectarea = models.FloatField(null=True, blank=True, help_text="Toneladas por hectárea")
    confiabilidad = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Porcentaje de confiabilidad"
    )
    
    # NUEVOS CAMPOS PARA ANÁLISIS ECONÓMICO
    inversion_estimada = models.FloatField(null=True, blank=True, help_text="Inversión total estimada en CLP")
    ingresos_proyectados_5anos = models.FloatField(null=True, blank=True, help_text="Ingresos proyectados a 5 años")
    roi_proyectado = models.FloatField(null=True, blank=True, help_text="ROI proyectado a 5 años (%)")
    
    # NUEVOS CAMPOS PARA CONSUMO DE AGUA
    consumo_agua_total = models.FloatField(null=True, blank=True, help_text="Consumo total de agua en m³")
    consumo_agua_por_hectarea = models.FloatField(null=True, blank=True, help_text="Consumo de agua por hectárea en m³")
    
    # Control de estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def calcular_prediccion(self):
        """Simula el cálculo de predicción usando factores diversos"""
        # Obtener rendimiento base del tipo de árbol
        base = self.tipo_arbol.rendimiento_base
        
        # Factores que afectan la producción
        factor_edad = self._factor_edad()
        factor_densidad = self._factor_densidad()
        factor_riego = self._factor_riego()
        factor_suelo = self._factor_suelo()
        factor_fertilizacion = self._factor_fertilizacion()
        factor_regional = self._factor_regional()
        
        # Calcular producción por hectárea
        self.produccion_por_hectarea = base * factor_edad * factor_densidad * factor_riego * factor_suelo * factor_fertilizacion * factor_regional
        
        # Calcular producción total
        self.produccion_total = self.produccion_por_hectarea * self.hectareas
        
        # NUEVO: Calcular consumo de agua
        self._calcular_consumo_agua()
        
        # NUEVO: Calcular análisis económico
        self._calcular_analisis_economico()
        
        # Calcular confiabilidad (entre 70% y 95%)
        base_confiabilidad = 85
        variacion = random.uniform(-15, 10)
        self.confiabilidad = max(70, min(95, int(base_confiabilidad + variacion)))
        
        self.estado = 'completada'
        self.save()
    
    def _calcular_consumo_agua(self):
        """Calcula el consumo de agua basado en la producción"""
        if self.produccion_total and self.tipo_arbol.consumo_agua_m3_ton:
            self.consumo_agua_total = self.produccion_total * self.tipo_arbol.consumo_agua_m3_ton
            self.consumo_agua_por_hectarea = self.consumo_agua_total / self.hectareas
        else:
            # Valores por defecto si no hay datos específicos
            agua_base_por_hectarea = {
                'palto': 8000,
                'naranjo': 6500,
                'limonero': 6000,
                'manzano': 4500,
                'cerezo': 5500,
                'nogal': 7000,
                'almendro': 5000,
                'olivo': 3500,
                'durazno': 5000,
                'peral': 4800,
            }
            
            self.consumo_agua_por_hectarea = agua_base_por_hectarea.get(self.tipo_arbol.tipo, 5000)
            self.consumo_agua_total = self.consumo_agua_por_hectarea * self.hectareas
    
    def _calcular_analisis_economico(self):
        """Calcula el análisis económico de la predicción"""
        if not self.tipo_arbol.precio_promedio_ton:
            return
            
        # Calcular inversión inicial
        costo_plantacion = self.tipo_arbol.costo_plantacion_hectarea * self.hectareas
        costo_mantenimiento_5anos = self.tipo_arbol.costo_mantenimiento_anual * self.hectareas * 5
        self.inversion_estimada = costo_plantacion + costo_mantenimiento_5anos
        
        # Calcular ingresos proyectados a 5 años
        if self.produccion_por_hectarea:
            ingresos_anuales = self.produccion_por_hectarea * self.hectareas * self.tipo_arbol.precio_promedio_ton
            self.ingresos_proyectados_5anos = ingresos_anuales * 5
            
            # Calcular ROI
            if self.inversion_estimada > 0:
                ganancia_neta = self.ingresos_proyectados_5anos - self.inversion_estimada
                self.roi_proyectado = (ganancia_neta / self.inversion_estimada) * 100
    
    def _factor_edad(self):
        """Factor basado en la edad de los árboles"""
        if self.edad_arboles <= 3:
            return 0.3
        elif self.edad_arboles <= 7:
            return 0.8
        elif self.edad_arboles <= 15:
            return 1.0
        else:
            return 0.9
    
    def _factor_densidad(self):
        """Factor basado en la densidad de plantación"""
        if self.densidad_plantacion < 200:
            return 0.85
        elif self.densidad_plantacion <= 400:
            return 1.0
        else:
            return 0.95
    
    def _factor_riego(self):
        """Factor basado en el tipo de riego"""
        factores = {
            'goteo': 1.1,
            'micro_aspersion': 1.05,
            'aspersion': 0.95,
            'gravedad': 0.85
        }
        return factores.get(self.tipo_riego, 1.0)
    
    def _factor_suelo(self):
        """Factor basado en el tipo de suelo"""
        factores = {
            'franco': 1.1,
            'arcilloso': 0.95,
            'limoso': 1.0,
            'arenoso': 0.9
        }
        return factores.get(self.tipo_suelo, 1.0)
    
    def _factor_fertilizacion(self):
        """Factor basado en el tipo de fertilización"""
        factores = {
            'mixta': 1.15,
            'quimica': 1.05,
            'organica': 1.0,
            'ninguna': 0.8
        }
        return factores.get(self.fertilizacion, 1.0)
    
    def _factor_regional(self):
        """Factor basado en la región (simulado)"""
        return random.uniform(0.9, 1.1)
    
    def get_rentabilidad_categoria(self):
        """Clasifica la rentabilidad de la predicción"""
        if not self.roi_proyectado:
            return "Sin datos"
        
        if self.roi_proyectado >= 50:
            return "Muy Alta"
        elif self.roi_proyectado >= 30:
            return "Alta"
        elif self.roi_proyectado >= 15:
            return "Media"
        elif self.roi_proyectado >= 0:
            return "Baja"
        else:
            return "Negativa"
    
    def __str__(self):
        return f"Predicción {self.tipo_arbol} - {self.comuna} ({self.fecha_creacion.strftime('%d/%m/%Y')})"
    
    class Meta:
        verbose_name = "Predicción"
        verbose_name_plural = "Predicciones"
        ordering = ['-fecha_creacion']

# NUEVO MODELO PARA DATOS CLIMÁTICOS
class DatoClimatico(models.Model):
    comuna = models.ForeignKey(Comuna, on_delete=models.CASCADE)
    fecha = models.DateTimeField()
    temperatura_actual = models.FloatField()
    humedad = models.IntegerField()
    descripcion_clima = models.CharField(max_length=100)
    icono_clima = models.CharField(max_length=50)
    
    class Meta:
        verbose_name = "Dato Climático"
        verbose_name_plural = "Datos Climáticos"
        unique_together = ['comuna', 'fecha']

# NUEVO MODELO PARA ANÁLISIS DE PREDICCIONES
class AnalisisPrediccion(models.Model):
    prediccion = models.OneToOneField(Prediccion, on_delete=models.CASCADE, related_name='analisis')
    fecha_analisis = models.DateTimeField(auto_now_add=True)
    
    # Análisis de rentabilidad
    categoria_rentabilidad = models.CharField(max_length=20)
    recomendacion = models.TextField()
    
    # Comparación con otras especies
    mejor_alternativa = models.ForeignKey(
        TipoArbol, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='analisis_como_alternativa'
    )
    
    class Meta:
        verbose_name = "Análisis de Predicción"
        verbose_name_plural = "Análisis de Predicciones"