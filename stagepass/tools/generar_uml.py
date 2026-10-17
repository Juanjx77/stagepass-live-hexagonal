"""Genera los diagramas de clases UML a partir del código fuente real (módulo ast + Graphviz).
Así el diagrama nunca se desfasa del código.   Uso:  python tools/generar_uml.py"""
import ast
import html
import pathlib
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SRC = RAIZ / "src" / "stagepass"
SALIDA = RAIZ / "docs"

# Paleta de la leyenda vista en clase
AMARILLO, MORADO, CELESTE = "#F9C80E", "#8E24AA", "#21D4D8"
GRIS_C, GRIS_M, ENUM = "#8FA3B8", "#D5DCE4", "#FFF3C4"


@dataclass
class Clase:
    nombre: str
    modulo: str
    bases: List[str]
    tipo: str                      # entidad | enum | interfaz | servicio | adaptador
    atributos: List[str] = field(default_factory=list)
    metodos: List[str] = field(default_factory=list)
    tipos_atributos: Dict[str, str] = field(default_factory=dict)
    tipos_init: List[str] = field(default_factory=list)


def nombres_en(nodo) -> List[str]:
    return [n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)]


def leer_clases() -> Dict[str, Clase]:
    clases = {}
    for ruta in sorted(SRC.rglob("*.py")):
        modulo = ruta.relative_to(SRC).with_suffix("").as_posix()
        for nodo in ast.parse(ruta.read_text(encoding="utf-8")).body:
            if not isinstance(nodo, ast.ClassDef):
                continue
            bases = [ast.unparse(b) for b in nodo.bases]
            c = Clase(nodo.name, modulo, bases, "entidad")
            es_enum = any(b.endswith("Enum") for b in bases)
            for s in nodo.body:
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                    ann = ast.unparse(s.annotation)
                    c.atributos.append(f"{s.target.id}: {ann}")
                    c.tipos_atributos[s.target.id] = ann
                elif es_enum and isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name):
                    c.atributos.append(s.targets[0].id)
                elif isinstance(s, ast.FunctionDef):
                    params = [a for a in s.args.args if a.arg != "self"]
                    if s.name == "__init__":
                        c.tipos_init = [n for a in params if a.annotation for n in nombres_en(a.annotation)]
                        continue
                    if s.name.startswith("_") or "staticmethod" in [ast.unparse(d) for d in s.decorator_list]:
                        continue
                    firma = ", ".join(a.arg + (f": {ast.unparse(a.annotation)}" if a.annotation else "")
                                      for a in params)
                    ret = f" -> {ast.unparse(s.returns)}" if s.returns else ""
                    c.metodos.append(f"+ {s.name}({firma}){ret}")
            if es_enum:
                c.tipo = "enum"
            elif "ABC" in bases:
                c.tipo = "interfaz"
            elif modulo.startswith("core/application"):
                c.tipo = "servicio"
            elif modulo.startswith("adapters"):
                c.tipo = "adaptador"
            clases[c.nombre] = c
    return clases


def tabla(c: Clase, color: str, texto="black", estereotipo="", borde="solid", atributos=True, metodos=True,
          max_len=78) -> str:
    def cortar(s):
        return s if len(s) <= max_len else s[:max_len - 1] + "…"
    filas = [f'<TR><TD BGCOLOR="{color}"><FONT COLOR="{texto}">'
             + (f"<I>&laquo;{estereotipo}&raquo;</I><BR/>" if estereotipo else "")
             + f"<B>{html.escape(c.nombre)}</B></FONT></TD></TR>"]
    if atributos:
        a = "<BR ALIGN=\"LEFT\"/>".join(html.escape("- " + cortar(x)) if c.tipo != "enum" else html.escape(x)
                                          for x in c.atributos) or " "
        filas.append(f'<TR><TD ALIGN="LEFT" BALIGN="LEFT">{a}<BR ALIGN="LEFT"/></TD></TR>')
    if metodos and c.metodos:
        m = "<BR ALIGN=\"LEFT\"/>".join(html.escape(cortar(x)) for x in c.metodos)
        filas.append(f'<TR><TD ALIGN="LEFT" BALIGN="LEFT">{m}<BR ALIGN="LEFT"/></TD></TR>')
    estilo = "dashed" if borde == "dashed" else "solid"
    return (f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" STYLE="{estilo}">'
            + "".join(filas) + "</TABLE>>")


def dot(titulo: str, cuerpo: str, rankdir="LR") -> str:
    return (f'digraph G {{ rankdir={rankdir}; fontname="Arial"; labelloc="t"; fontsize=20; '
            f'label="{titulo}"; nodesep=0.35; ranksep=0.9; splines=true; compound=true;\n'
            'node [shape=plain fontname="Arial" fontsize=10]; edge [fontname="Arial" fontsize=9];\n'
            f"{cuerpo}\n}}")


