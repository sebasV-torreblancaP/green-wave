# Plan de implementación de Green Wave

**Estado:** plan rector. Su implementación se registra mediante código, pruebas y `docs/decisions.md`; las decisiones pendientes siguen requiriendo resolución explícita.

**Fuente funcional:** [Plan.md](Plan.md), leído íntegramente en su versión de 1312 líneas. Las referencias `§` de este documento corresponden a las secciones numeradas de esa fuente.

**Destinatario:** agente de IA o desarrollador que implementará el sistema de forma incremental.

**Alcance de la entrega original de este documento:** diseñar la implementación. La solicitud posterior de implementar el plan autoriza crear código y pruebas de forma incremental. Este documento por sí solo no resuelve las decisiones funcionales abiertas.

## 1. Objetivo y alcance

### 1.1. Objetivo funcional

Construir un sistema Python capaz de buscar y representar una transición progresiva desde el estado temporal de Plan A hasta el de Plan B, respetando restricciones por intersección y registrando todos los estados intermedios.

El sistema inicial debe admitir seis intersecciones, sin incorporar ese número en los algoritmos. Cada intersección puede tener su propio ciclo y amarillo. El resultado incluye la trayectoria de cada intersección y la condición de finalización de la ejecución completa.

El número de ciclos necesarios es un resultado, no un objetivo fijo. El máximo de ciclos es exclusivamente una protección contra ejecución indefinida.

### 1.2. Alcance sustentado por Plan.md

- Configuración de intersecciones, planes y parámetros compartidos.
- Representación temporal R/V/A con un símbolo por segundo.
- Construcción del estado inicial desde `H_inicio`, aunque caiga dentro de una fase.
- Optimización independiente por intersección, usando el verde como gen.
- Evaluación de estados y fronteras contra un Plan B fijo.
- Restricciones de cambio, conservación de BEST, ausencia de regresión y congelación de intersecciones alineadas.
- Historial de los ciclos de transición y límite de protección.
- Algoritmo genético con generaciones internas, sujeto a completar sus definiciones pendientes.

### 1.3. Infraestructura propuesta

Este documento añade una organización de módulos, contratos de datos, simulación semafórica, exportación, pruebas y visualización para hacer implementable y verificable ese alcance. Son propuestas técnicas, no requisitos textuales adicionales de `Plan.md`.

El núcleo se denomina **motor de transición entre planes**. No confundirlo con un algoritmo de diseño de onda verde: el fitness del documento mide alineamiento con Plan B, no progresión vehicular.

### 1.4. Extensiones condicionadas a requisitos posteriores

- Generación de planes coordinados mediante distancias y velocidades.
- Simulación de vehículos, demanda, colas, detenciones o tiempos de viaje.
- Modelado de movimientos, grupos semafóricos, peatones o fases concurrentes.
- Comunicación y aplicación sobre controladores físicos.

No inventar valores ni comportamientos para estas extensiones. Reservar límites arquitectónicos, pero no crear módulos vacíos ni dependencias hasta iniciar su etapa.

### 1.5. Convenciones para interpretar este documento

| Etiqueta | Significado | Instrucción para el implementador |
|---|---|---|
| REQUISITO | Regla expresada en Plan.md | Preservarla; cualquier cambio funcional debe justificarse explícitamente |
| DERIVADO | Consecuencia matemática de las reglas existentes | Incorporarla sin presentarla como una regla nueva |
| PROPUESTA | Organización técnica o alternativa recomendada | Mantener su trazabilidad; no atribuirla a Plan.md |
| PENDIENTE | Decisión que afecta al comportamiento y aún no está cerrada | No resolverla con un valor predeterminado silencioso |
| FUTURO | Capacidad que requiere ampliar el alcance | No incluirla en la definición de completitud del núcleo inicial |

Antes de implementar, volver a leer `Plan.md`, las instrucciones aplicables del repositorio y el estado del árbol de trabajo. Si la fuente cambió, reconciliar diferencias con este documento. Preservar cambios preexistentes del usuario.

## 2. Requisitos y decisiones del Plan.md

### 2.1. Requisitos trazables

| ID | Requisito que debe mantenerse | Fuente |
|---|---|---|
| R01 | Plan A es el estado inicial; Plan B es la referencia objetivo y permanece fijo | §1–2 |
| R02 | La transición se realiza mediante estados sucesivos; no omitir el proceso de transición | §1, §25–27, §38 |
| R03 | El número inicial de intersecciones es seis y sus ciclos pueden diferir | §1, §33 |
| R04 | `H_inicio` se elige manualmente y puede caer dentro de cualquier fase | §3 |
| R05 | T0 se obtiene mediante una ventana de Plan A de duración C desde `H_inicio` | §4 |
| R06 | La representación principal es una secuencia R/V/A por segundos | §2, §7–8 |
| R07 | G es entero, es el gen y R se deriva mediante `R = C - A - G` | §5–6, §19–20 |
| R08 | Se cumplen `0 <= G <= 99`, `0 <= R <= 99` y `G + A + R = C` | §19, §36 |
| R09 | El amarillo permanece fijo y el orden cíclico es `R → V → A → R` | §36 |
| R10 | El cambio de G es como máximo ±20 % respecto al estado aplicado anterior | §18, §26, §36 |
| R11 | El fitness se calcula por intersección; no hay un fitness global de control | §10, §14–15 |
| R12 | `F = 0.5 F_estado + 0.5 F_frontera`, con resultado entre 0 y 1 | §10 |
| R13 | `F_estado = 1 - segundos_diferentes / C` es la formulación inicial | §11 |
| R14 | `F_frontera = 1` exige coincidencia exacta de todas las fronteras | §12, §37.2 |
| R15 | Se generan 15 candidatos; si hay menos valores válidos se usan todos | §15, §17 |
| R16 | El estado actual debe estar entre los candidatos y deben evitarse duplicados | §16–17, §36 |
| R17 | Los candidatos inválidos no se evalúan | §20, §36 |
| R18 | La población propuesta conserva cinco mejores y genera diez descendientes | §21 |
| R19 | Se preserva BEST; no se acepta regresión respecto al mejor estado alcanzado | §22, §36 |
| R20 | El GA termina por fitness perfecto, diez generaciones sin mejora o cien generaciones | §23, §31 |
| R21 | Generaciones del GA y ciclos de transición son niveles diferentes | §24 |
| R22 | Una intersección con F=1 deja de optimizarse; cada una puede terminar por separado | §13–14, §28 |
| R23 | El éxito global requiere que todas las intersecciones alcancen F=1 | §29, §38 |
| R24 | Debe existir `max_transition_cycles`; no define el número esperado de ciclos | §30–31 |
| R25 | Separar parámetros de intersección y parámetros generales | §32–34 |
| R26 | No introducir cuotas arbitrarias de exploración ni forzar movimientos hacia Plan B | §35 |
| R27 | La reproducción y la normalización de fronteras están pendientes de definición | §37 |

### 2.2. Interpretaciones que no deben introducirse silenciosamente

- No imponer un ciclo común: la fuente admite ciclos diferentes.
- No convertir R, amarillo, ciclo u offset en genes adicionales.
- No sustituir la búsqueda independiente por un cromosoma global.
- No considerar que alcanzar Plan B demuestra por sí solo una onda verde.
- No relajar la coincidencia exacta mediante una tolerancia numérica o un umbral menor que 1.
- No ampliar el ±20 % con un paso mínimo de un segundo.
- No aplicar el porcentaje respecto a un padre del GA ni respecto al Plan A original.
- No introducir mínimos positivos de verde o rojo para evitar fases ausentes.
- No asumir que un ejemplo ilustrativo equivale a configuración real disponible.

La lectura del modelo de un solo gen implica tratar C como contexto fijo por intersección durante la búsqueda. Confirmar su compatibilidad entre Plan A y Plan B antes de cerrar el modelo temporal.

## 3. Errores, inconsistencias y correcciones detectadas

### 3.1. Registro de hallazgos

Las correcciones matemáticas verificables se distinguen de las alternativas que necesitan una decisión funcional. Este registro no modifica `Plan.md`.

