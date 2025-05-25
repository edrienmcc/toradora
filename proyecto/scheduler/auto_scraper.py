# proyecto/scheduler/auto_scraper.py
import logging
import time
import random
from typing import Dict, List, Optional
from datetime import datetime

# Importar módulos existentes
from opciones.opcion1.scraper import Opcion1Scraper
from opciones.opcion1.downloader import VideoDownloader
from database.wordpress_publisher import WordPressPublisher
from database.category_manager import CategoryManager

logger = logging.getLogger(__name__)

class AutoScraper:
    """Ejecuta scraping automático programado"""
    
    def __init__(self):
        self.scraper = Opcion1Scraper()
        self.downloader = VideoDownloader()
        self.publisher = WordPressPublisher()
        self.category_manager = CategoryManager()
        
        # Configuración por defecto
        self.default_config = {
            'max_videos_per_run': 50,
            'delay_between_videos': (1, 3),  # segundos (min, max)
            'auto_publish': True,
            'skip_existing': True,
            'max_retries': 3
        }
        
        logger.info("🤖 AutoScraper inicializado")
    
    def execute_scheduled_scraping(self, category_url: str, category_name: str, 
                                 max_videos: int = 50, auto_publish: bool = True,
                                 task_config: Dict = None) -> Dict:
        """
        Ejecuta scraping programado para una categoría
        
        Args:
            category_url: URL de la categoría a scrapear
            category_name: Nombre de la categoría
            max_videos: Máximo número de videos a procesar
            auto_publish: Si auto-publicar en WordPress
            task_config: Configuración adicional de la tarea
            
        Returns:
            Dict con resultado de la ejecución
        """
        start_time = datetime.now()
        result = {
            'success': False,
            'message': '',
            'videos_processed': 0,
            'videos_published': 0,
            'errors': [],
            'start_time': start_time.isoformat(),
            'end_time': None
        }
        
        try:
            logger.info(f"🚀 Iniciando scraping automático: {category_name}")
            logger.info(f"📂 URL: {category_url}")
            logger.info(f"🎯 Máximo videos: {max_videos}")
            logger.info(f"📝 Auto publicar: {auto_publish}")
            
            # Combinar configuración
            config = {**self.default_config}
            if task_config:
                config.update(task_config)
            
            # Obtener categorías de WordPress para publicación
            wp_categories = []
            if auto_publish:
                wp_categories = self._get_wordpress_categories()
                if not wp_categories:
                    result['errors'].append("No se pudieron cargar categorías de WordPress")
                    logger.error("❌ No hay categorías de WordPress disponibles")
                    return result
            
            # Obtener videos de la categoría
            logger.info("🔍 Obteniendo videos de la categoría...")
            videos = list(self.scraper.get_videos(category_url))
            
            if not videos:
                result['message'] = "No se encontraron videos en la categoría"
                logger.warning(f"⚠️ {result['message']}")
                return result
            
            # Limitar número de videos
            videos_to_process = videos[:max_videos]
            logger.info(f"📋 Procesando {len(videos_to_process)} de {len(videos)} videos encontrados")
            
            # Procesar cada video
            for i, video in enumerate(videos_to_process, 1):
                try:
                    logger.info(f"🎬 Procesando video {i}/{len(videos_to_process)}: {video.get('title', 'Sin título')[:50]}...")
                    
                    # Verificar si ya existe (opcional)
                    if config.get('skip_existing', True):
                        if self._video_already_exists(video):
                            logger.info(f"⏭️ Video ya existe, saltando: {video.get('title', '')[:30]}...")
                            continue
                    
                    # Procesar video
                    process_result = self._process_single_video(video, wp_categories, config)
                    
                    if process_result['success']:
                        result['videos_processed'] += 1
                        if process_result.get('published', False):
                            result['videos_published'] += 1
                    else:
                        result['errors'].append(f"Video {i}: {process_result.get('error', 'Error desconocido')}")
                    
                    # Delay entre videos para evitar ser bloqueado
                    if i < len(videos_to_process):  # No delay después del último
                        delay_range = config.get('delay_between_videos', (1, 3))
                        delay = random.uniform(delay_range[0], delay_range[1])
                        logger.debug(f"⏳ Esperando {delay:.1f} segundos...")
                        time.sleep(delay)
                
                except Exception as e:
                    error_msg = f"Error procesando video {i}: {str(e)}"
                    result['errors'].append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    continue
            
            # Resultado final
            result['success'] = result['videos_processed'] > 0
            result['message'] = (
                f"Procesados: {result['videos_processed']} videos, "
                f"Publicados: {result['videos_published']} videos"
            )
            
            if result['errors']:
                result['message'] += f", Errores: {len(result['errors'])}"
            
            logger.info(f"✅ Scraping completado: {result['message']}")
            
        except Exception as e:
            error_msg = f"Error general en scraping automático: {str(e)}"
            result['errors'].append(error_msg)
            result['message'] = error_msg
            logger.error(f"❌ {error_msg}")
        
        finally:
            result['end_time'] = datetime.now().isoformat()
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"⏱️ Duración total: {duration:.1f} segundos")
        
        return result
    
    def _get_wordpress_categories(self) -> List[Dict]:
        """Obtiene categorías de WordPress para publicación"""
        try:
            return self.category_manager.get_categories_from_database()
        except Exception as e:
            logger.error(f"❌ Error obteniendo categorías de WordPress: {str(e)}")
            return []
    
    def _video_already_exists(self, video: Dict) -> bool:
        """Verifica si un video ya existe en WordPress"""
        try:
            # Aquí podrías implementar lógica para verificar si el video ya está publicado
            # Por ejemplo, buscar por título o URL en wp_posts
            
            # Por ahora, retorna False (no verificar duplicados)
            return False
            
        except Exception as e:
            logger.error(f"❌ Error verificando video existente: {str(e)}")
            return False
    
    def _process_single_video(self, video: Dict, wp_categories: List[Dict], config: Dict) -> Dict:
        """
        Procesa un solo video (descarga y publica)
        
        Returns:
            Dict con resultado del procesamiento
        """
        result = {
            'success': False,
            'published': False,
            'error': None,
            'post_id': None
        }
        
        try:
            # 1. Descargar video
            logger.info(f"⬇️ Descargando: {video.get('title', 'Sin título')[:30]}...")
            
            download_success = self.downloader.download_video(video.get('url'), video)
            
            if not download_success:
                result['error'] = "Error en descarga"
                return result
            
            logger.info("✅ Descarga completada")
            
            # 2. Publicar en WordPress si está habilitado
            if config.get('auto_publish', True) and wp_categories:
                logger.info("📝 Publicando en WordPress...")
                
                # Seleccionar categoría (usar la primera por defecto, o implementar lógica de selección)
                selected_category = self._select_category_for_video(video, wp_categories)
                
                if selected_category:
                    # Obtener código de StreamWish si está disponible
                    streamwish_code = self._get_streamwish_code_from_downloader()
                    
                    # Publicar
                    publish_result = self.publisher.publish_video(
                        video_data=video,
                        category_id=selected_category['id'],
                        streamwish_filecode=streamwish_code
                    )
                    
                    if publish_result['success']:
                        result['published'] = True
                        result['post_id'] = publish_result['post_id']
                        logger.info(f"✅ Publicado con ID: {publish_result['post_id']}")
                    else:
                        result['error'] = f"Error publicando: {publish_result['error']}"
                        logger.error(f"❌ Error publicando: {publish_result['error']}")
                else:
                    result['error'] = "No se pudo seleccionar categoría"
                    logger.error("❌ No se pudo seleccionar categoría para publicación")
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = f"Error procesando video: {str(e)}"
            logger.error(f"❌ {result['error']}")
        
        return result
    
    def _select_category_for_video(self, video: Dict, categories: List[Dict]) -> Optional[Dict]:
        """
        Selecciona una categoría apropiada para el video
        
        Puedes implementar lógica más sofisticada aquí, como:
        - Análisis del título del video
        - Mapeo de categorías basado en palabras clave
        - Configuración manual de categorías por defecto
        """
        try:
            # Por ahora, usar la primera categoría disponible
            # TODO: Implementar lógica más inteligente de selección
            
            if categories:
                # Buscar categorías con contenido existente
                categories_with_content = [cat for cat in categories if cat.get('count', 0) > 0]
                
                if categories_with_content:
                    # Usar la categoría con más contenido
                    selected = max(categories_with_content, key=lambda x: x.get('count', 0))
                    logger.info(f"📂 Categoría seleccionada: {selected['title']} (ID: {selected['id']})")
                    return selected
                else:
                    # Usar la primera categoría disponible
                    selected = categories[0]
                    logger.info(f"📂 Categoría por defecto: {selected['title']} (ID: {selected['id']})")
                    return selected
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error seleccionando categoría: {str(e)}")
            return None
    
    def _get_streamwish_code_from_downloader(self) -> Optional[str]:
        """Obtiene el código de StreamWish del último upload"""
        try:
            if (hasattr(self.downloader, 'streamwish_uploader') and 
                self.downloader.streamwish_uploader):
                return self.downloader.streamwish_uploader.get_last_filecode()
            return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo código StreamWish: {str(e)}")
            return None
    
    def test_category_scraping(self, category_url: str, max_videos: int = 5) -> Dict:
        """
        Prueba el scraping de una categoría sin publicar
        
        Útil para verificar que una categoría funciona antes de programarla
        """
        try:
            logger.info(f"🧪 Probando scraping de categoría: {category_url}")
            
            videos = list(self.scraper.get_videos(category_url))
            videos_sample = videos[:max_videos]
            
            result = {
                'success': True,
                'total_videos_found': len(videos),
                'sample_videos': len(videos_sample),
                'videos': []
            }
            
            for video in videos_sample:
                video_info = {
                    'title': video.get('title', 'Sin título'),
                    'url': video.get('url', ''),
                    'duration': video.get('duration', ''),
                    'views': video.get('views', ''),
                    'uploader': video.get('uploader', ''),
                    'thumbnail': video.get('thumbnail', '')
                }
                result['videos'].append(video_info)
            
            logger.info(f"✅ Test completado: {len(videos)} videos encontrados")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error en test de scraping: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'total_videos_found': 0,
                'sample_videos': 0,
                'videos': []
            }
    
    def get_category_info(self, category_url: str) -> Dict:
        """Obtiene información básica de una categoría"""
        try:
            # Hacer una solicitud rápida para verificar que la categoría existe
            import requests
            
            response = requests.get(category_url, headers=self.scraper.headers, timeout=10)
            if response.status_code == 200:
                return {
                    'accessible': True,
                    'status_code': response.status_code,
                    'content_length': len(response.content)
                }
            else:
                return {
                    'accessible': False,
                    'status_code': response.status_code,
                    'content_length': 0
                }
        except Exception as e:
            return {
                'accessible': False,
                'error': str(e),
                'status_code': 0,
                'content_length': 0
            }