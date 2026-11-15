"""Single source of truth for datasets, variables, demos, and the guided flow.

Adding a dataset, variable, or guided-flow mapping only requires editing this file.
The module validates itself at import time and raises ``ConfigError`` if anything is
inconsistent, so problems surface before any pipeline work starts.

Note: ``PRECTOTLAND`` is published in the MERRA-2 land collection (``M2TMNXLND``),
not in ``M2TMNXSLV``, so it is registered under its own dataset entry.
"""
from __future__ import annotations

from datetime import date

from modules.errors import ConfigError
from modules.models import (
    BoundingBox,
    DatasetConfig,
    DemoPreset,
    TimeRange,
    VariableMeta,
)

ALPHA: float = 0.05

SIGNIFICANCE_COLORS: dict[str, str] = {
    "increasing": "#2e7d32",  # green
    "decreasing": "#c62828",  # red
    "none": "#757575",  # gray
}

ENVIRONMENTS: dict[str, str] = {
    "water_cycle": "Water and rain",
    "surface": "Land and ocean surface",
    "atmosphere": "Atmosphere",
}

DATASETS: dict[str, DatasetConfig] = {
    "GPM_3IMERGM": DatasetConfig(
        short_name="GPM_3IMERGM",
        version="07",
        provider="GES_DISC",
        title="GPM IMERG Monthly Precipitation",
        description=(
            "Satellite rainfall estimates from the Global Precipitation Measurement "
            "mission, combined into one monthly map of the whole world."
        ),
        period_start="2000-06-01",
        period_end="present",
        variables=("precipitation",),
        group="Grid",
    ),
    "M2TMNXSLV": DatasetConfig(
        short_name="M2TMNXSLV",
        version="5.12.4",
        provider="GES_DISC",
        title="MERRA-2 Monthly Single-Level Diagnostics",
        description=(
            "A NASA weather and climate reanalysis that blends satellite and ground "
            "data with a computer model to give a complete monthly picture of the "
            "atmosphere near the surface."
        ),
        period_start="1980-01-01",
        period_end="present",
        variables=("T2M", "TS", "QV2M", "PS", "SLP", "U10M", "V10M", "TQV"),
    ),
    "M2TMNXLND": DatasetConfig(
        short_name="M2TMNXLND",
        version="5.12.4",
        provider="GES_DISC",
        title="MERRA-2 Monthly Land Surface Diagnostics",
        description=(
            "The land surface part of the MERRA-2 reanalysis, including how much "
            "rain and snow falls on land each month."
        ),
        period_start="1980-01-01",
        period_end="present",
        variables=("PRECTOTLAND", "EVLAND", "GWETTOP", "GWETROOT", "RUNOFF", "LAI"),
    ),
    "M2TMNXFLX": DatasetConfig(
        short_name="M2TMNXFLX",
        version="5.12.4",
        provider="GES_DISC",
        title="MERRA-2 Monthly Surface Flux Diagnostics",
        description=(
            "The MERRA-2 reanalysis view of what moves between the surface and the "
            "air each month, such as evaporation and near-surface wind speed."
        ),
        period_start="1980-01-01",
        period_end="present",
        variables=("EVAP", "SPEED"),
    ),
    "M2TMNXAER": DatasetConfig(
        short_name="M2TMNXAER",
        version="5.12.4",
        provider="GES_DISC",
        title="MERRA-2 Monthly Aerosol Diagnostics",
        description=(
            "MERRA-2 estimates of tiny particles in the air, such as dust, smoke, sea "
            "salt, and pollution, constrained by satellite aerosol observations."
        ),
        period_start="1980-01-01",
        period_end="present",
        variables=("TOTEXTTAU", "DUEXTTAU"),
    ),
    "M2TMNXOCN": DatasetConfig(
        short_name="M2TMNXOCN",
        version="5.12.4",
        provider="GES_DISC",
        title="MERRA-2 Monthly Ocean Surface Diagnostics",
        description=(
            "The ocean surface part of the MERRA-2 reanalysis, including the skin "
            "temperature of open water each month."
        ),
        period_start="1980-01-01",
        period_end="present",
        variables=("TSKINWTR",),
    ),
}

