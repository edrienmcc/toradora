from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QScrollArea, QFrame, QGridLayout, QMessageBox,
                            QDialog, QLineEdit, QCheckBox, QDialogButtonBox, QTextEdit,
                            QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QPixmap, QImage

import requests
from io import BytesIO
import time
import random
import threading
import os
import logging

# Configurar logger si no existe
logger = logging.getLogger(__name__)

from opciones.opcion1.scraper import Opcion1Scraper
from utils.common import normalize_image_url

# Importar downloader de manera segura
try:
    from opciones.opcion1.downloader import VideoDownloader
    DOWNLOADER_AVAILABLE = True
except ImportError:
    DOWNLOADER_AVAILABLE = False
    print("⚠️ Downloader no disponible. Instala las dependencias necesarias.")

# Importar StreamWish de manera segura
try:
    from opciones.opcion1.config_streamwish import StreamWishConfig
    STREAMWISH_AVAILABLE = True
except ImportError:
    STREAMWISH_AVAILABLE = False

# Importar publisher de WordPress
try:
    from database.wordpress_publisher import WordPressPublisher
    WORDPRESS_PUBLISHER_AVAILABLE = True
except ImportError:
    WORDPRESS_PUBLISHER_AVAILABLE = False
    print("⚠️ WordPress Publisher no disponible")

class StreamWishConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar StreamWish")
        self.setFixedSize(500, 400)
        self.setup_ui()
        self.load_current_config()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("⚙️ Configuración de StreamWish")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Descripción
        desc = QLabel("StreamWish permite subir automáticamente los videos descargados a la nube.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 15px;")
        layout.addWidget(desc)
        
        # API Key
        api_layout = QVBoxLayout()
        api_label = QLabel("🔑 API Key:")
        api_label.setStyleSheet("font-weight: bold;")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Ingresa tu API key de StreamWish")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_key_input)
        layout.addLayout(api_layout)
        
        # Auto upload
        self.auto_upload_checkbox = QCheckBox("📤 Subir automáticamente después de descargar")
        self.auto_upload_checkbox.setChecked(True)
        layout.addWidget(self.auto_upload_checkbox)
        
        # Settings adicionales
        settings_label = QLabel("⚙️ Configuraciones adicionales:")
        settings_label.setStyleSheet("font-weight: bold; margin-top: 15px;")
        layout.addWidget(settings_label)
        
        # Público/Privado
        self.public_checkbox = QCheckBox("🌐 Videos públicos (recomendado)")
        self.public_checkbox.setChecked(True)
        layout.addWidget(self.public_checkbox)
        
        # Contenido adulto
        self.adult_checkbox = QCheckBox("🔞 Marcar como contenido adulto")
        self.adult_checkbox.setChecked(True)
        layout.addWidget(self.adult_checkbox)
        
        # Tags
        tags_layout = QVBoxLayout()
        tags_label = QLabel("🏷️ Tags (separados por comas):")
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("pornhub, hd, video")
        self.tags_input.setText("pornhub, hd, video")
        
        tags_layout.addWidget(tags_label)
        tags_layout.addWidget(self.tags_input)
        layout.addLayout(tags_layout)
        
        # Eliminar después de subir
        self.delete_after_checkbox = QCheckBox("🗑️ Eliminar archivo local después de subir")
        self.delete_after_checkbox.setStyleSheet("color: #d32f2f;")
        layout.addWidget(self.delete_after_checkbox)
        
        # Botones
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_current_config(self):
        """Carga la configuración actual"""
        if not STREAMWISH_AVAILABLE:
            return
        
        try:
            config = StreamWishConfig()
            
            # API Key
            api_key = config.get_api_key()
            if api_key:
                self.api_key_input.setText(api_key)
            
            # Auto upload
            self.auto_upload_checkbox.setChecked(config.is_auto_upload_enabled())
            
            # Settings de upload
            settings = config.get_upload_settings()
            self.public_checkbox.setChecked(settings.get('file_public', 1) == 1)
            self.adult_checkbox.setChecked(settings.get('file_adult', 1) == 1)
            self.tags_input.setText(settings.get('tags', 'pornhub, hd, video'))
            self.delete_after_checkbox.setChecked(config.config.get('delete_after_upload', False))
            
        except Exception as e:
            print(f"Error cargando configuración: {str(e)}")
    
    def get_config(self):
        """Obtiene la configuración del diálogo"""
        return {
            'api_key': self.api_key_input.text().strip(),
            'auto_upload': self.auto_upload_checkbox.isChecked(),
            'upload_settings': {
                'file_public': 1 if self.public_checkbox.isChecked() else 0,
                'file_adult': 1 if self.adult_checkbox.isChecked() else 0,
                'tags': self.tags_input.text().strip()
            },
            'delete_after_upload': self.delete_after_checkbox.isChecked()
        }

