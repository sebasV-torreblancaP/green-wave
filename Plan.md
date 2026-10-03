# Algoritmo Genético para Transición entre Plan A y Plan B

## 1. Objetivo

Diseñar un algoritmo genético (GA) capaz de realizar una transición progresiva entre dos planes de semáforos:

* **Plan A:** estado inicial.
* **Plan B:** estado objetivo.
* **6 intersecciones:** I1, I2, I3, I4, I5, I6.
* Cada intersección posee su propio ciclo, tiempos de amarillo y estado.
* La transición se realiza **ciclo por ciclo**.

El algoritmo no debe cambiar directamente de Plan A a Plan B.

La evolución será:

```text
Plan A
  ↓
T0
  ↓
T1
  ↓
T2
  ↓
T3
  ↓
...
  ↓
Plan B
```

El número de ciclos necesarios para completar la transición **no es un parámetro fijo**. Es un resultado del algoritmo.

---

# 2. Conceptos principales

## 2.1 Plan A

Representa el estado inicial del sistema.

Las seis intersecciones comienzan utilizando el estado correspondiente de Plan A.

---

## 2.2 Plan B

Representa el estado objetivo.

Plan B permanece **fijo durante toda la transición** y funciona como referencia para calcular el fitness.

Para cada intersección se obtiene una ventana temporal de exactamente un ciclo comenzando en `H_inicio`.

Ejemplo:

```text
Plan B:

RRRRVVVVVVVVAAARRRRRRVV...
    ↑
 H_inicio
```

La ventana correspondiente al ciclo puede representarse segundo a segundo:

```text
RRRVVVVVVAAARRRRRR
```

Donde:

```text
R = Rojo
V = Verde
A = Amarillo
```

Esta secuencia es la representación temporal principal del estado.

---

# 3. Inicio temporal de la transición

El usuario selecciona manualmente:

```text
H_inicio
```

Este instante representa el momento real en el que comenzará la transición.

No se debe asumir que `H_inicio` coincide con el inicio de un rojo, verde o amarillo.

Puede caer en cualquier punto del ciclo.

Por ejemplo:

```text
R R R R V V V V A A R R
        ↑
     H_inicio
```

Por lo tanto, la representación temporal siempre debe construirse desde `H_inicio`.

---

# 4. Estado temporal inicial T0

Para cada intersección:

1. Se toma su ciclo `C`.
2. Se toma `H_inicio`.
3. Se extrae desde Plan A una ventana temporal de duración `C`.
4. Se obtiene el estado real existente en ese momento.

De forma equivalente:

```text
Plan A
   │
   ├── H_inicio
   │
   └── H_inicio + C
```

La ventana puede comenzar en cualquier fase.

Por ejemplo, si el ciclo nominal es:

```text
V V V V V A A R R R R R R R
```

pero `H_inicio` cae en el tercer segundo de verde, la ventana temporal será algo como:

```text
V V A A R R R R R R V V V A
```

La secuencia temporal es la que representa el estado real de la intersección.

---

# 5. Parámetros de cada intersección

Cada intersección posee parámetros físicos propios.

Como mínimo:

```text
C = duración total del ciclo
A = duración del amarillo
```

El verde será la variable que optimiza el algoritmo:

```text
G = verde
```

El rojo se calcula automáticamente:

```text
R = C - A - G
```

Por lo tanto:

```text
C = G + A + R
```

No se utilizará `R` como un gen independiente.

---

# 6. Genotipo e individuo

El gen principal del individuo es:

```text
G
```

Ejemplo:

```text
C = 140
A = 3
G = 50
```

Entonces:

```text
R = 140 - 3 - 50
R = 87
```

El individuo queda definido por:

```text
G = 50
```

y el resto se deriva.

---

# 7. Fenotipo temporal

Aunque el gen sea solamente `G`, el algoritmo debe convertirlo en una secuencia temporal completa.

Ejemplo:

```text
G = 50
A = 3
R = 87
```

Estado nominal:

```text
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVAAARRRR...
```

Pero la secuencia utilizada por el fitness depende de `H_inicio`.

Si `H_inicio` cae durante el verde:

```text
VVVVVVVVVVAAARRRRRRRRRRRR...
```

Si cae durante el rojo:

```text
RRRRRRRRVVVVVVVVVVVVVVAAARRR...
```

Si cae durante el amarillo:

```text
AARRRRRRRRRRVVVVVVVVVVVVVV...
```

Por lo tanto:

> La secuencia temporal segundo a segundo es el fenotipo que realmente se compara con Plan B.

---

# 8. Representación temporal

La representación principal de una intersección será una cadena:

```text
RRRRVVVVVVAAARRRR
```

Cada posición representa un segundo.

Esto permite obtener directamente:

* estado del semáforo en cada segundo;
* duración de cada fase;
* cambios de fase;
* posición de las fronteras;
* comparación temporal con Plan B.

Ejemplo:

```text
RRRRVVVVVVAAARRRR
    ↑     ↑  ↑
   R→V   V→A A→R
```

---

# 9. Fronteras de fase

Además de comparar el estado segundo a segundo, se compararán las fronteras de las fases.

Las fronteras relevantes son:

```text
R → V
V → A
A → R
```

Ejemplo para Plan B:

```text
R→V = 40
V→A = 90
A→R = 93
```

Ejemplo de candidato:

```text
R→V = 35
V→A = 85
A→R = 88
```

La posición de estas fronteras forma parte del fitness.

---

# 10. Fitness

El fitness se calcula **independientemente para cada intersección**.

No existirá un único fitness global que controle las seis intersecciones.

Para cada intersección:

```text
F = 0.5 × F_estado + 0.5 × F_frontera
```

Donde:

```text
F_estado
```

mide la coincidencia segundo a segundo.

Y:

```text
F_frontera
```

mide la coincidencia de las fronteras de fase.

El resultado debe estar siempre en:

```text
0 ≤ F ≤ 1
```

---

# 11. Fitness de estado

Se compara la secuencia temporal del candidato con la secuencia temporal de Plan B.

Por cada segundo:

```text
Candidato == Plan B → coincide
Candidato != Plan B → no coincide
```

Por ejemplo:

```text
Plan B:
RRRRVVVVVVAAARRRR

Candidato:
RRRRVVVVAAARRRRRR
```

Se contabilizan los segundos diferentes.

Una formulación inicial es:

```text
F_estado =
1 - (segundos_diferentes / C)
```

Por lo tanto:

```text
0 = ninguna coincidencia
1 = coincidencia completa
```

La posición de los errores importa.

Dos candidatos pueden tener la misma cantidad de segundos diferentes pero producir secuencias diferentes.

---

# 12. Fitness de fronteras

Se comparan las posiciones de:

```text
R→V
V→A
A→R
```

entre el candidato y Plan B.

Condición obligatoria:

```text
F_frontera = 1
```

solamente cuando todas las fronteras coinciden exactamente.

La normalización exacta de esta parte queda pendiente de definir antes de implementar.

---

# 13. Fitness perfecto

Cuando:

```text
F = 1.0
```

la intersección se considera completamente alineada con el estado objetivo de Plan B.

En ese momento:

```text
INTERSECCIÓN = FROZEN
```

La intersección deja de participar en la optimización de los siguientes ciclos.

Su estado permanece fijo.

---

# 14. Evolución independiente de las intersecciones

Cada intersección puede alcanzar:

```text
F = 1
```

en un ciclo diferente.

Ejemplo:

```text
I1 → F=1 en T3
I2 → F=1 en T5
I3 → F=1 en T3
I4 → F=1 en T5
I5 → F=1 en T2
I6 → F=1 en T4
```

Por lo tanto, no todas tienen que terminar al mismo tiempo.

La transición completa termina cuando:

```text
F1 = F2 = F3 = F4 = F5 = F6 = 1
```

En el ejemplo anterior:

```text
TRANSICIÓN COMPLETA = T5
```

---

# 15. Candidatos por intersección

En cada ciclo de transición se generan:

```text
15 candidatos por intersección
```

Por ejemplo:

```text
I1:
G = 42
G = 44
G = 46
...
```

Las seis intersecciones evolucionan independientemente.

Si una intersección ya está congelada:

```text
F = 1
```

no necesita generar candidatos.

---

# 16. Inclusión obligatoria del estado actual

Uno de los 15 candidatos siempre debe ser el estado actual.

