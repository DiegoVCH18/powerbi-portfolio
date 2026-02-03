# 🏪 Minimarket Aurelion – Retail Analytics Pipeline

End-to-end retail sales analytics project including data simulation, cleaning,
exploratory analysis (EDA), ABC segmentation, and automated report generation.

- **Author:** Diego Armando Vásquez Chávez  
- **Program:** Fundamentals of AI – IBM & Guayerd  
- **Version:** 2.1 (Nov 1, 2025)

---

## 📘 Introduction

The objective of this project is to identify top-performing products, seasonality
patterns, and ABC segmentation of both customers and items in a retail context.

The pipeline integrates, cleans, and analyzes data from multiple sources
(Excel, CSV, JSON), exporting metrics, visualizations, and executive summaries
to support business decision-making.

### Key Highlights
- Stratified sampling preserves payment method distribution during data simulation
- Data cleaning with integrity validations (primary keys, foreign keys, dates, prices)
  and business rule derivation (sales channel inferred from payment method)
- EDA including KPIs (average ticket, top 5 products, correlations) and ABC classification
- Structured logging (JSONL) and execution metrics by pipeline stage

---

## 🏗️ Architecture

### Main Repository Components

#### 📓 Notebooks
- `4. simulador_datos_comerciales.ipynb` → Generates simulated retail datasets
- `7. Limpieza_datos.ipynb` → Data integration and cleaning; exports `*_clean.xlsx`
- `8. EDA_Aurelion.ipynb` → Exploratory analysis and visualizations; generates CSV and PNG outputs

#### ⚙️ Scripts
- `2. programa.py` → Pipeline orchestrator (cleaning, KPIs, exports, logging, metrics)
- `regenerar_pipeline.py` → Non-interactive full pipeline execution and validation

#### 📦 Utility Package (`aurelion/`)
- `pipeline_utils.py` → Configuration, autodetected input reading (Excel/CSV/JSON),
  validations, cleaning, integration, and execution metrics
- `logging_utils.py` → Structured logging (console, `errors.log.jsonl`, `metrics.log.jsonl`)
- `visualization_utils.py` → `generar_visualizacion()` for histogram, boxplot,
  heatmap, and Pareto charts
- `eda_analyzer.py` → `EDAAnalyzer` class (KPIs, outlier detection, ABC segmentation,
  CSV report generation)

#### 📁 Data & Outputs
- Raw data: `datasets/`
- Clean data: `datasets_limpios/`
- Exports: `export/` (CSV/JSON/TXT)
- Visual assets: `visualizaciones_EDA/` (PNG)
- Logs: `logs/` (JSONL)
- Documentation: `docs/` (Markdown)

#### ⚙️ Configuration
- `5. config.json` → Paths, parameters, and validation thresholds

---

## ▶️ Execution

### Requirements
- Python 3.10+
- Packages: `pandas`, `numpy`, `matplotlib`, `seaborn`, `openpyxl`

### Recommended Flow (VS Code Terminal or Codespaces – PowerShell)

```powershell
# 1) (Optional) Generate simulated data
python "4. simulador_datos_comerciales.py"

# 2) Run the pipeline (interactive menu)
python "2. programa.py"

# 3) Alternative non-interactive execution
python regenerar_pipeline.py

# 4) Manual EDA
# Open and execute: 8. EDA_Aurelion.ipynb

