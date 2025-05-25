# proyecto/scheduler/task_scheduler.py
import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Callable
import logging
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class TaskFrequency(Enum):
    """Frecuencias de ejecución de tareas"""
    ONCE = "once"           # Una sola vez
    DAILY = "daily"         # Diario
    WEEKLY = "weekly"       # Semanal
    MONTHLY = "monthly"     # Mensual
    HOURLY = "hourly"       # Cada hora
    CUSTOM = "custom"       # Intervalo personalizado

class TaskStatus(Enum):
    """Estados de las tareas"""
    PENDING = "pending"     # Pendiente
    RUNNING = "running"     # Ejecutándose
    COMPLETED = "completed" # Completada
    FAILED = "failed"       # Falló
    CANCELLED = "cancelled" # Cancelada
    PAUSED = "paused"       # Pausada

@dataclass
class ScheduledTask:
    """Representa una tarea programada"""
    id: str
    name: str
    description: str
    category_url: str
    category_name: str
    next_run: datetime
    frequency: TaskFrequency
    status: TaskStatus
    created_at: datetime
    last_run: Optional[datetime] = None
    last_result: Optional[str] = None
    run_count: int = 0
    max_videos: int = 50  # Máximo de videos a procesar por ejecución
    auto_publish: bool = True  # Si auto-publicar en WordPress
    
    # Configuración específica
    config: Dict = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}
    
    def to_dict(self):
        """Convierte a diccionario para serialización"""
        data = asdict(self)
        # Convertir datetime a string
        data['next_run'] = self.next_run.isoformat() if self.next_run else None
        data['created_at'] = self.created_at.isoformat()
        data['last_run'] = self.last_run.isoformat() if self.last_run else None
        data['frequency'] = self.frequency.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Crea instancia desde diccionario"""
        # Convertir strings a datetime
        if data.get('next_run'):
            data['next_run'] = datetime.fromisoformat(data['next_run'])
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('last_run'):
            data['last_run'] = datetime.fromisoformat(data['last_run'])
        
        # Convertir strings a enums
        data['frequency'] = TaskFrequency(data['frequency'])
        data['status'] = TaskStatus(data['status'])
        
        return cls(**data)

class TaskScheduler:
    """Programador de tareas automáticas"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or str(Path.home() / ".pornhub_downloader" / "scheduled_tasks.json")
        self.config_dir = Path(self.config_file).parent
        self.config_dir.mkdir(exist_ok=True)
        
        self.tasks: List[ScheduledTask] = []
        self.running = False
        self.scheduler_thread = None
        self.task_callbacks: Dict[str, Callable] = {}
        
        # Cargar tareas existentes
        self.load_tasks()
        
        logger.info(f"✅ TaskScheduler inicializado con {len(self.tasks)} tareas")
    
    def register_callback(self, task_type: str, callback: Callable):
        """Registra un callback para un tipo de tarea"""
        self.task_callbacks[task_type] = callback
        logger.info(f"📝 Callback registrado para: {task_type}")
    
    def add_task(self, task: ScheduledTask) -> bool:
        """Añade una nueva tarea"""
        try:
            # Verificar que no existe una tarea con el mismo ID
            if any(t.id == task.id for t in self.tasks):
                logger.error(f"❌ Ya existe una tarea con ID: {task.id}")
                return False
            
            self.tasks.append(task)
            self.save_tasks()
            
            logger.info(f"✅ Tarea añadida: {task.name} - Próxima ejecución: {task.next_run}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error añadiendo tarea: {str(e)}")
            return False
    
    def remove_task(self, task_id: str) -> bool:
        """Elimina una tarea"""
        try:
            original_count = len(self.tasks)
            self.tasks = [t for t in self.tasks if t.id != task_id]
            
            if len(self.tasks) < original_count:
                self.save_tasks()
                logger.info(f"🗑️ Tarea eliminada: {task_id}")
                return True
            else:
                logger.warning(f"⚠️ Tarea no encontrada: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error eliminando tarea: {str(e)}")
            return False
    
    def update_task(self, task_id: str, updates: Dict) -> bool:
        """Actualiza una tarea existente"""
        try:
            for task in self.tasks:
                if task.id == task_id:
                    for key, value in updates.items():
                        if hasattr(task, key):
                            setattr(task, key, value)
                    
                    self.save_tasks()
                    logger.info(f"📝 Tarea actualizada: {task_id}")
                    return True
            
            logger.warning(f"⚠️ Tarea no encontrada para actualizar: {task_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error actualizando tarea: {str(e)}")
            return False
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Obtiene una tarea por ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_all_tasks(self) -> List[ScheduledTask]:
        """Obtiene todas las tareas"""
        return self.tasks.copy()
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[ScheduledTask]:
        """Obtiene tareas por estado"""
        return [t for t in self.tasks if t.status == status]
    
    def start_scheduler(self):
        """Inicia el programador de tareas"""
        if self.running:
            logger.warning("⚠️ El scheduler ya está ejecutándose")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("🚀 Scheduler iniciado")
    
    def stop_scheduler(self):
        """Detiene el programador de tareas"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("⏹️ Scheduler detenido")
    
    def _scheduler_loop(self):
        """Loop principal del scheduler"""
        logger.info("🔄 Loop del scheduler iniciado")
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Buscar tareas pendientes que deben ejecutarse
                for task in self.tasks:
                    if (task.status == TaskStatus.PENDING and 
                        task.next_run and 
                        current_time >= task.next_run):
                        
                        self._execute_task(task)
                
                # Dormir por 30 segundos antes de la siguiente verificación
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Error en scheduler loop: {str(e)}")
                time.sleep(60)  # Esperar más tiempo si hay error
        
        logger.info("🔄 Loop del scheduler terminado")
    
    def _execute_task(self, task: ScheduledTask):
        """Ejecuta una tarea específica"""
        try:
            logger.info(f"🚀 Ejecutando tarea: {task.name}")
            
            # Cambiar estado a ejecutándose
            task.status = TaskStatus.RUNNING
            task.last_run = datetime.now()
            self.save_tasks()
            
            # Buscar callback registrado para scraping
            callback = self.task_callbacks.get('scrape_category')
            if callback:
                # Ejecutar scraping en hilo separado para no bloquear el scheduler
                task_thread = threading.Thread(
                    target=self._run_task_callback,
                    args=(callback, task),
                    daemon=True
                )
                task_thread.start()
            else:
                logger.error(f"❌ No hay callback registrado para scraping")
                task.status = TaskStatus.FAILED
                task.last_result = "No callback disponible"
                self._schedule_next_run(task)
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando tarea {task.name}: {str(e)}")
            task.status = TaskStatus.FAILED
            task.last_result = f"Error: {str(e)}"
            self._schedule_next_run(task)
    
    def _run_task_callback(self, callback: Callable, task: ScheduledTask):
        """Ejecuta el callback de la tarea en hilo separado"""
        try:
            # Ejecutar callback con parámetros de la tarea
            result = callback(
                category_url=task.category_url,
                category_name=task.category_name,
                max_videos=task.max_videos,
                auto_publish=task.auto_publish,
                task_config=task.config
            )
            
            # Actualizar resultado de la tarea
            if result:
                task.status = TaskStatus.COMPLETED
                task.last_result = f"Exitoso: {result.get('message', 'Completado')}"
                task.run_count += 1
            else:
                task.status = TaskStatus.FAILED
                task.last_result = "Falló sin detalles"
            
        except Exception as e:
            logger.error(f"❌ Error en callback de tarea {task.name}: {str(e)}")
            task.status = TaskStatus.FAILED
            task.last_result = f"Error callback: {str(e)}"
        
        finally:
            # Programar próxima ejecución
            self._schedule_next_run(task)
            self.save_tasks()
    
    def _schedule_next_run(self, task: ScheduledTask):
        """Programa la próxima ejecución de una tarea"""
        try:
            if task.frequency == TaskFrequency.ONCE:
                # Tarea de una sola vez, no reprogramar
                task.next_run = None
                logger.info(f"📅 Tarea única completada: {task.name}")
                
            elif task.frequency == TaskFrequency.HOURLY:
                task.next_run = datetime.now() + timedelta(hours=1)
                task.status = TaskStatus.PENDING
                
            elif task.frequency == TaskFrequency.DAILY:
                task.next_run = datetime.now() + timedelta(days=1)
                task.status = TaskStatus.PENDING
                
            elif task.frequency == TaskFrequency.WEEKLY:
                task.next_run = datetime.now() + timedelta(weeks=1)
                task.status = TaskStatus.PENDING
                
            elif task.frequency == TaskFrequency.MONTHLY:
                # Aproximación: 30 días
                task.next_run = datetime.now() + timedelta(days=30)
                task.status = TaskStatus.PENDING
                
            elif task.frequency == TaskFrequency.CUSTOM:
                # Usar intervalo personalizado desde config
                interval_hours = task.config.get('interval_hours', 24)
                task.next_run = datetime.now() + timedelta(hours=interval_hours)
                task.status = TaskStatus.PENDING
            
            if task.next_run:
                logger.info(f"📅 Próxima ejecución de {task.name}: {task.next_run}")
                
        except Exception as e:
            logger.error(f"❌ Error programando próxima ejecución: {str(e)}")
    
    def load_tasks(self):
        """Carga tareas desde archivo"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.tasks = []
                for task_data in data.get('tasks', []):
                    try:
                        task = ScheduledTask.from_dict(task_data)
                        self.tasks.append(task)
                    except Exception as e:
                        logger.error(f"❌ Error cargando tarea: {str(e)}")
                
                logger.info(f"📂 {len(self.tasks)} tareas cargadas desde {self.config_file}")
            else:
                logger.info("📂 No hay archivo de tareas, iniciando con lista vacía")
        
        except Exception as e:
            logger.error(f"❌ Error cargando tareas: {str(e)}")
            self.tasks = []
    
    def save_tasks(self):
        """Guarda tareas a archivo"""
        try:
            data = {
                'tasks': [task.to_dict() for task in self.tasks],
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"💾 Tareas guardadas en {self.config_file}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando tareas: {str(e)}")
    
    def pause_task(self, task_id: str) -> bool:
        """Pausa una tarea"""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.PAUSED
            self.save_tasks()
            logger.info(f"⏸️ Tarea pausada: {task.name}")
            return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """Reanuda una tarea pausada"""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PAUSED:
            task.status = TaskStatus.PENDING
            self.save_tasks()
            logger.info(f"▶️ Tarea reanudada: {task.name}")
            return True
        return False
    
    def get_scheduler_status(self) -> Dict:
        """Obtiene el estado del scheduler"""
        return {
            'running': self.running,
            'total_tasks': len(self.tasks),
            'pending_tasks': len(self.get_tasks_by_status(TaskStatus.PENDING)),
            'running_tasks': len(self.get_tasks_by_status(TaskStatus.RUNNING)),
            'completed_tasks': len(self.get_tasks_by_status(TaskStatus.COMPLETED)),
            'failed_tasks': len(self.get_tasks_by_status(TaskStatus.FAILED)),
            'paused_tasks': len(self.get_tasks_by_status(TaskStatus.PAUSED))
        }
    
    def cleanup_old_tasks(self, days_old: int = 30):
        """Limpia tareas antiguas completadas"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            original_count = len(self.tasks)
            
            self.tasks = [
                t for t in self.tasks 
                if not (t.status == TaskStatus.COMPLETED and 
                       t.last_run and 
                       t.last_run < cutoff_date)
            ]
            
            removed_count = original_count - len(self.tasks)
            if removed_count > 0:
                self.save_tasks()
                logger.info(f"🧹 {removed_count} tareas antiguas eliminadas")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"❌ Error limpiando tareas: {str(e)}")
            return 0