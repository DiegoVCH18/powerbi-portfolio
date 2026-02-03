
from __future__ import annotations

"""
Minimarket Aurelion – Pipeline Analítico v2.2 (Noviembre 2025)
Autor: Diego Armando Vásquez Chávez | Mentor: Mirta Gladys Julio
Curso: Fundamentos en IA (IBM & Guayerd) | Sprint 2 – EDA + Preparación ML

Propósito general:
    Orquestar el pipeline de análisis comercial: ingesta, limpieza, métricas, exportación y trazabilidad, con preparación para modelado ML (Sprint 3).

Estructura de carpetas:
    - datasets/: datos crudos
    - datasets_limpios/: datos limpios
    - export/: resultados y métricas
    - logs/: logs estructurados (pipeline, errores, performance)
    - docs/: reportes ejecutivos
    - aurelion/: utilidades y módulos core

Flujo de ejecución:
    Simulación → Limpieza → EDA → Exportación → Reporte
    Modularidad avanzada, logging estructurado, CLI moderno y validaciones robustas.

Ejemplo de logs:
    logs/aurelion_pipeline_YYYYMMDD.log.jsonl
    logs/performance.log.jsonl
    logs/errors.log.jsonl

Uso CLI:
    python 2.programa.py --run full
    python 2.programa.py --run fastmode
    python 2.programa.py --help
"""
import sys
import argparse
import traceback
import platform
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict, Tuple, Optional
import numpy as np

try:
    from colorama import Fore, Style, init as colorama_init
except ImportError:
    colorama_init = lambda: None
    Fore = Style = type('', (), {'RESET_ALL': ''})()

import pandas as pd
import numpy as np

from aurelion.logging_utils import configure_logging, configure_metrics_logger
from aurelion.pipeline_utils import (
    find_project_root,
    load_config,
    resolve_routes,
    read_excel_first_data_sheet,
    validate_referential_integrity,
    clean_all,
    integrate,
    ticket_promedio_mensual,
    top5_productos_por_importe,
    medios_pago_pct,
    clasificacion_abc,
)
# Sugerencia: mover funciones largas/reutilizables a aurelion.core_utils para mayor limpieza y testeo.
import warnings
warnings.filterwarnings('ignore')

# Variable global para logger
logger = None

# ==================== UTILIDADES AUXILIARES ====================

def make_json_serializable(obj: Any) -> Any:
    """
    Convierte objetos no serializables a JSON en tipos compatibles.
    
    Args:
        obj: Objeto a convertir
        
    Returns:
        Objeto serializable a JSON
    """
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif hasattr(obj, 'item'):  # Para escalares numpy
        return obj.item()
    else:
        return obj

# ==================== CONFIGURACIÓN INICIAL ====================


def configurar_logging() -> logging.Logger:
    """Configura logging estructurado (consola + JSON por archivo)."""
    return configure_logging(app_name="aurelion_pipeline", level=logging.INFO, logs_dir="logs")


def cargar_configuracion() -> Dict[str, Any]:
    """Carga parámetros desde ``config.json`` en la raíz del proyecto."""
    try:
        root = find_project_root(Path.cwd())
        cfg_path = root / "config.json"
        config = load_config(cfg_path)
        if logger:
            logger.info("Configuración cargada", extra={"event": "config_loaded", "context": {"path": str(cfg_path)}})
        return config
    except FileNotFoundError:
        manejar_error("configuración", "Archivo de configuración no encontrado")
        raise
    except json.JSONDecodeError as e:
        manejar_error("configuración", f"Error al parsear configuración: {e}")
        raise

# ==================== INGESTA DE DATOS ====================


