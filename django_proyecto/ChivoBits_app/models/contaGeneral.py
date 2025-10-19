from django.db import models
from .usuario import Usuario

class Cuenta(models.Model):
    TIPOS_CUENTA = [
        ('ACTIVO', 'Activo'),
        ('PASIVO', 'Pasivo'),
        ('PATRIMONIO', 'Patrimonio'),
        ('INGRESO', 'Ingreso'),
        ('GASTO', 'Gasto'),
    ]
    
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=15, choices=TIPOS_CUENTA)
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

class CentroCosto(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

class Transaccion(models.Model):
    fecha = models.DateField()
    cuenta = models.ForeignKey(Cuenta, on_delete=models.RESTRICT)
    centro_costo = models.ForeignKey(CentroCosto, on_delete=models.RESTRICT, null=True, blank=True)
    debe = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    haber = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    descripcion = models.TextField()
    es_ajuste = models.BooleanField(default=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.fecha} - {self.descripcion[:30]}"
    
    class Meta:
        ordering = ['-fecha', '-id']