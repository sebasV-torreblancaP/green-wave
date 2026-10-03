# Configuración inicial

El esquema JSON versión 1 permite validar un escenario antes de que se defina la semántica temporal completa. El archivo principal enumera las intersecciones y referencia Plan A, Plan B, perfiles de controlador y parámetros de transición mediante rutas relativas a su ubicación.

El ejemplo de `config/examples/synthetic/scenario.json` contiene **seis intersecciones sintéticas**. Sus duraciones y verdes no proceden de mediciones ni de `Plan.md`; permiten ejercitar carga y restricciones. `max_transition_cycles=20` existe solo en este ejemplo. No es un valor recomendado para producción.

Para validar la estructura:

```sh
PYTHONPATH=src python3 -m green_wave config/examples/synthetic/scenario.json --validate
```

Para inspeccionar el dominio de verde del siguiente paso a partir del verde de Plan A:

```sh
PYTHONPATH=src python3 -m green_wave config/examples/synthetic/scenario.json --domain I1
```

Ambos comandos son diagnósticos. Ninguno ejecuta el GA ni garantiza que Plan B sea temporalmente representable. Para consultar el estado de las decisiones, véase `docs/decisions.md`.

Se puede previsualizar una señal fija indicando explícitamente el segundo en que comienza su verde. El origen y `h_inicio_s` deben estar expresados en la misma escala de segundos del ejemplo:

```sh
PYTHONPATH=src python3 -m green_wave config/examples/synthetic/scenario.json --preview I1 --plan A --green-origin-s 10
```

La previsualización es una simulación de un plan fijo. No define cómo aplicar una transición entre planes.

Existe también un **prototipo de referencia** con decisiones temporales explícitas. El archivo `phase_origins.json` del ejemplo declara para cada intersección el segundo en que comienza el verde de A y B. La métrica `circular` se elige en la invocación. El prototipo aplica cada cambio en el siguiente inicio de verde de la intersección, cuenta el límite de ciclos localmente y utiliza búsqueda exhaustiva de G. Estas elecciones son provisionales y no resuelven las decisiones D01–D10 del sistema definitivo.

```sh
PYTHONPATH=src python3 -m green_wave config/examples/synthetic/scenario.json --run-reference --origins config/examples/synthetic/phase_origins.json --boundary-metric circular
```

Para exportar el resultado, añadir `--output results/mi-ejecucion` con una ruta que todavía no exista. Se generan `run.json`, `effective_config.json` y una traza JSON por intersección. Un estado `completed` describe el caso bajo la política explícita del prototipo; no acredita un GA ni integración física.

La exportación también genera `transitions.csv`, `phase_events.csv`, `signals.svg` y `fitness.svg`. Los gráficos utilizan las trazas y pasos ya calculados; `signals.svg` muestra los colores por segundo, los orígenes temporales declarados y los cambios aplicados. Las velocidades y distancias no aparecen porque no forman parte de los datos actuales.

El prototipo requiere las tres fases con duración positiva para calcular el fitness de fronteras. El validador estructural sigue admitiendo verde o rojo cero conforme a `Plan.md`; la política de fitness para esas fases está pendiente.

El mismo motor admite un GA de un gen con decisiones de operador declaradas en `genetic_choices.json`. El ejemplo sintético usa promedio entero de dos padres, probabilidad de mutación 0.5, desplazamiento máximo de 5 segundos, conservación del estado actual en cada generación y semilla 12345. Estos valores son elecciones de demostración, no recomendaciones ni acuerdos de `Plan.md`.

```sh
PYTHONPATH=src python3 -m green_wave config/examples/synthetic/scenario.json --run-genetic --origins config/examples/synthetic/phase_origins.json --boundary-metric circular --genetic-choices config/examples/synthetic/genetic_choices.json
```

También se admite `parent_strategy: "copy"` y la métrica `linear` como alternativas explícitas. La salida registra las opciones, generaciones, candidatos evaluados y motivo de parada por paso. El motor aplica el ±20 % respecto al estado anterior de cada paso, manteniendo ese dominio durante las generaciones internas.
