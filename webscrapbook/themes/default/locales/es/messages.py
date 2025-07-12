bidi_dir = 'ltr'
html_lang = 'es'

index_title = 'Índice de {path}'

data_table_header_directory = 'Directorio'
data_table_header_name = 'Nombre'
data_table_header_last_modified = 'Última modificación'
data_table_header_size = 'Tamaño'

explorer_tooltip = 'Modo de vista [{}]'
explorer_table = 'Vista de tabla'
explorer_gallery = 'Vista de galería'
explorer_gallery2 = 'Vista de galería (+media)'

tools_tooltip = 'Herramientas [{}]'
tools_preview_on = 'Habilitar vista previa'
tools_preview_off = 'Deshabilitar vista previa'
tools_select_all = 'Seleccionar todo'
tools_deselect_all = 'Deseleccionar todo'
tools_expand_all = 'Expandir todo'
tools_filter = 'Filtrar'
tools_filter_clear = 'Borrar filtro'

tools_filter_prompt = 'Filtrar con la palabra clave (cadena o "/patrón/banderas" para expresiones regulares):'

command_tooltip = 'Comandos [{}]'
command_mkdir = 'Nueva carpeta'
command_mkzip = 'Nuevo zip'
command_mkfile = 'Archivo nuevo'
command_upload = 'Cargar'
command_uploaddir = 'Cargar carpeta'
command_source = 'Ver código fuente'
command_download = 'Descargar'
command_exec = 'Ejecutar de forma nativa'
command_browse = 'Navegar de forma nativa'
command_edit = 'Editar'
command_editx = 'Editar página'
command_move = 'Mover'
command_copy = 'Copiar'
command_link = 'Crear enlace'
command_delete = 'Borrar'

command_mkdir_prompt = 'Crear una nueva carpeta con el nombre:'
command_mkdir_default = 'nueva-carpeta'
command_mkzip_prompt = 'Crear un archivo ZIP con el nombre:'
command_mkzip_default = 'nuevo-archivo.zip'
command_mkfile_prompt = 'Crear un archivo con el nombre:'
command_mkfile_default = 'nuevo-archivo.txt'
command_move_prompt = 'Mover a la ruta o carpeta:'
command_move_prompt_multi = 'Mover a la carpeta:'
command_copy_prompt = 'Copiar a la ruta o carpeta:'
command_copy_prompt_multi = 'Copiar a la carpeta:'
command_link_prompt = 'Crear un enlace en la ruta o dentro de la carpeta:'
command_link_prompt_multi = 'Crear enlaces en la carpeta:'

label_selected = '%count% seleccionado'

previewer_toolbar_title = """\
Atajos de teclado:
• [Esc]: cerrar vista previa.
• [I] o [Espacio]: alterna la barra de información.
• [Entrar]: abrir en una nueva pestaña.
• [RePág] o [Alt+←] o [←]: muestra la entrada anterior.
• [PageDown] o [Alt+→] o [→]: muestra la entrada siguiente.
• [Inicio]: muestra la primera entrada.
• [Fin]: muestra la última entrada.
• [+] o [Alt+↑] o [↑]: acercar.
• [-] o [Alt+↓] o [↓]: alejar.
• [Ctrl+0]: vista de ajuste de zoom.
• [Ctrl+1]: zoom entre el tamaño natural y el último tamaño de zoom.
• [Ctrl+←] o [Shift+←]: mover a la izquierda.
• [Ctrl+→] o [Shift+→]: mover a la derecha.
• [Ctrl+↑] o [Shift+↑]: subir.
• [Ctrl+↓] o [Shift+↓]: mover hacia abajo.
"""
previewer_button_previous = 'Anterior'
previewer_button_next = 'Siguiente'
previewer_button_infobar = 'Alternar barra de información'
previewer_button_close = 'Cerrar vista previa'

edit_title = 'Editar {path}'
edit_error_no_javascript = 'Habilite JavaScript o actualice su navegador para admitir JavaScript, de modo que el editor HTML pueda funcionar.'
edit_warning_encoding = 'Este archivo se decodifica como {encoding} y se codificará como UTF-8 cuando se guarde.'

markdown_title = 'Página {path}'
maff_index_title = 'Paginas de {path}'

button_save = 'GUARDAR'
button_save_tooltip = 'Guardar [{}]'
button_exit = 'SALIR'
button_exit_tooltip = 'Salir [{}]'


#########################################################################
# scrapbook.cache
#########################################################################

# map.html
cache_index_toggle_all = 'Alternar todo'
cache_index_search_link_title = 'Búsqueda'
cache_index_source_link_title = 'Enlace de origen'

