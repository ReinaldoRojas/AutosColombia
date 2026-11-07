# Autos Colombia

## Iteración RF-01 a RF-05 (alineada con el documento de diseño)

Esta etapa implementa los requerimientos RF-01 a RF-05 del documento «EA1 Diseño de sistema
de información». La pantalla *Control de acceso* se reemplaza por **Entrada** y **Salida**, y
la gestión de vehículos pasa a la ficha de cada cliente. Las secciones posteriores de este
archivo describen etapas anteriores y se conservan como historial.

| RF / HU | Qué hace | Dónde |
| --- | --- | --- |
| RF-01 / HU-01 Registrar cliente | Tipo y número de documento (único), nombres, apellidos, teléfono colombiano y correo opcional. Si el documento ya existe responde 409 con `cliente_id` y la pantalla abre su ficha. | `POST/GET/PATCH /clientes`, pantalla **Clientes** |
| RF-02 / HU-02 Vehículo asociado a un cliente | Todo vehículo nuevo exige `cliente_id`, `linea` y `fecha_pago`. PostgreSQL calcula `fecha_vencimiento = fecha_pago + 30 días` (RN-06). Un cliente puede tener varios vehículos. Tipos: `CARRO`, `CAMIONETA`, `MOTO`. | `POST /vehiculos`, ficha del cliente |
| RF-03 / HU-03 Consultar por placa | Devuelve vehículo, propietario, estado de la mensualidad, si está adentro y el cupo de su tipo. Placa inexistente: 404 «Vehículo no registrado» y botón para registrarlo. | `GET /estancias/vehiculo/{placa}`, pantalla **Entrada** |
| RF-04 / HU-04 Validar mensualidad | `VIGENTE`, `VENCE_HOY` (permite y avisa), `VENCIDA` (bloquea con días de mora), `SIN_PAGO` y `SIN_CLIENTE` (bloquean). La fecha es la del servidor en America/Bogota (RNF-11). | `app/services/mensualidad.py` |
| RF-05 / HU-05 Entrada, celda automática y recibo | El operario ya no elige celda: el sistema toma una libre del tipo del vehículo con `FOR UPDATE SKIP LOCKED`, de modo que dos puertas a la vez reciben celdas distintas. Guarda operador y puerta de entrada y genera el recibo `E-000001`. | `POST /estancias/entrada`, `GET /estancias/recibo/{numero}` |

Lo mínimo que RF-05 necesita fuera de esos RF:

- **Puertas**: tabla `puerta` con *Puerta 1* y *Puerta 2* (`GET /puertas`); la entrada exige
  `puerta_id`.
- **Tipo de celda**: solo `CARRO_CAMIONETA` o `MOTO`, para saber qué celda corresponde a cada
  vehículo. La migración crea las celdas 01–70 y 71–80 que no existan (RN-05). La pantalla
  **Celdas** se conserva y ahora elige el tipo de una lista.
- **Turno**: mientras no exista inicio de sesión (RNF-05), el operario elige su nombre y su
  puerta en la pantalla y queda guardado en el navegador.
- **Salida**: conserva su contrato (placa y operador). La búsqueda por recibo, la puerta de
  salida y RF-06 a RF-11 no hacen parte de esta entrega.

### Migración 0005

Revisar el SQL sin tocar la base y luego aplicarla:

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
Pop-Location
```

Datos existentes: los vehículos `AUTOMOVIL` pasan a `CARRO`; los vehículos anteriores quedan
sin cliente ni pago y **no podrán ingresar** hasta asociarlos (RF-04). Los tipos libres de
celda que contienen «MOTO» pasan a `MOTO` y el resto a `CARRO_CAMIONETA`. Las estancias
existentes quedan registradas en la Puerta 1.

### Pantallas nuevas

- `/operacion/entrada`: 1) placa, 2) verificación de vehículo, propietario y mensualidad,
  3) confirmar; muestra el recibo para imprimir (RNF-08: máximo 3 pasos).
- `/operacion/salida`: salida por placa con el operador del turno.
- `/gestion/clientes`: búsqueda, registro de clientes y sus vehículos con fecha de pago.

### Pruebas

`RUN_POSTGRES_TESTS=1` ejecuta además el recorrido real: mensualidad, celda automática por
tipo, recibo, cupo lleno de motos y concurrencia entre las dos puertas (misma placa y dos
vehículos a la vez). La prueba de esquema exige la revisión `0005`.

## Pantalla Control de acceso

Disponible en **Control de acceso** en la navegación y en
<http://127.0.0.1:4200/control-acceso>. Esta etapa añade únicamente frontend y
documentación; las secciones siguientes conservan resultados de etapas anteriores.

La entrada solicita placa, celda y operador. La placa se recorta y convierte a
mayúsculas. Los selectores cargan todas las páginas de los catálogos existentes
con `limit=100`, avanzando por offset hasta alcanzar total; no se limita la
selección a la primera página. Si una página falla, se bloquea el registro y se
ofrece **Actualizar catálogos**, sin presentar una lista parcial como completa.
El botón también permite recargar referencias creadas en otra pantalla.

La API no ofrece consulta de disponibilidad de celdas. La pantalla lo indica:
**la ocupación se valida al registrar**; ninguna opción se anuncia como disponible.
Los conflictos de vehículo dentro, celda ocupada y referencias inexistentes
muestran los mensajes en español devueltos por FastAPI.

La sección de consulta y salida distingue **Vehículo no registrado** de
**Fuera — Vehículo registrado sin estancia abierta**. Al estar dentro muestra
celda y fecha de entrada, y permite confirmar la salida con un operador. La
solicitud de salida contiene solo placa y operador_id; tras el cierre se consulta
de nuevo el vehículo. Cambiar la placa invalida el resultado anterior y descarta
respuestas de consultas previas que lleguen tarde. No se permite cerrar basándose
en el resultado de otra placa. Ante un error de salida se exige volver a consultar.

No se solicitan fechas ni horas. Las cadenas ISO recibidas se interpretan con su
offset original y se formatean con `Intl.DateTimeFormat`, zona **America/Bogota**,
independientemente de la zona del equipo. Las acciones en curso se bloquean para
evitar duplicados. Ante una respuesta perdida, consulta antes de reintentar:
la escritura podría haberse completado en el servidor.

### Iniciar en dos terminales PowerShell

Terminal 1, con el entorno virtual existente:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, con Angular CLI local:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd start -- --host 127.0.0.1 --port 4200
```

Detén con Ctrl+C una instancia anterior antes de volver a iniciar el mismo puerto.
Se reiniciaron ambos servidores para cargar las rutas backend ya implementadas y
el proxy frontend nuevo; no se modificó código del backend. El proxy incorpora
`/estancias/**` hacia `127.0.0.1:8000`; reinicia Angular si cambias esa configuración.