| ID | Problema | Por qué es un problema | Corrección propuesta y estado |
|---|---|---|---|
| P01 | Se habla de Green Wave sin modelar distancias, velocidades ni vehículos | El fitness solo demuestra coincidencia con Plan B | PROPUESTA: separar transición de planes y futura coordinación vehicular |
| P02 | G, C y amarillo no especifican un anclaje temporal | Duraciones iguales pueden producir secuencias desplazadas | PENDIENTE D01: definir referencia temporal y frontera que permanece anclada al variar G |
| P03 | Plan B puede no ser representable con el único gen G | Un offset, ciclo o amarillo incompatible puede impedir F=1 | DERIVADO: validar representabilidad; PENDIENTE D01/D04 para concretar el contrato |
| P04 | El ejemplo de T0 altera las cantidades de amarillo y rojo | Una ventana de un periodo completo conserva el número de segundos de cada color | DERIVADO: utilizar la rotación corregida de §3.2 como prueba |
| P05 | No se define cómo aplicar un cambio durante una fase en curso | Una secuencia nominal válida puede truncar amarillo o reiniciar fases al concatenarse | PENDIENTE D02: política de aplicación y continuidad |
| P06 | T1, T2 y T5 se presentan como si fueran tiempos compartidos | Con ciclos diferentes, el mismo índice local representa tiempos distintos | PENDIENTE D03: separar índices locales, rondas lógicas y tiempos físicos |
| P07 | Las ventanas parten de H_inicio, pero el reloj de ejecución avanza | La comparación puede usar orígenes temporales incompatibles | PENDIENTE D03: demostrar equivalencia periódica o definir ventanas compatibles sin cambiar Plan B |
| P08 | Solo G tiene un requisito explícito de integralidad | C, amarillo o H_inicio fraccionarios no encajan directamente con una cadena por segundos | PROPUESTA pendiente D05: segundos enteros y ventanas semiabiertas; no redondear en silencio |
| P09 | No se documenta el dominio conjunto de G | Puede ocultar configuraciones imposibles o provocar generación por rechazo innecesaria | DERIVADO: calcular la intersección de límites del controlador y límite porcentual |
| P10 | G entre 0 y 4 no puede cambiar bajo ±20 % e integralidad | Hay estados bloqueados; además, no se alcanza G=0 desde G positivo | DERIVADO: diagnosticar imposibilidad cuando esté demostrada; no alterar la regla |
| P11 | Se admiten G=0 y R=0, pero se esperan tres fronteras observables | Una fase ausente elimina o superpone fronteras | PENDIENTE D06: semántica de eventos ausentes/coincidentes; no introducir mínimos positivos |
| P12 | No se define la frontera en el cierre de la ventana | La fase inicial puede estar repartida entre principio y final | PROPUESTA pendiente D06: detectar cierre circular del fenotipo y distinguirlo de la ejecución real |
| P13 | Se dice que importa la posición de los errores, pero F_estado solo cuenta discrepancias | Distintos patrones con igual cantidad de errores obtienen el mismo valor | DERIVADO: conservar la fórmula y documentar su límite; usar fronteras y posiciones como información adicional |
| P14 | F_frontera no tiene fórmula completa | No se puede reproducir ni verificar el fitness | PENDIENTE D06: normalización, circularidad, correspondencia y casos degenerados |
| P15 | Usar menos de 15 valores contradice una población rígida de 5+10 | Puede haber menos de cinco valores disponibles | PROPUESTA pendiente D07: tamaño efectivo y élites adaptados al dominio |
| P16 | “Siempre incluir el actual” no aclara si abarca cada generación | Puede ocupar una plaza adicional a las cinco élites | PENDIENTE D07: definir individuos obligatorios y completar las plazas restantes |
| P17 | El ejemplo de pérdida del mejor fitness contradice elitismo correcto | Con contexto fijo y élites preservadas el máximo no debería bajar | DERIVADO: distinguir máximo de promedio; mantener BEST y delimitar su ámbito |
| P18 | La búsqueda local sin regresión no garantiza llegar a B | Puede haber mesetas, repetición de estados o ausencia de camino admisible | PROPUESTA: diagnosticar sin afirmar imposibilidad por mera falta de convergencia; PENDIENTE D08 para empates |
| P19 | “No cambiar directamente” es ambiguo si B cabe en el rango del primer paso | El procedimiento puede seleccionar B sin violar el porcentaje | PENDIENTE D10: aclarar si se permite un único cambio válido |
| P20 | FROZEN puede confundirse con detener el color del semáforo | Se debe distinguir detener la búsqueda de detener la señal periódica | PROPUESTA pendiente D02: congelar optimización y continuar ejecutando el plan alcanzado |
| P21 | target_fitness figura como parámetro aunque el éxito exige exactamente 1 | Un valor menor altera la definición de finalización | PROPUESTA: mantenerlo en 1 y rechazar otros valores en el modo conforme al plan |
| P22 | No se da valor ni semántica completa a max_transition_cycles | No se sabe si cuenta rondas, ciclos locales ni si incluye T0 | PENDIENTE D09: definir conteo y salida incompleta, sin inventar un valor |
| P23 | §31 presenta valores iniciales ajustables y §36 denomina definitivo al 20 % | No queda claro qué modificaciones son experimentos y cuáles conservan conformidad | PROPUESTA pendiente D11: mantener perfil conforme y etiquetar explícitamente experimentos |

### 3.2. Corrección verificable del ejemplo de T0

El ciclo nominal de §4 contiene cinco segundos verdes, dos amarillos y siete rojos:

```text
V V V V V A A R R R R R R R
```

Comenzando en el tercer segundo verde, la ventana correcta de un periodo completo es:

```text
V V V A A R R R R R R R V V
```

La ventana publicada contiene tres amarillos y seis rojos. La prueba de rotación debe verificar tanto longitud como cantidades de cada color; no copiar el ejemplo erróneo como resultado esperado.

### 3.3. Registro de decisiones pendientes

| ID | Decisión a cerrar | Evidencia exigida para cerrarla | Componentes dependientes |
|---|---|---|---|
| D01 | Referencia temporal de cada plan y decodificación de G | Ejemplos con iguales duraciones y distintos offsets; regla explícita sobre qué frontera se mantiene fija | PlanEntry, PhaseReference, fenotipo, representabilidad |
| D02 | Instante efectivo de aplicación y continuidad de fase; significado de FROZEN | Transiciones iniciadas dentro de rojo, verde y amarillo con tiempos efectivos | Política de transición, simulación, aplicación real futura |
| D03 | Calendario para ciclos heterogéneos y ventana de comparación | Ejemplo de dos intersecciones con ciclos distintos, índices locales y tiempos absolutos | Scheduler, no regresión, referencia objetivo, métricas |
| D04 | Compatibilidad de C y amarillo entre A y B | Contrato que confirme parámetros fijos o documente una ampliación del modelo | Configuración y validación de planes |
| D05 | Unidades, resolución, origen temporal y extremos de ventanas | Convención de segundos, tratamiento de fracciones y significado de H_inicio | Carga, matemáticas y serialización |
| D06 | Fronteras, fases nulas y fórmula de F_frontera | Fórmula con dominio, casos límite, ejemplos y demostración de igualdad exacta | Evaluador completo y congelación |
| D07 | Tamaño efectivo de población, élites e inclusión del actual | Casos con 1, 4, 5, 10 y 15 valores válidos | Población genética |
| D08 | Selección, reproducción, mutación, desempate y conteo de estancamiento | Operadores descritos, parámetros, semilla y ejemplos reproducibles | GA y selección de estados |
| D09 | Valor y conteo del máximo de ciclos; resultado al agotarlo | Ejemplos del último paso permitido y salida incompleta | Terminación y resultados |
| D10 | Transición alcanzable en un solo paso | Regla expresa para A distinto de B pero B admisible inmediatamente | Motor y pruebas de aceptación |
| D11 | Parámetros ajustables y reglas de conformidad | Clasificación de límites, pesos, porcentaje y umbral; configuración efectiva versionada | Validación y experimentos |

Registrar las resoluciones futuras en `docs/decisions.md`: ID, estado, fuente, decisión, motivo, alternativas, impacto funcional y pruebas asociadas. Una propuesta de este documento no cuenta como resolución de una ambigüedad del plan.

Continuar el trabajo independiente que esté definido. No presentar como completa una etapa cuyo comportamiento depende de decisiones abiertas. Si una decisión funcional es indispensable, solicitarla de forma concreta indicando las alternativas y su impacto; no solicitar confirmación para elecciones técnicas reversibles ya cubiertas por el alcance.

## 4. Arquitectura general

### 4.1. Capas y dirección de dependencias

La aplicación compondrá un núcleo de dominio independiente de archivos, gráficos, redes y controladores.

