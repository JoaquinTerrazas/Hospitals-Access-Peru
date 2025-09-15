# Hospitals-Access-Peru.

## Proceso de Filtrado de Hospitales

###  Paso 1: Carga del dataset
- Se cargó el archivo IPRESS completo del MINSA.  
- Se detectó automáticamente la **codificación** para manejar correctamente los caracteres especiales.

###  Paso 2: Filtrado por estado operativo
Se seleccionaron únicamente los hospitales que cumplen con ambas condiciones:  
- `Estado = "ACTIVADO"` → Establecimientos registrados y reconocidos oficialmente.  
- `Condición = "EN FUNCIONAMIENTO"` → Hospitales que están operando actualmente.  

###  Paso 3: Validación de coordenadas
- Se eliminaron los registros sin **coordenadas geográficas válidas** en las columnas `NORTE` y `ESTE`.  
- Esto garantiza la posibilidad de realizar un análisis espacial confiable.  

###  Paso 4: Selección de columnas relevantes
Se conservaron únicamente las columnas necesarias y se renombraron para mayor claridad.  