Comandos de compilación y pruebas ejecutados:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación.' }
npm.cmd test -- --watch=false
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas.' }
```

### Recorrido manual desde la pantalla

1. Desde Vehículos, Celdas y Operadores prepara dos vehículos, una celda y un
   operador de prueba con identificadores nuevos. Ejemplos: placas
   `PRUEBA-ACCESO-A-01` y `PRUEBA-ACCESO-B-01`, celda `PRUEBA-CELDA-01` de tipo
   libre y operador `PRUEBA ACCESO 01`, teléfono `001`. Cambia el sufijo si existe.
2. Abre Control de acceso y pulsa **Actualizar catálogos**. En Registrar entrada,
   escribe ` prueba-acceso-a-01 ` y selecciona tu celda y operador. Espera
   confirmación con placa normalizada, código de celda y fecha en Bogotá.
3. Consulta esa placa en la sección inferior: espera **Dentro**, la celda y la
   fecha de entrada. Repite Registrar entrada: espera **El vehículo ya está dentro**.
4. Intenta ingresar el vehículo B en la misma celda: espera **La celda está ocupada**.
5. Consulta A, selecciona el operador de salida y pulsa **Confirmar salida**.
   Espera confirmación y actualización automática a **Fuera**, sin estancia abierta.
6. Ingresa B en la misma celda: ahora debe aceptarse. Consulta B y registra su
   salida para dejar la celda libre. Al cambiar una placa consultada, desaparecen
   el estado anterior y el botón de confirmar hasta una consulta nueva.
7. Consulta una placa que no esté registrada: espera **Vehículo no registrado**.
   Los campos vacíos o con espacios deben impedir el envío. No hay campos de fecha.

El historial de estas pruebas manuales queda guardado por diseño. La API no ofrece
borrado de estancias; no intentes borrar sus referencias desde los CRUD. La limpieza
de la verificación automatizada de esta etapa se hizo por ids exactos de registros
nuevos, después de comprobar su identidad, sin añadir una operación de borrado a la API.

### Verificaciones y archivos de esta etapa

- **Compilación correcta y 38 pruebas aprobadas**, incluidas seis nuevas de acceso:
  recorrido paginado de catálogos, normalización, validación, conflictos, bloqueo
  de doble envío, invalidación de consultas tardías, salida con solo dos campos,
  actualización fuera y conversión de zonas horarias.
- **Recorrido real en navegador con FastAPI/PostgreSQL**: entrada, consulta dentro,
  rechazo duplicado, rechazo de celda ocupada, salida, consulta fuera, reutilización
  de celda y segunda salida. Se revisó la presentación de escritorio.
- Se limpiaron exclusivamente dos vehículos, una celda, un operador y sus dos
  estancias cerradas creados para la prueba con prefijo `TEST-ACCESO-8577CBD436`.
  Se verificó la ausencia de esas estancias después de la limpieza.
- **Pendiente**: revisión visual móvil y accesibilidad completa; catálogo real
  de más de cien registros (la paginación se probó con HTTP simulado); fallos de
  red provocados en navegador y carga prolongada. Las pruebas no afirman esos resultados.

Nuevos: `frontend/src/app/control-acceso/control-acceso.ts`, `.html`, `.css`,
`.spec.ts`, `frontend/src/app/models/estancia.ts` y
`frontend/src/app/services/estancias.service.ts`. Modificados:
`frontend/src/app/app.routes.ts`, `frontend/src/app/app.html`,
`frontend/proxy.conf.json` y este README. Se conservaron las pantallas existentes,
las dependencias y el backend. No se modificó el esquema ni se creó un commit.

## Servicio y endpoints de estancias

Se verificó antes de implementar que `0002` está aplicada y que existen la tabla
estancia, sus cuatro FK RESTRICT, ambos CHECK y los índices únicos parciales.
Esta etapa no modifica modelos, tablas, migraciones ni Angular.

| Método y ruta | Solicitud | Respuesta |
| --- | --- | --- |
| `POST /estancias/entrada` | placa, celda_id, operador_id | 201, estancia registrada |
| `POST /estancias/salida` | placa, operador_id | 200, estancia cerrada |
| `GET /estancias/vehiculo/{placa}` | placa en la ruta | 200, vehículo y estado actual; 404 si no está registrado |

Las respuestas de entrada/salida contienen `id`, `vehiculo_id`, `celda_id`,
`entrada`, `salida`, `operador_entrada_id` y `operador_salida_id`. Las fechas se
generan en el servidor y se devuelven en UTC. No se aceptan fechas ni id enviados
por el cliente. La salida tampoco acepta celda_id.

La consulta devuelve `vehiculo` con los datos del vehículo, `esta_dentro` booleano
y `estancia`. Cuando está fuera, `estancia` es null. Cuando está dentro, contiene
los siete campos de la estancia y `celda` con id, codigo y tipo; la fecha de ingreso
está en `estancia.entrada`. La consulta usa una sola sentencia para obtener ese
estado consistente. No devuelve historial ni permite editar o borrar estancias.

Las placas se recortan y convierten a mayúsculas. Los ids deben ser enteros JSON
positivos dentro del rango BIGINT; no se aceptan booleanos, cadenas numéricas,
nulos o campos extra. No se imponen reglas de compatibilidad entre tipos.

- 404: vehículo, celda u operador inexistentes.
- 409: vehículo ya dentro, celda ocupada o intento de salida sin estancia abierta.
- 422: datos inválidos o incumplimiento de restricciones de integridad.
- 503: fallo de base de datos, con mensaje genérico sin detalles internos.

`ServicioEstancia` ejecuta cada operación en una transacción. Las comprobaciones
previas ofrecen mensajes claros, pero la garantía ante entradas simultáneas reside
en los índices únicos de PostgreSQL; sus conflictos se convierten en 409 y la
transacción se revierte. La salida selecciona la estancia abierta con
`SELECT ... FOR UPDATE`, llama a `cerrar()` con la hora UTC del servidor y mantiene
el bloqueo hasta el commit. Una segunda salida concurrente obtiene 409 y no
sobrescribe fecha ni operador. Una respuesta se materializa antes del commit y
solo se devuelve si este termina correctamente. Si el reloj del servidor fuera
anterior a la entrada o el modelo no permitiera cerrar, se rechaza el cierre con
409 y sin cambios parciales.

### Iniciar el backend y ejecutar las pruebas (PowerShell)

Para cargar las rutas nuevas, detén con Ctrl+C cualquier instancia anterior sin
recarga y ejecuta en una terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

En otra terminal, usando la misma base configurada en `.env` y sin mostrarla:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
$valorAnterior = $env:RUN_POSTGRES_TESTS
try {
    $env:RUN_POSTGRES_TESTS = '1'
    .\.venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas.' }
} finally {
    $env:RUN_POSTGRES_TESTS = $valorAnterior
}
```

La suite no requiere un servidor externo: TestClient carga la aplicación real.
Las nuevas pruebas de concurrencia **confirman datos de prueba** para que sean
visibles a conexiones independientes. Usan nombres, placas y códigos
`TEST-EST-<UUID>`, y eliminan en `finally` solo sus estancias y referencias,
identificadas por sus ids. No eliminan datos previos ni hacen DDL. Las secuencias
pueden avanzar. Si se interrumpe abruptamente el proceso de pruebas, revisa sus
registros identificables antes de cualquier limpieza manual.

### Recorrido manual desde /docs

Abre <http://127.0.0.1:8000/docs>, grupo **Estancias**, y usa **Try it out** y
**Execute**. Este recorrido manual está documentado, pero no se ejecutó en
navegador durante esta etapa; sus resultados se comprobaron mediante TestClient
y PostgreSQL real.

1. Prepara dos vehículos, una celda y dos operadores nuevos desde sus CRUD en
   `/docs`. Usa placas y código exclusivos de prueba (por ejemplo,
   `DOCS-EST-A-20261019`, `DOCS-EST-B-20261019` y `DOCS-CELDA-20261019`, cambiando el
   sufijo si ya existen). Vehículo de ejemplo:
   `{"placa":"DOCS-EST-A-20261019","color":"Azul","modelo":2026,"marca":"Prueba","tipo":"MOTO"}`.
   Celda: `{"codigo":"DOCS-CELDA-20261019","tipo":"Libre"}`.
   Operadores: `{"nombre":"PRUEBA entrada","telefono":"001"}` y
   `{"nombre":"PRUEBA salida","telefono":"002"}`. Anota los ids reales.