class CategorySelectionDialog(QDialog):
    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📂 Seleccionar Categoría para Publicar")
        self.setFixedSize(500, 600)
        self.categories = categories
        self.selected_category = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("📂 Selecciona una categoría para publicar el video")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 15px; color: #e0e0e0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Descripción
        desc = QLabel("Es obligatorio seleccionar una categoría de tu web para publicar el video.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888; margin-bottom: 20px; text-align: center;")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        # Búsqueda
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Buscar:")
        search_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar categorías...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        self.search_input.textChanged.connect(self.filter_categories)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Lista de categorías
        self.category_list = QListWidget()
        self.category_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 5px;
                color: white;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #404040;
                border-radius: 3px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #404040;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
        """)
        
        # Poblar lista con categorías
        self.populate_categories()
        
        layout.addWidget(self.category_list)
        
        # Información de categoría seleccionada
        self.category_info = QLabel("")
        self.category_info.setStyleSheet("color: #888; font-size: 12px; padding: 10px; background-color: #1a1a1a; border-radius: 4px;")
        self.category_info.setWordWrap(True)
        layout.addWidget(self.category_info)
        
        # Conectar selección
        self.category_list.itemSelectionChanged.connect(self.on_category_selected)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("❌ Cancelar")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        self.publish_button = QPushButton("📤 Publicar Video")
        self.publish_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #cccccc;
            }
        """)
        self.publish_button.setEnabled(False)
        self.publish_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.publish_button)
        
        layout.addLayout(button_layout)
    
    def populate_categories(self):
        """Poblar la lista con categorías"""
        self.category_list.clear()
        
        for category in self.categories:
            item = QListWidgetItem()
            
            # Texto del item
            category_text = f"📁 {category['title']}"
            if category.get('count', 0) > 0:
                category_text += f" ({category['count']:,} posts)"
            
            item.setText(category_text)
            item.setData(Qt.UserRole, category)  # Guardar datos de categoría
            
            # Tooltip con información
            tooltip = f"ID: {category['id']}\nSlug: {category['slug']}\nPosts: {category.get('count', 0):,}"
            if category.get('description'):
                tooltip += f"\nDescripción: {category['description'][:100]}..."
            item.setToolTip(tooltip)
            
            self.category_list.addItem(item)
    
    def filter_categories(self, search_text):
        """Filtrar categorías según búsqueda"""
        search_text = search_text.lower()
        
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            category = item.data(Qt.UserRole)
            
            # Buscar en título, slug y descripción
            visible = (
                search_text in category['title'].lower() or
                search_text in category.get('slug', '').lower() or
                search_text in category.get('description', '').lower()
            )
            
            item.setHidden(not visible)
    
    def on_category_selected(self):
        """Manejar selección de categoría"""
        current_item = self.category_list.currentItem()
        
        if current_item:
            self.selected_category = current_item.data(Qt.UserRole)
            self.publish_button.setEnabled(True)
            
            # Mostrar información de la categoría
            category = self.selected_category
            info_text = (
                f"📂 <b>{category['title']}</b><br>"
                f"🆔 ID: {category['id']}<br>"
                f"📝 Slug: {category['slug']}<br>"
                f"📊 Posts actuales: {category.get('count', 0):,}<br>"
            )
            
            if category.get('description'):
                description = category['description']
                if len(description) > 100:
                    description = description[:97] + "..."
                info_text += f"📄 Descripción: {description}"
            
            self.category_info.setText(info_text)
        else:
            self.selected_category = None
            self.publish_button.setEnabled(False)
            self.category_info.setText("")
    
    def get_selected_category(self):
        """Obtener categoría seleccionada"""
        return self.selected_category

