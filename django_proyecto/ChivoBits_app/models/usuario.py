from django.db import models
from django.shortcuts import render,redirect
from django.contrib.auth.hashers import check_password
class Usuario(models.Model):
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    email = models.EmailField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.username
    def login_view(request):
        if request.method == 'POST':
            username = request.POST.get('username')
            password = request.POST.get('password')

            try:
                usuario = Usuario.objects.get(username=username)
                if check_password(password, usuario.password):
                    request.session['username'] = usuario.username
                    request.session['password'] = usuario.password
                    return render(request, 'usuarios/login.html', {'error': 'Usuario no encontrado'})
                else:
                    return render(request, 'usuarios/login.html', {'error': 'Contraseña incorrecta'})
            except Usuario.DoesNotExist:
                return render(request, 'usuarios/login.html', {'error': 'Usuario no encontrado'})

        return render(request, 'usuarios/login.html')