# Panel de configuración

*   **Autor:** rmalanco
*   **Estado:** Implementado el 2026-11-22 (historias 17 a 27 en `docs/historias/hechas/`; comportamiento en
    `docs/specs/configuracion.md`). Antes: propuesto, revisado (arquitectura: «aprobar con cambios»; implementation readiness: «listo con
    ajustes»); cambios de la revisión aplicados el 2026-11-22, ver «Revisión (2026-11-22)». Las seis decisiones de
    producto las tomó el usuario el 2026-11-22 («Decisiones tomadas»).
*   **Fecha:** 2026-11-22
*   **Origen:** `BACKLOG.md`, sección «Backlog», puntos 5 (panel de configuración, carril L) y 6 (sesión de GitHub
    Copilot desde el panel, carril M, requiere el 5).

Las líneas citadas son las del commit `3c79616`. Si las líneas se mueven, manda el nombre de la función.

**Orden con otro trabajo en curso.** La historia 16 (`docs/historias/16-limite-de-entrada.md`, límite de entrada: lee
`max_prompt_tokens` del catálogo) cambia `src/copilot.py` y `src/asistente_ia.py`. Las historias de este diseño que
tocan `src/copilot.py` (**B** y **E1**) van **después de la 16, en serie**; ninguna historia de este diseño toca
`src/asistente_ia.py`.

--------------------------------------------------------------------------------

## Resumen

Hoy, para cambiar un valor por defecto (el formato de salida, el idioma, la temperatura de la IA, el dominio de GitHub
Enterprise…) hay que editar `config/settings.yaml`, que está versionado. Los controles del panel lateral solo cambian
la transcripción en curso y se olvidan al cerrar; la única excepción es el modelo de IA, que desde el punto #11 de
«Salud del código» se guarda en `~/.local/share/transcriptor-audio/preferencias.json` y gana a `ia.modelo`. Para
iniciar sesión en Copilot hay que pulsar «Generar» o «↻» sin sesión, o usar la terminal; para cerrarla, solo la
terminal (`--copilot-logout`).

Este diseño añade una tercera vista, «⚙ Configuración» (`Ctrl+3`), junto a «Transcribir» e «Historial», con las 21
claves de `configuracion.py` agrupadas en Transcripción, Salida, IA e Historial (lo avanzado, plegado), y una sección
«Sesión de GitHub Copilot». Lo que el usuario guarda va a `preferencias.json`, solo las claves que difieren del YAML, y
gana al YAML solo en la ventana; el YAML sigue siendo de solo lectura y la CLI no cambia. La lógica (convertir,
validar, combinar y guardar los ajustes; qué controles laterales cambian; de dónde sale la sesión) vive en funciones
sin Tk de `configuracion.py`, `idiomas.py` (nuevo), `flujo_documentos.py` y `copilot.py`, con tests; la vista nueva,
`src/ui_configuracion.py`, solo pinta.

El trabajo se parte en doce historias pequeñas (A1, A2a, A2b, A3, C0, C1, C2, D1, D2, B, E1 y E2, con la 16 ajena
intercalada); E1 y E2 son el punto 6 del backlog.

## El problema

1.  **Ajustar la app obliga a editar un archivo versionado.** `config/settings.yaml` es el valor por defecto del
    proyecto (punto #11: «Guardar el modelo de IA elegido fuera del repo, junto al token, en vez de reescribir
    `config/settings.yaml`»). Cambiarlo a mano ensucia `git status`, se pierde al actualizar el repo y un error de
    sintaxis impide abrir la ventana (`docs/specs/configuracion.md`, «Configuración con errores»).
2.  **Los controles del panel lateral no se recuerdan, y hay claves que la ventana no muestra.** `AppTranscriptor.__init__`
    (`src/ui.py:159-167`) inicializa modelo de Whisper, idioma, formato, dispositivo, precisión y marcas de tiempo desde
    el YAML; lo que el usuario elige ahí vale solo para esa sesión. Las siete claves de decodificación de Whisper,
    `salida.palabra_por_palabra`, `historial.ruta` y cinco claves de IA (todas salvo `ia.modelo`) no se ven en ningún
    sitio de la ventana.
3.  **La sesión de Copilot no se ve ni se cierra desde la ventana.** `DialogoLoginCopilot` solo se abre como reacción
    a una falta de sesión (`_generar_documento_ia`, `_recibir_documento_ia`, `_sin_sesion_para_modelos`). No se ve si
    hay sesión ni de dónde sale, y cerrarla exige `python -m src.main --copilot-logout`.

## Objetivos

1.  **Todo lo configurable, en la ventana.** Las 21 claves de `configuracion._tabla()` (15 fuera de `ia` y 6 de `ia`)
    se ven y se cambian desde la vista «Configuración».
2.  **Una sola fuente de verdad por valor.** El valor efectivo de cada clave en la ventana es: el de
    `preferencias.json` si existe y es válido; si no, el del YAML; si no, el por defecto de `configuracion.py`. El modelo
    de IA sigue la regla de hoy (`modelo_ia` gana a `ia.modelo`). `config/settings.yaml` no se escribe nunca.
3.  **Validación con los mismos mensajes.** Un valor inválido se rechaza con el texto de `ErrorConfiguracion` (sin la
    ruta del YAML), más unos topes propios del panel; con un solo valor inválido no se guarda nada.
4.  **Sesión de Copilot visible y gobernable sin red.** La sección muestra si hay sesión y su origen leyendo solo
    archivos locales y la variable de entorno; inicia sesión con el diálogo de siempre y cierra **solo** la sesión
    propia de la app.
5.  **Sin regresiones.** Al abrir la ventana no hay tráfico de red ni se lee el token (spec «Lista de modelos bajo
    demanda»); el panel nunca ofrece ni guarda familias no autorizadas (regla 7); los widgets solo se tocan en el hilo
    principal (regla 9); la CLI no cambia.

## Fuera de alcance

