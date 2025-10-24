from django.core.management.base import BaseCommand
from predicciones.models import Region, Comuna, TipoArbol, Prediccion
from django.contrib.auth.models import User
import random

class Command(BaseCommand):
    help = 'Populate the database with initial data for AgroPredict without emojis'

    def handle(self, *args, **options):
        self.stdout.write('Starting data population')

        # Create regions
        regions_data = [
            {'nombre': 'Región Metropolitana', 'codigo': 'RM'},
            {'nombre': 'Región de Valparaíso', 'codigo': 'VA'},
            {'nombre': "Región de O'Higgins", 'codigo': 'OH'},
            {'nombre': 'Región del Maule', 'codigo': 'MA'},
            {'nombre': 'Región de Coquimbo', 'codigo': 'CO'},
        ]

        self.stdout.write('+ Creating regions')
        for data in regions_data:
            region, created = Region.objects.get_or_create(
                codigo=data['codigo'],
                defaults={'nombre': data['nombre']}
            )
            if created:
                self.stdout.write(f'Region created: {region.nombre}')
            else:
                self.stdout.write(f'Region exists: {region.nombre}')

        # Create communes
        communes_data = [
            {'nombre': 'Santiago', 'codigo': 'ST', 'region_codigo': 'RM'},
            {'nombre': 'Valparaíso', 'codigo': 'VP', 'region_codigo': 'VA'},
            {'nombre': 'Rancagua', 'codigo': 'RA', 'region_codigo': 'OH'},
            {'nombre': 'Talca', 'codigo': 'TC', 'region_codigo': 'MA'},
            {'nombre': 'La Serena', 'codigo': 'LS', 'region_codigo': 'CO'},
        ]

        self.stdout.write('+ Creating communes')
        for data in communes_data:
            try:
                region = Region.objects.get(codigo=data['region_codigo'])
                commune, created = Comuna.objects.get_or_create(
                    codigo=data['codigo'],
                    defaults={'nombre': data['nombre'], 'region': region}
                )
                if created:
                    self.stdout.write(f'Commune created: {commune.nombre}')
                else:
                    self.stdout.write(f'Commune exists: {commune.nombre}')
            except Region.DoesNotExist:
                self.stdout.write(f'Region not found: {data["region_codigo"]}')

        # Create tree types
        tree_types = [
            {'tipo': 'palto', 'nombre_cientifico': 'Persea americana', 'rendimiento_base': 12.5},
            {'tipo': 'manzano', 'nombre_cientifico': 'Malus domestica', 'rendimiento_base': 45.0},
            {'tipo': 'cerezo', 'nombre_cientifico': 'Prunus avium', 'rendimiento_base': 8.5},
        ]

        self.stdout.write('+ Creating tree types')
        for data in tree_types:
            tree, created = TipoArbol.objects.get_or_create(
                tipo=data['tipo'],
                defaults={
                    'nombre_cientifico': data['nombre_cientifico'],
                    'rendimiento_base': data['rendimiento_base']
                }
            )
            if created:
                self.stdout.write(f'Tree type created: {tree.get_tipo_display()}')
            else:
                self.stdout.write(f'Tree type exists: {tree.get_tipo_display()}')

        # Create anonymous user
        user, created = User.objects.get_or_create(
            username='anonimo',
            defaults={'first_name': 'Usuario', 'last_name': 'Anonimo'}
        )
        if created:
            self.stdout.write('Anonymous user created')
        else:
            self.stdout.write('Anonymous user exists')

        # Create example predictions
        self.stdout.write('+ Creating example predictions')
        for i in range(3):
            tree = TipoArbol.objects.order_by('?').first()
            commune = Comuna.objects.order_by('?').first()
            pred = Prediccion(
                usuario=user,
                tipo_arbol=tree,
                comuna=commune,
                hectareas=round(random.uniform(1,5),1),
                edad_arboles=random.randint(3,10),
                densidad_plantacion=random.randint(200,400),
                tipo_riego='goteo',
                tipo_suelo='franco',
                fertilizacion='mixta'
            )
            pred.estado='procesando'
            pred.save()
            pred.calcular_prediccion()
            self.stdout.write(f'Prediction created: {pred}')

        self.stdout.write('Data population completed successfully')