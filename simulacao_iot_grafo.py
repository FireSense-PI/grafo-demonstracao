import sys
from collections import defaultdict

import matplotlib

try:
    matplotlib.use("QtAgg", force=True)
except ImportError:
    print("[aviso] Qt não encontrado; usando backend padrão. "
          "Se der erro de Tcl/Tk, rode: pip install PyQt6")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

class Grafo:
    def __init__(self):
        self.adj = defaultdict(list)
        self.tipo = {}
        self.pos = {}
        self.rotulo = {}

    def add_no(self, nome, tipo, x, y, rotulo=None):
        self.tipo[nome] = tipo
        self.pos[nome] = (x, y)
        self.rotulo[nome] = rotulo or nome
        self.adj.setdefault(nome, [])

    def add_aresta(self, origem, destino):
        self.adj[origem].append(destino)

    def arestas(self):
        return [(u, v) for u, vizinhos in self.adj.items() for v in vizinhos]

    def dfs(self, inicio, visitados=None):
        if visitados is None:
            visitados = set()
        ordem = []

        def visitar(no):
            visitados.add(no)
            ordem.append(no)
            for vizinho in self.adj[no]:
                if vizinho not in visitados:
                    visitar(vizinho)

        if inicio not in visitados:
            visitar(inicio)
        return ordem


N_BOMBEIROS = 4
SENSORES = [
    ("Temp. corporal", "Temp"),
    ("Pressão O2", "O2"),
    ("Saturação", "SpO2"),
    ("Gases", "Gás"),
]
GAP_ENTRE_BOMBEIROS = 0.6


def construir_arquitetura():
    g = Grafo()
    ns = len(SENSORES)

    topo = N_BOMBEIROS * ns + (N_BOMBEIROS - 1) * GAP_ENTRE_BOMBEIROS - 1
    y_meio = topo / 2

    g.add_no("Mosquitto", "broker", 2, y_meio)
    g.add_no("Servidor", "servidor", 3, y_meio)
    g.add_no("InfluxDB", "banco", 4, y_meio)
    g.add_no("Grafana", "grafana", 5, y_meio)
    g.add_no("Comandante", "pessoa", 6, y_meio + 2.5)
    g.add_no("Paramédico", "pessoa", 6, y_meio - 2.5)

    for b in range(1, N_BOMBEIROS + 1):
        base = (N_BOMBEIROS - b) * (ns + GAP_ENTRE_BOMBEIROS)
        nome_b = f"Bombeiro {b}"
        ys = []
        for i, (nome_s, curto) in enumerate(SENSORES):
            y = base + (ns - 1 - i)
            ys.append(y)
            no_s = f"B{b} {nome_s}"
            g.add_no(no_s, "sensor", 1, y, rotulo=curto)
        g.add_no(nome_b, "bombeiro", 0, sum(ys) / len(ys), rotulo=f"Bombeiro\n{b}")

        for nome_s, _ in SENSORES:
            no_s = f"B{b} {nome_s}"
            g.add_aresta("Mosquitto", no_s)
            g.add_aresta(no_s, nome_b)

    g.add_aresta("Mosquitto", "Servidor")
    g.add_aresta("Servidor", "InfluxDB")
    g.add_aresta("InfluxDB", "Grafana")
    g.add_aresta("Grafana", "Comandante")
    g.add_aresta("Grafana", "Paramédico")
    return g


CORES = {
    "bombeiro": "#f4a261",
    "sensor": "#a8dadc",
    "broker": "#b8e0a8",
    "servidor": "#c7b8ea",
    "banco": "#ffe08a",
    "grafana": "#ffb38a",
    "pessoa": "#d9d9d9",
}
TAMANHO = {
    "bombeiro": 1500,
    "sensor": 800,
    "broker": 2400,
    "servidor": 2400,
    "banco": 2400,
    "grafana": 2400,
    "pessoa": 2600,
}
FONTE = {"bombeiro": 7, "sensor": 6.5, "broker": 7.5, "servidor": 7.5,
         "banco": 7.5, "grafana": 7.5, "pessoa": 7.5}

VERMELHO = "#e63946"
VERMELHO_ESCURO = "#7a0010"
LARANJA_VISITA = "#ff9f1c"