class VideoLoader(QThread):
    video_loaded = pyqtSignal(dict)
    finished_loading = pyqtSignal()
    
    def __init__(self, scraper, category_url):
        super().__init__()
        self.scraper = scraper
        self.category_url = category_url
        self.is_running = True
        
    def run(self):
        for video in self.scraper.get_videos(self.category_url):
            if not self.is_running:
                break
            if video:
                self.video_loaded.emit(video)
        self.finished_loading.emit()
    
    def stop(self):
        self.is_running = False

class CategoryLoader(QThread):
    category_loaded = pyqtSignal(list)
    
    def __init__(self, scraper):
        super().__init__()
        self.scraper = scraper
        
    def run(self):
        categories = self.scraper.get_categories()
        self.category_loaded.emit(categories)

class DownloadWorker(QThread):
    """Worker thread para descargar videos sin bloquear la UI"""
    finished = pyqtSignal(bool)
    
    def __init__(self, video_url, video_data, downloader):
        super().__init__()
        self.video_url = video_url
        self.video_data = video_data
        self.downloader = downloader
    
    def run(self):
        try:
            success = self.downloader.download_video(self.video_url, self.video_data)
            self.finished.emit(success)
        except Exception as e:
            print(f"❌ Error en worker de descarga: {str(e)}")
            self.finished.emit(False)

