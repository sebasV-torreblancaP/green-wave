# Resultado de la implementación diaria

## Resultado físico y alcance

Se implementó el calendario diario, consultas del estado real, separación de
nominal/temporal, objetivos A/B independientes, planificación en eventos locales,
recuperación nominal dinámica, exportación y verificación independiente.
No se implementó una reversión físicamente imposible fingiendo nuevos offsets.
`audit_history` conserva sus comprobaciones anteriores.

La representación anterior mezclaba ventanas globales con ciclos locales:
cambiar offsets entre ventanas desplazaba o truncaba los eventos y alteraba
el intervalo entre verdes. Ahora `LocalCycle` contiene el origen físico y
G/A/R completos; el timeline sólo observa esos eventos. La solicitud conserva
la fase y el tiempo transcurrido reales, incluso en tiempos fraccionarios.

Las alternativas son: mover offsets (requiere ciclos transitorios no constantes),
ampliar verdes para obtener una banda distinta (no recupera el objetivo nominal),
o conservar el ciclo físico y comprobar la alcanzabilidad exacta. Se usa esta
última, con recuperación nominal en los casos compatibles.

De t[k+1] = t[k] + 140 se deduce offset[k+1] = offset[k] módulo 140.
Por ello ΔG = -ΔR no produce corrección de offset. La solicitud de BAJADA
original es **TARGET NOT ACHIEVABLE UNDER CURRENT CONSTRAINTS**. El parámetro
que impide la reversión es el intervalo físico estrictamente constante entre
verdes; más ciclos, mayor porcentaje o menores mínimos no resuelven esa
incompatibilidad. La variante que conserva todos los invariantes exige offsets
objetivo iguales a los actuales y se ensayó explícitamente como caso separado.

## Antes y después

| Ensayo | Ciclos observados | Ciclos distintos de 140 s | Secuencias inválidas | Solicitud |
| --- | ---: | ---: | ---: | --- |
| Histórico anterior 20261002T182215_555568Z | 57 | 28 | 1 | Offset mutado |
| Día obligatorio 06:00–22:00 | 2466 | 0 | 0 | FAILED: B incompatible |
| Recuperación con objetivo compatible | 306 | 0 | 0 | SUCCESS |

Los ensayos tienen duraciones diferentes; el histórico anterior se conserva,
sin reescribirlo ni presentarlo como un experimento de idénticos parámetros.

**Día obligatorio:** [audit.txt](historico/20261002T215259_241981Z/audit.txt),
[verificación](historico/20261002T215259_241981Z/physical_verification.json),
[ciclos](historico/20261002T215259_241981Z/cycles.csv),
[detalle](historico/20261002T215259_241981Z/day_transition_detail.png).
Offsets A = [0,18,45,59,91,113], B = [57,26,119,94,39,0]. Nominal G =
[60,40,55,53,43,65], R = [77,97,82,84,94,72]. La solicitud de 13:37:24
se rechaza sin modificar los controladores. Los nominales se mantienen todo
el día. Horizonte solicitado 57600 s; auditado 57680 s (80 s de margen
declarado para ventanas completas). Todos los 2477 ciclos físicos exportados
cumplen C=140, A=3 y límites. Se reauditaron estados, ventanas y ciclos desde
los archivos guardados.

**Recuperación compatible:** [auditoría](historico/20261002T215246_410194Z/audit.txt),
[verificación](historico/20261002T215246_410194Z/physical_verification.json),
[ajustes](historico/20261002T215246_410194Z/transitions.csv),
[gráfico](historico/20261002T215246_410194Z/transition.png).
Parte de un histórico temporal importado con desviaciones [-2,+3,-1,+1,0,0],
creadas mediante pasos de 1 s y rojo compensado. En 303 s y hasta 3 ajustes
por controlador restaura exactamente los nominales, con 6002 s posteriores
estables. Objetivo B explícitamente compatible, no la BAJADA original.

Ambos ensayos tienen cero violaciones de ámbar, mínimos/máximos de verde,
mínimo de rojo, límites de modificación y secuencia.

## Código y pruebas

`day_simulation.py` maneja calendario, estados reales, solicitudes y métricas.
`green_wave.py` separa ajustes de duración/corrección de offset. `continuous.py`
y `timeline.py` separan ciclos físicos de ventanas. `history.py` exporta y
consulta; `verify_day.py` verifica los CSV. `main.py`, `plot_cycles.py`,
`visualization.py` y `diagnose_fixed_cycle.py` usan el modelo diario.
`simulation.py` ya no sustituye el objetivo por una banda distinta.

**74 tests pasaron**, incluidos solicitudes durante verde/ámbar/rojo,
continuidad de límites, tiempo fraccionario, medianoche, recuperación con ambos
signos, restauración, objetivos incompatibles, rechazo de falso SUCCESS,
manipulación de CSV y presupuesto insuficiente sin aplicación parcial.
También se ejecutaron simulación diaria, ensayo positivo, auditoría independiente
y verificación de ambos históricos. El código 2 del caso obligatorio expresa
FAILED de la solicitud, no un fallo del histórico físico.
