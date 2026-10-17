"""Genera docs/StagePass_UML.drawio (3 páginas) a partir del código fuente real.
La posición de cada clase la calcula Graphviz (dot -Tjson); luego se emite el XML de draw.io,
así que el archivo se abre y se edita en app.diagrams.net / draw.io Desktop.   Uso: python tools/generar_drawio.py"""
import ast
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from generar_uml import (ADAPTADORES_PRIMARIOS, AMARILLO, CELESTE, COMPLETOS, ENUM, GRIS_C, GRIS_M,  # noqa: E402
                         MORADO, SALIDA, leer_clases, nombres_en)

PX_CHAR, FILA, SEP = 6.3, 15, 8


@dataclass
class Nodo:
    id: str
    nombre: str
    estereotipo: str = ""
    attrs: List[str] = field(default_factory=list)
    metodos: List[str] = field(default_factory=list)
    relleno: str = "#FFFFFF"
    texto: str = "#000000"
    punteado: bool = False
    cluster: str = ""
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    cab: int = 28

    def medir(self):
        lineas = [self.nombre, f"«{self.estereotipo}»" if self.estereotipo else ""] + self.attrs + self.metodos
        self.w = max(150, max(len(l) for l in lineas) * PX_CHAR + 24)
        self.cab = 44 if self.estereotipo else 28
        h = self.cab
        if self.attrs:
            h += len(self.attrs) * FILA + 8
        if self.metodos:
            h += (SEP if self.attrs else 0) + len(self.metodos) * FILA + 8
        self.h = max(h, self.cab + 4)
        return self


@dataclass
class Arista:
    tipo: str            # realizacion | dependencia | asociacion | agregacion | enumref | externa
    origen: str
    destino: str
    etiqueta: str = ""


@dataclass
class Grupo:
    id: str
    titulo: str
    color: str


ESTILOS_ARISTA = {
    "realizacion": "endArrow=block;endFill=0;dashed=1;",
    "dependencia": "endArrow=open;endFill=0;dashed=1;dashPattern=1 3;",
    "asociacion": "endArrow=open;endFill=0;",
    "agregacion": "startArrow=diamondThin;startFill=0;endArrow=open;endFill=0;",
    "enumref": "endArrow=open;endFill=0;dashed=1;dashPattern=1 4;strokeColor=#AAAAAA;",
    "externa": "endArrow=open;endFill=0;dashed=1;strokeColor=#666666;",
}


def distribuir(nodos, grupos, dot_aristas):
    """Graphviz solo calcula posiciones. Devuelve el rectángulo (x, y, ancho, alto) de cada grupo."""
    lineas = ['digraph G { rankdir=LR; nodesep=0.45; ranksep=1.3; splines=false; compound=true;',
              'node [shape=box fixedsize=true label=""];']
    for g in grupos:
        lineas.append(f'subgraph cluster_{g.id} {{ label="{g.titulo}"; margin=24;')
        lineas += [f'"{n.id}" [width={n.w / 72:.3f} height={n.h / 72:.3f}];' for n in nodos if n.cluster == g.id]
        lineas.append("}")
    lineas += [f'"{o}" -> "{d}";' for o, d in dot_aristas]
    lineas.append("}")
    salida = subprocess.run(["dot", "-Tjson"], input="\n".join(lineas), capture_output=True, text=True, check=True)
    datos = json.loads(salida.stdout)
    alto = float(datos["bb"].split(",")[3])
    por_id = {n.id: n for n in nodos}
    limites = {}
    for obj in datos["objects"]:
        nombre = obj["name"]
        if nombre.startswith("cluster_"):
            x1, y1, x2, y2 = map(float, obj["bb"].split(","))
            limites[nombre[8:]] = (x1, alto - y2, x2 - x1, y2 - y1)
        elif nombre in por_id:
            n = por_id[nombre]
            cx, cy = map(float, obj["pos"].split(","))
            n.x, n.y = cx - n.w / 2, alto - cy - n.h / 2
    return limites