2. Consulta GET con la placa del primer vehículo: espera 200,
   `esta_dentro: false` y `estancia: null`.
3. Envía la entrada con este ejemplo, **sustituyendo 101 y 201 por los ids reales**:

   ```json
   { "placa": " docs-est-a-20261019 ", "celda_id": 101, "operador_id": 201 }
   ```

   Espera 201, entrada UTC, salida y operador_salida_id nulos. Repite el ingreso:
   espera 409. Intenta ingresar el segundo vehículo en la misma celda: espera 409.
4. Consulta el primer vehículo: espera `esta_dentro: true`, estancia abierta,
   datos de celda y fecha de entrada. Una placa no registrada devuelve 404.
5. Envía salida, sustituyendo 202 por el id real del operador de salida:

   ```json
   { "placa": "DOCS-EST-A-20261019", "operador_id": 202 }
   ```

   Espera 200, salida UTC no anterior a entrada y operador_salida_id correspondiente.
   Repite: espera 409. Consulta nuevamente: fuera, estancia null.
6. Ingresa el segundo vehículo en la misma celda: ahora se espera 201. Registra
   también su salida al finalizar. El historial permanece guardado; esta API no
   ofrece eliminación de estancias. No intentes borrar referencias del historial.
7. Comprueba 422 con una placa vacía, id nulo o un campo `celda_id` en salida.
   Usa un id que hayas comprobado inexistente para probar 404 de celda u operador;
   el rechazo no debe registrar una estancia.

### Archivos y verificación de esta etapa

- Nuevos: `backend/app/schemas/estancia.py`, `backend/app/services/estancia.py`
  (`ServicioEstancia`) y `backend/app/routers/estancias.py`.
- Modificado: `backend/app/main.py`, para registrar el router y el manejo público
  de `EstanciaError`; este README documenta su uso.
- Nuevos: `backend/tests/test_estancias_api.py` y
  `backend/tests/test_estancias_postgres.py`.
- **111 pruebas aprobadas**, incluido el recorrido dentro/fuera, normalización,
  ingreso duplicado, celda ocupada, referencias ausentes, salida repetida,
  reutilización de celda y regresión de vehículos, celdas, operadores y `/health`.
  Se mantiene un aviso conocido de deprecación de Starlette/httpx.
- **Concurrencia real comprobada** con conexiones independientes y barreras que
  fuerzan la carrera: entradas del mismo vehículo, entradas a la misma celda y
  dos salidas con operadores distintos. En cada caso hubo una respuesta exitosa
  y una 409, sin filas adicionales ni sobrescritura del cierre ganador.
- Las rutas se verificaron en `/openapi.json` mediante TestClient. La limpieza de
  registros de prueba terminó correctamente. No se modificó el esquema.
- **Pendiente:** recorrido manual en navegador y comprobación de estas rutas en
  un proceso Uvicorn reiniciado; pruebas de carga prolongada y fallos de red durante
  commit. No se afirma haber realizado esas verificaciones.

No se implementó frontend, ni edición o eliminación de estancias. No se creó un commit.

## Modelo Estancia y migración 0002 aplicada

Antes de implementar se comprobó PostgreSQL: SELECT 1 correcto, revisión aplicada
`0001` y ninguna tabla `estancia` en los esquemas consultados. El historial local
solo contenía `0001`. Primero se preparó `0002_estancia.py` sin aplicarla.
Posteriormente, el 19 de octubre de 2026, se revisó y aplicó a la base local
`autos_colombia` por solicitud expresa. **Estado comprobado: `0002 (head)`**.
Las referencias a `0001` aplicada en otras secciones son resultados históricos.

### Aplicación y verificación realizadas

Antes de aplicar: conexión SELECT 1 correcta; `current` = `0001`, `heads` =
`0002`; historial lineal `0001 -> 0002`. Se comprobó que `estancia` no existía
y que las tres tablas referenciadas tenían PK BIGINT. La revisión del archivo y
las **13 pruebas de Estancia aprobadas** confirmaron que la migración correspondía
al modelo. No se detectaron discrepancias ni se editaron migraciones.

Comandos PowerShell utilizados con el entorno existente:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe check_db.py
.\.venv\Scripts\python.exe -m alembic -c alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.\.venv\Scripts\python.exe -m alembic -c alembic.ini history
.\.venv\Scripts\python.exe -m pytest tests/test_estancia.py -q
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade 0002
if ($LASTEXITCODE -ne 0) { throw 'La migración falló; detener y revisar.' }
.\.venv\Scripts\python.exe -m alembic -c alembic.ini current
```

`upgrade 0002` terminó con código 0; la consulta posterior mostró `0002 (head)`.
Las consultas de catálogo con SQLAlchemy comprobaron:

| Elemento | Resultado observado |
| --- | --- |
| Tabla y columnas | `estancia` existe con las siete columnas acordadas, sin campos adicionales. |
| Identificador | BIGINT, identidad ALWAYS, clave primaria `id`. |
| Nulabilidad | Solo `salida` y `operador_salida_id` admiten NULL. |
| Fechas | Ambas con zona horaria; entrada DEFAULT now(), salida sin valor predeterminado. |
| Referencias | Cuatro FK hacia vehiculo, celda y los dos operadores, todas ON DELETE RESTRICT. |
| Fechas válidas | CHECK `salida >= entrada`. |
| Cierre completo | CHECK `(salida IS NULL) = (operador_salida_id IS NULL)`. |
| Exclusividad de abiertas | Dos índices únicos, sobre vehiculo_id y celda_id, ambos WHERE salida IS NULL. |
| Historial | Índice no único `(vehiculo_id, entrada)`, en ese orden. |
| Estado del catálogo | Restricciones validadas; todos los índices válidos y listos. |

Se conservaron vehiculo, celda y operador. No se borraron ni recrearon tablas
existentes. En esta etapa solo se modificó este README en el código del proyecto;
el cambio de PostgreSQL fue la aplicación de la revisión existente `0002`.

**Pendiente:** pruebas de inserciones inválidas, bloqueos de eliminación y
concurrencia con datos de prueba, y ensayo de downgrade en una base aislada.
La inspección del catálogo confirma las definiciones instaladas; no equivale
a ejecutar esos escenarios. No se repitió la suite completa ni se implementaron
servicios, endpoints o Angular. No se creó un commit.

`Estancia` se encuentra en `backend/app/models.py`, junto a los modelos existentes:

- `id`: BIGINT GENERATED ALWAYS AS IDENTITY, clave primaria.
- `vehiculo_id`, `celda_id`, `operador_entrada_id`: BIGINT obligatorios con FK.
- `entrada`: fecha/hora con zona horaria, obligatoria, DEFAULT now() del servidor.
- `salida`: fecha/hora con zona horaria nullable; inicialmente NULL.
- `operador_salida_id`: BIGINT nullable, FK al operador de salida.

Las relaciones `vehiculo`, `celda`, `operador_entrada` y `operador_salida` permiten
navegar desde una estancia. Las dos relaciones de operador usan explícitamente
sus respectivas claves foráneas. Las cuatro FK tienen ON DELETE RESTRICT y no
hay cascadas ORM de eliminación: los registros referenciados no se pueden borrar
mientras exista historial, incluso si la estancia está cerrada.

Los índices únicos parciales `uq_estancia_vehiculo_abierta` y
`uq_estancia_celda_abierta` usan `WHERE salida IS NULL`; impiden dos estancias
abiertas para el mismo vehículo o celda, sin restringir su historial cerrado.
`ix_estancia_vehiculo_entrada` indexa `(vehiculo_id, entrada)`. Los CHECK
`ck_estancia_orden_fechas` y `ck_estancia_cierre_completo` exigen salida >= entrada
y que salida/operador_salida_id estén ambos nulos o ambos informados.

`esta_abierta()` calcula `salida is None`. `cerrar(fecha_salida, operador)` recibe
un objeto Operador con id asignado, valida el estado abierto y fechas conscientes
de zona horaria, compara los instantes en UTC y asigna fecha, relación e id de
salida. Acepta salida igual a entrada. Si falla una validación no modifica el
cierre. No hace flush ni commit. Antes de cerrar una estancia nueva, el futuro
servicio deberá hacer flush y cargar la entrada generada por PostgreSQL; también
deberá persistir el operador si es nuevo. La FK verifica su existencia al guardar.
PostgreSQL conserva instantes con zona horaria, no el nombre original del huso.

### Revisar sin aplicar (PowerShell)

Usa el entorno virtual existente; no necesitas activarlo ni reinstalar paquetes:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe check_db.py
.\.venv\Scripts\python.exe -m alembic -c alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.\.venv\Scripts\python.exe -m alembic -c alembic.ini history
Get-Content -LiteralPath migrations\versions\0002_estancia.py
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade 0001:0002 --sql
.\.venv\Scripts\python.exe -m pytest tests/test_estancia.py -q
```

