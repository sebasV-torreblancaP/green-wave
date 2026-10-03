# Decisiones del modelo

La columna «estado» refleja únicamente decisiones respaldadas por `Plan.md` o por una respuesta explícita posterior. Una propuesta del plan de implementación no equivale a un acuerdo funcional.

| ID | Estado | Contenido pendiente o acordado | Impacto |
|---|---|---|---|
| D01 | Pendiente | Referencia temporal de cada plan y frontera fija al cambiar G | Fenotipo y representabilidad |
| D02 | Pendiente | Momento de aplicación, continuidad y ejecución de una intersección congelada | Simulación |
| D03 | Pendiente | Calendario para ciclos heterogéneos y origen de la comparación | Motor y evaluación |
| D04 | Pendiente | Compatibilidad de ciclo y amarillo entre Plan A y Plan B | Validación de planes |
| D05 | Pendiente | Semántica real de H_inicio, resolución y extremos de ventanas | Entrada temporal |
| D06 | Pendiente | Fórmula de F_frontera y fases de duración cero | Fitness y éxito |
| D07 | Pendiente | Población menor de 15 e inclusión obligatoria del estado actual | GA |
| D08 | Pendiente | Operadores, empates y estancamiento | GA |
| D09 | Pendiente | Valor y conteo del máximo de ciclos | Terminación |
| D10 | Pendiente | Admisibilidad de alcanzar B en un único cambio válido | Motor |
| D11 | Pendiente | Parámetros experimentales frente al perfil conforme | Configuración |

El comando `--validate` comprueba estructura y restricciones físicas; su respuesta incluye `temporal_contract: unresolved`. No ejecuta la transición. El ejemplo de `config/examples/synthetic` contiene valores inventados exclusivamente para pruebas, identificados como sintéticos. `h_inicio_s` se acepta como entero en ese esquema provisional, sin afirmar una semántica de reloj real.

El modo `--run-reference` exige orígenes de verde explícitos y una métrica de fronteras explícita. Usa como política provisional el próximo inicio de verde de cada intersección y un máximo de ciclos local. El hecho de que el modo produzca una trayectoria no convierte estas alternativas en decisiones funcionales aprobadas. El método de búsqueda es exhaustivo y se identifica en la salida como tal.

Para cerrar una decisión, registrar fuente, alternativa elegida, motivo, ejemplo verificable e impacto en configuración y pruebas. No convertir una decisión pendiente en un valor predeterminado silencioso.