def cluster(nombre, etiqueta, nodos, color="#EEEEEE"):
    return (f'subgraph cluster_{nombre} {{ label="{etiqueta}"; style="rounded,filled"; '
            f'fillcolor="{color}"; fontsize=13; color="#999999";\n' + "\n".join(nodos) + "\n}\n")


def nodo(c: Clase, **kw):
    return f'{c.nombre} [label={tabla(c, **kw)}];'


def render(nombre, contenido):
    ruta = SALIDA / f"{nombre}.dot"
    ruta.write_text(contenido, encoding="utf-8")
    for fmt in ("png", "svg"):
        extra = ["-Gdpi=130"] if fmt == "png" else []
        subprocess.run(["dot", f"-T{fmt}", *extra, str(ruta), "-o", str(SALIDA / f"{nombre}.{fmt}")], check=True)


def diagrama_dominio(cl):
    entidades = ["Evento", "Asiento", "Cliente", "Orden", "Boleto"]
    reglas = ["CalculadoraTarifas"]
    valores = ["ResultadoTarifa", "SolicitudPago", "ConfirmacionPago", "Factura", "Mensaje",
               "ResultadoValidacion", "ComandoIniciarCompra", "ResultadoCompra"]
    enums = [n for n, c in cl.items() if c.tipo == "enum"]
    cuerpo = cluster("ent", "Entidades del dominio", [nodo(cl[n], color=AMARILLO) for n in entidades], "#FFFBE6")
    cuerpo += cluster("reg", "Reglas de negocio puras", [nodo(cl[n], color=AMARILLO) for n in reglas], "#FFFBE6")
    cuerpo += cluster("vo", "Objetos de valor y comandos (cruzan los puertos)",
                      [nodo(cl[n], color="#FFE680") for n in valores], "#FFFBE6")
    cuerpo += cluster("en", "Enumeraciones", [nodo(cl[n], color=ENUM) for n in enums], "#FFFBE6")
    nombres = set(cl)
    for n in entidades + valores:
        for atributo, tipo in cl[n].tipos_atributos.items():
            for ref in nombres_en(ast.parse(tipo, mode="eval")):
                if ref in nombres and ref != n:
                    if cl[ref].tipo == "enum":
                        cuerpo += f'{n} -> {ref} [style=dotted arrowhead=vee color="#BBBBBB"];\n'
                    else:
                        cabeza = "odiamond" if (n, ref) == ("Orden", "Asiento") else "vee"
                        cuerpo += f'{n} -> {ref} [label="{atributo}" arrowhead={cabeza}];\n'
    cuerpo += 'CalculadoraTarifas -> ResultadoTarifa [style=dashed arrowhead=vee label="crea"];\n'
    cuerpo += 'CalculadoraTarifas -> Asiento [style=dashed arrowhead=vee label="usa"];\n'
    render("uml_1_dominio", dot("Figura 1. Diagrama de clases: núcleo de dominio (Inside)", cuerpo))


def diagrama_nucleo(cl):
    p_entrada = [n for n, c in cl.items() if c.modulo == "core/ports/entrada" and c.tipo == "interfaz"]
    p_salida = [n for n, c in cl.items() if c.modulo == "core/ports/salida" and c.tipo == "interfaz"]
    servicios = [n for n, c in cl.items() if c.tipo == "servicio"]
    cuerpo = cluster("pe", "Puertos primarios (driving)",
                     [nodo(cl[n], color=CELESTE, estereotipo="interface", borde="dashed", atributos=False)
                      for n in p_entrada], "#E8FAFB")
    cuerpo += cluster("uc", "Casos de uso (implementan puertos primarios)",
                      [nodo(cl[n], color=MORADO, texto="white", atributos=False, metodos=False)
                       for n in servicios], "#F5E8F8")
    cuerpo += cluster("ps", "Puertos secundarios (driven)",
                      [nodo(cl[n], color=CELESTE, estereotipo="interface", borde="dashed", atributos=False)
                       for n in p_salida], "#E8FAFB")
    for s in servicios:
        for base in cl[s].bases:
            if base in cl:
                cuerpo += f'{base} -> {s} [dir=back arrowtail=empty style=dashed];\n'
        for ref in dict.fromkeys(cl[s].tipos_init):
            if ref in p_salida:
                cuerpo += f'{s} -> {ref} [arrowhead=vee style=dotted];\n'
    cuerpo += 'ServicioCompra -> CalculadoraTarifas [arrowhead=vee style=dotted];\n'
    cuerpo += 'CalculadoraTarifas [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">' \
              '<TR><TD BGCOLOR="#F9C80E"><B>CalculadoraTarifas</B><BR/>(dominio)</TD></TR></TABLE>>];\n'
    render("uml_2_nucleo_puertos", dot(
        "Figura 2. Puertos primarios, casos de uso y puertos secundarios (la flecha punteada = «usa»)", cuerpo))