VARIABLES: dict[str, VariableMeta] = {
    "GPM_3IMERGM/precipitation": VariableMeta(
        variable_id="precipitation",
        dataset_key="GPM_3IMERGM",
        long_name="Monthly mean precipitation rate",
        short_description="How much rain and snow falls in an average day of the month.",
        units="mm/day",
        plain_language=(
            "Precipitation is all the water that falls from the sky as rain, snow, or "
            "hail. This number is the average depth of water that lands each day. "
            "If it goes up over many years, the region is getting wetter. If it goes "
            "down, the region is getting drier."
        ),
        category="water_cycle",
        trend_direction_hint="higher means wetter",
        unit_scale=24.0,  # source units are mm/hr
    ),
    "M2TMNXSLV/T2M": VariableMeta(
        variable_id="T2M",
        dataset_key="M2TMNXSLV",
        long_name="2-meter air temperature",
        short_description="The air temperature about two meters above the ground.",
        units="\u00b0C",
        plain_language=(
            "This is the temperature of the air at about head height, like the number "
            "on a weather forecast. Long-term rises show that a place is warming. "
            "Scientists watch it because small shifts can change plants, ice, and "
            "weather."
        ),
        category="atmosphere",
        trend_direction_hint="higher means warmer",
        unit_offset=-273.15,
    ),
    "M2TMNXSLV/TS": VariableMeta(
        variable_id="TS",
        dataset_key="M2TMNXSLV",
        long_name="Surface skin temperature",
        short_description="How warm the ground, water, or ice surface itself is.",
        units="\u00b0C",
        plain_language=(
            "Skin temperature is how hot the very top of the land, ocean, or ice is. "
            "It can differ a lot from the air above it. A rise over time can mean "
            "melting ice, drier soil, or a warming sea surface in that region."
        ),
        category="surface",
        trend_direction_hint="higher means warmer",
        unit_offset=-273.15,
    ),
    "M2TMNXSLV/QV2M": VariableMeta(
        variable_id="QV2M",
        dataset_key="M2TMNXSLV",
        long_name="2-meter specific humidity",
        short_description="How much water vapor is mixed into the air near the ground.",
        units="g/kg",
        plain_language=(
            "Humidity here is the grams of invisible water vapor in each kilogram of "
            "air. Warmer air can hold more vapor, so rising humidity often goes with "
            "warming. Vapor is also a greenhouse gas and fuels clouds and storms."
        ),
        category="atmosphere",
        trend_direction_hint="higher means more humid",
        unit_scale=1000.0,  # source units are kg/kg
    ),
    "M2TMNXSLV/PS": VariableMeta(
        variable_id="PS",
        dataset_key="M2TMNXSLV",
        long_name="Surface pressure",
        short_description="The weight of the air pressing down on the ground.",
        units="hPa",
        plain_language=(
            "Surface pressure is the force of the air above pressing on the ground. "
            "It falls as you go up a mountain. Changes over time can show shifts in "
            "storm tracks and large weather patterns that bring wet or dry spells."
        ),
        category="atmosphere",
        trend_direction_hint="higher means heavier air above",
        unit_scale=0.01,  # source units are Pa
    ),
    "M2TMNXSLV/SLP": VariableMeta(
        variable_id="SLP",
        dataset_key="M2TMNXSLV",
        long_name="Sea-level pressure",
        short_description="Air pressure adjusted as if the place were at sea level.",
        units="hPa",
        plain_language=(
            "Sea-level pressure lets us compare places at different heights fairly. "
            "High pressure usually means calm, clear weather. Low pressure often "
            "brings clouds and storms. Trends can reveal changing weather patterns."
        ),
        category="atmosphere",
        trend_direction_hint="higher means calmer, clearer weather",
        unit_scale=0.01,  # source units are Pa
    ),
    "M2TMNXSLV/U10M": VariableMeta(
        variable_id="U10M",
        dataset_key="M2TMNXSLV",
        long_name="10-meter eastward wind",
        short_description="How fast wind blows toward the east, ten meters up.",
        units="m/s",
        plain_language=(
            "This is the part of the wind that blows from west to east, measured "
            "about ten meters above the ground. Positive numbers mean wind toward the "
            "east. Negative numbers mean wind toward the west. Trends can show "
            "changing weather and ocean patterns."
        ),
        category="atmosphere",
        trend_direction_hint="higher means stronger wind toward the east",
    ),
    "M2TMNXSLV/V10M": VariableMeta(
        variable_id="V10M",
        dataset_key="M2TMNXSLV",
        long_name="10-meter northward wind",
        short_description="How fast wind blows toward the north, ten meters up.",
        units="m/s",
        plain_language=(
            "This is the part of the wind that blows from south to north, measured "
            "about ten meters above the ground. Positive numbers mean wind toward the "
            "north. Negative numbers mean wind toward the south. Trends can show "
            "shifting storm paths."
        ),
        category="atmosphere",
        trend_direction_hint="higher means stronger wind toward the north",
    ),
    "M2TMNXLND/PRECTOTLAND": VariableMeta(
        variable_id="PRECTOTLAND",
        dataset_key="M2TMNXLND",
        long_name="Total precipitation over land",
        short_description="How much rain and snow falls on land in an average day.",
        units="mm/day",
        plain_language=(
            "This is the average depth of rain and snow that falls on land each day, "
            "taken from the MERRA-2 model. It is a good second opinion to compare with "
            "satellite rain estimates. Rising values mean wetter land. Falling values "
            "mean drier land."
        ),
        category="water_cycle",
        trend_direction_hint="higher means wetter",
        unit_scale=86400.0,  # source units are kg m-2 s-1 (= mm/s)
    ),
    "M2TMNXSLV/TQV": VariableMeta(
        variable_id="TQV",
        dataset_key="M2TMNXSLV",
        long_name="Total precipitable water vapor",
        short_description="All the water vapor in a column of air, as a depth of liquid water.",
        units="mm",
        plain_language=(
            "If you squeezed all the invisible water vapor out of the air above one spot "
            "into liquid, this is how deep the puddle would be. Warmer air can hold more "
            "vapor, so a rise often goes with warming and can feed heavier rain."
        ),
        category="atmosphere",
        trend_direction_hint="higher means more moisture in the air",
        # source units are kg m-2, which equals mm of liquid water
    ),
    "M2TMNXLND/EVLAND": VariableMeta(
        variable_id="EVLAND",
        dataset_key="M2TMNXLND",
        long_name="Evaporation from land",
        short_description="How much water rises from soil, plants, and snow into the air each day.",
        units="mm/day",
        plain_language=(
            "Water leaves the land as vapor from wet soil, from plant leaves, and from "
            "snow. This is the average depth lost each day. Rising values can mean a "
            "warmer or wetter surface. Falling values can mean the soil is running dry."
        ),
        category="water_cycle",
        trend_direction_hint="higher means more water returned to the air",
        unit_scale=86400.0,  # source units are kg m-2 s-1 (= mm/s)
    ),
    "M2TMNXLND/GWETTOP": VariableMeta(
        variable_id="GWETTOP",
        dataset_key="M2TMNXLND",
        long_name="Surface soil wetness",
        short_description="How close the top few centimeters of soil are to being fully soaked.",
        units="% saturation",
        plain_language=(
            "This shows how full of water the top layer of soil is, from 0% for bone dry "
            "to 100% for soaked. It reacts quickly to rain and heat. A long-term drop can "
            "be a sign of more frequent drought in that region."
        ),
        category="water_cycle",
        trend_direction_hint="higher means wetter soil",
        unit_scale=100.0,  # source is a 0-1 fraction of saturation
        mask_variable="GWETROOT",  # GWETTOP is 1.0 over ocean instead of missing
    ),
    "M2TMNXLND/GWETROOT": VariableMeta(
        variable_id="GWETROOT",
        dataset_key="M2TMNXLND",
        long_name="Root zone soil wetness",
        short_description="How wet the soil is down where plant roots draw their water.",
        units="% saturation",
        plain_language=(
            "This is how full of water the deeper soil is, where most plant roots live. "
            "It changes more slowly than the surface layer, so it shows lasting wet and "
            "dry periods. A steady decline can mean worsening drought for crops and trees."
        ),
        category="water_cycle",
        trend_direction_hint="higher means wetter soil for roots",
        unit_scale=100.0,  # source is a 0-1 fraction of saturation
    ),
    "M2TMNXLND/RUNOFF": VariableMeta(
        variable_id="RUNOFF",
        dataset_key="M2TMNXLND",
        long_name="Overland runoff",
        short_description="Water that flows off the land surface toward streams and rivers.",
        units="mm/day",
        plain_language=(
            "When rain falls faster than the ground can soak it up, the extra water runs "
            "across the surface toward streams. This is the average depth that runs off "
            "each day. It is a model estimate related to streamflow, not a river gauge."
        ),
        category="water_cycle",
        trend_direction_hint="higher means more water running off the land",
        unit_scale=86400.0,  # source units are kg m-2 s-1 (= mm/s)
    ),
    "M2TMNXLND/LAI": VariableMeta(
        variable_id="LAI",
        dataset_key="M2TMNXLND",
        long_name="Leaf area index",
        short_description="How much leaf area covers each patch of ground.",
        units="m\u00b2/m\u00b2",
        plain_language=(
            "Leaf area index is the total area of leaves above one square meter of "
            "ground. Bare desert is near 0 and thick rainforest can be above 5. Changes "
            "over time can show greening or browning, as simulated by the MERRA-2 model."
        ),
        category="surface",
        trend_direction_hint="higher means more leaves",
    ),
    "M2TMNXFLX/EVAP": VariableMeta(
        variable_id="EVAP",
        dataset_key="M2TMNXFLX",
        long_name="Surface evaporation",
        short_description="How much water evaporates from land and ocean surfaces each day.",
        units="mm/day",
        plain_language=(
            "This is the average depth of water that turns into vapor each day from the "
            "surface below, whether it is ocean, lake, soil, or plants. Over the sea it "
            "is the main source of moisture for rain. Trends show a changing water cycle."
        ),
        category="water_cycle",
        trend_direction_hint="higher means more water evaporating",
        unit_scale=86400.0,  # source units are kg m-2 s-1 (= mm/s)
    ),
    "M2TMNXFLX/SPEED": VariableMeta(
        variable_id="SPEED",
        dataset_key="M2TMNXFLX",
        long_name="Surface wind speed",
        short_description="How fast the wind blows near the surface, in any direction.",
        units="m/s",
        plain_language=(
            "This is the speed of the wind near the ground or sea, no matter which way "
            "it blows. It matters for wind energy, waves, dust storms, and evaporation. "
            "Trends can show if a region is becoming windier or calmer over the years."
        ),
        category="atmosphere",
        trend_direction_hint="higher means windier",
    ),
    "M2TMNXAER/TOTEXTTAU": VariableMeta(
        variable_id="TOTEXTTAU",
        dataset_key="M2TMNXAER",
        long_name="Total aerosol optical depth (550 nm)",
        short_description="How much tiny airborne particles dim sunlight passing through the air.",
        units="unitless",
        plain_language=(
            "Aerosols are tiny particles like dust, smoke, sea salt, and pollution. This "
            "number says how much they block sunlight. Below 0.1 is clean air and above "
            "1 is very hazy. Trends can show cleaner air or more fires, dust, or smog."
        ),
        category="atmosphere",
        trend_direction_hint="higher means hazier air",
    ),
    "M2TMNXAER/DUEXTTAU": VariableMeta(
        variable_id="DUEXTTAU",
        dataset_key="M2TMNXAER",
        long_name="Dust aerosol optical depth (550 nm)",
        short_description="How much windblown desert dust dims sunlight passing through the air.",
        units="unitless",
        plain_language=(
            "This is the part of the haze made by mineral dust lifted from deserts and "
            "dry land. Dust can travel across oceans and affects health, rain, and "
            "sunlight. Trends can reveal changes in drought, wind, or land use upwind."
        ),
        category="atmosphere",
        trend_direction_hint="higher means more dust in the air",
    ),
    "M2TMNXOCN/TSKINWTR": VariableMeta(
        variable_id="TSKINWTR",
        dataset_key="M2TMNXOCN",
        long_name="Open water skin temperature",
        short_description="How warm the very top of the ocean or lake surface is.",
        units="\u00b0C",
        plain_language=(
            "This is the temperature of the thin top layer of open water, as estimated "
            "by MERRA-2. It is closely related to sea surface temperature. Choose a "
            "region over water, since land areas have no value. A rise means warmer seas."
        ),
        category="surface",
        trend_direction_hint="higher means warmer water",
        unit_offset=-273.15,
    ),
}