def xml_clase(n: Nodo, cid: str) -> List[str]:
    cabecera = (f"&laquo;{n.estereotipo}&raquo;<br><b>{escape(n.nombre)}</b>" if n.estereotipo
                else f"<b>{escape(n.nombre)}</b>")
    estilo = ("swimlane;fontStyle=0;align=center;verticalAlign=top;childLayout=stackLayout;horizontal=1;"
              f"startSize={n.cab};horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;"
              f"collapsible=0;marginBottom=0;html=1;fontSize=12;fillColor={n.relleno};fontColor={n.texto};"
              "strokeColor=#333333;swimlaneFillColor=#FFFFFF;" + ("dashed=1;" if n.punteado else ""))
    filas = [f'<mxCell id="{cid}" value={quoteattr(cabecera)} style={quoteattr(estilo)} vertex="1" parent="1">'
             f'<mxGeometry x="{n.x:.0f}" y="{n.y:.0f}" width="{n.w:.0f}" height="{n.h:.0f}" as="geometry"/></mxCell>']
    texto = ("text;strokeColor=none;fillColor=none;align=left;verticalAlign=top;spacingLeft=4;spacingRight=4;"
             "overflow=hidden;rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;whiteSpace=wrap;"
             "html=1;fontSize=11;")
    linea = ("line;strokeWidth=1;fillColor=none;align=left;verticalAlign=middle;spacingTop=-1;spacingLeft=3;"
             "spacingRight=3;rotatable=0;labelPosition=right;points=[];portConstraint=eastwest;strokeColor=inherit;")
    y = n.cab
    if n.attrs:
        alto = len(n.attrs) * FILA + 8
        filas.append(f'<mxCell id="{cid}_a" value={quoteattr("<br>".join(escape(a) for a in n.attrs))} '
                     f'style={quoteattr(texto)} vertex="1" parent="{cid}"><mxGeometry y="{y}" width="{n.w:.0f}" '
                     f'height="{alto}" as="geometry"/></mxCell>')
        y += alto
    if n.metodos:
        if n.attrs:
            filas.append(f'<mxCell id="{cid}_s" value="" style={quoteattr(linea)} vertex="1" parent="{cid}">'
                         f'<mxGeometry y="{y}" width="{n.w:.0f}" height="{SEP}" as="geometry"/></mxCell>')
            y += SEP
        alto = len(n.metodos) * FILA + 8
        filas.append(f'<mxCell id="{cid}_m" value={quoteattr("<br>".join(escape(m) for m in n.metodos))} '
                     f'style={quoteattr(texto)} vertex="1" parent="{cid}"><mxGeometry y="{y}" width="{n.w:.0f}" '
                     f'height="{alto}" as="geometry"/></mxCell>')
    return filas