```text
CLI
 └─ Application
     ├─ Configuration ───────────────┐
     ├─ Transition engine           │
     │   ├─ Optimizer (contrato)     │
     │   ├─ Evaluator               ├─ Models + Mathematics
     │   └─ Executor (contrato)      │
     ├─ Signal simulator ───────────┤
     ├─ Persistence ────────────────┤
     └─ Visualization ──────────────┘
```

- `models`: tipos e invariantes locales; no importa capas externas.
- `mathematics`: funciones puras sobre números y modelos; no realiza E/S.
- `configuration`: traduce archivos a modelos y usa validaciones comunes.
- `evaluation`: compara fenotipos; no controla generaciones ni ciclos de ejecución.
- `optimization`: busca candidatos mediante contratos; no aplica estados ni modifica configuración.
- `algorithms`: dirige la transición y las condiciones de aplicación y terminación; recibe colaboradores por contrato.
- `simulation`: ejecuta programaciones y emite trazas; no decide qué verde optimizar.
- `persistence` y `visualization`: consumen datos del dominio; no recalculan reglas funcionales.
- `application`: conecta implementaciones concretas y coordina el caso de uso.
- `cli`: interpreta argumentos y presenta el resultado; no contiene fórmulas.

Los contratos deben ubicarse donde no creen ciclos de importación. El optimizador recibe evaluación y validación por contrato o funciones inyectadas; el evaluador concreto no necesita importar el motor de transición. La política temporal prepara solicitudes ejecutables; el simulador no importa decisiones internas del GA.

### 4.2. Reglas de codificación futura

1. Implementar módulos pequeños con una responsabilidad reconocible y funciones testeables.
2. Usar nombres descriptivos; preferir `green_s`, `yellow_s`, `cycle_s` a letras ambiguas fuera de las fórmulas.
3. Tipar contratos, entidades y retornos donde ayude a detectar errores. Usar tipos de la biblioteca estándar y clases de datos antes de añadir frameworks.
4. Representar colores y estados de ejecución mediante tipos explícitos, evitando cadenas arbitrarias distribuidas por el código.
5. Mantener configuración fuera del código y resolverla una sola vez por ejecución. No mutarla desde el optimizador.
6. Centralizar fórmulas e invariantes. Un gráfico, exportador u operador genético no debe implementar su propia versión del fitness o del rango válido.
7. Evitar fuentes duplicadas: R, fronteras, cantidad de intersecciones y número efectivo de candidatos se derivan.
8. No introducir variables globales mutables ni un reloj o generador aleatorio ocultos. Inyectar contexto, reloj simulado y aleatoriedad.
9. Mantener funciones matemáticas libres de lecturas de archivos, registros y efectos secundarios.
10. Definir precondiciones, postcondiciones, unidades y convenciones temporales en los contratos públicos.
11. Tratar parámetros inválidos explícitamente. No corregirlos mediante redondeos, recortes o valores predeterminados silenciosos.
12. No capturar excepciones de forma genérica para continuar con resultados aparentemente válidos.
13. Empezar con biblioteca estándar para JSON, modelos, rutas y CLI. Añadir una herramienta de pruebas y una biblioteca de gráficos solo en las etapas que las necesiten.
14. No añadir bases de datos, servicios web, frameworks de inyección, procesamiento distribuido ni dependencias de GA sin una necesidad demostrada.
15. Declarar versión de Python y dependencias en `pyproject.toml` al crear el proyecto, según el entorno verificado; no asumir una versión por este documento.
16. Hacer cambios incrementales y revisar diferencias. Ejecutar las pruebas relevantes antes de avanzar.
17. No modificar decisiones funcionales de Plan.md sin documentar motivo, impacto y decisión explícita. Una simplificación técnica no justifica cambiar una regla.
18. Crear archivos cuando tengan una responsabilidad implementada y verificable; la estructura futura no exige crear todos los directorios por anticipado.

## 5. Estructura completa de carpetas y archivos

Estructura objetivo propuesta. Las anotaciones `FUTURO` indican extensiones condicionadas, no entregables del núcleo. Los datos reales de las seis intersecciones no están disponibles en Plan.md; cualquier escenario de prueba debe etiquetarse como sintético.

```text
green-wave/
├── Plan.md
├── IMPLEMENTATION_PLAN.md
├── pyproject.toml
├── config/
│   ├── scenario.json
│   ├── transition.json
│   ├── controller_profiles.json
│   ├── intersections/
│   │   ├── I1.json
│   │   ├── I2.json
│   │   ├── I3.json
│   │   ├── I4.json
│   │   ├── I5.json
│   │   └── I6.json
│   ├── plans/
│   │   ├── plan_a.json
│   │   └── plan_b.json
│   └── corridor.json                    # FUTURO
├── src/
│   └── green_wave/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── application.py
│       ├── configuration/
│       │   ├── __init__.py
│       │   ├── loader.py
│       │   ├── schema.py
│       │   └── validation.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── intersection.py
│       │   ├── phase.py
│       │   ├── plan.py
│       │   ├── timeline.py
│       │   ├── candidate.py
│       │   ├── transition.py
│       │   ├── settings.py
│       │   └── errors.py
│       ├── mathematics/
│       │   ├── __init__.py
│       │   ├── durations.py
│       │   ├── feasible_domain.py
│       │   ├── periodic_time.py
│       │   └── phenotype.py
│       ├── algorithms/
│       │   ├── __init__.py
│       │   ├── transition_engine.py
│       │   ├── transition_policy.py
│       │   └── termination.py
│       ├── optimization/
│       │   ├── __init__.py
│       │   ├── interfaces.py
│       │   ├── search_context.py
│       │   ├── exhaustive.py
│       │   └── genetic/
│       │       ├── __init__.py
│       │       ├── optimizer.py
│       │       ├── population.py
│       │       └── operators.py
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── state_fitness.py
│       │   ├── boundary_fitness.py
│       │   ├── evaluator.py
│       │   └── metrics.py
│       ├── simulation/
│       │   ├── __init__.py
│       │   ├── interfaces.py
│       │   ├── scheduler.py
│       │   ├── signal_simulator.py
│       │   ├── trace.py
│       │   └── traffic_simulator.py      # FUTURO
│       ├── visualization/
│       │   ├── __init__.py
│       │   ├── signal_timeline.py
│       │   ├── convergence.py
│       │   └── time_distance.py          # FUTURO
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── result_writer.py
│       │   └── result_reader.py
│       └── integration/                 # FUTURO
│           ├── __init__.py
│           ├── controller_port.py
│           └── controller_adapter.py
├── tests/
│   ├── unit/
│   │   ├── test_configuration.py
│   │   ├── test_feasible_domain.py
│   │   ├── test_temporal_windows.py
│   │   ├── test_fitness.py
│   │   ├── test_transition_policy.py
│   │   ├── test_termination.py
│   │   ├── test_genetic_optimizer.py
│   │   └── test_persistence.py
│   ├── integration/
│   │   ├── test_transition_pipeline.py
│   │   ├── test_heterogeneous_cycles.py
│   │   ├── test_cli.py
│   │   ├── test_visualization.py
│   │   ├── test_traffic_simulation.py    # FUTURO
│   │   └── test_controller_adapter.py   # FUTURO
│   ├── properties/
│   │   └── test_domain_properties.py
│   └── fixtures/
│       ├── synthetic_scenarios.json
│       └── expected_timelines.json
├── scripts/
│   └── benchmark_scaling.py
├── results/                             # Artefactos generados por ejecución
└── docs/
    ├── conceptual_model.md
    ├── decisions.md
    ├── configuration.md
    └── validation_strategy.md
```

La entrada principal propuesta es `python -m green_wave`, después de instalar el paquete en el entorno de desarrollo. No crear otro flujo funcional independiente en un `main.py` raíz.

## 6. Responsabilidad de cada módulo

Las rutas Python de esta sección son relativas a `src/green_wave/`.

