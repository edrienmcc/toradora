# proyecto/ui/scheduler_ui.py - CORREGIDO para categorías web extraídas
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTableWidget, QTableWidgetItem, 
                            QDialog, QLineEdit, QComboBox, QSpinBox,
                            QDateTimeEdit, QTextEdit, QCheckBox, QDialogButtonBox,
                            QMessageBox, QGroupBox, QScrollArea, QFrame,
                            QHeaderView, QAbstractItemView, QTabWidget,
                            QProgressBar, QSplitter)
from PyQt5.QtCore import Qt, QDateTime, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QIcon

from datetime import datetime, timedelta
import uuid
import logging

# Importar módulos del scheduler
try:
    from scheduler.task_scheduler import TaskScheduler, ScheduledTask, TaskFrequency, TaskStatus
    from scheduler.auto_scraper import AutoScraper
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    print("⚠️ Módulo de scheduler no disponible")

logger = logging.getLogger(__name__)

class TaskCreationDialog(QDialog):
    """Diálogo para crear nuevas tareas programadas"""
    
    def __init__(self, web_categories=None, db_categories=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📅 Crear Tarea Programada")
        self.setFixedSize(600, 800)
        self.web_categories = web_categories or []  # Categorías WEB extraídas (Anal, Checas, etc.)
        self.db_categories = db_categories or []    # Categorías BD para publicar en WordPress
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("📅 Nueva Tarea Programada")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e0e0e0; margin-bottom: 15px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Scroll área para el contenido
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Información básica
        basic_group = QGroupBox("📝 Información Básica")
        basic_layout = QVBoxLayout(basic_group)
        
        # Nombre de la tarea
        basic_layout.addWidget(QLabel("Nombre de la tarea:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Scraping diario de categoría Anal")
        basic_layout.addWidget(self.name_input)
        
        # Descripción
        basic_layout.addWidget(QLabel("Descripción:"))
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.description_input.setPlaceholderText("Descripción opcional de la tarea...")
        basic_layout.addWidget(self.description_input)
        
        content_layout.addWidget(basic_group)
        
        # Configuración de categoría WEB (para scrapear)
        web_category_group = QGroupBox("🌐 Categoría Web a Scrapear")
        web_category_layout = QVBoxLayout(web_category_group)
        
        # Selección de categoría web extraída
        web_category_layout.addWidget(QLabel("Categoría web extraída:"))
        self.web_category_combo = QComboBox()
        self.web_category_combo.addItem("Seleccionar categoría web...", "")
        
        # Agregar las categorías web extraídas (Anal, Checas, Cosplay, etc.)
        for category in self.web_categories:
            display_text = f"{category['title']} ({category['count']} videos)"
            self.web_category_combo.addItem(display_text, category['url'])
        
        web_category_layout.addWidget(self.web_category_combo)
        
        # URL manual (alternativa)
        web_category_layout.addWidget(QLabel("O URL manual de categoría:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://es.pornhub.com/categories/...")
        web_category_layout.addWidget(self.url_input)
        
        content_layout.addWidget(web_category_group)
        
        # Configuración de categoría BD (para publicar)
        db_category_group = QGroupBox("📂 Categoría WordPress (para publicar)")
        db_category_layout = QVBoxLayout(db_category_group)
        
        # Selección de categoría de base de datos
        db_category_layout.addWidget(QLabel("Categoría de WordPress donde publicar:"))
        self.db_category_combo = QComboBox()
        self.db_category_combo.addItem("Seleccionar categoría WordPress...", "")
        
        # Agregar las categorías de la base de datos
        for category in self.db_categories:
            display_text = f"{category['title']} (ID: {category['id']})"
            self.db_category_combo.addItem(display_text, category['id'])
        
        db_category_layout.addWidget(self.db_category_combo)
        
        # Advertencia si no hay categorías BD
        if not self.db_categories:
            warning_label = QLabel("⚠️ No hay categorías de WordPress cargadas.\nAsegúrate de cargar las categorías desde la base de datos.")
            warning_label.setStyleSheet("color: #FF9800; font-size: 12px; padding: 5px;")
            warning_label.setWordWrap(True)
            db_category_layout.addWidget(warning_label)
        
        content_layout.addWidget(db_category_group)
        
        # Configuración de programación
        schedule_group = QGroupBox("⏰ Programación")
        schedule_layout = QVBoxLayout(schedule_group)
        
        # Frecuencia
        schedule_layout.addWidget(QLabel("Frecuencia:"))
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItem("Una sola vez", TaskFrequency.ONCE.value)
        self.frequency_combo.addItem("Cada hora", TaskFrequency.HOURLY.value)
        self.frequency_combo.addItem("Diario", TaskFrequency.DAILY.value)
        self.frequency_combo.addItem("Semanal", TaskFrequency.WEEKLY.value)
        self.frequency_combo.addItem("Mensual", TaskFrequency.MONTHLY.value)
        self.frequency_combo.addItem("Personalizado", TaskFrequency.CUSTOM.value)
        schedule_layout.addWidget(self.frequency_combo)
        
        # Primera ejecución
        schedule_layout.addWidget(QLabel("Primera ejecución:"))
        self.datetime_input = QDateTimeEdit()
        self.datetime_input.setDateTime(QDateTime.currentDateTime().addSecs(3600))  # 1 hora desde ahora
        self.datetime_input.setCalendarPopup(True)
        schedule_layout.addWidget(self.datetime_input)
        
        # Intervalo personalizado (solo para frecuencia personalizada)
        self.custom_interval_label = QLabel("Intervalo personalizado (horas):")
        self.custom_interval_input = QSpinBox()
        self.custom_interval_input.setRange(1, 8760)  # 1 hora a 1 año
        self.custom_interval_input.setValue(24)
        
        schedule_layout.addWidget(self.custom_interval_label)
        schedule_layout.addWidget(self.custom_interval_input)
        
        # Mostrar/ocultar intervalo personalizado
        self.frequency_combo.currentTextChanged.connect(self._toggle_custom_interval)
        self._toggle_custom_interval()
        
        content_layout.addWidget(schedule_group)
        
        # Configuración de procesamiento
        processing_group = QGroupBox("⚙️ Configuración de Procesamiento")
        processing_layout = QVBoxLayout(processing_group)
        
        # Máximo de videos
        processing_layout.addWidget(QLabel("Máximo de videos por ejecución:"))
        self.max_videos_input = QSpinBox()
        self.max_videos_input.setRange(1, 500)
        self.max_videos_input.setValue(50)
        processing_layout.addWidget(self.max_videos_input)
        
        # Auto publicar
        self.auto_publish_checkbox = QCheckBox("📤 Publicar automáticamente en WordPress")
        self.auto_publish_checkbox.setChecked(True)
        processing_layout.addWidget(self.auto_publish_checkbox)
        
        content_layout.addWidget(processing_group)
        
        # Configuración avanzada
        advanced_group = QGroupBox("🔧 Configuración Avanzada")
        advanced_layout = QVBoxLayout(advanced_group)
        
        # Delay entre videos
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay entre videos (segundos):"))
        self.delay_min_input = QSpinBox()
        self.delay_min_input.setRange(0, 60)
        self.delay_min_input.setValue(1)
        delay_layout.addWidget(self.delay_min_input)
        delay_layout.addWidget(QLabel("a"))
        self.delay_max_input = QSpinBox()
        self.delay_max_input.setRange(0, 60)
        self.delay_max_input.setValue(3)
        delay_layout.addWidget(self.delay_max_input)
        advanced_layout.addLayout(delay_layout)
        
        # Saltar existentes
        self.skip_existing_checkbox = QCheckBox("⏭️ Saltar videos ya existentes")
        self.skip_existing_checkbox.setChecked(True)
        advanced_layout.addWidget(self.skip_existing_checkbox)
        
        content_layout.addWidget(advanced_group)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Botones
        button_layout = QHBoxLayout()
        
        # Botón de prueba
        self.test_button = QPushButton("🧪 Probar Categoría")
        self.test_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.test_button.clicked.connect(self._test_category)
        button_layout.addWidget(self.test_button)
        
        button_layout.addStretch()
        
        # Botones principales
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setText("✅ Crear Tarea")
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setText("❌ Cancelar")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        
        button_layout.addWidget(button_box)
        layout.addLayout(button_layout)
    
    def _toggle_custom_interval(self):
        """Muestra/oculta el campo de intervalo personalizado"""
        is_custom = self.frequency_combo.currentData() == TaskFrequency.CUSTOM.value
        self.custom_interval_label.setVisible(is_custom)
        self.custom_interval_input.setVisible(is_custom)
    
    def _test_category(self):
        """Prueba la categoría web seleccionada"""
        web_category_url = self._get_web_category_url()
        if not web_category_url:
            QMessageBox.warning(self, "Error", "Selecciona una categoría web o ingresa una URL")
            return
        
        try:
            self.test_button.setEnabled(False)
            self.test_button.setText("🔄 Probando...")
            
            # Mostrar información de la categoría
            category_name = self._get_web_category_name()
            QMessageBox.information(
                self, 
                "Prueba de Categoría Web",
                f"✅ Categoría web seleccionada:\n\n"
                f"📂 Nombre: {category_name}\n"
                f"🌐 URL: {web_category_url}\n\n"
                f"La categoría será probada cuando se ejecute la tarea."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error probando categoría:\n{str(e)}")
        finally:
            self.test_button.setEnabled(True)
            self.test_button.setText("🧪 Probar Categoría")
    
    def _get_web_category_url(self):
        """Obtiene la URL de la categoría web seleccionada o ingresada"""
        # Priorizar URL manual
        manual_url = self.url_input.text().strip()
        if manual_url:
            return manual_url
        
        # Usar categoría del combo
        return self.web_category_combo.currentData()
    
    def _get_web_category_name(self):
        """Obtiene el nombre de la categoría web"""
        if self.url_input.text().strip():
            return "Categoría manual"
        
        if self.web_category_combo.currentIndex() > 0:
            return self.web_category_combo.currentText().split(" (")[0]
        
        return "Sin nombre"
    
    def _get_db_category_id(self):
        """Obtiene el ID de la categoría de base de datos"""
        return self.db_category_combo.currentData()
    
    def get_task_data(self):
        """Obtiene los datos de la tarea desde el formulario"""
        web_category_url = self._get_web_category_url()
        if not web_category_url:
            QMessageBox.warning(self, "Error", "Debes seleccionar una categoría web para scrapear")
            return None
        
        db_category_id = self._get_db_category_id()
        if self.auto_publish_checkbox.isChecked() and not db_category_id:
            reply = QMessageBox.question(
                self,
                "Categoría WordPress",
                "No has seleccionado una categoría de WordPress.\n\n"
                "¿Quieres continuar sin auto-publicar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return None
        
        # Obtener nombre de categoría web
        web_category_name = self._get_web_category_name()
        
        # Crear configuración de la tarea
        config = {
            'max_videos_per_run': self.max_videos_input.value(),
            'delay_between_videos': (self.delay_min_input.value(), self.delay_max_input.value()),
            'auto_publish': self.auto_publish_checkbox.isChecked(),
            'skip_existing': self.skip_existing_checkbox.isChecked(),
            'max_retries': 3,
            'db_category_id': db_category_id  # ID de categoría WordPress donde publicar
        }
        
        # Añadir intervalo personalizado si aplica
        if self.frequency_combo.currentData() == TaskFrequency.CUSTOM.value:
            config['interval_hours'] = self.custom_interval_input.value()
        
        return {
            'id': str(uuid.uuid4()),
            'name': self.name_input.text().strip() or f"Tarea {web_category_name}",
            'description': self.description_input.toPlainText().strip(),
            'category_url': web_category_url,  # URL de categoría WEB a scrapear
            'category_name': web_category_name,  # Nombre de categoría WEB
            'next_run': self.datetime_input.dateTime().toPython(),
            'frequency': TaskFrequency(self.frequency_combo.currentData()),
            'status': TaskStatus.PENDING,
            'created_at': datetime.now(),
            'max_videos': self.max_videos_input.value(),
            'auto_publish': self.auto_publish_checkbox.isChecked(),
            'config': config
        }

class SchedulerWidget(QWidget):
    """Widget principal para gestionar tareas programadas"""
    
    def __init__(self):
        super().__init__()
        self.scheduler = None
        self.auto_scraper = None
        self.web_categories = []      # Categorías WEB extraídas (Anal, Checas, etc.)
        self.db_categories = []       # Categorías BD para publicar
        
        if SCHEDULER_AVAILABLE:
            self.scheduler = TaskScheduler()
            self.auto_scraper = AutoScraper()
            
            # Registrar callback para ejecutar tareas
            self.scheduler.register_callback('scrape_category', self._execute_scraping_task)
        
        self.setup_ui()
        self.setup_timer()
        
        if self.scheduler:
            self.load_tasks()
            self.scheduler.start_scheduler()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Título
        title = QLabel("📅 Tareas Programadas")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e0e0e0; margin-bottom: 15px;")
        layout.addWidget(title)
        
        if not SCHEDULER_AVAILABLE:
            error_label = QLabel("❌ Módulo de scheduler no disponible")
            error_label.setStyleSheet("color: #f44336; font-size: 14px; padding: 20px;")
            error_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(error_label)
            return
        
        # Barra de herramientas
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 10)
        
        # Botón nueva tarea
        self.new_task_btn = QPushButton("➕ Nueva Tarea")
        self.new_task_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.new_task_btn.clicked.connect(self.create_new_task)
        toolbar_layout.addWidget(self.new_task_btn)
        
        # Botón refrescar
        self.refresh_btn = QPushButton("🔄 Refrescar")
        self.refresh_btn.clicked.connect(self.load_tasks)
        toolbar_layout.addWidget(self.refresh_btn)
        
        # Estado del scheduler
        self.scheduler_status = QLabel("🔄 Scheduler: Iniciando...")
        self.scheduler_status.setStyleSheet("color: #888; font-size: 12px;")
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.scheduler_status)
        
        layout.addWidget(toolbar)
        
        # Splitter principal
        splitter = QSplitter(Qt.Horizontal)
        
        # Panel izquierdo - Lista de tareas
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        # Tabla de tareas
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(6)
        self.tasks_table.setHorizontalHeaderLabels([
            "Nombre", "Estado", "Categoría Web", "Próxima Ejecución", "Frecuencia", "Acciones"
        ])
        
        # Configurar tabla
        header = self.tasks_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.tasks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tasks_table.setAlternatingRowColors(True)
        self.tasks_table.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                gridline-color: #3a3a3a;
                color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3a3a;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
            }
            QHeaderView::section {
                background-color: #404040;
                color: #e0e0e0;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        left_layout.addWidget(self.tasks_table)
        
        # Panel derecho - Detalles y estadísticas
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        # Estadísticas
        stats_group = QGroupBox("📊 Estado de Tareas")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_labels = {}
        stats_items = [
            ('total', '📋 Total de tareas'),
            ('pending', '⏳ Pendientes'),
            ('running', '🔄 Ejecutándose'),
            ('completed', '✅ Completadas'),
            ('failed', '❌ Fallidas'),
            ('paused', '⏸️ Pausadas')
        ]
        
        for key, label in stats_items:
            stats_label = QLabel(f"{label}: 0")
            stats_label.setStyleSheet("padding: 4px; color: #e0e0e0;")
            self.stats_labels[key] = stats_label
            stats_layout.addWidget(stats_label)
        
        right_layout.addWidget(stats_group)
        
        # Información de categorías
        categories_group = QGroupBox("📂 Categorías Disponibles")
        categories_layout = QVBoxLayout(categories_group)
        
        self.web_categories_label = QLabel("🌐 Categorías Web: 0")
        self.web_categories_label.setStyleSheet("padding: 4px; color: #e0e0e0;")
        categories_layout.addWidget(self.web_categories_label)
        
        self.db_categories_label = QLabel("📄 Categorías WordPress: 0")
        self.db_categories_label.setStyleSheet("padding: 4px; color: #e0e0e0;")
        categories_layout.addWidget(self.db_categories_label)
        
        right_layout.addWidget(categories_group)
        
        # Log de actividad reciente
        log_group = QGroupBox("📝 Actividad Reciente")
        log_layout = QVBoxLayout(log_group)
        
        self.activity_log = QTextEdit()
        self.activity_log.setMaximumHeight(200)
        self.activity_log.setReadOnly(True)
        self.activity_log.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        log_layout.addWidget(self.activity_log)
        
        right_layout.addWidget(log_group)
        right_layout.addStretch()
        
        # Configurar splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 300])
        
        layout.addWidget(splitter)
    
    def setup_timer(self):
        """Configura timer para actualizar la UI"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(5000)  # Actualizar cada 5 segundos
    
    def set_web_categories(self, categories):
        """Establece las categorías WEB extraídas (Anal, Checas, etc.)"""
        self.web_categories = categories
        self.web_categories_label.setText(f"🌐 Categorías Web: {len(categories)}")
        logger.info(f"🌐 {len(categories)} categorías web cargadas para scheduler")
        self.log_activity(f"🌐 {len(categories)} categorías web disponibles para programación")
    
    def set_db_categories(self, categories):
        """Establece las categorías de BD para publicar"""
        self.db_categories = categories
        self.db_categories_label.setText(f"📄 Categorías WordPress: {len(categories)}")
        logger.info(f"📄 {len(categories)} categorías BD cargadas para scheduler")
        self.log_activity(f"📄 {len(categories)} categorías WordPress disponibles")
    
    def create_new_task(self):
        """Abre diálogo para crear nueva tarea"""
        if not self.web_categories:
            QMessageBox.warning(
                self,
                "Categorías Web Requeridas",
                "❌ No hay categorías web disponibles.\n\n"
                "Primero ve a 'Explorar Categorías' y deja que se carguen las categorías web."
            )
            return
        
        dialog = TaskCreationDialog(self.web_categories, self.db_categories, self)
        
        if dialog.exec_() == QDialog.Accepted:
            task_data = dialog.get_task_data()
            if task_data:
                # Crear tarea
                task = ScheduledTask(**task_data)
                
                if self.scheduler.add_task(task):
                    QMessageBox.information(
                        self,
                        "Tarea Creada",
                        f"✅ Tarea '{task.name}' creada exitosamente\n\n"
                        f"📂 Categoría web: {task.category_name}\n"
                        f"🕐 Próxima ejecución: {task.next_run.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🎯 Máx. videos: {task.max_videos}"
                    )
                    self.load_tasks()
                    self.log_activity(f"✅ Tarea creada: {task.name} → {task.category_name}")
                else:
                    QMessageBox.critical(self, "Error", "❌ Error creando la tarea")
    
    def load_tasks(self):
        """Carga las tareas en la tabla"""
        if not self.scheduler:
            return
        
        tasks = self.scheduler.get_all_tasks()
        
        self.tasks_table.setRowCount(len(tasks))
        
        for row, task in enumerate(tasks):
            # Nombre
            name_item = QTableWidgetItem(task.name)
            name_item.setData(Qt.UserRole, task.id)
            self.tasks_table.setItem(row, 0, name_item)
            
            # Estado
            status_item = QTableWidgetItem(self._get_status_display(task.status))
            status_item.setForeground(self._get_status_color(task.status))
            self.tasks_table.setItem(row, 1, status_item)
            
            # Categoría Web
            self.tasks_table.setItem(row, 2, QTableWidgetItem(task.category_name))
            
            # Próxima ejecución
            next_run = task.next_run.strftime('%Y-%m-%d %H:%M') if task.next_run else "N/A"
            self.tasks_table.setItem(row, 3, QTableWidgetItem(next_run))
            
            # Frecuencia
            self.tasks_table.setItem(row, 4, QTableWidgetItem(task.frequency.value.title()))
            
            # Botones de acción
            actions_widget = self._create_action_buttons(task)
            self.tasks_table.setCellWidget(row, 5, actions_widget)
        
        self.update_statistics()
    
    def _get_status_display(self, status):
        """Obtiene texto de visualización para el estado"""
        status_map = {
            TaskStatus.PENDING: "⏳ Pendiente",
            TaskStatus.RUNNING: "🔄 Ejecutándose",
            TaskStatus.COMPLETED: "✅ Completada",
            TaskStatus.FAILED: "❌ Falló",
            TaskStatus.CANCELLED: "🚫 Cancelada",
            TaskStatus.PAUSED: "⏸️ Pausada"
        }
        return status_map.get(status, str(status))
    
    def _get_status_color(self, status):
        """Obtiene color para el estado"""
        from PyQt5.QtGui import QColor
        
        color_map = {
            TaskStatus.PENDING: QColor("#FF9800"),
            TaskStatus.RUNNING: QColor("#2196F3"),
            TaskStatus.COMPLETED: QColor("#4CAF50"),
            TaskStatus.FAILED: QColor("#f44336"),
            TaskStatus.CANCELLED: QColor("#666666"),
            TaskStatus.PAUSED: QColor("#9E9E9E")
        }
        return color_map.get(status, QColor("#e0e0e0"))
    
    def _create_action_buttons(self, task):
        """Crea botones de acción para una tarea"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Botón pausar/reanudar
        if task.status == TaskStatus.PENDING:
            pause_btn = QPushButton("⏸️")
            pause_btn.setToolTip("Pausar tarea")
            pause_btn.clicked.connect(lambda: self._pause_task(task.id))
        elif task.status == TaskStatus.PAUSED:
            pause_btn = QPushButton("▶️")
            pause_btn.setToolTip("Reanudar tarea")
            pause_btn.clicked.connect(lambda: self._resume_task(task.id))
        else:
            pause_btn = QPushButton("⏸️")
            pause_btn.setEnabled(False)
        
        pause_btn.setFixedSize(30, 25)
        layout.addWidget(pause_btn)
        
        # Botón eliminar
        delete_btn = QPushButton("🗑️")
        delete_btn.setToolTip("Eliminar tarea")
        delete_btn.setFixedSize(30, 25)
        delete_btn.clicked.connect(lambda: self._delete_task(task.id))
        layout.addWidget(delete_btn)
        
        return widget
    
    def _pause_task(self, task_id):
        """Pausa una tarea"""
        if self.scheduler.pause_task(task_id):
            self.load_tasks()
            self.log_activity(f"⏸️ Tarea pausada: {task_id}")
    
    def _resume_task(self, task_id):
        """Reanuda una tarea"""
        if self.scheduler.resume_task(task_id):
            self.load_tasks()
            self.log_activity(f"▶️ Tarea reanudada: {task_id}")
    
    def _delete_task(self, task_id):
        """Elimina una tarea"""
        reply = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            "¿Estás seguro de que quieres eliminar esta tarea?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.scheduler.remove_task(task_id):
                self.load_tasks()
                self.log_activity(f"🗑️ Tarea eliminada: {task_id}")
    
    def update_statistics(self):
        """Actualiza las estadísticas"""
        if not self.scheduler:
            return
        
        stats = self.scheduler.get_scheduler_status()
        
        self.stats_labels['total'].setText(f"📋 Total de tareas: {stats['total_tasks']}")
        self.stats_labels['pending'].setText(f"⏳ Pendientes: {stats['pending_tasks']}")
        self.stats_labels['running'].setText(f"🔄 Ejecutándose: {stats['running_tasks']}")
        self.stats_labels['completed'].setText(f"✅ Completadas: {stats['completed_tasks']}")
        self.stats_labels['failed'].setText(f"❌ Fallidas: {stats['failed_tasks']}")
        self.stats_labels['paused'].setText(f"⏸️ Pausadas: {stats['paused_tasks']}")
    
    def update_ui(self):
        """Actualiza la interfaz periódicamente"""
        if not self.scheduler:
            return
        
        # Actualizar estado del scheduler
        if self.scheduler.running:
            self.scheduler_status.setText("✅ Scheduler: Activo")
            self.scheduler_status.setStyleSheet("color: #4CAF50; font-size: 12px;")
        else:
            self.scheduler_status.setText("❌ Scheduler: Inactivo")
            self.scheduler_status.setStyleSheet("color: #f44336; font-size: 12px;")
        
        # Recargar tareas para mostrar cambios de estado
        self.load_tasks()
    
    def log_activity(self, message):
        """Añade mensaje al log de actividad"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.activity_log.append(formatted_message)
        
        # Mantener solo las últimas 50 líneas
        text = self.activity_log.toPlainText()
        lines = text.split('\n')
        if len(lines) > 50:
            self.activity_log.setPlainText('\n'.join(lines[-50:]))
    
    def _execute_scraping_task(self, category_url, category_name, max_videos, auto_publish, task_config):
        """Ejecuta una tarea de scraping (callback para el scheduler)"""
        try:
            self.log_activity(f"🚀 Iniciando scraping: {category_name}")
            
            if not self.auto_scraper:
                return {'success': False, 'message': 'AutoScraper no disponible'}
            
            # Ejecutar scraping
            result = self.auto_scraper.execute_scheduled_scraping(
                category_url=category_url,
                category_name=category_name,
                max_videos=max_videos,
                auto_publish=auto_publish,
                task_config=task_config
            )
            
            # Log del resultado
            if result['success']:
                self.log_activity(f"✅ Scraping completado: {result['message']}")
            else:
                self.log_activity(f"❌ Scraping falló: {result['message']}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error en scraping automático: {str(e)}"
            self.log_activity(f"❌ {error_msg}")
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}
    
    def closeEvent(self, event):
        """Maneja el cierre del widget"""
        if self.scheduler:
            self.scheduler.stop_scheduler()
        event.accept()