def pagina(pid, titulo, nodos, aristas, grupos, limites, leyenda, ortogonal):
    celdas = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for g in grupos:
        x, y, w, h = limites[g.id]
        estilo = (f"rounded=1;arcSize=2;whiteSpace=wrap;html=1;fillColor={g.color};strokeColor=#999999;"
                  "verticalAlign=top;fontStyle=1;fontSize=13;opacity=70;")
        celdas.append(f'<mxCell id="g_{g.id}" value={quoteattr(escape(g.titulo))} style={quoteattr(estilo)} '
                      f'vertex="1" parent="1"><mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
                      'as="geometry"/></mxCell>')
    ids = {n.id: f"c_{i}" for i, n in enumerate(nodos)}
    for n in nodos:
        celdas += xml_clase(n, ids[n.id])
    base = "html=1;rounded=0;fontSize=10;" + ("edgeStyle=orthogonalEdgeStyle;" if ortogonal else "")
    for i, a in enumerate(aristas):
        celdas.append(f'<mxCell id="e_{i}" value={quoteattr(escape(a.etiqueta))} '
                      f'style={quoteattr(base + ESTILOS_ARISTA[a.tipo])} edge="1" parent="1" '
                      f'source="{ids[a.origen]}" target="{ids[a.destino]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    minx = min(x for x, _, _, _ in limites.values())
    miny = min(y for _, y, _, _ in limites.values())
    maxy = max(y + h for _, y, _, h in limites.values())
    celdas.append(f'<mxCell id="leyenda" value={quoteattr("<br>".join(leyenda))} style="text;html=1;align=left;'
                  'verticalAlign=top;whiteSpace=wrap;fontSize=11;strokeColor=#999999;fillColor=#FFFFFF;spacing=6;" '
                  f'vertex="1" parent="1"><mxGeometry x="{minx:.0f}" y="{maxy + 30:.0f}" width="560" '
                  f'height="{len(leyenda) * 18 + 16}" as="geometry"/></mxCell>')
    celdas.append(f'<mxCell id="titulo" value={quoteattr("<b>" + escape(titulo) + "</b>")} style="text;html=1;'
                  f'fontSize=18;align=left;verticalAlign=middle;" vertex="1" parent="1"><mxGeometry x="{minx:.0f}" '
                  f'y="{miny - 50:.0f}" width="900" height="30" as="geometry"/></mxCell>')
    return (f'<diagram id="{pid}" name={quoteattr(titulo)}><mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" '
            'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1654" '
            'pageHeight="1169" math="0" shadow="0"><root>' + "".join(celdas) + "</root></mxGraphModel></diagram>")


def cuadro(color, texto):
    return f'<font color="{color}">&#9632;</font> {texto}'


def nodo_de(c, **kw) -> Nodo:
    attrs = [a if c.tipo == "enum" else "+ " + a for a in c.atributos]
    return Nodo(c.nombre, c.nombre, attrs=attrs, metodos=list(c.metodos), **kw)


def d1(cl):
    entidades = ["Evento", "Asiento", "Cliente", "Orden", "Boleto"]
    valores = ["ResultadoTarifa", "SolicitudPago", "ConfirmacionPago", "Factura", "Mensaje",
               "ResultadoValidacion", "ComandoIniciarCompra", "ResultadoCompra"]
    enums = [n for n, c in cl.items() if c.tipo == "enum"]
    grupos = [Grupo("ent", "Entidades del dominio", "#FFFBE6"), Grupo("reg", "Reglas de negocio puras", "#FFFBE6"),
              Grupo("vo", "Objetos de valor y comandos (cruzan los puertos)", "#FFFBE6"),
              Grupo("en", "Enumeraciones", "#FFFBE6")]
    nodos = []
    for lista, g, color in [(entidades, "ent", AMARILLO), (["CalculadoraTarifas"], "reg", AMARILLO),
                            (valores, "vo", "#FFE680"), (enums, "en", ENUM)]:
        for n in lista:
            x = nodo_de(cl[n], relleno=color, cluster=g)
            x.estereotipo = "enumeration" if g == "en" else ""
            nodos.append(x.medir())
    aristas = []
    for n in entidades + valores:
        for atributo, tipo in cl[n].tipos_atributos.items():
            for ref in nombres_en(ast.parse(tipo, mode="eval")):
                if ref in cl and ref != n:
                    if cl[ref].tipo == "enum":
                        aristas.append(Arista("enumref", n, ref))
                    elif (n, ref) == ("Orden", "Asiento"):
                        aristas.append(Arista("agregacion", n, ref, "asientos 1..*"))
                    else:
                        aristas.append(Arista("asociacion", n, ref, atributo))
    aristas += [Arista("dependencia", "CalculadoraTarifas", "ResultadoTarifa", "«create»"),
                Arista("dependencia", "CalculadoraTarifas", "Asiento", "«use»")]
    leyenda = [cuadro(AMARILLO, "Entidad / regla de dominio"), cuadro("#FFE680", "Objeto de valor o comando"),
               cuadro(ENUM, "Enumeración"),
               "◇── agregación (la orden contiene asientos) &nbsp; ──&gt; asociación &nbsp; - - &gt; dependencia",
               "«+» = atributo público. Este diagrama no contiene ninguna clase de infraestructura."]
    return nodos, aristas, grupos, [(a.origen, a.destino) for a in aristas if a.tipo != "enumref"], leyenda


def d2(cl):
    p_in = [n for n, c in cl.items() if c.modulo == "core/ports/entrada" and c.tipo == "interfaz"]
    p_out = [n for n, c in cl.items() if c.modulo == "core/ports/salida" and c.tipo == "interfaz"]
    servicios = [n for n, c in cl.items() if c.tipo == "servicio"]
    grupos = [Grupo("pe", "Puertos primarios (driving)", "#E8FAFB"), Grupo("uc", "Casos de uso", "#F5E8F8"),
              Grupo("ps", "Puertos secundarios (driven)", "#E8FAFB")]
    nodos = []
    for lista, g in [(p_in, "pe"), (p_out, "ps")]:
        for n in lista:
            x = nodo_de(cl[n], relleno=CELESTE, punteado=True, cluster=g)
            x.estereotipo = "interface"
            nodos.append(x.medir())
    for n in servicios:
        nodos.append(Nodo(n, n, "use case", relleno=MORADO, texto="#FFFFFF", cluster="uc").medir())
    nodos.append(Nodo("CalculadoraTarifas", "CalculadoraTarifas", "domain service", relleno=AMARILLO,
                      cluster="uc").medir())
    aristas, dot_aristas = [], []
    for s in servicios:
        for base in cl[s].bases:
            if base in cl:
                aristas.append(Arista("realizacion", s, base))
                dot_aristas.append((base, s))
        for ref in dict.fromkeys(cl[s].tipos_init):
            if ref in p_out:
                aristas.append(Arista("dependencia", s, ref, "«use»"))
                dot_aristas.append((s, ref))
    aristas.append(Arista("dependencia", "ServicioCompra", "CalculadoraTarifas", "«use»"))
    dot_aristas.append(("ServicioCompra", "CalculadoraTarifas"))
    leyenda = [cuadro(CELESTE, "Puerto (interface, borde punteado)"),
               cuadro(MORADO, "Caso de uso (implementa un puerto primario)"), cuadro(AMARILLO, "Servicio de dominio"),
               "- - ▷ realización (implementa) &nbsp; ·····&gt; dependencia («use»)",
               "Todas las dependencias apuntan hacia el núcleo; los puertos solo usan tipos del dominio."]
    return nodos, aristas, grupos, dot_aristas, leyenda


EXTERNOS = {"MySqlEventoRepositorio": "MySQL legacy", "MySqlRecintoRepositorio": "MySQL legacy",
            "MongoOrdenRepositorio": "MongoDB", "MongoBoletoRepositorio": "MongoDB",
            "PayPalSimulado": "PayPal", "WompiSimulado": "Wompi", "PseSimulado": "PSE",
            "HmacCredenciales": "hmac · hashlib · secrets", "SendgridCorreoSimulado": "SendGrid",
            "WhatsAppSimulado": "WhatsApp", "DianSimulado": "DIAN (autoridad tributaria)"}


def d3(cl):
    grupos = [Grupo("ext_in", "Actores externos", "#FFFFFF"), Grupo("ap", "Adaptadores primarios", "#F2F5F8"),
              Grupo("pt", "Puertos del núcleo (frontera del hexágono)", "#E8FAFB"),
              Grupo("as", "Adaptadores secundarios", "#F2F5F8"),
              Grupo("ext", "Tecnología externa (Adaptee)", "#FFFFFF")]
    nodos, aristas, dot_aristas, usados = [], [], [], set()

    def externo(nombre, grupo):
        if not any(n.id == "x_" + nombre for n in nodos):
            nodos.append(Nodo("x_" + nombre, nombre, "external", cluster=grupo).medir())
        return "x_" + nombre

    for n, (_, mets, puertos) in ADAPTADORES_PRIMARIOS.items():
        nodos.append(Nodo(n, n, "primary adapter", metodos=list(mets), relleno=GRIS_C, cluster="ap").medir())
        for p in puertos:
            aristas.append(Arista("dependencia", n, p, "«use»"))
            dot_aristas.append((n, p))
            usados.add(p)
    for ext in (externo("Navegador / App móvil", "ext_in"), externo("Pasarelas (webhook)", "ext_in")):
        aristas.append(Arista("externa", ext, "ApiRestAdapter", "HTTP + JSON"))
        dot_aristas.append((ext, "ApiRestAdapter"))

    def puerto_de(c):
        pend = list(c.bases)
        while pend:
            b = pend.pop(0)
            if b in cl and cl[b].tipo == "interfaz":
                return b
            if b in cl:
                pend += cl[b].bases
        return None

    for n, c in cl.items():
        puerto = puerto_de(c)
        if c.tipo != "adaptador" or n.startswith("_") or puerto is None:
            continue
        completo = n in COMPLETOS
        nodos.append(Nodo(n, n, "secondary adapter · " + ("completo" if completo else "mock"),
                          relleno=GRIS_C if completo else GRIS_M, cluster="as").medir())
        usados.add(puerto)
        aristas.append(Arista("realizacion", n, puerto))
        dot_aristas.append((puerto, n))
        if n in EXTERNOS:
            aristas.append(Arista("externa", n, externo(EXTERNOS[n], "ext"), "traduce"))
            dot_aristas.append((n, "x_" + EXTERNOS[n]))
    for p in sorted(usados):
        x = nodo_de(cl[p], relleno=CELESTE, punteado=True, cluster="pt")
        x.estereotipo, x.attrs = "interface", []
        x.metodos = [m.split("(")[0] + "()" for m in cl[p].metodos]
        nodos.append(x.medir())
    leyenda = [cuadro(GRIS_C, "Adaptador completo (código real)"),
               cuadro(GRIS_M, "Adaptador mock (simulado o en memoria)"), cuadro(CELESTE, "Puerto del núcleo"),
               "──▷ realización &nbsp; ·····&gt; usa un puerto primario &nbsp; - - &gt; traduce desde / hacia la tecnología externa",
               "Ningún adaptador contiene reglas de negocio: solo traduce entre tecnología y dominio.",
               "MySQL probado solo con SQLite; MongoDB probado con mongomock."]
    return nodos, aristas, grupos, dot_aristas, leyenda


def construir():
    cl = leer_clases()
    paginas, previas = [], []
    for pid, titulo, fn, orto in [("p1", "1. Núcleo de dominio", d1, True),
                                  ("p2", "2. Puertos y casos de uso", d2, False),
                                  ("p3", "3. Adaptadores y puertos", d3, False)]:
        nodos, aristas, grupos, dot_aristas, leyenda = fn(cl)
        limites = distribuir(nodos, grupos, dot_aristas)
        paginas.append(pagina(pid, titulo, nodos, aristas, grupos, limites, leyenda, orto))
        previas.append((titulo, nodos, aristas, limites))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="app.diagrams.net" type="device">'
           + "".join(paginas) + "</mxfile>")
    (SALIDA / "StagePass_UML.drawio").write_text(xml, encoding="utf-8")
    return xml, previas


if __name__ == "__main__":
    contenido, _ = construir()
    print("drawio generado:", len(contenido), "bytes")