El rango `0001:0002 --sql` solo genera SQL de la nueva revisión, sin conexión ni
ejecución de DDL. Revisa una creación de tabla, cuatro FK RESTRICT, dos CHECK,
dos índices únicos parciales y el índice de historial. No debe recrear las tablas
existentes. No uses `stamp` para simular que la migración fue aplicada.

### Comando de aplicación (ya ejecutado en esta base)

El siguiente bloque **sí modifica el esquema** cuando la revisión está pendiente.
Se conserva como referencia para otros entornos; esta base ya está en `0002`.
Si la tabla existe pero Alembic indica `0001`, detente y revisa la discrepancia.

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe check_db.py
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL no está disponible.' }
.\.venv\Scripts\python.exe -m alembic -c alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade 0002
if ($LASTEXITCODE -ne 0) { throw 'La migración falló; revisar el esquema.' }
.\.venv\Scripts\python.exe -m alembic -c alembic.ini current
```

Se obtuvo `0002 (head)`. El downgrade elimina la tabla y todo su historial;
no forma parte de estos comandos y no se ejecutó.

### Comprobar después tabla, relaciones e índices

Este bloque de PowerShell/Python realiza únicamente consultas de catálogo usando
la configuración existente, sin imprimir credenciales. En esta base ya debe
mostrar la estructura instalada; si falta la tabla, informa del problema.

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
@'
from sqlalchemy import inspect
from app.database import get_engine
try:
    with get_engine().connect() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("estancia"):
            print("La tabla estancia no existe; migracion 0002 pendiente.")
            raise SystemExit(1)
        for column in inspector.get_columns("estancia"):
            print(column["name"], column["type"], "nullable:", column["nullable"],
                  "default:", column.get("default"), "identity:", column.get("identity"))
        print("PK:", inspector.get_pk_constraint("estancia"))
        print("FK:", inspector.get_foreign_keys("estancia"))
        print("CHECK:", inspector.get_check_constraints("estancia"))
        print("Indices:", inspector.get_indexes("estancia"))
except Exception:
    print("No se pudo inspeccionar estancia; revisar conexion y permisos localmente.")
    raise SystemExit(1)
'@ | .\.venv\Scripts\python.exe -
```

Comprueba las siete columnas, PK id, cuatro FK con RESTRICT, dos CHECK y tres
índices descritos arriba. En los dos índices únicos revisa `unique=True` y
`postgresql_where` equivalente a `salida IS NULL`; en el índice de historial,
el orden de columnas debe ser vehiculo_id, entrada.

### Alcance y resultados de Estancia

- Modificados: `backend/app/models.py` y este README.
- Nueva migración: `backend/migrations/versions/0002_estancia.py`; `0001` intacta.
- Nuevas pruebas: `backend/tests/test_estancia.py` cubre cierre, zonas horarias,
  entradas no cargadas, operador sin id, cierre repetido, ausencia de mutación
  ante errores, relaciones sin cascada y equivalencia de SQL modelo/migración.
- Ajustadas: `backend/tests/test_models.py` limita la obligatoriedad de todos los
  campos a los tres modelos iniciales; las pruebas de integración de vehículos y
  operadores aceptan tanto `0001` como `0002`, para poder ejecutarlas antes y
  después de aplicar esta revisión.
- Comprobado: **96 pruebas aprobadas** con integración de los CRUD actuales y
  rollback; SQL offline revisado. Un aviso conocido de Starlette/httpx.
- La aplicación y la verificación de catálogo ya se completaron en la etapa
  documentada al principio. Quedan pendientes las pruebas de comportamiento en
  PostgreSQL aislado y la reversión; no se ha ejecutado downgrade.

No se añadieron servicios, esquemas API, controladores, endpoints ni cambios Angular.

## Pantalla de operadores en Angular

Disponible desde **Operadores** en la navegación y en
<http://127.0.0.1:4200/gestion/operadores>. Incluye listado de diez registros por
página, formulario reactivo de nombre y teléfono, edición, confirmación de
eliminación con nombre/teléfono/id, estados de carga y mensajes de resultado.

Los dos campos son obligatorios; se recortan espacios exteriores y se rechazan
textos vacíos o solo espacios. Teléfono usa un control de texto (`type="tel"`),
sin formato ni longitud máxima inventados: conserva prefijos y ceros iniciales.
Los nombres y teléfonos repetidos están permitidos por la API. Durante las
solicitudes se bloquean las acciones para evitar envíos duplicados. Guardar o
eliminar recarga el listado; una última página vacía vuelve a la anterior.

`OperadoresService` centraliza las llamadas y reutiliza `API_BASE_URL`. El proxy
añade `/operadores` y `/operadores/**` hacia `127.0.0.1:8000`; no se cambió CORS
ni ningún archivo del backend. Reinicia Angular para cargar cambios del proxy.

### Iniciar y verificar con PowerShell

Terminal 1, si FastAPI todavía no está iniciado (usa el entorno existente):

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, para iniciar Angular con las dependencias locales:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd start -- --host 127.0.0.1 --port 4200
```

Si el puerto está ocupado por una instancia anterior, detenla con Ctrl+C en su
terminal antes de reiniciar. Mantén ambos servidores activos mientras pruebas.
Para compilar y ejecutar la suite frontend en otra terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación.' }
npm.cmd test -- --watch=false
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas frontend.' }
```

Se ejecutaron compilación, pruebas y arranque Angular con estos comandos. FastAPI
ya estaba iniciado y se reutilizó sin modificarlo. No se instalaron paquetes ni
se actualizaron Angular CLI o TypeScript globalmente.

### Recorrido manual y resultados esperados