| Archivo o grupo | Responsabilidad | Exclusiones |
|---|---|---|
| `__init__.py` de cada paquete | Definir la superficie pública mínima | No ejecutar simulaciones ni leer configuración al importar |
| `__main__.py` | Delegar en la CLI | No duplicar el caso de uso |
| `cli.py` | Argumentos, selección explícita de modo y presentación del resultado | Sin fórmulas ni reglas genéticas |
| `application.py` | Cargar escenario, componer colaboradores y coordinar salida | Sin implementar fitness, operadores o gráficos |
| `configuration/loader.py` | Leer JSON y resolver rutas relativas al escenario | Sin búsqueda de candidatos |
| `configuration/schema.py` | Contrato de formato, campos, tipos y versión | Sin duplicar el estado de ejecución |
| `configuration/validation.py` | Validación cruzada de escenario, planes e intersecciones | Reutilizar fórmulas comunes, no copiarlas |
| `models/intersection.py` | Identidad, ciclo, amarillo y perfil de límites | Sin reloj ni E/S |
| `models/phase.py` | Colores y tipos de frontera | Sin políticas de tráfico no especificadas |
| `models/plan.py` | Planes y referencias temporales | Sin carga JSON |
| `models/timeline.py` | Ventanas, eventos y metadatos temporales | Sin renderizado |
| `models/candidate.py` | Candidato, validación y desglose de fitness | Sin selección genética |
| `models/transition.py` | Estados, pasos, resultados y motivos de finalización | Sin algoritmo de ejecución |
| `models/settings.py` | Configuración efectiva tipada de transición y ejecución | Sin variables globales mutables |
| `models/errors.py` | Errores estructurados del dominio y contratos | Sin imprimir ni decidir recuperación |
| `mathematics/durations.py` | Derivación de rojo y conservación de duraciones | Sin redondeo implícito |
| `mathematics/feasible_domain.py` | Intervalo entero válido y cardinalidad | Sin muestrear población |
| `mathematics/periodic_time.py` | Posiciones modulares, ventanas y detección de fronteras bajo la convención acordada | No aplicar cambios reales |
| `mathematics/phenotype.py` | Decodificar G y contexto en una secuencia por segundos | No inventar el anclaje pendiente |
| `algorithms/transition_engine.py` | Gestionar intersecciones activas, solicitar búsquedas y registrar pasos | Sin operadores del GA |
| `algorithms/transition_policy.py` | Determinar admisibilidad temporal y momento efectivo del cambio | Sin protocolo de controlador |
| `algorithms/termination.py` | Éxito, congelación y límite de ciclos | Sin modificar el fitness |
| `optimization/interfaces.py` | Contratos de búsqueda, evaluación y observación | Sin implementación concreta del GA |
| `optimization/search_context.py` | Contexto inmutable de una búsqueda local | No actualizar el estado aplicado entre generaciones |
| `optimization/exhaustive.py` | Referencia que evalúa el dominio completo de G | No presentarse como el GA requerido |
| `optimization/genetic/optimizer.py` | Bucle generacional, BEST y paradas internas | Sin avanzar el reloj semafórico |
| `optimization/genetic/population.py` | Unicidad, tamaño efectivo, élites y candidatos obligatorios | Sin cambiar límites para llenar población |
| `optimization/genetic/operators.py` | Selección, reproducción y mutación acordadas | Sin heurísticas manuales hacia Plan B |
| `evaluation/state_fitness.py` | Discrepancias por segundo y F_estado | Sin decidir congelación |
| `evaluation/boundary_fitness.py` | Errores por frontera y normalización acordada | Sin fórmulas provisionales ocultas |
| `evaluation/evaluator.py` | Evaluación explicable de un fenotipo válido | Sin mutar candidato ni contexto |
| `evaluation/metrics.py` | Resúmenes por intersección y ejecución | Sin fitness global que controle la búsqueda |
| `simulation/interfaces.py` | Contrato del ejecutor temporal y sus resultados | Sin depender de controladores concretos |
| `simulation/scheduler.py` | Ordenar eventos por tiempo y aplicar el calendario acordado | No sincronizar ciclos diferentes por conveniencia |
| `simulation/signal_simulator.py` | Ejecutar solicitudes válidas y verificar continuidad observable | Sin elegir el mejor verde |
| `simulation/trace.py` | Construir trazas de eventos y muestras desde modelos compartidos | Sin duplicar entidades temporales |
| `simulation/traffic_simulator.py` | FUTURO: movimiento vehicular bajo un modelo especificado | Sin asumir demanda ni dinámica |
| `visualization/signal_timeline.py` | Señales, fronteras, offsets definidos y comparación con B | Sin reconstruir reglas del negocio |
| `visualization/convergence.py` | Fitness, BEST, verdes y congelación | Sin interpretar un límite como éxito |
| `visualization/time_distance.py` | FUTURO: diagrama espacio-tiempo | Requiere enlaces y trayectorias reales del simulador |
| `persistence/result_writer.py` | Exportar datos con esquema y unidades | Sin recalcular soluciones |
| `persistence/result_reader.py` | Leer y validar artefactos para análisis y gráficos | No implica reanudación automática de búsquedas |
| `integration/controller_port.py` | FUTURO: contrato de lectura, aplicación y confirmación | Sin suponer API o hardware |
| `integration/controller_adapter.py` | FUTURO: traducción al equipo elegido | Sin reglas matemáticas propias |

Archivos de soporte:

- `pyproject.toml`: empaquetado, versión de Python, dependencias y herramientas de pruebas.
- `config/*`: entradas declarativas; sus responsabilidades se detallan en §8.
- `tests/unit/*`: contratos matemáticos y de componentes aislados.
- `tests/integration/*`: comportamiento de módulos conectados y casos de uso completos.
- `tests/properties/*`: invariantes sobre múltiples entradas válidas.
- `tests/fixtures/*`: escenarios sintéticos y resultados esperados independientes del código probado.
- `scripts/benchmark_scaling.py`: medir coste; no contener un segundo motor.
- `results/`: resultados generados, organizados por ejecución; no configuración fuente.
- `docs/conceptual_model.md`: modelo resuelto y convenciones temporales.
- `docs/decisions.md`: decisiones pendientes y resueltas con su impacto.
- `docs/configuration.md`: esquema, unidades y ejemplos identificados como sintéticos.
- `docs/validation_strategy.md`: correspondencia entre requisitos, pruebas y evidencias.

## 7. Modelo de datos

### 7.1. Entidades propuestas

| Entidad | Campos conceptuales | Invariantes o propósito |
|---|---|---|
| `IntersectionConfig` | `id`, `cycle_s`, `yellow_s`, `controller_profile_id` | Identificador único; sin datos duplicados de Plan A/B |
| `ControllerLimits` | Límites de verde y rojo | Perfil compartido inicial 0–99; no inventar capacidades por equipo |
| `Phase` | R, V, A | Un símbolo representa un segundo en el fenotipo |
| `PhaseReference` | Evento de referencia, origen y desplazamiento temporal según D01/D05 | Es contexto, no gen; evitar dos orígenes redundantes |
| `SignalPlan` | ID y mapa de entradas por intersección | Plan B inmutable durante la ejecución |
| `PlanEntry` | Verde y referencia temporal, o forma de importación acordada | Derivar R; comprobar compatibilidad de C y amarillo |
| `TemporalWindow` | Intersección, inicio, duración y secuencia | Longitud C y marco temporal explícito |
| `PhaseBoundary` | Tipo de evento y posición | Semántica de ausencia/coincidencia pendiente D06 |
| `Candidate` | `green_s` | Único gen entero |
| `CandidateValidation` | Validez y violaciones identificadas | Candidato inválido no llega al fitness |
| `FitnessBreakdown` | F_estado, F_frontera, total, discrepancias y errores | Explicar el resultado; coincidencia exacta sin tolerancia de éxito |
| `SearchContext` | Intersección, estado aplicado anterior, objetivo, dominio, contexto temporal y reglas | Inmutable durante todas las generaciones del mismo paso |
| `OptimizationResult` | Candidato elegido, desglose, evaluaciones, generaciones y motivo | No equivale a un estado ya aplicado |
| `IntersectionState` | G, referencia temporal, índice local, tiempos efectivos y condición | ACTIVE o FROZEN según la política acordada |
| `TransitionStep` | Estado previo, estado seleccionado, solicitud de aplicación, resultado y métricas | Distinguir selección de aplicación efectiva |
| `SimulationTrace` | Eventos y muestras identificados por intersección y tiempo | Datos independientes del formato visual |
| `TransitionResult` | Trayectorias, configuración efectiva, semillas, métricas, estado y motivos | Diferenciar completo, incompleto y error |

### 7.2. Fuente única de verdad