# search.html
cache_search_title = '%book% :: Búsqueda'
cache_search_view_in_map = 'Ver en mapa'
cache_search_start = 'ir'
cache_search_help_label = 'Ayuda de sintaxis de búsqueda'
cache_search_help_desc = """\
• By default the input keywords are searched from title, comment, or fulltext.
• Use espacio para separar varias palabras clave. Por ejemplo, “organización w3c” significa elementos que contienen “w3c” y “organización”.
• Use comillas dobles para marcar una frase completa, una comilla doble literal se puede escapar mediante la duplicación. Por ejemplo, “"Tom ""loves"" Mary."” significa elementos que contienen “Tom "loves" Mary.”
• Utilice el signo menos para excluir una palabra clave. Por ejemplo, “-virus” significa elementos sin “virus”.
• Utilice “<comando>:<palabra clave>” para especificar una condición de búsqueda especial. Se puede anteponer un signo menos para exclusión o reversión. Los comandos disponibles incluyen:
  • default: Reset the fields to search for any keyword without a commmand. The fields are separated with “,” and matching any of the fields is considered a hit. For example, “default:id,title,source,comment,content 2020” means items whose ID, title, source URL, comment, or fulltext contains “2020”. “-default:” remove fields from the current default fields, i.e., “default:title,comment -default:comment” works like “default:title”.
  • mc: cada palabra clave subsiguiente coincide con distinción entre mayúsculas y minúsculas. Por ejemplo, “mc: CIA FBI -mc: presidente” significa que los elementos que contienen “CIA” y “FBI” distinguen mayúsculas de minúsculas y “presidente” distingue entre mayúsculas y minúsculas.
  • re: cada palabra clave posterior se trata como una expresión regular. Por ejemplo, “re: \\bcolou?r\\b -re: 1+1=2” significa elementos que coinciden con la expresión regular “\\bcolou?r\\b” y contienen la palabra clave “1+1=2”.
  • id: elemento cuyo ID es igual a la palabra clave (o coincide con la expresión regular). Múltiples valores están conectados “or". Por ejemplo, “id:2020 id:2021” significa elementos de ID “2020” o “2021”; “-id:2020” significa artículos cuyo ID no es “2020”.
  • type: elementos cuyo tipo es igual a la palabra clave (o coincide con la expresión regular). Múltiples valores están conectados “or”. Los tipos disponibles son “” (página), “bookmark”, “file”, “note”, etc. Por ejemplo, “type: type:bookmark” significa elementos cuyo tipo es página o marcador.
  • title: elementos cuyo título contiene la palabra clave.
  • content: elementos cuyo texto completo contiene la palabra clave.
  • comment: elementos cuyo comentario contiene la palabra clave.
  • index: elementos cuya ruta de archivo de índice contiene la palabra clave.
  • source: elementos cuya URL fuente contiene la palabra clave.
  • icon: elementos cuyo icono URL contiene la palabra clave.
  • charset: elementos cuyo juego de caracteres contiene la palabra clave.
  • create: elementos cuyo tiempo de creación coincide con la condición. Múltiples valores están conectados “or”. La condición de tiempo es un intervalo con 0-17 dígitos, seguido de un signo menos opcionalmente, y luego seguido de 0-17 dígitos. Los dos números de 17 dígitos significan el año (4 dígitos), mes (01-12), día (01-31), horas (00-59), minutos (00-59), segundos (00-59) y milisegundos (000-999) en fecha y hora local. Se supone que cada dígito omitido es un "0", excepto que se asume "999..." si se omite totalmente la fecha y hora de finalización. Por ejemplo, “create:2014-2015” significa desde 2014 hasta 2015; “create:-201309” significa antes de septiembre de 2013; y “create:20110825” significa después del 25 de agosto de 2011.
  • modify: elementos cuyo tiempo de modificación coincide con la condición. Múltiples valores están conectados “or”. El formato de hora es el mismo que crear.
  • marked: elementos marcados.
  • locked: elementos bloqueados.
  • location: artículos con información de geolocalización.
  • file: elementos cuyo nombre de archivo contiene la palabra clave.
  • root: elementos bajo el elemento de ID. Múltiples valores están conectados “or”.
  • book: artículos en el álbum de recortes específico (por ID). Múltiples valores están conectados “or”.
  • sort: ordenar los resultados de la búsqueda usando la condición específica, que puede ser id, title, comment, file, content, source, type, create o modify. Por ejemplo, “sort:id -sort:modify” significa ordenar por ID en orden ascendente y luego ordenar por tiempo de modificación en orden descendente.
  • limit: establece un límite en el número de resultados de búsqueda. Por ejemplo, “limit:10” significa mostrar los primeros 10 resultados. “-limit:” significa anular el límite."""
cache_search_result = 'Encontrado %length% resultados:'
cache_search_result_named = '(%name%) Encontrado %length% resultados:'
cache_search_sort_last_created = 'Última creación'
cache_search_sort_last_modified = 'Última modificación'
cache_search_sort_title = 'Ordenar por título'
cache_search_sort_id = 'Ordenar por ID'
cache_search_confirm_remote = 'Cargar la caché completa de texto remoto puede requerir un gran flujo de red. ¿Continuar?'


#########################################################################
# WebScrapBook
#########################################################################

EditorDeleteAnnotationConfirm = '¿Eliminar esta anotación?'
