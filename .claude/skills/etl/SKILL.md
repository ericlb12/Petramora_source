---
name: etl
description: Ejecuta el ETL de Petramora para cargar datos de Power BI a Supabase
disable-model-invocation: true
allowed-tools: Bash
argument-hint: [--segmentacion | --lineas | --catalogo]
---

Ejecuta el ETL de Petramora. Argumentos recibidos: $ARGUMENTS

## Comando

```bash
cd ETL-Segmentador-Petramora && python etl_segmentador.py $ARGUMENTS
```

## Opciones disponibles

- Sin argumentos: ejecuta los 3 procesos (segmentacion, lineas, catalogo)
- `--segmentacion`: solo RFM (tabla `segmentacion_clientes_raw`)
- `--lineas`: solo lineas cliente-producto (tabla `lineas_cliente_producto`)
- `--catalogo`: solo catalogo de productos (tabla `catalogo_productos`)
- Se pueden combinar: `--lineas --catalogo`

## Comportamiento

1. Ejecuta el comando con los argumentos proporcionados
2. Muestra el output completo al usuario
3. Si hay errores, resaltalos claramente
4. Reporta el resumen final (registros procesados, errores)
