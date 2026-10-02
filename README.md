# Green Wave: simulación diaria

Los controladores conservan VERDE → ÁMBAR → ROJO, C = 140 s y A = 3 s.
R = C - G - A. Las ventanas de análisis no reinician ciclos físicos.
Las duraciones nominales son independientes de Wave A y Wave B.

## Alcanzabilidad y transición

Con inicios consecutivos de verde separados exactamente por C, el offset
módulo C permanece constante. Compensar verde con rojo o aumentar el número
de ciclos no desplaza ese offset.

El código separa `PhaseDurationAdjustment` de `PhaseOffsetCorrection`.
Los objetivos incompatibles se registran como FAILED / TARGET NOT ACHIEVABLE
UNDER CURRENT CONSTRAINTS, conservando el plan anterior. No se sustituye el
objetivo por una banda distinta ni se debilita la auditoría. Para cambiar
offsets debe permitirse un intervalo físico transitorio diferente de 140 s
o modificarse explícitamente el objetivo.

Con offsets compatibles se reevalúa cada ciclo local, recuperando duraciones
nominales mediante aumentos o reducciones del verde y compensación exacta del
rojo. Las órdenes se aplican al inicio local de verde; no interrumpen fases.
Se respetan mínimos/máximos, porcentaje relativo al nominal y el límite
opcional `green_step_s`. El porcentaje también limita la desviación total
respecto al nominal, conforme a la auditoría existente.

## Ejecución

```powershell
& .venv/Scripts/python.exe -m pytest
& .venv/Scripts/python.exe main.py --config config.day.example.json --no-show
& .venv/Scripts/python.exe plot_cycles.py --config config.day.example.json --no-show
& .venv/Scripts/python.exe history.py --latest
& .venv/Scripts/python.exe history.py --latest --at 13:37:24
& .venv/Scripts/python.exe verify_fixed_cycle.py historico/NOMBRE_EJECUCION
& .venv/Scripts/python.exe validate_nominal_recovery.py
```

FAILED devuelve código 2 aunque la simulación física sea válida. El ensayo
de recuperación declara offsets compatibles; no demuestra una reversión a
los offsets originales de BAJADA.

`config.day.example.json` implementa el caso obligatorio de seis intersecciones,
verdes [60,40,55,53,43,65], offsets A [0,18,45,59,91,113], horario 06:00–22:00,
solicitud 13:37:24 y los offsets B calculados con los parámetros del proyecto.
La configuración principal conserva las velocidades actuales de 40 km/h.

`day.start`, `day.end`, `day.transition_time` y `day.post_transition_s`
configuran el calendario. CLI: `--start`, `--end`, `--transition-time`,
`--duration-s`, `--at`. `waves.A` y `waves.B` admiten `direction`, `speed_kmh`
y `offsets_s` independientes del nominal. `day.requests` permite solicitudes
cronológicas múltiples. `cycles_up`/`cycles_down` ya no controlan el calendario.

El horizonte se redondea hacia arriba a una ventana de 140 s para la auditoría;
el margen se declara en metadatos. Tras SUCCESS se garantiza el período estable
configurado (una hora por defecto), ampliando el horizonte cuando hace falta.
No se insertan ciclos de espera. Las consultas admiten segundos fraccionarios.

```python
from day_simulation import simulate_day
day = simulate_day(config=cfg, start="06:00", end="22:00", wave="A")
result = day.transition("13:37:24", from_wave="A", to_wave="B")
day.simulate_remaining_day()
day.export("historico")
```

## Histórico

Cada ejecución conserva `frames.csv`, `states.csv`, `cycles.csv`, `audit.json`
y `audit.txt`. `yellow` en esos CSV significa ÁMBAR.

- `controller_cycles.csv`: ciclos completos con sus orígenes físicos.
- `baseline_controller_cycles.csv`, `baseline_states.csv`: funcionamiento
  inicial antes de planificar solicitudes.
- `phase_history.csv`: timestamps, ciclo local, límites completos de cada
  fase, duraciones, offset y parte visible.
- `transitions.csv`, `transition_summary.json`: estados inicial/objetivo/final,
  ajustes y correcciones solicitadas/aplicadas, métricas y motivos.
- `physical_verification.json`: verificación independiente de límites,
  continuidad, secuencia, objetivo y restauración nominal.
- Gráficos del día, detalle de la solicitud y curvas de G/R, offsets, ámbar y C.

Resultados y comparación: [DAY_TRANSITION_RESULT.md](DAY_TRANSITION_RESULT.md).