def cargar_datasets(config: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carga los datasets de acuerdo a las rutas configuradas y valida columnas esperadas."""
    logger.info("Iniciando carga de datasets", extra={"event": "load_start"})
    rutas = resolve_routes(config, root=find_project_root(Path.cwd()))
    try:
        from aurelion.pipeline_utils import read_table_auto
        df_productos = read_table_auto(rutas.productos)
        if not isinstance(df_productos, pd.DataFrame):
            df_productos = pd.concat(df_productos, ignore_index=True)
        df_clientes = read_table_auto(rutas.clientes)
        if not isinstance(df_clientes, pd.DataFrame):
            df_clientes = pd.concat(df_clientes, ignore_index=True)
        df_ventas = read_table_auto(rutas.ventas)
        if not isinstance(df_ventas, pd.DataFrame):
            df_ventas = pd.concat(df_ventas, ignore_index=True)
        df_detalle = read_table_auto(rutas.detalle_ventas)
        if not isinstance(df_detalle, pd.DataFrame):
            df_detalle = pd.concat(df_detalle, ignore_index=True)

        # Validación de columnas esperadas
        columnas_esperadas = {
            'productos': {'id_producto', 'nombre_producto', 'categoria', 'precio_unitario'},
            'clientes': {'id_cliente', 'nombre_cliente', 'email', 'ciudad', 'fecha_alta'},
            'ventas': {'id_venta', 'fecha', 'id_cliente', 'medio_pago', 'canal'},
            'detalle': {'id_venta', 'id_producto', 'cantidad', 'precio_unitario', 'importe'},
        }
        columnas_opcionales = {
            'detalle': {'nombre_producto'},
        }

        for nombre, cols_obligatorias in columnas_esperadas.items():
            df = {
                'productos': df_productos,
                'clientes': df_clientes,
                'ventas': df_ventas,
                'detalle': df_detalle,
            }[nombre]
            opcionales = columnas_opcionales.get(nombre, set())
            faltantes = cols_obligatorias - set(df.columns)
            faltantes_requeridos = [col for col in faltantes if col not in opcionales]
            if faltantes_requeridos:
                manejar_error("ingesta", f"Faltan columnas en {nombre}: {set(faltantes_requeridos)}")
                raise ValueError(f"Faltan columnas en {nombre}: {set(faltantes_requeridos)}")
            faltantes_opcionales = [col for col in opcionales if col not in df.columns]
            if faltantes_opcionales and logger:
                logger.warning(
                    "Columna opcional ausente",
                    extra={
                        "event": "optional_column_missing",
                        "context": {"tabla": nombre, "faltantes": faltantes_opcionales}
                    }
                )

        if 'nombre_producto' not in df_detalle.columns and 'id_producto' in df_detalle.columns and 'nombre_producto' in df_productos.columns:
            nombre_map = df_productos[['id_producto', 'nombre_producto']].drop_duplicates()
            df_detalle = df_detalle.merge(nombre_map, on='id_producto', how='left')
            logger.info(
                "Nombre de producto agregado por merge",
                extra={"event": "detalle_nombre_producto_merge", "context": {"registros": len(df_detalle)}}
            )

        # Control de uso de memoria
        for nombre, df in zip(['productos', 'clientes', 'ventas', 'detalle'],
                              [df_productos, df_clientes, df_ventas, df_detalle]):
            print(f"\n{Fore.CYAN}{nombre.upper()}:{Style.RESET_ALL}")
            df.info(memory_usage='deep')

        logger.info(
            "Datasets cargados",
            extra={
                "event": "load_ok",
                "context": {
                    "productos": len(df_productos),
                    "clientes": len(df_clientes),
                    "ventas": len(df_ventas),
                    "detalle": len(df_detalle),
                },
            },
        )

        ok, stats = validate_referential_integrity(df_productos, df_clientes, df_ventas, df_detalle, config)
        logger.info("Integridad referencial verificada", extra={"event": "ri_check", "context": stats})
        if not ok:
            logger.warning("Se detectaron problemas de integridad; se continuará con limpieza", extra={"event": "ri_warning"})

        return df_productos, df_clientes, df_ventas, df_detalle
    except Exception as e:
        manejar_error("ingesta", e)
        raise

# Validación movida a aurelion.pipeline_utils.validate_referential_integrity

# ==================== LIMPIEZA Y TRANSFORMACIÓN ====================


def limpiar_datos(df_productos: pd.DataFrame, df_clientes: pd.DataFrame, df_ventas: pd.DataFrame, df_detalle: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Aplica reglas de limpieza delegando a utilidades reutilizables."""
    logger.info("🧹 Iniciando limpieza de datos...")
    prod, cli, ven, det, stats = clean_all(df_productos, df_clientes, df_ventas, df_detalle)
    for tabla, (inicial, final) in stats.items():
        descartes = inicial - final
        if descartes > 0:
            logger.warning(f"  ⚠️ {tabla}: {descartes} registros descartados ({(descartes/inicial*100 if inicial else 0):.1f}%)")
        else:
            logger.info(f"  ✓ {tabla}: sin descartes")
    logger.info("✅ Limpieza completada")
    # Control de uso de memoria tras limpieza
    for nombre, df in zip(['productos', 'clientes', 'ventas', 'detalle'], [prod, cli, ven, det]):
        print(f"\n{Fore.GREEN}MEMORIA LIMPIA {nombre.upper()}:{Style.RESET_ALL}")
        df.info(memory_usage='deep')
    return prod, cli, ven, det

# ==================== ANÁLISIS Y MÉTRICAS ====================


def calcular_metricas(df_ventas: pd.DataFrame, df_detalle: pd.DataFrame, df_productos: pd.DataFrame, df_clientes: pd.DataFrame) -> Dict[str, Any]:
    """Calcula métricas clave y retorna un diccionario con resultados."""
    logger.info("📊 Calculando métricas principales...")
    df_completo = integrate(df_detalle, df_ventas, df_productos)
    ticket_promedio = ticket_promedio_mensual(df_completo)
    top5_productos = top5_productos_por_importe(df_completo)
    medios_pct = medios_pago_pct(df_completo)
    productos_importe = df_completo.groupby([c for c in ("id_producto", "nombre_producto") if c in df_completo.columns])['importe'].sum()
    clientes_importe = df_completo.groupby('id_cliente')['importe'].sum()
    abc_productos = clasificacion_abc(productos_importe)
    abc_clientes = clasificacion_abc(clientes_importe)
    metricas = {
        'ticket_promedio': ticket_promedio,
        'top5_productos': top5_productos,
        'medios_pago': medios_pct,
        'abc_productos': abc_productos,
        'abc_clientes': abc_clientes,
        'df_completo': df_completo
    }
    logger.info("✅ Métricas calculadas correctamente")
    return metricas


def mostrar_metricas_consola(metricas: Dict[str, Any]) -> None:
    """Imprime las métricas principales en formato legible y colorido."""
    print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}📊 MÉTRICAS PRINCIPALES - MINIMARKET AURELION{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}🎯 TICKET PROMEDIO MENSUAL:{Style.RESET_ALL}")
    print(metricas['ticket_promedio'].tail(6).to_string())
    print(f"\n{Fore.CYAN}🏆 TOP 5 PRODUCTOS POR IMPORTE:{Style.RESET_ALL}")
    for idx, (key, valor) in enumerate(metricas['top5_productos'].items(), 1):
        print(f"  {idx}. {key[1]}: ${valor:,.2f}")
    print(f"\n{Fore.CYAN}💳 PARTICIPACIÓN POR MEDIO DE PAGO:{Style.RESET_ALL}")
    for medio, pct in metricas['medios_pago'].items():
        print(f"  {medio.upper()}: {pct:.2f}%")
    print(f"\n{Fore.CYAN}📈 CLASIFICACIÓN ABC PRODUCTOS:{Style.RESET_ALL}")
    conteo_abc = metricas['abc_productos']['clasificacion'].value_counts()
    for clase in ['A', 'B', 'C']:
        if clase in conteo_abc:
            print(f"  Clase {clase}: {conteo_abc[clase]} productos")
    print(f"\n{Fore.CYAN}👥 CLASIFICACIÓN ABC CLIENTES:{Style.RESET_ALL}")
    conteo_abc_cli = metricas['abc_clientes']['clasificacion'].value_counts()
    for clase in ['A', 'B', 'C']:
        if clase in conteo_abc_cli:
            print(f"  Clase {clase}: {conteo_abc_cli[clase]} clientes")
    print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}\n")