ADAPTADORES_PRIMARIOS = {
    "ApiRestAdapter": ("Adaptador primario REST (http.server)", ["+ crear_servidor(app, host, puerto)",
                       "+ GET /api/eventos, /api/eventos/{id}/asientos", "+ POST /api/compras",
                       "+ POST /webhooks/pagos/{pasarela}", "+ GET /api/ordenes/{id}",
                       "+ GET /api/boletos/{codigo}/validacion"],
                       ["ConsultarCatalogoUseCase", "IniciarCompraUseCase", "ConfirmarPagoUseCase",
                        "ConsultarOrdenUseCase", "ValidarBoletoUseCase"]),
    "ProgramadorLiberacion": ("Adaptador primario temporizador", ["+ iniciar()", "+ detener()"],
                              ["LiberarBloqueosExpiradosUseCase"]),
    "PruebasAutomatizadas": ("Test harness (unittest)", ["+ test_tarifas, test_casos_uso", "+ test_rest, "
                             "test_arquitectura"], ["IniciarCompraUseCase", "ConfirmarPagoUseCase",
                             "ValidarBoletoUseCase"]),
}
COMPLETOS = {"HmacCredenciales", "MongoOrdenRepositorio", "MongoBoletoRepositorio",
             "MySqlEventoRepositorio", "MySqlRecintoRepositorio", "RelojSistema", "GeneradorUuid"}


def diagrama_adaptadores(cl):
    cuerpo, usados = "", set()
    prim = []
    for n, (desc, mets, puertos) in ADAPTADORES_PRIMARIOS.items():
        fila = "".join(f'<TR><TD ALIGN="LEFT">{html.escape(m)}</TD></TR>' for m in mets)
        prim.append(f'{n} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">'
                    f'<TR><TD BGCOLOR="{GRIS_C}"><I>&laquo;adaptador primario&raquo;</I><BR/><B>{n}</B><BR/>'
                    f'{html.escape(desc)}</TD></TR>{fila}</TABLE>>];')
        for p in puertos:
            cuerpo += f'{n} -> {p} [arrowhead=vee style=dotted];\n'
            usados.add(p)
    cuerpo = cluster("ap", "Adaptadores primarios (Outside, lado izquierdo)", prim, "#F2F5F8") + cuerpo
    adaptadores = [n for n, c in cl.items() if c.tipo == "adaptador"]
    sec = []
    def puerto_de(c):
        pendientes = list(c.bases)
        while pendientes:
            b = pendientes.pop(0)
            if b in cl and cl[b].tipo == "interfaz":
                return b
            if b in cl:
                pendientes += cl[b].bases
        return None

    for n in adaptadores:
        c = cl[n]
        puerto = puerto_de(c)
        if puerto is None or n.startswith("_"):
            continue
        etiqueta = "completo" if n in COMPLETOS else "mock"
        sec.append(f'{n} [label={tabla(c, color=GRIS_C if n in COMPLETOS else GRIS_M, estereotipo="adaptador secundario - " + etiqueta, atributos=False, metodos=False)}];')
        cuerpo += f'{puerto} -> {n} [dir=back arrowtail=empty];\n'
        usados.add(puerto)
    cuerpo = cluster("as", "Adaptadores secundarios (Outside, lado derecho)", sec, "#F2F5F8") + cuerpo
    puertos = [nodo(cl[n], color=CELESTE, estereotipo="interface", borde="dashed", atributos=False, metodos=False)
               for n in sorted(usados)]
    cuerpo = cluster("pt", "Puertos del núcleo (frontera del hexágono)", puertos, "#E8FAFB") + cuerpo
    render("uml_3_adaptadores", dot(
        "Figura 3. Adaptadores y puertos (flecha vacía = implementa, punteada = usa). Gris oscuro = completo, claro = mock",
        cuerpo))


def mermaid(cl):
    lineas = ["classDiagram", "direction LR"]
    for n, c in cl.items():
        lineas.append(f"class {n} {{")
        if c.tipo == "interfaz":
            lineas.append("  <<interface>>")
        if c.tipo == "enum":
            lineas.append("  <<enumeration>>")
        for a in c.atributos:
            lineas.append("  " + a.replace("[", "~").replace("]", "~").replace(",", ";"))
        for m in c.metodos:
            lineas.append("  " + m.replace("[", "~").replace("]", "~").replace(",", ";"))
        lineas.append("}")
    for n, c in cl.items():
        for b in c.bases:
            if b in cl and cl[b].tipo != "enum":
                lineas.append(f"{b} <|.. {n}")
        for ref in dict.fromkeys(c.tipos_init):
            if ref in cl and cl[ref].tipo == "interfaz":
                lineas.append(f"{n} ..> {ref}")
    (SALIDA / "uml_completo.mmd").write_text("\n".join(lineas), encoding="utf-8")


if __name__ == "__main__":
    clases = leer_clases()
    diagrama_dominio(clases)
    diagrama_nucleo(clases)
    diagrama_adaptadores(clases)
    mermaid(clases)
    print("Clases analizadas:", len(clases))
