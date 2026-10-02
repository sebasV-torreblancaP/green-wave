# Diagnóstico de la transición con ciclo físico fijo

## Restricción matemática

En el modelo actual hay una secuencia G → A → R y un inicio de verde por
ciclo local. Si cada secuencia dura C = 140 s y no hay saltos ni solapamientos,
el inicio siguiente es necesariamente t[i,k+1] = t[i,k] + C. Por inducción,
t[i,k] = t[i,0] + k C. Su offset módulo C es constante.

Modificar G y compensarlo exactamente en R no cambia esta conclusión.
Una referencia del controlador q[k] = k C puede coexistir con un inicio
t[i,k] = q[k] + fase[i,k], pero entonces el intervalo físico entre verdes
es C + fase[i,k+1] - fase[i,k]. Tener una referencia fija no garantiza una
secuencia física de 140 s. La auditoría actual mide esta última y debe seguir
haciéndolo. El número de ciclos disponible no altera esta restricción.

## Alternativas consideradas

1. Secuencias locales explícitas de 140 s, con inicios fijos y cambios de
   reparto. Conservan continuidad y duración física, pero solo alcanzan
   objetivos cuyos offsets relativos ya coinciden.
2. Referencia periódica de 140 s con fases móviles. Permite alcanzar offsets
   diferentes si se programan eventos continuos y se respetan los mínimos,
   pero implica intervalos físicos variables entre verdes. No satisface la
   interpretación estricta del ciclo físico; no debe presentarse como tal.
3. Inicios fijos y cambios de reparto para obtener una ventana de paso en
   BAJADA. Puede funcionar en otros corredores, sin reproducir necesariamente
   los offsets objetivo. En este corredor no existe ventana ni siquiera
   usando simultáneamente todos los verdes máximos permitidos.

La alternativa 1 corresponde al ciclo físico estricto del modelo actual.
No permite completar la transición solicitada con los planes configurados.
La alternativa 2 requiere aceptar explícitamente la diferencia entre
referencia de controlador e intervalo físico entre verdes; no se ha
implementado como si cumpliera ambos requisitos.

## Datos del corredor

Offsets SUBIDA: [0, 18, 45, 59, 91, 113].
Offsets BAJADA antes de desplazar la referencia: [85, 49, 136, 107, 44, 0].
Los desplazamientos comunes necesarios para hacerlos coincidir serían
[55, 109, 49, 92, 47, 113] módulo 140. Son distintos, por lo que ninguna
referencia común los iguala.

Verdes máximos permitidos respecto a la base:
[72, 48, 66, 63, 51, 78] s. Manteniendo los inicios de SUBIDA, la intersección
de las ventanas de salida de BAJADA a 35 km/h es vacía con estos máximos.
Verificación reproducible: `diagnose_fixed_cycle.py`.

## Reproducción larga del algoritmo existente

Configuración: `config.long.before.json`, 10 ciclos de SUBIDA, máximo de
transición de 200 ciclos y 30 ciclos estables de BAJADA. El algoritmo existente
elige 4 ciclos de transición. Horizonte: 6160 s = 102 min 40 s.

Histórico: `historico/20261002T192957_679667Z/`.

- 25 tests existentes pasan.
- 261 ciclos observados completos; 28 tienen duración diferente de 140 s.
- Duraciones observadas entre 49 y 148 s.
- Un cambio de color fuera de secuencia.
- Todas las sumas programadas por ventana son 140 s.
- Los ciclos observados exclusivamente en las etapas estables de SUBIDA y
  BAJADA son constantes; el fallo aparece al cambiar de plan.
- El plan final coincide con los offsets BAJADA desplazados:
  [24, 128, 75, 46, 123, 79]. Esto no demuestra una transición válida.

La auditoría se ejecutó otra vez sobre los CSV guardados, con
`history.py --latest`. Este histórico conserva la evidencia del fallo.

## Solución implementada: BAJADA por banda con inicios fijos

Se implementó la alternativa 3 con una variante de parámetros autorizada:
la coordinación se representa por una banda de llegadas dentro del verde,
no por la obligación de que cada llegada coincida con su inicio. El ciclo
físico sigue siendo VERDE → ÁMBAR → ROJO y dura 140 s.