# ==================== EXPORTACIÓN ====================


def exportar_resultados(metricas: Dict[str, Any], config: Dict[str, Any]) -> None:
    """Exporta métricas y reportes a las carpetas configuradas."""
    logger.info("💾 Exportando resultados...")
    export_dir = Path("export")
    docs_dir = Path("docs")
    export_dir.mkdir(exist_ok=True)
    docs_dir.mkdir(exist_ok=True)
    try:
        metricas['top5_productos'].reset_index().to_csv(export_dir / "out_top5.csv", index=False, encoding='utf-8-sig')
        metricas['medios_pago'].reset_index().to_csv(export_dir / "out_mediopago.csv", index=False, encoding='utf-8-sig')
        metricas['abc_productos'].reset_index().to_csv(export_dir / "out_abc_productos.csv", index=False, encoding='utf-8-sig')
        metricas['abc_clientes'].reset_index().to_csv(export_dir / "out_abc_clientes.csv", index=False, encoding='utf-8-sig')
        generar_resumen_markdown(metricas, docs_dir / "resumen_mensual.md")
        logger.info(f"  ✓ Archivos exportados en {export_dir}/")
        logger.info(f"  ✓ Resumen generado en {docs_dir}/resumen_mensual.md")
        logger.info("✅ Exportación completada")
    except Exception as e:
        manejar_error("exportación", e)
        raise


