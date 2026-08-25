import os
import sys
from collections import defaultdict
from datetime import date

import requests


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

BASE_URL = "https://sandbox.tradier.com/v1"

SCRIPT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CONFIG_FILE = os.path.join(
    SCRIPT_DIR,
    "config.txt",
)

# La defensa únicamente se activa cuando la pérdida
# alcanza este porcentaje del riesgo máximo original.

DEFENSE_TRIGGER_PERCENT = 20.0

# Crédito mínimo aceptable para una defensa.
# 0.10 equivale a $10 por contrato.

MIN_DEFENSE_CREDIT = 0.10

# Máximo de recomendaciones mostradas.

MAX_RECOMMENDATIONS = 2

# Días máximos de diferencia al buscar vencimientos
# alternativos si no existe una defensa adecuada
# para el vencimiento original.

MAX_ALTERNATIVE_DAYS = 10

# Cantidad de vencimientos alternativos consultados.

MAX_ALTERNATIVE_EXPIRATIONS = 4

# Distancia máxima analizada desde el SPX.

STRIKE_RANGE = 400

CONTRACT_MULTIPLIER = 100

REQUEST_TIMEOUT = 30


# ==========================================================
# UTILIDADES
# ==========================================================

def number(value, default=0.0):

    try:

        return float(value)

    except (TypeError, ValueError):

        return default


def integer(value, default=0):

    try:

        return int(float(value))

    except (TypeError, ValueError):

        return default


def dollars(value):

    return f"${value:,.2f}"


def normalized_strike(value):

    return round(float(value), 4)


def read_float(message, minimum=None):

    while True:

        raw = input(message).strip()
        raw = raw.replace(",", "")

        try:

            value = float(raw)

        except ValueError:

            print("Ingresa un número válido.")
            continue

        if minimum is not None and value < minimum:

            print(
                f"El valor debe ser igual "
                f"o superior a {minimum}."
            )

            continue

        return value


def read_integer(message, minimum=1):

    while True:

        raw = input(message).strip()

        try:

            value = int(raw)

        except ValueError:

            print(
                "Ingresa un número entero válido."
            )

            continue

        if value < minimum:

            print(
                f"El valor debe ser igual "
                f"o superior a {minimum}."
            )

            continue

        return value


def option_greek(option, greek_name):

    greeks = option.get("greeks") or {}

    return number(
        greeks.get(greek_name)
    )


def option_midpoint(option):

    bid = number(
        option.get("bid")
    )

    ask = number(
        option.get("ask")
    )

    if bid > 0 and ask > 0:

        return (
            bid + ask
        ) / 2

    last = number(
        option.get("last")
    )

    if last > 0:

        return last

    return max(
        bid,
        ask,
        0.0,
    )


def calculate_days_remaining(expiration):

    try:

        expiration_date = date.fromisoformat(
            expiration
        )

    except ValueError:

        return None

    return max(
        (
            expiration_date
            - date.today()
        ).days,
        0,
    )


# ==========================================================
# TOKEN DE TRADIER
# ==========================================================

def load_token():
    try:
        import streamlit as st

        token = st.secrets.get("TRADIER_TOKEN", "")

        if token:
            return str(token).strip()

    except Exception:
        pass

    raise RuntimeError(
        "No se encontró TRADIER_TOKEN en Streamlit Secrets."
    )

# ==========================================================
# CLIENTE TRADIER
# ==========================================================

