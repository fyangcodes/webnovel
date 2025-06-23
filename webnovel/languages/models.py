from django.db import models

# Create your models here.

class Language(models.Model):
    code = models.CharField(max_length=10, unique=True)  # e.g., 'en'
    name = models.CharField(max_length=50)               # e.g., 'English'

    def __str__(self):
        return self.name
