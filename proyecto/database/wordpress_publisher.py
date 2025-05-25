# proyecto/database/wordpress_publisher.py - ARCHIVO COMPLETO
import mysql.connector
from mysql.connector import Error
import logging
import requests
from datetime import datetime
import re
import os
import tempfile
from .config import DatabaseConfig

logger = logging.getLogger(__name__)

class WordPressPublisher:
    """Publica videos en WordPress con estructura AMVG"""
    
    def __init__(self):
        self.db_config = DatabaseConfig()
    
    def publish_video(self, video_data, category_id, streamwish_filecode=None):
        self.current_video_data = video_data  # Para acceso desde _set_featured_image

        """
        Publica un video en WordPress
        
        Args:
            video_data: Datos del video (título, descripción, etc.)
            category_id: ID de la categoría seleccionada
            streamwish_filecode: Código del archivo en StreamWish
            
        Returns:
            dict: Resultado de la publicación
        """
        connection = None
        
        try:
            connection = self.db_config.get_connection()
            if not connection:
                return {'success': False, 'error': 'No se pudo conectar a la base de datos'}
            
            cursor = connection.cursor()
            
            # 1. Crear el post principal
            post_id = self._create_post(cursor, video_data)
            if not post_id:
                return {'success': False, 'error': 'Error creando el post'}
            
            # 2. Añadir metadatos del video
            self._add_video_metadata(cursor, post_id, video_data, streamwish_filecode)
            
            # 3. Asignar categoría
            self._assign_category(cursor, post_id, category_id)
            
            # 4. Establecer imagen destacada desde FTP
            attachment_id = None
            if video_data.get('ftp_image_url') or video_data.get('twitter_image') or video_data.get('thumbnail'):
                attachment_id = self._set_featured_image(cursor, post_id, 
                    video_data.get('thumbnail', ''), video_data['title'])
            
            # 5. Establecer formato de post como video
            self._set_post_format(cursor, post_id, 'video')
            
            connection.commit()
            
            logger.info(f"✅ Video publicado exitosamente: ID {post_id}")
            return {
                'success': True, 
                'post_id': post_id,
                'attachment_id': attachment_id,
                'message': f'Video publicado con ID: {post_id}'
            }
            
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"❌ Error publicando video: {str(e)}")
            return {'success': False, 'error': str(e)}
            
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def _create_post(self, cursor, video_data):
        """Crea el post principal en wp_posts"""
        try:
            # Limpiar título y contenido
            title = self._clean_text(video_data.get('title', 'Video sin título'))
            content = self._clean_text(video_data.get('description', ''))
            
            # Crear slug desde el título
            slug = self._create_slug(title)
            
            # Datos del post
            post_data = {
                'post_author': 1,
                'post_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_date_gmt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_content': content,
                'post_title': title,
                'post_excerpt': content[:150] + '...' if len(content) > 150 else content,
                'post_status': 'publish',
                'comment_status': 'open',
                'ping_status': 'open',
                'post_password': '',
                'post_name': slug,
                'to_ping': '',
                'pinged': '',
                'post_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_modified_gmt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_content_filtered': '',
                'post_parent': 0,
                'guid': '',
                'menu_order': 0,
                'post_type': 'post',
                'post_mime_type': '',
                'comment_count': 0
            }
            
            # Insertar post
            insert_query = """
                INSERT INTO FNfxR_posts (
                    post_author, post_date, post_date_gmt, post_content, post_title,
                    post_excerpt, post_status, comment_status, ping_status, post_password,
                    post_name, to_ping, pinged, post_modified, post_modified_gmt,
                    post_content_filtered, post_parent, guid, menu_order, post_type,
                    post_mime_type, comment_count
                ) VALUES (
                    %(post_author)s, %(post_date)s, %(post_date_gmt)s, %(post_content)s, %(post_title)s,
                    %(post_excerpt)s, %(post_status)s, %(comment_status)s, %(ping_status)s, %(post_password)s,
                    %(post_name)s, %(to_ping)s, %(pinged)s, %(post_modified)s, %(post_modified_gmt)s,
                    %(post_content_filtered)s, %(post_parent)s, %(guid)s, %(menu_order)s, %(post_type)s,
                    %(post_mime_type)s, %(comment_count)s
                )
            """
            
            cursor.execute(insert_query, post_data)
            post_id = cursor.lastrowid
            
            # Actualizar GUID
            guid = f"https://omeplay.com/?p={post_id}"
            cursor.execute("UPDATE FNfxR_posts SET guid = %s WHERE ID = %s", (guid, post_id))
            
            logger.info(f"📝 Post creado con ID: {post_id}")
            print(f"✅ Post creado: ID {post_id}, Título: {title}")
            return post_id
            
        except Exception as e:
            logger.error(f"❌ Error creando post: {str(e)}")
            return None
    
    def _add_video_metadata(self, cursor, post_id, video_data, streamwish_filecode):
        """Añade metadatos del video"""
        try:
            metadata = []
            
            # Metadatos básicos del video
            if video_data.get('duration'):
                metadata.append(('duration', video_data['duration']))
            
            if video_data.get('views'):
                metadata.append(('views', video_data['views']))
                
            if video_data.get('rating'):
                metadata.append(('rating', video_data['rating']))
                
            if video_data.get('uploader'):
                metadata.append(('uploader', video_data['uploader']))
            
            # URL original del video
            if video_data.get('url'):
                metadata.append(('original_url', video_data['url']))
            
            # Miniatura original
            if video_data.get('thumbnail'):
                metadata.append(('thumb_original', video_data['thumbnail']))
            
            # StreamWish embed personalizado
            if streamwish_filecode:
                # Limpiar el código si viene con URL completa
                clean_code = self._extract_streamwish_id(streamwish_filecode)
                
                if clean_code:
                    # Tu URL personalizada de embed
                    embed_url = f"https://omeplay.com/embed2/?host=streamwish&id={clean_code}&ahost=streamwish&aid={clean_code}"
                    
                    # Crear iframe completo como en tu ejemplo
                    iframe_embed = (
                        f'<iframe title="" '
                        f'src="{embed_url}" '
                        f'width="640" height="320" '
                        f'loading="lazy" '
                        f'allow="fullscreen; accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; geolocation; web-share; screen-wake-lock; idle-detection">'
                        f'</iframe>'
                    )
                    
                    # Guardar el iframe completo
                    metadata.append(('embed', iframe_embed))
                    metadata.append(('streamwish_code', clean_code))
                    metadata.append(('streamwish_embed_url', embed_url))
                    
                    logger.info(f"🎥 Iframe embed creado: {embed_url}")
                    print(f"✅ Iframe guardado con URL: {embed_url}")
                else:
                    logger.warning(f"⚠️ No se pudo extraer ID de: {streamwish_filecode}")
                    # Si no hay StreamWish válido, guardar iframe placeholder
                    placeholder_iframe = (
                        f'<iframe title="" '
                        f'src="about:blank" '
                        f'width="640" height="320" '
                        f'loading="lazy">'
                        f'</iframe>'
                    )
                    metadata.append(('embed', placeholder_iframe))
            else:
                # Sin StreamWish, guardar iframe placeholder
                placeholder_iframe = (
                    f'<iframe title="" '
                    f'src="about:blank" '
                    f'width="640" height="320" '
                    f'loading="lazy">'
                    f'</iframe>'
                )
                metadata.append(('embed', placeholder_iframe))
                logger.info("📺 Iframe placeholder creado (sin StreamWish)")
            
            # Partner info (para compatibilidad con AMVG)
            metadata.append(('partner', 'pornhub'))
            metadata.append(('partner_cat', 'imported'))
            metadata.append(('video_id', video_data.get('id', post_id)))
            
            # Insertar todos los metadatos
            for meta_key, meta_value in metadata:
                if meta_value:
                    cursor.execute(
                        "INSERT INTO FNfxR_postmeta (post_id, meta_key, meta_value) VALUES (%s, %s, %s)",
                        (post_id, meta_key, str(meta_value))
                    )
            
            logger.info(f"📋 Metadatos añadidos: {len(metadata)} campos")
            print(f"✅ Metadatos guardados: {len(metadata)} campos")
            
        except Exception as e:
            logger.error(f"❌ Error añadiendo metadatos: {str(e)}")
    
    def _assign_category(self, cursor, post_id, category_id):
        """Asigna el post a una categoría"""
        try:
            # Verificar que la categoría existe
            cursor.execute(
                "SELECT term_taxonomy_id FROM FNfxR_term_taxonomy WHERE term_id = %s AND taxonomy = 'category'",
                (category_id,)
            )
            
            result = cursor.fetchone()
            if not result:
                logger.error(f"❌ Categoría {category_id} no encontrada")
                return False
            
            term_taxonomy_id = result[0]
            
            # Insertar relación post-categoría
            cursor.execute(
                "INSERT INTO FNfxR_term_relationships (object_id, term_taxonomy_id) VALUES (%s, %s)",
                (post_id, term_taxonomy_id)
            )
            
            # Actualizar contador de la categoría
            cursor.execute(
                "UPDATE FNfxR_term_taxonomy SET count = count + 1 WHERE term_taxonomy_id = %s",
                (term_taxonomy_id,)
            )
            
            logger.info(f"📂 Post asignado a categoría: {category_id}")
            print(f"✅ Categoría asignada: ID {category_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error asignando categoría: {str(e)}")
            return False
    
    def _set_featured_image(self, cursor, post_id, image_url, title):
        """Crea attachment y establece imagen destacada desde URL FTP"""
        try:
            # PRIORIZAR imagen FTP si está disponible
            ftp_image_url = None
            
            # Verificar si tenemos imagen FTP en video_data
            if hasattr(self, 'current_video_data') and self.current_video_data.get('ftp_image_url'):
                ftp_image_url = self.current_video_data['ftp_image_url']
                logger.info(f"🎯 Usando imagen FTP existente: {ftp_image_url}")
                print(f"🎯 Usando imagen FTP: {ftp_image_url}")
            else:
                # Si no hay imagen FTP, usar FTP uploader para subirla
                from utils.ftp_uploader import FTPUploader
                
                # Usar imagen de Twitter si existe, sino la original
                source_image_url = image_url
                if hasattr(self, 'current_video_data') and self.current_video_data.get('twitter_image'):
                    source_image_url = self.current_video_data['twitter_image']
                    logger.info(f"🎯 Usando imagen de Twitter: {source_image_url}")
                    print(f"🎯 Usando imagen Twitter: {source_image_url}")
                
                # Subir por FTP
                if source_image_url:
                    ftp_uploader = FTPUploader()
                    ftp_image_url = ftp_uploader.upload_image_from_url(source_image_url, title)
                    
                    if ftp_image_url:
                        logger.info(f"✅ Imagen subida por FTP: {ftp_image_url}")
                        print(f"✅ Imagen FTP creada: {ftp_image_url}")
                    else:
                        logger.warning("⚠️ No se pudo subir imagen por FTP")
                        print("⚠️ Error subiendo imagen por FTP")
            
            if not ftp_image_url:
                logger.error("❌ No hay imagen FTP disponible")
                return None
            
            # Crear attachment en WordPress con la URL FTP
            attachment_id = self._create_attachment_from_ftp_url(cursor, post_id, ftp_image_url, title)
            
            if attachment_id:
                # INSERTAR URL en thumb (metadato del post)
                cursor.execute(
                    "INSERT INTO FNfxR_postmeta (post_id, meta_key, meta_value) VALUES (%s, %s, %s)",
                    (post_id, 'thumb', ftp_image_url)
                )
                
                # INSERTAR thumb_id (ID del attachment)
                cursor.execute(
                    "INSERT INTO FNfxR_postmeta (post_id, meta_key, meta_value) VALUES (%s, %s, %s)",
                    (post_id, 'thumb_id', attachment_id)
                )
                
                # INSERTAR como imagen destacada de WordPress
                cursor.execute(
                    "INSERT INTO FNfxR_postmeta (post_id, meta_key, meta_value) VALUES (%s, %s, %s)",
                    (post_id, '_thumbnail_id', attachment_id)
                )
                
                logger.info(f"🖼️ Imagen destacada establecida: {attachment_id}")
                logger.info(f"🌐 URL guardada en BD: {ftp_image_url}")
                print(f"✅ Imagen en BD: ID {attachment_id}, URL: {ftp_image_url}")
                
                return attachment_id
            else:
                logger.error("❌ No se pudo crear attachment")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error estableciendo imagen destacada: {str(e)}")
            print(f"❌ Error con imagen: {str(e)}")
            return None

    def _create_attachment_from_ftp_url(self, cursor, post_id, ftp_url, title):
        """
        Crea un attachment en WordPress desde una URL FTP
        """
        try:
            current_year = datetime.now().year
            current_month = datetime.now().strftime('%m')
            
            # Determinar extensión desde la URL
            if '.jpg' in ftp_url.lower() or 'jpeg' in ftp_url.lower():
                extension = '.jpg'
                content_type = 'image/jpeg'
            elif '.png' in ftp_url.lower():
                extension = '.png'
                content_type = 'image/png'
            elif '.webp' in ftp_url.lower():
                extension = '.webp'
                content_type = 'image/webp'
            else:
                extension = '.jpg'
                content_type = 'image/jpeg'
            
            # Crear nombre de archivo relativo para WordPress
            # La URL es: https://www.xpleasurehub.com/wp-content/uploads/2025/05/titulo-limpio.jpg
            # Extraer la parte después de wp-content/uploads/
            if '/wp-content/uploads/' in ftp_url:
                relative_filename = ftp_url.split('/wp-content/uploads/')[1]
            else:
                # Fallback: crear estructura estándar
                safe_title = self._create_slug(title)
                relative_filename = f"{current_year}/{current_month}/{safe_title}{extension}"
            
            # Insertar en wp_posts como attachment
            attachment_data = {
                'post_author': 1,
                'post_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_date_gmt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_content': '',
                'post_title': f"Miniatura: {title}",
                'post_excerpt': '',
                'post_status': 'inherit',
                'comment_status': 'open',
                'ping_status': 'closed',
                'post_password': '',
                'post_name': self._create_slug(title) + '-miniatura',
                'to_ping': '',
                'pinged': '',
                'post_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_modified_gmt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'post_content_filtered': '',
                'post_parent': post_id,
                'guid': ftp_url,  # Usar la URL FTP completa
                'menu_order': 0,
                'post_type': 'attachment',
                'post_mime_type': content_type,
                'comment_count': 0
            }
            
            attachment_query = """
                INSERT INTO FNfxR_posts (
                    post_author, post_date, post_date_gmt, post_content, post_title,
                    post_excerpt, post_status, comment_status, ping_status, post_password,
                    post_name, to_ping, pinged, post_modified, post_modified_gmt,
                    post_content_filtered, post_parent, guid, menu_order, post_type,
                    post_mime_type, comment_count
                ) VALUES (
                    %(post_author)s, %(post_date)s, %(post_date_gmt)s, %(post_content)s, %(post_title)s,
                    %(post_excerpt)s, %(post_status)s, %(comment_status)s, %(ping_status)s, %(post_password)s,
                    %(post_name)s, %(to_ping)s, %(pinged)s, %(post_modified)s, %(post_modified_gmt)s,
                    %(post_content_filtered)s, %(post_parent)s, %(guid)s, %(menu_order)s, %(post_type)s,
                    %(post_mime_type)s, %(comment_count)s
                )
            """
            
            cursor.execute(attachment_query, attachment_data)
            attachment_id = cursor.lastrowid
            
            # Añadir metadatos del attachment
            cursor.execute(
                "INSERT INTO FNfxR_postmeta (post_id, meta_key, meta_value) VALUES (%s, %s, %s)",
                (attachment_id, '_wp_attached_file', relative_filename)
            )
            
            # Agregar metadatos adicionales del attachment
            cursor.execute(
                "INSERT INTO FNfxR_postmeta (post_id, meta_key, meta_value) VALUES (%s, %s, %s)",
                (attachment_id, '_wp_attachment_metadata', 'a:0:{}')  # Metadata vacío
            )
            
            logger.info(f"📎 Attachment creado: ID {attachment_id}")
            logger.info(f"📁 Archivo relativo: {relative_filename}")
            print(f"📎 Attachment: ID {attachment_id}")
            
            return attachment_id
            
        except Exception as e:
            logger.error(f"❌ Error creando attachment: {str(e)}")
            print(f"❌ Error creando attachment: {str(e)}")
            return None
        
    def _set_post_format(self, cursor, post_id, format_type):
        """Establece el formato del post"""
        try:
            # Buscar el término del formato
            cursor.execute(
                "SELECT tt.term_taxonomy_id FROM FNfxR_terms t "
                "INNER JOIN FNfxR_term_taxonomy tt ON t.term_id = tt.term_id "
                "WHERE t.slug = %s AND tt.taxonomy = 'post_format'",
                (f"post-format-{format_type}",)
            )
            
            result = cursor.fetchone()
            if not result:
                # Crear el término si no existe
                cursor.execute(
                    "INSERT INTO FNfxR_terms (name, slug, term_group) VALUES (%s, %s, %s)",
                    (format_type.title(), f"post-format-{format_type}", 0)
                )
                term_id = cursor.lastrowid
                
                # Crear taxonomía
                cursor.execute(
                    "INSERT INTO FNfxR_term_taxonomy (term_id, taxonomy, description, parent, count) VALUES (%s, %s, %s, %s, %s)",
                    (term_id, 'post_format', '', 0, 0)
                )
                taxonomy_id = cursor.lastrowid
            else:
                taxonomy_id = result[0]
            
            if taxonomy_id:
                # Asignar formato al post
                cursor.execute(
                    "INSERT INTO FNfxR_term_relationships (object_id, term_taxonomy_id) VALUES (%s, %s)",
                    (post_id, taxonomy_id)
                )
                
                # Actualizar contador
                cursor.execute(
                    "UPDATE FNfxR_term_taxonomy SET count = count + 1 WHERE term_taxonomy_id = %s",
                    (taxonomy_id,)
                )
            
            logger.info(f"🎬 Formato de post establecido: {format_type}")
            print(f"✅ Formato de post: {format_type}")
            
        except Exception as e:
            logger.error(f"❌ Error estableciendo formato de post: {str(e)}")
    
    def _extract_streamwish_id(self, input_data):
        """
        Extrae el ID de StreamWish de diferentes formatos
        
        Ejemplos:
        - "qoueyklh8ch1" -> "qoueyklh8ch1"
        - "https://dhcplay.com/qoueyklh8ch1" -> "qoueyklh8ch1"
        - "https://streamwish.to/qoueyklh8ch1" -> "qoueyklh8ch1"
        """
        try:
            if not input_data:
                return None
            
            input_str = str(input_data).strip()
            
            # Si contiene "http", es una URL - extraer el ID
            if 'http' in input_str:
                # Ejemplos: 
                # https://dhcplay.com/qoueyklh8ch1
                # https://streamwish.to/qoueyklh8ch1
                
                # Obtener la parte después del último '/'
                parts = input_str.split('/')
                if len(parts) > 0:
                    potential_id = parts[-1]
                    
                    # Remover extensiones (.html, .php, etc)
                    potential_id = potential_id.split('.')[0]
                    
                    # Verificar que sea un ID válido
                    if potential_id and len(potential_id) >= 8 and potential_id.replace('_', '').replace('-', '').isalnum():
                        logger.info(f"🔍 ID extraído de URL: {potential_id}")
                        print(f"✅ StreamWish ID extraído: {potential_id}")
                        return potential_id
            else:
                # Ya es el ID directo
                if input_str and len(input_str) >= 8:
                    logger.info(f"🔍 ID directo recibido: {input_str}")
                    print(f"✅ StreamWish ID directo: {input_str}")
                    return input_str
            
            logger.warning(f"⚠️ No se pudo extraer ID válido de: {input_str}")
            print(f"⚠️ No se pudo extraer StreamWish ID de: {input_str}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo ID: {str(e)}")
            return None
    
    def _clean_text(self, text):
        """Limpia texto para inserción en BD"""
        if not text:
            return ""
        
        # Remover caracteres problemáticos
        text = str(text).strip()
        text = re.sub(r'[<>"\']', '', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text[:500]  # Limitar longitud
    
    def _create_slug(self, title):
        """Crea un slug válido desde el título"""
        if not title:
            return f"video-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Convertir a minúsculas y remover caracteres especiales
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        
        # Limitar longitud
        if len(slug) > 100:
            slug = slug[:100].rstrip('-')
        
        return slug or f"video-{datetime.now().strftime('%Y%m%d%H%M%S')}"