def raio_pt(tipo):
    return (TAMANHO[tipo] ** 0.5) / 2


class Simulacao:
    def __init__(self, grafo):
        self.g = grafo
        self.falhas = []
        self.afetados = set()
        self.animando = False
        self.fig, self.ax = plt.subplots(figsize=(18, 10))
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)

    def desenhar(self, atual=None, ordem=None):
        ax = self.ax
        ax.clear()
        ymax = max(y for _, y in self.g.pos.values())
        ax.set_xlim(-0.6, 6.7)
        ax.set_ylim(-1.6, ymax + 1.6)
        ax.axis("off")


        for u, v in self.g.arestas():
            x1, y1 = self.g.pos[u]
            x2, y2 = self.g.pos[v]
            propagou = u in self.afetados and v in self.afetados
            ax.add_patch(FancyArrowPatch(
                (x1, y1), (x2, y2),
                arrowstyle="-|>", mutation_scale=14,
                shrinkA=raio_pt(self.g.tipo[u]) + 1.5,
                shrinkB=raio_pt(self.g.tipo[v]) + 1.5,
                color=VERMELHO if propagou else "#777777",
                lw=2.2 if propagou else 1.0,
                alpha=1.0 if propagou else 0.6,
                zorder=2 if propagou else 1,
            ))

        for no, (x, y) in self.g.pos.items():
            tipo = self.g.tipo[no]
            if no in self.falhas:
                cor = VERMELHO_ESCURO
            elif no == atual:
                cor = LARANJA_VISITA
            elif no in self.afetados:
                cor = VERMELHO
            else:
                cor = CORES[tipo]
            ax.scatter(x, y, s=TAMANHO[tipo], c=cor, edgecolors="black",
                       linewidths=1.2, zorder=3)
            escuro = no in self.afetados or no in self.falhas
            ax.text(x, y, self.g.rotulo[no], ha="center", va="center",
                    fontsize=FONTE[tipo], fontweight="bold", zorder=4,
                    color="white" if escuro else "black")

        self.fig.canvas.draw_idle()


    def aplicar_falha(self, no, animar=True):
        if no in self.falhas:

            self.falhas.remove(no)
            self.afetados = set()
            for f in self.falhas:
                self.g.dfs(f, self.afetados)
            self.desenhar()
            return

        self.falhas.append(no)
        visitados = set(self.afetados) - {no}
        ordem = self.g.dfs(no, visitados)
        print(f"\nDFS a partir de '{no}' ({len(ordem)} nós):")
        print("  " + " -> ".join(ordem))

        self.animando = True
        parcial = []
        for passo in ordem:
            parcial.append(passo)
            self.afetados.add(passo)
            if animar:
                self.desenhar(atual=passo, ordem=parcial)
                plt.pause(0.35)
        self.animando = False
        self.desenhar(ordem=ordem)

    def on_click(self, event):
        if event.inaxes != self.ax or self.animando:
            return
        melhor, dist_min = None, 1e9
        for no, (x, y) in self.g.pos.items():
            px, py = self.ax.transData.transform((x, y))
            d = ((px - event.x) ** 2 + (py - event.y) ** 2) ** 0.5
            if d < dist_min:
                melhor, dist_min = no, d
        if melhor and dist_min < 30:
            self.aplicar_falha(melhor)

    def on_key(self, event):
        if event.key == "r" and not self.animando:
            self.falhas.clear()
            self.afetados.clear()
            self.desenhar()

    def rodar(self, falhas_iniciais):
        self.desenhar()
        plt.ion()
        plt.show(block=False)
        for f in falhas_iniciais:
            if f in self.g.pos:
                self.aplicar_falha(f)
            else:
                print(f"[aviso] nó '{f}' não existe. Opções: {', '.join(self.g.pos)}")
        plt.ioff()
        plt.show()


if __name__ == "__main__":
    grafo = construir_arquitetura()

    print("=== Lista de adjacência (A -> quem depende de A) ===")
    for no, vizinhos in grafo.adj.items():
        print(f"{no:22s} -> {vizinhos}")

    Simulacao(grafo).rodar(sys.argv[1:])