class VideoCard(QWidget):
    def __init__(self, video_data):
        super().__init__()
        self.video_data = video_data
        self.is_downloading = False
        self.download_worker = None
        self.selected_category_for_publish = None
        self.already_published = False  # ✅ NUEVO: Flag para evitar doble publicación
        self.setup_ui()
        
    def setup_ui(self):
        self.setObjectName("video-card")
        self.setFixedSize(200, 320)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        
        # Contenedor de la miniatura
        thumbnail_container = QWidget()
        thumbnail_container.setObjectName("thumbnail-container")
        thumbnail_container.setFixedSize(184, 130)
        
        # Layout para la miniatura y duración
        thumb_layout = QVBoxLayout(thumbnail_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        
        # Miniatura (imagen)
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(184, 130)
        self.thumbnail_label.setScaledContents(True)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        
        # Crear pixmap por defecto
        default_pixmap = QPixmap(184, 130)
        default_pixmap.fill(Qt.darkGray)
        self.thumbnail_label.setPixmap(default_pixmap)
        
        # Duración overlay
        if self.video_data.get('duration'):
            duration_label = QLabel(self.video_data['duration'])
            duration_label.setObjectName("duration-overlay")
            duration_label.setAlignment(Qt.AlignCenter)
            duration_label.setFixedSize(50, 20)
            duration_label.setStyleSheet("""
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            """)
            
            # Posicionar la duración en la esquina inferior derecha
            duration_label.move(130, 105)
            duration_label.setParent(self.thumbnail_label)
        
        # Cargar imagen si existe
        if self.video_data.get('thumbnail'):
            # Normalizar URL de imagen
            thumbnail_url = normalize_image_url(self.video_data['thumbnail'], 'https://es.pornhub.com')
            if thumbnail_url:
                threading.Thread(target=self.load_image, args=(thumbnail_url,), daemon=True).start()
        
        layout.addWidget(thumbnail_container)
        
        # Etiqueta del título
        title_text = self.video_data.get('title', 'Sin título')
        # Truncar título si es muy largo
        if len(title_text) > 60:
            title_text = title_text[:57] + "..."
            
        title_label = QLabel(title_text)
        title_label.setObjectName("video-title")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title_label.setFixedHeight(40)
        title_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        layout.addWidget(title_label)
        
        # Información adicional
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Uploader
        if self.video_data.get('uploader'):
            uploader_label = QLabel(self.video_data['uploader'])
            uploader_label.setStyleSheet("color: #888; font-size: 11px;")
            uploader_label.setAlignment(Qt.AlignLeft)
            info_layout.addWidget(uploader_label)
        
        # Vistas y rating en la misma línea
        if self.video_data.get('views') or self.video_data.get('rating'):
            stats_layout = QHBoxLayout()
            
            if self.video_data.get('views'):
                views_label = QLabel(f"{self.video_data['views']} vistas")
                views_label.setStyleSheet("color: #999; font-size: 10px;")
                stats_layout.addWidget(views_label)
            
            if self.video_data.get('rating'):
                rating_label = QLabel(f"👍 {self.video_data['rating']}")
                rating_label.setStyleSheet("color: #999; font-size: 10px;")
                stats_layout.addWidget(rating_label)
            
            stats_layout.addStretch()
            info_layout.addLayout(stats_layout)
        
        layout.addLayout(info_layout)
        
        # Botón Importar
        self.import_button = QPushButton("Importar")
        self.import_button.setStyleSheet("""
            QPushButton {
                background-color: #FF6B35;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #E55A2B;
            }
            QPushButton:pressed {
                background-color: #CC4E26;
            }
            QPushButton:disabled {
                background-color: #888888;
                color: #CCCCCC;
            }
        """)
        self.import_button.clicked.connect(self.import_video)
        
        layout.addWidget(self.import_button)
        layout.addStretch()
        
    def import_video(self):
        """Importa/descarga el video y lo publica en WordPress"""
        if not DOWNLOADER_AVAILABLE:
            QMessageBox.warning(self, "Error", "El módulo de descarga no está disponible.\nInstala las dependencias necesarias.")
            return
            
        if not self.video_data.get('url'):
            QMessageBox.warning(self, "Error", "No hay URL de video para importar")
            return
        
        if self.is_downloading:
            return
        
        # ✅ VERIFICAR SI YA SE PUBLICÓ
        if self.already_published:
            QMessageBox.information(
                self, 
                "Ya Publicado", 
                "🎉 Este video ya fue publicado exitosamente.\n\nSi necesitas publicarlo nuevamente, recarga la página."
            )
            return
        
        # PASO 1: Obtener categorías de la base de datos
        main_window = self.window()
        
        if not hasattr(main_window, 'loaded_categories') or not main_window.loaded_categories:
            QMessageBox.warning(
                self, 
                "Categorías Requeridas", 
                "❌ No hay categorías cargadas.\n\n"
                "Es necesario tener categorías de la web para publicar videos.\n"
                "Haz clic en 'Recargar' en el panel de categorías de la derecha."
            )
            return
        
        # PASO 2: Mostrar diálogo de selección de categoría
        category_dialog = CategorySelectionDialog(main_window.loaded_categories, self)
        
        if category_dialog.exec_() != QDialog.Accepted:
            print("❌ Publicación cancelada - No se seleccionó categoría")
            return
        
        selected_category = category_dialog.get_selected_category()
        if not selected_category:
            QMessageBox.warning(self, "Error", "No se seleccionó ninguna categoría")
            return
        
        print(f"✅ Categoría seleccionada: {selected_category['title']} (ID: {selected_category['id']})")
        
        # PASO 3: Iniciar descarga
        self.selected_category_for_publish = selected_category
        
        print(f"🚀 Iniciando importación de: {self.video_data['title']}")
        
        # Cambiar el estado del botón
        self.is_downloading = True
        self.import_button.setText("Descargando...")
        self.import_button.setEnabled(False)
        
        # Mostrar barra de progreso de descarga
        main_window.show_download_progress(f"⬇️ Descargando: {self.video_data['title'][:30]}...")
        
        # Crear downloader
        self.downloader = VideoDownloader()
        
        # Conectar señales de progreso
        self.downloader.progress_reporter.download_progress.connect(main_window.update_download_progress)
        self.downloader.progress_reporter.upload_progress.connect(main_window.update_upload_progress)
        self.downloader.progress_reporter.status_changed.connect(self._handle_status_change)
        self.downloader.progress_reporter.finished.connect(self._handle_download_finished)
        
        # Crear y ejecutar worker thread
        self.download_worker = DownloadWorker(self.video_data['url'], self.video_data, self.downloader)
        self.download_worker.finished.connect(self._handle_worker_finished)
        self.download_worker.start()
    
    def _handle_status_change(self, status_text):
        """Maneja cambios de estado"""
        main_window = self.window()
        main_window.update_progress_status(status_text)
        
        # Si el estado indica que se está subiendo, cambiar a barra de upload
        if "📤" in status_text and "StreamWish" in status_text:
            main_window.show_upload_progress(status_text)
    
    def _handle_download_finished(self, success):
        """Maneja finalización de descarga/upload"""
        main_window = self.window()
        
        if success:
            print(f"✅ Descarga/Upload completado exitosamente: {self.video_data['title']}")
            
            # PASO 4: Publicar en WordPress después de descarga exitosa
            # ✅ SOLO PUBLICAR SI NO SE HA PUBLICADO ANTES
            if not self.already_published:
                self._publish_to_wordpress()
            
        else:
            print(f"❌ Error en descarga/upload: {self.video_data['title']}")
            main_window.update_progress_status("❌ Error en descarga/upload")
            main_window.hide_progress()
    
    def _publish_to_wordpress(self):
        """Publica el video en WordPress - VERSIÓN ÚNICA"""
        try:
            if not WORDPRESS_PUBLISHER_AVAILABLE:
                QMessageBox.warning(self, "Error", "WordPress Publisher no está disponible")
                return
            
            # ✅ MARCAR COMO EN PROCESO DE PUBLICACIÓN
            if self.already_published:
                print("⚠️ Ya se está publicando o ya se publicó este video")
                return
                
            self.already_published = True  # ✅ Marcar INMEDIATAMENTE para evitar duplicados
            
            main_window = self.window()
            main_window.update_progress_status("📝 Publicando en WordPress...")
            
            # Obtener código de StreamWish si existe
            streamwish_code = None
            if hasattr(self.downloader, 'streamwish_uploader') and self.downloader.streamwish_uploader:
                streamwish_code = self._extract_streamwish_code()
            
            # NUEVO: Obtener y subir imagen por FTP
            ftp_image_url = None
            if hasattr(self.downloader, 'downloaded_image_path') and self.downloader.downloaded_image_path:
                main_window.update_progress_status("📤 Subiendo imagen por FTP...")
                
                # Generar un post_id temporal para el nombre del archivo
                import time
                temp_post_id = int(time.time())
                
                ftp_image_url = self.downloader.get_image_ftp_url(
                    self.video_data.get('title', 'video'), 
                    temp_post_id
                )
                
                if ftp_image_url:
                    # Actualizar video_data con la URL del FTP
                    self.video_data['ftp_image_url'] = ftp_image_url
                    logger.info(f"✅ Imagen FTP URL: {ftp_image_url}")
                    print(f"🌐 Imagen FTP: {ftp_image_url}")
                else:
                    logger.warning("⚠️ No se pudo subir imagen por FTP")
                    print("⚠️ Error subiendo imagen por FTP")
            
            if not streamwish_code:
                # Si no hay código de StreamWish, preguntar al usuario
                reply = QMessageBox.question(
                    self,
                    "StreamWish",
                    "⚠️ No se detectó código de StreamWish.\n\n"
                    "¿Deseas continuar publicando sin reproductor de StreamWish?\n"
                    "(Solo se publicará título e imagen)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    main_window.update_progress_status("❌ Publicación cancelada")
                    main_window.hide_progress()
                    self.already_published = False  # ✅ Resetear flag si se cancela
                    return
            
            # Crear publisher
            publisher = WordPressPublisher()
            
            # MODIFICAR: Usar la imagen FTP si está disponible
            if ftp_image_url:
                # Priorizar imagen FTP sobre imagen original
                original_thumbnail = self.video_data.get('thumbnail')
                self.video_data['thumbnail'] = ftp_image_url
                logger.info(f"🎯 Usando imagen FTP para WordPress: {ftp_image_url}")
                print(f"🎯 WordPress usará imagen FTP: {ftp_image_url}")
            
            # Publicar video
            result = publisher.publish_video(
                video_data=self.video_data,
                category_id=self.selected_category_for_publish['id'],
                streamwish_filecode=streamwish_code
            )
            
            if result['success']:
                main_window.update_progress_status(f"✅ Publicado en WordPress! Post ID: {result['post_id']}")
                
                # ACTUALIZAR: Mostrar información de archivos descargados
                downloaded_paths = self.downloader.get_downloaded_paths()
                
                # Mostrar mensaje de éxito mejorado
                success_msg = (
                    f"🎉 <b>Video publicado exitosamente!</b><br><br>"
                    f"📝 <b>Post ID:</b> {result['post_id']}<br>"
                    f"📂 <b>Categoría:</b> {self.selected_category_for_publish['title']}<br>"
                    f"🎬 <b>Título:</b> {self.video_data['title'][:50]}...<br>"
                )
                
                # Información de archivos descargados
                if downloaded_paths['video_path']:
                    video_filename = os.path.basename(downloaded_paths['video_path'])
                    success_msg += f"🎥 <b>Video local:</b> {video_filename}<br>"
                
                if downloaded_paths['image_path']:
                    image_filename = os.path.basename(downloaded_paths['image_path'])
                    success_msg += f"🖼️ <b>Imagen local:</b> {image_filename}<br>"
                
                if ftp_image_url:
                    success_msg += f"🌐 <b>Imagen FTP:</b> {ftp_image_url}<br>"
                
                if streamwish_code:
                    embed_url = f"https://omeplay.com/embed2/?host=streamwish&id={streamwish_code}&ahost=streamwish&aid={streamwish_code}"
                    success_msg += f"🎥 <b>Reproductor:</b> StreamWish configurado<br>"
                    success_msg += f"🔗 <b>URL:</b> {embed_url}<br>"
                
                success_msg += f"<br>🌐 <b>Ver en:</b> https://omeplay.com/?p={result['post_id']}"
                
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("🎉 Publicación Exitosa")
                msg_box.setText(success_msg)
                msg_box.setTextFormat(Qt.RichText)
                msg_box.setIcon(QMessageBox.Information)
                msg_box.exec_()
                
                print(f"🎉 Video publicado en WordPress: Post ID {result['post_id']}")
                
                # Mostrar rutas de archivos en consola
                if downloaded_paths['video_path']:
                    print(f"📁 Video guardado: {downloaded_paths['video_path']}")
                if downloaded_paths['image_path']:
                    print(f"📁 Imagen guardada: {downloaded_paths['image_path']}")
                
            else:
                main_window.update_progress_status(f"❌ Error publicando: {result['error']}")
                
                QMessageBox.critical(
                    self,
                    "Error de Publicación",
                    f"❌ Error publicando en WordPress:\n\n{result['error']}\n\n"
                    f"Verifica:\n"
                    f"• Conexión a la base de datos\n"
                    f"• Permisos de escritura\n"
                    f"• Configuración en database/config.py"
                )
                
                print(f"❌ Error publicando en WordPress: {result['error']}")
                self.already_published = False  # ✅ Resetear flag si hay error
            
            # Ocultar progreso después de un momento
            main_window.hide_progress()
            
        except Exception as e:
            error_msg = f"Error inesperado publicando: {str(e)}"
            main_window = self.window()
            main_window.update_progress_status(f"❌ {error_msg}")
            main_window.hide_progress()
            
            QMessageBox.critical(self, "Error", f"❌ {error_msg}")
            print(f"❌ {error_msg}")
            self.already_published = False  # ✅ Resetear flag si hay error

    def _extract_streamwish_code(self):
        """Extrae el código de StreamWish del resultado del upload"""
        try:
            # Usar el nuevo método del uploader
            if (hasattr(self.downloader, 'streamwish_uploader') and 
                self.downloader.streamwish_uploader):
                
                code = self.downloader.streamwish_uploader.get_last_filecode()
                if code:
                    print(f"✅ Código de StreamWish obtenido: {code}")
                    return code
            
            print("⚠️ No se pudo obtener código de StreamWish")
            return None
            
        except Exception as e:
            print(f"⚠️ Error extrayendo código de StreamWish: {str(e)}")
            return None
    
    def _handle_worker_finished(self, success):
        """Maneja finalización del worker thread"""
        self.is_downloading = False
        
        if success:
            self.import_button.setText("✅ Completado")
            self.import_button.setStyleSheet("""
                QPushButton {
                    background-color: #28A745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
        else:
            self.import_button.setText("❌ Error")
            self.import_button.setStyleSheet("""
                QPushButton {
                    background-color: #DC3545;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
        
        self.import_button.setEnabled(True)
        
        # Restaurar el estado original después de 5 segundos
        QTimer.singleShot(5000, self._restore_button)
    
    def _restore_button(self):
        """Restaura el estado original del botón"""
        if not self.is_downloading and not self.already_published:
            self.import_button.setText("Importar")
            self.import_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF6B35;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #E55A2B;
                }
                QPushButton:pressed {
                    background-color: #CC4E26;
                }
            """)
        elif self.already_published:
            # Mantener el estado de "Completado" para videos ya publicados
            self.import_button.setText("✅ Publicado")
            self.import_button.setEnabled(False)
        
    def load_image(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://es.pornhub.com/'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                image = QImage()
                if image.loadFromData(response.content):
                    pixmap = QPixmap.fromImage(image)
                    scaled_pixmap = pixmap.scaled(
                        184, 130, 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    self.thumbnail_label.setPixmap(scaled_pixmap)
                    
        except Exception as e:
            print(f"Error al cargar imagen: {str(e)}")

class Opcion1Widget(QWidget):
    def __init__(self):
        super().__init__()
        self.scraper = Opcion1Scraper()
        self.loader = None
        self.video_count = 0
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Barra superior con configuración
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(20, 10, 20, 10)
        
        # Status de StreamWish (movemos el botón pero dejamos el status aquí)
        self.streamwish_status = QLabel("")
        
        top_bar_layout.addStretch()
        layout.addWidget(top_bar)
        
        # Etiqueta de estado
        self.status_label = QLabel("Selecciona una categoría para ver videos")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 16px; padding: 20px;")
        layout.addWidget(self.status_label)
        
        # Contador de videos
        self.counter_label = QLabel("")
        self.counter_label.setAlignment(Qt.AlignCenter)
        self.counter_label.setStyleSheet("color: #666; font-size: 14px; padding: 10px;")
        layout.addWidget(self.counter_label)
        
        # Scroll área para mostrar videos
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        
        self.content_widget = QWidget()
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid_layout.setContentsMargins(20, 20, 20, 20)
        self.grid_layout.setSpacing(15)
        
        self.scroll.setWidget(self.content_widget)
        layout.addWidget(self.scroll)
        
        # Ocultar scroll inicialmente
        self.scroll.hide()
        self.counter_label.hide()
        
        # Actualizar estado de StreamWish
        self.update_streamwish_status()
    
    def initialize(self):
        """Inicializa el widget cargando las categorías"""
        self.status_label.setText("Cargando categorías...")
        self.category_loader = CategoryLoader(self.scraper)
        self.category_loader.category_loaded.connect(self.on_categories_loaded)
        self.category_loader.start()
    
    def on_categories_loaded(self, categories):
        """Callback cuando se cargan las categorías"""
        # Obtener referencia a la ventana principal
        main_window = self.window()
        
        # Borrar categorías existentes
        while main_window.cat_layout.count():
            child = main_window.cat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not categories:
            self.status_label.setText("No se pudieron cargar las categorías")
            return
        
        # Añadir categorías a la barra lateral
        for category in categories:
            category_btn = QPushButton(f"{category['title']} ({category['count']})")
            category_btn.setObjectName("category-button")
            category_btn.clicked.connect(lambda checked, url=category['url']: self.load_category(url))
            main_window.cat_layout.addWidget(category_btn)
        
        self.status_label.setText(f"✅ {len(categories)} categorías cargadas. Selecciona una categoría.")
    
    def load_category(self, category_url):
        """Carga los videos de una categoría"""
        # Mostrar mensaje de carga
        self.status_label.setText("Cargando videos...")
        self.status_label.show()
        self.scroll.hide()
        self.counter_label.hide()
        self.video_count = 0
        
        # Limpiar el grid de videos
        self.clear_videos()
        
        # Detener el cargador anterior si existe
        if self.loader and self.loader.isRunning():
            self.loader.stop()
            self.loader.wait()
        
        # Crear y arrancar nuevo cargador
        self.loader = VideoLoader(self.scraper, category_url)
        self.loader.video_loaded.connect(self.add_video)
        self.loader.finished_loading.connect(self.on_loading_finished)
        self.loader.start()
    
    def add_video(self, video_data):
        """Añade un video al grid"""
        # Ocultar mensaje de estado y mostrar scroll la primera vez
        if self.status_label.isVisible():
            self.status_label.hide()
            self.scroll.show()
            self.counter_label.show()
        
        self.video_count += 1
        self.counter_label.setText(f"Videos cargados: {self.video_count}")
        
        row = (self.video_count - 1) // 4  # 4 columnas
        col = (self.video_count - 1) % 4
        
        video_card = VideoCard(video_data)
        self.grid_layout.addWidget(video_card, row, col)
    
    def on_loading_finished(self):
        """Callback cuando termina la carga de videos"""
        if self.video_count == 0:
            self.status_label.setText("No se encontraron videos en esta categoría")
            self.status_label.show()
            self.scroll.hide()
            self.counter_label.hide()
        else:
            self.counter_label.setText(f"✅ {self.video_count} videos cargados. Haz clic en 'Importar' para descargar.")
            print(f"✅ Se cargaron {self.video_count} videos exitosamente")
    
    def configure_streamwish(self):
        """Abre el diálogo de configuración de StreamWish"""
        if not STREAMWISH_AVAILABLE:
            QMessageBox.warning(self, "Error", "StreamWish no está disponible.\nInstala las dependencias necesarias.")
            return
        
        dialog = StreamWishConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_config()
            
            if not config['api_key']:
                QMessageBox.warning(self, "Error", "La API Key es requerida para configurar StreamWish.")
                return
            
            # Configurar StreamWish
            try:
                downloader = VideoDownloader()
                
                # Configurar delete_after_upload por separado
                if config['delete_after_upload']:
                    downloader.streamwish_config.set_delete_after_upload(True)
                
                success = downloader.configure_streamwish(
                    config['api_key'],
                    config['auto_upload'],
                    config['upload_settings']
                )
                
                if success:
                    QMessageBox.information(self, "Éxito", "StreamWish configurado correctamente!")
                    self.update_streamwish_status()
                else:
                    QMessageBox.critical(self, "Error", "Error configurando StreamWish.\nVerifica tu API Key.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error configurando StreamWish:\n{str(e)}")
    
    def update_streamwish_status(self):
        """Actualiza el estado de StreamWish en la UI"""
        if not STREAMWISH_AVAILABLE:
            self.streamwish_status.setText("StreamWish no disponible")
            return
        
        try:
            downloader = VideoDownloader()
            status = downloader.get_streamwish_status()
            
            if status['configured']:
                if status['auto_upload']:
                    self.streamwish_status.setText("☁️ StreamWish: Configurado - Upload automático ON")
                    self.streamwish_status.setStyleSheet("color: #4CAF50; font-size: 11px;")
                else:
                    self.streamwish_status.setText("☁️ StreamWish: Configurado - Upload automático OFF")
                    self.streamwish_status.setStyleSheet("color: #FF9800; font-size: 11px;")
            else:
                self.streamwish_status.setText("☁️ StreamWish: No configurado")
                self.streamwish_status.setStyleSheet("color: #666; font-size: 11px;")
                
        except Exception as e:
            self.streamwish_status.setText("☁️ StreamWish: Error")
            self.streamwish_status.setStyleSheet("color: #f44336; font-size: 11px;")
    
    def clear_videos(self):
        """Limpia todos los videos del grid"""
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.video_count = 0