1. Abre **Operadores**. Si no hay datos, debe aparecer **Aún no hay operadores**.
   Si los hay, usa **Anterior/Siguiente** para recorrer páginas de diez registros.
2. Pulsa **Nuevo operador**. Para identificar tu prueba usa un nombre nuevo como
   `PRUEBA-ANGULAR-ANA-20261019-01` y teléfono ` +57 00123 `. Al guardar se espera
   confirmación de registro y teléfono `+57 00123`, sin espacios exteriores.
   El registro nuevo puede estar en la última página, pues se ordena por id.
3. Pulsa **Editar** sobre ese registro, cambia el teléfono a `00045` y guarda.
   Debe conservar los ceros y actualizar el listado con confirmación de éxito.
4. Prueba un campo vacío o con espacios: debe aparecer un error junto al campo y
   no enviarse la solicitud. Cancela el formulario para salir de esta comprobación.
5. Pulsa **Eliminar** únicamente sobre tu operador de prueba. Comprueba nombre,
   teléfono e id; **Cancelar eliminación** conserva el registro y **Confirmar
   eliminación** lo borra y actualiza la lista. No elimines datos preexistentes.

El 422 de FastAPI se muestra como validación, con errores de campo cuando la
respuesta los identifica. El 404 informa que el operador ya no existe; el 409
de eliminación informa del conflicto o relación. Los fallos de conexión muestran
un mensaje para comprobar el servicio y actualizar el listado antes de reintentar,
pues una solicitud podría haberse completado aunque no llegara su respuesta.

### Verificación de esta etapa frontend

- **Compilación correcta y 32 pruebas aprobadas**: incluye las 24 existentes y
  ocho nuevas de operadores. Cubren formulario HTML, recorte, teléfono como texto,
  doble envío, PATCH sin id, confirmación/cancelación, listado vacío, paginación,
  recuperación de última página, errores 404/409/422 y conexión simulados.
- **Integración HTTP real por el proxy**: POST 201, listado y consulta 200,
  PATCH 200 conservando `00045`, validación 422, DELETE 204 y consulta posterior
  404. Vehículos, celdas y `/health` respondieron 200.
- **Navegador con FastAPI real**: creación, listado, edición del teléfono,
  confirmación y eliminación completadas; se revisó la presentación de escritorio
  y el estado vacío. Se eliminaron únicamente los dos operadores nuevos creados
  para las pruebas HTTP y de navegador.
- **Pendiente**: revisión visual móvil y accesibilidad completa; paginación con
  más de diez registros reales; conflicto por una relación real y errores de red
  provocados desde el navegador. Estos últimos comportamientos se cubren con
  pruebas simuladas, no se consideran verificados contra relaciones reales.

Archivos nuevos: `frontend/src/app/models/operador.ts`,
`frontend/src/app/services/operadores.service.ts` y
`frontend/src/app/operadores/operadores.ts`, `.html`, `.css`, `.spec.ts`.
Archivos modificados: `frontend/src/app/app.routes.ts`, `app.html`, `app.css`
(navegación que se ajusta a varias líneas), `frontend/proxy.conf.json` y este README.
No se modificaron vehículos, celdas, backend, tablas, migraciones ni dependencias.
No se creó un commit.

## CRUD de operadores (solo backend)

Se comprobó en `autos_colombia` que la revisión aplicada es `0001` y que existe
`operador`: id BIGINT generado siempre por PostgreSQL, clave primaria, nombre y
telefono TEXT NOT NULL y CHECK contra textos vacíos. No hay unicidad en nombre
ni teléfono. En aquella etapa no se modificaron modelos, tablas, migraciones ni Angular.

| Método y ruta | Respuesta |
| --- | --- |
| `POST /operadores` | 201 con `id`, `nombre` y `telefono` |
| `GET /operadores?offset=0&limit=20` | 200 con `items`, `total`, `offset`, `limit` |
| `GET /operadores/{id}` | 200 con el operador; 404 si no existe |
| `PATCH /operadores/{id}` | 200 con el operador actualizado; 404 si no existe |
| `DELETE /operadores/{id}` | 204 sin cuerpo; 404 si no existe |

La paginación es la misma de vehículos y celdas: orden por id ascendente,
offset desde cero, límite entre 1 y 100 (20 por defecto). Los ids admitidos son
enteros positivos dentro del rango BIGINT. Al crear se exigen nombre y telefono;
al actualizar solo se validan y cambian los campos enviados. PATCH con `{}` no
cambia los datos. No se acepta `id` ni otros campos desconocidos en los cuerpos.

Ambos textos se recortan en los extremos; valores nulos, vacíos, solo espacios o
de otro tipo devuelven 422. El teléfono debe enviarse como cadena JSON: conserva
prefijos y ceros iniciales, sin imponer un formato o una longitud máxima adicional
al tipo TEXT del modelo. Se permiten nombres y teléfonos repetidos. Una relación
que impida borrar produce 409 sin borrar registros relacionados; se revierten
transacciones fallidas. Los errores generales de base de datos producen 503 con
un mensaje público, sin detalles internos. Operador no incorpora autenticación.

### Comandos PowerShell con el entorno existente

