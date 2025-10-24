#!/usr/bin/env python3
"""
Script de instalación automática para AgroPredict
Versión con nuevas funcionalidades: Widget climático, análisis de consumo de agua,
análisis de predicción y comparación de predicciones.
"""

import os
import sys
import subprocess
import platform

def run_command(command, description):
    """Ejecuta un comando y maneja errores"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completado")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en {description}: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def check_python_version():
    """Verifica que la versión de Python sea compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Se requiere Python 3.8 o superior")
        print(f"Versión actual: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor} es compatible")
    return True

def main():
    print("🌱 AgroPredict - Instalación Automática")
    print("=" * 50)
    print("Sistema de Predicciones Agrícolas con:")
    print("• Widget climático integrado")
    print("• Análisis de consumo de agua")
    print("• Análisis de ROI e inversión")
    print("• Comparación de predicciones")
    print("=" * 50)

    # Verificar Python
    if not check_python_version():
        sys.exit(1)

    # Detectar sistema operativo
    sistema = platform.system()
    print(f"Sistema operativo detectado: {sistema}")

    # Verificar si estamos en el directorio correcto
    if not os.path.exists('manage.py'):
        print("⚠️  No se encontró manage.py")
        print("Este script debe ejecutarse en el directorio raíz del proyecto Django")
        respuesta = input("¿Desea continuar? (s/n): ")
        if respuesta.lower() != 's':
            sys.exit(1)

    # Crear entorno virtual
    if not os.path.exists('venv'):
        if not run_command('python -m venv venv', "Creando entorno virtual"):
            print("⚠️ Intentando con python3...")
            if not run_command('python3 -m venv venv', "Creando entorno virtual con python3"):
                print("❌ No se pudo crear el entorno virtual")
                sys.exit(1)
    else:
        print("✅ Entorno virtual ya existe")

    # Activar entorno virtual y instalar dependencias
    if sistema == "Windows":
        activate_cmd = "venv\\Scripts\\activate"
        pip_cmd = "venv\\Scripts\\pip"
        python_cmd = "venv\\Scripts\\python"
    else:
        activate_cmd = "source venv/bin/activate"
        pip_cmd = "venv/bin/pip"
        python_cmd = "venv/bin/python"

    # Instalar dependencias
    if not run_command(f'{pip_cmd} install --upgrade pip', "Actualizando pip"):
        print("⚠️ No se pudo actualizar pip, continuando...")

    if not run_command(f'{pip_cmd} install -r requirements.txt', "Instalando dependencias"):
        print("❌ Error instalando dependencias")
        sys.exit(1)

    # Crear migraciones
    if not run_command(f'{python_cmd} manage.py makemigrations', "Creando migraciones"):
        print("❌ Error creando migraciones")
        sys.exit(1)

    # Aplicar migraciones
    if not run_command(f'{python_cmd} manage.py migrate', "Aplicando migraciones"):
        print("❌ Error aplicando migraciones")
        sys.exit(1)

 
       # Poblar datos iniciales
    if not run_command(f'{python_cmd} manage.py poblar_sin_emojis_fix', "Poblando datos iniciales sin emojis"):
        print("❌ Error poblando datos")
        sys.exit(1)


    # Crear archivo .env para configuración
    if not os.path.exists('.env'):
        if not run_command('echo "ACCUWEATHER_API_KEY=demo_key" > .env', "Creando archivo de configuración"):
            print("⚠️ No se pudo crear archivo .env")
    
    # Crear directorio para logs
    if not os.path.exists('logs'):
        if not run_command('mkdir logs', "Creando directorio de logs"):
            print("⚠️ No se pudo crear directorio de logs")

    # Collectstatic (solo si existe la carpeta static)
    if os.path.exists('static'):
        run_command(f'{python_cmd} manage.py collectstatic --noinput', "Recolectando archivos estáticos")

    print("\n" + "=" * 60)
    print("🎉 ¡INSTALACIÓN COMPLETADA EXITOSAMENTE!")
    print("=" * 60)
    
    print("\n📋 Funcionalidades implementadas:")
    print("✅ Widget climático en dashboard (parte inferior derecha)")
    print("✅ Cálculo automático de consumo de agua por especie")
    print("✅ Análisis de ROI e inversión con recomendaciones")
    print("✅ Comparación de múltiples predicciones")
    print("✅ Navegación mejorada con nuevas secciones")

    print("\n🚀 Para iniciar el servidor:")
    if sistema == "Windows":
        print("   venv\\Scripts\\activate")
        print("   python manage.py runserver")
    else:
        print("   source venv/bin/activate")
        print("   python manage.py runserver")

    print("\n🌐 Acceder a:")
    print("   • Dashboard: http://127.0.0.1:8000/")
    print("   • Análisis: http://127.0.0.1:8000/analisis/")
    print("   • Comparación: http://127.0.0.1:8000/comparacion/")
    print("   • Admin: http://127.0.0.1:8000/admin/")

    print("\n📋 Configuración adicional:")
    print("1. Para usar datos climáticos reales:")
    print("   - Registrarse en AccuWeather Developer")
    print("   - Obtener API key gratuita")
    print("   - Agregar ACCUWEATHER_API_KEY=tu_key al archivo .env")
    print("\n2. Para personalizar precios y costos:")
    print("   - Ir al admin panel")
    print("   - Editar 'Tipos de Árboles'")
    print("   - Actualizar precios y costos según mercado local")

    print("\n3. Para crear superusuario del admin:")
    if sistema == "Windows":
        print("   venv\\Scripts\\python manage.py createsuperuser")
    else:
        print("   venv/bin/python manage.py createsuperuser")

    print("\n💡 El sistema incluye datos de ejemplo para empezar a usar inmediatamente")
    print("📧 Para soporte, consultar los archivos de documentación incluidos")

if __name__ == "__main__":
    main()