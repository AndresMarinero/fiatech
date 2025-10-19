from django.shortcuts import redirect, render


def login_usuario(request):
    return render(request, 'Usuario/login.html')

def logout_view(request):
    request.session.flush()
    return redirect('login')