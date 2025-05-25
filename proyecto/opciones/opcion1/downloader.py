import requests
from bs4 import BeautifulSoup
import logging
import json
import re
import os
import time
import subprocess
from urllib.parse import urljoin, urlparse
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal

# Importar configuraciones
from .config import DownloadConfig
from .config_streamwish import StreamWishConfig
from .streamwish_uploader import StreamWishUploader

# Configurar logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('VideoDownloader')

class ProgressReporter(QObject):
    """Señales para reportar progreso"""
    download_progress = pyqtSignal(int)  # 0-100
    upload_progress = pyqtSignal(int)    # 0-100
    conversion_progress = pyqtSignal(int)  # 0-100
    status_changed = pyqtSignal(str)     # Mensaje de estado
    finished = pyqtSignal(bool)          # True si exitoso

class VideoDownloader(QObject):
    def __init__(self):
        super().__init__()
        self.base_url = "https://es.pornhub.com"
        self.headers = DownloadConfig.DEFAULT_HEADERS
        
        # Crear carpeta de descargas si no existe
        self.download_folder = DownloadConfig.get_download_folder()
        
        # Configuración de StreamWish
        self.streamwish_config = StreamWishConfig()
        self.streamwish_uploader = None
        
        # Reporter de progreso
        self.progress_reporter = ProgressReporter()
        
        # Variables para almacenar rutas de archivos descargados
        self.downloaded_video_path = None
        self.downloaded_image_path = None
        
        # Inicializar StreamWish si está configurado
        if self.streamwish_config.is_configured():
            self.streamwish_uploader = StreamWishUploader(self.streamwish_config.get_api_key())
            # Conectar señales de upload
            self.streamwish_uploader.progress_reporter.upload_progress.connect(
                self.progress_reporter.upload_progress.emit
            )
            self.streamwish_uploader.progress_reporter.status_changed.connect(
                self.progress_reporter.status_changed.emit
            )

    def _clean_filename_advanced(self, filename):
        """Limpia nombre de archivo de forma avanzada - MÉTODO UNIFICADO"""
        import re
        
        # Remover caracteres especiales y acentos
        clean_name = filename
        clean_name = re.sub(r'[áàäâ]', 'a', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'[éèëê]', 'e', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'[íìïî]', 'i', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'[óòöô]', 'o', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'[úùüû]', 'u', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'[ñ]', 'n', clean_name, flags=re.IGNORECASE)
        
        # Remover caracteres especiales, mantener solo letras, números, espacios y guiones
        clean_name = re.sub(r'[^\w\s-]', '', clean_name)
        
        # Convertir espacios múltiples a uno solo
        clean_name = re.sub(r'\s+', ' ', clean_name)
        
        # Convertir espacios a guiones
        clean_name = clean_name.replace(' ', '-')
        
        # Remover guiones múltiples
        clean_name = re.sub(r'-+', '-', clean_name)
        
        # Convertir a minúsculas
        clean_name = clean_name.lower()
        
        # Remover guiones al inicio y final
        clean_name = clean_name.strip('-')
        
        # Limitar longitud a 80 caracteres
        if len(clean_name) > 80:
            clean_name = clean_name[:80].rstrip('-')
        
        logger.info(f"📝 Nombre original: {filename}")
        logger.info(f"📝 Nombre limpio: {clean_name}")
        print(f"📝 Limpiando: {filename} → {clean_name}")
        
        return clean_name.strip()
           
    def _extract_twitter_image(self, html_content):
        """
        Extrae la URL de imagen del meta tag twitter:image
        """
        try:
            import re
            
            # Buscar el meta tag twitter:image
            patterns = [
            r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
            r'<meta\s+name=["\']og:image["\']\s+content=["\']([^"\']+)["\']'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    image_url = matches[0]
                    logger.info(f"🖼️ Imagen Twitter encontrada: {image_url}")
                    print(f"✅ Imagen detectada: {image_url}")
                    return image_url
            
            logger.warning("⚠️ No se encontró meta tag twitter:image")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo imagen Twitter: {str(e)}")
            return None

    def _download_image(self, image_url, video_title):
        """
        Descarga la imagen localmente con nombre limpio
        """
        try:
            if not image_url:
                logger.warning("⚠️ No hay URL de imagen para descargar")
                return None
            
            self.progress_reporter.status_changed.emit("🖼️ Descargando imagen...")
            logger.info(f"🖼️ Descargando imagen: {image_url}")
            print(f"📥 Descargando imagen desde: {image_url}")
            
            # Crear nombre de archivo limpio - SIN post_id ni _thumbnail
            clean_title = self._clean_filename_advanced(video_title)
            
            # Determinar extensión de la imagen
            if '.jpg' in image_url or 'jpeg' in image_url:
                image_extension = '.jpg'
            elif '.png' in image_url:
                image_extension = '.png'
            elif '.webp' in image_url:
                image_extension = '.webp'
            else:
                image_extension = '.jpg'  # Por defecto
            
            # Nombre final: titulo-limpio.jpg (SIN _thumbnail)
            image_filename = f"{clean_title}{image_extension}"
            image_path = self.download_folder / image_filename
            
            # Verificar si la imagen ya existe
            if image_path.exists():
                logger.info(f"ℹ️ La imagen ya existe: {image_filename}")
                print(f"✅ Imagen ya descargada: {image_filename}")
                return str(image_path)
            
            # Descargar la imagen
            response = requests.get(image_url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"✅ Imagen descargada: {image_path}")
                print(f"✅ Imagen guardada: {image_filename}")
                return str(image_path)
            else:
                logger.error(f"❌ Error descargando imagen: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error descargando imagen: {str(e)}")
            print(f"❌ Error descargando imagen: {str(e)}")
            return None

    def _upload_image_to_ftp(self, image_path, video_title):
        """
        Sube la imagen descargada por FTP con nombre limpio (SIN post_id)
        """
        try:
            if not image_path or not os.path.exists(image_path):
                logger.warning("⚠️ No hay imagen para subir por FTP")
                return None
            
            self.progress_reporter.status_changed.emit("📤 Subiendo imagen por FTP...")
            logger.info(f"📤 Subiendo imagen por FTP: {image_path}")
            print(f"📤 Subiendo imagen: {os.path.basename(image_path)}")
            
            # Conectar FTP
            import ftplib
            import tempfile
            from datetime import datetime
            
            # Configuración FTP
            ftp_host = "154.12.238.207"
            ftp_user = "arielmmc@xpleasurehub.com"
            ftp_pass = "G5)QO]2I3c(u"
            ftp_port = 21
            web_base_url = "https://www.xpleasurehub.com/wp-content/uploads"
            
            # Leer la imagen
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Crear nombre final limpio (sin post_id)
            clean_title = self._clean_filename_advanced(video_title)
            extension = os.path.splitext(image_path)[1]
            final_filename = f"{clean_title}{extension}"
            
            # Estructura de carpetas
            current_year = datetime.now().year
            current_month = datetime.now().strftime('%m')
            remote_folder = f"{current_year}/{current_month}"
            
            ftp = None
            try:
                # Conectar FTP
                ftp = ftplib.FTP()
                ftp.connect(ftp_host, ftp_port)
                ftp.login(ftp_user, ftp_pass)
                
                logger.info(f"🔗 Conectado a FTP: {ftp.pwd()}")
                print(f"🔗 FTP conectado")
                
                # Crear estructura de carpetas
                self._create_ftp_directories_simple(ftp, remote_folder)
                
                # Cambiar a directorio de destino
                ftp.cwd(f"/{remote_folder}")
                
                # Crear archivo temporal para upload
                with tempfile.NamedTemporaryFile() as temp_file:
                    temp_file.write(image_data)
                    temp_file.flush()
                    
                    # Subir archivo
                    with open(temp_file.name, 'rb') as f:
                        result = ftp.storbinary(f'STOR {final_filename}', f)
                        logger.info(f"📤 Upload resultado: {result}")
                
                # Construir URL web final
                web_url = f"{web_base_url}/{remote_folder}/{final_filename}"
                
                # Verificar que se subió
                files = ftp.nlst()
                if final_filename in files:
                    logger.info(f"✅ Imagen verificada en servidor: {final_filename}")
                    print(f"✅ Imagen confirmada: {final_filename}")
                else:
                    logger.warning(f"⚠️ {final_filename} no encontrado en listado")
                
                ftp.quit()
                
                logger.info(f"✅ Imagen subida por FTP: {web_url}")
                print(f"🌐 URL FTP: {web_url}")
                return web_url
                
            except Exception as ftp_error:
                if ftp:
                    try:
                        ftp.quit()
                    except:
                        pass
                logger.error(f"❌ Error FTP: {str(ftp_error)}")
                print(f"❌ Error FTP: {str(ftp_error)}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error en upload FTP de imagen: {str(e)}")
            print(f"❌ Error FTP imagen: {str(e)}")
            return None

    def _create_ftp_directories_simple(self, ftp, path):
        """Crea directorios FTP de forma simple"""
        import ftplib
        
        try:
            # Dividir path: "2025/05" -> ["2025", "05"]
            parts = path.strip('/').split('/')
            current_path = ""
            
            for part in parts:
                current_path = part if not current_path else current_path + "/" + part
                
                try:
                    ftp.cwd("/" + current_path)
                except ftplib.error_perm:
                    # No existe, crearlo
                    try:
                        ftp.cwd("/")
                        ftp.mkd(current_path)
                        ftp.cwd("/" + current_path)
                        print(f"✅ Creado directorio: {current_path}")
                    except ftplib.error_perm as e:
                        logger.error(f"❌ Error creando {current_path}: {str(e)}")
                        return False
            return True
        except Exception as e:
            logger.error(f"❌ Error creando directorios: {str(e)}")
            return False

    def download_video(self, video_url, video_data):
        """
        Descarga un video desde la URL proporcionada y opcionalmente lo sube a StreamWish
        """
        try:
            self.progress_reporter.status_changed.emit("🔍 Analizando video...")
            logger.info(f"🔍 Analizando video: {video_data.get('title', 'Sin título')}")
            
            # Obtener el HTML de la página del video
            response = requests.get(video_url, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"❌ Error al acceder a la página: {response.status_code}")
                self.progress_reporter.finished.emit(False)
                return False
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # EXTRAER IMAGEN DE TWITTER META TAG
            twitter_image = self._extract_twitter_image(response.text)
            if twitter_image:
                # Actualizar video_data con la imagen encontrada
                video_data['twitter_image'] = twitter_image
                logger.info(f"🎯 Imagen Twitter agregada a video_data: {twitter_image}")
                
                # DESCARGAR IMAGEN LOCALMENTE con nombre limpio
                downloaded_image_path = self._download_image(twitter_image, video_data.get('title', 'video'))
                if downloaded_image_path:
                    self.downloaded_image_path = downloaded_image_path
                    video_data['local_image_path'] = downloaded_image_path
                    logger.info(f"💾 Imagen guardada localmente: {downloaded_image_path}")
                    print(f"💾 Imagen local: {os.path.basename(downloaded_image_path)}")
                    
                    # SUBIR IMAGEN POR FTP inmediatamente
                    ftp_image_url = self._upload_image_to_ftp(downloaded_image_path, video_data.get('title', 'video'))
                    if ftp_image_url:
                        video_data['ftp_image_url'] = ftp_image_url
                        logger.info(f"🌐 Imagen FTP URL: {ftp_image_url}")
                        print(f"🌐 Imagen en servidor: {ftp_image_url}")
                
            # Buscar las URLs de video en los scripts
            self.progress_reporter.status_changed.emit("🔍 Buscando URLs de video...")
            video_urls = self._extract_video_urls(response.text)
            
            if not video_urls:
                logger.error("❌ No se encontraron URLs de video")
                self.progress_reporter.finished.emit(False)
                return False
            
            # Seleccionar la mejor calidad disponible
            best_video_url, video_format = self._select_best_quality(video_urls)
            
            if not best_video_url:
                logger.error("❌ No se pudo determinar la mejor calidad")
                self.progress_reporter.finished.emit(False)
                return False
            
            logger.info(f"🎥 URL de video encontrada: {best_video_url[:100]}...")
            logger.info(f"📹 Formato detectado: {video_format}")
            
            # Descargar según el formato
            self.progress_reporter.status_changed.emit(f"⬇️ Descargando {video_format.upper()}...")
            
            if video_format == 'hls':
                download_success = self._download_hls_with_ffmpeg(best_video_url, video_data)
            elif video_format == 'mp4':
                download_success = self._download_direct_mp4(best_video_url, video_data)
            else:
                logger.error(f"❌ Formato no soportado: {video_format}")
                self.progress_reporter.finished.emit(False)
                return False
            
            if download_success:
                self.progress_reporter.download_progress.emit(100)
                self.progress_reporter.status_changed.emit("✅ Descarga completada!")
                
                # Guardar ruta del video descargado con nombre limpio
                title = video_data.get('title', 'video_sin_titulo')
                clean_title = self._clean_filename_advanced(title)
                self.downloaded_video_path = str(self.download_folder / f"{clean_title}.mp4")
                
                # Si StreamWish está configurado para auto-upload
                if self.streamwish_config.is_auto_upload_enabled():
                    time.sleep(1)  # Pequeña pausa visual
                    upload_success = self._upload_to_streamwish(video_data)
                    self.progress_reporter.finished.emit(upload_success)
                    return upload_success
                else:
                    self.progress_reporter.finished.emit(True)
                    return True
            else:
                self.progress_reporter.finished.emit(False)
                return False
            
        except Exception as e:
            logger.error(f"❌ Error general durante la descarga: {str(e)}")
            self.progress_reporter.status_changed.emit(f"❌ Error: {str(e)}")
            self.progress_reporter.finished.emit(False)
            return False
    
    def _upload_to_streamwish(self, video_data):
        """
        Sube el video descargado a StreamWish
        """
        try:
            if not self.streamwish_uploader:
                logger.warning("⚠️ StreamWish no está configurado correctamente")
                return False
            
            # Construir la ruta del archivo descargado con nombre limpio
            title = video_data.get('title', 'video_sin_titulo')
            clean_title = self._clean_filename_advanced(title)
            video_file = self.download_folder / f"{clean_title}.mp4"
            
            if not video_file.exists():
                logger.error(f"❌ Archivo descargado no encontrado: {video_file}")
                return False
            
            self.progress_reporter.status_changed.emit("📤 Iniciando upload a StreamWish...")
            logger.info(f"📤 Iniciando upload a StreamWish: {clean_title}")
            
            # Preparar datos adicionales para el upload
            upload_data = {
                'title': title,
                'description': f"Video descargado desde {video_data.get('url', '')}",
                'tags': f"pornhub, {video_data.get('uploader', '')}, hd".replace(', ,', ',').strip(','),
                'duration': video_data.get('duration', ''),
                'views': video_data.get('views', ''),
                'rating': video_data.get('rating', '')
            }
            
            # Obtener configuración de upload
            upload_settings = self.streamwish_config.get_upload_settings()
            
            # Realizar el upload
            result = self.streamwish_uploader.upload_video(
                str(video_file), 
                upload_data, 
                upload_settings
            )
            
            if result and result.get('status') == 200:
                logger.info("✅ Upload a StreamWish completado exitosamente")
                self.progress_reporter.status_changed.emit("✅ Upload completado!")
                
                # Mostrar información de los archivos subidos
                if 'files' in result:
                    for file_info in result['files']:
                        filecode = file_info.get('filecode', 'N/A')
                        logger.info(f"🔗 StreamWish Code: {filecode}")
                        logger.info(f"🌐 Ver en: https://streamwish.to/{filecode}")
                
                # Si está configurado para eliminar después del upload
                if self.streamwish_config.is_delete_after_upload_enabled():
                    try:
                        video_file.unlink()
                        logger.info(f"🗑️ Archivo local eliminado: {clean_title}")
                        self.progress_reporter.status_changed.emit("🗑️ Archivo local eliminado")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo eliminar el archivo local: {str(e)}")
                
                return True
            else:
                logger.error("❌ Error en upload a StreamWish")
                self.progress_reporter.status_changed.emit("❌ Error en upload")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error durante upload a StreamWish: {str(e)}")
            self.progress_reporter.status_changed.emit(f"❌ Error upload: {str(e)}")
            return False
    
    def configure_streamwish(self, api_key, auto_upload=True, upload_settings=None):
        """
        Configura StreamWish con los parámetros proporcionados
        """
        try:
            # Configurar API key
            if not self.streamwish_config.set_api_key(api_key):
                return False
            
            # Configurar auto upload
            if not self.streamwish_config.set_auto_upload(auto_upload):
                return False
            
            # Configurar settings de upload si se proporcionan
            if upload_settings:
                if not self.streamwish_config.update_upload_settings(upload_settings):
                    return False
            
            # Inicializar el uploader
            self.streamwish_uploader = StreamWishUploader(api_key)
            
            # Conectar señales de progreso
            self.streamwish_uploader.progress_reporter.upload_progress.connect(
                self.progress_reporter.upload_progress.emit
            )
            self.streamwish_uploader.progress_reporter.status_changed.connect(
                self.progress_reporter.status_changed.emit
            )
            
            # Probar la conexión
            if self.streamwish_uploader.test_connection():
                logger.info("✅ StreamWish configurado y probado exitosamente")
                return True
            else:
                logger.error("❌ Error probando conexión con StreamWish")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error configurando StreamWish: {str(e)}")
            return False
    
    def get_streamwish_status(self):
        """
        Obtiene el estado actual de la configuración de StreamWish
        """
        try:
            return {
                'configured': self.streamwish_config.is_configured(),
                'auto_upload': self.streamwish_config.is_auto_upload_enabled(),
                'api_key_set': bool(self.streamwish_config.get_api_key()),
                'uploader_ready': self.streamwish_uploader is not None
            }
        except Exception as e:
            logger.error(f"❌ Error obteniendo estado de StreamWish: {str(e)}")
            return {
                'configured': False,
                'auto_upload': False,
                'api_key_set': False,
                'uploader_ready': False
            }
    
    def upload_existing_video(self, video_path, video_data=None):
        """
        Sube un video ya existente a StreamWish
        """
        try:
            if not self.streamwish_uploader:
                logger.error("❌ StreamWish no está configurado")
                return False
            
            if not os.path.exists(video_path):
                logger.error(f"❌ Archivo no encontrado: {video_path}")
                return False
            
            # Si no se proporcionan datos del video, usar el nombre del archivo
            if not video_data:
                filename = os.path.splitext(os.path.basename(video_path))[0]
                video_data = {
                    'title': filename,
                    'description': f"Video subido desde archivo local: {filename}"
                }
            
            result = self.streamwish_uploader.upload_video(
                video_path,
                video_data,
                self.streamwish_config.get_upload_settings()
            )
            
            return result and result.get('status') == 200
            
        except Exception as e:
            logger.error(f"❌ Error subiendo video existente: {str(e)}")
            return False
    
    def _extract_video_urls(self, html_content):
        """
        Extrae las URLs de video del HTML, priorizando MP4 directo sobre HLS
        """
        video_urls = {}
        
        try:
            # Buscar en flashvars
            flashvars_match = re.search(r'var flashvars_\d+\s*=\s*({.*?});', html_content, re.DOTALL)
            if flashvars_match:
                flashvars_str = flashvars_match.group(1)
                # Limpiar y parsear JSON
                flashvars_str = re.sub(r',\s*}', '}', flashvars_str)
                flashvars_str = re.sub(r',\s*]', ']', flashvars_str)
                
                try:
                    flashvars = json.loads(flashvars_str)
                    
                    # Buscar mediaDefinitions
                    if 'mediaDefinitions' in flashvars:
                        for media in flashvars['mediaDefinitions']:
                            if 'videoUrl' in media and 'quality' in media:
                                quality = media['quality']
                                if isinstance(quality, list) and len(quality) > 0:
                                    quality = quality[0]
                                elif isinstance(quality, str):
                                    quality = quality
                                else:
                                    quality = str(quality)
                                
                                video_url = media['videoUrl']
                                
                                # Determinar formato
                                if '.m3u8' in video_url or '/hls/' in video_url:
                                    format_type = 'hls'
                                elif '.mp4' in video_url and 'seg-' not in video_url:
                                    format_type = 'mp4'
                                else:
                                    format_type = 'unknown'
                                
                                video_urls[quality] = {
                                    'url': video_url,
                                    'format': format_type
                                }
                                logger.info(f"📹 Calidad encontrada: {quality} ({format_type})")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Error parseando flashvars JSON: {str(e)}")
            
            # Método alternativo: buscar URLs directamente en el HTML
            if not video_urls:
                logger.info("🔍 Buscando URLs alternativas...")
                # Buscar patrones de URLs de video MP4 directos
                mp4_patterns = [
                    r'"(https://[^"]*\.mp4[^"]*)"',
                    r'videoUrl:\s*"([^"]+\.mp4[^"]*)"',
                ]
                
                for pattern in mp4_patterns:
                    matches = re.findall(pattern, html_content)
                    for match in matches:
                        # Limpiar URL
                        clean_url = match.replace('\\/', '/')
                        if 'mp4' in clean_url and 'seg-' not in clean_url:
                            # Intentar extraer calidad del URL
                            quality_match = re.search(r'(\d+)P?_', clean_url)
                            quality = quality_match.group(1) if quality_match else 'unknown'
                            video_urls[quality] = {
                                'url': clean_url,
                                'format': 'mp4'
                            }
                            logger.info(f"📹 MP4 directo encontrado: {quality}")
            
            return video_urls
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo URLs de video: {str(e)}")
            return {}
    
    def _select_best_quality(self, video_urls):
        """
        Selecciona la mejor calidad disponible, priorizando MP4 directo
        """
        if not video_urls:
            return None, None
        
        # Prioridad de calidades (de mayor a menor)
        quality_priority = DownloadConfig.QUALITY_PRIORITY
        
        # Primero buscar MP4 directo
        for quality in quality_priority:
            if quality in video_urls and video_urls[quality]['format'] == 'mp4':
                logger.info(f"✅ Seleccionado MP4 directo: {quality}p")
                return video_urls[quality]['url'], 'mp4'
        
        # Si no hay MP4 directo, buscar HLS
        for quality in quality_priority:
            if quality in video_urls and video_urls[quality]['format'] == 'hls':
                logger.info(f"⚠️ Seleccionado HLS: {quality}p")
                return video_urls[quality]['url'], 'hls'
        
        # Último recurso: tomar cualquier formato disponible
        first_quality = list(video_urls.keys())[0]
        video_info = video_urls[first_quality]
        logger.info(f"⚠️ Usando formato disponible: {first_quality} ({video_info['format']})")
        return video_info['url'], video_info['format']
    
    def _download_direct_mp4(self, video_url, video_data):
        """
        Descarga un archivo MP4 directo con progreso y nombre limpio
        """
        return self._download_file(video_url, video_data, '.mp4')
    
    def _download_file(self, video_url, video_data, extension='.mp4'):
        """
        Descarga un archivo directo con progreso y nombre limpio
        """
        try:
            # Limpiar el nombre del archivo
            title = video_data.get('title', 'video_sin_titulo')
            clean_title = self._clean_filename_advanced(title)
            filename = f"{clean_title}{extension}"
            filepath = self.download_folder / filename
            
            # Verificar si el archivo ya existe
            if filepath.exists():
                logger.info(f"ℹ️ El archivo ya existe: {filename}")
                self.progress_reporter.download_progress.emit(100)
                return True
            
            logger.info(f"⬇️ Descargando: {filename}")
            
            # Realizar la descarga
            with requests.get(video_url, headers=self.headers, stream=True) as response:
                response.raise_for_status()
                
                # Obtener el tamaño total si está disponible
                total_size = int(response.headers.get('content-length', 0))
                
                with open(filepath, 'wb') as f:
                    downloaded = 0
                    chunk_size = DownloadConfig.CHUNK_SIZE
                    
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Calcular y emitir progreso
                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                self.progress_reporter.download_progress.emit(progress)
                                
                                # Log cada 10%
                                if progress % 10 == 0 and progress > 0:
                                    mb_downloaded = downloaded / (1024*1024)
                                    mb_total = total_size / (1024*1024)
                                    logger.info(f"📊 Descarga: {progress}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)")
                            else:
                                # Si no conocemos el tamaño total, actualizar cada MB
                                if downloaded % (1024 * 1024) == 0:
                                    mb_downloaded = downloaded / (1024*1024)
                                    logger.info(f"📊 Descargado: {mb_downloaded:.1f}MB")
            
            logger.info(f"✅ Descarga completada: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error durante la descarga del archivo: {str(e)}")
            self.progress_reporter.status_changed.emit(f"❌ Error descarga: {str(e)}")
            return False
    
    def _download_hls_with_ffmpeg(self, m3u8_url, video_data):
        """
        Descarga un stream HLS usando ffmpeg con progreso real y nombre limpio
        """
        try:
            # Verificar si ffmpeg está instalado
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("❌ FFmpeg no está instalado. Instalando...")
                return self._install_and_use_ffmpeg(m3u8_url, video_data)
            
            # Limpiar el nombre del archivo
            title = video_data.get('title', 'video_sin_titulo')
            clean_title = self._clean_filename_advanced(title)
            filename = f"{clean_title}.mp4"
            filepath = self.download_folder / filename
            
            # Verificar si el archivo ya existe
            if filepath.exists():
                logger.info(f"ℹ️ El archivo ya existe: {filename}")
                self.progress_reporter.download_progress.emit(100)
                return True
            
            logger.info(f"⬇️ Descargando HLS: {filename}")
            self.progress_reporter.status_changed.emit("📋 Analizando video HLS...")
            
            # Primero obtener información del video para calcular duración
            info_cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                m3u8_url
            ]
            
            try:
                info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
                duration = None
                if info_result.returncode == 0:
                    import json
                    info_data = json.loads(info_result.stdout)
                    if 'format' in info_data and 'duration' in info_data['format']:
                        duration = float(info_data['format']['duration'])
                        logger.info(f"🕐 Duración del video: {duration:.1f} segundos")
            except:
                duration = None
                logger.warning("⚠️ No se pudo obtener duración del video")
            
            self.progress_reporter.status_changed.emit("🔄 Convirtiendo video HLS...")
            
            # Comando ffmpeg con progreso
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', m3u8_url,
                '-c', 'copy',  # Copiar sin recodificar
                '-bsf:a', 'aac_adtstoasc',  # Fix para audio AAC
                '-progress', 'pipe:1',  # Enviar progreso a stdout
                '-y',  # Sobrescribir archivo si existe
                str(filepath)
            ]
            
            # Ejecutar ffmpeg con monitoreo de progreso
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Monitorear progreso en tiempo real
            self._monitor_ffmpeg_progress(process, duration)
            
            # Esperar a que termine el proceso
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                self.progress_reporter.download_progress.emit(100)
                self.progress_reporter.status_changed.emit("✅ Conversión HLS completada!")
                logger.info(f"✅ Descarga HLS completada: {filepath}")
                return True
            else:
                logger.error(f"❌ Error en ffmpeg: {stderr}")
                self.progress_reporter.status_changed.emit("❌ Error en conversión HLS")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error descargando HLS: {str(e)}")
            self.progress_reporter.status_changed.emit(f"❌ Error HLS: {str(e)}")
            return False
    
    def _monitor_ffmpeg_progress(self, process, total_duration=None):
        """
        Monitorea el progreso de FFmpeg en tiempo real
        """
        try:
            current_time = 0
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                
                if output:
                    line = output.strip()
                    
                    # Buscar información de tiempo actual
                    if line.startswith('out_time='):
                        time_str = line.split('=')[1]
                        try:
                            # Convertir tiempo formato HH:MM:SS.microseconds a segundos
                            if ':' in time_str:
                                time_parts = time_str.split(':')
                                if len(time_parts) == 3:
                                    hours = float(time_parts[0])
                                    minutes = float(time_parts[1])
                                    seconds = float(time_parts[2])
                                    current_time = hours * 3600 + minutes * 60 + seconds
                            else:
                                # Tiempo en microsegundos
                                current_time = float(time_str) / 1000000
                            
                            # Calcular progreso si conocemos la duración total
                            if total_duration and total_duration > 0:
                                progress = min(int((current_time / total_duration) * 100), 99)
                                self.progress_reporter.download_progress.emit(progress)
                                
                                if progress % 10 == 0 and progress > 0:
                                    logger.info(f"🔄 Conversión HLS: {progress}% ({current_time:.1f}s/{total_duration:.1f}s)")
                            else:
                                # Si no conocemos la duración, mostrar tiempo transcurrido
                                if int(current_time) % 5 == 0:  # Log cada 5 segundos
                                    logger.info(f"🔄 Procesando HLS: {current_time:.1f}s")
                                    # Progreso estimado basado en tiempo (máximo 90%)
                                    estimated_progress = min(int(current_time * 2), 90)
                                    self.progress_reporter.download_progress.emit(estimated_progress)
                        
                        except ValueError:
                            continue
                    
                    # Buscar estado del progreso
                    elif line.startswith('progress='):
                        status = line.split('=')[1]
                        if status == 'end':
                            self.progress_reporter.download_progress.emit(100)
                            break
                        elif status == 'continue':
                            self.progress_reporter.status_changed.emit(f"🔄 Convirtiendo... {current_time:.1f}s")
        
        except Exception as e:
            logger.error(f"❌ Error monitoreando progreso FFmpeg: {str(e)}")
    
    def _install_and_use_ffmpeg(self, m3u8_url, video_data):
        """
        Intenta instalar ffmpeg y descargar el video
        """
        try:
            import platform
            system = platform.system().lower()
            
            logger.info("🔧 Intentando instalar ffmpeg...")
            self.progress_reporter.status_changed.emit("🔧 Instalando ffmpeg...")
            
            if system == "darwin":  # macOS
                try:
                    subprocess.run(['brew', 'install', 'ffmpeg'], check=True)
                    return self._download_hls_with_ffmpeg(m3u8_url, video_data)
                except subprocess.CalledProcessError:
                    logger.error("❌ No se pudo instalar ffmpeg con Homebrew")
            
            elif system == "linux":
                try:
                    subprocess.run(['sudo', 'apt', 'update'], check=True)
                    subprocess.run(['sudo', 'apt', 'install', '-y', 'ffmpeg'], check=True)
                    return self._download_hls_with_ffmpeg(m3u8_url, video_data)
                except subprocess.CalledProcessError:
                    logger.error("❌ No se pudo instalar ffmpeg con apt")
            
            # Fallback: descargar segmentos manualmente
            logger.warning("⚠️ Fallback: descargando segmentos HLS manualmente...")
            return self._download_hls_manually(m3u8_url, video_data)
            
        except Exception as e:
            logger.error(f"❌ Error en instalación de ffmpeg: {str(e)}")
            return False
    
    def _download_hls_manually(self, m3u8_url, video_data):
        """
        Descarga manual de HLS obteniendo la playlist y segmentos con nombre limpio
        """
        try:
            logger.info("📋 Descargando playlist HLS...")
            self.progress_reporter.status_changed.emit("📋 Analizando playlist HLS...")
            
            # Descargar playlist m3u8
            response = requests.get(m3u8_url, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"❌ Error descargando playlist: {response.status_code}")
                return False
            
            playlist_content = response.text
            
            # Extraer URLs de segmentos
            segment_urls = []
            base_url = m3u8_url.rsplit('/', 1)[0] + '/'
            
            for line in playlist_content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    if line.startswith('http'):
                        segment_urls.append(line)
                    else:
                        segment_urls.append(base_url + line)
            
            if not segment_urls:
                logger.error("❌ No se encontraron segmentos en la playlist")
                return False
            
            logger.info(f"📦 Encontrados {len(segment_urls)} segmentos")
            
            # Descargar segmentos y combinar con nombre limpio
            title = video_data.get('title', 'video_sin_titulo')
            clean_title = self._clean_filename_advanced(title)
            temp_folder = self.download_folder / f"temp_{clean_title}"
            temp_folder.mkdir(exist_ok=True)
            
            # Descargar cada segmento con progreso
            for i, segment_url in enumerate(segment_urls):
                try:
                    segment_response = requests.get(segment_url, headers=self.headers)
                    if segment_response.status_code == 200:
                        segment_path = temp_folder / f"segment_{i:04d}.ts"
                        with open(segment_path, 'wb') as f:
                            f.write(segment_response.content)
                        
                        # Calcular y emitir progreso
                        progress = int((i + 1) / len(segment_urls) * 100)
                        self.progress_reporter.download_progress.emit(progress)
                        
                        if i % 10 == 0:  # Log cada 10 segmentos
                            logger.info(f"📊 Descargando segmentos: {progress}% ({i+1}/{len(segment_urls)})")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error descargando segmento {i}: {str(e)}")
            
            # Combinar segmentos
            self.progress_reporter.status_changed.emit("🔧 Combinando segmentos...")
            final_path = self.download_folder / f"{clean_title}.mp4"
            with open(final_path, 'wb') as output_file:
                for i in range(len(segment_urls)):
                    segment_path = temp_folder / f"segment_{i:04d}.ts"
                    if segment_path.exists():
                        with open(segment_path, 'rb') as segment_file:
                            output_file.write(segment_file.read())
            
            # Limpiar archivos temporales
            import shutil
            shutil.rmtree(temp_folder)
            
            logger.info(f"✅ Video HLS combinado: {final_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en descarga manual HLS: {str(e)}")
            return False

    def get_downloaded_paths(self):
        """
        Devuelve las rutas de los archivos descargados
        """
        return {
            'video_path': self.downloaded_video_path,
            'image_path': self.downloaded_image_path
        }
    
    def get_image_ftp_url(self, video_title, post_id=None):
        """
        Devuelve la URL FTP de la imagen (ya subida en download_video)
        """
        # Si ya se subió la imagen, la URL está en video_data
        # Esta función es para compatibilidad con el código existente
        return None  # Ya no es necesaria porque se sube automáticamente