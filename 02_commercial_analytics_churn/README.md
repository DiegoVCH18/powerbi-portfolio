# 🏪 Minimarket Aurelion – README PRO

Proyecto de análisis de ventas minoristas con pipeline de simulación, limpieza, EDA y generación automática de reportes.

- Autor: Diego Armando Vásquez Chávez  
- Curso: Fundamentos en IA – IBM & Guayerd  
- Versión: 2.1 (1 nov 2025)

---

## 📘 Introducción

El objetivo del proyecto es identificar productos estrella, estacionalidad y segmentación ABC de clientes y artículos. El pipeline integra, limpia y analiza datos provenientes de archivos (Excel/CSV/JSON), y exporta métricas, visualizaciones y resúmenes ejecutivos.

Puntos destacados:
- Distribución de medios de pago preservada por muestreo estratificado en la simulación.
- Limpieza con validaciones de integridad (claves, FKs, fechas, precios) y derivación de reglas de negocio (canal por medio de pago).
- EDA con KPIs (ticket promedio, top 5, correlaciones) y clasificación ABC (productos y clientes).
- Logging estructurado (JSONL) y métricas de ejecución por etapa.

---

## 🏗️ Arquitectura

Componentes principales del repo:

- Notebooks
   - `4. simulador_datos_comerciales.ipynb` → Genera datasets simulados.
   - `7. Limpieza_datos.ipynb` → Integra y limpia datos; exporta `*_clean.xlsx`.
   - `8. EDA_Aurelion.ipynb` → EDA y visualizaciones; genera CSV y PNG.
- Scripts
   - `2. programa.py` → Orquestador del pipeline (limpieza, KPIs, export, logs y métricas).
   - `regenerar_pipeline.py` → Verificación rápida y ejecución no interactiva del flujo.
- Paquete utilitario `aurelion/`
   - `pipeline_utils.py` → Config/rutas, lectura autodetectada (Excel/CSV/JSON), validaciones, limpieza, integración y métricas.
   - `logging_utils.py` → Logging estructurado (consola, errors.log.jsonl, metrics.log.jsonl).
   - `visualization_utils.py` → `generar_visualizacion()` (histograma/boxplot/heatmap/pareto).
   - `eda_analyzer.py` → Clase `EDAAnalyzer` (KPIs, outliers, ABC, reportes CSV).
- Datos y salidas
   - `datasets/` y `datasets_limpios/`
   - `export/` (CSV/JSON/txt), `visualizaciones_EDA/` (PNG), `logs/` (JSONL) y `docs/` (Markdown).
- Configuración
   - `5. config.json` → Rutas, parámetros y umbrales de validación.

---

## ▶️ Ejecución

Requisitos: Python 3.10+ y paquetes: pandas, numpy, matplotlib, seaborn, openpyxl.

- Flujo recomendado (terminal de VS Code o Codespaces – PowerShell):

```powershell
# 1) (Opcional) Generar datos simulados
python "4. simulador_datos_comerciales.py"

# 2) Ejecutar el pipeline (menú interactivo)
python "2. programa.py"

# 3) (Alternativa no interactiva)
python regenerar_pipeline.py

# 4) EDA manual
# Abrir y ejecutar: 8. EDA_Aurelion.ipynb
```

Notas:
- Rutas de archivos en `5. config.json`. La lectura autodetecta formato por extensión (xlsx/csv/json).
- Los resultados quedan en `export/`, imágenes en `visualizaciones_EDA/` y logs en `logs/`.

---

## 📊 Resultados

- Exportaciones (ejemplos):
   - `export/distribucion_medio_pago_ventas.csv`
   - `export/top5_productos.csv`
   - `export/correlaciones.csv`
   - `export/clasificacion_abc_productos.csv`, `export/clasificacion_abc_clientes.csv`
   - `export/outliers_detectados.csv`, `export/outliers_importe_total_iqr.csv`
   - `docs/resumen_mensual.md` (si se genera desde el pipeline)
- Visualizaciones: `visualizaciones_EDA/*.png` (barras, heatmap, Pareto, etc.).
- Logs y métricas:
   - `logs/aurelion_pipeline_*.log.jsonl` (eventos del pipeline)
   - `logs/errors.log.jsonl` (errores críticos)
   - `logs/metrics.log.jsonl` (tiempos por etapa y resumen final)

---

## 🚀 Próximos pasos

- Procesamiento por chunks (streaming) end-to-end para CSV/NDJSON grandes.
- Test suite (smoke + unitarios) para utils clave (validaciones y lectura autodetectada).
- Dashboards interactivos (Streamlit/Plotly) con KPIs y filtros.
- Validaciones extendidas: reglas por categoría de producto y umbrales diferenciales.

---

## 🔗 Enlaces rápidos (notebooks y scripts)

- Simulación de datos: [`4. simulador_datos_comerciales.ipynb`](./4.%20simulador_datos_comerciales.ipynb)  
- Limpieza de datos: [`7. Limpieza_datos.ipynb`](./7.%20Limpieza_datos.ipynb)  
- EDA: [`8. EDA_Aurelion.ipynb`](./8.%20EDA_Aurelion.ipynb)  
- Pipeline principal: [`2. programa.py`](./2.%20programa.py)  
- Verificación fin a fin: [`regenerar_pipeline.py`](./regenerar_pipeline.py)  
- Utilitarios (paquete): [`aurelion/`](./aurelion/)

## 🔗 Interactive Dashboard
👉 **Access the live Power BI dashboard here:** 
- https://app.powerbi.com/view?r=eyJrIjoiODUxMThiNjMtNzY3NC00MzEwLWFiN2MtZTUxOTRmZTBhZDNhIiwidCI6IjVjZTc1OWViLWYzNDYtNDljOC1hNTA2LWY4ODM5MTA3ZWMzOCIsImMiOjR9