*   Escribir `config/settings.yaml` (punto #11).
*   Que la CLI lea `preferencias.json` (decisión tomada 4).
*   Comprobar contra GitHub que el token es válido: sería tráfico de red que nadie pidió; el estado dice «se comprueba
    al usarla», no «la sesión es válida».
*   Cerrar la sesión de opencode o quitar `COPILOT_GITHUB_TOKEN`: la app nunca modifica el archivo de opencode
    (`00-actual.md`, «Datos y secretos») y no puede cambiar el entorno del proceso que la lanzó.
*   Recordar el tema (Sistema/Claro/Oscuro) o el tamaño de la ventana.
*   Reabrir el historial en caliente al cambiar `historial.ruta` (alternativa E).
*   Cambiar `FAMILIAS_EXCLUIDAS` o permitir desactivarla (`.context/transcriptor-facts.md`).
*   Endurecer la validación del YAML (rechazar `.nan`, topes): los topes y `math.isfinite` solo valen en el panel y en
    las preferencias, para no cambiar la CLI.
*   Botones de «restablecer» por clave: guardar una clave con el valor del YAML ya la quita de las preferencias.

## Decisiones tomadas

### Decisiones de producto (tomadas por el usuario el 2026-11-22)

El usuario eligió en las seis la opción que el diseño recomendaba.

1.  **El panel es una tercera vista de la barra de navegación, «⚙  Configuración», con el atajo `Ctrl+3`**, como
    «📚 Historial»: se construye la primera vez que se muestra. Mientras se ve, no se ven las pestañas de resultado.
2.  **Se muestran las 21 claves.** Las siete de decodificación de Whisper (`beam_size`, `best_of`, `temperature`,
    `condition_on_previous_text`, `compression_ratio_threshold`, `logprob_threshold`, `no_speech_threshold`) y las tres
    de ajuste fino de la IA (`temperatura`, `max_caracteres_bloque`, `peticiones_paralelas`) van en bloques plegados
    «Avanzado».
3.  **El panel lateral vale «para esta transcripción»; la vista Configuración guarda los valores por defecto.** Al
    guardar, los controles laterales de las claves que cambiaron toman el valor nuevo; los demás conservan lo que el
    usuario eligiera a mano. El selector de modelo de IA del lateral sigue guardando su elección en `modelo_ia`, que es
    la misma preferencia que el campo «Modelo de IA» del panel.
4.  **Las preferencias valen solo en la ventana.** La CLI sigue usando el YAML (o `--config`) y sus opciones;
    `docs/specs/cli.md` no cambia. El mismo audio sin opciones puede transcribirse con otro formato en la CLI que en la
    ventana (ya pasa hoy con los controles laterales).
5.  **«Restablecer valores del proyecto» borra todo lo guardado por el panel y también `modelo_ia`.** Después, la
    ventana usa exactamente el YAML.
6.  **Se guarda con un botón «Guardar» que valida todos los campos**; si uno es inválido no se guarda ninguno.

### Decisiones técnicas del diseño

1.  **Formato de `preferencias.json`.** Se conserva `modelo_ia` (spec «Modelo de IA elegido en la ventana») y se añade
    `configuracion`, con secciones y claves del YAML, solo las que difieren de él:

    ```json
    {
      "modelo_ia": "claude-sonnet-5.5",
      "configuracion": {
        "salida": {"formato": "srt"},
        "transcripcion": {"beam_size": 3}
      }
    }
    ```

    `ia.modelo` **nunca** va dentro de `configuracion`. Si `configuracion` queda sin secciones, se quita la clave (no se
    escribe `{}`); una sección sin claves tampoco se escribe.
2.  **Una sola escritura atómica por acción.** Guardar y Restablecer escriben el archivo entero una vez (temporal
    `preferencias.json.tmp` + `os.replace`), incluido `modelo_ia`. El estado de la ventana (`self.configuracion`,
    `_modelo_preferido`, asistente) solo cambia **después** de una escritura correcta; si falla, no se aplica nada y se
    avisa. `guardar_modelo_preferido` (selector lateral) usa la misma escritura.
3.  **Un fallo transitorio de lectura no borra preferencias.** Al escribir, si el archivo no existe se parte de `{}`; si
    es ilegible (JSON inválido o no es un objeto) se reemplaza; si leerlo da `OSError` (permiso, disco), no se escribe
    y se avisa.
4.  **Una preferencia inválida no impide abrir la ventana.** Un YAML inválido sí la impide (es el del proyecto); una
    preferencia inválida es estado del equipo del usuario: se ignora esa clave, se usa la del YAML y se avisa.
5.  **Guardar descarta lo que no sirve.** Al guardar, las claves desconocidas o inválidas que hubiera en
    `configuracion` se quitan, con un aviso; las válidas que el formulario no muestra (porque su historia aún no se
    implementó) se conservan.
6.  **Los topes del panel no tocan la validación del YAML.** Ver «Plan técnico», 2.
7.  **Guardar, Restablecer y las acciones de sesión se rechazan mientras se transcribe o se genera**, con «Espera a que
    termine el proceso en curso.». El motivo **no** es la seguridad de los hilos (eso lo da C0: el hilo de la
    transcripción deja de leer `self.configuracion`, y `self.configuracion` se sustituye, nunca se muta), sino el estado
    de los controles: durante una transcripción los controles laterales están bloqueados (`_bloquear_opciones`) y
    durante una generación el selector de modelo también; cambiarlos por debajo dejaría la vista incoherente con lo
    que está corriendo. Guardar se rechaza además mientras «↻» consulta los modelos o el diálogo de login está abierto
    (D2).
8.  **El estado de la sesión se calcula al mostrar la vista y tras iniciar o cerrar sesión**, nunca al abrir la ventana
    ni con un temporizador. Leer la variable de entorno y dos JSON pequeños ocurre en el hilo principal: milisegundos,
    como `leer_modelo_preferido` hoy.
9.  **El asistente se olvida solo si cambia con qué se crea**: `argumentos_asistente(anterior, modelo_anterior) !=
    argumentos_asistente(nueva, modelo_nuevo)`, y siempre al iniciar o cerrar sesión.
10. **Época de la IA contra respuestas viejas de «↻».** `AppTranscriptor._epoca_ia: int` se captura al lanzar
    `_cargar_modelos_ia` y se incrementa al iniciar sesión, al cerrarla y al cambiar `ia.copilot_enterprise_url`.
    `_mostrar_modelos_ia`, `_fallo_cargar_modelos_ia` y `_sin_sesion_para_modelos` reciben la época capturada y, si no
    coincide, solo devuelven «↻» a su estado y limpian `_consultando_modelos`, sin tocar listas ni abrir el login.

### Lo que dirá la spec (`/cerrar`)

*   La configuración guardada desde el panel gana al YAML solo en la ventana; la CLI no la lee.
*   Como solo se guardan las diferencias, **si el YAML del repositorio cambia, quien tenía guardado un valor igual al
    YAML viejo pasa a usar el nuevo**; quien tenía uno distinto conserva el suyo.
*   Guardar descarta, con aviso, las claves desconocidas o inválidas que hubiera en las preferencias.
*   Las notas conservadas de una generación se pierden también al cambiar la configuración de la IA que usa el
    asistente (spec «Fallo de una parte»), y al iniciar o cerrar sesión desde el panel.

## Recorridos críticos (CUJ)

### CUJ 1: cambiar el formato por defecto a SRT

*   **Dado** `config/settings.yaml` con `salida.formato: "txt"` y sin `preferencias.json`.
*   **Cuando** la persona abre «⚙ Configuración», elige `srt` en «Formato de salida» y pulsa «Guardar».
*   **Entonces** `preferencias.json` contiene `{"configuracion": {"salida": {"formato": "srt"}}}`,
    `config/settings.yaml` no cambia (mismo contenido y misma fecha de modificación), el selector de formato del panel
    lateral muestra `srt`, el pie de la vista dice «Configuración guardada» y la siguiente transcripción exporta
    `reunion.m4a_transcripcion.srt`. Al cerrar y abrir la ventana, el formato sigue en `srt`. La CLI sigue usando `txt`.

### CUJ 2: un valor inválido

*   **Dado** la vista Configuración abierta.
*   **Cuando** la persona escribe `cinco` en «Haz de búsqueda» y `0,5` en «Umbral de silencio», y pulsa «Guardar».
*   **Entonces** bajo «Haz de búsqueda» aparece «`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale
    «cinco»).», el pie dice «No se guardó nada: corrige 1 valor.», y `preferencias.json` no cambia (tampoco el umbral
    de silencio, que era válido).

### CUJ 3: iniciar sesión desde el panel

*   **Dado** ninguna sesión (ni variable de entorno, ni archivo propio, ni opencode).
*   **Cuando** la persona abre Configuración, ve «No has iniciado sesión en GitHub Copilot.» y pulsa «Iniciar sesión».
*   **Entonces** se abre el mismo `DialogoLoginCopilot`; al autorizar, la sección dice «Sesión iniciada con la app. La
    sesión se comprueba al usarla.», «Cerrar sesión» queda habilitado y la siguiente generación crea un asistente nuevo
    con el token nuevo. Mostrar la vista no hizo ninguna petición de red; solo el diálogo la hace.

### CUJ 4: cerrar la sesión propia teniendo también la de opencode

*   **Dado** un token propio en `~/.local/share/transcriptor-audio/copilot.json` y una sesión de opencode.
*   **Cuando** la persona pulsa «Cerrar sesión» y confirma.
*   **Entonces** se borra solo el archivo propio, `~/.local/share/opencode/auth.json` no cambia, y la sección dice «Se
    usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. La sesión se comprueba al usarla.», con
    «Cerrar sesión» deshabilitado e «Iniciar sesión con la app» habilitado.

### CUJ 5: preferencias corruptas

*   **Dado** un `preferencias.json` que no es JSON válido.
*   **Cuando** se abre la ventana y después la vista Configuración.
*   **Entonces** la ventana abre con los valores del YAML, la pestaña Registro anota «Las preferencias <ruta> no son un
    JSON válido; se usan los valores de config/settings.yaml. Al guardar se reemplazará el archivo.» y la vista muestra
    ese aviso arriba. Tras guardar, el aviso desaparece.

## Plan técnico

### Estructura

```text
                         hilo principal (Tk)
 ┌──────────────────────────────────────────────────────────────────┐
 │ ui.main()                                                        │
 │   proyecto = cargar_configuracion()            (YAML, sin cambios)│
 │   efectiva, avisos = combinar(proyecto, leer_ajustes())          │
 │   AppTranscriptor(efectiva, proyecto=proyecto, avisos=avisos)    │
 │                                                                  │
 │ AppTranscriptor                                                  │
 │   self.configuracion  ← SIEMPRE un dict nuevo, nunca mutado      │
 │   _procesar_transcripcion(opciones, parametros)  (C0: no lee self.configuracion)
 │   mostrar_vista(VISTA_CONFIGURACION) ──► PanelConfiguracion      │
 │                                     (src/ui_configuracion.py, solo pinta)
 │   Guardar ──► guardar_formulario(...) ─► ResultadoGuardado       │
 │   aplicar_guardado(resultado)                                    │
 │      ├─ valores_laterales(cambiadas, efectiva) → variables Tk    │
 │      ├─ argumentos_asistente cambió → olvidar_asistente()  (D1)  │
 │      ├─ dominio cambió → _epoca_ia += 1, listas a auto+config(D1)│
 │      └─ modelo_preferido, var_modelo_ia, etiquetas         (D2)  │
 │   Sesión ──► copilot.estado_sesion / describir_sesion (disco)    │
 │          ──► DialogoLoginCopilot (red, en su propio hilo)        │
 │          ──► _cerrar_sesion_copilot() ─► copilot.cerrar_sesion_propia
 └──────────────────────────────────────────────────────────────────┘
 configuracion.py: _tabla, cargar_configuracion, AjustesLeidos, leer_ajustes, combinar, TOPES_PANEL,
                   valor_desde_formulario, validar_formulario, resumen_errores, guardar_ajustes,
                   restablecer_ajustes, claves_cambiadas, REQUIEREN_REINICIO, ResultadoGuardado,
                   guardar_formulario, restablecer_formulario, valores_laterales
 idiomas.py:       IDIOMAS_DISPONIBLES, opciones_de_idioma, codigo_de_idioma, nombre_de_idioma
 flujo_documentos.py: argumentos_asistente
 copilot.py:       Sesion.token(repr=False), EstadoSesion, estado_sesion, DescripcionSesion,
                   describir_sesion, cerrar_sesion_propia
 Ninguna importa tkinter ni hace peticiones de red.
```

### 1. Leer y combinar los ajustes (historia A1)

En `src/configuracion.py` (pseudocódigo de firmas, no código final):

```text
CLAVE_AJUSTES = "configuracion"

_mensaje_invalido(seccion, clave, valor, esperado=None) -> str
    # «`s.k` debe ser <esperado> (vale «v»)», SIN punto final; esperado por defecto = _tabla()[(s,k)].esperado.
    # cargar_configuracion:  f"En la configuración {ruta}, {_mensaje_invalido(...)}."   (texto de hoy, sin cambios)

@dataclass(frozen=True)
AjustesLeidos:
    valores: dict[tuple[str, str], Any]     # (sección, clave) → valor tal como vino del JSON
    avisos: list[str]
    ilegible: bool                          # True solo si el archivo existe y no es JSON o no es un objeto

leer_ajustes() -> AjustesLeidos
    # No existe                       → valores {}, avisos [], ilegible False
    # OSError al leer                 → valores {}, avisos [«Las preferencias <ruta> no se pudieron leer (<motivo>);
    #                                    se usan los valores de config/settings.yaml.»], ilegible False
    # JSON inválido o no es un objeto → valores {}, avisos [«Las preferencias <ruta> no son un JSON válido; se usan
    #                                    los valores de config/settings.yaml. Al guardar se reemplazará el archivo.»],
    #                                    ilegible True
    # datos["configuracion"] falta    → valores {}
    # datos["configuracion"] no es un objeto → aviso «En <ruta>, «configuracion» no es un objeto; se ignora.»
    # una sección que no es un objeto → aviso «En <ruta>, la sección `<s>` no es un objeto; se ignora.»

combinar(proyecto: dict, ajustes: AjustesLeidos) -> tuple[dict, list[str]]
    # efectiva = copy.deepcopy(proyecto); avisos = list(ajustes.avisos)
    # Por cada (s, k), valor en ajustes.valores, en el orden del archivo:
    #   (s,k) == ("ia","modelo")      → «En <ruta>, `ia.modelo` no se guarda en «configuracion» (el modelo elegido va
    #                                    en «modelo_ia»); se ignora.»
    #   (s,k) no está en _tabla()      → «En <ruta>, `s.k` no es una clave de la configuración; se ignora.»
    #   número no finito (math.isfinite) o not _tabla()[(s,k)].valida(valor)
    #                                  → f"En {ruta}, {_mensaje_invalido(s, k, valor)}; se usa el valor de
    #                                     config/settings.yaml."
    #   si no                          → efectiva[s][k] = valor
    # No lanza nunca.
```

*   `ui.main()` pasa a `proyecto = cargar_configuracion()`, `efectiva, avisos = combinar(proyecto, leer_ajustes())`,
    cada aviso a `log.warning`, y `AppTranscriptor(efectiva, proyecto=proyecto, avisos=avisos)`. El constructor acepta
    `proyecto: Optional[dict] = None` (si falta, el mismo dict) y `avisos: Sequence[str] = ()`, guarda
    `self.configuracion_proyecto` y `self.avisos_preferencias = list(avisos)`, y escribe cada aviso en Registro con
    `_log` después de `_construir_ui`.
*   `leer_modelo_preferido`, `modelo_ia_efectivo` y la CLI no cambian.

### 2. Convertir, validar y guardar (historias A2a y A2b)

```text
TOPES_PANEL = {                                   # solo el formulario; cargar_configuracion no los usa
    ("transcripcion", "beam_size"):            (1, 20,      "un número entero entre 1 y 20"),
    ("transcripcion", "best_of"):              (1, 20,      "un número entero entre 1 y 20"),
    ("transcripcion", "temperature"):          (0, 2,       "un número entre 0 y 2"),
    ("transcripcion", "no_speech_threshold"):  (0, 1,       "un número entre 0 y 1"),
    ("ia", "temperatura"):                     (0, 2,       "un número entre 0 y 2"),
    ("ia", "peticiones_paralelas"):            (1, 8,       "un número entero entre 1 y 8"),
    ("ia", "max_caracteres_bloque"):           (5000, 500000, "un número entero entre 5000 y 500000"),
}
# Para estas claves, el «esperado» del mensaje es el del tope en TODOS sus errores (también «cinco»).

valor_desde_formulario(seccion, clave, valor_widget) -> Any    # lanza ErrorConfiguracion(_mensaje_invalido(...) + ".")
    # El tipo sale del valor por defecto de _tabla():
    #   bool  → el widget da bool (interruptor); otro tipo → error
    #   int   → texto.strip() con re.fullmatch(r"-?\d+") → int; «3.0», «», «cinco» → error
    #   float → texto.strip().replace(",", ".") → float; «» o no numérico → error; no finito («nan», «inf», «1e999»)
    #           → error
    #   str   → texto.strip()
    # Después: _tabla()[…].valida(valor); el tope de TOPES_PANEL si lo hay; y además:
    #   ia.copilot_enterprise_url: "" o re.fullmatch(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+", valor); si no:
    #       «`ia.copilot_enterprise_url` debe ser un nombre de dominio sin https:// ni barras, como empresa.ghe.com,
    #        o estar vacío (vale «v»).»
    #   historial.ruta: ruta = Path(valor); si no es absoluta, RAIZ_PROYECTO / ruta; resuelta con .resolve().
    #       Si está dentro de RAIZ_PROYECTO y no dentro de RAIZ_PROYECTO / "data":
    #       «`historial.ruta` no puede estar dentro de la carpeta del proyecto salvo en data/ (vale «v»).»  (regla 8)
    #       Si el primer antecesor existente de ruta.parent no es un directorio escribible (os.access W_OK):
    #       «`historial.ruta` está en una carpeta que no se puede crear ni escribir (vale «v»).»
    #       La validación no crea carpetas.

validar_formulario(valores_widget: dict[(s,k), Any], modelo_ia: Optional[str] = None)
        -> tuple[dict[(s,k), Any], dict[(s,k), str]]
    # Acepta un subconjunto de claves. Devuelve (convertidos, errores), los errores en el orden de entrada.
    # ("ia","modelo") no puede venir en valores_widget (ValueError: va en modelo_ia).
    # Si modelo_ia y copilot.familia_excluida(modelo_ia) (import dentro de la función, para que configuracion.py no
    # cargue httpx al importarse): errores[("ia","modelo")] = «El modelo «<m>» es de la familia «<f>», que no está
    # autorizada por la empresa. Elige otro modelo.»  (regla 7)

resumen_errores(n: int) -> str
    # 1 → «No se guardó nada: corrige 1 valor.»; n > 1 → «No se guardó nada: corrige <n> valores.»

guardar_ajustes(proyecto, valores: dict[(s,k), Any], modelo_ia: Optional[str] = None) -> list[str]
    # Lanza OSError si no puede leer (salvo «no existe») o escribir. Devuelve avisos de lo descartado.
    # 1. datos = _leer_para_escribir(): no existe → {}; JSON inválido o no objeto → {}; OSError → se propaga.
    # 2. previas = claves válidas de datos["configuracion"] (mismas reglas que combinar); las desconocidas o inválidas
    #    se descartan con el aviso «Se descartaron de <ruta> claves que no sirven: `a.b`, `c.d`.»
    # 3. nuevas = previas, sustituidas por `valores`; se quitan las que valen igual que proyecto[s][k].
    # 4. datos["configuracion"] = nuevas agrupadas por sección; si no queda ninguna, se borra la clave.
    # 5. modelo_ia: None → se deja datos["modelo_ia"] como esté; igual a proyecto["ia"]["modelo"] → se borra la clave;
    #    otro → datos["modelo_ia"] = modelo_ia. (familia excluida → ValueError: validar_formulario ya lo impide)
    # 6. _escribir_preferencias(datos)  — UNA escritura atómica.

restablecer_ajustes() -> None                              # lanza OSError si no puede leer (salvo no existe) o escribir
    # datos = _leer_para_escribir(); borra "configuracion" y "modelo_ia"; conserva el resto; _escribir_preferencias.

_escribir_preferencias(datos: dict) -> None
    # mkdir(parents=True, exist_ok=True); escribe RUTA_PREFERENCIAS.with_suffix(".json.tmp"); os.replace al final.
    # guardar_modelo_preferido pasa a usar _leer_para_escribir y _escribir_preferencias (con un OSError de lectura ya
    # no reescribe el archivo desde cero; la ventana sigue tratando su OSError como hoy).
```

### 3. Componer el guardado sin ventana (historia A3)

```text
claves_cambiadas(anterior: dict, nueva: dict) -> set[(s,k)]     # solo claves de _tabla()
REQUIEREN_REINICIO = frozenset({("historial", "ruta")})

@dataclass
ResultadoGuardado:
    errores: dict[(s,k), str]          # vacío si se intentó escribir
    efectiva: Optional[dict]           # None si no se guardó
    modelo_preferido: Optional[str]    # modelo_ia que quedó guardado (None = ninguno); solo si efectiva no es None
    avisos: list[str]                  # descartes de guardar_ajustes + avisos de combinar tras releer
    cambiadas: set[(s,k)]              # claves_cambiadas(anterior, efectiva) y ("ia","modelo") si cambió
                                       # modelo_ia_efectivo
    mensaje: str                       # pie de la vista

guardar_formulario(proyecto, anterior, valores_widget, modelo_ia=None, preferido_anterior=None) -> ResultadoGuardado
    # 1. convertidos, errores = validar_formulario(valores_widget, modelo_ia)
    #    errores → ResultadoGuardado(errores, None, None, [], set(), resumen_errores(len(errores)))
    # 2. try: descartes = guardar_ajustes(proyecto, convertidos, modelo_ia)
    #    except OSError as e: → ResultadoGuardado({}, None, None, [], set(),
    #                              f"No se pudo guardar la configuración: {motivo_de_error(e)}.")   (nada se aplica)
    # 3. efectiva, avisos = combinar(proyecto, leer_ajustes()); preferido = leer_modelo_preferido()
    # 4. cambiadas = claves_cambiadas(anterior, efectiva) (+ ("ia","modelo") si
    #    modelo_ia_efectivo(anterior, preferido_anterior) != modelo_ia_efectivo(efectiva, preferido))
    # 5. mensaje = «Configuración guardada», más « · el historial nuevo se abrirá al reiniciar la app» si
    #    cambiadas ∩ REQUIEREN_REINICIO
    #    → ResultadoGuardado({}, efectiva, preferido, descartes + avisos, cambiadas, mensaje)

restablecer_formulario(proyecto, anterior, preferido_anterior) -> ResultadoGuardado          # historia C2
    # restablecer_ajustes(); OSError → mensaje «No se pudo restablecer la configuración: <motivo>.», efectiva None
    # si va bien: efectiva, avisos = combinar(proyecto, leer_ajustes()); preferido None; cambiadas como arriba;
    # mensaje «Se restablecieron los valores de config/settings.yaml»

valores_laterales(cambiadas: set[(s,k)], configuracion: dict) -> dict[str, Any]
    # Solo para las claves cambiadas que tienen control lateral; las claves del dict son los nombres de las variables:
    #   ("modelo","nombre")            → "var_modelo": valor
    #   ("modelo","dispositivo")       → "var_dispositivo": valor
    #   ("modelo","compute_type")      → "var_compute": valor
    #   ("transcripcion","idioma")     → "var_idioma": nombre_de_idioma(codigo),
    #                                    "opciones_idioma": opciones_de_idioma(codigo)
    #   ("salida","formato")           → "var_formato": valor
    #   ("salida","incluir_timestamps")→ "var_timestamps": valor
```

`src/idiomas.py` (nuevo, sin Tk): `IDIOMAS_DISPONIBLES`, `opciones_de_idioma` y `codigo_de_idioma` se mueven aquí
desde `src/ui.py`, y se añade `nombre_de_idioma(codigo) = IDIOMAS_DISPONIBLES.get(codigo, codigo)` (lo que hoy hace
`src/ui.py:161`). `src/ui.py` los importa de `src.idiomas`, así que `from src.ui import codigo_de_idioma` (tests de
`tests/test_ui.py`) sigue funcionando. `src/ui_configuracion.py` los importa de `src.idiomas`, no de `src.ui`.

### 4. El hilo de la transcripción deja de leer la configuración (historia C0)

Hoy `_procesar_transcripcion` lee `self.configuracion["transcripcion"]` **en el hilo de fondo** (`src/ui.py:666`). En
C0, `_iniciar_transcripcion` captura `parametros = self.configuracion["transcripcion"]` en el hilo principal, junto a
`opciones`, y lanza el hilo con `args=(opciones, parametros)`; `_procesar_transcripcion(self, opciones, parametros)` usa
`parametros` y no menciona `self.configuracion`. Sin cambios de comportamiento.

### 5. La vista «Configuración» (historias C1 y C2)

`src/ui_configuracion.py`:

```text
@dataclass(frozen=True)
Campo:
    seccion: str
    clave: str
    etiqueta: str
    control: str          # "lista" | "lista_editable" | "botones" | "interruptor" | "texto"
    grupo: str            # "Transcripción" | "Salida" | "IA" | "Historial"
    avanzado: bool = False
    opciones: tuple = ()  # para "lista", "lista_editable" y "botones"
    nota: str = ""        # texto bajo el campo (p. ej. «Se aplica al reiniciar la app.»)

CAMPOS: tuple[Campo, ...]        # en el orden en que se pintan
motivo_para_no_guardar(transcribiendo: bool, generando: bool, consultando_modelos: bool = False,
                       login_abierto: bool = False) -> Optional[str]
    # transcribiendo o generando → «Espera a que termine el proceso en curso.»
    # consultando_modelos        → «Espera a que termine la consulta de modelos de IA.»        (D2)
    # login_abierto              → «Termina o cancela el inicio de sesión en GitHub Copilot.»  (D2)
    # si no → None
aviso_modelo(modelo: str) -> Optional[str]                                                     (D2)
    # familia excluida → «El modelo configurado «<m>» es de la familia «<f>», que no está autorizada por la empresa:
    #                     no se enviará. Elige otro.»;  si no → None

class PanelConfiguracion(ctk.CTkFrame):
    __init__(master, app)          # construye CAMPOS en un CTkScrollableFrame; llama a refrescar()
    refrescar()                    # vuelve a poner en cada campo el valor de app.configuracion: descarta lo no
                                   # guardado; repinta el recuadro de avisos (app.avisos_preferencias) y, en E2, la
                                   # sección Sesión
    _guardar()                     # pide app.guardar_configuracion(valores_widget, modelo_ia) y pinta el Resultado
    _restablecer()                 # (C2) pide app.restablecer_configuracion() y pinta el Resultado
```

Tabla de campos (15 fuera de `ia` + 6 de `ia` = 21):

| Historia | Grupo | Clave | Etiqueta | Control | Se aplica |
|---|---|---|---|---|---|
| C1 | Transcripción | `modelo.nombre` | Modelo de Whisper | lista (`MODELOS_WHISPER`) | en la siguiente transcripción |
| C1 | Transcripción | `transcripcion.idioma` | Idioma | lista editable (`opciones_de_idioma`); texto libre se guarda tal cual, el nombre se traduce con `codigo_de_idioma` | ídem |
| C1 | Transcripción | `modelo.dispositivo` | Dispositivo | lista (`DISPOSITIVOS`) | ídem |
| C1 | Transcripción | `modelo.compute_type` | Precisión | lista (`TIPOS_COMPUTO`) | ídem |
| C1 | Salida | `salida.formato` | Formato de salida | botones (`FORMATOS`) | en la siguiente transcripción y en «Guardar como…» |
| C1 | Salida | `salida.incluir_timestamps` | Incluir marcas de tiempo | interruptor | ídem |
| C1 | Salida | `salida.palabra_por_palabra` | Marcas por palabra | interruptor | en la siguiente transcripción |
| C2 | Transcripción › Avanzado | `transcripcion.beam_size` | Haz de búsqueda | texto | ídem |
| C2 | Transcripción › Avanzado | `transcripcion.best_of` | Candidatos | texto | ídem |
| C2 | Transcripción › Avanzado | `transcripcion.temperature` | Temperatura de Whisper | texto | ídem |
| C2 | Transcripción › Avanzado | `transcripcion.condition_on_previous_text` | Usar el texto anterior como contexto | interruptor | ídem |
| C2 | Transcripción › Avanzado | `transcripcion.compression_ratio_threshold` | Umbral de compresión | texto | ídem |
| C2 | Transcripción › Avanzado | `transcripcion.logprob_threshold` | Umbral de probabilidad | texto | ídem |
| C2 | Transcripción › Avanzado | `transcripcion.no_speech_threshold` | Umbral de silencio | texto | ídem |
| C2 | Historial | `historial.ruta` | Archivo del historial (relativo a la carpeta del proyecto) | texto, nota «Se aplica al reiniciar la app.» | **al reiniciar la app** |
| D2 | IA | `ia.modelo` | Modelo de IA | lista + «↻» | en la siguiente generación |
| D1 | IA | `ia.copilot_enterprise_url` | Dominio de GitHub Enterprise (vacío = github.com) | texto | en la siguiente generación, «↻» y el estado de la sesión |
| D1 | IA | `ia.revision_fidelidad` | Revisión de fidelidad | interruptor | en la siguiente generación |
| D1 | IA › Avanzado | `ia.temperatura` | Temperatura de la IA | texto | ídem |
| D1 | IA › Avanzado | `ia.max_caracteres_bloque` | Caracteres por parte | texto | ídem |
| D1 | IA › Avanzado | `ia.peticiones_paralelas` | Partes a la vez | texto | ídem |

Cada campo lleva su etiqueta, debajo la clave del YAML en gris pequeño, su nota si la tiene, y una línea de error vacía.
Pie: «Guardar», «Restablecer valores del proyecto» (C2) y una línea de estado. Arriba, si `app.avisos_preferencias` no
está vacío, un recuadro con los avisos, uno por línea.

En `AppTranscriptor` (`src/ui.py`):

```text
VISTA_CONFIGURACION = "⚙  Configuración"
self.panel_configuracion = None            # en __init__, junto a self.panel_historial
self.nav: values=[VISTA_TRANSCRIBIR, VISTA_HISTORIAL, VISTA_CONFIGURACION]
_configurar_atajos: self.bind("<Control-Key-3>", lambda e: self.mostrar_vista(VISTA_CONFIGURACION))

mostrar_vista(vista):
    si vista == VISTA_HISTORIAL y not self.historial: diálogo de hoy; vista = VISTA_TRANSCRIBIR
    self.nav.set(vista); self.vista_actual = vista
    self.vista_transcribir.grid_remove()
    para panel en (self.panel_historial, self.panel_configuracion): si panel no es None: panel.grid_remove()
    si vista == VISTA_HISTORIAL:
        si self.panel_historial es None:
            from src.ui_historial import PanelHistorial
            self.panel_historial = PanelHistorial(self, self, self.historial)
            self.panel_historial.grid(row=1, column=0, sticky="nsew")
        si no: self.panel_historial.refrescar(); self.panel_historial.grid()
    si vista == VISTA_CONFIGURACION:
        igual, con `from src.ui_configuracion import PanelConfiguracion` y PanelConfiguracion(self, self)
    si no: self.vista_transcribir.grid()

guardar_configuracion(valores_widget, modelo_ia=None) -> ResultadoGuardado
    motivo = motivo_para_no_guardar(self._transcribiendo(), self._generando_ia(), …)
    si motivo: messagebox.showwarning("Configuración", motivo); devuelve ResultadoGuardado vacío con mensaje=motivo
    resultado = guardar_formulario(self.configuracion_proyecto, self.configuracion, valores_widget, modelo_ia,
                                   self._modelo_preferido)
    si resultado.efectiva es None y not resultado.errores: messagebox.showerror("Configuración", resultado.mensaje)
    si resultado.efectiva no es None: self.aplicar_guardado(resultado); _log de las claves cambiadas
    devuelve resultado

restablecer_configuracion() -> Optional[ResultadoGuardado]                    # C2
    mismo rechazo; messagebox.askyesno("Restablecer configuración", «¿Volver a los valores de config/settings.yaml?
    Se borrarán los cambios guardados en este panel y el modelo de IA elegido.»); no → None
    resultado = restablecer_formulario(self.configuracion_proyecto, self.configuracion, self._modelo_preferido)
    error → messagebox.showerror("Configuración", resultado.mensaje); nada se aplica
    si va bien: self.aplicar_guardado(resultado)

aplicar_guardado(resultado)                                  # solo hilo principal; solo tras una escritura correcta
    anterior, modelo_anterior = self.configuracion, self._modelo_ia_configurado()
    self.configuracion = resultado.efectiva                  # sustitución, nunca mutación
    self.avisos_preferencias = resultado.avisos
    para nombre, valor en valores_laterales(resultado.cambiadas, resultado.efectiva):
        "opciones_idioma" → self.combo_idioma.configure(values=valor); el resto → getattr(self, nombre).set(valor)
    (C2) self._modelo_preferido = resultado.modelo_preferido; self.var_modelo_ia.set(self._modelo_ia_configurado())
    (C2) refrescar las etiquetas de estado de las pestañas de IA que mostraban el texto del modelo anterior
         (lo que hace hoy _al_cambiar_modelo_ia)
    (C2 y D1) si argumentos_asistente(anterior, modelo_anterior) != argumentos_asistente(nueva, modelo_nuevo):
         self._documentos.olvidar_asistente()          (en C2, sin argumentos_asistente aún: si cambió el modelo)
    (D1) si ("ia","copilot_enterprise_url") en cambiadas: self._epoca_ia += 1;
         combo_modelo_ia (y el del panel) → opciones_de_modelo([MODELO_AUTO], self._modelo_ia_configurado())
```

*   **Los valores temporales del lateral se respetan**: solo cambian las variables de las claves que cambiaron en ese
    guardado.
*   **`historial.ruta`** cambia en `self.configuracion`, pero `self.historial`, `GestorDocumentos` y `PanelHistorial`
    siguen con la base abierta; al reiniciar, `Historial(self.configuracion["historial"]["ruta"])` abre la nueva.

### 6. Grupo IA (historias D1 y D2)

*   **D1.** `flujo_documentos.argumentos_asistente(configuracion, modelo) -> dict` devuelve `modelo`, `temperatura`,
    `max_caracteres_bloque`, `revision_fidelidad`, `peticiones_paralelas` y `enterprise_url`
    (`copilot_enterprise_url or None`). `_crear_asistente` pasa a `AsistenteIA(**argumentos_asistente(self.configuracion,
    self._modelo_ia_configurado()))`. `aplicar_guardado` olvida el asistente solo si esos argumentos cambian.
    `_epoca_ia` (empieza en 0): `_cargar_modelos_ia` la captura, marca `self._consultando_modelos = True`, y pasa la
    época a `_mostrar_modelos_ia(opciones, epoca)`, `_fallo_cargar_modelos_ia(mensaje, epoca)` y
    `_sin_sesion_para_modelos(epoca)`; cada uno empieza con `self._consultando_modelos = False`,
    `btn_cargar_modelos_ia` a `normal` y, si `epoca != self._epoca_ia`, `_log("Se descarta una lista de modelos de una
    sesión o un dominio anteriores")` y vuelve.
*   **D2.** El campo «Modelo de IA» es un `CTkOptionMenu` con **su propia** variable (no `var_modelo_ia`). Valor inicial:
    `app._modelo_ia_configurado()`; opciones: `app.combo_modelo_ia.cget("values")`, que ya pasan por
    `copilot.opciones_de_modelo` y nunca incluyen una familia excluida. Si el modelo efectivo es de una familia
    excluida (YAML o preferencia antigua), se muestra el texto de `aviso_modelo` bajo el campo, en rojo, y el modelo no
    está entre las opciones; Guardar lo rechaza con el mensaje de `validar_formulario` hasta que se elija otro. No hay
    texto libre. `_mostrar_modelos_ia` actualiza también el menú del panel si existe. «↻» del panel llama a
    `app._cargar_modelos_ia`. Al guardar, el panel pasa `modelo_ia = <valor del campo>` a `guardar_configuracion`: el
    modelo y el resto se escriben juntos en una sola escritura; **no** se llama a `_al_cambiar_modelo_ia`. Guardar se
    rechaza si `self._consultando_modelos` o `self._login_abierto` (este lo pone `_iniciar_sesion_copilot` y lo quita
    su `al_terminar`).
*   La defensa en el envío (`AsistenteIA._modelo_para_peticion`) no cambia.

### 7. Sesión de GitHub Copilot (historias B, E1 y E2)

En `src/copilot.py`:

```text
Sesion.token: str = field(repr=False)              # B: repr(sesion) no muestra el token

ORIGEN_VARIABLE, ORIGEN_APP, ORIGEN_OPENCODE = "variable", "app", "opencode"

@dataclass(frozen=True)
EstadoSesion:
    origen: Optional[str]          # uno de los tres o None
    hay_token_propio: bool         # RUTA_TOKEN se puede leer, es un objeto JSON y tiene "token" de texto no vacío
                                   # (aunque la variable lo tape o sea de otro dominio)

estado_sesion(enterprise_url) -> EstadoSesion
    # sesion = leer_token(enterprise_url) — solo entorno y disco, sin red, sin escribir
    # origen: VARIABLE_ENTORNO → "variable"; str(RUTA_TOKEN) → "app"; str(RUTA_AUTH_OPENCODE) → "opencode"; None → None

@dataclass(frozen=True)
DescripcionSesion:
    texto: str
    puede_iniciar: bool
    texto_iniciar: str             # «Iniciar sesión» o «Iniciar sesión con la app»
    puede_cerrar: bool             # == hay_token_propio

describir_sesion(estado) -> DescripcionSesion
cerrar_sesion_propia(enterprise_url) -> EstadoSesion            # E1
    # cerrar_sesion() (borra solo RUTA_TOKEN; OSError se propaga) y devuelve estado_sesion(enterprise_url)
```

Textos de `describir_sesion`. Las frases se unen con un espacio. Orden: frase del origen; después, si toca, la frase de
la sesión propia que no se usa; al final, si hay origen, «La sesión se comprueba al usarla.».

| Origen | `hay_token_propio` | `texto` | Iniciar | Cerrar |
|---|---|---|---|---|
| None | no | «No has iniciado sesión en GitHub Copilot.» | sí, «Iniciar sesión» | no |
| None | sí | «No has iniciado sesión en GitHub Copilot. Hay una sesión guardada por la app para otro dominio de GitHub.» | sí, «Iniciar sesión» | sí |
| app | sí | «Sesión iniciada con la app. La sesión se comprueba al usarla.» | no | sí |
| opencode | no | «Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. La sesión se comprueba al usarla.» | sí, «Iniciar sesión con la app» | no |
| opencode | sí | «Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. Hay una sesión guardada por la app para otro dominio de GitHub. La sesión se comprueba al usarla.» | sí, «Iniciar sesión con la app» | sí |
| variable | no | «Se usa el token de la variable de entorno COPILOT_GITHUB_TOKEN. La app no puede cerrarlo: quita la variable para usar otra sesión. La sesión se comprueba al usarla.» | no | no |
| variable | sí | «Se usa el token de la variable de entorno COPILOT_GITHUB_TOKEN. La app no puede cerrarlo: quita la variable para usar otra sesión. Hay además una sesión guardada por la app que ahora no se usa. La sesión se comprueba al usarla.» | no | sí |

Ningún texto contiene el token.

En la vista (E2), sección «Sesión de GitHub Copilot» al principio del grupo IA:

*   **Mostrar.** `refrescar()` llama a `estado_sesion(app.configuracion["ia"]["copilot_enterprise_url"] or None)` y
    pinta `describir_sesion`. `AppTranscriptor.__init__` no la llama: el panel se construye la primera vez que se
    muestra.
*   **Dominio editado sin guardar.** Un `<KeyRelease>` del campo de dominio compara su texto (sin espacios) con el
    guardado; si difieren, los dos botones de sesión se deshabilitan y la sección añade «Guarda primero el dominio».
*   **Iniciar sesión.** Rechazado durante un proceso (`motivo_para_no_guardar` con transcripción o generación). Si no,
    `app._iniciar_sesion_copilot(al_conectar)` (el diálogo de siempre, título «Iniciar sesión en GitHub Copilot»),
    con `al_conectar` que hace `self._epoca_ia += 1`, `olvidar_asistente()` y `refrescar_sesion()`. No recarga la
    lista de modelos: eso sigue siendo «↻».
*   **Cerrar sesión.** Lo hace `AppTranscriptor._cerrar_sesion_copilot(self) -> Optional[copilot.EstadoSesion]`:
    rechazo durante un proceso; `messagebox.askyesno("Cerrar sesión", «¿Cerrar la sesión de GitHub Copilot guardada por
    la app? La de opencode y la variable de entorno no se tocan.»)`; `cerrar_sesion_propia(...)`; con `OSError`,
    `messagebox.showerror("Sesión de GitHub Copilot", f"No se pudo cerrar la sesión:\n{motivo}")` y devuelve `None`.
    Si va bien: `self._epoca_ia += 1`; `olvidar_asistente()`; `combo_modelo_ia` (y el del panel) a
    `opciones_de_modelo([MODELO_AUTO], actual)`; `_log("Sesión de GitHub Copilot cerrada")`; devuelve el estado, que el
    panel pinta.
*   **Hilos.** Todo ocurre en el hilo principal salvo el device flow, que ya corre en el hilo `login-copilot` del
    diálogo y vuelve con su `_en_ui`. La CLI (`--copilot-login`, `--copilot-logout`) no cambia.

### 8. Qué no cambia

*   `cargar_configuracion`, sus mensajes, y que un YAML inválido impide abrir la ventana.
*   `historial.py`, `asistente_ia.py`, `persistencia.py`, `flujo_transcripcion.py`, `ui_copilot.py`, `ui_historial.py`,
    `main.py`.
*   El modelo de concurrencia de `00-actual.md`: el panel no lanza hilos propios.
*   El tráfico de red: solo «Iniciar sesión» (el device flow de siempre) y «↻» del panel (la misma consulta que «↻»
    del lateral).

## Historias

Cada historia cabe en tres criterios de `/story` y en un `/pair`, deja `./venv/bin/python -m pytest -q` en verde, sin
red (regla 3), tiene paso rojo y su lista **cerrada** de archivos: si necesita otro, se para y se vuelve a este diseño.
La documentación (`docs/specs/configuracion.md`, `docs/specs/documentos-ia.md`, `docs/disenos/00-actual.md`, `EGM.md`,
`src/EGM.md`, `AGENTS.md`, `.context/*` y `README.md`: la sección «Configuración» y los atajos `Ctrl+3`) la actualiza
`/cerrar`.

| Orden | Historia | Carril | Depende de | Backlog |
|---|---|---|---|---|
| 1 | A1 — Las preferencias guardadas ganan al YAML al abrir la ventana | M | — | #5 |
| 2 | A2a — Convertir y validar los valores del formulario | S | A1 | #5 |
| 3 | A2b — Guardar y restablecer las preferencias en una escritura atómica | S | A2a | #5 |
| 4 | A3 — Componer el guardado y los valores laterales sin ventana | S | A2b | #5 |
| 5 | C0 — El hilo de la transcripción deja de leer la configuración | S | — | #5 |
| 6 | C1 — Vista «Configuración» con Transcripción y Salida | M | A3, C0 | #5 |
| 7 | C2 — Avanzado de Transcripción, Historial y Restablecer | M | C1 | #5 |
| 8 | D1 — IA: dominio, fidelidad y ajuste fino | M | C2 | #5 |
| 9 | D2 — IA: el modelo en el panel | M | D1 | #5 |
| — | 16 — Límite de entrada (historia ajena, toca `copilot.py`) | M | — | Salud #26 |
| 10 | B — Saber de dónde sale la sesión, sin red | S | 16 | #6 |
| 11 | E1 — Cerrar solo la sesión propia | S | B | #6 |
| 12 | E2 — Sección Sesión en la vista | M | E1, D2 | #6 |

A1–A3 y C0 no cambian nada visible (salvo A1 al arrancar). B y E1 van después de la 16, en serie, porque las tres tocan
`src/copilot.py`. D va antes que E2 (E2 usa `_epoca_ia` y `_login_abierto`, que llegan en D1 y D2).

### Dobles de test

*   `preferencias_aisladas` (autouse, `tests/conftest.py`) ya aísla `RUTA_PREFERENCIAS`.
*   `rutas_aisladas` es local de `tests/test_copilot.py`: los tests de B y E1 van en ese archivo.
*   «Sin red» se comprueba parcheando `copilot.httpx.get` y `copilot.httpx.post` con una función que lanza
    `AssertionError`.
*   «El YAML no cambia»: YAML en `tmp_path`, se comparan contenido y `st_mtime_ns` antes y después.
*   Los métodos de la ventana que se prueban sin ventana (C0, D1) se prueban sin instanciar `AppTranscriptor`: con
    `inspect.getsource` o llamando al método sin enlazar con un `types.SimpleNamespace` como `self`.

### Historia A1 — Las preferencias guardadas ganan al YAML al abrir la ventana

**Criterios:**

1.  *Dado* un YAML con `salida.formato: "txt"` y `transcripcion.beam_size: 5`, y un `preferencias.json` con
    `{"configuracion": {"salida": {"formato": "srt"}}}`, *cuando* se combina, *entonces* la efectiva tiene `formato`
    `srt` y `beam_size` 5, sin avisos, y el YAML no cambia.
2.  *Dado* un `preferencias.json` con, dentro de `configuracion`, `transcripcion.beam_size: "cinco"`,
    `transcripcion.temperature: NaN`, `audio.sample_rate: 16000`, `ia.modelo: "x"` y una sección `salida: 3`, *cuando*
    se combina, *entonces* todas toman el valor del YAML y hay cinco avisos, entre ellos «En <ruta>,
    `transcripcion.beam_size` debe ser un número entero mayor que 0 (vale «cinco»); se usa el valor de
    config/settings.yaml.» y «En <ruta>, la sección `salida` no es un objeto; se ignora.».
3.  *Dado* un `preferencias.json` que no es JSON, o es una lista, o tiene `"configuracion": 3`, *cuando* se combina,
    *entonces* la efectiva es igual a la del YAML, con el aviso correspondiente de «Plan técnico», 1, e `ilegible` es
    verdadero solo en los dos primeros casos; sin archivo, no hay aviso.

**Tests** (`tests/test_configuracion.py`): `test_un_ajuste_guardado_gana_al_yaml_sin_tocarlo`,
`test_sin_preferencias_la_efectiva_es_la_del_yaml_sin_avisos`,
`test_ajustes_invalidos_desconocidos_no_finitos_e_ia_modelo_se_ignoran_con_aviso`,
`test_preferencias_ilegibles_dan_aviso_y_valores_del_yaml` (parametrizado: texto no JSON, lista JSON,
`"configuracion": 3`). Los mensajes de `cargar_configuracion` siguen cubiertos por los tests existentes.

**Archivos (lista cerrada):** `src/configuracion.py` (`CLAVE_AJUSTES`, `_mensaje_invalido`, `AjustesLeidos`,
`leer_ajustes`, `combinar`), `src/ui.py` (`main`; `AppTranscriptor.__init__` con `proyecto` y `avisos`),
`tests/test_configuracion.py`.

**Verificación en la ventana real:** con `{"configuracion": {"salida": {"formato": "srt"}}}` en
`~/.local/share/transcriptor-audio/preferencias.json`, la ventana abre con `srt`; con `{` en el archivo, abre con `txt`
y Registro muestra el aviso; `git status` no muestra `config/settings.yaml`.

### Historia A2a — Convertir y validar los valores del formulario

**Criterios:**

1.  *Dado* el formulario, *cuando* se convierten «3» en `beam_size`, «0,6» en `no_speech_threshold`, «-1» en
    `logprob_threshold` y «» en `copilot_enterprise_url`, *entonces* dan 3, 0.6, -1.0 y ""; y «cinco», «3.0» y «50» en
    `beam_size`, «nan» y «1e999» en `temperature` lanzan `ErrorConfiguracion`, el primero con «`transcripcion.beam_size`
    debe ser un número entero entre 1 y 20 (vale «cinco»).».
2.  *Dado* `https://empresa.ghe.com/` en el dominio, `historial.ruta` = `src/historial.db` (dentro del repo, fuera de
    `data/`) o una ruta bajo un archivo regular, *cuando* se convierten, *entonces* lanzan los mensajes de «Plan
    técnico», 2; y `empresa.ghe.com`, `data/otro.db` y una ruta absoluta en `tmp_path` son válidos, sin crear carpetas.
3.  *Dado* un subconjunto `{beam_size: "cinco", formato: "srt", best_of: "x"}` y `modelo_ia="Mistral-Large-3"`,
    *cuando* se valida, *entonces* devuelve `formato` convertido y tres errores en el orden de entrada, el del modelo
    con el texto de la regla 7; y `resumen_errores(1)` es «No se guardó nada: corrige 1 valor.» y `resumen_errores(3)`
    «No se guardó nada: corrige 3 valores.».

**Tests** (`tests/test_configuracion.py`): `test_valor_desde_formulario_convierte` (parametrizado),
`test_valor_desde_formulario_rechaza_con_topes_y_no_finitos` (parametrizado),
`test_dominio_enterprise_debe_ser_un_nombre_de_host`, `test_historial_ruta_fuera_del_repo_salvo_data_y_escribible`,
`test_validar_formulario_subconjunto_errores_en_orden_y_regla_7`, `test_resumen_errores_singular_y_plural`.

**Archivos (lista cerrada):** `src/configuracion.py` (`TOPES_PANEL`, `valor_desde_formulario`, `validar_formulario`,
`resumen_errores`), `tests/test_configuracion.py`.

**Verificación:** solo tests.

### Historia A2b — Guardar y restablecer las preferencias en una escritura atómica

**Criterios:**

1.  *Dado* un YAML con `formato` `txt` y `beam_size` 5, y un `preferencias.json` con `{"modelo_ia": "gpt-4.1",
    "configuracion": {"transcripcion": {"best_of": 3, "beam_size": "x"}, "audio": {"a": 1}}}`, *cuando* se guardan
    `formato` `srt` y `beam_size` 5 sin `modelo_ia`, *entonces* el archivo queda `{"modelo_ia": "gpt-4.1",
    "configuracion": {"transcripcion": {"best_of": 3}, "salida": {"formato": "srt"}}}`, el aviso nombra
    `transcripcion.beam_size` y `audio.a`, y no queda `preferencias.json.tmp`; si después se guarda `formato` `txt` y
    `best_of` 5, la clave `configuracion` desaparece.
2.  *Dado* `modelo_ia="claude-sonnet-5.5"` y después el modelo del YAML, *cuando* se guarda, *entonces* el primero se
    escribe junto con `configuracion` en una sola llamada a `os.replace` y el segundo quita `modelo_ia`; y si leer el
    archivo da `OSError` (parcheado), `guardar_ajustes` lo propaga y el archivo no cambia, mientras que con JSON
    inválido lo reemplaza.
3.  *Dado* un `preferencias.json` con `modelo_ia`, `configuracion` y otra clave `x`, *cuando* se restablece, *entonces*
    queda `{"x": …}`; y `guardar_modelo_preferido` conserva las demás claves y no reescribe el archivo si su lectura da
    `OSError`.

**Tests** (`tests/test_configuracion.py`): `test_guardar_ajustes_solo_diferencias_y_descarta_lo_que_no_sirve`,
`test_guardar_ajustes_quita_configuracion_vacia`, `test_guardar_ajustes_con_modelo_en_una_sola_escritura` (cuenta las
llamadas a `os.replace`), `test_guardar_el_modelo_del_yaml_quita_modelo_ia`,
`test_fallo_de_lectura_no_borra_las_preferencias`, `test_json_invalido_se_reemplaza_al_guardar`,
`test_restablecer_borra_ajustes_y_modelo_y_conserva_lo_demas`,
`test_guardar_modelo_preferido_no_reescribe_si_no_puede_leer`. Los tests existentes de `guardar_modelo_preferido`
siguen pasando.

**Archivos (lista cerrada):** `src/configuracion.py` (`guardar_ajustes`, `restablecer_ajustes`, `_leer_para_escribir`,
`_escribir_preferencias`; `guardar_modelo_preferido` las usa), `tests/test_configuracion.py`.

**Verificación:** solo tests.

### Historia A3 — Componer el guardado y los valores laterales sin ventana

**Criterios:**

1.  *Dado* un formulario con un valor inválido, *cuando* se llama a `guardar_formulario`, *entonces* `efectiva` es
    `None`, `mensaje` es `resumen_errores(1)` y `preferencias.json` no existe ni cambia; y si `guardar_ajustes` lanza
    `OSError`, `mensaje` es «No se pudo guardar la configuración: <motivo>.» y `efectiva` es `None`.
2.  *Dado* un formulario válido que cambia `formato` y `historial.ruta`, *cuando* se guarda, *entonces* `efectiva`
    tiene los valores nuevos, `cambiadas` son esas dos claves, `avisos` está vacío (el aviso de un archivo antes
    ilegible desaparece) y `mensaje` es «Configuración guardada · el historial nuevo se abrirá al reiniciar la app».
3.  *Dado* `cambiadas` con `transcripcion.idioma` = `nl`, `salida.formato` y `transcripcion.beam_size`, *cuando* se
    piden los valores laterales, *entonces* son `var_idioma` «nl», `opciones_idioma` con «nl» al final y `var_formato`,
    y nada para `beam_size`; con `idioma` `es`, `var_idioma` es «Español». `from src.ui import codigo_de_idioma` sigue
    funcionando.

**Tests** (`tests/test_configuracion.py`): `test_guardar_formulario_con_errores_no_escribe`,
`test_guardar_formulario_con_fallo_de_escritura_no_devuelve_efectiva`,
`test_guardar_formulario_devuelve_cambiadas_avisos_y_mensaje`, `test_claves_cambiadas_solo_las_de_la_tabla`,
`test_valores_laterales_solo_de_las_claves_cambiadas`. `tests/test_importaciones.py`: añadir `src.idiomas` a `MODULOS`
y a `SIN_TK`.

**Archivos (lista cerrada):** `src/idiomas.py` (crear), `src/ui.py` (importa los tres nombres de `src.idiomas` y usa
`nombre_de_idioma` en `__init__`), `src/configuracion.py` (`claves_cambiadas`, `REQUIEREN_REINICIO`,
`ResultadoGuardado`, `guardar_formulario`, `valores_laterales`), `tests/test_configuracion.py`,
`tests/test_importaciones.py`.

**Verificación:** solo tests; el selector de idioma de la ventana sigue igual.

### Historia C0 — El hilo de la transcripción deja de leer la configuración

**Criterios:**

1.  *Dado* `AppTranscriptor._procesar_transcripcion`, *cuando* se inspecciona su código, *entonces* no contiene
    `self.configuracion` y su firma es `(self, opciones, parametros)`.
2.  *Dado* `_iniciar_transcripcion`, *cuando* se inspecciona, *entonces* captura `self.configuracion["transcripcion"]`
    y lanza el hilo con `args=(opciones, parametros)`.
3.  *Dado* una transcripción real, *cuando* termina, *entonces* el resultado es el mismo que antes (verificación a mano).

**Tests** (`tests/test_ui.py`): `test_el_hilo_de_transcripcion_no_lee_la_configuracion` (con `inspect.getsource` e
`inspect.signature`), `test_los_parametros_se_capturan_en_el_hilo_principal`.

**Archivos (lista cerrada):** `src/ui.py` (`_iniciar_transcripcion`, `_procesar_transcripcion`), `tests/test_ui.py`.

**Verificación en la ventana real:** transcribir un audio corto con `tiny`; `grep -n 'self.configuracion' src/ui.py`
no devuelve líneas dentro de `_procesar_transcripcion`.

### Historia C1 — Vista «Configuración» con Transcripción y Salida

**Criterios:**

1.  *Dado* el YAML del proyecto y sin preferencias, *cuando* se abre «⚙ Configuración» (o `Ctrl+3`), se elige `srt` y
    se pulsa «Guardar», *entonces* `preferencias.json` queda con `salida.formato` `srt`, el YAML no cambia, el selector
    de formato del lateral muestra `srt`, el lateral conserva el modelo de Whisper elegido antes a mano, y el pie dice
    «Configuración guardada».
2.  *Dado* `nl` escrito en «Idioma», *cuando* se guarda, *entonces* el selector de idioma del lateral ofrece y muestra
    `nl`; y si se cambia un campo, se va a Transcribir y se vuelve sin guardar, el campo vuelve al valor guardado.
3.  *Dado* una transcripción en curso, *cuando* se pulsa «Guardar», *entonces* aparece «Espera a que termine el proceso
    en curso.» y nada cambia.

**Tests:** `tests/test_ui.py::test_campos_de_transcripcion_y_salida` (`CAMPOS` contiene exactamente las siete claves
de C1, todas con `avanzado=False`), `tests/test_ui.py::test_motivo_para_no_guardar_durante_un_proceso`,
`tests/test_importaciones.py` (añadir `src.ui_configuracion` a `MODULOS`, antes de `src.ui`; no va en `SIN_TK`).

**Archivos (lista cerrada):** `src/ui_configuracion.py` (crear: `Campo`, `CAMPOS` de C1, `motivo_para_no_guardar` con
los dos primeros parámetros, `PanelConfiguracion` con `refrescar` y `_guardar`), `src/ui.py` (`VISTA_CONFIGURACION`,
`self.panel_configuracion`, `self.nav`, `mostrar_vista`, `<Control-Key-3>`, `guardar_configuracion`,
`aplicar_guardado` sin las partes de C2 y D1), `tests/test_ui.py`, `tests/test_importaciones.py`.

**Verificación en la ventana real:** CUJ 1; `Ctrl+1`, `Ctrl+2` y `Ctrl+3` alternan las tres vistas; `git status` sin
`config/settings.yaml`; guion de «sin red ni token al abrir» (ver «Verificación común»).

### Historia C2 — Avanzado de Transcripción, Historial y Restablecer

**Criterios:**

1.  *Dado* «cinco» en «Haz de búsqueda» y «0,5» en «Umbral de silencio», *cuando* se pulsa «Guardar», *entonces* se
    cumple el CUJ 2; con «3», `preferencias.json` guarda `beam_size` 3.
2.  *Dado* `historial.ruta` cambiado a `data/otro.db` y guardado, *cuando* se mira el pie y la vista Historial,
    *entonces* el pie dice «Configuración guardada · el historial nuevo se abrirá al reiniciar la app» y el historial
    sigue siendo el de antes; tras reiniciar, la ventana usa `data/otro.db`.
3.  *Dado* preferencias con `formato` `srt` y `modelo_ia`, *cuando* se pulsa «Restablecer valores del proyecto» y se
    confirma, *entonces* `preferencias.json` queda sin `configuracion` ni `modelo_ia`, los campos, el lateral y el
    selector de modelo de IA muestran los del YAML, el asistente se olvida, y si la escritura falla no se aplica nada y
    aparece el diálogo «Configuración».

**Tests:** `tests/test_ui.py::test_campos_avanzados_e_historial` (`CAMPOS` cubre las 15 claves fuera de `ia`; las siete
de decodificación con `avanzado=True`; `historial.ruta` con su nota), `tests/test_configuracion.py::test_restablecer_formulario_devuelve_el_yaml_y_sin_modelo`,
`tests/test_configuracion.py::test_restablecer_formulario_con_fallo_no_devuelve_efectiva`.

**Archivos (lista cerrada):** `src/ui_configuracion.py` (campos de C2, «Avanzado» plegado, `_restablecer`, recuadro de
avisos), `src/ui.py` (`restablecer_configuracion`, `aplicar_guardado` con `_modelo_preferido`, `var_modelo_ia`,
etiquetas de IA y `olvidar_asistente` si cambió el modelo), `src/configuracion.py` (`restablecer_formulario`),
`tests/test_ui.py`, `tests/test_configuracion.py`.

**Verificación en la ventana real:** CUJ 2 y CUJ 5; Restablecer con y sin `modelo_ia`; carpeta de preferencias sin
permiso de escritura → diálogo y nada aplicado.

### Historia D1 — IA: dominio, fidelidad y ajuste fino

**Criterios:**

1.  *Dado* `ia.temperatura` 0.2, *cuando* se piden `argumentos_asistente` antes y después de guardar 0.5, *entonces*
    difieren solo en `temperatura`; con un cambio de `salida.formato`, son iguales (el asistente no se olvida); y
    `copilot_enterprise_url` vacío da `enterprise_url` `None`.
2.  *Dado* «↻» lanzado con la época 0 y un cambio de dominio guardado (época 1), *cuando* llega la lista de modelos,
    *entonces* se descarta: el selector no cambia, «↻» vuelve a estar habilitado y Registro lo anota.
3.  *Dado* `ia.copilot_enterprise_url` cambiado a `empresa.ghe.com`, *cuando* se guarda, *entonces* el selector de
    modelo vuelve a ofrecer solo `auto` y el configurado, y el asistente siguiente usa ese dominio.

**Tests:** `tests/test_flujo_documentos.py::test_argumentos_asistente_salen_de_la_configuracion`,
`tests/test_flujo_documentos.py::test_argumentos_asistente_solo_cambian_con_la_ia`,
`tests/test_ui.py::test_lista_de_modelos_de_otra_epoca_se_descarta` (llama a `AppTranscriptor._mostrar_modelos_ia`
sin enlazar con un `SimpleNamespace` que tiene `_epoca_ia=1`, `combo_modelo_ia` y `btn_cargar_modelos_ia` simulados y
`_log`; comprueba que `combo_modelo_ia.configure(values=…)` no se llama y que `btn_cargar_modelos_ia` vuelve a
`normal`), `tests/test_ui.py::test_campos_de_ia_sin_modelo` (`CAMPOS` cubre las cinco claves `ia.*` salvo `ia.modelo`).

**Archivos (lista cerrada):** `src/flujo_documentos.py` (`argumentos_asistente`), `src/ui.py` (`_crear_asistente`,
`_epoca_ia`, `_consultando_modelos`, `_cargar_modelos_ia`, `_mostrar_modelos_ia`, `_fallo_cargar_modelos_ia`,
`_sin_sesion_para_modelos`, `aplicar_guardado` con la parte IA), `src/ui_configuracion.py` (campos de D1),
`tests/test_flujo_documentos.py`, `tests/test_ui.py`.

**Verificación en la ventana real:** cambiar `revision_fidelidad` y generar muestra «Revisando fidelidad…»; pulsar
«↻» y, antes de que responda, guardar un dominio nuevo: la lista no se pinta; `grep -n "AsistenteIA(" src/ui.py`
devuelve solo la línea de `_crear_asistente`.

### Historia D2 — IA: el modelo en el panel

**Criterios:**

1.  *Dado* una lista cargada con «↻», *cuando* se elige otro modelo en el panel y se guarda, *entonces* `modelo_ia` y
    `configuracion` se escriben en una sola escritura, el selector lateral muestra el nuevo, `_al_cambiar_modelo_ia` no
    se llamó y el asistente se olvida.
2.  *Dado* `ia.modelo` o `modelo_ia` con `Mistral-Large-3`, *cuando* se abre la vista, *entonces* el campo muestra
    «El modelo configurado «Mistral-Large-3» es de la familia «mistral», que no está autorizada por la empresa: no se
    enviará. Elige otro.», el modelo no está entre las opciones, y Guardar sin cambiarlo lo rechaza con el error de la
    regla 7 bajo el campo.
3.  *Dado* «↻» en curso o el diálogo de login abierto, *cuando* se pulsa «Guardar», *entonces* aparece «Espera a que
    termine la consulta de modelos de IA.» o «Termina o cancela el inicio de sesión en GitHub Copilot.» y nada cambia.

**Tests:** `tests/test_ui.py::test_aviso_modelo_solo_para_familias_excluidas`,
`tests/test_ui.py::test_motivo_para_no_guardar_con_consulta_o_login`,
`tests/test_configuracion.py::test_guardar_formulario_con_modelo_cambia_cambiadas_y_modelo_preferido`,
`tests/test_ui.py::test_campos_cubren_las_21_claves`.

**Archivos (lista cerrada):** `src/ui_configuracion.py` (campo `ia.modelo`, `aviso_modelo`, `motivo_para_no_guardar`
con los dos parámetros nuevos), `src/ui.py` (`_login_abierto` en `_iniciar_sesion_copilot`, `guardar_configuracion`
con los cuatro motivos, `_mostrar_modelos_ia` actualiza el menú del panel), `tests/test_ui.py`,
`tests/test_configuracion.py`.

**Verificación en la ventana real:** con una sesión real, «↻» del panel carga la misma lista que el lateral; elegir y
guardar cambia el lateral; con `ia.modelo: "Mistral-Large-3"` en un YAML de prueba (`git stash` después), el aviso sale
y no hay petición al generar.

### Historia B — Saber de dónde sale la sesión, sin red (después de la 16)

**Criterios:**

1.  *Dado* cada combinación (nada; solo opencode; archivo propio y opencode; variable y archivo propio; archivo propio
    corrupto), *cuando* se pide `estado_sesion`, *entonces* el origen es `None`, `opencode`, `app`, `variable`, `None`,
    y `hay_token_propio` es falso, falso, verdadero, verdadero, falso, sin ninguna petición de red y sin crear ni
    cambiar archivos.
2.  *Dado* cada fila de la tabla de «Plan técnico», 7, *cuando* se describe, *entonces* `texto`, `puede_iniciar`,
    `texto_iniciar` y `puede_cerrar` son los de la tabla.
3.  *Dado* una `Sesion` y un `EstadoSesion` con el token `gho_secreto`, *cuando* se piden `repr(sesion)`,
    `repr(estado)` y todos los textos, *entonces* ninguno contiene `gho_secreto`.

**Tests** (`tests/test_copilot.py`, con `rutas_aisladas`): `test_estado_sesion_segun_el_origen_sin_red_ni_escritura`
(parametrizado), `test_describir_sesion_texto_y_botones` (parametrizado, siete filas),
`test_el_token_no_aparece_en_repr_ni_en_los_textos`.

**Archivos (lista cerrada):** `src/copilot.py` (`Sesion.token` con `repr=False`, `ORIGEN_*`, `EstadoSesion`,
`estado_sesion`, `DescripcionSesion`, `describir_sesion`), `tests/test_copilot.py`.

**Verificación:** solo tests.

### Historia E1 — Cerrar solo la sesión propia (después de B)

**Criterios:**

1.  *Dado* un archivo propio y una sesión de opencode, *cuando* se llama a `cerrar_sesion_propia`, *entonces* el propio
    desaparece, el de opencode queda igual byte a byte y el estado devuelto es `opencode` sin token propio.
2.  *Dado* la variable de entorno y un archivo propio, *cuando* se cierra, *entonces* el estado devuelto es `variable`
    sin token propio y la variable sigue definida.
3.  *Dado* que borrar el archivo da `OSError` (parcheado), *cuando* se cierra, *entonces* el `OSError` se propaga y el
    archivo sigue.

**Tests** (`tests/test_copilot.py`): `test_cerrar_sesion_propia_no_toca_opencode`,
`test_cerrar_sesion_propia_con_la_variable_sigue_en_la_variable`, `test_cerrar_sesion_propia_propaga_oserror`.

**Archivos (lista cerrada):** `src/copilot.py` (`cerrar_sesion_propia`), `tests/test_copilot.py`.

**Verificación:** solo tests; `python -m src.main --copilot-logout` sigue igual.

### Historia E2 — Sección Sesión en la vista (Backlog #6; después de E1 y D2)

**Criterios:**

1.  *Dado* la ventana recién abierta, *cuando* se muestra la vista Configuración, *entonces* la sección dice el texto de
    `describir_sesion` para la sesión actual, sin ninguna petición de red; y abrir la ventana sin mostrar la vista no
    leyó el token (guion de «Verificación común»).
2.  *Dado* «No has iniciado sesión», *cuando* se pulsa «Iniciar sesión» y se autoriza, *entonces* se cumple el CUJ 3 y
    `_epoca_ia` aumenta; si se cancela el diálogo, el estado no cambia; con el dominio editado sin guardar, los dos
    botones están deshabilitados con «Guarda primero el dominio».
3.  *Dado* una sesión propia y una de opencode, *cuando* se pulsa «Cerrar sesión» y se confirma, *entonces* se cumple
    el CUJ 4, el selector de modelo vuelve a `auto` y el configurado, el asistente se olvida y Registro anota «Sesión de
    GitHub Copilot cerrada»; durante una generación, los dos botones muestran «Espera a que termine el proceso en
    curso.».

**Tests:** `tests/test_ui.py::test_cerrar_sesion_copilot_olvida_el_asistente_y_avanza_la_epoca` (llama a
`AppTranscriptor._cerrar_sesion_copilot` sin enlazar con un `SimpleNamespace`; `messagebox.askyesno` y
`copilot.cerrar_sesion_propia` parcheados; comprueba `olvidar_asistente`, `_epoca_ia` + 1, `combo_modelo_ia` con
`auto` y el configurado y el estado devuelto), `tests/test_ui.py::test_cerrar_sesion_copilot_con_oserror_no_aplica_nada`.

**Archivos (lista cerrada):** `src/ui_configuracion.py` (sección Sesión, `refrescar_sesion`, control del dominio sin
guardar), `src/ui.py` (`_cerrar_sesion_copilot`; `al_conectar` del panel con época y `olvidar_asistente`),
`tests/test_ui.py`.

**Verificación en la ventana real:** CUJ 3 y CUJ 4 con una cuenta real; con `COPILOT_GITHUB_TOKEN` definida, la sección
lo dice y los botones siguen la tabla; `sha256sum ~/.local/share/opencode/auth.json` igual antes y después;
`python -m src.main --copilot-logout` sigue igual.

### Verificación común

Guion de verificación en la carpeta temporal (no en el repo), con la ventana real: antes de construirla, parchea
`httpx.get`, `httpx.post`, `httpx.stream` y `copilot.leer_token` con funciones que anotan cada llamada; construye
`AppTranscriptor(...)`, procesa eventos un segundo y comprueba que no hubo **ninguna** llamada. Después llama a
`mostrar_vista(VISTA_CONFIGURACION)`: en C1 sigue sin llamadas; desde E2, `leer_token` se llama una vez y `httpx`
ninguna. Se ejecuta tras C1, D2 y E2.

--------------------------------------------------------------------------------

## Alternativas consideradas

### A. Escribir los cambios en `config/settings.yaml`

*   **A favor:** un solo archivo.
*   **En contra:** es el archivo versionado; reescribirlo pierde los comentarios, ensucia `git status` y vuelve a lo que
    el punto #11 quitó (A-19).
*   **Motivo del rechazo:** rechazada por el autor: contradice la decisión del punto #11.

### B. Un YAML del usuario completo (`~/.config/transcriptor-audio/settings.yaml`)

*   **A favor:** el mismo formato que el del proyecto.
*   **En contra:** si guarda todas las claves, congela los valores por defecto y un cambio del YAML del repo ya no
    llega; habría dos archivos de preferencias.
*   **Motivo del rechazo:** rechazada por el autor: guardar solo las diferencias en `preferencias.json` resuelve lo
    mismo con un archivo.

### C. Guardar la configuración efectiva completa en `preferencias.json`

*   **Motivo del rechazo:** rechazada por el autor: el mismo congelamiento que B.

### D. Guardar al salir de cada campo

*   **Motivo del rechazo:** decisión del usuario 6 (2026-11-22): botón «Guardar».

### E. Reabrir el historial en caliente al cambiar `historial.ruta`

*   **A favor:** no hace falta reiniciar.
*   **En contra:** `GestorDocumentos` y `PanelHistorial` guardan la referencia al `Historial`; una generación en curso
    guardaría en la base vieja; la entrada mostrada dejaría de existir en la nueva.
*   **Motivo del rechazo:** rechazada por el autor: riesgo de perder trabajo (regla 6) a cambio de evitar un reinicio.

### F. Comprobar la sesión contra GitHub al mostrar el panel

*   **Motivo del rechazo:** rechazada por el autor: tráfico de red sin acción del usuario; nadie lo pidió.

### G. Cerrar también la sesión de opencode desde el panel

*   **Motivo del rechazo:** rechazada por el autor: la app nunca modifica el archivo de opencode.

### H. Mover la lógica a un módulo nuevo `src/preferencias.py`

*   **En contra:** las funciones nuevas necesitan `_tabla()` y la lectura de preferencias, privadas de
    `configuracion.py`.
*   **Motivo del rechazo:** rechazada por el autor. Sí se crea `src/idiomas.py`, porque los helpers de idioma vivían en
    `src/ui.py` (con Tk) y el panel y `valores_laterales` los necesitan sin Tk.

### I. Rechazar también las acciones de sesión mientras «↻» consulta

*   **A favor:** no haría falta la época.
*   **En contra:** «↻» puede tardar y bloquearía cerrar sesión sin motivo visible; la época también cubre el cambio de
    dominio.
*   **Motivo del rechazo:** rechazada por el autor: la época descarta la respuesta vieja; Guardar sí se rechaza.

--------------------------------------------------------------------------------

## Requisitos no funcionales

*   **Privacidad y secretos.** `preferencias.json` no guarda secretos; `Sesion.token` no sale en `repr`;
    `EstadoSesion` no lleva token. Nada se escribe en el repositorio (regla 8), y `historial.ruta` no puede apuntar
    dentro del repo salvo `data/`.
*   **Red.** Abrir la ventana y mostrar el panel no hacen peticiones; solo «Iniciar sesión» y «↻», como hoy.
*   **Cumplimiento (regla 7).** El campo «Modelo de IA» no admite texto libre, sus opciones pasan por
    `opciones_de_modelo`, `validar_formulario` rechaza un modelo excluido y un modelo efectivo excluido se muestra con
    aviso. La defensa en el envío no cambia.
*   **Hilos (regla 9).** El panel no lanza hilos; las llamadas de fondo (login, «↻») vuelven con `_en_ui`.
    `self.configuracion` se sustituye, no se muta, y el hilo de la transcripción no la lee (C0).
*   **Vuelta atrás.** Cada historia es un commit con la suite en verde. Borrar `preferencias.json` (o «Restablecer»)
    devuelve la app al YAML. Una versión anterior de la app ignora la clave `configuracion`.

### Riesgos

1.  **Dos ventanas abiertas a la vez** escriben el mismo `preferencias.json`; gana la última. Aceptado.
2.  **Editar `preferencias.json` a mano con la ventana abierta**: Guardar relee el archivo y conserva `modelo_ia` y las
    claves válidas que el formulario no muestra, pero las que el formulario sí muestra toman el valor del formulario.
    Aceptado y anotado en la spec.
3.  **Regresión visual que los tests no ven.** Mitigación: la lógica está en funciones puras con tests; cada historia
    con ventana tiene su verificación real y el guion común.
4.  **Divergencia CLI/ventana** (decisión 4). Mitigación: la spec lo dice.
5.  **Conflicto con la historia 16** en `src/copilot.py`. Mitigación: B y E1 van después, en serie.

### Mejoras futuras

*   Indicar en cada campo si su valor viene del YAML o de las preferencias, con un «↺» por campo.
*   Reabrir el historial sin reiniciar cuando no haya ninguna generación en curso.
*   Recordar el tema de la ventana en las mismas preferencias.

### Recursos

*   `BACKLOG.md` (Backlog #5 y #6; Salud del código #10, #11 y #26).
*   `docs/specs/configuracion.md`, `docs/specs/documentos-ia.md`, `docs/specs/cli.md`.
*   `docs/disenos/00-actual.md`, `docs/disenos/05-flujos-fuera-de-la-ventana.md`, `docs/historias/16-limite-de-entrada.md`.
*   `.context/transcriptor-facts.md`.

--------------------------------------------------------------------------------

## Revisión (2026-11-22)

Revisores: arquitectura («aprobar con cambios») e implementation readiness («listo con ajustes»). El usuario eligió la
opción recomendada en las seis decisiones de producto.

| Hallazgo | Cómo quedó |
|---|---|
| Seis decisiones de producto abiertas | «Decisiones tomadas», de producto, con fecha 2026-11-22 |
| Conflicto con la historia 16 en `copilot.py` | B y E1 después de la 16, en serie (cabecera e «Historias») |
| A2 demasiado grande | A2a (convertir y validar, `resumen_errores`) y A2b (guardar y restablecer atómicos) |
| C demasiado grande; carrera del hilo de la transcripción | C0 (parámetros capturados en el hilo principal, test con `inspect`), C1 (vista, `mostrar_vista` para tres vistas con pseudocódigo, `Ctrl+3`, Transcripción y Salida) y C2 (Avanzado, Historial, Restablecer) |
| E mezclaba lógica y vista | E1 (`cerrar_sesion_propia`) y E2 (sección); orden fijo D antes de E2 |
| Más lógica probable sin ventana | `guardar_formulario` → `ResultadoGuardado`, `restablecer_formulario`, `valores_laterales`, `motivo_para_no_guardar`, `aviso_modelo`, `argumentos_asistente`; helpers de idioma en `src/idiomas.py` sin Tk |
| Carrera de «↻» con login, logout y cambio de dominio | `_epoca_ia` capturada y comparada; Guardar rechazado con «↻» en curso o login abierto; botones de sesión deshabilitados con el dominio sin guardar |
| Guardado no atómico; `_al_cambiar_modelo_ia` antes de guardar | Una escritura atómica con `modelo_ia`; estado aplicado solo tras el éxito; sin `_al_cambiar_modelo_ia` |
| Restablecer no olvidaba `_modelo_preferido` ni el asistente | En C2, la misma historia que borra `modelo_ia` |
| Regla 7 en el guardado | `validar_formulario` rechaza modelos excluidos (test); aviso «no se enviará» si el efectivo es excluido |
| Preferencias raras podían romper o borrarse | `configuracion` o secciones que no son objeto → aviso; `math.isfinite`; `OSError` de lectura no borra; `ilegible`; avisos refrescados tras guardar |
| `historial.ruta` sin validar | Fuera del repo salvo `data/` (regla 8) y carpeta escribible o creable |
| Valores absurdos en el panel | `TOPES_PANEL` con valores y mensajes; el YAML no cambia |
| Dominio Enterprise sin validar | Nombre de host sin esquema, barras ni espacios, o vacío |
| Sesión: token propio corrupto, `repr` del token, textos incompletos | `hay_token_propio` solo si es legible y tiene token; `Sesion.token` con `repr=False` y test; tabla de siete textos; `_cerrar_sesion_copilot` con firma y títulos |
| Asistente olvidado de más | Solo si cambian `argumentos_asistente`, y al iniciar o cerrar sesión |
| Literales sueltos | Avisos de A1 completos; `_mensaje_invalido` sin punto; «1 valor» / «N valores»; `Campo`; 15 + 6 = 21; subconjunto y orden en `validar_formulario`; `configuracion` vacía se quita; `refrescar` descarta lo no guardado; valor y opciones del campo «Modelo de IA» |
| Spec: qué pasa si cambia el YAML y con lo inválido al guardar | «Lo que dirá la spec» |
| Tests que pasarían antes de implementar | Quitados o sustituidos: la parte de `leer_modelo_preferido` de A1; `test_cambiar_la_ia_olvida_el_asistente` → `test_argumentos_asistente_solo_cambian_con_la_ia`; `test_opciones_del_panel_nunca_incluyen_familias_excluidas` (duplicaba `test_copilot.py`) → `test_validar_formulario_subconjunto_errores_en_orden_y_regla_7` y `test_aviso_modelo_solo_para_familias_excluidas`; `test_la_ventana_no_calcula_la_sesion_al_construirse` → guion de «Verificación común» |
| Verificación visual sin red | Guion que parchea `httpx.get`, `httpx.post`, `httpx.stream` y `copilot.leer_token` antes de construir la ventana |
| `README.md` sin actualizar | Añadido a lo que actualiza `/cerrar` |
| Motivo de rechazar Guardar durante un proceso | Explicado: estado de los controles, no seguridad de hilos (C0) |

Desviaciones respecto a lo pedido:

*   `guardar_formulario` recibe además `anterior` y `preferido_anterior`, necesarios para calcular `cambiadas`.
*   `claves_cambiadas` y `REQUIEREN_REINICIO` van en una historia nueva, A3 (con `guardar_formulario` y
    `valores_laterales`), y no en C1, para que C1 quede en tres criterios.
*   D se parte en D1 y D2 por tamaño.
*   `math.isfinite` y los topes solo valen en el panel y en las preferencias, no en el YAML, para no cambiar la CLI.
*   Las acciones de sesión no se rechazan mientras «↻» consulta: basta la época (alternativa I).

--------------------------------------------------------------------------------

*Redactado con EGM (Tándem `/diseno`) el 2026-11-22; revisado el 2026-11-22.*