def generar_resumen_markdown(metricas: Dict[str, Any], ruta_salida: Path) -> None:
    """Genera un archivo Markdown con el resumen ejecutivo."""
    with open(ruta_salida, 'w', encoding='utf-8') as f:
        f.write("# 📊 Resumen Mensual - Minimarket Aurelion\n\n")
        f.write(f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write("## 🎯 Ticket Promedio Mensual\n\n")
        f.write("```\n")
        f.write(metricas['ticket_promedio'].tail(6).to_string())
        f.write("\n```\n\n")
        f.write("## 🏆 Top 5 Productos por Importe\n\n")
        for idx, (key, valor) in enumerate(metricas['top5_productos'].items(), 1):
            f.write(f"{idx}. **{key[1]}**: ${valor:,.2f}\n")
        f.write("\n")
        f.write("## 💳 Participación por Medio de Pago\n\n")
        for medio, pct in metricas['medios_pago'].items():
            f.write(f"- **{medio.upper()}**: {pct:.2f}%\n")
        f.write("\n")
        f.write("## 📈 Clasificación ABC\n\n")
        f.write("### Productos\n")
        conteo = metricas['abc_productos']['clasificacion'].value_counts()
        for clase in ['A', 'B', 'C']:
            if clase in conteo:
                f.write(f"- **Clase {clase}**: {conteo[clase]} productos\n")
        f.write("\n### Clientes\n")
        conteo_cli = metricas['abc_clientes']['clasificacion'].value_counts()
        for clase in ['A', 'B', 'C']:
            if clase in conteo_cli:
                f.write(f"- **Clase {clase}**: {conteo_cli[clase]} clientes\n")
        f.write("\n---\n")
        f.write("*Generado automáticamente por el pipeline de Minimarket Aurelion*\n")

# ==================== PIPELINE PRINCIPAL ====================


def ejecutar_pipeline(config: Dict[str, Any], fastmode: bool = False) -> Tuple[Any, ...]:
    """Ejecuta el flujo completo del pipeline analítico."""
    logger.info("🚀 Iniciando pipeline completo...", extra={"event": "pipeline_start"})
    performance_logger = configurar_performance_logger()
    metrics_logger = configure_metrics_logger()
    stage_times: Dict[str, float] = {}
    mem_usos: Dict[str, int] = {}
    t0 = datetime.now()
    try:
        t_load = datetime.now()
        df_productos, df_clientes, df_ventas, df_detalle = cargar_datasets(config)
        stage_times["load_sec"] = (datetime.now() - t_load).total_seconds()
        mem_usos["load_mem"] = sum([df.memory_usage(deep=True).sum() for df in [df_productos, df_clientes, df_ventas, df_detalle]])
        ri_ok, ri_stats = validate_referential_integrity(df_productos, df_clientes, df_ventas, df_detalle, config)
        t_clean = datetime.now()
        df_productos, df_clientes, df_ventas, df_detalle = limpiar_datos(df_productos, df_clientes, df_ventas, df_detalle)
        stage_times["clean_sec"] = (datetime.now() - t_clean).total_seconds()
        mem_usos["clean_mem"] = sum([df.memory_usage(deep=True).sum() for df in [df_productos, df_clientes, df_ventas, df_detalle]])
        t_metrics = datetime.now()
        metricas = calcular_metricas(df_ventas, df_detalle, df_productos, df_clientes)
        stage_times["metrics_sec"] = (datetime.now() - t_metrics).total_seconds()
        mem_usos["metrics_mem"] = metricas['df_completo'].memory_usage(deep=True).sum()
        if not fastmode:
            t_export = datetime.now()
            exportar_resultados(metricas, config)
            stage_times["export_sec"] = (datetime.now() - t_export).total_seconds()
        stage_times["total_sec"] = (datetime.now() - t0).total_seconds()
        registrar_metricas(metrics_logger, stage_times, context={"ri_ok": ri_ok, "ri_stats": ri_stats, "mem_usos": mem_usos})
        registrar_performance(performance_logger, stage_times, mem_usos)
        logger.info("🎉 Pipeline ejecutado exitosamente", extra={"event": "pipeline_success"})
        return metricas, df_productos, df_clientes, df_ventas, df_detalle
    except Exception as e:
        manejar_error("pipeline", e)
        try:
            registrar_metricas(metrics_logger, {"total_sec": None}, status="failed", context={"error": str(e)})
            registrar_performance(performance_logger, stage_times, mem_usos, status="failed", context={"error": str(e)})
        except Exception:
            pass
        raise



def registrar_metricas(metrics_logger: logging.Logger, stage_times: Dict[str, float], status: str = "success", context: Optional[Dict] = None) -> None:
    """Registra métricas de ejecución en logs/metrics.log."""
    payload = {
        "status": status,
        "stage_times": make_json_serializable(stage_times),
        "timestamp": datetime.now().isoformat(),
    }
    if context:
        payload.update(make_json_serializable(context))
    metrics_logger.info("pipeline_summary", extra={"event": "metrics", "context": payload})

def configurar_performance_logger() -> logging.Logger:
    """Configura logger para performance (logs/performance.log.jsonl)."""
    perf_logger = logging.getLogger("performance")
    if not perf_logger.handlers:
        handler = logging.FileHandler("logs/performance.log.jsonl", encoding="utf-8")
        handler.setFormatter(logging.Formatter('%(message)s'))
        perf_logger.addHandler(handler)
        perf_logger.setLevel(logging.INFO)
    return perf_logger

def registrar_performance(perf_logger: logging.Logger, stage_times: Dict[str, float], mem_usos: Dict[str, int], status: str = "success", context: Optional[Dict] = None) -> None:
    """Registra tiempos y memoria en logs/performance.log.jsonl."""
    payload = {
        "status": status,
        "stage_times": make_json_serializable(stage_times),
        "mem_usos": make_json_serializable(mem_usos),
        "timestamp": datetime.now().isoformat(),
    }
    if context:
        payload.update(make_json_serializable(context))
    
    try:
        perf_logger.info(json.dumps(payload, ensure_ascii=False))
    except TypeError as e:
        # Fallback en caso de que aún haya problemas de serialización
        simplified_payload = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "error": f"Serialization error: {str(e)}"
        }
        perf_logger.info(json.dumps(simplified_payload, ensure_ascii=False))


