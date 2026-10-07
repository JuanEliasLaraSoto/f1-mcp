# Consistencia del piloto medida sobre residuos, no sobre tiempos brutos

**Fecha:** 2026-10-07

## Problema

La primera versión de `compare_drivers` medía la consistencia como la desviación típica
de los tiempos por vuelta "limpios". Con datos reales (Monza 2025, LEC vs HAM) salía
~1.1 s, demasiado alta para un piloto de F1 en ritmo de carrera.

La causa: en una carrera el tiempo por vuelta tiene **tendencia**. El coche mejora
~0.055 s/vuelta al quemar combustible (~3 s en 53 vueltas) y cada stint tiene su propia
degradación. La desviación típica bruta medía esa evolución del coche, no la regularidad
del piloto. Además, el filtro del 107% de la mediana deja pasar vueltas de entrada a
boxes (~5 s más lentas).

## Decisión

Medir la consistencia sobre los **residuos**:

1. Por cada stint, ajustar una recta tiempo = a + b·vuelta (mínimos cuadrados).
2. Calcular los residuos respecto a la recta de su stint.
3. Quitar outliers de forma robusta: |r − mediana| > 3σ, con σ = 1.4826·MAD.
4. Consistencia = desviación típica de los residuos restantes.

Se mantiene la desviación bruta en la salida para que se vea la diferencia.

## Efecto secundario: menos peticiones

Necesitar también los stints habría subido `compare_drivers` a 5 peticiones simultáneas
(vueltas y stints de cada piloto + pilotos), por encima del límite gratuito de OpenF1
(3 req/s). Se pasa a pedir vueltas y stints **de toda la sesión** en una petición cada
uno y filtrar en local: 3 peticiones en total.

## Verificación

Test con datos sintéticos (tendencia de −0.1 s/vuelta + ruido de ±0.1 s + una vuelta
con +5 s): la desviación bruta supera 0.5 s y la consistencia sobre residuos queda
por debajo de 0.2 s, recuperando el ruido introducido.
