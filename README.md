# DIAN Contable — MVP Streamlit

Aplicativo para **cargar / estructurar / clasificar / exportar y validar** facturas de la DIAN hacia el archivo plano del software contable (plantilla de 14 columnas), con **Human-in-the-Loop** cuando la confianza es menor al **80%** o hay errores críticos.

## Requisitos

- Python 3.11 o superior
- Windows, macOS o Linux

## Instalación

```bash
cd dian-facturas-mvp
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python scripts\build_samples.py
```

**Linux / macOS:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/build_samples.py
```

Fase 2 (opcional, automatización del portal):

```bash
playwright install chromium
```

No escriba contraseñas en el código. Use `.env` o `.streamlit/secrets.toml`.

## Ejecución

Desde la raíz del proyecto:

```bash
streamlit run app.py
```

La interfaz guía el proceso en 7 pasos y muestra un indicador de avance. El plan de cuentas se carga automáticamente desde `archivos/Plan_de_Cuentas_v2.xlsx`.

`✅ Completado` · `⚠️ Requiere atención` · `⬜ Pendiente`

## Flujo operativo

1. **Cargar reporte DIAN** — Emitidas o Recibidas (.xlsx).
2. **Procesar facturas** — Normalización (NIT, factura, fechas, valores).
3. **Clasificar** — Usa el plan cargado automáticamente; cruce y puntaje de confianza.
4. **Software contable** — Cruce manual; `Base = 0,00` marca factura encontrada.
5. **HITL** — Solo ítems en `REQUIERE_REVISION` / `ERROR` / no encontradas.
6. **Validación final** — Marca `1` (día) o `4` (transferencia única) y cierra la revisión.
7. **Archivo plano final** — Genera el CSV/TXT según `MODELO PLANTILLA.csv` para cargarlo en el software contable.

**Auditoría** y **Configuración** permanecen como accesos opcionales.

## Formato del archivo plano

- Separador: `;`
- Decimales: coma (`166600000,00`)
- Fecha: `MM/DD/YYYY`
- `Tipo`: `1` débito, `2` crédito
- Encabezado exacto de 14 columnas (ver `data/samples/MODELO PLANTILLA.csv`)

Partida doble (ejemplo venta):

| Cuenta    | Tipo | Valor         | Base          |
|-----------|------|---------------|---------------|
| 130505    | 1    | 166600000,00  | 0,00          |
| 41355602  | 2    | 140000000,00  | 0,00          |
| 24080501  | 2    | 26600000,00   | 140000000,00  |

## Motor de confianza

| Señal                    | Peso |
|--------------------------|------|
| NIT exacto               | 25%  |
| Número de factura        | 25%  |
| Fecha                    | 15%  |
| Valor total              | 15%  |
| Cuenta contable          | 10%  |
| Descripción / concepto   | 10%  |

```text
si confianza >= 0.80 y no hay errores críticos → AUTOMATICO
si no → REQUIERE_REVISION
```

Errores críticos (forzan HITL): duplicadas, NIT o factura ausentes, valores/fechas inconsistentes, cuenta no asignada, no encontrada en el software.

## Arquitectura

```text
app.py                 entrada Streamlit
pages/                 pantallas del flujo
core/                  config, modelos Pydantic, logging, excepciones
services/              reglas de negocio (DIAN, Excel, clasificación, TXT, matching, auditoría)
utils/                 fechas, números, cadenas
tests/                 pytest
data/samples/          plantilla y XLSX de ejemplo
```

`txt_service.py` es la fuente de verdad del plano. `dian_service.py` deja el gancho Playwright de **Fase 2** (credenciales por entorno; la carga manual es el camino productivo del MVP).

## Pruebas

```bash
pytest -q
```

Cubre normalización numérica/fechas, umbral 79% vs 80%, errores críticos y las 14 columnas del plano.

## Despliegue

1. Instale dependencias en un entorno aislado.
2. Configure `.env` (sin commitear secretos).
3. Ejecute `streamlit run app.py --server.port 8501`.
4. Para un servidor interno: reverse proxy (nginx) hacia el puerto de Streamlit y autenticación de red de la firma.

Los logs rotan en `data/logs/app.log`. La auditoría persistente está en `data/audit/audit.jsonl`.