def mostrar_registros_recientes(df_ventas: pd.DataFrame, df_detalle: pd.DataFrame, n: int = 10) -> None:
    """Muestra las últimas N ventas con sus detalles."""
    print(f"\n{Fore.YELLOW}📋 ÚLTIMAS {n} VENTAS REGISTRADAS:{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    ventas_recientes = df_ventas.nlargest(n, 'fecha')[['id_venta', 'fecha', 'id_cliente', 'medio_pago']]
    for _, venta in ventas_recientes.iterrows():
        print(f"\n🛒 Venta #{venta['id_venta']} - {venta['fecha'].strftime('%Y-%m-%d')} - Cliente #{venta['id_cliente']}")
        print(f"   Medio de pago: {venta['medio_pago'].upper()}")
        detalle = df_detalle[df_detalle['id_venta'] == venta['id_venta']]
        for _, item in detalle.iterrows():
            nombre_producto = item.get('nombre_producto', 'Producto sin nombre')
            print(f"   • {nombre_producto}: {item['cantidad']} x ${item['precio_unitario']:.2f} = ${item['importe']:.2f}")
        total = detalle['importe'].sum()
        print(f"   TOTAL: ${total:.2f}")
    print(f"\n{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}\n")

# ==================== MENÚ INTERACTIVO ====================


def mostrar_menu():
    """Muestra el menú principal del sistema."""
    print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}🏪 MINIMARKET AURELION - SISTEMA DE ANÁLISIS v2.2{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}[1]{Style.RESET_ALL} 🚀 Ejecutar pipeline completo")
    print(f"{Fore.CYAN}[2]{Style.RESET_ALL} 📊 Mostrar métricas principales")
    print(f"{Fore.CYAN}[3]{Style.RESET_ALL} 📋 Ver registros recientes")
    print(f"{Fore.CYAN}[4]{Style.RESET_ALL} 📄 Ver resumen de logs")
    print(f"{Fore.CYAN}[5]{Style.RESET_ALL} 📝 Generar reporte ejecutivo")
    print(f"{Fore.CYAN}[0]{Style.RESET_ALL} 🚪 Salir")
    print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")