- Configurar la duración verde de cada plan y su referencia temporal cuando se cierre D01.
- Construir la cadena temporal como representación principal del fenotipo.
- Si se admite importar cadenas, derivar duraciones y validar estructura; no exigir simultáneamente otra definición independiente que pueda contradecirlas.
- Calcular R siempre desde C, amarillo y G. Puede exportarse como dato derivado, identificándolo como tal.
- Obtener fronteras y métricas mediante los módulos comunes. Las cachés son resultados derivados, nunca configuración editable.
- Contar G sobre el periodo completo cuando se importa una ventana; no usar solamente el primer segmento verde.

### 7.3. Límites del modelo inicial

Una intersección representa una única señal cíclica R/V/A. No hay información suficiente para modelar varias señales en conflicto, movimientos o fases concurrentes. Cambiar el número de fases requiere ampliar el dominio y las restricciones, aunque modificar las duraciones de las fases existentes sea configurable.

## 8. Organización de parámetros

### 8.1. Distribución por archivo

| Archivo | Datos fuente | Datos que no debe duplicar |
|---|---|---|
| `config/scenario.json` | ID y versión del escenario, H_inicio, referencias explícitas a planes, intersecciones, reglas y opciones de ejecución | Número de intersecciones, duraciones de cada plan |
| `config/intersections/<id>.json` | ID, C, amarillo y referencia al perfil del controlador | G de A/B, R calculado, parámetros generales del GA |
| `config/plans/plan_a.json` | Entradas iniciales por ID y anclaje temporal | Límites del controlador ni ajustes genéticos |
| `config/plans/plan_b.json` | Entradas objetivo por ID y anclaje temporal | Copias editables de las restricciones |
| `config/controller_profiles.json` | Definición compartida de límites, inicialmente G/R entre 0 y 99 | Ajustes del optimizador |
| `config/transition.json` | Parámetros de búsqueda, pesos, reglas y protección | Parámetros físicos propios de cada intersección |
| `config/corridor.json` | FUTURO: enlaces, longitudes, sentidos y datos de circulación acordados | Duraciones semafóricas ya definidas en otros archivos |

Usar identificadores y referencias, no posiciones fijas en una lista. Resolver rutas relativas al archivo de escenario. Evitar mezclar configuraciones mediante precedencias implícitas; si se añaden sobrescrituras de CLI, documentarlas y exportar el resultado efectivo.

### 8.2. Parámetros compartidos del modelo inicial

| Nombre propuesto | Valor de referencia | Tratamiento |
|---|---|---|
| `candidates_per_intersection` | 15 | Tamaño solicitado; el efectivo depende del dominio |
| `max_green_change_percent` | 20 | Regla conforme al plan; ajustes experimentales sujetos a D11 |
| `max_generations` | 100 | Límite de búsqueda interna |
| `stagnation_generations` | 10 | Conteo exacto pendiente D08 |
| `elite_count` | 5 | Política para poblaciones pequeñas pendiente D07 |
| `state_weight` | 0.5 | Peso inicial del plan |
| `boundary_weight` | 0.5 | Peso inicial del plan |
| `target_fitness` | 1.0 | No admitir éxito aproximado en el modo conforme |
| `max_transition_cycles` | Sin valor especificado | Requerir valor explícito y semántica D09 |

Los diez descendientes se derivan de la población inicial de quince y las cinco élites bajo la política acordada. No introducir tres tamaños independientes que puedan contradecirse.

PROPUESTAS de operación: semilla aleatoria, carpeta de resultados y detalle del historial. Guardar estos valores con la configuración efectiva. No afectan por sí mismos a la definición matemática del objetivo.

### 8.3. Parámetros derivados

R, intervalo válido, cardinalidad del dominio, tamaño efectivo de población, secuencias, fronteras, fitness, BEST, congelación, ciclos usados y tiempo de finalización son resultados calculados. No pedirlos como entradas independientes.

### 8.4. Parámetros no definidos por el plan

- No hay ciclo común obligatorio. Si se añade un escenario con esa restricción, representarla una sola vez y validar todas las intersecciones.
- Las distancias corresponden a enlaces entre intersecciones, potencialmente dirigidos.
- Las velocidades requieren definir si pertenecen al enlace, ruta, escenario o vehículo.
- No existen datos completos de I1–I6, ni un máximo de ciclos de protección concreto.
- No hay configuración vehicular ni parámetros de comunicaciones reales.

## 9. Flujo completo de ejecución

### 9.1. Preparación

1. Cargar el escenario y resolver sus referencias.
2. Validar tipos, unidades, IDs, presencia de planes y consistencia cruzada.
3. Validar dominios físicos y compatibilidad representacional de Plan B.
4. Comprobar que las decisiones temporales utilizadas están explícitamente resueltas.
5. Construir el contexto temporal y las ventanas de T0 y objetivo desde H_inicio.
6. Evaluar T0: una intersección inicialmente alineada no necesita búsqueda.
7. Preparar estados locales, calendario, semilla y registro de resultados.

### 9.2. Búsqueda y aplicación

```text
Intersección activa en el instante definido por el calendario
                         ↓
Contexto fijo basado en el estado aplicado anterior
                         ↓
Dominio entero admisible
                         ↓
Optimizer
  ├─ generar o enumerar candidatos según el método seleccionado
  ├─ validar restricciones y admisibilidad temporal definida
  ├─ construir fenotipo
  ├─ evaluar contra Plan B en un marco compatible
  ├─ preservar BEST y obligaciones de población
  └─ devolver candidato y motivo de parada interna
                         ↓
Comprobar no regresión y contrato de aplicación
                         ↓
Aplicar mediante ejecutor simulado y registrar tiempo efectivo
                         ↓
Actualizar estado local y verificar alineación del estado aplicado
                         ↓
Congelar búsqueda si se cumple la igualdad exacta
                         ↓
Comprobar éxito global o límite de protección
```

El candidato elegido no equivale a un estado aplicado. Si la aplicación se difiere, distinguir ambos tiempos. No declarar éxito físico a partir de una evaluación nominal sin demostrar la correspondencia con la traza.

Si se incumple una invariante de aplicación, devolver el fallo o diagnóstico definido, no ajustar el verde por cuenta propia. La política temporal debe permitir detectar candidatos inadmisibles antes de elegirlos cuando corresponda.

### 9.3. Finalización

Generar un resultado estructurado con trayectorias, trazas, métricas, configuración efectiva, semillas, decisiones utilizadas y motivos de parada. Exportar resultados y generar visualizaciones si se solicitan.

El fitness se calcula dentro de la búsqueda; no necesita un simulador vehicular ni depende de generar imágenes.

## 10. Algoritmos y responsabilidades matemáticas

### 10.1. Duraciones y dominio físico

REQUISITO:

```text
R = C - A - G
C = G + A + R
0 <= G <= 99
0 <= R <= 99
G entero
```

Aquí A significa duración del amarillo, no Plan A. En código usar `yellow_s`.

Bajo la discretización entera propuesta, el dominio físico es:

```text
L_fisico = max(0, C - A - 99)
U_fisico = min(99, C - A)
```

La existencia de un verde físicamente válido exige `0 <= C - A <= 198`, además de C positivo y la validez temporal de amarillo. Esta condición no demuestra representabilidad de fronteras ni alcanzabilidad del objetivo.

### 10.2. Restricción por transición

Para el porcentaje vigente del 20 %:

```text
L = max(L_fisico, ceil(0.8 * G_actual))
U = min(U_fisico, floor(1.2 * G_actual))
dominio = enteros entre L y U, inclusive
```

Usar aritmética exacta para el cálculo de límites cuando sea posible: el 20 % equivale a factores 4/5 y 6/5. Evitar que errores de coma flotante modifiquen el dominio entero.

Ejemplos verificables:

- C=140, amarillo=3: dominio físico G=38…99.
- Con esos parámetros y G_actual=50: dominio siguiente G=40…60.
- G_actual=56: intervalo porcentual entero 45…67, antes de otras restricciones.
- G_actual=0, 1, 2, 3 o 4: el intervalo porcentual solo permite conservar el valor.
- Desde cualquier G_actual positivo no se alcanza cero con esta regla.

Mantener este dominio fijo durante todas las generaciones de una misma búsqueda. Actualizarlo solamente después de aplicar el siguiente estado.

### 10.3. Construcción temporal

El fenotipo requiere C, amarillo, G y un anclaje temporal. H_inicio es el comienzo de la observación, no sustituye ese anclaje.

Para una señal periódica ya definida, la operación matemática es consultar su posición módulo C desde un origen acordado. D01 debe especificar qué origen corresponde al candidato y cómo cambia o se conserva al variar G.

