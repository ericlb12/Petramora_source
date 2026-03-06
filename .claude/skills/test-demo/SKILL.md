---
name: test-demo
description: Ejecuta los tests demo del agente segmentador contra Supabase y Gemini reales y analiza los resultados
allowed-tools: Bash, Read
---

Ejecuta los tests demo del agente segmentador y analiza los resultados.

## Comando

```bash
cd Agente_segmentador && python tests/test_demo.py $ARGUMENTS
```

## Comportamiento

1. Ejecuta los tests con output verbose (-v -s)
2. Los tests son de integración real (Supabase + Gemini), pueden tardar ~50s
3. Después de la ejecución, analiza el output completo:
   - **Resumen**: tests pasados / fallidos / total
   - **Calidad de respuestas**: revisar si las respuestas del agente son coherentes, factuales y bien formateadas (tablas markdown correctas, datos numéricos razonables)
   - **Recomendaciones**: en tests de `get_recommendation`, verificar que los productos recomendados tienen notas correctas ("Producto más comprado", "Mayor margen", "Dcto habitual X%", "Recomendado del catálogo"), que los descuentos mostrados son de mercado (no del cliente), y que la estrategia corresponde al segmento
   - **Errores o warnings**: destacar cualquier anomalía en los datos (márgenes negativos, descuentos >50%, productos sin descripción, etc.)
   - **Si hay fallos**: analizar la causa raíz y sugerir correcciones concretas
4. Presenta el análisis en formato conciso al usuario
