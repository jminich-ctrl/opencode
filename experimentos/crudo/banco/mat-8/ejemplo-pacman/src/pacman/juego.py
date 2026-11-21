"""Estado de la partida: puntaje, vidas y modo asustado.

Orquesta el `tick` y decide qué pasa cuando Pacman y un fantasma se encuentran.
No imprime nada: `render` se encarga de mostrar lo que acá se decide.
"""

from .laberinto import PODER, PUNTO, VACIO

PUNTOS_POR_PUNTO = 10
PUNTOS_POR_PASTILLA = 50
PUNTOS_PRIMER_FANTASMA = 200
PUNTOS_FRUTA = 100
UMBRAL_FRUTA = 300
TURNOS_FRUTA = 50
TICKS_ASUSTADO = 20
VIDAS_INICIALES = 3


class Juego:
    """Lleva el puntaje y el estado del nivel."""

    def __init__(self, laberinto):
        """Arranca una partida sobre `laberinto`, con el puntaje en cero."""
        self.laberinto = laberinto
        self.puntaje = 0
        self.ultima_pastilla = False
        self.asustado_restante = 0
        self.vidas = VIDAS_INICIALES
        self._comidos_en_este_modo = 0
        self.fruta = None
        self._turnos_fruta = 0
        self._fruta_usada = False
        self.pausado = False

    def comer_en(self, pos: tuple[int, int]) -> str:
        """Come lo que haya en `pos`, suma el puntaje y devuelve qué comió.

        Un punto suma 10 y una pastilla 50; una celda ya comida no suma nada.
        Deja en `ultima_pastilla` si lo comido fue una pastilla, que es lo que
        dispara el modo asustado (T05).
        """
        if self.fruta is not None and pos == self.fruta:
            self.puntaje += PUNTOS_FRUTA
            self.fruta = None
            self.ultima_pastilla = False
            return "fruta"

        comido = self.laberinto.comer(pos)
        if comido == PUNTO:
            self.puntaje += PUNTOS_POR_PUNTO
        elif comido == PODER:
            self.puntaje += PUNTOS_POR_PASTILLA
        self.ultima_pastilla = comido == PODER
        if self.ultima_pastilla:
            self.asustado_restante = TICKS_ASUSTADO
            self._comidos_en_este_modo = 0
        return comido

    def tick(self) -> None:
        """Avanza un turno: descuenta el modo asustado y la vida de la fruta."""
        if self.pausado:
            return
            
        if self.asustado_restante > 0:
            self.asustado_restante -= 1

        if self.fruta is not None:
            self._turnos_fruta -= 1
            if self._turnos_fruta <= 0:
                self.fruta = None
        elif not self._fruta_usada and self.puntaje >= UMBRAL_FRUTA:
            self.fruta = self._donde_poner_la_fruta()
            self._turnos_fruta = TURNOS_FRUTA
            self._fruta_usada = True

    def _donde_poner_la_fruta(self):
        """Primera celda libre y sin punto, recorriendo desde el centro hacia afuera.

        Regla fija en vez de azar: los tests dependen de que sea determinista.
        """
        lab = self.laberinto
        centro = (lab.alto // 2, lab.ancho // 2)
        candidatas = sorted(
            ((f, c) for f in range(lab.alto) for c in range(lab.ancho)),
            key=lambda p: (abs(p[0] - centro[0]) + abs(p[1] - centro[1]), p))
        for pos in candidatas:
            if not lab.es_pared(pos) and lab.contenido(pos) == VACIO:
                return pos
        return None

    @property
    def asustados(self) -> bool:
        """¿Los fantasmas están comestibles en este momento?"""
        return self.asustado_restante > 0

    def colision(self, pos_pacman: tuple[int, int], fantasmas: list,
                 pos_previa_pacman: tuple[int, int] = None, 
                 previas_fantasmas: dict = None) -> str:
        """Resuelve el encuentro con los fantasmas que estén en `pos_pacman`.

        En modo asustado el fantasma vuelve a su inicio y suma 200, 400, 800…
        duplicando por cada fantasma comido dentro del mismo modo. Fuera del
        modo, Pacman pierde una vida. Devuelve "comio", "perdio" o "nada".

        Si se pasan posiciones anteriores, también se cuenta como colisión si
        hay intercambio de posiciones (cruce).
        """
        # Verificar si hay colisión directa (misma celda)
        tocados = [f for f in fantasmas if f.pos == pos_pacman]
        if tocados:
            if not self.asustados:
                self.perder_vida(pos_pacman, fantasmas)
                return "perdio"
            for fantasma in tocados:
                self.puntaje += PUNTOS_PRIMER_FANTASMA * (2 ** self._comidos_en_este_modo)
                self._comidos_en_este_modo += 1
                fantasma.pos = fantasma.inicio
            return "comio"
        
        # Verificar si hay cruce (intercambio de posiciones)
        if pos_previa_pacman is not None and previas_fantasmas is not None:
            for fantasma in fantasmas:
                pos_anterior = previas_fantasmas.get(id(fantasma))
                # Cruce de verdad: el fantasma quedó donde estaba Pacman Y vino de
                # donde Pacman está ahora. Sin la segunda mitad, un fantasma que lo
                # SIGUE por atrás contaba como cruce y le sacaba una vida sin tocarlo.
                if (pos_anterior is not None
                        and fantasma.pos == pos_previa_pacman
                        and pos_anterior == pos_pacman):
                    if not self.asustados:
                        self.perder_vida(pos_pacman, fantasmas)
                        return "perdio"
                    # En modo asustado, el fantasma se come
                    self.puntaje += PUNTOS_PRIMER_FANTASMA * (2 ** self._comidos_en_este_modo)
                    self._comidos_en_este_modo += 1
                    fantasma.pos = fantasma.inicio
                    return "comio"
        
        return "nada"

    def perder_vida(self, pos_pacman, fantasmas) -> None:
        """Descuenta una vida y devuelve a todos a su posición inicial."""
        self.vidas -= 1
        self.asustado_restante = 0
        self._comidos_en_este_modo = 0
        for fantasma in fantasmas:
            fantasma.pos = fantasma.inicio

    def terminado(self) -> bool:
        """¿Terminó la partida, por vidas agotadas o por nivel limpio?"""
        return self.vidas <= 0 or self.nivel_limpio()

    def resultado(self):
        """"ganó", "perdió" o None si la partida sigue."""
        if self.vidas <= 0:
            return "perdió"
        if self.nivel_limpio():
            return "ganó"
        return None

    def alternar_pausa(self) -> None:
        """Alterna el estado de pausa."""
        self.pausado = not self.pausado

    def nivel_limpio(self) -> bool:
        """¿Ya no quedan puntos ni pastillas para comer?"""
        return self.laberinto.puntos_restantes() == 0