La extracción de un periodo completo debe conservar longitud y cantidades por color. Una fase puede aparecer repartida entre los extremos de la ventana; no significa que existan dos fases independientes.

No tratar el cierre circular de un fenotipo como evidencia de continuidad al conectar dos programaciones distintas. Esa continuidad corresponde a la política y al simulador.

### 10.4. Fitness de estado

```text
diferencias = cantidad de segundos con símbolos diferentes
F_estado = 1 - diferencias / C
```

Precondiciones: ventanas compatibles, misma duración de comparación y símbolos válidos. Devolver también los índices discrepantes si el nivel de detalle lo solicita.

El conteo no distingue la ubicación de los errores. No añadir pesos posicionales como si estuvieran ya acordados.

### 10.5. Fitness de fronteras: alternativa pendiente

Para C entero, al menos tres segundos, periodos iguales y las tres fronteras presentes, una alternativa circular es:

```text
d_j = min(abs(b_j - b_objetivo_j), C - abs(b_j - b_objetivo_j))
F_frontera = 1 - (d_RV + d_VA + d_AR) / (3 * floor(C / 2))
```

Las posiciones deben normalizarse al mismo periodo. La fórmula tiene rango [0,1] y solo alcanza 1 si las tres distancias son cero bajo esas precondiciones.

**PENDIENTE D06:** esta es una opción, no una fórmula aprobada. No resuelve fases ausentes, eventos coincidentes ni la elección entre distancias circulares y lineales. No implementarla por defecto mientras la decisión siga abierta.

### 10.6. Fitness compuesto y coincidencia exacta

```text
F = 0.5 * F_estado + 0.5 * F_frontera
```

Mantener los pesos del documento en el modo conforme. Para detectar éxito, verificar igualdad exacta de secuencia y de fronteras conforme a D06; no usar una tolerancia que acepte discrepancias. El valor presentado como 1 debe corresponder a esa igualdad, no a un redondeo visual.

### 10.7. No regresión, BEST y alcanzabilidad

- BEST de una búsqueda interna pertenece a un contexto fijo.
- El historial de mejores estados aplicados tiene otro ámbito; no reutilizar un candidato antiguo sin comprobar su admisibilidad actual.
- La no regresión entre ciclos solo es interpretable si las evaluaciones son comparables bajo D03.
- Registrar mesetas y estados repetidos; el desempate corresponde a D08.
- Un límite alcanzado no demuestra imposibilidad matemática.
- Una prueba exhaustiva de alcanzabilidad solo puede usar G como estado completo si se demuestra que no existen otras variables temporales relevantes.

### 10.8. Referencia exhaustiva propuesta

G tiene como máximo cien valores posibles. Proponer un optimizador exhaustivo que evalúe el dominio válido de un paso permite disponer de una referencia determinista para pruebas y para el prototipo.

Este método debe identificarse como `exhaustive`, no como GA. No está sujeto a fingir una población genética de quince. Conserva las restricciones del dominio y la función objetivo; no reemplaza la entrega posterior del GA ni demuestra una trayectoria global óptima.

El sistema no tiene como objetivo especificado minimizar el número de ciclos. No añadir esa meta ni penalizaciones de tiempo a la función objetivo sin una decisión nueva.

## 11. Diseño de simulación y visualización

### 11.1. Simulación semafórica inicial

Entradas: planes resueltos, solicitudes de aplicación válidas, contexto temporal y calendario acordado.

Salidas: estados por segundo, eventos de frontera, tiempos de aplicación, duraciones realmente ejecutadas y diagnósticos de continuidad.

La simulación debe:

- Ser determinista para entradas iguales.
- Poder ejecutarse sin interfaz gráfica.
- Mantener el reloj separado de los índices locales de transición.
- Procesar ciclos heterogéneos sin imponer una barrera temporal inexistente.
- Continuar la señal de intersecciones cuya búsqueda esté congelada, según D02.
- Verificar la ejecución desde H_inicio sin modificar segmentos ya transcurridos.
- Distinguir programación nominal y señal ejecutada.

Un calendario por eventos evita expandir obligatoriamente todas las señales al mínimo común múltiplo de sus ciclos. La resolución visible de las ventanas sigue siendo de un segundo conforme al plan.

### 11.2. Trazas y exportación

Propuesta de artefactos por ejecución:

| Artefacto | Contenido |
|---|---|
| `run.json` | Versión de esquema, método, estado global, motivos, semillas y métricas |
| `effective_config.json` | Configuración resuelta, planes y decisiones necesarias para reproducir el caso |
| `transitions.csv` | Estados anteriores y nuevos, G/R, índices locales y tiempos efectivos |
| `fitness.csv` | Componentes, total, discrepancias y errores de frontera |
| `phase_events.csv` | Cambios de color con intersección y tiempo |
| `states.csv` | Muestras por segundo cuando se solicite este nivel de detalle |
| `generations.csv` | Historial genético opcional, sin obligar a guardar cada fenotipo |
| Imágenes | Visualizaciones derivadas de los artefactos anteriores |

No sobrescribir resultados anteriores sin una política explícita. Versionar el esquema de exportación e incluir unidades. La lectura posterior debe permitir análisis y gráficos; la reanudación de optimizaciones no es un requisito actual.

### 11.3. Visualización semafórica

- Líneas R/V/A por intersección y por tiempo.
- Comparación de candidato o estado aplicado con Plan B.
- Fronteras y posiciones discrepantes.
- G y R por ciclo local.
- Evolución de F_estado, F_frontera, F y BEST.
- Momento de congelación y motivo de terminación.
- Offsets cuando D01 determine su referencia y significado.

Los gráficos consumen trazas y métricas existentes. No ejecutar el optimizador desde una función de dibujo ni reconstruir el fitness en la visualización.

### 11.4. Extensión vehicular

Antes de crear el simulador vehicular, definir topología, sentidos, longitudes, velocidades, salidas de vehículos y comportamiento ante señales. Decidir si se modelarán detención, aceleración y colas.

Solo entonces producir trayectorias, tiempos de viaje, paradas y diagramas tiempo–distancia. Sin estos datos, no presentar una animación como evidencia de onda verde ni inventar métricas vehiculares.

## 12. Preparación para el algoritmo genético

### 12.1. Contratos de extensión

| Contrato | Entrada | Salida o efecto permitido |
|---|---|---|
| `Optimizer` | SearchContext fijo, evaluador, validador y aleatoriedad explícita | OptimizationResult; no aplicar el candidato |
| `CandidateValidator` | G y contexto | Validez y razones de rechazo |
| `CandidateDecoder` | G y contexto temporal | TemporalWindow y fronteras derivadas |
| `FitnessEvaluator` | Fenotipo válido y objetivo compatible | FitnessBreakdown |
| `TransitionApplicationPolicy` | Estado aplicado, candidato y tiempo | Admisibilidad y solicitud de aplicación conforme a D02 |
| `SignalExecutor` | Solicitud y programación temporal | Estado efectivamente ejecutado y traza |
| `OptimizationObserver` | Eventos de búsqueda | Registro opcional; no modificar la selección |

Los contratos son conceptuales; no requieren crear una clase para cada función si una función tipada permite una implementación más simple.

### 12.2. Cromosoma y solución

El cromosoma individual es únicamente G para una intersección y un paso. La solución de toda la ejecución es un conjunto de trayectorias locales, no un vector genético de las seis intersecciones.

- Modificable por el GA: G entero.
- Derivado: R, secuencia, fronteras y fitness.
- Fijo dentro de una búsqueda: estado anterior, dominio, objetivo y contexto temporal.
- Fijo según el modelo inicial: amarillo y ciclo propios de cada intersección, sujeto a D04.
- No autorizado como gen: offset, ciclo, amarillo, velocidad o distancia.

### 12.3. Población y operadores

Propuesta a cerrar mediante D07:

```text
P_efectivo = min(candidates_per_intersection, cantidad_de_valores_validos)
E_efectivo = min(elite_count, P_efectivo)
```

La composición final depende también del alcance de la inclusión obligatoria del estado actual. Si debe preservarse en todas las generaciones y no es élite, reservar su plaza y ajustar la descendencia según la decisión documentada.

Los operadores deben generar enteros válidos y respetar el dominio original del paso. Si se usa rechazo, acotar los intentos y definir cómo se completa la población con valores válidos restantes; no permitir un bucle infinito al agotarse los valores únicos. No añadir una política de reparación o recorte sin documentarla como parte del operador.