Para una banda mínima de 1 s a 35 km/h, la mínima relajación uniforme del
límite respecto a los verdes base es **25/43 = 0.5813953488…**. Se configura
0.581396, redondeando hacia arriba. El buscador enumera todos los umbrales
de capacidad enteros, intersectando ventanas de salida con aritmética
racional. La primera capacidad suficiente demuestra el mínimo para ese
ancho de banda. No modifica la velocidad, las distancias, C, el amarillo,
los mínimos ni los verdes base.

Los verdes objetivo son [60,40,65,53,68,65]. S3 aumenta 10 s y S5 aumenta
25 s. En cada ciclo ambos avanzan como máximo 1 s y reducen su rojo en la
misma cantidad. La rampa tarda 25 ciclos reales. Al alcanzar el objetivo,
el reparto se mantiene. Los rojos finales son [77,97,72,84,69,72].

La banda final de salidas desde S6 es [113,114.228571…) s módulo 140, a
35 km/h. Se conserva la coordinación de SUBIDA al extender sus verdes.
El plan no reproduce los offsets ideales originales de BAJADA, que siguen
siendo inalcanzables bajo el requisito físico. `run.json` y la verificación
registran explícitamente esa limitación, sin sustituir los offsets ideales.

### Representación y archivos

- `green_wave.py`: rampa de verdes con inicios fijos, rechazo de offsets
  incompatibles y búsqueda mínima de la variante por banda.
- `continuous.py`, `timeline.py`: ciclos locales completos y eventos
  continuos; las ventanas globales se calculan a partir de esos eventos.
- `history.py`: solo se amplía la exportación con `controller_cycles.csv`
  y metadatos del modelo. **La función audit_history no se modifica.**
- `simulation.py`, `main.py`, `plot_cycles.py`: preparación común y horizonte
  configurable que conserva la transición completa y la BAJADA posterior.
- `visualization.py`: dibuja BAJADA con los verdes finales y muestra la
  duración física, sin regresar a los verdes base en la gráfica final.
- `diagnose_fixed_cycle.py`: informa la mínima variante por banda.
- `verify_fixed_cycle.py`: relee los CSV físicos, los contrasta exactamente
  con los eventos y verifica viajes sobre los eventos reales de BAJADA.
- `config.json`, `README.md` y tests: parámetros y contrato físico actualizados.

### Validación antes/después

Ejecución posterior de 7280 s = **121 min 20 s**, con 3 ciclos previos,
25 de transición y 24 posteriores. Histórico del simulador:
`historico/20261002T195726_697779Z/`. La segunda vista reproduce el mismo
resultado en `historico/20261002T195741_044770Z/`.

| Comprobación | Antes, 6160 s | Después, 7280 s |
| --- | ---: | ---: |
| Ciclos observados completos | 261 | 306 |
| Ciclos distintos de 140 s | 28 | 0 |
| Duración mínima/máxima | 49/148 s | 140/140 s |
| Cambios fuera de secuencia | 1 | 0 |
| Fases fuera de duración/mínimos | 10 | 0 |

La comprobación posterior confirma además:

- Cada fila de `controller_cycles.csv` suma 140 s y enlaza exactamente con
  la siguiente; el amarillo físico siempre dura 3 s.
- Cada par de inicios de verde observados está separado por 140 s.
- Cada verde cumple su límite respecto a la base y el incremento por ciclo
  no supera 1 s. Los mínimos de verde y rojo se conservan.
- `states.csv` coincide exactamente con los eventos de los controladores.
- Todas las ventanas globales cubren 140 s y concuerdan con los eventos.
- La banda de BAJADA completa satisface las llegadas en verde; 22 vehículos
  de prueba cruzan los seis semáforos en verde durante la etapa estable.

Se mantienen pruebas negativas que detectan históricos de ciclos deformados,
secuencias inválidas y CSV físicos manipulados. No se considera que los tests
por sí solos demuestren la validez del plan.

Resultado final de la suite: **33 tests pasan**. Las ejecuciones independientes
de `history.py` y `verify_fixed_cycle.py` sobre el histórico de la segunda
vista confirman los resultados de la tabla y los 22 recorridos en verde.

La banda de 1,23 s es estrecha y demuestra la mínima variante funcional;
no garantiza capacidad suficiente para tráfico real, colas ni movimientos
conflictivos no modelados. Ampliar la banda requiere mayor verde y puede
resultar imposible con los mínimos y límites configurados.
