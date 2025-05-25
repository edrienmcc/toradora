# proyecto/ui/main_window.py - CÓDIGO COMPLETO FINAL
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QLineEdit, QComboBox, 
                            QScrollArea, QFrame, QStackedWidget, QProgressBar,
                            QSplitter, QMessageBox)
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont

from opciones.opcion1.ui import Opcion1Widget
from ui.styles import dark_style_sheet

# Importar manejo de base de datos
try:
    from database.category_manager import CategoryManager
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    print("⚠️ Módulo de base de datos no disponible")

# Importar scheduler UI
try:
    from ui.scheduler_ui import SchedulerWidget
    SCHEDULER_UI_AVAILABLE = True
except ImportError:
    SCHEDULER_UI_AVAILABLE = False
    print("⚠️ Interfaz de scheduler no disponible")

class DatabaseCategoryLoader(QThread):
    """Hilo para cargar categorías de la base de datos"""
    categories_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.category_manager = None
        if DATABASE_AVAILABLE:
            self.category_manager = CategoryManager()
    
    def run(self):
        if not self.category_manager:
            self.error_occurred.emit("Módulo de base de datos no disponible")
            return
        
        try:
            categories = self.category_manager.get_categories_from_database()
            self.categories_loaded.emit(categories)
        except Exception as e:
            self.error_occurred.emit(f"Error cargando categorías: {str(e)}")

