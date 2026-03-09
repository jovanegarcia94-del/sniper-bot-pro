from iqoptionapi.stable_api import IQ_Option
import time
from datetime import datetime

def catag(API, niveis_mg=0, usar_mg=False):
    pares_abertos = []
    all_asset = API.get_all_open_time()

    # Identifica pares abertos
    for par in all_asset['digital']:
        if all_asset['digital'][par]['open']: pares_abertos.append(par)
    for par in all_asset['turbo']:
        if all_asset['turbo'][par]['open'] and par not in pares_abertos:
            pares_abertos.append(par)

    resultado = []
    
    # Loop único para processar todos os pares
    for par in pares_abertos:
        try:
            # Baixa velas de M1
            velas_m1 = API.get_candles(par, 60, 120, time.time())
            
            # --- LÓGICA MHI ---
            w, g1, g2, l = 0,0,0,0
            for i in range(len(velas_m1)):
                minutos = float(datetime.fromtimestamp(velas_m1[i]['from']).strftime('%M')[1:])
                if (minutos == 5 or minutos == 0) and i >= 3:
                    try:
                        v1 = 'Verde' if velas_m1[i-3]['open'] < velas_m1[i-3]['close'] else 'Vermelha'
                        v2 = 'Verde' if velas_m1[i-2]['open'] < velas_m1[i-2]['close'] else 'Vermelha'
                        v3 = 'Verde' if velas_m1[i-1]['open'] < velas_m1[i-1]['close'] else 'Vermelha'
                        e1 = 'Verde' if velas_m1[i]['open'] < velas_m1[i]['close'] else 'Vermelha'
                        e2 = 'Verde' if velas_m1[i+1]['open'] < velas_m1[i+1]['close'] else 'Vermelha'
                        e3 = 'Verde' if velas_m1[i+2]['open'] < velas_m1[i+2]['close'] else 'Vermelha'
                        direcao = 'Vermelha' if [v1,v2,v3].count('Verde') > [v1,v2,v3].count('Vermelha') else 'Verde'
                        if e1 == direcao: w += 1
                        elif e2 == direcao: g1 += 1
                        elif e3 == direcao: g2 += 1
                        else: l += 1
                    except: pass
            if (w+g1+g2+l) > 0:
                tot = w+g1+g2+l
                resultado.append(['MHI', par, round(w/tot*100,2), round((w+g1)/tot*100,2), round((w+g1+g2)/tot*100,2)])

            # --- LÓGICA TORRES GÊMEAS ---
            w, g1, g2, l = 0,0,0,0
            for i in range(len(velas_m1)):
                minutos = float(datetime.fromtimestamp(velas_m1[i]['from']).strftime('%M')[1:])
                if (minutos == 4 or minutos == 9) and i >= 4:
                    try:
                        v1 = 'Verde' if velas_m1[i-4]['open'] < velas_m1[i-4]['close'] else 'Vermelha'
                        e1 = 'Verde' if velas_m1[i]['open'] < velas_m1[i]['close'] else 'Vermelha'
                        e2 = 'Verde' if velas_m1[i+1]['open'] < velas_m1[i+1]['close'] else 'Vermelha'
                        e3 = 'Verde' if velas_m1[i+2]['open'] < velas_m1[i+2]['close'] else 'Vermelha'
                        if e1 == v1: w += 1
                        elif e2 == v1: g1 += 1
                        elif e3 == v1: g2 += 1
                        else: l += 1
                    except: pass
            if (w+g1+g2+l) > 0:
                tot = w+g1+g2+l
                resultado.append(['Torres Gêmeas', par, round(w/tot*100,2), round((w+g1)/tot*100,2), round((w+g1+g2)/tot*100,2)])

            # --- LÓGICA MHI M5 ---
            velas_m5 = API.get_candles(par, 300, 146, time.time())
            w, g1, g2, l = 0,0,0,0
            for i in range(len(velas_m5)):
                minutos = float(datetime.fromtimestamp(velas_m5[i]['from']).strftime('%M'))
                if (minutos == 30 or minutos == 0) and i >= 3:
                    try:
                        v1 = 'Verde' if velas_m5[i-3]['open'] < velas_m5[i-3]['close'] else 'Vermelha'
                        v2 = 'Verde' if velas_m5[i-2]['open'] < velas_m5[i-2]['close'] else 'Vermelha'
                        v3 = 'Verde' if velas_m5[i-1]['open'] < velas_m5[i-1]['close'] else 'Vermelha'
                        e1 = 'Verde' if velas_m5[i]['open'] < velas_m5[i]['close'] else 'Vermelha'
                        e2 = 'Verde' if velas_m5[i+1]['open'] < velas_m5[i+1]['close'] else 'Vermelha'
                        e3 = 'Verde' if velas_m5[i+2]['open'] < velas_m5[i+2]['close'] else 'Vermelha'
                        direcao = 'Vermelha' if [v1,v2,v3].count('Verde') > [v1,v2,v3].count('Vermelha') else 'Verde'
                        if e1 == direcao: w += 1
                        elif e2 == direcao: g1 += 1
                        elif e3 == direcao: g2 += 1
                        else: l += 1
                    except: pass
            if (w+g1+g2+l) > 0:
                tot = w+g1+g2+l
                resultado.append(['MHI M5', par, round(w/tot*100,2), round((w+g1)/tot*100,2), round((w+g1+g2)/tot*100,2)])

        except: continue

    # Ordena usando níveis de martingale passado pelo app
    linha = 2 if niveis_mg == 0 else 3 if niveis_mg == 1 else 4
    return sorted(resultado, key=lambda x: x[linha], reverse=True), linha