No imponer un crossover multigénico artificial. Definir selección, reproducción y mutación apropiadas para un único entero mediante D08.

### 12.4. Paradas y métricas

Paradas internas: igualdad perfecta, diez generaciones sin mejora o cien generaciones, según configuración conforme y convención de conteo acordada. La falta de mejora se refiere a BEST; definir si la evaluación inicial cuenta como generación y cuándo se reinicia el contador.

Registrar evaluaciones, rechazos, diversidad, generaciones, BEST, semilla y motivo de parada. Para ejecución completa registrar ciclos locales, tiempo físico simulado y resultado por intersección.

El GA es estocástico: no exigir que toda semilla encuentre siempre el óptimo local salvo que el método lo garantice. Usar la referencia exhaustiva para medir calidad y comprobar casos controlados, además de verificar invariantes en todas las ejecuciones.

## 13. Validaciones y manejo de errores

### 13.1. Niveles de validación

| Momento | Comprobaciones |
|---|---|
| Carga | Archivos legibles, JSON válido, campos y versión conocidos, tipos correctos |
| Configuración | IDs únicos, referencias existentes, conjunto de intersecciones no vacío, entradas A/B completas |
| Unidades | C positivo y resolución temporal acordada; no aceptar NaN, infinitos o booleanos como duraciones enteras |
| Dominio físico | G/R dentro de límites, conservación del ciclo y dominio no vacío |
| Planes | Compatibilidad de C/amarillo, anclaje definido, representación posible y símbolos válidos |
| Parámetros generales | Límites positivos donde corresponda, pesos conforme al modo, máximo de ciclos explícito |
| Candidato | Integralidad, límites, ±20 % respecto al anterior y admisibilidad temporal definida |
| Fenotipo | Longitud, cantidades, orden y fronteras conforme a decisiones resueltas |
| Evaluación | Ventanas compatibles, componentes en [0,1], igualdad exacta coherente |
| Selección/aplicación | BEST válido, no regresión, momento efectivo y continuidad |
| Terminación | Todas alineadas para éxito; límite agotado es resultado incompleto |
| Exportación | Esquema, unidades, referencias y escritura completa |

No rechazar G=0 o R=0 alegando que están prohibidos por Plan.md. Si su semántica de fronteras aún no está implementada, informar una capacidad o decisión pendiente, no falsear la regla fuente.

### 13.2. Resultados y errores propuestos

- `COMPLETED`: todas las intersecciones cumplen la igualdad exacta y el contrato temporal de aplicación.
- `INCOMPLETE_LIMIT`: se alcanzó la protección sin completar la transición.
- `UNREACHABLE`: existe evidencia verificable de imposibilidad bajo las reglas; incluirla.
- `INVALID_CONFIGURATION`: entrada inconsistente, con ruta del campo y explicación.
- `UNRESOLVED_MODEL_DECISION`: falta una decisión necesaria para ejecutar ese caso.
- `INVARIANT_VIOLATION`: la ejecución o un componente incumple su contrato.
- `IO_ERROR`: fallo de lectura o exportación, separado del resultado matemático obtenido.

Estos nombres son una propuesta de API. Mantener la distinción semántica aunque cambien los nombres. Conservar el último estado válido y el diagnóstico; no devolver éxito ante una excepción ni reanudar con valores inventados.

Los errores de candidatos del GA son rechazos contabilizados. Los errores de configuración o invariantes deben propagarse al coordinador con contexto. No silenciar fallos mediante excepciones genéricas.

### 13.3. Riesgos y escalado

| Riesgo | Consecuencia | Mitigación |
|---|---|---|
| Anclaje incorrecto | Fitness alto para una programación equivocada | Casos de referencia y D01/D03 |
| Objetivo no representable | Búsqueda sin posibilidad de éxito | Validación estructural y diagnóstico |
| Ventanas válidas pero discontinuas | Amarillos o fases ejecutados incorrectamente | Simulación de enlaces y política explícita |
| Mesetas sin regresión | Repetición hasta el límite | Desempate documentado e historial; no prometer convergencia |
| Guardar todos los candidatos por segundo | Consumo elevado de memoria y disco | Historial configurable y caché contextual |
| Ciclos heterogéneos | Tiempos mal interpretados | Reloj común e índices locales |
| Estado global o constante seis | Escalado defectuoso | Mapas por ID y contexto independiente |
| Usar gráficos como verificación | Errores ocultos por presentación | Comprobar trazas y números antes de dibujar |

Una ronda de evaluación directa tiene coste aproximado proporcional a la suma de `P_i * K_i * C_i`, para población P, generaciones K y duración C por intersección activa. Medir antes de paralelizar. No compartir una caché indexada solo por G entre contextos temporales distintos.

## 14. Plan de implementación por etapas

### E0. Resolver el contrato conceptual

- **Objetivo:** cerrar semántica temporal y matemática necesaria para el núcleo.
- **Archivos:** `docs/conceptual_model.md`, `docs/decisions.md`, `docs/validation_strategy.md`.
- **Componentes:** definiciones y ejemplos, sin implementación de algoritmos.
- **Dependencias:** decisiones D01–D06 y D09–D11 para el comportamiento del núcleo. D07/D08 pueden continuar pendientes hasta preparar el GA, salvo el desempate que necesite el prototipo.
- **Resultado:** contrato temporal verificable y registro explícito de qué sigue abierto.

### E1. Configuración y dominio

- **Objetivo:** cargar y validar escenarios sin ejecutar optimización.
- **Archivos:** `pyproject.toml`, `config/*` del núcleo, `models/*`, `configuration/*`, documentación de configuración y fixtures sintéticos.
- **Componentes:** tipos, perfiles compartidos, cargador, esquema y validación cruzada; crear utilidades matemáticas mínimas solo donde sean necesarias.
- **Dependencias:** E0 para los campos temporales; puede adelantarse trabajo de validación independiente de las decisiones pendientes.
- **Resultado:** configuración efectiva tipada, sin duplicación y válida para N intersecciones.

### E2. Matemáticas, fenotipo y evaluación

- **Objetivo:** evaluar candidatos válidos de forma determinista y explicable.
- **Archivos:** `mathematics/*`, `evaluation/*`, modelos temporales necesarios y sus pruebas.
- **Componentes:** duraciones, dominio entero, ventanas, fronteras, F_estado y fórmula aprobada de F_frontera.
- **Dependencias:** E1; D01, D04, D05 y D06 resueltas para declarar completo el evaluador.
- **Resultado:** A, B y candidatos pueden compararse en un marco temporal coherente.

### E3. Infraestructura mínima funcional

- **Objetivo:** ejecutar una transición semafórica completa o devolver un motivo verificable de no completitud.
- **Archivos:** `algorithms/*`, `optimization/interfaces.py`, `optimization/search_context.py`, `optimization/exhaustive.py`, simulación semafórica, `application.py`, `cli.py`, `__main__.py`.
- **Componentes:** motor, política de aplicación, scheduler, trazas, terminación y referencia exhaustiva identificada como tal.
- **Dependencias:** E2; D02, D03, D09 y D10; desempate explícito para el método de referencia.
- **Resultado:** prototipo verificable sin GA y sin gráficos obligatorios. No declarar terminado el objetivo genético de Plan.md.

### E4. Persistencia y visualización

- **Objetivo:** hacer reproducibles y revisables los resultados.
- **Archivos:** `persistence/*`, visualizaciones semafóricas y de convergencia, documentación de formatos.
- **Componentes:** exportación, lectura y gráficos a partir de datos existentes.
- **Dependencias:** E3 y un contrato estable de trazas.
- **Resultado:** una ejecución puede analizarse y visualizarse sin repetir la optimización.

### E5. Algoritmo genético

- **Objetivo:** incorporar la búsqueda requerida por Plan.md detrás del contrato existente.
- **Archivos:** `optimization/genetic/*`, pruebas genéticas y actualización de configuración/documentación.
- **Componentes:** población, élites, operadores, BEST, semilla, paradas y observación.
- **Dependencias:** E3; D07 y D08 resueltas. Reutilizar E4 para análisis si ya está disponible.
- **Resultado:** GA intercambiable con la referencia de pruebas, sin reescribir simulación ni motor.

### E6. Escalado y robustez

- **Objetivo:** verificar el crecimiento más allá de seis intersecciones y medir recursos.
- **Archivos:** `scripts/benchmark_scaling.py`, fixtures adicionales, pruebas de integración y documentación de medidas.
- **Componentes:** medición y optimizaciones justificadas por resultados; evitar anticipar concurrencia.
- **Dependencias:** E3–E5 estables.
- **Resultado:** capacidad conocida, consumo medido y ausencia de supuestos fijos de seis intersecciones.