def _format_bytes(num_bytes: int) -> str:
    """Convierte un tamaño en bytes a formato legible."""
    step = 1024.0
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(num_bytes)
    for unit in units:
        if size < step:
            return f"{size:.1f} {unit}"
        size /= step
    return f"{size:.1f} PB"


def mostrar_resumen_proyecto(config: Dict[str, Any]) -> None:
    """Imprime un panorama general del proyecto y sus artefactos clave."""
    try:
        root = find_project_root(Path.cwd())
    except Exception:
        root = Path.cwd()

    rutas = resolve_routes(config, root=root)
    print(f"{Fore.BLUE}\n{'='*64}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🔍 Panorama del Proyecto{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'='*64}{Style.RESET_ALL}")
    print(f"Ruta base: {root}")
    print(f"Python: {platform.python_version()} | Sistema: {platform.system()} {platform.release()}")

    carpetas_clave = [
        ('datasets', root / 'datasets'),
        ('datasets_limpios', root / 'datasets_limpios'),
        ('export', root / 'export'),
        ('docs', root / 'docs'),
        ('logs', root / 'logs'),
        ('reportes', root / 'reportes'),
        ('visualizaciones_EDA', root / 'visualizaciones_EDA'),
    ]

    print(f"\n{Fore.CYAN}📁 Carpetas relevantes:{Style.RESET_ALL}")
    for nombre, ruta in carpetas_clave:
        existe = ruta.exists()
        archivos = len(list(ruta.glob('*'))) if existe else 0
        estado = f"{Fore.GREEN}OK{Style.RESET_ALL}" if existe else f"{Fore.RED}No existe{Style.RESET_ALL}"
        print(f"  - {nombre:20} {estado} | archivos: {archivos}")

    datasets_info = {
        'clientes': rutas.clientes,
        'productos': rutas.productos,
        'ventas': rutas.ventas,
        'detalle_ventas': rutas.detalle_ventas,
    }

    print(f"\n{Fore.CYAN}📦 Datasets configurados:{Style.RESET_ALL}")
    for nombre, ruta in datasets_info.items():
        path_obj = Path(ruta)
        if path_obj.exists():
            stat = path_obj.stat()
            tam = _format_bytes(stat.st_size)
            actualizado = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  - {nombre:16} {Fore.GREEN}OK{Style.RESET_ALL} | tamaño: {tam} | modificado: {actualizado}")
        else:
            print(f"  - {nombre:16} {Fore.RED}No encontrado{Style.RESET_ALL}")

    export_dir = root / 'export'
    if export_dir.exists():
        export_files = sorted(export_dir.glob('*.csv'))
        print(f"\n{Fore.CYAN}📤 Últimas exportaciones CSV:{Style.RESET_ALL}")
        for path in export_files[-5:]:
            stat = path.stat()
            print(f"  - {path.name:30} {_format_bytes(stat.st_size)} | {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"\n{Fore.CYAN}📤 Últimas exportaciones CSV:{Style.RESET_ALL} {Fore.YELLOW}Sin carpeta export{Style.RESET_ALL}")

    logs_dir = root / 'logs'
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob('*.log.jsonl'))
        print(f"\n{Fore.CYAN}🪵 Logs recientes:{Style.RESET_ALL}")
        for path in log_files[-5:]:
            stat = path.stat()
            print(f"  - {path.name:35} {_format_bytes(stat.st_size)} | {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"\n{Fore.CYAN}🪵 Logs recientes:{Style.RESET_ALL} {Fore.YELLOW}Sin carpeta logs{Style.RESET_ALL}")

    print(f"{Fore.BLUE}{'='*64}{Style.RESET_ALL}\n")



def menu_interactivo(config: Dict[str, Any]) -> None:
    """Maneja el menú interactivo por consola."""
    metricas = None
    df_ventas = None
    df_detalle = None
    while True:
        mostrar_menu()
        opcion = input(f"\n{Fore.YELLOW}👉 Seleccione una opción:{Style.RESET_ALL} ").strip()
        if opcion == "1":
            try:
                resultado = ejecutar_pipeline(config)
                metricas, _, _, df_ventas, df_detalle = resultado
                print(f"\n{Fore.GREEN}✅ Pipeline ejecutado correctamente. Puede consultar las métricas en la opción 2.{Style.RESET_ALL}")
            except Exception as e:
                print(f"\n{Fore.RED}❌ Error al ejecutar pipeline: {e}{Style.RESET_ALL}")
        elif opcion == "2":
            if metricas is None:
                print(f"\n{Fore.RED}⚠️ Debe ejecutar el pipeline primero (opción 1){Style.RESET_ALL}")
            else:
                mostrar_metricas_consola(metricas)
        elif opcion == "3":
            if df_ventas is None or df_detalle is None:
                print(f"\n{Fore.RED}⚠️ Debe ejecutar el pipeline primero (opción 1){Style.RESET_ALL}")
            else:
                n = input(f"{Fore.YELLOW}¿Cuántos registros desea ver? (por defecto 10): {Style.RESET_ALL}").strip()
                n = int(n) if n.isdigit() else 10
                mostrar_registros_recientes(df_ventas, df_detalle, n)
        elif opcion == "4":
            print(f"\n{Fore.CYAN}Mostrando resumen de logs de performance:{Style.RESET_ALL}")
            try:
                with open("logs/performance.log.jsonl", encoding="utf-8") as f:
                    for line in list(f)[-5:]:
                        print(line.strip())
            except Exception as e:
                print(f"{Fore.RED}No se pudo leer logs de performance: {e}{Style.RESET_ALL}")
        elif opcion == "5":
            if metricas is None:
                print(f"\n{Fore.RED}⚠️ Debe ejecutar el pipeline primero (opción 1){Style.RESET_ALL}")
            else:
                try:
                    generar_resumen_markdown(metricas, Path("docs/resumen_mensual.md"))
                    print(f"{Fore.GREEN}Reporte ejecutivo generado en docs/resumen_mensual.md{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Error al generar reporte: {e}{Style.RESET_ALL}")
        elif opcion == "0":
            print(f"\n{Fore.GREEN}👋 ¡Hasta pronto! Cerrando sistema...{Style.RESET_ALL}")
            break
        else:
            print(f"\n{Fore.RED}❌ Opción inválida. Intente nuevamente.{Style.RESET_ALL}")

# ==================== MAIN ====================


def manejar_error(etapa: str, error: Any) -> None:
    """Centraliza el manejo de errores: loguea tipo, mensaje y traceback."""
    tb = traceback.format_exc()
    # Solo usar logger si está disponible
    if logger:
        logger.error(f"[{etapa.upper()}] {type(error).__name__}: {error}", extra={"event": "error", "context": {"traceback": tb}})
    else:
        # Fallback a print si logger no está disponible
        print(f"{Fore.RED}ERROR [{etapa.upper()}] {type(error).__name__}: {error}{Style.RESET_ALL}")
    
    # Asegurar que el directorio logs existe
    Path("logs").mkdir(exist_ok=True)
    
    try:
        with open("logs/errors.log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"etapa": etapa, "error": str(error), "traceback": tb, "timestamp": datetime.now().isoformat()}) + "\n")
    except Exception:
        # Si no se puede escribir al archivo, al menos mostrar en consola
        print(f"{Fore.YELLOW}Advertencia: No se pudo escribir al archivo de logs{Style.RESET_ALL}")

def validar_version_python():
    """Valida que la versión de Python sea >= 3.11."""
    if sys.version_info < (3, 11):
        print(f"{Fore.RED}Se requiere Python 3.11 o superior. Versión detectada: {platform.python_version()}{Style.RESET_ALL}")
        sys.exit(1)

def detectar_entorno() -> str:
    """Detecta si se ejecuta en local, Colab o Docker."""
    if 'google.colab' in sys.modules:
        return 'colab'
    try:
        with open('/proc/1/cgroup', 'rt') as ifh:
            if 'docker' in ifh.read():
                return 'docker'
    except Exception:
        pass
    return 'local'

def mostrar_banner():
    """Muestra banner de inicio con versión y fecha actual."""
    print(f"{Fore.GREEN}\n╔════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║           🏪 MINIMARKET AURELION - PIPELINE v2.2           ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║  Proyecto: Inteligencia Comercial y Analítica Predictiva   ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║  Autor: Diego Armando Vásquez Chávez                       ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║  Mentor: Mirta Gladys Julio                                ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║  Curso: Fundamentos en IA - IBM & Guayerd                  ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║  Sprint: 2 - EDA + ML Prep                                 ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                      ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}╚════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")

def mostrar_ayuda():
    """Muestra ayuda CLI."""
    print(f"""
{Fore.YELLOW}USO:{Style.RESET_ALL}
  python 2.programa.py --run full         # Ejecuta pipeline completo
  python 2.programa.py --run fastmode     # Solo limpieza y métricas (sin exportar)
  python 2.programa.py --help             # Muestra esta ayuda

Opciones del menú interactivo:
  [1] Ejecutar pipeline completo
  [2] Mostrar métricas principales
  [3] Ver registros recientes
  [4] Ver resumen de logs de performance
  [5] Generar reporte ejecutivo
  [0] Salir
""")

def main():
    """Función principal: inicializa sistema, parsea argumentos y ejecuta menú o pipeline."""
    colorama_init(autoreset=True)
    validar_version_python()
    mostrar_banner()
    global logger
    logger = configurar_logging()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--run', type=str, choices=['full', 'fastmode'], help='Modo de ejecución del pipeline')
    parser.add_argument('--help', action='store_true', help='Mostrar ayuda')
    args = parser.parse_args()
    if args.help:
        mostrar_ayuda()
        sys.exit(0)
    try:
        config = cargar_configuracion()
        mostrar_resumen_proyecto(config)
        entorno = detectar_entorno()
        logger.info(f"Entorno detectado: {entorno}", extra={"event": "env_detected", "context": {"env": entorno}})
        if args.run == 'full':
            ejecutar_pipeline(config, fastmode=False)
        elif args.run == 'fastmode':
            ejecutar_pipeline(config, fastmode=True)
        else:
            menu_interactivo(config)
    except Exception as e:
        manejar_error("main", e)
        print(f"\n{Fore.RED}❌ Error crítico: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Revise los logs para más detalles.{Style.RESET_ALL}")
    finally:
        logger.info("🔚 Cerrando programa...")

if __name__ == "__main__":
    main()

#
# =================== CHANGELOG ===================
#
# - Estructura modular optimizada
# - Nuevas opciones CLI (help, fastmode, resumen de logs)
# - Validaciones y control de errores mejorados
# - Logs de performance y métricas extendidas
# - Preparación para integración con ML (Sprint 3)
