from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SimulationParams(BaseModel):
    """Parámetros de una simulación individual."""

    carrier_freq: float = Field(
        default=4000.0,
        description="Frecuencia portadora del estímulo RAM [Hz].",
        gt=0,
    )
    fs: float = Field(
        default=100_000.0,
        description="Frecuencia de muestreo [Hz]. El modelo trabaja internamente a 100kHz.",
        gt=0,
    )
    poles_profile: str = Field(
        default="Flat00",
        description=(
            "Nombre de la subcarpeta dentro de Poles/ que contiene el StartingPoles.dat. "
            "Ejemplos: 'Flat00' (audición normal), 'Flat30', 'Flat35', 'Slope30'."
        ),
    )
    fc: str = Field(
        default="abr",
        description=(
            "Secciones de la cóclea a procesar. "
            "'abr' = 401 secciones (recomendado para EFR/ABR), "
            "'half' = 500, 'all' = 1000."
        ),
        pattern="^(abr|half|all)$",
    )
    irregularities: int = Field(
        default=1,
        description="Activar (1) o desactivar (0) irregularidades y no-linealidades cocleares.",
        ge=0,
        le=1,
    )
    storeflag: str = Field(
        default="w",
        description=(
            "Máscara de variables a guardar. Cada letra activa una salida: "
            "v=velocidad BM, y=desplazamiento BM, e=OAE, i=IHC, "
            "h=fibras HSR, m=fibras MSR, l=fibras LSR, b=CN+IC, w=ondas ABR (w1/w3/w5). "
            "Forzado internamente: 'w' y 'b'. Máximo: 'evihmlbw'."
        ),
    )
    subject: int = Field(
        default=1,
        description="Semilla para las irregularidades aleatorias. Afecta reproducibilidad.",
        ge=1,
    )
    irr_pct: float = Field(
        default=0.05,
        description="Magnitud de perturbaciones aleatorias en la membrana basilar (default 5%).",
        ge=0.0,
        le=1.0,
    )
    non_linear_type: str = Field(
        default="vel",
        description=(
            "'vel' = no-linealidad instantánea basada en velocidad BM (default). "
            "'none' = modelo lineal."
        ),
        pattern="^(vel|none)$",
    )
    nH: int = Field(
        default=13,
        description="Número de fibras HSR (alta tasa espontánea). Normal = 13.",
        ge=0,
    )
    nM: int = Field(
        default=3,
        description="Número de fibras MSR (media tasa espontánea). Normal = 3.",
        ge=0,
    )
    nL: int = Field(
        default=3,
        description="Número de fibras LSR (baja tasa espontánea). Normal = 3.",
        ge=0,
    )
    save_raw: bool = Field(
        default=False,
        description=(
            "Si es True, guarda raw.npz (cf, stimulus, fs_bm) y, si 'v' está en storeflag, "
            "también bm_velocity.npz con la velocidad de la membrana basilar."
        ),
    )


class BatchSimulationRequest(BaseModel):
    """Múltiples simulaciones a correr en paralelo."""

    simulations: List[SimulationParams] = Field(
        ...,
        description="Lista de configuraciones. Cada una corre en un proceso separado.",
        min_length=1,
        max_length=32,
    )


class EFRResult(BaseModel):
    efr_value_uV: float
    harmonics: Dict[int, float]


class SimulationResult(BaseModel):
    status: str
    carrier_freq: float
    poles_profile: str
    w1: Optional[List[float]] = None
    w3: Optional[List[float]] = None
    w5: Optional[List[float]] = None
    sim_id: Optional[str] = None
    efr: Optional[EFRResult] = None
    error: Optional[str] = None