GUIDED_FLOW: dict[str, list[str]] = {
    "water_cycle": ["GPM_3IMERGM/precipitation", "M2TMNXLND/PRECTOTLAND"],
    "surface": ["M2TMNXSLV/TS"],
    "atmosphere": [
        "M2TMNXSLV/T2M",
        "M2TMNXSLV/QV2M",
        "M2TMNXSLV/PS",
        "M2TMNXSLV/SLP",
        "M2TMNXSLV/U10M",
        "M2TMNXSLV/V10M",
    ],
}

# Named regions (west, south, east, north) offered as quick picks.
PRESET_REGIONS: dict[str, BoundingBox] = {
    "California": BoundingBox(-124.5, 32.5, -114.0, 42.0),
    "Amazon Basin": BoundingBox(-75.0, -10.0, -50.0, 5.0),
    "Sahel": BoundingBox(-18.0, 10.0, 25.0, 17.0),
    "Arctic (north of 66.5\u00b0N)": BoundingBox(-180.0, 66.5, 180.0, 90.0),
    "Tropical Pacific (Ni\u00f1o 3.4)": BoundingBox(-170.0, -5.0, -120.0, 5.0),
    "North Atlantic": BoundingBox(-60.0, 30.0, -20.0, 60.0),
}

DEMO_PRESETS: list[DemoPreset] = [
    DemoPreset(
        name="California rainfall",
        description=(
            "California depends on winter storms for its water. Has the amount of "
            "rain and snow changed since satellites began measuring it in 2000?"
        ),
        dataset_key="GPM_3IMERGM",
        variable_id="precipitation",
        bounds=PRESET_REGIONS["California"],
        time_range=TimeRange("2000-06-01", "2024-12-31"),
        use_anomalies=True,
        expected_insight=(
            "Year-to-year swings between drought and wet years are large, so the "
            "trend may be small or not statistically significant."
        ),
    ),
    DemoPreset(
        name="Arctic warming",
        description=(
            "The Arctic is often said to warm faster than the rest of the planet. "
            "Does 45 years of air temperature data agree?"
        ),
        dataset_key="M2TMNXSLV",
        variable_id="T2M",
        bounds=PRESET_REGIONS["Arctic (north of 66.5\u00b0N)"],
        time_range=TimeRange("1980-01-01", "2024-12-31"),
        use_anomalies=True,
        expected_insight=(
            "Expect a clear and statistically significant warming trend, faster than "
            "the global average."
        ),
    ),
    DemoPreset(
        name="Amazon rain patterns",
        description=(
            "The Amazon rainforest makes much of its own rain. Is the rain it "
            "receives changing over time?"
        ),
        dataset_key="GPM_3IMERGM",
        variable_id="precipitation",
        bounds=PRESET_REGIONS["Amazon Basin"],
        time_range=TimeRange("2000-06-01", "2024-12-31"),
        use_anomalies=True,
        expected_insight=(
            "Rainfall changes here are subtle and vary across the basin, so the "
            "trend may not reach statistical significance."
        ),
    ),
]