class WebCategoryLoader(QThread):
    """Hilo para cargar categorías web de pornhub"""
    web_categories_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        try:
            from opciones.opcion1.scraper import Opcion1Scraper
            scraper = Opcion1Scraper()
            web_categories = scraper.get_categories()
            self.web_categories_loaded.emit(web_categories)
        except Exception as e:
            self.error_occurred.emit(f"Error cargando categorías web: {str(e)}")

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Explorador de Contenido")
        self.setMinimumSize(1400, 700)
        self.setStyleSheet(dark_style_sheet)
        
        # Inicializar variables de instancia
        self.loaded_categories = []  # Categorías BD
        self.web_categories = []     # Categorías WEB
        self.db_category_loader = None
        self.web_category_loader = None
        self.expand_timer = None
        self.collapse_timer = None
        self.expand_height = 0
        self.collapse_height = 100
        
        # NUEVA VARIABLE PARA SCHEDULER
        self.scheduler_widget = None
        
        # Crear widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Contenido principal (horizontal con splitter)
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Panel izquierdo (barra lateral) - MODIFICADO PARA INCLUIR SCHEDULER
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(250)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        
        # Botones de opciones - AÑADIR BOTÓN DE SCHEDULER
        self.opcion1_btn = QPushButton("📁 Explorar Categorías")
        self.opcion1_btn.setObjectName("sidebar-button")
        self.opcion1_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        sidebar_layout.addWidget(self.opcion1_btn)
        
        # NUEVO BOTÓN PARA SCHEDULER
        if SCHEDULER_UI_AVAILABLE:
            self.scheduler_btn = QPushButton("📅 Tareas Programadas")
            self.scheduler_btn.setObjectName("sidebar-button")
            self.scheduler_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
            sidebar_layout.addWidget(self.scheduler_btn)
        
        # Espacio para categorías web
        self.categorias_label = QLabel("Categorías Web")
        self.categorias_label.setObjectName("sidebar-header")
        sidebar_layout.addWidget(self.categorias_label)
        
        # Scroll área para categorías web
        self.cat_scroll = QScrollArea()
        self.cat_scroll.setWidgetResizable(True)
        self.cat_scroll.setFrameShape(QFrame.NoFrame)
        
        self.cat_container = QWidget()
        self.cat_layout = QVBoxLayout(self.cat_container)
        self.cat_layout.setAlignment(Qt.AlignTop)
        self.cat_layout.setContentsMargins(0, 0, 0, 0)
        self.cat_layout.setSpacing(5)
        
        self.cat_scroll.setWidget(self.cat_container)
        sidebar_layout.addWidget(self.cat_scroll)
        
        sidebar_layout.addStretch()
        content_splitter.addWidget(self.sidebar)
    
        self.content_panel = QWidget()
        content_panel_layout = QVBoxLayout(self.content_panel)
        content_panel_layout.setContentsMargins(0, 0, 0, 0)
        content_panel_layout.setSpacing(0)
        
        # Barra de búsqueda - MODIFICADA PARA INCLUIR BOTÓN DE SCHEDULER
        search_bar = QWidget()
        search_bar.setObjectName("search-bar")
        search_bar.setFixedHeight(70)
        search_layout = QHBoxLayout(search_bar)
        
        self.search_button = QPushButton("🔍 Automatización")
        self.search_button.setObjectName("search-button")
        
        # Añadir botón de StreamWish en la barra de búsqueda
        try:
            from opciones.opcion1.config_streamwish import StreamWishConfig
            STREAMWISH_AVAILABLE = True
            self.streamwish_btn = QPushButton("☁️ StreamWish")
            self.streamwish_btn.setObjectName("advanced-button")
            # Conectar el botón al método configure_streamwish del widget de opción 1
            self.streamwish_btn.clicked.connect(lambda: self.opcion1_widget.configure_streamwish())
        except ImportError:
            STREAMWISH_AVAILABLE = False
        
        # NUEVO BOTÓN PARA SCHEDULER EN LA BARRA
        if SCHEDULER_UI_AVAILABLE:
            self.scheduler_quick_btn = QPushButton("📅 Programar")
            self.scheduler_quick_btn.setObjectName("advanced-button")
            self.scheduler_quick_btn.setToolTip("Ir a tareas programadas")
            self.scheduler_quick_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        search_layout.addWidget(self.search_button)
        if STREAMWISH_AVAILABLE:
            search_layout.addWidget(self.streamwish_btn)
        if SCHEDULER_UI_AVAILABLE:
            search_layout.addWidget(self.scheduler_quick_btn)
        
        search_layout.addStretch()
        content_panel_layout.addWidget(search_bar)
        
        # Contenido principal (stack de widgets) - AÑADIR SCHEDULER WIDGET
        self.stack = QStackedWidget()
        
        # Añadir widgets de opciones al stack
        self.opcion1_widget = Opcion1Widget()
        self.stack.addWidget(self.opcion1_widget)
        
        # AÑADIR SCHEDULER WIDGET
        if SCHEDULER_UI_AVAILABLE:
            self.scheduler_widget = SchedulerWidget()
            self.stack.addWidget(self.scheduler_widget)
        
        content_panel_layout.addWidget(self.stack)
        content_splitter.addWidget(self.content_panel)
        
        # Panel derecho - Categorías de base de datos
        self.db_categories_panel = QWidget()
        self.db_categories_panel.setObjectName("db-categories-panel")
        self.db_categories_panel.setMinimumWidth(250)
        self.db_categories_panel.setMaximumWidth(300)
        
        db_categories_layout = QVBoxLayout(self.db_categories_panel)
        db_categories_layout.setContentsMargins(15, 15, 15, 15)
        db_categories_layout.setSpacing(10)
        
        # Título del panel de categorías de BD
        db_title = QLabel("📂 Categorías WordPress")
        db_title.setObjectName("db-panel-title")
        db_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #e0e0e0;
            padding: 10px 0;
            border-bottom: 2px solid #3a3a3a;
        """)
        db_categories_layout.addWidget(db_title)
        
        # Estado de conexión
        self.db_status_label = QLabel("🔌 Conectando...")
        self.db_status_label.setStyleSheet("color: #888; font-size: 12px; padding: 5px;")
        db_categories_layout.addWidget(self.db_status_label)
        
        # Botón para recargar categorías
        self.reload_db_btn = QPushButton("🔄 Recargar")
        self.reload_db_btn.setObjectName("reload-button")
        self.reload_db_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #cccccc;
            }
        """)
        self.reload_db_btn.clicked.connect(self.load_database_categories)
        db_categories_layout.addWidget(self.reload_db_btn)
        
        # Campo de búsqueda de categorías
        self.category_search = QLineEdit()
        self.category_search.setPlaceholderText("🔍 Buscar categorías...")
        self.category_search.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 6px 8px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        self.category_search.textChanged.connect(self.filter_database_categories)
        db_categories_layout.addWidget(self.category_search)
        
        # Scroll área para categorías de BD
        self.db_cat_scroll = QScrollArea()
        self.db_cat_scroll.setWidgetResizable(True)
        self.db_cat_scroll.setFrameShape(QFrame.NoFrame)
        self.db_cat_scroll.setStyleSheet("background-color: transparent;")
        
        self.db_cat_container = QWidget()
        self.db_cat_layout = QVBoxLayout(self.db_cat_container)
        self.db_cat_layout.setAlignment(Qt.AlignTop)
        self.db_cat_layout.setContentsMargins(0, 0, 0, 0)
        self.db_cat_layout.setSpacing(8)
        
        self.db_cat_scroll.setWidget(self.db_cat_container)
        db_categories_layout.addWidget(self.db_cat_scroll)
        
        # Estadísticas de categorías
        self.category_stats = QLabel("")
        self.category_stats.setStyleSheet("color: #888; font-size: 11px; padding: 5px; text-align: center;")
        self.category_stats.setAlignment(Qt.AlignCenter)
        db_categories_layout.addWidget(self.category_stats)
        
        content_splitter.addWidget(self.db_categories_panel)
        
        # Configurar el splitter
        content_splitter.setSizes([200, 800, 250])
        main_layout.addWidget(content_splitter)

        # BARRA DE PROGRESO GLOBAL
        self.progress_container = QWidget()
        self.progress_container.setObjectName("progress-container")
        self.progress_container.setFixedHeight(100)
        self.progress_container.hide()
        self.progress_container.setStyleSheet("""
            #progress-container {
                background-color: #2a2a2a;
                border-top: 1px solid #3a3a3a;
            }
        """)
        
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(20, 10, 20, 10)
        progress_layout.setSpacing(8)
        
        # Etiqueta de estado
        self.progress_status = QLabel("")
        self.progress_status.setObjectName("progress-status")
        self.progress_status.setAlignment(Qt.AlignCenter)
        self.progress_status.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #e0e0e0;
            padding: 5px;
            background-color: transparent;
        """)
        progress_layout.addWidget(self.progress_status)
        
        # Barra de progreso de descarga
        self.download_progress = QProgressBar()
        self.download_progress.setObjectName("download-progress")
        self.download_progress.setVisible(False)
        self.download_progress.setMinimum(0)
        self.download_progress.setMaximum(100)
        self.download_progress.setFormat("Descargando... %p%")
        self.download_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                background-color: #1a1a1a;
                color: white;
                height: 30px;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #66BB6A);
                border-radius: 6px;
                margin: 1px;
            }
        """)
        progress_layout.addWidget(self.download_progress)
        
        # Barra de progreso de conversión (FFmpeg)
        self.conversion_progress = QProgressBar()
        self.conversion_progress.setObjectName("conversion-progress")
        self.conversion_progress.setVisible(False)
        self.conversion_progress.setMinimum(0)
        self.conversion_progress.setMaximum(100)
        self.conversion_progress.setFormat("Convirtiendo video... %p%")
        self.conversion_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                background-color: #1a1a1a;
                color: white;
                height: 30px;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF9800, stop:1 #FFB74D);
                border-radius: 6px;
                margin: 1px;
            }
        """)
        progress_layout.addWidget(self.conversion_progress)
        
        # Barra de progreso de upload
        self.upload_progress = QProgressBar()
        self.upload_progress.setObjectName("upload-progress")
        self.upload_progress.setVisible(False)
        self.upload_progress.setMinimum(0)
        self.upload_progress.setMaximum(100)
        self.upload_progress.setFormat("Subiendo a StreamWish... %p%")
        self.upload_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                background-color: #1a1a1a;
                color: white;
                height: 30px;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2196F3, stop:1 #42A5F5);
                border-radius: 6px;
                margin: 1px;
            }
        """)
        progress_layout.addWidget(self.upload_progress)
        
        # Agregar contenedor de progreso al layout principal
        main_layout.addWidget(self.progress_container)
        
        # Conectar señales del widget de opción 1 al progreso global
        self._connect_progress_signals()
        
        # Inicializar
        self.opcion1_widget.initialize()
        self.load_database_categories()
        
        # CARGAR CATEGORÍAS WEB PARA EL SCHEDULER CON DELAY
        QTimer.singleShot(3000, self.load_web_categories_for_scheduler)  # 3 segundos de delay
    
    def load_web_categories_for_scheduler(self):
        """Carga las categorías web para el scheduler"""
        if not SCHEDULER_UI_AVAILABLE or not self.scheduler_widget:
            return
        
        print("🌐 Cargando categorías web para scheduler...")
        
        self.web_category_loader = WebCategoryLoader()
        self.web_category_loader.web_categories_loaded.connect(self._on_web_categories_loaded)
        self.web_category_loader.error_occurred.connect(self._on_web_categories_error)
        self.web_category_loader.start()
    
    def _on_web_categories_loaded(self, web_categories):
        """Callback cuando se cargan las categorías WEB"""
        self.web_categories = web_categories
        
        # Actualizar barra lateral con categorías web
        self._update_web_categories_sidebar(web_categories)
        
        # Pasar al scheduler
        if SCHEDULER_UI_AVAILABLE and self.scheduler_widget:
            self.scheduler_widget.set_web_categories(web_categories)
            self.scheduler_widget.log_activity(f"🌐 {len(web_categories)} categorías web cargadas")
        
        print(f"✅ {len(web_categories)} categorías web cargadas para scheduler")
    
    def _on_web_categories_error(self, error_message):
        """Callback cuando hay error cargando categorías web"""
        print(f"❌ Error cargando categorías web: {error_message}")
        if SCHEDULER_UI_AVAILABLE and self.scheduler_widget:
            self.scheduler_widget.log_activity(f"❌ Error cargando categorías web: {error_message}")
    
    def _update_web_categories_sidebar(self, web_categories):
        """Actualiza la barra lateral con las categorías web"""
        # Limpiar categorías existentes
        while self.cat_layout.count():
            child = self.cat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Añadir nuevas categorías
        for category in web_categories[:112]:  # Limitar a 20 para no saturar
            category_btn = QPushButton(f"{category['title']} ({category['count']})")
            category_btn.setObjectName("category-button")
            category_btn.clicked.connect(lambda checked, url=category['url']: self.opcion1_widget.load_category(url))
            self.cat_layout.addWidget(category_btn)
    
    def load_database_categories(self):
        """Carga las categorías desde la base de datos"""
        if not DATABASE_AVAILABLE:
            self.db_status_label.setText("❌ BD no disponible")
            self.db_status_label.setStyleSheet("color: #f44336; font-size: 12px;")
            self.category_stats.setText("Instala mysql-connector-python")
            return
        
        self.db_status_label.setText("🔄 Cargando categorías...")
        self.db_status_label.setStyleSheet("color: #FF9800; font-size: 12px;")
        self.reload_db_btn.setEnabled(False)
        self.reload_db_btn.setText("🔄 Cargando...")
        
        # Limpiar categorías existentes
        self._clear_database_categories()
        
        # Cargar categorías en hilo separado
        self.db_category_loader = DatabaseCategoryLoader()
        self.db_category_loader.categories_loaded.connect(self.on_database_categories_loaded)
        self.db_category_loader.error_occurred.connect(self.on_database_error)
        self.db_category_loader.start()
    
    def on_database_categories_loaded(self, categories):
        """Callback cuando se cargan las categorías de la base de datos"""
        self.reload_db_btn.setEnabled(True)
        self.reload_db_btn.setText("🔄 Recargar")
        
        # Almacenar categorías para filtrado
        self.loaded_categories = categories
        
        # PASAR CATEGORÍAS BD AL SCHEDULER WIDGET (para publicar)
        if SCHEDULER_UI_AVAILABLE and self.scheduler_widget:
            self.scheduler_widget.set_db_categories(categories)
            self.scheduler_widget.log_activity(f"📂 {len(categories)} categorías WordPress cargadas")
        
        if not categories:
            self.db_status_label.setText("⚠️ Sin categorías")
            self.db_status_label.setStyleSheet("color: #FF9800; font-size: 12px;")
            self.category_stats.setText("No hay categorías disponibles")
            return
        
        # Mostrar todas las categorías inicialmente
        self._display_categories(categories)
        
        # Actualizar estado y estadísticas
        total_count = sum(cat.get('count', 0) for cat in categories)
        self.db_status_label.setText(f"✅ {len(categories)} categorías")
        self.db_status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.category_stats.setText(f"Total: {len(categories)} | Contenido: {total_count:,}")
        
        print(f"✅ Se cargaron {len(categories)} categorías BD desde la base de datos")
    
    def _display_categories(self, categories):
        """Muestra las categorías en el panel"""
        # Limpiar categorías existentes
        self._clear_database_categories()
        
        # Mostrar categorías
        for category in categories:
            cat_button = QPushButton(f"📁 {category['title']}")
            cat_button.setObjectName("db-category-button")
            
            # Tooltip con información detallada
            tooltip_text = (
                f"ID: {category['id']}\n"
                f"Slug: {category['slug']}\n"
                f"Contenido: {category['count']:,} elementos\n"
                f"URL: {category['url']}"
            )
            if category['description']:
                tooltip_text += f"\n\nDescripción:\n{category['description'][:100]}..."
            
            cat_button.setToolTip(tooltip_text)
            
            # Estilo del botón con indicador de cantidad
            count_color = "#4CAF50" if category['count'] > 100 else "#FF9800" if category['count'] > 10 else "#666"
            cat_button.setStyleSheet(f"""
                QPushButton#db-category-button {{
                    background-color: transparent;
                    border: 1px solid #404040;
                    border-radius: 4px;
                    text-align: left;
                    padding: 8px 12px;
                    font-size: 13px;
                    color: #e0e0e0;
                    margin: 2px 0;
                }}
                QPushButton#db-category-button:hover {{
                    background-color: #404040;
                    border-color: #606060;
                    color: white;
                }}
                QPushButton#db-category-button:pressed {{
                    background-color: #505050;
                }}
            """)
            
            # Agregar indicador de cantidad si hay contenido
            if category['count'] > 0:
                count_indicator = QLabel(f"{category['count']:,}")
                count_indicator.setStyleSheet(f"""
                    background-color: {count_color};
                    color: white;
                    border-radius: 10px;
                    padding: 2px 6px;
                    font-size: 10px;
                    font-weight: bold;
                """)
                count_indicator.setFixedHeight(20)
                count_indicator.setAlignment(Qt.AlignCenter)
                
                # Layout horizontal para botón + indicador
                cat_widget = QWidget()
                cat_layout = QHBoxLayout(cat_widget)
                cat_layout.setContentsMargins(0, 0, 0, 0)
                cat_layout.setSpacing(5)
                
                cat_layout.addWidget(cat_button, 1)
                cat_layout.addWidget(count_indicator)
                
                self.db_cat_layout.addWidget(cat_widget)
            else:
                self.db_cat_layout.addWidget(cat_button)
            
            # Conectar clic para mostrar información
            cat_button.clicked.connect(
                lambda checked, cat=category: self.on_database_category_clicked(cat)
            )
    
    def filter_database_categories(self, search_text):
        """Filtra las categorías según el texto de búsqueda"""
        if not hasattr(self, 'loaded_categories') or not self.loaded_categories:
            return
        
        search_text = search_text.lower().strip()
        
        if not search_text:
            # Mostrar todas las categorías si no hay texto de búsqueda
            filtered_categories = self.loaded_categories
        else:
            # Filtrar categorías que coincidan con el texto
            filtered_categories = [
                cat for cat in self.loaded_categories
                if (search_text in cat['title'].lower() or 
                    search_text in cat['slug'].lower() or
                    search_text in str(cat['id']) or
                    (cat['description'] and search_text in cat['description'].lower()))
            ]
        
        # Mostrar categorías filtradas
        self._display_categories(filtered_categories)
        
        # Actualizar estadísticas
        if search_text:
            total_count = sum(cat.get('count', 0) for cat in filtered_categories)
            self.category_stats.setText(f"Filtrado: {len(filtered_categories)} de {len(self.loaded_categories)} | Contenido: {total_count:,}")
        else:
            total_count = sum(cat.get('count', 0) for cat in self.loaded_categories)
            self.category_stats.setText(f"Total: {len(self.loaded_categories)} | Contenido: {total_count:,}")
    
    def on_database_error(self, error_message):
        """Callback cuando hay error cargando categorías de BD"""
        self.reload_db_btn.setEnabled(True)
        self.reload_db_btn.setText("🔄 Recargar")
        self.db_status_label.setText("❌ Error de BD")
        self.db_status_label.setStyleSheet("color: #f44336; font-size: 12px;")
        self.category_stats.setText("Error de conexión")
        
        # Mostrar error detallado en consola
        print(f"❌ Error cargando categorías de BD: {error_message}")
        
        # Log para scheduler
        if SCHEDULER_UI_AVAILABLE and self.scheduler_widget:
            self.scheduler_widget.log_activity(f"❌ Error BD: {error_message}")
        
        # Mostrar diálogo de error solo si es un error crítico
        if "no disponible" not in error_message.lower():
            QMessageBox.critical(
                self, 
                "Error de Base de Datos",
                f"No se pudieron cargar las categorías:\n\n{error_message}\n\n"
                f"Verifica:\n"
                f"• Configuración en database/config.py\n"
                f"• Que MySQL esté ejecutándose\n"
                f"• Que las credenciales sean correctas\n"
                f"• Que las tablas existan"
            )
    
    def on_database_category_clicked(self, category):
        """Maneja el clic en una categoría de la base de datos"""
        print(f"🔍 Categoría seleccionada: {category['title']} (ID: {category['id']})")
        
        # Crear mensaje detallado
        message = (
            f"<b>Categoría:</b> {category['title']}<br><br>"
            f"<b>ID:</b> {category['id']}<br>"
            f"<b>Slug:</b> {category['slug']}<br>"
            f"<b>Contenido:</b> {category['count']:,} elementos<br>"
            f"<b>URL:</b> {category['url']}<br>"
        )
        
        if category['description']:
            description = category['description']
            if len(description) > 200:
                description = description[:197] + "..."
            message += f"<br><b>Descripción:</b><br>{description}"
        
        # Mostrar información de la categoría
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"📂 {category['title']}")
        msg_box.setText(message)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setIcon(QMessageBox.Information)
        
        # Botones personalizados
        msg_box.addButton("🔍 Ver Contenido", QMessageBox.AcceptRole)
        msg_box.addButton("✖️ Cerrar", QMessageBox.RejectRole)
        
        result = msg_box.exec_()
        
        if result == 0:  # Botón "Ver Contenido"
            print(f"🚀 Mostrando contenido de categoría: {category['title']}")
            # Aquí puedes agregar lógica para mostrar el contenido de la categoría
    
    def _clear_database_categories(self):
        """Limpia todas las categorías de la base de datos del panel"""
        while self.db_cat_layout.count():
            child = self.db_cat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def _connect_progress_signals(self):
        """Conecta las señales de progreso del widget de opción 1"""
        # Las conexiones se harán desde el VideoCard cuando inicie una descarga
        pass
        
    def show_download_progress(self, status_text="⬇️ Descargando video..."):
        """Muestra la barra de progreso de descarga"""
        self.progress_status.setText(status_text)
        self.progress_container.show()
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)
        self.upload_progress.setVisible(False)
        self.conversion_progress.setVisible(False)
        
        # Animar la aparición del contenedor
        self.progress_container.setFixedHeight(0)
        self.progress_container.show()
        
        # Expandir gradualmente
        self.expand_timer = QTimer()
        self.expand_height = 0
        self.expand_timer.timeout.connect(self._expand_progress_container)
        self.expand_timer.start(10)
    
    def _expand_progress_container(self):
        """Anima la expansión del contenedor de progreso"""
        self.expand_height += 5
        if self.expand_height >= 100:
            self.expand_height = 100
            self.expand_timer.stop()
        self.progress_container.setFixedHeight(self.expand_height)
    
    def update_download_progress(self, value):
        """Actualiza el progreso de descarga"""
        self.download_progress.setValue(value)
        if value < 100:
            self.progress_status.setText(f"⬇️ Descargando video... {value}%")
        else:
            self.progress_status.setText("✅ Descarga completada!")
            
        # Actualizar formato de la barra
        if value == 100:
            self.download_progress.setFormat("✅ Descarga completada!")
    
    def show_conversion_progress(self, status_text="🔄 Convirtiendo video..."):
        """Muestra la barra de progreso de conversión"""
        self.progress_status.setText(status_text)
        self.download_progress.setVisible(False)
        self.conversion_progress.setVisible(True)
        self.conversion_progress.setValue(0)
        self.upload_progress.setVisible(False)
    
    def update_conversion_progress(self, value):
        """Actualiza el progreso de conversión"""
        self.conversion_progress.setValue(value)
        if value < 100:
            self.progress_status.setText(f"🔄 Convirtiendo video... {value}%")
        else:
            self.progress_status.setText("✅ Conversión completada!")
            
        # Actualizar formato de la barra
        if value == 100:
            self.conversion_progress.setFormat("✅ Conversión completada!")

    def show_upload_progress(self, status_text="📤 Subiendo a StreamWish..."):
        """Muestra la barra de progreso de upload"""
        self.progress_status.setText(status_text)
        self.download_progress.setVisible(False)
        self.conversion_progress.setVisible(False)
        self.upload_progress.setVisible(True)
        self.upload_progress.setValue(0)
    
    def update_upload_progress(self, value):
        """Actualiza el progreso de upload"""
        self.upload_progress.setValue(value)
        if value < 100:
            self.progress_status.setText(f"📤 Subiendo a StreamWish... {value}%")
        else:
            self.progress_status.setText("☁️ Upload completado!")
            
        # Actualizar formato de la barra
        if value == 100:
            self.upload_progress.setFormat("☁️ Upload completado!")
    
    def update_progress_status(self, status_text):
        """Actualiza solo el texto de estado"""
        self.progress_status.setText(status_text)
    
    def hide_progress(self):
        """Oculta todas las barras de progreso con animación"""
        # Esperar un poco antes de ocultar para que el usuario vea el resultado
        QTimer.singleShot(3000, self._start_hide_animation)
    
    def _start_hide_animation(self):
        """Inicia la animación de ocultado"""
        self.collapse_timer = QTimer()
        self.collapse_height = 100
        self.collapse_timer.timeout.connect(self._collapse_progress_container)
        self.collapse_timer.start(10)
    
    def _collapse_progress_container(self):
        """Anima el colapso del contenedor de progreso"""
        self.collapse_height -= 5
        if self.collapse_height <= 0:
            self.collapse_height = 0
            self.collapse_timer.stop()
            self._hide_progress_delayed()
        self.progress_container.setFixedHeight(self.collapse_height)
    
    def _hide_progress_delayed(self):
        """Oculta el progreso completamente"""
        self.progress_container.hide()
        self.download_progress.setVisible(False)
        self.conversion_progress.setVisible(False)
        self.upload_progress.setVisible(False)
        self.download_progress.setValue(0)
        self.conversion_progress.setValue(0)
        self.upload_progress.setValue(0)
        self.download_progress.setFormat("Descargando... %p%")
        self.conversion_progress.setFormat("Convirtiendo video... %p%")
        self.upload_progress.setFormat("Subiendo a StreamWish... %p%")
        self.progress_container.setFixedHeight(100)  # Resetear altura
    
    def keyPressEvent(self, event):
        """Maneja eventos de teclado"""
        # F5 para refrescar
        if event.key() == Qt.Key_F5:
            self.refresh_all_data()
        
        # Cmd+R para recargar categorías de BD (Mac)
        elif event.key() == Qt.Key_R and event.modifiers() == Qt.ControlModifier:
            self.load_database_categories()
        
        # Cmd+D para mostrar estado de conexión de BD (Mac)
        elif event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            self.show_database_connection_status()
        
        # Cmd+F para enfocar búsqueda de categorías (Mac)
        elif event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
            self.category_search.setFocus()
            self.category_search.selectAll()
        
        # Cmd+T para ir a tareas programadas (Mac)
        elif event.key() == Qt.Key_T and event.modifiers() == Qt.ControlModifier:
            if SCHEDULER_UI_AVAILABLE:
                self.stack.setCurrentIndex(1)
        
        # Cmd+1 para ir a explorar categorías (Mac)
        elif event.key() == Qt.Key_1 and event.modifiers() == Qt.ControlModifier:
            self.stack.setCurrentIndex(0)
        
        # Escape para limpiar búsqueda de categorías
        elif event.key() == Qt.Key_Escape:
            if self.category_search.hasFocus():
                self.category_search.clear()
        
        else:
            super().keyPressEvent(event)
    
    def contextMenuEvent(self, event):
        """Menú contextual"""
        from PyQt5.QtWidgets import QMenu, QAction
        
        menu = QMenu(self)
        
        # Acciones del menú
        refresh_action = QAction("🔄 Refrescar Todo (F5)", self)
        refresh_action.triggered.connect(self.refresh_all_data)
        menu.addAction(refresh_action)
        
        reload_db_action = QAction("🔄 Recargar BD (Cmd+R)", self)
        reload_db_action.triggered.connect(self.load_database_categories)
        menu.addAction(reload_db_action)
        
        reload_web_action = QAction("🌐 Recargar Categorías Web", self)
        reload_web_action.triggered.connect(self.load_web_categories_for_scheduler)
        menu.addAction(reload_web_action)
        
        menu.addSeparator()
        
        # Navegación
        explore_action = QAction("📁 Explorar Categorías (Cmd+1)", self)
        explore_action.triggered.connect(lambda: self.stack.setCurrentIndex(0))
        menu.addAction(explore_action)
        
        if SCHEDULER_UI_AVAILABLE:
            scheduler_action = QAction("📅 Tareas Programadas (Cmd+T)", self)
            scheduler_action.triggered.connect(lambda: self.stack.setCurrentIndex(1))
            menu.addAction(scheduler_action)
        
        menu.addSeparator()
        
        db_status_action = QAction("📊 Estado de BD (Cmd+D)", self)
        db_status_action.triggered.connect(self.show_database_connection_status)
        menu.addAction(db_status_action)
        
        menu.addSeparator()
        
        about_action = QAction("ℹ️ Acerca de", self)
        about_action.triggered.connect(self.show_about)
        menu.addAction(about_action)
        
        menu.exec_(event.globalPos())
    
    def show_about(self):
        """Muestra información sobre la aplicación"""
        scheduler_status = "✅ Disponible" if SCHEDULER_UI_AVAILABLE else "❌ No disponible"
        db_status = "✅ Disponible" if DATABASE_AVAILABLE else "❌ No disponible"
        
        web_categories_count = len(self.web_categories) if hasattr(self, 'web_categories') else 0
        db_categories_count = len(self.loaded_categories) if hasattr(self, 'loaded_categories') else 0
        
        about_text = f"""
        <h3>🎬 Explorador de Contenido</h3>
        <p><b>Versión:</b> 1.2.0</p>
        <p><b>Descripción:</b> Aplicación para explorar y descargar contenido multimedia con tareas programadas</p>
        
        <h4>📋 Características:</h4>
        <ul>
        <li>🔍 Exploración de categorías web</li>
        <li>📂 Integración con base de datos MySQL: {db_status}</li>
        <li>⬇️ Descarga de videos en múltiples formatos</li>
        <li>☁️ Upload automático a StreamWish</li>
        <li>📅 Tareas programadas automáticas: {scheduler_status}</li>
        <li>🎨 Interfaz moderna con tema oscuro</li>
        </ul>
        
        <h4>📊 Estado Actual:</h4>
        <ul>
        <li><b>Categorías Web:</b> {web_categories_count} cargadas</li>
        <li><b>Categorías WordPress:</b> {db_categories_count} cargadas</li>
        <li><b>Base de Datos:</b> {db_status}</li>
        <li><b>Scheduler:</b> {scheduler_status}</li>
        </ul>
        
        <h4>⌨️ Atajos de teclado:</h4>
        <ul>
        <li><b>F5:</b> Refrescar todo</li>
        <li><b>Cmd+R:</b> Recargar categorías BD</li>
        <li><b>Cmd+D:</b> Estado de conexión BD</li>
        <li><b>Cmd+F:</b> Buscar categorías</li>
        <li><b>Cmd+1:</b> Explorar categorías</li>
        <li><b>Cmd+T:</b> Tareas programadas</li>
        <li><b>Escape:</b> Limpiar búsqueda</li>
        </ul>
        
        <h4>🛠️ Tecnologías:</h4>
        <p>PyQt5, MySQL, FFmpeg, BeautifulSoup, Requests, Threading</p>
        
        <p><small>💡 Haz clic derecho para más opciones</small></p>
        """
        
        QMessageBox.about(self, "Acerca de Explorador de Contenido", about_text)
    
    def closeEvent(self, event):
        """Maneja el cierre de la aplicación"""
        print("👋 Cerrando aplicación...")
        
        # Detener hilos activos si existen
        if hasattr(self, 'db_category_loader') and self.db_category_loader and self.db_category_loader.isRunning():
            self.db_category_loader.terminate()
            self.db_category_loader.wait(1000)
        
        if hasattr(self, 'web_category_loader') and self.web_category_loader and self.web_category_loader.isRunning():
            self.web_category_loader.terminate()
            self.web_category_loader.wait(1000)
        
        # Detener cualquier descarga activa
        if hasattr(self.opcion1_widget, 'loader') and self.opcion1_widget.loader:
            if self.opcion1_widget.loader.isRunning():
                self.opcion1_widget.loader.stop()
                self.opcion1_widget.loader.wait(1000)
        
        # Detener scheduler si está disponible
        if SCHEDULER_UI_AVAILABLE and self.scheduler_widget:
            print("⏹️ Deteniendo scheduler...")
            self.scheduler_widget.closeEvent(event)
        
        event.accept()
    
    def resizeEvent(self, event):
        """Maneja el redimensionamiento de la ventana"""
        super().resizeEvent(event)
        
        # Ajustar tamaños del splitter al redimensionar
        if hasattr(self, 'content_splitter'):
            window_width = self.width()
            if window_width < 1200:
                # Ventana pequeña: ocultar panel de categorías de BD
                self.db_categories_panel.hide()
            else:
                # Ventana normal: mostrar panel de categorías de BD
                self.db_categories_panel.show()
    
    def get_database_categories_count(self):
        """Obtiene el número de categorías cargadas"""
        return len(self.loaded_categories) if hasattr(self, 'loaded_categories') else 0
    
    def get_web_categories_count(self):
        """Obtiene el número de categorías web cargadas"""
        return len(self.web_categories) if hasattr(self, 'web_categories') else 0
    
    def search_database_categories(self, search_term):
        """Busca categorías por término de búsqueda"""
        if not DATABASE_AVAILABLE:
            return []
        
        try:
            category_manager = CategoryManager()
            return category_manager.search_categories(search_term)
        except Exception as e:
            print(f"❌ Error buscando categorías: {str(e)}")
            return []
    
    def refresh_all_data(self):
        """Recarga todos los datos (categorías de BD y categorías web)"""
        print("🔄 Refrescando todos los datos...")
        
        # Recargar categorías de base de datos
        self.load_database_categories()
        
        # Recargar categorías web (Opción 1)
        if hasattr(self.opcion1_widget, 'initialize'):
            self.opcion1_widget.initialize()
        
        # Recargar categorías web para scheduler
        self.load_web_categories_for_scheduler()
        
        self.progress_status.setText("🔄 Refrescando datos...")
        
        # Log para scheduler si está disponible
        if SCHEDULER_UI_AVAILABLE and self.scheduler_widget:
            self.scheduler_widget.log_activity("🔄 Datos refrescados desde menú principal")
    
    def show_database_connection_status(self):
        """Muestra el estado de la conexión a la base de datos"""
        if not DATABASE_AVAILABLE:
            QMessageBox.warning(
                self,
                "Base de Datos",
                "❌ Módulo de base de datos no disponible\n\n"
                "Para habilitar la conexión a MySQL:\n"
                "1. Instala: pip3 install mysql-connector-python\n"
                "2. Configura database/config.py\n"
                "3. Reinicia la aplicación"
            )
            return
        
        try:
            from database.config import DatabaseConfig
            config = DatabaseConfig()
            
            if config.test_connection():
                categories_count = self.get_database_categories_count()
                web_categories_count = self.get_web_categories_count()
                scheduler_status = "Activo" if (SCHEDULER_UI_AVAILABLE and self.scheduler_widget and 
                                              hasattr(self.scheduler_widget, 'scheduler') and 
                                              self.scheduler_widget.scheduler.running) else "Inactivo"
                
                QMessageBox.information(
                    self,
                    "Estado del Sistema",
                    f"✅ Conexión a BD exitosa\n\n"
                    f"🗄️ <b>Base de Datos:</b>\n"
                    f"Host: {config.config['host']}\n"
                    f"BD: {config.config['database']}\n"
                    f"Usuario: {config.config['user']}\n"
                    f"Puerto: {config.config['port']}\n\n"
                    f"📊 <b>Estadísticas:</b>\n"
                    f"Categorías WordPress: {categories_count}\n"
                    f"Categorías Web: {web_categories_count}\n"
                    f"Scheduler: {scheduler_status}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Error de Conexión",
                    f"❌ No se pudo conectar a la base de datos\n\n"
                    f"Host: {config.config['host']}\n"
                    f"Base de datos: {config.config['database']}\n"
                    f"Usuario: {config.config['user']}\n"
                    f"Puerto: {config.config['port']}\n\n"
                    f"Verifica la configuración en database/config.py"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"❌ Error verificando conexión:\n\n{str(e)}"
            )
    
    def get_application_stats(self):
        """Obtiene estadísticas completas de la aplicación"""
        scheduler_stats = {}
        if SCHEDULER_UI_AVAILABLE and self.scheduler_widget and hasattr(self.scheduler_widget, 'scheduler'):
            scheduler_stats = self.scheduler_widget.scheduler.get_scheduler_status()
        
        stats = {
            'database_available': DATABASE_AVAILABLE,
            'scheduler_available': SCHEDULER_UI_AVAILABLE,
            'db_categories_loaded': self.get_database_categories_count(),
            'web_categories_loaded': self.get_web_categories_count(),
            'window_size': f"{self.width()}x{self.height()}",
            'current_tab': 'Explorar Categorías' if self.stack.currentIndex() == 0 else 'Tareas Programadas' if self.stack.currentIndex() == 1 else 'Desconocido',
            'scheduler_stats': scheduler_stats
        }
        return stats