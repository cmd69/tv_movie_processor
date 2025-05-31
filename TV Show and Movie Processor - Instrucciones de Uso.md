# TV Show and Movie Processor - Instrucciones de Uso

## Requisitos

- Docker y Docker Compose instalados
- Acceso a la ruta `/mnt/nfs/media` (se creará automáticamente si no existe)

## Despliegue con Docker Compose

1. Clona o descarga este repositorio
2. Navega al directorio del proyecto
3. Ejecuta el siguiente comando para iniciar la aplicación:

```bash
docker-compose up -d
```

4. Accede a la aplicación web en tu navegador:

```
http://localhost:5000
```

## Estructura de Volúmenes

La aplicación está configurada para trabajar exclusivamente con archivos dentro de `/mnt/nfs/media`. Este directorio se monta como un volumen en el contenedor Docker, permitiendo que la aplicación acceda a tus archivos multimedia.

Si necesitas cambiar la ubicación de tus archivos multimedia, modifica el archivo `docker-compose.yml` y actualiza el mapeo de volumen:

```yaml
volumes:
  - /tu/ruta/de/medios:/mnt/nfs/media
```

## Características Principales

1. **Navegación Restringida**: Solo se puede acceder a archivos dentro de `/mnt/nfs/media`
2. **Matcheo Automático Mejorado**: Emparejamiento inteligente entre versiones originales y dobladas
3. **Modo Película**: Procesamiento 1 a 1 de archivos individuales
4. **Modo Serie TV**: Procesamiento por lotes de múltiples episodios
5. **Seguimiento de Trabajos**: Monitoreo en tiempo real del progreso

## Solución de Problemas

- **Error de permisos**: Asegúrate de que el usuario que ejecuta Docker tiene permisos de lectura/escritura en `/mnt/nfs/media`
- **Directorio no encontrado**: El directorio se creará automáticamente, pero necesitarás permisos para ello
- **Problemas de red**: Verifica que el puerto 5000 no esté siendo utilizado por otra aplicación

## Detener la Aplicación

Para detener la aplicación, ejecuta:

```bash
docker-compose down
```