class TradierClient:

    def __init__(self, token):

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        self.chain_cache = {}

    def get(self, endpoint, params=None):

        url = f"{BASE_URL}{endpoint}"

        try:

            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

        except requests.exceptions.Timeout:

            raise RuntimeError(
                "Tradier tardó demasiado en responder."
            )

        except requests.exceptions.ConnectionError:

            raise RuntimeError(
                "No se pudo establecer conexión "
                "con Tradier."
            )

        except requests.exceptions.RequestException as error:

            raise RuntimeError(
                f"Error consultando Tradier: {error}"
            )

        if response.status_code == 401:

            raise RuntimeError(
                "Tradier rechazó el token. "
                "Comprueba config.txt."
            )

        if response.status_code == 403:

            raise RuntimeError(
                "La cuenta no tiene autorización "
                "para consultar estos datos."
            )

        if response.status_code == 429:

            raise RuntimeError(
                "Se alcanzó el límite de consultas "
                "de Tradier."
            )

        if not response.ok:

            raise RuntimeError(
                f"Tradier devolvió el error "
                f"{response.status_code}: "
                f"{response.text[:250]}"
            )

        try:

            return response.json()

        except ValueError:

            raise RuntimeError(
                "Tradier devolvió una respuesta "
                "que no se puede interpretar."
            )

    def spx_price(self):

        data = self.get(
            "/markets/quotes",
            params={
                "symbols": "SPX",
            },
        )

        quotes = data.get("quotes") or {}
        quote = quotes.get("quote")

        if isinstance(quote, list):

            quote = (
                quote[0]
                if quote
                else None
            )

        if not quote:

            raise RuntimeError(
                "No se encontró una cotización "
                "para el SPX."
            )

        for field in (
            "last",
            "close",
            "prevclose",
        ):

            value = number(
                quote.get(field)
            )

            if value > 0:

                return value

        bid = number(
            quote.get("bid")
        )

        ask = number(
            quote.get("ask")
        )

        if bid > 0 and ask > 0:

            return (
                bid + ask
            ) / 2

        raise RuntimeError(
            "La cotización del SPX no contiene "
            "un precio utilizable."
        )

    def expirations(self):

        data = self.get(
            "/markets/options/expirations",
            params={
                "symbol": "SPX",
                "includeAllRoots": "true",
                "strikes": "false",
            },
        )

        expirations = (
            data.get("expirations")
            or {}
        )

        available = (
            expirations.get("date")
            or []
        )

        if isinstance(available, str):

            available = [
                available,
            ]

        today = (
            date.today()
            .isoformat()
        )

        available = sorted(
            expiration
            for expiration in available
            if expiration >= today
        )

        if not available:

            raise RuntimeError(
                "No hay vencimientos disponibles "
                "para opciones del SPX."
            )

        return available

    def option_chain(self, expiration):

        if expiration in self.chain_cache:

            return self.chain_cache[
                expiration
            ]

        data = self.get(
            "/markets/options/chains",
            params={
                "symbol": "SPX",
                "expiration": expiration,
                "greeks": "true",
            },
        )

        container = (
            data.get("options")
            or {}
        )

        options = (
            container.get("option")
            or []
        )

        if isinstance(options, dict):

            options = [
                options,
            ]

        if not options:

            raise RuntimeError(
                f"No se encontraron opciones "
                f"para {expiration}."
            )

        self.chain_cache[
            expiration
        ] = options

        return options


# ==========================================================
# OPCIONES Y NIVELES GAMMA
# ==========================================================

