from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import os

UNIT_RAD_S = "rad/s"
UNIT_RPS = "rps"

ROLE_RESEARCHER = "researcher"
ROLE_STUDENT = "student"
ROLE_ADMIN = "admin"


@dataclass
class SensorConfig:
    port: str = ""
    baud_rate: int = 115200
    sample_rate_hz: int = 20       # 10–1000 Hz
    slots: int = 20
    disk_diameter_mm: float = 75.0


@dataclass
class Scenario:
    id: str
    name_ru: str
    name_en: str
    description_ru: str
    description_en: str
    unit: str = UNIT_RAD_S
    interval_ms: int = 500
    sensor: SensorConfig = field(default_factory=SensorConfig)
    has_simulation: bool = False
    allowed_roles: list = field(default_factory=lambda: [ROLE_RESEARCHER, ROLE_STUDENT, ROLE_ADMIN])

    def name(self, lang: str = "ru") -> str:
        return self.name_ru if lang == "ru" else self.name_en

    def description(self, lang: str = "ru") -> str:
        return self.description_ru if lang == "ru" else self.description_en


BUILTIN_SCENARIOS: list[Scenario] = [
    Scenario(
        id="qualitative",
        name_ru="Качественный анализ",
        name_en="Qualitative Analysis",
        description_ru="Демонстрация закономерностей: быстрее/медленнее, растёт/убывает.",
        description_en="Demonstrate patterns: faster/slower, increasing/decreasing.",
        unit=UNIT_RAD_S,
        interval_ms=500,
        sensor=SensorConfig(sample_rate_hz=10),
    ),
    Scenario(
        id="quantitative",
        name_ru="Количественный анализ",
        name_en="Quantitative Analysis",
        description_ru="Точные измерения и обработка числовых данных.",
        description_en="Precise measurements and numerical data processing.",
        unit=UNIT_RAD_S,
        interval_ms=100,
        sensor=SensorConfig(sample_rate_hz=100),
    ),
    Scenario(
        id="fluid_simulation",
        name_ru="Жидкость во вращающемся сосуде",
        name_en="Fluid in Rotating Vessel",
        description_ru="Интеграция с модулем моделирования поведения жидкости.",
        description_en="Integration with fluid behaviour simulation module.",
        unit=UNIT_RAD_S,
        interval_ms=100,
        sensor=SensorConfig(sample_rate_hz=50),
        has_simulation=True,
    ),
    Scenario(
        id="rotation_demo",
        name_ru="Демонстрационная установка «Вращательное движение»",
        name_en="Rotational Motion Demo",
        description_ru="Демонстрация вращательного движения на лабораторном стенде.",
        description_en="Demonstration of rotational motion on a lab stand.",
        unit=UNIT_RAD_S,
        interval_ms=100,
        sensor=SensorConfig(sample_rate_hz=50),
    ),
]


def load_scenarios(scenarios_dir: str) -> list[Scenario]:
    scenarios = list(BUILTIN_SCENARIOS)
    if not os.path.isdir(scenarios_dir):
        return scenarios
    for fname in os.listdir(scenarios_dir):
        if fname.endswith(".scenario"):
            path = os.path.join(scenarios_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sensor_data = data.pop("sensor", {})
                data["sensor"] = SensorConfig(**sensor_data)
                scenarios.append(Scenario(**data))
            except Exception:
                pass
    return scenarios