# --------------------------------------------------------------------------- helpers
def resolve_period_end(period_end: str, today: date | None = None) -> date:
    """Turn a dataset ``period_end`` (ISO date or ``"present"``) into a date."""
    if period_end == "present":
        return today or date.today()
    return date.fromisoformat(period_end)


def dataset_period(dataset_key: str, today: date | None = None) -> tuple[date, date]:
    """Return the (start, end) dates available for a dataset."""
    ds = DATASETS[dataset_key]
    return date.fromisoformat(ds.period_start), resolve_period_end(ds.period_end, today)


def get_variable_meta(dataset_key: str, variable_id: str) -> VariableMeta:
    return VARIABLES[f"{dataset_key}/{variable_id}"]


def validate_request(
    dataset_key: object,
    variable_id: object,
    time_range: TimeRange,
    today: date | None = None,
) -> None:
    """Validate a dataset/variable/time selection against this configuration.

    Raises ``ValueError`` naming the offending field. Performs no network access.
    """
    for name, value in (("dataset_key", dataset_key), ("variable_id", variable_id)):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
    if dataset_key not in DATASETS:
        raise ValueError(
            f"dataset_key {dataset_key!r} is not a known dataset; choose one of {sorted(DATASETS)}"
        )
    if variable_id not in DATASETS[dataset_key].variables:
        raise ValueError(
            f"variable_id {variable_id!r} is not available for dataset {dataset_key!r}; "
            f"choose one of {list(DATASETS[dataset_key].variables)}"
        )
    start, end = dataset_period(dataset_key, today)
    if time_range.start_date > time_range.end_date or time_range.start_date < start or time_range.end_date > end:
        raise ValueError(
            f"TimeRange {time_range.start} to {time_range.end} is invalid; dataset "
            f"{dataset_key} is available from {start.isoformat()} to {end.isoformat()}"
        )