def build_option_index(options):

    index = {}

    for option in options:

        option_type = str(
            option.get("option_type")
            or ""
        ).lower()

        if option_type not in (
            "put",
            "call",
        ):

            continue

        strike = option.get(
            "strike"
        )

        if strike is None:

            continue

        try:

            key = (
                option_type,
                normalized_strike(strike),
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        previous = index.get(
            key
        )

        if previous is None:

            index[key] = option
            continue

        previous_oi = integer(
            previous.get(
                "open_interest"
            )
        )

        current_oi = integer(
            option.get(
                "open_interest"
            )
        )

        if current_oi > previous_oi:

            index[key] = option

    return index


def get_option(
    option_index,
    option_type,
    strike,
):

    return option_index.get(
        (
            option_type,
            normalized_strike(strike),
        )
    )


def calculate_gamma_levels(
    options,
    spx,
):

    levels = defaultdict(
        lambda: {
            "call_gex": 0.0,
            "put_gex": 0.0,
        }
    )

    for option in options:

        strike = option.get(
            "strike"
        )

        if strike is None:

            continue

        strike = number(
            strike,
            default=-1,
        )

        if strike < 0:

            continue

        if abs(
            strike - spx
        ) > STRIKE_RANGE:

            continue

        option_type = str(
            option.get("option_type")
            or ""
        ).lower()

        gamma = option_greek(
            option,
            "gamma",
        )

        open_interest = integer(
            option.get(
                "open_interest"
            )
        )

        gex = (
            gamma
            * open_interest
            * CONTRACT_MULTIPLIER
            * (spx ** 2)
            * 0.01
        )

        if option_type == "call":

            levels[strike][
                "call_gex"
            ] += gex

        elif option_type == "put":

            levels[strike][
                "put_gex"
            ] -= gex

    resistances = [
        (
            strike,
            values["call_gex"],
        )
        for strike, values in levels.items()
        if strike > spx
        and values["call_gex"] > 0
    ]

    supports = [
        (
            strike,
            abs(values["put_gex"]),
        )
        for strike, values in levels.items()
        if strike < spx
        and values["put_gex"] < 0
    ]

    resistances.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    supports.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    resistance = (
        resistances[0][0]
        if resistances
        else None
    )

    support = (
        supports[0][0]
        if supports
        else None
    )

    net_gamma = sum(
        values["call_gex"]
        + values["put_gex"]
        for values in levels.values()
    )

    return {
        "support": support,
        "resistance": resistance,
        "net_gamma": net_gamma,
    }


# ==========================================================
# ENTRADA MANUAL DE LA POSICIÓN
# ==========================================================

def select_expiration(
    available_expirations,
):

    print("\nVENCIMIENTOS DISPONIBLES:")

    for expiration in (
        available_expirations[:15]
    ):

        days = calculate_days_remaining(
            expiration
        )

        print(
            f"  {expiration}"
            f"  [{days} DTE]"
        )

    if len(
        available_expirations
    ) > 15:

        print(
            "  ... también puedes ingresar "
            "otro vencimiento disponible."
        )

    default = (
        available_expirations[0]
    )

    while True:

        expiration = input(
            f"\nVencimiento de tu operación "
            f"[Enter = {default}]: "
        ).strip()

        if not expiration:

            return default

        if expiration in (
            available_expirations
        ):

            return expiration

        print(
            "Ese vencimiento no está disponible. "
            "Utiliza el formato AAAA-MM-DD."
        )


def select_strategy():

    while True:

        strategy = input(
            "\nTipo de operación [PCS/CCS]: "
        ).strip().upper()

        if strategy in (
            "PCS",
            "CCS",
        ):

            return strategy

        print(
            "Escribe PCS o CCS."
        )


def enter_position():

    print("\n" + "=" * 58)
    print("DATOS DE TU OPERACIÓN EN ROBINHOOD")
    print("=" * 58)

    strategy = select_strategy()

    short_strike = read_float(
        "Strike vendido: ",
        minimum=0.01,
    )

    long_strike = read_float(
        "Strike comprado: ",
        minimum=0.01,
    )

    if (
        strategy == "PCS"
        and long_strike >= short_strike
    ):

        raise RuntimeError(
            "En un PCS, el strike comprado "
            "debe ser inferior al vendido."
        )

    if (
        strategy == "CCS"
        and long_strike <= short_strike
    ):

        raise RuntimeError(
            "En un CCS, el strike comprado "
            "debe ser superior al vendido."
        )

    credit = read_float(
        "Crédito recibido por spread "
        "[ejemplo: 1.50]: ",
        minimum=0.01,
    )

    contracts = read_integer(
        "Cantidad de contratos: ",
        minimum=1,
    )

    width = abs(
        short_strike
        - long_strike
    )

    if credit >= width:

        raise RuntimeError(
            "El crédito no puede ser igual "
            "o superior al ancho del spread."
        )

    option_type = (
        "put"
        if strategy == "PCS"
        else "call"
    )

    return {
        "strategy": strategy,
        "option_type": option_type,
        "short_strike": short_strike,
        "long_strike": long_strike,
        "credit": credit,
        "contracts": contracts,
        "width": width,
    }


# ==========================================================
# ANÁLISIS DE LA OPERACIÓN
# ==========================================================

def analyze_position(
    position,
    option_index,
    spx,
):

    short_option = get_option(
        option_index,
        position["option_type"],
        position["short_strike"],
    )

    long_option = get_option(
        option_index,
        position["option_type"],
        position["long_strike"],
    )

    if short_option is None:

        raise RuntimeError(
            "No se encontró el strike vendido "
            "para el vencimiento seleccionado."
        )

    if long_option is None:

        raise RuntimeError(
            "No se encontró el strike comprado "
            "para el vencimiento seleccionado."
        )

    short_midpoint = (
        option_midpoint(
            short_option
        )
    )

    long_midpoint = (
        option_midpoint(
            long_option
        )
    )

    current_spread_value = max(
        short_midpoint
        - long_midpoint,
        0.0,
    )

    multiplier = (
        position["contracts"]
        * CONTRACT_MULTIPLIER
    )

    current_pnl = (
        position["credit"]
        - current_spread_value
    ) * multiplier

    maximum_loss = (
        position["width"]
        - position["credit"]
    ) * multiplier

    trigger_loss = (
        maximum_loss
        * DEFENSE_TRIGGER_PERCENT
        / 100
    )

    if current_pnl < 0:

        loss_percent = (
            abs(current_pnl)
            / maximum_loss
            * 100
        )

    else:

        loss_percent = 0.0

    short_delta = option_greek(
        short_option,
        "delta",
    )

    short_gamma = option_greek(
        short_option,
        "gamma",
    )

    net_delta = (
        option_greek(
            long_option,
            "delta",
        )
        - short_delta
    ) * multiplier

    net_gamma = (
        option_greek(
            long_option,
            "gamma",
        )
        - short_gamma
    ) * multiplier

    if position["strategy"] == "PCS":

        distance = (
            spx
            - position["short_strike"]
        )

    else:

        distance = (
            position["short_strike"]
            - spx
        )

    return {
        "short_option": short_option,
        "long_option": long_option,
        "current_spread_value": current_spread_value,
        "pnl": current_pnl,
        "max_loss": maximum_loss,
        "trigger_loss": trigger_loss,
        "loss_percent": loss_percent,
        "short_delta": short_delta,
        "short_gamma": short_gamma,
        "net_delta": net_delta,
        "net_gamma": net_gamma,
        "distance": distance,
    }


def show_position_summary(
    position,
    analysis,
    expiration,
    spx,
    gamma_levels,
):

    days = (
        calculate_days_remaining(
            expiration
        )
    )

    print("\n" + "=" * 58)
    print("SPX DEFENDER")
    print("=" * 58)

    print(
        f"\nOperación: "
        f"{position['strategy']} "
        f"{position['short_strike']:.0f}/"
        f"{position['long_strike']:.0f}"
    )

    print(
        f"Vencimiento: "
        f"{expiration} "
        f"[{days} DTE]"
    )

    print(
        f"SPX actual: "
        f"{spx:,.2f}"
    )

    print(
        f"Contratos: "
        f"{position['contracts']}"
    )

    print(
        f"Resultado estimado: "
        f"{dollars(analysis['pnl'])}"
    )

    print(
        f"Riesgo máximo inicial: "
        f"{dollars(analysis['max_loss'])}"
    )

    print(
        f"Defensa a partir de: "
        f"-{dollars(analysis['trigger_loss'])}"
        f" [{DEFENSE_TRIGGER_PERCENT:.0f}%]"
    )

    print(
        f"Pérdida actual sobre riesgo máximo: "
        f"{analysis['loss_percent']:.1f}%"
    )

    print(
        f"Delta del strike vendido: "
        f"{analysis['short_delta']:+.3f}"
    )

    if (
        gamma_levels["support"]
        is not None
    ):

        print(
            f"Soporte gamma: "
            f"{gamma_levels['support']:.0f}"
        )

    if (
        gamma_levels["resistance"]
        is not None
    ):

        print(
            f"Resistencia gamma: "
            f"{gamma_levels['resistance']:.0f}"
        )


# ==========================================================
# CANDIDATOS DE DEFENSA
# ==========================================================

def available_strikes(
    option_index,
    option_type,
):

    return sorted(
        {
            strike
            for current_type, strike
            in option_index
            if current_type == option_type
        }
    )


def defense_credit(
    short_option,
    long_option,
):

    short_bid = number(
        short_option.get(
            "bid"
        )
    )

    long_ask = number(
        long_option.get(
            "ask"
        )
    )

    if short_bid <= 0:

        return 0.0

    if long_ask <= 0:

        return 0.0

    return max(
        short_bid
        - long_ask,
        0.0,
    )


def defense_net_delta(
    short_option,
    long_option,
    contracts,
):

    return (
        option_greek(
            long_option,
            "delta",
        )
        - option_greek(
            short_option,
            "delta",
        )
    ) * (
        contracts
        * CONTRACT_MULTIPLIER
    )


def build_defenses(
    position,
    analysis,
    option_index,
    expiration,
    original_expiration,
    spx,
    gamma_levels,
):

    if position["strategy"] == "PCS":

        defense_type = "call"
        defense_name = "CCS"

        reference = (
            gamma_levels["resistance"]
        )

    else:

        defense_type = "put"
        defense_name = "PCS"

        reference = (
            gamma_levels["support"]
        )

    if reference is None:

        reference = spx

    strikes = (
        available_strikes(
            option_index,
            defense_type,
        )
    )

    strikes.sort(
        key=lambda strike: (
            abs(
                strike - reference
            ),
            abs(
                strike - spx
            ),
        )
    )

    candidates = []

    for short_strike in strikes:

        if (
            abs(
                short_strike
                - spx
            )
            > STRIKE_RANGE
        ):

            continue

        if defense_type == "call":

            if short_strike <= spx:

                continue

            if (
                short_strike
                <= position["short_strike"]
            ):

                continue

            long_strike = (
                short_strike
                + position["width"]
            )

        else:

            if short_strike >= spx:

                continue

            if (
                short_strike
                >= position["short_strike"]
            ):

                continue

            long_strike = (
                short_strike
                - position["width"]
            )

        short_option = get_option(
            option_index,
            defense_type,
            short_strike,
        )

        long_option = get_option(
            option_index,
            defense_type,
            long_strike,
        )

        if (
            short_option is None
            or long_option is None
        ):

            continue

        credit = defense_credit(
            short_option,
            long_option,
        )

        if credit < (
            MIN_DEFENSE_CREDIT
        ):

            continue

        if credit >= (
            position["width"]
        ):

            continue

        short_delta = option_greek(
            short_option,
            "delta",
        )

        absolute_delta = abs(
            short_delta
        )

        # Evitamos strikes extremadamente cercanos
        # o demasiado alejados.

        if (
            absolute_delta < 0.05
            or absolute_delta > 0.35
        ):

            continue

        added_delta = (
            defense_net_delta(
                short_option,
                long_option,
                position["contracts"],
            )
        )

        combined_delta = (
            analysis["net_delta"]
            + added_delta
        )

        contracts_multiplier = (
            position["contracts"]
            * CONTRACT_MULTIPLIER
        )

        total_credit = (
            credit
            * contracts_multiplier
        )

        same_expiration = (
            expiration
            == original_expiration
        )

        if same_expiration:

            maximum_combined_loss = max(
                position["width"]
                - position["credit"]
                - credit,
                0,
            ) * contracts_multiplier

            risk_reduction = (
                analysis["max_loss"]
                - maximum_combined_loss
            )

            potential_cumulative_loss = None

        else:

            defense_maximum_loss = (
                position["width"]
                - credit
            ) * contracts_multiplier

            potential_cumulative_loss = (
                analysis["max_loss"]
                + defense_maximum_loss
            )

            maximum_combined_loss = None
            risk_reduction = None

        open_interest = integer(
            short_option.get(
                "open_interest"
            )
        )

        candidates.append(
            {
                "strategy": defense_name,
                "expiration": expiration,
                "same_expiration": same_expiration,
                "short_strike": short_strike,
                "long_strike": long_strike,
                "credit": credit,
                "total_credit": total_credit,
                "delta": short_delta,
                "combined_delta": combined_delta,
                "open_interest": open_interest,
                "distance": abs(
                    short_strike
                    - spx
                ),
                "maximum_combined_loss": (
                    maximum_combined_loss
                ),
                "risk_reduction": (
                    risk_reduction
                ),
                "potential_cumulative_loss": (
                    potential_cumulative_loss
                ),
            }
        )

    candidates.sort(
        key=lambda candidate: (

            abs(
                candidate["combined_delta"]
            ),

            -candidate["total_credit"],

            -candidate["open_interest"],
        )
    )

    return candidates


def nearby_expirations(
    available_expirations,
    original_expiration,
):

    original = date.fromisoformat(
        original_expiration
    )

    candidates = []

    for expiration in (
        available_expirations
    ):

        if expiration == (
            original_expiration
        ):

            continue

        expiration_date = (
            date.fromisoformat(
                expiration
            )
        )

        difference = abs(
            (
                expiration_date
                - original
            ).days
        )

        if difference > (
            MAX_ALTERNATIVE_DAYS
        ):

            continue

        candidates.append(
            (
                difference,
                expiration,
            )
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return [

        expiration

        for _, expiration in candidates[
            :MAX_ALTERNATIVE_EXPIRATIONS
        ]
    ]


def find_defenses(
    client,
    position,
    analysis,
    original_index,
    original_expiration,
    available_expirations,
    spx,
    gamma_levels,
):

    same_expiration_defenses = (
        build_defenses(
            position,
            analysis,
            original_index,
            original_expiration,
            original_expiration,
            spx,
            gamma_levels,
        )
    )

    if same_expiration_defenses:

        return (
            same_expiration_defenses,
            False,
        )

    print(
        "\nNo se encontró una defensa adecuada "
        "para el mismo vencimiento."
    )

    print(
        "Buscando fechas cercanas..."
    )

    alternatives = []

    for expiration in (
        nearby_expirations(
            available_expirations,
            original_expiration,
        )
    ):

        try:

            options = client.option_chain(
                expiration
            )

        except RuntimeError:

            continue

        option_index = (
            build_option_index(
                options
            )
        )

        alternative_gamma_levels = (
            calculate_gamma_levels(
                options,
                spx,
            )
        )

        defenses = build_defenses(
            position,
            analysis,
            option_index,
            expiration,
            original_expiration,
            spx,
            alternative_gamma_levels,
        )

        alternatives.extend(
            defenses[:2]
        )

    alternatives.sort(
        key=lambda candidate: (

            abs(
                candidate["combined_delta"]
            ),

            -candidate["total_credit"],
        )
    )

    return (
        alternatives,
        True,
    )


def show_defenses(
    defenses,
    alternatives_used,
    analysis,
):

    if not defenses:

        print(
            "\nESTADO: NO SE ENCONTRÓ "
            "UNA DEFENSA ADECUADA."
        )

        print(
            "Es preferible revisar nuevamente "
            "más adelante que abrir un spread "
            "sin crédito o liquidez suficientes."
        )

        return

    if alternatives_used:

        print("\n" + "!" * 58)

        print(
            "ATENCIÓN: LAS DEFENSAS ENCONTRADAS "
            "TIENEN UN VENCIMIENTO DIFERENTE."
        )

        print(
            "Una fecha distinta no forma un "
            "iron condor tradicional."
        )

        print(
            "Puede existir riesgo adicional "
            "cuando una posición vence antes "
            "que la otra."
        )

        print("!" * 58)

    for number_id, defense in enumerate(

        defenses[
            :MAX_RECOMMENDATIONS
        ],

        start=1,

    ):

        print("\n" + "-" * 58)

        print(
            f"DEFENSA #{number_id}"
        )

        print("-" * 58)

        print(
            f"Estrategia: "
            f"{defense['strategy']} "
            f"{defense['short_strike']:.0f}/"
            f"{defense['long_strike']:.0f}"
        )

        print(
            f"Vencimiento: "
            f"{defense['expiration']}"
        )

        print(
            f"Crédito adicional: "
            f"{dollars(defense['total_credit'])}"
        )

        print(
            f"Delta del strike vendido: "
            f"{defense['delta']:+.3f}"
        )

        print(
            f"Distancia desde SPX: "
            f"{defense['distance']:.1f} puntos"
        )

        if defense[
            "same_expiration"
        ]:

            print(
                f"Riesgo máximo antes: "
                f"{dollars(analysis['max_loss'])}"
            )

            print(
                f"Riesgo máximo después: "
                f"{dollars(defense['maximum_combined_loss'])}"
            )

            print(
                f"Reducción del riesgo máximo: "
                f"{dollars(defense['risk_reduction'])}"
            )

        else:

            print(
                "Riesgo máximo conjunto: "
                "no comparable con un iron condor "
                "del mismo vencimiento."
            )

            print(
                "Pérdida acumulada teórica si ambas "
                "estructuras sufren su pérdida máxima: "
                f"{dollars(defense['potential_cumulative_loss'])}"
            )

    print(
        "\nLas cifras se calculan utilizando "
        "bid/ask y pueden variar durante "
        "la ejecución."
    )

    print(
        "El programa no envía órdenes."
    )


# ==========================================================
# FLUJO PRINCIPAL
# ==========================================================

def main():

    print("\n" + "=" * 58)

    print(
        "SPX DEFENDER - ROBINHOOD PCS / CCS"
    )

    print("=" * 58)

    token = load_token()

    client = TradierClient(
        token
    )

    spx = client.spx_price()

    print(
        f"\nSPX actual: "
        f"{spx:,.2f}"
    )

    available_expirations = (
        client.expirations()
    )

    expiration = select_expiration(
        available_expirations
    )

    position = enter_position()

    print(
        "\nConsultando opciones y calculando "
        "la posición..."
    )

    options = client.option_chain(
        expiration
    )

    option_index = (
        build_option_index(
            options
        )
    )

    gamma_levels = (
        calculate_gamma_levels(
            options,
            spx,
        )
    )

    analysis = analyze_position(
        position,
        option_index,
        spx,
    )

    show_position_summary(
        position,
        analysis,
        expiration,
        spx,
        gamma_levels,
    )

    # Si está en ganancia, no hacemos nada.

    if analysis["pnl"] >= 0:

        print("\n" + "-" * 58)

        print(
            "ESTADO: POSICIÓN EN GANANCIA."
        )

        print(
            "ACCIÓN: NO HACER NADA."
        )

        print("-" * 58)

        return

    # Si está en pérdida, pero todavía no llegó
    # al 20 % del riesgo máximo, no defendemos.

    if (
        analysis["loss_percent"]
        < DEFENSE_TRIGGER_PERCENT
    ):

        print("\n" + "-" * 58)

        print(
            "ESTADO: PÉRDIDA CONTROLADA."
        )

        print(
            "ACCIÓN: NO DEFENDER TODAVÍA."
        )

        print("-" * 58)

        return

    # Cuando la pérdida alcanza o supera el 20 %,
    # buscamos primero defensas del mismo vencimiento.

    print("\n" + "-" * 58)

    print(
        "ESTADO: SE ALCANZÓ EL LÍMITE DE PÉRDIDA."
    )

    print(
        "ACCIÓN: BUSCAR DEFENSA."
    )

    print("-" * 58)

    defenses, alternatives_used = (
        find_defenses(
            client,
            position,
            analysis,
            option_index,
            expiration,
            available_expirations,
            spx,
            gamma_levels,
        )
    )

    show_defenses(
        defenses,
        alternatives_used,
        analysis,
    )


if __name__ == "__main__":

    try:

        main()

    except RuntimeError as error:

        print(
            f"\nERROR: {error}"
        )

        sys.exit(1)

    except KeyboardInterrupt:

        print(
            "\nPrograma cancelado."
        )

        sys.exit(0)
