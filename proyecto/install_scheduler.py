# proyecto/install_scheduler.py
"""
Script de instalación y configuración del sistema de tareas programadas
"""

import os
import sys
import subprocess
from pathlib import Path

def install_dependencies():
    """Instala las dependencias necesarias"""
    print("📦 Instalando dependencias del scheduler...")
    
    dependencies = [
        "schedule",  # Para programación de tareas (alternativa más simple)
        "croniter",  # Para parsing de expresiones cron
    ]
    
    for dep in dependencies:
        try:
            print(f"📥 Instalando {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"✅ {dep} instalado correctamente")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error instalando {dep}: {str(e)}")
            return False
    
    return True

def create_scheduler_directories():
    """Crea los directorios necesarios para el scheduler"""
    print("📁 Creando directorios del scheduler...")
    
    base_dir = Path(__file__).parent
    scheduler_dir = base_dir / "scheduler"
    
    # Crear directorio scheduler si no existe
    scheduler_dir.mkdir(exist_ok=True)
    
    # Crear archivo __init__.py si no existe
    init_file = scheduler_dir / "__init__.py"
    if not init_file.exists():
        with open(init_file, 'w') as f:
            f.write('# Módulo de tareas programadas\n')
    
    # Crear directorio de configuración del usuario
    config_dir = Path.home() / ".pornhub_downloader"
    config_dir.mkdir(exist_ok=True)
    
    print(f"✅ Directorios creados:")
    print(f"   - {scheduler_dir}")
    print(f"   - {config_dir}")

def test_scheduler_installation():
    """Prueba que el scheduler se pueda importar correctamente"""
    print("🧪 Probando instalación del scheduler...")
    
    try:
        # Intentar importar los módulos del scheduler
        sys.path.insert(0, str(Path(__file__).parent))
        
        from scheduler.task_scheduler import TaskScheduler, ScheduledTask, TaskFrequency, TaskStatus
        from scheduler.auto_scraper import AutoScraper
        
        print("✅ Módulos del scheduler importados correctamente")
        
        # Crear instancia de prueba
        scheduler = TaskScheduler()
        auto_scraper = AutoScraper()
        
        print("✅ Instancias creadas correctamente")
        
        # Verificar estado
        status = scheduler.get_scheduler_status()
        print(f"✅ Estado del scheduler: {status}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error importando módulos: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        return False

def show_usage_instructions():
    """Muestra las instrucciones de uso"""
    print("\n" + "="*60)
    print("📋 INSTRUCCIONES DE USO DEL SCHEDULER")
    print("="*60)
    
    print("""
🚀 CÓMO USAR EL SISTEMA DE TAREAS PROGRAMADAS:

1. 📅 CREAR TAREAS PROGRAMADAS:
   - Abre la aplicación principal
   - Ve a la pestaña "Tareas Programadas" (Ctrl+T)
   - Haz clic en "➕ Nueva Tarea"
   - Configura:
     * Nombre de la tarea
     * Categoría web a scrapear
     * Fecha y hora de ejecución
     * Frecuencia (una vez, diario, semanal, etc.)
     * Máximo de videos por ejecución
     * Si auto-publicar en WordPress

2. ⚙️ OPCIONES DE FRECUENCIA:
   - 🔸 Una sola vez: Se ejecuta solo una vez
   - 🔸 Cada hora: Se repite cada hora
   - 🔸 Diario: Se ejecuta una vez al día
   - 🔸 Semanal: Se ejecuta una vez por semana
   - 🔸 Mensual: Se ejecuta una vez al mes
   - 🔸 Personalizado: Define tu propio intervalo

3. 🎯 PROCESO AUTOMÁTICO:
   Una vez programada, la tarea:
   - Visitará la categoría web automáticamente
   - Descargará los videos especificados
   - Los subirá a StreamWish (si está configurado)
   - Los publicará en WordPress con la categoría correcta
   - Registrará los resultados en el log

4. 📊 MONITOREO:
   - Ve el estado en tiempo real
   - Consulta estadísticas de ejecución
   - Revisa el log de actividad
   - Pausa/reanuda tareas según necesites

5. 🛠️ CONFIGURACIÓN AVANZADA:
   - Ajusta delays entre videos
   - Configura categorías por defecto
   - Personaliza intervalos de ejecución
   - Define máximos de videos por tarea

💡 EJEMPLO DE USO:
   "Quiero que todos los días a las 9:00 AM se descarguen automáticamente
   los primeros 20 videos de la categoría 'Popular' y se publiquen en mi web"
   
   → Crear tarea con:
     - Nombre: "Scraping diario Popular"
     - Categoría: Popular
     - Fecha: Mañana 9:00 AM
     - Frecuencia: Diario
     - Máx videos: 20
     - Auto-publicar: ✅

⚠️ IMPORTANTE:
   - Asegúrate de que StreamWish esté configurado
   - Verifica la conexión a la base de datos
   - Las tareas se ejecutan en segundo plano
   - El scheduler debe estar activo para funcionar

🔑 ATAJOS DE TECLADO:
   - Ctrl+T: Ir a tareas programadas
   - Ctrl+1: Ir a explorar categorías
   - F5: Refrescar todo
""")

def main():
    """Función principal de instalación"""
    print("🚀 INSTALADOR DEL SISTEMA DE TAREAS PROGRAMADAS")
    print("=" * 50)
    
    # Verificar Python
    if sys.version_info < (3, 7):
        print("❌ Se requiere Python 3.7 o superior")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detectado")
    
    # Instalar dependencias
    if not install_dependencies():
        print("❌ Error instalando dependencias")
        return False
    
    # Crear directorios
    create_scheduler_directories()
    
    # Probar instalación
    if not test_scheduler_installation():
        print("❌ Error en las pruebas de instalación")
        return False
    
    print("\n✅ SCHEDULER INSTALADO EXITOSAMENTE!")
    
    # Mostrar instrucciones
    show_usage_instructions()
    
    return True

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎉 ¡Instalación completada!")
        print("👉 Ahora puedes ejecutar la aplicación principal y usar las tareas programadas")
        sys.exit(0)
    else:
        print("\n💥 Instalación falló")
        print("👉 Revisa los errores mostrados arriba")
        sys.exit(1)