Estos comandos de conexión, dependencias y pruebas se ejecutaron con
`backend/.venv`; no hace falta activarlo ni recrearlo:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe check_db.py
if ($LASTEXITCODE -ne 0) { throw 'No se pudo verificar PostgreSQL.' }
.\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Hay conflictos de dependencias.' }
$valorAnterior = $env:RUN_POSTGRES_TESTS
try {
    $env:RUN_POSTGRES_TESTS = '1'
    .\.venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas del backend.' }
} finally {
    $env:RUN_POSTGRES_TESTS = $valorAnterior
}
```

Resultado observado: SELECT 1 correcto, dependencias sin conflictos y **83 pruebas
aprobadas**. Sin `RUN_POSTGRES_TESTS`, se comprobaron **79 aprobadas y 4 omitidas**.
Ambas ejecuciones emitieron un aviso de deprecación de Starlette/httpx.
La integración usa TestClient con PostgreSQL real, transacción exterior y
savepoints; revierte todos los datos de prueba incluso si falla una aserción.
Solo elimina operadores nuevos identificados como `TEST-OPERADOR-...`; las
secuencias de ids pueden avanzar. No requiere un servidor HTTP iniciado ni hace DDL.

### Probar operadores desde /docs

Inicia FastAPI con el entorno existente. Si ya hay un servidor sin `--reload`
en el puerto 8000, detenlo con Ctrl+C en su terminal antes de reiniciarlo para
cargar las nuevas rutas:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Abre <http://127.0.0.1:8000/docs>, grupo **Operadores**, y usa **Try it out** y
**Execute**. Este recorrido manual en navegador está pendiente; los estados
indicados son los esperados y se comprobaron mediante pruebas automatizadas:

1. Ejecuta POST con `{"nombre":" PRUEBA-DOCS-OPERADOR ","telefono":" +57 001234 "}`.
   Espera 201, los textos recortados y un id generado. Anota ese id.
2. Consulta GET del listado y GET de ese id: espera 200. La lista es paginada;
   el nuevo operador podría no aparecer en la primera página.
3. Ejecuta PATCH de ese id con `{"telefono":" 00045 "}`: espera 200 y teléfono
   `"00045"`, con el nombre conservado.
4. Prueba PATCH con `{"nombre":null}`, `{"telefono":"   "}` o `{"id":1}`:
   espera 422. POST sin teléfono también debe devolver 422.
5. Elimina únicamente el id creado en el paso 1: espera 204 sin cuerpo.
   GET, PATCH válido o DELETE de ese id ya eliminado deben devolver 404.

### Archivos y alcance de la verificación de operadores

- Nuevos: `backend/app/schemas/operador.py` (validación y respuestas),
  `backend/app/routers/operadores.py` (APIRouter) y
  `backend/app/services/operador.py` (CRUD, errores y rollback).
- Nuevos: `backend/tests/test_operadores.py` (validación HTTP y errores simulados)
  y `backend/tests/test_operadores_postgres.py` (estructura y CRUD real).
- Modificados: `backend/app/main.py` (router y manejador de errores), este README
  y `backend/README.md` (referencia a estas instrucciones).
- Verificado: creación, consulta, listado y paginación, PATCH parcial, teléfono
  como texto, duplicados permitidos, DELETE sin cuerpo, errores 404/422,
  rollback y mensajes públicos. Las suites incluyen regresión de vehículos,
  celdas y `/health`.
- Pendiente: recorrido manual en `/docs` y conflicto de borrado contra una
  relación real. El 409 y su rollback se verificaron con un error de clave
  foránea simulado, sin añadir relaciones a PostgreSQL. El frontend se añadió en
  la etapa descrita al principio de este README.

La primera ejecución restringida no permitió completar la comprobación local;
se repitieron las comprobaciones con acceso autorizado y los resultados anteriores
corresponden a esas ejecuciones completas.

## Gestión de celdas

Disponible en la navegación **Celdas** y en
<http://127.0.0.1:4200/gestion/celdas>. Incluye listado paginado, creación y edición
de código y tipo, confirmación de eliminación y mensajes de resultado y error.
El tipo es texto libre obligatorio; no se han definido compatibilidades con vehículos.

La tabla `celda` ya estaba creada por `0001`. Se verificaron las restricciones
reales y no hubo migraciones pendientes ni cambios de esquema. El CRUD y sus
restricciones se probaron en PostgreSQL, conservando vehículos y `/health`.

El proxy incluye `/celdas` y `/celdas/**`. Reinicia ambas aplicaciones para cargar
las rutas nuevas, usando las dos terminales descritas abajo. El servicio Angular
`CeldasService` reutiliza `API_BASE_URL`; no requiere cambios de CORS.

Verificación: 61 pruebas backend (con PostgreSQL), 24 pruebas frontend y compilación
correcta. Se comprobó también el CRUD HTTP mediante el proxy con una celda nueva,
eliminada al finalizar. La revisión visual en navegador no se realizó.

Proyecto con backend en Python y FastAPI y frontend en Angular con TypeScript.
El frontend utiliza componentes standalone, enrutamiento, CSS y comprobación
estricta de TypeScript y plantillas.

## Requisitos en Windows

Versiones verificadas en este equipo:

| Herramienta | Versión |
| --- | --- |
| Python | 3.13.16 |
| pip | 26.2.1 |
| Node.js | 24.22.0 |
| npm | 11.7.0 |
| Git | 2.45.2.windows.1 |
| Angular y Angular CLI locales | 22.2.3 |
| TypeScript local | 6.0.3 |

Utiliza Python 3.13 y una versión de Node.js de la rama 24 igual o superior a
24.15.0. Abre una terminal nueva después de instalar herramientas o cambiar PATH.
Comprueba las herramientas desde PowerShell:

```powershell
py -3.13 --version
py -3.13 -m pip --version
node --version
npm.cmd --version
git --version
Get-Command python, pip, node, npm.cmd, git | Select-Object Name, Source
```

Los comandos siguientes usan la ruta actual de este equipo. Si mueves o clonas
el proyecto en otra ubicación, sustituye la ruta en los comandos `Set-Location`.
Las comillas permiten trabajar con los espacios y acentos del nombre de carpeta.

## Estructura

```text
AutosColombia/
├── README.md
├── .gitignore
├── backend/
│   ├── .venv/                 # Entorno local, excluido de Git
│   ├── app/main.py            # Aplicación FastAPI y GET /health
│   ├── tests/test_health.py   # Prueba del endpoint
│   └── requirements.txt       # Versiones exactas, incluidas las transitivas
└── frontend/
    ├── src/app/               # Componentes y rutas Angular
    ├── angular.json
    ├── tsconfig.json
    ├── package.json
    └── package-lock.json      # Versiones resueltas de las dependencias
```

## Instalar las dependencias

Ejecuta esta preparación antes de iniciar los servidores. Necesitas acceso a
Internet para descargar paquetes de PyPI y npm.

### Backend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    throw 'No se encontró el entorno virtual existente backend/.venv.'
}
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Se reutiliza `.venv` sin recrearlo. Los comandos usan
directamente su intérprete: no hace falta activar el entorno ni cambiar la
política de ejecución de PowerShell. `requirements.txt` fija las versiones de las
dependencias de ejecución y pruebas.

### Frontend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd ci
npm.cmd ls @angular/core @angular/cli typescript --depth=0
```

`npm ci` instala las versiones de `package-lock.json` y reconstruye
`node_modules`. Conserva `package-lock.json` en el repositorio; no lo borres para
reinstalar. Se utiliza `npm.cmd` para evitar depender de la ejecución de scripts
`.ps1` en PowerShell.

El proyecto se generó con `npx @angular/cli@22`. Los scripts `npm` de este proyecto
utilizan Angular CLI y TypeScript locales. No necesitas instalar ni actualizar
ninguna de estas herramientas globalmente.

## Verificar antes de ejecutar

### Pruebas y dependencias del backend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado esperado: dependencias sin conflictos y todas las pruebas aprobadas. La prueba de salud
verifica HTTP 200, el tipo de contenido JSON y el cuerpo `{"status": "ok"}` de
`GET /health`. No necesita un servidor iniciado. Las dependencias actuales pueden
emitir un aviso de deprecación de Starlette sobre `httpx`; no es un fallo de la prueba.

### Configurar y verificar PostgreSQL local

La configuración se documenta en [backend/README.md](backend/README.md#postgresql-local).
Completa `DB_NAME`, `DB_USER` y `DB_PASSWORD` en `backend/.env` y confirma
`DB_HOST`, `DB_PORT` y `DB_CONNECT_TIMEOUT`. La plantilla `backend/.env.example`
contiene valores de ejemplo; `.env` queda excluido de Git.

Desde la raíz del proyecto:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia'
.\backend\.venv\Scripts\python.exe .\backend\check_db.py
```

El comando comprueba `SELECT 1` sin modificar tablas y solo informa éxito si la
conexión funciona. Las pruebas ejecutadas sin habilitar la integración no requieren PostgreSQL y no
sustituyen esta comprobación real. `/health` conserva su respuesta aunque falte
la configuración de PostgreSQL.

Los modelos `Vehiculo`, `Celda` y `Operador` usan la migración Alembic `0001`,
verificada como aplicada en `autos_colombia`. Consulta los comandos PowerShell de
[revisión y aplicación de migraciones](backend/README.md#modelos-y-migración-inicial).
La revisión con `upgrade head --sql` solo genera SQL; `upgrade head` sí modifica
el esquema y debe ejecutarse después de revisarlo.

El backend incluye el [CRUD de vehículos](backend/README.md#crud-de-vehículos),
con instrucciones para probarlo desde `/docs` y PowerShell. Las pruebas de
integración con PostgreSQL se habilitan con `RUN_POSTGRES_TESTS=1`; por defecto
se omiten para mantener las pruebas habituales independientes de la base local.

Para comprobar el estado de Alembic y ejecutar también las pruebas de vehículos
y celdas contra la base local configurada en `backend/.env`:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe check_db.py
if ($LASTEXITCODE -ne 0) { throw 'No se pudo verificar PostgreSQL.' }
.\.venv\Scripts\python.exe -m alembic -c alembic.ini current
if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar la revisión aplicada.' }
.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads
if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar la revisión disponible.' }
$valorAnterior = $env:RUN_POSTGRES_TESTS
try {
    $env:RUN_POSTGRES_TESTS = '1'
    .\.venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas del backend.' }
} finally {
    $env:RUN_POSTGRES_TESTS = $valorAnterior
}
```

Las pruebas de integración usan transacciones con rollback y savepoints;
no crean tablas ni conservan los registros de prueba. Las secuencias de ids
pueden avanzar. `current` y `heads` no aplican migraciones. En la revisión
realizada coincidían en `0001`; no fue necesario aplicar ninguna migración.

### Compilación y pruebas del frontend

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd run build
npm.cmd test -- --watch=false
```

Resultado esperado actual: compilación correcta y **38 pruebas aprobadas**. La salida de
compilación queda en `frontend/dist/frontend`. Estas pruebas tampoco requieren
que el servidor de desarrollo esté iniciado.

## Ejecutar en dos terminales de PowerShell

Abre dos ventanas o pestañas de PowerShell. Cada servidor ocupa su terminal hasta
que lo detengas. Mantén ambas abiertas mientras desarrollas.

### Terminal 1: backend, puerto 8000

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Salud de la API: <http://127.0.0.1:8000/health>
- Documentación interactiva: <http://127.0.0.1:8000/docs>

`--reload` reinicia la API cuando cambias el código del backend.

### Terminal 2: comprobar la API e iniciar el frontend, puerto 4200

Cuando la terminal 1 indique que la API está lista, ejecuta lo siguiente en la
terminal 2. La comprobación HTTP se hace antes de iniciar Angular, para que no
necesites una tercera terminal:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
$healthResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing
$healthResponse.StatusCode
$healthResponse.Content
if ($healthResponse.StatusCode -ne 200 -or ($healthResponse.Content | ConvertFrom-Json).status -ne 'ok') {
    throw 'La comprobación de salud del backend falló.'
}
npm.cmd start -- --host 127.0.0.1 --port 4200
```

La comprobación muestra `200` y `{"status":"ok"}`. Cuando Angular termine de
compilar, abre <http://127.0.0.1:4200> en el navegador. Verás la pantalla de bienvenida
de Autos Colombia. Al cargar, la pantalla consulta `GET /health` mediante
`HttpClient` y muestra “Comprobando conexión…”, “Servicio disponible” o
“No se pudo conectar con el servicio”. Una respuesta distinta de `{"status":"ok"}`,
un error HTTP o de red, o una espera superior a 5 segundos muestran el error.
La comprobación se realiza una vez al cargar: recarga la página para repetirla.
Angular actualiza la página al guardar cambios.

El proxy de desarrollo de `frontend/proxy.conf.json`, activado en `angular.json`,
redirige `/health`, `/vehiculos`, `/vehiculos/**`, `/celdas`, `/celdas/**`,
`/operadores` y `/operadores/**`
a `http://127.0.0.1:8000`. El navegador hace la solicitud al
mismo origen de Angular, por lo que no se necesita habilitar CORS en FastAPI.
Reinicia `npm.cmd start` si cambias el proxy. Este proxy solo funciona con el
servidor de desarrollo; en producción se debe configurar el servidor web para
redirigir esas rutas de API al backend y las rutas de pantalla al archivo `index.html`.

## Pantalla de gestión de vehículos

Con las dos terminales anteriores activas, abre
<http://127.0.0.1:4200/gestion/vehiculos> o selecciona **Vehículos** en la navegación.
La bienvenida permanece en **Inicio**. La ruta de pantalla `/gestion/vehiculos`
es distinta de la ruta API `/vehiculos` para evitar conflictos con el proxy.

- El listado usa páginas de 10 vehículos, ordenadas por id, con Anterior y Siguiente.
- **Nuevo vehículo** abre un formulario reactivo con placa, marca, año, color y tipo.
  Todos son obligatorios; el año es entero entre 1 y 9999. La placa se recorta y
  convierte a mayúsculas. Los tipos son MOTO, AUTOMOVIL y CAMIONETA.
- **Editar** consulta la versión actual del vehículo y guarda mediante PATCH sin id.
- **Eliminar** muestra una confirmación con placa, marca y año. Solo se envía DELETE
  al pulsar **Confirmar eliminación**; **Cancelar eliminación** no modifica datos.
- Guardar o eliminar actualiza el listado. Si la última página queda vacía, se
  retrocede a una página existente. Los mensajes indican el resultado de cada acción.
- Se muestran errores junto a los campos, placas duplicadas, vehículos que ya no
  existen y conflictos de eliminación. Mientras hay una petición se bloquean
  las acciones para evitar envíos duplicados. Ante fallos de conexión o espera,
  actualiza el listado antes de repetir una operación, pues el servidor podría
  haberla completado aunque su respuesta no haya llegado.

Las llamadas HTTP se centralizan en `frontend/src/app/services/api.service.ts` y
los contratos están en `frontend/src/app/models/vehiculo.ts`. `API_BASE_URL` usa
el mismo origen por defecto; los componentes no contienen direcciones del backend.
El destino local se configura en `frontend/proxy.conf.json`. No se cambió CORS ni
se añadieron dependencias visuales. Reinicia Angular después de cambiar el proxy.

### Verificación realizada

En la etapa de vehículos pasaron la compilación y las 20 pruebas entonces existentes
(el total posterior con celdas es 24). Las pruebas cubren validación,
estados de carga, paginación, creación, edición, confirmación, eliminación, bloqueo
de doble envío y errores 404/409/422 y de red. El CRUD HTTP también se verificó
contra el backend local a través del puerto 4200 con un registro nuevo, eliminado
al finalizar. No se tocaron registros existentes. La interacción y revisión visual
en navegador quedaron pendientes por un límite de uso de la herramienta de navegador.

Para comprobar el proxy con ambos servidores activos, abre una terminal adicional:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:4200/health'
```

El resultado debe mostrar `status` con valor `ok`.

Para detener ambos servidores, pulsa **Ctrl+C en cada terminal**. Si Windows
pregunta si deseas terminar el trabajo por lotes, confirma. Si un puerto ya está
ocupado, detén primero la instancia anterior del servidor antes de volver a iniciarlo.

## Probar celdas desde /docs

Con el backend iniciado, abre <http://127.0.0.1:8000/docs> y despliega el grupo
**Celdas**. En cada operación pulsa **Try it out**, completa los parámetros y
pulsa **Execute**. Los resultados siguientes son los esperados para esta prueba
manual; no constituyen una afirmación de que se haya ejecutado desde Swagger.

1. Genera un código exclusivo para tus pruebas en una terminal PowerShell:

   ```powershell
   $codigoPrueba = 'PRUEBA-' + [guid]::NewGuid().ToString('N')
   $codigoPrueba
   ```

2. En `POST /celdas`, sustituye el código del siguiente cuerpo por el generado.
   Puedes escribirlo en minúsculas y con espacios exteriores para comprobar la
   normalización. Espera HTTP **201** y guarda el `id` de la respuesta.

   ```json
   { "codigo": " prueba-reemplazar-por-codigo-unico ", "tipo": "Espacio de prueba" }
   ```

3. En `GET /celdas`, usa `offset=0` y `limit=10`. Espera **200** y un objeto con
   `items`, `total`, `offset` y `limit`. El orden es por id ascendente; el registro
   nuevo podría estar en otra página. El límite admite de 1 a 100 y el offset
   debe ser mayor o igual a cero. Consulta `GET /celdas/{id}` con tu id para
   comprobar **200**, el código en mayúsculas y sin espacios exteriores.
4. Repite el POST con ese mismo código: espera **409** por duplicado.
5. En `PATCH /celdas/{id}`, envía `{"tipo":"Otro tipo de prueba"}`: espera **200**,
   con el código conservado. `tipo` es texto libre; no es un selector de tipos
   de vehículo. Código y tipo son obligatorios al crear; PATCH admite omitirlos,
   pero rechaza `null`, textos vacíos y espacios. Enviar `{"tipo":"   "}`,
   `{"codigo":null}` o un campo `id` en el cuerpo debe responder **422**.
6. Elimina **solo el id que acabas de crear** mediante `DELETE /celdas/{id}`:
   espera **204 sin cuerpo**. Consulta nuevamente ese id: espera **404**.

Un conflicto por una relación que impida eliminar debe producir **409** sin
borrar registros relacionados. Actualmente no se incorporaron relaciones para
provocar ese caso; su comprobación contra una relación real queda pendiente.
Los errores de negocio usan `detail`; las validaciones de FastAPI pueden devolver
una lista en `detail` con la ubicación y descripción de cada error.

## Probar celdas desde Angular

Inicia las dos terminales como se indica arriba y abre
<http://127.0.0.1:4200/gestion/celdas>, o pulsa **Celdas** en la navegación.
Este recorrido manual está pendiente de verificación en navegador:

1. Comprueba el listado o el mensaje **Aún no hay celdas** si está vacío. Pulsa
   **Nueva celda**, escribe un código nuevo exclusivo de prueba y un tipo libre,
   y pulsa **Guardar celda**. Espera la confirmación y el listado actualizado.
   Busca tu registro con **Siguiente** si no aparece en la primera página.
2. Prueba campos vacíos o con espacios: deben aparecer errores junto a los campos.
   Intenta crear otra celda con el mismo código: debe indicarse el duplicado.
   Cancela el formulario cuando termines esa comprobación.
3. Pulsa **Editar** en tu registro, cambia el tipo y guarda. Comprueba que el
   listado refleje el cambio y que las acciones se bloqueen durante el envío.
4. Pulsa **Eliminar** en tu registro y revisa que la confirmación identifique su
   código y tipo. Prueba **Cancelar eliminación**; después repite y pulsa
   **Confirmar eliminación**. Elimina únicamente registros que tú hayas creado
   para esta prueba. Comprueba la confirmación de éxito y el listado actualizado.
5. Revisa **Anterior/Siguiente** cuando haya más de diez celdas, y la presentación
   en una ventana estrecha. Para probar un fallo de conexión, detén temporalmente
   el backend con Ctrl+C y pulsa **Actualizar listado**; debe aparecer un error.
   Reinícialo con el comando de la terminal 1 y vuelve a actualizar.

Si aparece `ECONNREFUSED 127.0.0.1:8000`, el proxy no consigue conectar con
FastAPI: comprueba que la terminal 1 siga activa y que `/health` responda en el
puerto 8000. Si cambias `proxy.conf.json`, reinicia Angular. Que `/health` responda
no demuestra por sí solo que PostgreSQL esté disponible: usa `check_db.py`.

## Archivos de la implementación de celdas

Las rutas de esta tabla son relativas a la raíz del proyecto.

| Archivo | Cambio y responsabilidad |
| --- | --- |
| `backend/app/schemas/celda.py` | Nuevo: contratos Pydantic, validación y paginación. |
| `backend/app/services/celda.py` | Nuevo: operaciones SQLAlchemy, conflictos y rollback. |
| `backend/app/routers/celdas.py` | Nuevo: endpoints CRUD mediante APIRouter. |
| `backend/app/main.py` | Registra el router y el manejo de errores de celdas. |
| `backend/tests/test_celdas_postgres.py` | Nuevo: restricciones reales y CRUD con rollback. |
| `frontend/src/app/models/celda.ts` | Nuevo: tipos de solicitudes y respuestas. |
| `frontend/src/app/services/celdas.service.ts` | Nuevo: llamadas HTTP con la base de API existente. |
| `frontend/src/app/celdas/celdas.ts`, `celdas.html`, `celdas.css` | Nuevos: formulario reactivo, listado, estados y confirmación. |
| `frontend/src/app/celdas/celdas.spec.ts` | Nuevo: cuatro pruebas del componente. |
| `frontend/src/app/app.routes.ts`, `app.html` | Ruta de pantalla y enlace de navegación. |
| `frontend/proxy.conf.json` | Añade las rutas API de celdas al proxy local. |
| `README.md`, `backend/README.md`, `AGENTS.md` | Documentan estructura, uso y verificación. |

Se reutilizaron `Celda`, la configuración privada y la migración `0001` existentes.
No se editaron modelos, migraciones aplicadas ni dependencias para esta etapa.
Esta actualización de documentación modifica únicamente el README raíz.

## Verificaciones realizadas y pendientes de celdas

Resultados observados durante la implementación, anteriores a esta actualización
de documentación:

| Comprobación | Resultado observado |
| --- | --- |
| PostgreSQL y Alembic | Revisión `0001` aplicada, sin migraciones pendientes; tabla `celda` existente. No se aplicó DDL. |
| Estructura real de `celda` | id BIGINT con identidad y PK; codigo/tipo TEXT NOT NULL; código único; CHECK de textos no vacíos y código normalizado. |
| Pruebas backend con integración habilitada | 61 aprobadas; un aviso de deprecación de Starlette/httpx. |
| Dependencias backend | `pip check` sin conflictos. |
| Frontend | Compilación correcta y 24 pruebas aprobadas, cuatro de celdas. |
| HTTP a través del proxy Angular | Creación 201, consulta/listado 200, edición 200, duplicado 409 y eliminación 204 de una celda nueva de prueba. |
| Regresión HTTP | Listado de vehículos 200 y `/health` con `status: ok`. |

Las suites se ejecutaron antes de los ajustes finales de textos de mensajes y
del nombre de una variable del servicio Angular; no se repitieron después de esos
ajustes. El servidor de desarrollo compiló los cambios y la comprobación HTTP
descrita se realizó después. Las pruebas de componente usan HTTP simulado; la
prueba HTTP del proxy sí utilizó el backend y PostgreSQL locales.

Quedan pendientes la ejecución manual desde `/docs`, el recorrido completo con
clics en Angular, la revisión visual móvil y de accesibilidad, y un conflicto de
eliminación con una relación real. La herramienta de navegador alcanzó un límite
de uso durante la implementación. No se consideran estos casos aprobados.
La celda creada para la comprobación HTTP se eliminó al terminar; las pruebas
de integración revirtieron sus transacciones. No se eliminaron registros previos.

Para esta modificación exclusivamente documental se revisan rutas, contratos y
sintaxis de los bloques PowerShell; no se reinstalan dependencias, no se aplican
migraciones y no se vuelven a ejecutar las suites ni las pruebas manuales.

