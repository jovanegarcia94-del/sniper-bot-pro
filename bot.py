import time
import threading
from datetime import datetime
from typing import Callable, Tuple, Optional, List
import argparse

from configobj import ConfigObj
from iqoptionapi.stable_api import IQ_Option

from catalogador import catag


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def load_config(path: str = "config.txt") -> ConfigObj:
    """Carrega o arquivo de configuração para facilitar defaults na UI."""
    return ConfigObj(path)


# -----------------------------------------------------------------------------
# Núcleo do robô
# -----------------------------------------------------------------------------
class BinaryBot:
    """Robô de operações binárias com suporte a controle start/stop e recatalogação."""

    def __init__(
        self,
        email: str,
        senha: str,
        conta: str = "PRACTICE",
        estrategia: str = "MHI",
        valor_entrada: float = 2.0,
        stop_win: float = 100.0,
        stop_loss: float = 50.0,
        analise_medias: bool = False,
        velas_medias: int = 10,
        martingale_levels: int = 0,
        fator_mg: float = 2.2,
        usar_soros: bool = False,
        niveis_soros: int = 0,
        recatalog_minutes: int = 10,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.email = email
        self.senha = senha
        self.conta = conta.upper()
        self.estrategia = estrategia.lower()
        self.valor_entrada = valor_entrada
        self.stop_win = stop_win
        self.stop_loss = stop_loss
        self.analise_medias = analise_medias
        self.velas_medias = velas_medias
        self.martingale_levels = martingale_levels
        self.fator_mg = fator_mg
        self.usar_soros = usar_soros
        self.niveis_soros = niveis_soros
        self.recatalog_seconds = recatalog_minutes * 60

        self.API: Optional[IQ_Option] = None
        self.profile = {}
        self.cifrao = "R$"
        self.nome = ""

        self.lucro_total = 0.0
        self.valor_soros = 0.0
        self.nivel_soros = 0
        self.lucro_op_atual = 0.0
        self.loss_streak = 0

        self.current_pair: Optional[str] = None
        self.last_catalog = 0.0
        self._stop_event = threading.Event()

        # log_fn deve ser rápido; padrão: imprimir
        self.log_fn = log_fn or (lambda msg: print(msg))

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------
    def connect(self) -> Tuple[bool, str]:
        """Abre conexão com a IQ Option e seleciona saldo."""
        # limpa qualquer sessão/SSID pendente no módulo da lib para garantir login com as credenciais atuais
        try:
            from iqoptionapi import global_value

            global_value.SSID = None
        except Exception:
            pass

        self.API = IQ_Option(self.email, self.senha)
        try:
            # limpa cookies/headers anteriores que possam estar em cache na instância interna
            if hasattr(self.API, "api") and hasattr(self.API.api, "session"):
                self.API.api.session.cookies.clear()
        except Exception:
            pass
        try:
            ok, reason = self.API.connect()
        except Exception as e:
            # protege contra ConnectTimeout sem atributos (bug da lib)
            self.log_fn(f"Erro de conexão: {e}")
            return False, str(e)

        if not ok:
            return False, str(reason)

        balance_type = "PRACTICE" if self.conta in ("PRACTICE", "DEMO") else "REAL"
        self.API.change_balance(balance_type)

        self.profile = self.API.get_profile_ansyc()
        self.cifrao = str(self.profile.get("currency_char", "R$"))
        self.nome = self.profile.get("name", "")
        return True, "Conectado"

    # ------------------------------------------------------------------
    def stop(self):
        self._stop_event.set()

    def stopped(self) -> bool:
        return self._stop_event.is_set()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _payout(self, par: str) -> Tuple[float, float, float]:
        profit = self.API.get_all_profit()
        all_asset = self.API.get_all_open_time()

        binary = 0
        turbo = 0
        digital = 0

        try:
            if all_asset["binary"][par]["open"] and profit[par]["binary"] > 0:
                binary = round(profit[par]["binary"], 2) * 100
        except Exception:
            pass

        try:
            if all_asset["turbo"][par]["open"] and profit[par]["turbo"] > 0:
                turbo = round(profit[par]["turbo"], 2) * 100
        except Exception:
            pass

        try:
            if all_asset["digital"][par]["open"]:
                digital = self.API.get_digital_payout(par)
        except Exception:
            pass

        return binary, turbo, digital

    def _tipo_atual(self, ativo: str, tipo_preferido: str) -> str:
        if tipo_preferido != "automatico":
            return tipo_preferido

        binary, turbo, digital = self._payout(ativo)
        if digital >= turbo:
            return "digital"
        return "binary"

    # ------------------------------------------------------------------
    def _compra(self, ativo: str, entrada_inicial: float, direcao: str, exp: int, tipo: str) -> Tuple[str, float]:
        """Abre ordem com martingale e retorna ('WIN'|'LOSS'|'DRAW'|'FAIL', lucro_float)."""
        entrada = entrada_inicial
        ultimo_estado = "FAIL"
        ultimo_valor = 0.0

        for i in range(self.martingale_levels + 1):
            if self.stopped():
                break

            check, order_id = (
                self.API.buy_digital_spot_v2(ativo, entrada, direcao, exp)
                if tipo == "digital"
                else self.API.buy(entrada, ativo, direcao, exp)
            )

            if not check:
                self.log_fn(f"Falha ao abrir ordem {ativo} (gale {i})")
                ultimo_estado = "FAIL"
                break

            while not self.stopped():
                time.sleep(0.2)
                status, resultado = (
                    self.API.check_win_digital_v2(order_id)
                    if tipo == "digital"
                    else self.API.check_win_v4(order_id)
                )
                if status:
                    resultado = round(resultado, 2)
                    self.lucro_total += resultado
                    self.valor_soros += resultado
                    self.lucro_op_atual += resultado

                    if resultado > 0:
                        ultimo_estado = "WIN"
                    elif resultado == 0:
                        ultimo_estado = "DRAW"
                    else:
                        ultimo_estado = "LOSS"
                    ultimo_valor = resultado
                    break

            if ultimo_estado == "WIN":
                break
            if ultimo_estado == "DRAW":
                if i + 1 <= self.martingale_levels:
                    entrada = round(abs(entrada), 2)
                else:
                    break
            if ultimo_estado == "LOSS":
                if i + 1 <= self.martingale_levels:
                    entrada = round(abs(float(entrada) * self.fator_mg), 2)
                else:
                    break

        # Controle de soros
        if self.usar_soros:
            if self.lucro_op_atual > 0 and self.nivel_soros < self.niveis_soros:
                self.nivel_soros += 1
            else:
                self.valor_soros = 0
                self.nivel_soros = 0
            self.lucro_op_atual = 0

        return ultimo_estado, ultimo_valor

    # ------------------------------------------------------------------
    def _medias(self, velas: List[dict]) -> str:
        soma = sum([i["close"] for i in velas])
        media = soma / self.velas_medias
        return "put" if media > velas[-1]["close"] else "call"

    # ------------------------------------------------------------------
    # Estratégias: cada uma realiza UMA entrada e retorna resultado.
    # ------------------------------------------------------------------
    def _estrategia_mhi(self, ativo: str, tipo_preferido: str) -> Tuple[str, float]:
        tipo = self._tipo_atual(ativo, tipo_preferido)
        timeframe = 60
        qnt_velas = 3

        while not self.stopped():
            minutos = float(datetime.fromtimestamp(self.API.get_server_timestamp()).strftime("%M.%S")[1:])
            entrar = (4.59 <= minutos <= 5.0) or minutos >= 9.59
            if not entrar:
                time.sleep(0.25)
                continue

            velas = self.API.get_candles(ativo, timeframe, self.velas_medias if self.analise_medias else qnt_velas, time.time())
            tendencia = self._medias(velas) if self.analise_medias else None

            velas[-1] = "Verde" if velas[-1]["open"] < velas[-1]["close"] else "Vermelha" if velas[-1]["open"] > velas[-1]["close"] else "Doji"
            velas[-2] = "Verde" if velas[-2]["open"] < velas[-2]["close"] else "Vermelha" if velas[-2]["open"] > velas[-2]["close"] else "Doji"
            velas[-3] = "Verde" if velas[-3]["open"] < velas[-3]["close"] else "Vermelha" if velas[-3]["open"] > velas[-3]["close"] else "Doji"

            cores = (velas[-3], velas[-2], velas[-1])
            direcao = None
            if cores.count("Verde") > cores.count("Vermelha") and cores.count("Doji") == 0:
                direcao = "put"
            if cores.count("Verde") < cores.count("Vermelha") and cores.count("Doji") == 0:
                direcao = "call"

            if self.analise_medias and direcao and direcao != tendencia:
                return "SKIP", 0.0

            if direcao in ("put", "call"):
                return self._compra(ativo, self.valor_entrada, direcao, 1, tipo)
            return "SKIP", 0.0

        return "STOP", 0.0

    def _estrategia_torres(self, ativo: str, tipo_preferido: str) -> Tuple[str, float]:
        tipo = self._tipo_atual(ativo, tipo_preferido)
        timeframe = 60
        qnt_velas = 4

        while not self.stopped():
            minutos = float(datetime.fromtimestamp(self.API.get_server_timestamp()).strftime("%M.%S")[1:])
            entrar = (3.59 <= minutos <= 4.0) or (8.59 <= minutos <= 9.0)
            if not entrar:
                time.sleep(0.25)
                continue

            velas = self.API.get_candles(ativo, timeframe, self.velas_medias if self.analise_medias else qnt_velas, time.time())
            tendencia = self._medias(velas) if self.analise_medias else None

            vela_ref = "Verde" if velas[-4]["open"] < velas[-4]["close"] else "Vermelha" if velas[-4]["open"] > velas[-4]["close"] else "Doji"
            cores = (vela_ref,)

            direcao = None
            if cores.count("Verde") > cores.count("Vermelha") and cores.count("Doji") == 0:
                direcao = "call"
            if cores.count("Verde") < cores.count("Vermelha") and cores.count("Doji") == 0:
                direcao = "put"

            if self.analise_medias and direcao and direcao != tendencia:
                return "SKIP", 0.0

            if direcao in ("put", "call"):
                return self._compra(ativo, self.valor_entrada, direcao, 1, tipo)
            return "SKIP", 0.0

        return "STOP", 0.0

    def _estrategia_mhi_m5(self, ativo: str, tipo_preferido: str) -> Tuple[str, float]:
        tipo = self._tipo_atual(ativo, tipo_preferido)
        timeframe = 300
        qnt_velas = 3

        while not self.stopped():
            minutos = float(datetime.fromtimestamp(self.API.get_server_timestamp()).strftime("%M.%S"))
            entrar = (29.59 <= minutos <= 30.0) or minutos == 59.59
            if not entrar:
                time.sleep(0.4)
                continue

            velas = self.API.get_candles(ativo, timeframe, self.velas_medias if self.analise_medias else qnt_velas, time.time())
            tendencia = self._medias(velas) if self.analise_medias else None

            velas[-1] = "Verde" if velas[-1]["open"] < velas[-1]["close"] else "Vermelha" if velas[-1]["open"] > velas[-1]["close"] else "Doji"
            velas[-2] = "Verde" if velas[-2]["open"] < velas[-2]["close"] else "Vermelha" if velas[-2]["open"] > velas[-2]["close"] else "Doji"
            velas[-3] = "Verde" if velas[-3]["open"] < velas[-3]["close"] else "Vermelha" if velas[-3]["open"] > velas[-3]["close"] else "Doji"

            cores = (velas[-3], velas[-2], velas[-1])
            direcao = None
            if cores.count("Verde") > cores.count("Vermelha") and cores.count("Doji") == 0:
                direcao = "put"
            if cores.count("Verde") < cores.count("Vermelha") and cores.count("Doji") == 0:
                direcao = "call"

            if self.analise_medias and direcao and direcao != tendencia:
                return "SKIP", 0.0

            if direcao in ("put", "call"):
                return self._compra(ativo, self.valor_entrada, direcao, 5, tipo)
            return "SKIP", 0.0

        return "STOP", 0.0

    # ------------------------------------------------------------------
    def _executa_estrategia(self, ativo: str, tipo_preferido: str) -> Tuple[str, float]:
        if self.estrategia in ("mhi", "mhi m1", "mhi_m1"):
            return self._estrategia_mhi(ativo, tipo_preferido)
        if self.estrategia in ("torres gemeas", "torres gêmeas", "torres"):
            return self._estrategia_torres(ativo, tipo_preferido)
        if self.estrategia in ("mhi m5", "mhi_m5"):
            return self._estrategia_mhi_m5(ativo, tipo_preferido)
        return "SKIP", 0.0

    # ------------------------------------------------------------------
    def _atualiza_stop(self) -> Optional[str]:
        if self.lucro_total <= -abs(self.stop_loss):
            return "STOP LOSS atingido"
        if self.lucro_total >= abs(self.stop_win):
            return "STOP WIN atingido"
        return None

    # ------------------------------------------------------------------
    def _catalogar(self, tipo_preferido: str) -> Optional[str]:
        lista_catalog, linha = catag(self.API, self.martingale_levels, usar_martingale=self.martingale_levels > 0)
        chave = {
            "mhi": "MHI",
            "mhi m1": "MHI",
            "mhi_m1": "MHI",
            "torres gemeas": "TORRES GÊMEAS",
            "torres gêmeas": "TORRES GÊMEAS",
            "torres": "TORRES GÊMEAS",
            "mhi m5": "MHI M5",
            "mhi_m5": "MHI M5",
        }.get(self.estrategia, "").lower()

        filtrado = [r for r in lista_catalog if r[0].lower() == chave] if chave else lista_catalog
        alvo = filtrado[0] if filtrado else lista_catalog[0]
        if not alvo:
            return None

        self.current_pair = alvo[1]
        assertividade = alvo[linha]
        self.log_fn(f"Melhor par: {self.current_pair} | Estratégia: {alvo[0]} | Assertividade: {assertividade}%")
        return self.current_pair

    # ------------------------------------------------------------------
    def run(self, tipo_preferido: str = "automatico"):
        """Loop principal. Execute em thread separada para não travar UI."""
        if not self.API:
            ok, reason = self.connect()
            if not ok:
                self.log_fn(f"Erro de conexão: {reason}")
                return

        self.log_fn(f"Conectado como {self.nome} | Saldo: {self.cifrao} {self.API.get_balance():.2f}")
        self.last_catalog = 0

        while not self.stopped():
            agora = time.time()
            if (agora - self.last_catalog) >= self.recatalog_seconds or self.loss_streak >= 2 or not self.current_pair:
                self._catalogar(tipo_preferido)
                self.loss_streak = 0
                self.last_catalog = agora

            if not self.current_pair:
                self.log_fn("Nenhum par disponível.")
                time.sleep(2)
                continue

            resultado, valor = self._executa_estrategia(self.current_pair, tipo_preferido)
            if resultado in ("WIN", "LOSS", "DRAW"):
                self.log_fn(f"Resultado {resultado} {self.cifrao}{valor:.2f} | Lucro acumulado {self.cifrao}{self.lucro_total:.2f}")

            if resultado == "LOSS":
                self.loss_streak += 1
            elif resultado == "WIN":
                self.loss_streak = 0

            alerta = self._atualiza_stop()
            if alerta:
                self.log_fn(alerta)
                break

            time.sleep(0.5)

        self.log_fn("Execução finalizada.")


# -----------------------------------------------------------------------------
# Execução em linha de comando (opcional)
# -----------------------------------------------------------------------------
def main_cli():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Robô Binary - CLI")
    parser.add_argument("--conta", default=cfg["AJUSTES"].get("tipo", "digital"))
    parser.add_argument("--estrategia", default="mhi")
    args = parser.parse_args()

    bot = BinaryBot(
        email=cfg["LOGIN"]["email"],
        senha=cfg["LOGIN"]["senha"],
        conta=args.conta,
        estrategia=args.estrategia,
        valor_entrada=float(cfg["AJUSTES"]["valor_entrada"]),
        stop_win=float(cfg["AJUSTES"]["stop_win"]),
        stop_loss=float(cfg["AJUSTES"]["stop_loss"]),
        analise_medias=cfg["AJUSTES"]["analise_medias"].upper() == "S",
        velas_medias=int(cfg["AJUSTES"]["velas_medias"]),
        martingale_levels=int(cfg["MARTINGALE"]["niveis_martingale"]) if cfg["MARTINGALE"]["usar_martingale"].upper() == "S" else 0,
        fator_mg=float(cfg["MARTINGALE"]["fator_martingale"]),
        usar_soros=cfg["SOROS"]["usar_soros"].upper() == "S",
        niveis_soros=int(cfg["SOROS"]["niveis_soros"]),
    )

    bot.run(tipo_preferido=cfg["AJUSTES"].get("tipo", "automatico"))


if __name__ == "__main__":
    import argparse  # import tardio para não pesar em importações na UI

    main_cli()
