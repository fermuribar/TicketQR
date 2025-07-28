# Usa una imagen base de Nginx
FROM nginx:alpine

# Copia los certificados SSL al contenedor
# Asegúrate de que la carpeta 'certs' esté en el mismo nivel que tu Dockerfile
COPY ./certs/nginx-selfsigned.crt /etc/nginx/ssl/nginx-selfsigned.crt
COPY ./certs/nginx-selfsigned.key /etc/nginx/ssl/nginx-selfsigned.key

# Copia la configuración de Nginx al contenedor
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia los archivos estáticos de la web al directorio de Nginx
COPY . /usr/share/nginx/html

# Expone el puerto 80
EXPOSE 80
EXPOSE 443

# Comando para iniciar Nginx (ya es el CMD por defecto de la imagen)
CMD ["nginx", "-g", "daemon off;"]