# --------------------------------------------------------------------------- self-check
_HEX = set("0123456789abcdefABCDEF")


def _is_hex_color(value: str) -> bool:
    return len(value) == 7 and value[0] == "#" and all(c in _HEX for c in value[1:])


def validate_config(
    datasets: dict | None = None,
    variables: dict | None = None,
    environments: dict | None = None,
    guided_flow: dict | None = None,
    demo_presets: list | None = None,
    alpha: float | None = None,
    colors: dict | None = None,
) -> None:
    """Check cross references and field constraints; raise ``ConfigError`` on any problem."""
    datasets = DATASETS if datasets is None else datasets
    variables = VARIABLES if variables is None else variables
    environments = ENVIRONMENTS if environments is None else environments
    guided_flow = GUIDED_FLOW if guided_flow is None else guided_flow
    demo_presets = DEMO_PRESETS if demo_presets is None else demo_presets
    alpha = ALPHA if alpha is None else alpha
    colors = SIGNIFICANCE_COLORS if colors is None else colors

    if not isinstance(alpha, float) or not 0.0 < alpha < 1.0:
        raise ConfigError(f"ALPHA must be a float in (0, 1), got {alpha!r}")
    for key in ("increasing", "decreasing", "none"):
        if key not in colors or not _is_hex_color(colors[key]):
            raise ConfigError(f"SIGNIFICANCE_COLORS[{key!r}] must be a #RRGGBB color")

    for key, label in environments.items():
        if not isinstance(label, str) or not 1 <= len(label) <= 50:
            raise ConfigError(f"ENVIRONMENTS[{key!r}] label must be 1-50 characters")

    for key, ds in datasets.items():
        if key != ds.short_name:
            raise ConfigError(f"DATASETS key {key!r} does not match short_name {ds.short_name!r}")
        for fld in ("short_name", "version", "provider", "title", "description", "period_start", "period_end"):
            if not getattr(ds, fld):
                raise ConfigError(f"DATASETS[{key!r}].{fld} must not be empty")
        if not ds.variables:
            raise ConfigError(f"DATASETS[{key!r}].variables must contain at least one variable")
        try:
            start = date.fromisoformat(ds.period_start)
            end = resolve_period_end(ds.period_end)
        except ValueError as exc:
            raise ConfigError(f"DATASETS[{key!r}] has an invalid period: {exc}") from exc
        if start > end:
            raise ConfigError(f"DATASETS[{key!r}] period_start is after period_end")
        for var_id in ds.variables:
            if f"{key}/{var_id}" not in variables:
                raise ConfigError(f"DATASETS[{key!r}] lists variable {var_id!r} with no VARIABLES entry")

    for vkey, meta in variables.items():
        ds_key = vkey.split("/", 1)[0]
        if ds_key not in datasets:
            raise ConfigError(f"VARIABLES[{vkey!r}] refers to unknown dataset {ds_key!r}")
        if vkey != f"{meta.dataset_key}/{meta.variable_id}":
            raise ConfigError(f"VARIABLES key {vkey!r} does not match its VariableMeta")
        if meta.category not in environments:
            raise ConfigError(f"VARIABLES[{vkey!r}].category {meta.category!r} is not in ENVIRONMENTS")
        for fld in ("long_name", "units"):
            if not getattr(meta, fld):
                raise ConfigError(f"VARIABLES[{vkey!r}].{fld} must not be empty")
        limits = {"short_description": 150, "plain_language": 300, "trend_direction_hint": 80}
        for fld, max_len in limits.items():
            text = getattr(meta, fld)
            if not text or len(text) > max_len:
                raise ConfigError(
                    f"VARIABLES[{vkey!r}].{fld} must be 1-{max_len} characters (got {len(text or '')})"
                )
        if len(meta.plain_language) < 200 or "\n" in meta.plain_language:
            raise ConfigError(
                f"VARIABLES[{vkey!r}].plain_language must be a single paragraph of 200-300 characters"
            )

    for env, keys in guided_flow.items():
        if env not in environments:
            raise ConfigError(f"GUIDED_FLOW category {env!r} is not in ENVIRONMENTS")
        for vkey in keys:
            if vkey not in variables:
                raise ConfigError(f"GUIDED_FLOW[{env!r}] refers to unknown variable {vkey!r}")

    if not 1 <= len(demo_presets) <= 20:
        raise ConfigError("DEMO_PRESETS must contain 1 to 20 presets")
    for preset in demo_presets:
        if f"{preset.dataset_key}/{preset.variable_id}" not in variables:
            raise ConfigError(f"DemoPreset {preset.name!r} refers to an unknown variable")
        for fld in ("name", "description", "expected_insight"):
            if not getattr(preset, fld):
                raise ConfigError(f"DemoPreset {preset.name!r}.{fld} must not be empty")
        try:
            validate_request(preset.dataset_key, preset.variable_id, preset.time_range)
        except ValueError as exc:
            raise ConfigError(f"DemoPreset {preset.name!r} is invalid: {exc}") from exc


validate_config()
