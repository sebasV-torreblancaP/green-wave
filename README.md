# Green Wave: ciclos físicos de 140 s

Cada controlador ejecuta una secuencia continua VERDE → ÁMBAR → ROJO → VERDE.
Sus inicios son `offset_i + k*C`, con C = 140 s. El amarillo sigue configurado
en 3 s. Cada orden de reparto entra en vigor al iniciar un ciclo local;
nunca interrumpe una fase ya iniciada.

## Transición implementada

Se cambia el reparto, conservando los inicios de verde:

```text
G[i,k] = base[i] + min(objetivo[i] - base[i], k*paso[i])
A[i,k] = amarillo configurado
R[i,k] = C - G[i,k] - A[i,k]
t[i,k+1] = t[i,k] + C
```

El planificador también admite rampas decrecientes. `paso[i]` no supera
`green_step_s` ni `floor(base[i]*max_green_change_fraction_per_cycle)`.
Ese porcentaje limita además la desviación total respecto a la base,
como exige la auditoría existente.

Los offsets ideales de SUBIDA y BAJADA son incompatibles con inicios fijos.
El nuevo objetivo de BAJADA es una **banda de salidas que llega en verde a
todos los semáforos**, a 35 km/h, en lugar de hacer coincidir cada llegada
con el inicio de verde. Los offsets permanecen en
`[0,18,45,59,91,113]`. Este objetivo no reproduce los offsets ideales
originales de BAJADA ni su anchura de banda.

Con ±20 % respecto a la base no existe banda BAJADA. Para una banda mínima
de 1 s, el límite mínimo uniforme es **25/43 ≈ 58,139535 %**. Se configura
`0.581396`, redondeado hacia arriba para conservar capacidades enteras.
El algoritmo enumera todos los umbrales de verde entero con aritmética
racional y escoge el primero con banda suficiente; no muestrea salidas.

La variante modifica S3 de 55 a 65 s y S5 de 43 a 68 s. Los otros verdes
permanecen en la base. La rampa usa incrementos de 1 s y necesita **25 ciclos**,
sin ciclos de relleno. Los verdes finales son `[60,40,65,53,68,65]` y los rojos
`[77,97,72,84,69,72]`. La banda final de salida desde S6 es
**[113,114.228571…) s módulo 140**, aproximadamente 1,23 s por ciclo.

## Ejecución y duración

En PowerShell, usando el intérprete del proyecto:

```powershell
& .venv/Scripts/python.exe -m unittest discover -s tests -v
& .venv/Scripts/python.exe main.py --no-show --duration-s 7200
& .venv/Scripts/python.exe plot_cycles.py --no-show --duration-s 7200
```

Ambas vistas aceptan `--config ruta.json`. `--duration-s` establece el
horizonte mínimo y añade ciclos estables de BAJADA si es necesario. Nunca
trunca la transición ni reduce `cycles_down`. El horizonte se redondea hacia
arriba a ciclos completos: 7200 s da 7280 s con esta configuración.

Las imágenes generadas son `green_wave.png`, `transition.png` y
`semaphore_cycles.png`; los gráficos usan los mismos eventos que el histórico.
La gráfica de BAJADA utiliza los verdes finales, no los verdes base.

## Parámetros de la variante

| Parámetro | Valor | Función |
| --- | ---: | --- |
| `cycle.common_cycle_s` | 140 | Duración física; no se modifica para coordinar |
| `cycle.yellow_s` | 3 | Amarillo de cada ciclo físico |
| `cycle.green_base_s` | [60,40,55,53,43,65] | Plan inicial y referencia porcentual |
| `transition.max_green_change_fraction_per_cycle` | 0.581396 | Máximo ajuste por ciclo y respecto a la base |
| `transition.green_step_s` | 1 | Paso de la rampa, en segundos enteros |
| `transition.min_down_band_s` | 1 | Anchura mínima de la banda BAJADA |
| `transition.max_transition_cycles` | 200 | Máximo permitido; la rampa usa solo lo necesario |
| `transition.min_green_s`, `min_red_s` | 1, 1 | Mínimos físicos |
| `simulation.cycles_up`, `cycles_down` | 3, 10 | Ciclos previos y mínimo posterior |
| `simulation.min_duration_s` | 3600 | Horizonte mínimo, ampliable por CLI |

Distancias, velocidades, IDs, offsets iniciales, modo manual/calculado y
parámetros de trayectorias conservan sus funciones. Los tiempos de control
deben ser segundos enteros. `optimize_target_phase` se conserva por
compatibilidad, pero no autoriza mover inicios: la API solo permite una
referencia común cuando los offsets relativos ya coinciden.

## Histórico y auditoría

Cada ejecución guarda una carpeta independiente en `historico/` y actualiza
`historico/latest.json`. La función `audit_history` conserva sus verificaciones.

- `controller_cycles.csv`: ciclos locales completos, incluidos los que
  cruzan los extremos del horizonte; inicio, fin, G, A, R y etapa.
- `states.csv`: eventos reales, recortados solo en los extremos del horizonte.
- `frames.csv`: ocupación de esos eventos por ventanas globales de 140 s.
  Estas ventanas son vistas; no reprograman el controlador. Sus tiempos de
  color pueden diferir del reparto de un ciclo local que las atraviesa.
- `cycles.csv`: intervalos observados entre verdes consecutivos y fases
  reales dentro de cada intervalo, medidos por la auditoría existente.
- `audit.json`, `audit.txt`: auditoría independiente de los CSV guardados.
- `run.json`: objetivo por banda, offsets ideales originales, offsets y
  verdes realmente usados; no afirma alcanzar los offsets ideales.
- `physical_verification.json`: verificación adicional del CSV físico,
  límites por ciclo, correspondencia exacta con eventos y banda final.
- `bajada_arrivals.csv`: llegadas de vehículos a todos los semáforos,
  contrastadas con los eventos guardados de la BAJADA estable.

```powershell
& .venv/Scripts/python.exe history.py --latest
& .venv/Scripts/python.exe verify_fixed_cycle.py historico/NOMBRE_EJECUCION
& .venv/Scripts/python.exe diagnose_fixed_cycle.py --config config.long.before.json
```

`config.long.before.json` conserva el límite original de 20 %. Con el nuevo
algoritmo se rechaza como inalcanzable y se informa el mínimo necesario;
no se genera una transición inválida. Los históricos anteriores permanecen
disponibles para auditar el fallo de 49–148 s.

## Limitaciones

La banda final es estrecha. Es una demostración mínima de coordinación,
no un plan de capacidad recomendado para tráfico real. Ampliar la banda
requiere más verde; el diagnóstico calcula el mínimo para el ancho solicitado.
No se modelan colas, aceleraciones, fases de giros ni movimientos conflictivos.
La certificación real de un controlador requiere esos datos adicionales.