### E7. Simulación vehicular y evaluación de onda verde — FUTURO

- **Objetivo:** evaluar progresión real dentro del modelo de tráfico que se acuerde.
- **Archivos:** `config/corridor.json`, modelos de enlaces/vehículos que se definan, `traffic_simulator.py`, `time_distance.py` y pruebas.
- **Componentes:** topología, movimiento, métricas y representación tiempo–distancia.
- **Dependencias:** requisitos vehiculares nuevos y núcleo validado.
- **Resultado:** trayectorias y métricas vehiculares sustentadas; no confundir con el fitness original.

### E8. Integración con controladores — FUTURO

- **Objetivo:** conectar el sistema con un equipo real mediante un adaptador verificable.
- **Archivos:** `integration/*`, pruebas contra un controlador simulado y documentación del protocolo.
- **Componentes:** lectura, aplicación, confirmación y tratamiento de fallos según capacidades reales.
- **Dependencias:** contrato del hardware, sincronización temporal y política de aplicación compatibles.
- **Resultado:** integración demostrada para el equipo elegido. La simulación inicial no acredita por sí sola este resultado.

## 15. Pruebas necesarias por etapa

Las pruebas deben comprobar resultados o invariantes independientes, no copiar las mismas fórmulas de implementación como única evidencia. Los siguientes comandos son instrucciones para etapas futuras, no pruebas ejecutadas durante la creación de este documento.

| Etapa | Pruebas y evidencia necesarias |
|---|---|
| E0 | Resolver manualmente ventanas desde las tres fases, ejemplo de dos ciclos distintos, fases nulas y caso alcanzable en un paso; documentar entradas y salidas esperadas |
| E1 | JSON inválido, campos desconocidos según esquema, IDs duplicados, referencias rotas, planes incompletos, escenario vacío, unidades, parámetros contradictorios y configuración válida con 1, 6 y 7 intersecciones |
| E2 | Conservación del ciclo, dominio físico, límites enteros, G=0…4, rotación corregida, fronteras en índice cero, fases divididas entre extremos, fases nulas según D06, igualdad exacta, rango de fitness y ventanas incompatibles |
| E3 | Casos A=B, transición alcanzable, objetivo incompatible, bloqueo demostrado, agotamiento de límite, no regresión, congelación, continuidad de fase, ciclos diferentes, tiempos de aplicación, conteo de T0 y salida CLI |
| E4 | Exportar y volver a leer sin pérdida semántica; rechazar esquema incompatible; reproducir gráficos desde archivos; comprobar valores y límites de ejes contra trazas sin depender de igualdad exacta de píxeles |
| E5 | Actual obligatorio, unicidad, poblaciones de 1/4/5/10/15 valores, operadores dentro del dominio fijo, BEST no decreciente, conteo de estancamiento, cien generaciones como límite, igualdad perfecta inmediata y reproducibilidad con semilla |
| E6 | Escenarios con más de seis intersecciones, ciclos heterogéneos, independencia de IDs, consumo de memoria e historial, tiempos de evaluación y ausencia de cachés cruzadas incorrectas |
| E7 | Viajes y encuentros semafóricos de resultado conocido, tiempos por enlace, reglas de detención y métricas conforme al modelo acordado |
| E8 | Confirmaciones, rechazos, retrasos, pérdida de conexión, lectura de estado y continuidad usando un doble del controlador; después, pruebas autorizadas sobre el equipo |

### 15.1. Pruebas de propiedades

- Toda ventana periódica de longitud C conserva los conteos del ciclo nominal.
- Todo valor del dominio calculado satisface las restricciones correspondientes.
- Si el estado anterior es válido, debe pertenecer al dominio porcentual y físico siguiente; si otra política lo excluye, diagnosticar la incompatibilidad con R16.
- Todo fenotipo válido tiene longitud C y símbolos admitidos.
- El fitness permanece en [0,1]; igualdad exacta produce 1 bajo el contrato acordado.
- Congelar la optimización no altera la ejecución del plan alcanzado.
- Añadir una intersección no modifica los resultados de otra cuando no existe una dependencia funcional definida.
- Ejecutar sin gráficos conserva exactamente los resultados numéricos.

### 15.2. Contraste del GA

Comparar resultados con la referencia exhaustiva para contextos idénticos. Medir diferencia de fitness, evaluaciones y tasa de éxito en escenarios sintéticos con semillas registradas. Las pruebas estrictas de óptimo deben usar casos donde el resultado esté garantizado; evitar pruebas aleatorias inestables que exijan convergencia universal.

### 15.3. Ejecución de comprobaciones

Al adoptar pytest en el proyecto, usar `python -m pytest tests/unit`, `python -m pytest tests/integration` y `python -m pytest tests/properties` según las carpetas ya implementadas. Ejecutar el conjunto relevante tras cada cambio y la regresión necesaria antes de cerrar una etapa.

No declarar una etapa validada porque la colección esté vacía o porque sus pruebas críticas estén omitidas. Registrar comandos, resultados y decisiones pendientes en la entrega de cada etapa.

## 16. Criterios para considerar cada etapa terminada

### 16.1. Criterios específicos

| Etapa | Criterio de cierre verificable |
|---|---|
| E0 | Las decisiones necesarias para el núcleo tienen resolución, ejemplos y consecuencias; los pendientes del GA y extensiones están delimitados. No quedan supuestos temporales ocultos |
| E1 | Los escenarios se convierten en modelos válidos o errores explicables; parámetros compartidos no se duplican; las pruebas correspondientes pasan |
| E2 | Ventanas y fronteras correctas para los casos aprobados; fitness reproducible; todos los candidatos inválidos quedan fuera de evaluación; no se usa una fórmula de fronteras sin resolver D06 |
| E3 | Una ejecución por CLI devuelve trayectoria y traza verificables o un resultado incompleto/diagnóstico correcto; maneja ciclos distintos, congelación y límite; no afirma que la referencia exhaustiva sea GA |
| E4 | Los artefactos contienen configuración efectiva, unidades, motivos y métricas; pueden leerse para reconstruir análisis y gráficos sin volver a buscar soluciones |
| E5 | El método genético respeta todas las restricciones de población y estado, conserva BEST, reproduce ejecuciones con semilla y satisface los casos de contraste acordados; no modifica otras capas para ocultar defectos |
| E6 | Añadir intersecciones solo requiere configuración; se publican medidas reproducibles y límites observados; no se prometen objetivos de rendimiento no establecidos |
| E7 | Existe una especificación vehicular aprobada y sus métricas coinciden con casos de referencia; los diagramas representan trazas del simulador |
| E8 | El adaptador demuestra aplicación y lectura coherentes con el controlador elegido, incluidos fallos; se distingue lo probado en simulación de lo probado físicamente |

### 16.2. Criterios comunes de calidad

- La etapa cumple su alcance sin introducir decisiones funcionales no documentadas.
- Las dependencias y decisiones necesarias están resueltas; los pendientes restantes se identifican claramente.
- Las pruebas pertinentes pasan y su evidencia está registrada.
- Los errores no se ocultan y los resultados incompletos no se etiquetan como éxito.
- No se han duplicado parámetros, fórmulas ni lógica entre capas.
- La configuración y los formatos afectados están documentados.
- Los cambios son incrementales y se revisó su alcance frente al estado previo del repositorio.
- No se exige crear módulos futuros para cerrar una etapa presente.

### 16.3. Definición de entregables

- **Infraestructura mínima funcional:** E1–E3, precedidas por las decisiones necesarias de E0. Permite validar el modelo mediante el método de referencia explícito.
- **Núcleo conforme al objetivo genético del plan:** E1–E5 con decisiones resueltas y pruebas aprobadas; E3 por sí sola no cumple el objetivo del GA.
- **Capacidad de crecimiento verificada:** E6, con medidas y escenarios documentados.
- **Evaluación vehicular e integración real:** E7 y E8 son alcances posteriores y no deben afirmarse completados por disponer de simulación semafórica.

**Siguiente acción recomendada para el futuro implementador:** revisar la fuente y cerrar E0 con ejemplos temporales concretos. Después avanzar por etapas, comenzando por configuración, dominio y matemáticas; incorporar el GA únicamente cuando su contrato y el evaluador estén definidos.