Por ejemplo:

```text
G_actual = 50
```

La población debe contener:

```text
50
```

Esto permite conservar el estado actual como referencia y evita que una generación elimine accidentalmente una solución ya válida.

---

# 17. Candidatos sin duplicados

Siempre que existan suficientes valores válidos:

```text
G1 != G2 != G3 ...
```

No deben existir candidatos duplicados.

Si existen menos de 15 valores válidos posibles:

```text
usar todos los valores disponibles
```

---

# 18. Restricción de cambio entre ciclos

El cambio de verde está limitado al:

```text
±20 %
```

Este porcentaje se aplica respecto al **estado anterior**, no respecto al Plan A original.

Para un ciclo:

```text
G_actual = 50
```

el siguiente ciclo puede utilizar:

```text
40 ≤ G_nuevo ≤ 60
```

Para:

```text
G_actual = 70
```

se obtiene:

```text
56 ≤ G_nuevo ≤ 84
```

La fórmula es:

```text
G_nuevo ∈ [G_actual × 0.80,
           G_actual × 1.20]
```

Después se aplican las restricciones del controlador.

---

# 19. Restricciones del controlador

El verde debe cumplir:

```text
0 ≤ G ≤ 99
```

El rojo se calcula:

```text
R = C - A - G
```

Y también debe cumplir:

```text
0 ≤ R ≤ 99
```

Además:

```text
G + A + R = C
```

Estas restricciones son obligatorias.

---

# 20. Validación de candidatos

Antes de calcular el fitness, cada candidato debe validarse.

Orden conceptual:

```text
Generar G
   ↓
¿G es entero?
   ↓
¿0 ≤ G ≤ 99?
   ↓
Calcular R
   ↓
¿0 ≤ R ≤ 99?
   ↓
¿G + A + R = C?
   ↓
¿Respeta ±20%?
   ↓
Candidato válido
```

Los candidatos inválidos no deben entrar al cálculo del fitness.

---

# 21. Estructura de la población

Población inicial:

```text
15 individuos
```

En cada generación:

```text
5 mejores
```

se conservan directamente.

Los otros:

```text
10 individuos
```

se generan mediante reproducción/mutación a partir de los mejores.

Conceptualmente:

```text
15 individuos
      │
      ├── 5 mejores
      │
      └── 10 nuevos
             ↑
        reproducción
        + mutación
```

---

# 22. Preservación del BEST

El algoritmo debe mantener permanentemente el mejor individuo encontrado.

Esto es importante porque:

> Una generación posterior puede tener un fitness peor que una generación anterior.

Ejemplo:

```text
Generación 10  → F = 0.94
Generación 50  → F = 0.93
Generación 100 → F = 0.91
```

El resultado final debe seguir siendo:

```text
BEST = 0.94
```

No se debe utilizar automáticamente el mejor individuo de la última generación.

---

# 23. Condiciones de parada del GA

Para cada intersección, el proceso interno de generaciones termina cuando se cumple una de estas condiciones:

### Condición 1 — Fitness perfecto

```text
F = 1.0
```

Se detiene inmediatamente.

### Condición 2 — Estancamiento

Si no existe mejora del BEST durante:

```text
10 generaciones
```

se detiene.

Se conserva el BEST encontrado.

### Condición 3 — Máximo de generaciones

Máximo inicial:

```text
100 generaciones
```

Si se alcanza:

```text
BEST
```

se convierte en el resultado.

---

# 24. Importante: generaciones ≠ ciclos de transición

Son dos niveles diferentes.

## Generación

Es una iteración interna del GA:

```text
Generación 1
Generación 2
Generación 3
...
```

Sirve para buscar el mejor estado para el siguiente ciclo.

## Ciclo de transición

Es un cambio real del estado de los semáforos:

```text
T0
T1
T2
T3
...
```

Por lo tanto:

```text
GA
└── muchas generaciones
       ↓
    produce
       ↓
siguiente ciclo T
```

---

# 25. Transición T0 → T1

Inicialmente:

```text
T0 = estado actual derivado de Plan A en H_inicio
```

Para cada intersección activa:

```text
1. Obtener G actual.
2. Calcular rango ±20%.
3. Generar 15 candidatos.
4. Incluir G actual.
5. Validar candidatos.
6. Construir secuencia temporal.
7. Comparar con Plan B.
8. Calcular fitness.
9. Ejecutar generaciones del GA.
10. Conservar BEST.
11. Seleccionar BEST como nuevo estado.
```

Al finalizar:

```text
T1 = resultado de la optimización
```

---

# 26. Transición T1 → T2

Se utiliza el resultado de T1 como nuevo estado.

Por ejemplo:

```text
T0:
G = 50

T1:
G = 56
```

El rango de T2 se calcula sobre:

```text
G = 56
```

y no sobre:

```text
G = 50
```

ni sobre el Plan A.

Por lo tanto:

```text
T1 → T2
```

utiliza:

```text
56 × 0.8
56 × 1.2
```

---

# 27. Proceso completo

```text
PLAN A
   │
   ▼
H_inicio
   │
   ▼
T0
   │
   ├───────────────┐
   │               │
   │          PLAN B fijo
   │               │
   ▼               │
Intersecciones     │
activas            │
   │               │
   ▼               │
15 candidatos      │
   │               │
   ▼               │
Validación         │
   │               │
   ▼               │
Secuencia temporal │
   │               │
   ▼               │
Fitness ◄──────────┘
   │
   ▼
Generaciones GA
   │
   ▼
BEST
   │
   ▼
T1
   │
   ▼
¿F = 1?
   │
   ├── Sí → congelar
   │
   └── No → siguiente ciclo
                │
                ▼
               T2
                │
               ...
                │
                ▼
         Todas F = 1
                │
                ▼
       TRANSICIÓN COMPLETA
```

---

# 28. Intersecciones congeladas

Cuando una intersección alcanza:

```text
F = 1.0
```

se congela.

Ejemplo:

```text
T1:
I1 activa
I2 activa
I3 activa
I4 activa
I5 activa
I6 activa

T3:
I1 = F1 → congelada
I3 = F1 → congelada

T4:
I5 = F1 → congelada

T5:
I2 = F1
I4 = F1
I6 = F1
```

Durante T5 solamente permanecen activas las intersecciones que todavía no alcanzaron el objetivo.

---

# 29. Condición de finalización global

La transición termina cuando:

```text
F1 = 1
F2 = 1
F3 = 1
F4 = 1
F5 = 1
F6 = 1
```

Es decir:

```text
∀i, Fi = 1
```

El número de ciclos utilizado será el resultado de la transición.

---

# 30. Máximo de ciclos de transición

Debe existir un límite de seguridad:

```text
MAX_TRANSITION_CYCLES
```

Este parámetro evita que el algoritmo quede ejecutándose indefinidamente.

No representa el número esperado de ciclos.

Es solamente un mecanismo de seguridad.

---

# 31. Parámetros generales iniciales

La configuración inicial propuesta es:

```text
candidates_per_intersection = 15

max_green_change_percent = 20

max_generations = 100

stagnation_generations = 10

target_fitness = 1.0

max_transition_cycles = configurable
```

Estos valores son iniciales y deberán observarse durante las pruebas reales.

No se consideran valores matemáticamente definitivos.

---

# 32. Organización de configuración

La configuración debe separar:

1. parámetros físicos de cada intersección;
2. parámetros generales del algoritmo.

Propuesta:

```text
config/
├── intersections/
│   ├── I1
│   ├── I2
│   ├── I3
│   ├── I4
│   ├── I5
│   └── I6
│
└── transition/
```

---

# 33. Configuración por intersección

Cada intersección debe contener sus parámetros particulares.

Por ejemplo:

```text
I1:
    cycle
    yellow
```

```text
I2:
    cycle
    yellow
```

etc.

Esto permite que cada intersección tenga:

```text
C diferente
A diferente
```

sin modificar el algoritmo.

---

# 34. Configuración general del algoritmo

Los parámetros generales deben estar separados:

```text
transition:
    candidates_per_intersection
    max_green_change_percent
    max_generations
    stagnation_generations
    target_fitness
    max_transition_cycles
```

De esta manera se puede cambiar el comportamiento del GA sin modificar las configuraciones físicas.

---

# 35. Principio de diseño

El algoritmo debe evitar reglas manuales innecesarias.

El usuario define:

* restricciones;
* límites físicos;
* Plan A;
* Plan B;
* `H_inicio`;
* función de fitness;
* parámetros del GA.

El algoritmo debe encargarse de buscar la transición.

No se deben introducir reglas arbitrarias como:

```text
7 candidatos para explorar
8 candidatos para explotar
```

ni forzar manualmente que los candidatos se acerquen a Plan B.

La dirección de la evolución debe surgir del fitness y del proceso genético.

---

# 36. Restricciones consolidadas

Las restricciones definitivas son:

1. `G` debe ser entero.
2. `0 ≤ G ≤ 99`.
3. `R = C - A - G`.
4. `0 ≤ R ≤ 99`.
5. `G + A + R = C`.
6. El cambio máximo entre ciclos es ±20%.
7. El amarillo permanece fijo.
8. El orden de fases permanece `R → V → A → R`.
9. La secuencia temporal se construye desde `H_inicio`.
10. El estado actual siempre debe estar entre los candidatos.
11. No se permiten candidatos duplicados cuando existan suficientes valores.
12. Solo candidatos válidos entran al cálculo del fitness.
13. El BEST debe preservarse.
14. El nuevo estado no debe provocar regresión respecto al mejor estado alcanzado.
15. Una intersección con `F=1` queda congelada.
16. Debe existir un máximo de ciclos de transición como protección.

---

# 37. Puntos pendientes antes de programar

El modelo conceptual está prácticamente definido.

Antes de comenzar la implementación todavía deben cerrarse dos detalles matemáticos.

## 37.1 Reproducción, crossover y mutación

Como el individuo tiene principalmente un solo gen:

```text
G
```

el crossover tradicional de múltiples genes no tiene demasiado sentido.

Debe definirse exactamente cómo los 5 mejores generan los 10 nuevos individuos.

Debe quedar definido:

* selección de padres;
* cálculo del nuevo `G`;
* método de mutación;
* porcentaje o intensidad de mutación;
* validación posterior.

La solución debe mantenerse simple y coherente con el hecho de que `G` es el gen principal.

---

## 37.2 Fórmula exacta de `F_frontera`

También falta cerrar la normalización de la diferencia entre las fronteras.

Debe definirse cómo transformar:

```text
distancia de frontera en segundos
```

en:

```text
fitness entre 0 y 1
```

Debe cumplirse obligatoriamente:

```text
todas las fronteras iguales
        ↓
F_frontera = 1
```

Y debe penalizarse progresivamente el desplazamiento de las fronteras.

---

# 38. Resultado esperado

El resultado final no será simplemente:

```text
Plan A → Plan B
```

Será una secuencia de estados intermedios:

```text
T0
T1
T2
T3
...
TN
```

donde cada ciclo representa una modificación limitada del estado anterior.

Cada intersección puede avanzar a una velocidad diferente:

```text
I1: T0 → T1 → T2 → T3 → congelada
I2: T0 → T1 → T2 → T3 → T4 → T5 → congelada
I3: T0 → T1 → T2 → T3 → congelada
...
```

La transición completa termina cuando todas las intersecciones alcanzan:

```text
F = 1.0
```

y por tanto coinciden con el estado temporal objetivo definido por Plan B.

---

# 39. Resumen conceptual

```text
                    PLAN A
                       │
                       ▼
                   H_inicio
                       │
                       ▼
                       T0
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
        Estado actual        PLAN B
              │                 │
              │          referencia fija
              │                 │
              └────────┬────────┘
                       ▼
                15 candidatos
                       │
                       ▼
                  Validación
                       │
                       ▼
              Secuencia temporal
                       │
                       ▼
                    Fitness
                       │
                       ▼
                 GA interno
                       │
                       ▼
                     BEST
                       │
                       ▼
                       T1
                       │
                       ▼
             repetir ciclo a ciclo
                       │
                       ▼
              algunas intersecciones
                  se congelan
                       │
                       ▼
              todas F = 1.0
                       │
                       ▼
             TRANSICIÓN COMPLETA
```

El objetivo es que el algoritmo encuentre automáticamente una trayectoria válida y progresiva desde el estado temporal de Plan A hasta el estado temporal de Plan B, respetando las restricciones físicas y de cambio establecidas.
