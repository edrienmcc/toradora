# proyecto/utils/ftp_uploader.py - ARCHIVO COMPLETO CORREGIDO (SIN post_id)
import ftplib
import os
import tempfile
import requests
import logging
import time
from datetime import datetime
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class FTPUploader:
    """Sube imágenes por FTP al servidor"""
    
    def __init__(self):
        # Configuración FTP - ACTUALIZADA PARA TU CPANEL
        self.ftp_host = "154.12.238.207"              # Tu servidor
        self.ftp_user = "arielmmc@xpleasurehub.com"   # Usuario FTP
        self.ftp_pass = "G5)QO]2I3c(u"               # Contraseña FTP
        self.ftp_port = 21                            # Puerto FTP
        
        # CORREGIDO: El usuario FTP ya inicia en /home/xpleasure/public_html/wp-content/uploads
        # Por lo tanto, cuando haces ftp.pwd() obtienes "/" pero realmente estás en wp-content/uploads
        self.remote_base_path = ""  # Vacío porque ya estamos en el directorio correcto
        
        # URL base para acceso web - CORREGIDA CON WWW
        self.web_base_url = "https://www.xpleasurehub.com/wp-content/uploads"  # CON www
        
        # Headers para descargar imágenes
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://es.pornhub.com/'
        }
    
    def upload_image_from_url(self, image_url, post_title, post_id=None):
        """
        Descarga una imagen y la sube por FTP
        
        Args:
            image_url: URL de la imagen a descargar
            post_title: Título del post para crear nombre de archivo
            post_id: ID del post (OPCIONAL - ya no se usa)
            
        Returns:
            str: URL web de la imagen subida, o None si falla
        """
        try:
            # 1. Descargar imagen
            logger.info(f"📥 Descargando imagen: {image_url}")
            print(f"📥 Descargando imagen desde: {image_url}")
            
            response = requests.get(image_url, headers=self.headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ Error descargando imagen: {response.status_code}")
                return None
            
            # 2. Determinar extensión
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = '.jpg'
            elif 'png' in content_type:
                extension = '.png'
            elif 'webp' in content_type:
                extension = '.webp'
            else:
                extension = '.jpg'  # Por defecto
            
            # 3. Crear nombre de archivo SIN post_id
            safe_filename = self._create_safe_filename(post_title, extension)
            
            # 4. Crear estructura de carpetas (año/mes)
            current_year = datetime.now().year
            current_month = datetime.now().strftime('%m')
            remote_folder = f"{current_year}/{current_month}"  # Ejemplo: "2025/05"
            
            # 5. Subir por FTP
            web_url = self._upload_to_ftp(response.content, safe_filename, remote_folder)
            
            if web_url:
                logger.info(f"✅ Imagen subida exitosamente: {web_url}")
                print(f"✅ Imagen subida a: {web_url}")
                return web_url
            else:
                logger.error("❌ Error subiendo imagen por FTP")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error en upload de imagen: {str(e)}")
            print(f"❌ Error subiendo imagen: {str(e)}")
            return None
    
    def _upload_to_ftp(self, image_data, filename, remote_folder):
        """
        Sube datos de imagen por FTP
        Usuario FTP ya inicia en: /home/xpleasure/public_html/wp-content/uploads
        """
        ftp = None
        temp_file = None
        
        try:
            # Crear archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(image_data)
            temp_file.close()
            
            # Conectar por FTP
            logger.info(f"🔗 Conectando por FTP a {self.ftp_host}...")
            print(f"🔗 Conectando FTP: {self.ftp_user}@{self.ftp_host}")
            
            ftp = ftplib.FTP()
            ftp.connect(self.ftp_host, self.ftp_port)
            ftp.login(self.ftp_user, self.ftp_pass)
            
            # Verificar directorio actual (debería ser "/" pero realmente wp-content/uploads)
            current_dir = ftp.pwd()
            logger.info(f"📁 FTP Home: {current_dir} (wp-content/uploads)")
            print(f"📁 Conectado a wp-content/uploads")
            
            # Crear estructura de carpetas si es necesaria
            upload_path = ""
            if remote_folder:
                success = self._create_ftp_directories(ftp, remote_folder)
                if success:
                    upload_path = remote_folder
                    logger.info(f"✅ Estructura creada: {remote_folder}")
                else:
                    logger.warning(f"⚠️ No se pudo crear {remote_folder}, subiendo en root")
                    ftp.cwd("/")  # Volver al root si falla
                    upload_path = ""
            
            # Subir archivo
            logger.info(f"📤 Subiendo {filename}...")
            print(f"📤 Subiendo: {filename}")
            
            with open(temp_file.name, 'rb') as f:
                result = ftp.storbinary(f'STOR {filename}', f)
                logger.info(f"📤 Resultado FTP: {result}")
            
            # Construir URL web final
            if upload_path:
                web_url = f"{self.web_base_url}/{upload_path}/{filename}"
            else:
                web_url = f"{self.web_base_url}/{filename}"
            
            # Limpiar URL (quitar dobles barras)
            web_url = web_url.replace("//", "/").replace("http:/", "http://").replace("https:/", "https://")
            
            # LÍNEAS DE DEBUG AGREGADAS:
            logger.info(f"🔗 URL base: {self.web_base_url}")
            logger.info(f"📂 Ruta upload: {upload_path}")
            logger.info(f"📄 Nombre archivo: {filename}")
            logger.info(f"🌐 URL construida: {web_url}")
            print(f"🔗 Construyendo URL:")
            print(f"   Base: {self.web_base_url}")
            print(f"   Carpeta: {upload_path}")
            print(f"   Archivo: {filename}")
            print(f"   Final: {web_url}")
            
            logger.info(f"✅ Archivo subido correctamente")
            print(f"🌐 URL final: {web_url}")
            
            # Verificar que se subió
            try:
                files = ftp.nlst()
                if filename in files:
                    logger.info(f"✅ Verificado: {filename} existe en servidor")
                    print(f"✅ Archivo confirmado en servidor")
                else:
                    logger.warning(f"⚠️ {filename} no encontrado en listado")
            except:
                logger.info("ℹ️ No se pudo verificar listado")
            
            return web_url
            
        except ftplib.all_errors as e:
            logger.error(f"❌ Error FTP: {str(e)}")
            print(f"❌ Error FTP: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error general: {str(e)}")
            print(f"❌ Error general: {str(e)}")
            return None
        finally:
            # Limpiar recursos
            if ftp:
                try:
                    ftp.quit()
                except:
                    try:
                        ftp.close()
                    except:
                        pass
            
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass

    def _create_ftp_directories(self, ftp, path):
        """
        Crea directorios en FTP si no existen
        Ya estamos en wp-content/uploads, solo crear año/mes
        """
        try:
            current_dir = ftp.pwd()
            logger.info(f"📁 Directorio base FTP: {current_dir} (realmente: wp-content/uploads)")
            
            # Dividir la ruta: "2025/05" -> ["2025", "05"]
            parts = path.strip('/').split('/')
            logger.info(f"📂 Creando estructura: {parts}")
            print(f"📂 Creando: {' -> '.join(parts)}")
            
            # Crear cada directorio paso a paso
            current_path = ""
            for part in parts:
                current_path = part if not current_path else current_path + "/" + part
                
                try:
                    # Intentar cambiar al directorio
                    ftp.cwd("/" + current_path)  # Siempre usar ruta absoluta desde root FTP
                    logger.info(f"✅ Directorio existe: {current_path}")
                    
                except ftplib.error_perm as e:
                    if "550" in str(e):
                        # El directorio no existe, crearlo
                        try:
                            # Volver al root
                            ftp.cwd("/")
                            # Crear directorio
                            ftp.mkd(current_path)
                            logger.info(f"📁 Directorio creado: {current_path}")
                            print(f"✅ Creado: {current_path}")
                            # Cambiar al directorio creado
                            ftp.cwd("/" + current_path)
                            
                        except ftplib.error_perm as create_error:
                            logger.error(f"❌ No se pudo crear {current_path}: {str(create_error)}")
                            print(f"❌ Error creando {current_path}: {str(create_error)}")
                            return False
                    else:
                        logger.error(f"❌ Error FTP: {str(e)}")
                        return False
            
            final_dir = ftp.pwd()
            logger.info(f"📍 Directorio final FTP: {final_dir}")
            print(f"📍 Ubicación final: /{path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error general creando directorios: {str(e)}")
            print(f"❌ Error general: {str(e)}")
            return False
        
    def _create_safe_filename(self, title, extension):
        """
        Crea un nombre de archivo seguro limpiando caracteres especiales (SIN post_id)
        """
        # Limpiar título: remover caracteres especiales y espacios
        safe_title = title
        
        # Remover caracteres especiales y acentos
        safe_title = re.sub(r'[áàäâ]', 'a', safe_title, flags=re.IGNORECASE)
        safe_title = re.sub(r'[éèëê]', 'e', safe_title, flags=re.IGNORECASE)
        safe_title = re.sub(r'[íìïî]', 'i', safe_title, flags=re.IGNORECASE)
        safe_title = re.sub(r'[óòöô]', 'o', safe_title, flags=re.IGNORECASE)
        safe_title = re.sub(r'[úùüû]', 'u', safe_title, flags=re.IGNORECASE)
        safe_title = re.sub(r'[ñ]', 'n', safe_title, flags=re.IGNORECASE)
        
        # Remover caracteres especiales, mantener solo letras, números, espacios y guiones
        safe_title = re.sub(r'[^\w\s-]', '', safe_title)
        
        # Convertir espacios múltiples a uno solo
        safe_title = re.sub(r'\s+', ' ', safe_title)
        
        # Convertir espacios a guiones
        safe_title = safe_title.replace(' ', '-')
        
        # Remover guiones múltiples
        safe_title = re.sub(r'-+', '-', safe_title)
        
        # Convertir a minúsculas
        safe_title = safe_title.lower()
        
        # Remover guiones al inicio y final
        safe_title = safe_title.strip('-')
        
        # Limitar longitud a 80 caracteres para permitir títulos más largos
        if len(safe_title) > 80:
            safe_title = safe_title[:80].rstrip('-')
        
        # Crear nombre final SIN post_id
        if safe_title:
            filename = f"{safe_title}{extension}"           # ✅ SIN post_id
        else:
            filename = f"video{extension}"                  # ✅ SIN post_id
        
        logger.info(f"📄 Nombre original: {title}")
        logger.info(f"📄 Nombre limpio: {safe_title}")
        logger.info(f"📄 Archivo final: {filename}")
        print(f"📄 Archivo: {filename}")
        
        return filename
    
    def test_connection(self):
        """
        Prueba la conexión FTP
        """
        try:
            logger.info(f"🧪 Probando conexión FTP a {self.ftp_host}...")
            print(f"🧪 Test FTP: {self.ftp_user}@{self.ftp_host}")
            
            ftp = ftplib.FTP()
            ftp.connect(self.ftp_host, self.ftp_port)
            ftp.login(self.ftp_user, self.ftp_pass)
            
            # Ver directorio actual
            current_dir = ftp.pwd()
            print(f"📁 Directorio base: {current_dir}")
            
            # Listar contenido
            try:
                files = ftp.nlst()
                logger.info(f"✅ Conexión FTP exitosa. Archivos/carpetas: {len(files)}")
                print(f"✅ FTP OK. Contenido: {files[:5]}")  # Mostrar primeros 5
            except:
                logger.info("✅ Conexión FTP exitosa (directorio vacío)")
                print("✅ FTP OK (directorio vacío)")
            
            ftp.quit()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test FTP: {str(e)}")
            print(f"❌ Test FTP falló: {str(e)}")
            return False

    def diagnose_ftp_connection(self):
        """
        Diagnóstica la conexión FTP y estructura de directorios
        """
        try:
            print("\n" + "="*60)
            print("🔍 DIAGNÓSTICO DE CONEXIÓN FTP")
            print("="*60)
            
            print(f"🖥️  Host: {self.ftp_host}")
            print(f"👤 Usuario: {self.ftp_user}")
            print(f"🔢 Puerto: {self.ftp_port}")
            print(f"🌐 URL base: {self.web_base_url}")
            
            # Conectar
            ftp = ftplib.FTP()
            ftp.connect(self.ftp_host, self.ftp_port)
            ftp.login(self.ftp_user, self.ftp_pass)
            
            # Información básica
            print(f"✅ Conexión exitosa")
            print(f"📁 Directorio actual: {ftp.pwd()}")
            print(f"📁 Directorio real: /home/xpleasure/public_html/wp-content/uploads")
            
            # Listar contenido
            try:
                files = ftp.nlst()
                print(f"📋 Archivos/carpetas encontradas: {len(files)}")
                for i, file in enumerate(files[:10]):  # Mostrar primeros 10
                    print(f"   {i+1}. {file}")
                if len(files) > 10:
                    print(f"   ... y {len(files) - 10} más")
            except Exception as e:
                print(f"⚠️ No se pudo listar contenido: {str(e)}")
            
            # Probar crear directorio de prueba
            test_dir = "test_upload_" + str(int(time.time()))
            try:
                ftp.mkd(test_dir)
                print(f"✅ Permisos de escritura: OK (creado {test_dir})")
                ftp.rmd(test_dir)
                print(f"✅ Permisos de eliminación: OK (eliminado {test_dir})")
            except Exception as e:
                print(f"❌ Error de permisos: {str(e)}")
            
            # Probar crear estructura año/mes
            current_year = datetime.now().year
            current_month = datetime.now().strftime('%m')
            test_structure = f"{current_year}/{current_month}"
            
            print(f"\n🗂️ Probando estructura: {test_structure}")
            success = self._create_ftp_directories(ftp, test_structure)
            if success:
                print(f"✅ Estructura {test_structure} creada/verificada correctamente")
            else:
                print(f"❌ Error creando estructura {test_structure}")
            
            ftp.quit()
            print("✅ Diagnóstico completado")
            return True
            
        except Exception as e:
            print(f"❌ Error en diagnóstico: {str(e)}")
            return False