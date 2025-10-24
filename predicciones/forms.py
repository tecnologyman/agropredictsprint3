from django import forms
from .models import Prediccion, TipoArbol, Comuna

class PrediccionForm(forms.ModelForm):
    class Meta:
        model = Prediccion
        fields = [
            'tipo_arbol', 'comuna', 'hectareas', 'edad_arboles', 
            'densidad_plantacion', 'tipo_riego', 'tipo_suelo', 'fertilizacion'
        ]
        
        widgets = {
            'tipo_arbol': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'comuna': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'hectareas': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'placeholder': 'Ej: 5.5'
            }),
            'edad_arboles': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100',
                'placeholder': 'Ej: 8'
            }),
            'densidad_plantacion': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '50',
                'max': '2000',
                'placeholder': 'Ej: 300'
            }),
            'tipo_riego': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'tipo_suelo': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'fertilizacion': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
        }
        
        labels = {
            'tipo_arbol': 'Tipo de Árbol',
            'comuna': 'Comuna',
            'hectareas': 'Hectáreas',
            'edad_arboles': 'Edad de los Árboles (años)',
            'densidad_plantacion': 'Densidad de Plantación (árboles/ha)',
            'tipo_riego': 'Tipo de Riego',
            'tipo_suelo': 'Tipo de Suelo',
            'fertilizacion': 'Tipo de Fertilización',
        }
        
        help_texts = {
            'hectareas': 'Superficie total del cultivo en hectáreas',
            'edad_arboles': 'Edad promedio de los árboles',
            'densidad_plantacion': 'Número de árboles por hectárea',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['comuna'].queryset = Comuna.objects.select_related('region').order_by('region__nombre', 'nombre')
        self.fields['tipo_arbol'].queryset = TipoArbol.objects.all().order_by('tipo')

# NUEVO FORMULARIO PARA ANÁLISIS DE PREDICCIÓN
class AnalisisPrediccionForm(forms.Form):
    prediccion = forms.ModelChoiceField(
        queryset=Prediccion.objects.none(),  # ← se setea en __init__
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        }),
        label='Seleccionar Predicción para Analizar',
        help_text='Elija una predicción completada para realizar análisis detallado'
    )
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar SOLO por predicciones completadas del usuario
        qs = Prediccion.objects.filter(
            estado='completada',
            usuario=user
        ).select_related('tipo_arbol', 'comuna').order_by('-fecha_creacion') if user else Prediccion.objects.none()

        self.fields['prediccion'].queryset = qs

        # Opciones legibles
        choices = []
        for p in qs:
            label = f"{p.tipo_arbol} - {p.comuna} - {p.fecha_creacion.strftime('%d/%m/%Y')}"
            if p.roi_proyectado:
                label += f" (ROI: {p.roi_proyectado:.1f}%)"
            choices.append((p.id, label))
        self.fields['prediccion'].choices = [('', 'Seleccione una predicción')] + choices


# NUEVO FORMULARIO PARA COMPARACIÓN DE PREDICCIONES
class ComparacionPrediccionesForm(forms.Form):
    predicciones = forms.ModelMultipleChoiceField(
        queryset=Prediccion.objects.filter(estado='completada'),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label='Seleccionar Predicciones para Comparar',
        help_text='Seleccione entre 2 y 5 predicciones para comparar',
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['predicciones'].queryset = Prediccion.objects.filter(
            estado='completada'
        ).select_related('tipo_arbol', 'comuna').order_by('-fecha_creacion')
    
    def clean_predicciones(self):
        predicciones = self.cleaned_data['predicciones']
        if len(predicciones) < 2:
            raise forms.ValidationError("Debe seleccionar al menos 2 predicciones para comparar.")
        if len(predicciones) > 5:
            raise forms.ValidationError("Puede seleccionar máximo 5 predicciones para comparar.")
        return predicciones