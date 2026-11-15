"""Variable discovery catalogue: categories, coverage, and trend-investigation questions.

Two kinds of entries:

* **Available** variables. Each one maps 1:1 to an entry in ``config.VARIABLES`` and can be
  retrieved by the analysis pipeline. Every name was checked against the dataset's
  OPeNDAP metadata and run through the pipeline on real data.
* **Requires additional dataset** variables. These are scientifically relevant, but no
  supported dataset provides them. They name the NASA dataset that would be needed and,
  where one exists, the closest supported variable. They can never be analyzed directly.

Nothing here says a variable *is* trending. Text describes why a variable is worth
testing; whether a trend exists is only reported from completed analyses.

The module validates itself at import time, like ``config``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config
from modules.errors import ConfigError

CATEGORIES: dict[str, tuple[str, str]] = {
    "climate": ("Climate", "Long-term averages of temperature and rainfall that define a region's climate."),
    "hydrology": ("Hydrology", "How water moves between the sky, the land, rivers, and the soil."),
    "atmosphere": ("Atmosphere", "The air itself: pressure, humidity, wind, and particles."),
    "ocean": ("Ocean", "The surface of the seas, which stores most of the planet's extra heat."),
    "land": ("Land", "The ground surface and the plants that cover it."),
}

LEVELS: dict[str, str] = {
    "beginner": "Familiar everyday quantity",
    "intermediate": "Needs a little background",
    "advanced": "Specialist quantity",
}

_MERRA2 = {
    "spatial_resolution": "0.5\u00b0 lat \u00d7 0.625\u00b0 lon (about 50 km)",
    "spatial_coverage": "Global",
    "temporal_resolution": "Monthly means",
    "source_type": "Reanalysis: a weather model continuously corrected with observations",
    "archive": "NASA GES DISC",
}

DATASET_COVERAGE: dict[str, dict[str, str]] = {
    "GPM_3IMERGM": {
        "spatial_resolution": "0.1\u00b0 \u00d7 0.1\u00b0 (about 10 km)",
        "spatial_coverage": "Global; most reliable between 60\u00b0S and 60\u00b0N",
        "temporal_resolution": "Monthly means",
        "source_type": "Satellite observations merged across the GPM constellation, gauge-adjusted",
        "archive": "NASA GES DISC",
    },
    "M2TMNXSLV": _MERRA2,
    "M2TMNXLND": {**_MERRA2, "spatial_coverage": "Global land only (ocean cells are empty)"},
    "M2TMNXFLX": _MERRA2,
    "M2TMNXAER": _MERRA2,
    "M2TMNXOCN": {**_MERRA2, "spatial_coverage": "Global open water only (land cells are empty)"},
}


# Measured end-to-end analysis time per year of monthly data (Nov 2026, home connection):
# GPM 10 years = 208 s; MERRA-2 10 years = 82 s. Used only for a rough wait estimate.
LOAD_SECONDS_PER_YEAR: dict[str, int] = {
    "GPM_3IMERGM": 21,
    "M2TMNXSLV": 8,
    "M2TMNXLND": 8,
    "M2TMNXFLX": 8,
    "M2TMNXAER": 8,
    "M2TMNXOCN": 8,
}


@dataclass(frozen=True)
class DatasetSuggestion:
    """A NASA dataset recommended for a variable that this app does not retrieve."""

    short_name: str
    title: str
    archive: str
    period: str
    note: str


@dataclass(frozen=True)
class AvailableEntry:
    common_name: str
    categories: tuple[str, ...]
    level: str
    why_trend: str
    keywords: tuple[str, ...] = ()
    other_datasets: tuple[DatasetSuggestion, ...] = ()


@dataclass(frozen=True)
class UnavailableEntry:
    entry_id: str
    common_name: str
    scientific_name: str
    categories: tuple[str, ...]
    level: str
    description: str
    plain_language: str
    typical_units: str
    why_trend: str
    reason_unavailable: str
    required_datasets: tuple[DatasetSuggestion, ...]
    closest_available: str | None = None  # key into config.VARIABLES
    keywords: tuple[str, ...] = field(default=())


_GLDAS = DatasetSuggestion(
    "GLDAS_NOAH025_M", "GLDAS Noah Land Surface Model L4 Monthly 0.25\u00b0", "NASA GES DISC",
    "1948 to present", "Finer 0.25\u00b0 soil moisture and runoff from a land model; same archive as MERRA-2.",
)
_MOD11C3 = DatasetSuggestion(
    "MOD11C3", "MODIS/Terra Land Surface Temperature Monthly 0.05\u00b0", "NASA LP DAAC",
    "2000 to present", "Direct satellite measurement of land surface temperature.",
)
_MUR = DatasetSuggestion(
    "MUR-JPL-L4-GLOB-v4.1", "GHRSST Level 4 MUR Global Sea Surface Temperature", "NASA PO.DAAC",
    "2002 to present", "Daily ~1 km satellite sea surface temperature; would need monthly averaging.",
)
_MOD13C2 = DatasetSuggestion(
    "MOD13C2", "MODIS/Terra Vegetation Indices Monthly 0.05\u00b0", "NASA LP DAAC",
    "2000 to present", "Satellite NDVI and EVI greenness indices.",
)

AVAILABLE: dict[str, AvailableEntry] = {
    "GPM_3IMERGM/precipitation": AvailableEntry(
        "Rainfall (satellite)", ("climate", "hydrology"), "beginner",
        "Rainfall controls water supply, floods, and droughts. Year-to-year swings are large, "
        "so a long record is needed to tell a real shift from natural variability.",
        ("rain", "precipitation", "snow", "drought", "flood", "wet"),
    ),
    "M2TMNXLND/PRECTOTLAND": AvailableEntry(
        "Rainfall over land (model)", ("hydrology", "climate"), "intermediate",
        "Covers 1980 onward, 20 years longer than satellite rainfall, and gives an independent "
        "second estimate. Agreement between the two strengthens any conclusion.",
        ("rain", "precipitation", "snow", "land", "drought"),
    ),
    "M2TMNXSLV/T2M": AvailableEntry(
        "Air temperature", ("climate", "atmosphere"), "beginner",
        "The most direct measure of warming or cooling where people live. Over decades it can "
        "show whether a region's average has moved beyond its usual year-to-year range.",
        ("temperature", "warming", "heat", "air", "climate"),
        (_MOD11C3,),
    ),
    "M2TMNXSLV/TS": AvailableEntry(
        "Surface temperature", ("land", "climate"), "beginner",
        "The ground or sea surface heats and cools faster than the air. Changes can point to "
        "drying soil, melting snow and ice, or urban heat.",
        ("temperature", "land surface temperature", "skin", "ground", "warming"),
        (_MOD11C3,),
    ),
    "M2TMNXSLV/QV2M": AvailableEntry(
        "Humidity near the ground", ("atmosphere",), "intermediate",
        "Warmer air can hold about 7% more water vapor per \u00b0C. Testing humidity alongside "
        "temperature shows whether the two are changing together.",
        ("humidity", "moisture", "water vapor", "muggy"),
    ),
    "M2TMNXSLV/TQV": AvailableEntry(
        "Atmospheric water vapor", ("atmosphere", "climate"), "intermediate",
        "Water vapor is the most abundant greenhouse gas and the fuel for heavy rain. A change in "
        "the total amount overhead is a key test of how the water cycle responds to warming.",
        ("water vapor", "humidity", "moisture", "precipitable water", "greenhouse"),
    ),
    "M2TMNXSLV/PS": AvailableEntry(
        "Surface pressure", ("atmosphere",), "advanced",
        "Mostly set by elevation, so trends are small. Persistent shifts can reflect changes in "
        "large-scale circulation.",
        ("pressure", "barometer", "air"),
    ),
    "M2TMNXSLV/SLP": AvailableEntry(
        "Sea-level pressure", ("atmosphere", "climate"), "intermediate",
        "Highs and lows steer storms. A long-term shift in sea-level pressure over a region can "
        "indicate a change in typical weather patterns and storm tracks.",
        ("pressure", "storms", "weather patterns", "high", "low"),
    ),
    "M2TMNXSLV/U10M": AvailableEntry(
        "East-west wind", ("atmosphere",), "advanced",
        "The west-to-east wind component reveals jet streams, trade winds, and monsoons. Testing it "
        "shows whether prevailing winds are strengthening, weakening, or reversing.",
        ("wind", "zonal", "trade winds", "westerlies"),
    ),
    "M2TMNXSLV/V10M": AvailableEntry(
        "North-south wind", ("atmosphere",), "advanced",
        "The south-to-north wind component carries heat and moisture toward the poles. Changes can "
        "indicate shifting storm paths.",
        ("wind", "meridional", "storm track"),
    ),
    "M2TMNXFLX/SPEED": AvailableEntry(
        "Wind speed", ("atmosphere",), "beginner",
        "Wind speed matters for wind power, waves, dust, and evaporation. Researchers have debated "
        "whether near-surface winds have slowed or sped up; your own region can be tested here.",
        ("wind", "speed", "gust", "wind energy", "stilling"),
    ),
    "M2TMNXLND/EVLAND": AvailableEntry(
        "Evaporation from land", ("hydrology", "land"), "intermediate",
        "Evaporation links soil water, plants, and rain. A change can mean a hotter surface, "
        "a different plant cover, or soil that has less water left to give.",
        ("evaporation", "evapotranspiration", "transpiration", "plants", "drying"),
        (_GLDAS,),
    ),
    "M2TMNXFLX/EVAP": AvailableEntry(
        "Evaporation (land and ocean)", ("hydrology", "ocean"), "intermediate",
        "Covers oceans as well as land. Ocean evaporation supplies most of the world's rain, so a "
        "change here can be tested against rainfall downwind.",
        ("evaporation", "ocean", "water cycle", "moisture"),
    ),
    "M2TMNXLND/RUNOFF": AvailableEntry(
        "Surface runoff", ("hydrology",), "intermediate",
        "The closest supported quantity to streamflow. It is modeled water leaving the surface, "
        "not river discharge, so treat a trend as a hint about rivers rather than a measurement.",
        ("runoff", "streamflow", "river", "flood", "discharge"),
        (_GLDAS,),
    ),
    "M2TMNXLND/GWETTOP": AvailableEntry(
        "Topsoil moisture", ("hydrology", "land"), "intermediate",
        "Topsoil dries quickly in heat waves and refills after rain. A long-term decline in a "
        "drought-prone region would be important for farming and wildfire risk.",
        ("soil moisture", "drought", "dry", "agriculture", "wildfire"),
        (_GLDAS,),
    ),
    "M2TMNXLND/GWETROOT": AvailableEntry(
        "Root-zone soil moisture", ("hydrology", "land"), "intermediate",
        "Deeper soil water changes slowly and shows lasting drought. It is what crops and forests "
        "rely on between rains.",
        ("soil moisture", "drought", "root zone", "crops", "forest"),
        (_GLDAS,),
    ),
    "M2TMNXLND/LAI": AvailableEntry(
        "Leaf cover (vegetation)", ("land",), "intermediate",
        "Leaf area tracks plant growth. Testing it can show greening from longer seasons or "
        "browning from drought. MERRA-2 values come from a model, so compare with satellite NDVI.",
        ("vegetation", "plants", "leaves", "greening", "forest", "ndvi"),
        (_MOD13C2,),
    ),
    "M2TMNXAER/TOTEXTTAU": AvailableEntry(
        "Haze and air particles", ("atmosphere",), "intermediate",
        "Aerosols affect health, sunlight, and clouds. Testing them can show the effect of pollution "
        "controls, growing cities, wildfires, or dust storms.",
        ("aerosol", "pollution", "smoke", "haze", "air quality", "aod"),
    ),
    "M2TMNXAER/DUEXTTAU": AvailableEntry(
        "Desert dust in the air", ("atmosphere",), "advanced",
        "Dust responds to drought, wind, and land use in source regions. It fertilizes oceans and "
        "rainforests far away.",
        ("dust", "sahara", "aerosol", "sand storm"),
    ),
    "M2TMNXOCN/TSKINWTR": AvailableEntry(
        "Sea surface temperature", ("ocean", "climate"), "intermediate",
        "Oceans absorb most of the planet's extra heat, and warm seas fuel hurricanes and coral "
        "bleaching. Use an ocean region; land cells have no value.",
        ("sea surface temperature", "sst", "ocean", "marine heatwave", "el nino"),
        (_MUR,),
    ),
}

UNAVAILABLE: list[UnavailableEntry] = [
    UnavailableEntry(
        "streamflow", "Streamflow", "River discharge", ("hydrology",), "beginner",
        "The volume of water flowing past a point in a river each second.",
        "Streamflow is how much water a river carries. It depends on rain, snowmelt, soil, and "
        "how much water people take out upstream.",
        "m\u00b3/s",
        "River flow integrates everything that happens in a watershed, so it is a sensitive "
        "indicator of water-cycle change.",
        "River discharge is measured at gauges or along river lines, not on the grids this app "
        "averages over regions.",
        (
            DatasetSuggestion(
                "SWOT_L2_HR_RiverSP_2.0", "SWOT Level 2 River Single-Pass Vector Data", "NASA PO.DAAC",
                "Dec 2022 to present", "Satellite river height and discharge; too short for long-term trends yet.",
            ),
        ),
        closest_available="M2TMNXLND/RUNOFF",
        keywords=("river", "discharge", "flow", "flood"),
    ),
    UnavailableEntry(
        "sea_surface_salinity", "Ocean salinity", "Sea surface salinity", ("ocean",), "intermediate",
        "The amount of dissolved salt in the top layer of the ocean.",
        "Salinity is how salty seawater is. Rain and rivers make it fresher. Evaporation makes it "
        "saltier, so it records the water cycle over the ocean.",
        "PSU (practical salinity units)",
        "Salty regions getting saltier and fresh regions getting fresher is a predicted signature "
        "of an intensifying water cycle, which you would need salinity data to test.",
        "None of the supported datasets include salinity.",
        (
            DatasetSuggestion(
                "SMAP_JPL_L3_SSS_CAP_MONTHLY_V5", "JPL SMAP Level 3 Sea Surface Salinity Monthly V5",
                "NASA PO.DAAC", "Apr 2015 to present", "Monthly satellite salinity maps.",
            ),
        ),
        keywords=("salt", "salinity", "ocean", "sss"),
    ),
    UnavailableEntry(
        "satellite_sst", "Satellite sea surface temperature", "Foundation sea surface temperature",
        ("ocean",), "intermediate",
        "Ocean temperature just below the surface, measured from satellites at about 1 km.",
        "This is the ocean surface temperature seen directly by satellites, in much finer detail "
        "than the model-based value this app supports.",
        "\u00b0C",
        "Fine detail matters for coasts, coral reefs, and marine heatwaves.",
        "The supported value comes from the MERRA-2 model at about 50 km resolution.",
        (_MUR,),
        closest_available="M2TMNXOCN/TSKINWTR",
        keywords=("sst", "ocean", "satellite", "coral", "marine heatwave"),
    ),
    UnavailableEntry(
        "ndvi", "Vegetation greenness (NDVI)", "Normalized Difference Vegetation Index",
        ("land",), "intermediate",
        "A satellite index of how green and dense the vegetation is, from -1 to 1.",
        "NDVI compares red and near-infrared light reflected by plants. Healthy, dense vegetation "
        "has a high value. Bare ground and water are low.",
        "unitless (-1 to 1)",
        "NDVI is the standard satellite measure for greening and browning, independent of models.",
        "Needs MODIS land products, which are on a different archive and grid.",
        (_MOD13C2,),
        closest_available="M2TMNXLND/LAI",
        keywords=("vegetation", "greening", "plants", "ndvi", "evi"),
    ),
    UnavailableEntry(
        "satellite_lst", "Satellite land surface temperature", "Land surface temperature",
        ("land", "climate"), "beginner",
        "The temperature of the land surface measured from satellites at about 5 km.",
        "This is how hot the ground looks from space, measured day and night by the MODIS "
        "instrument.",
        "\u00b0C",
        "An observation-based check on the model surface temperature, with finer detail over "
        "cities and mountains.",
        "Needs MODIS land products, which are on a different archive and grid.",
        (_MOD11C3,),
        closest_available="M2TMNXSLV/TS",
        keywords=("temperature", "land surface temperature", "lst", "urban heat"),
    ),
    UnavailableEntry(
        "water_storage", "Total water storage", "Terrestrial water storage anomaly",
        ("hydrology", "land"), "advanced",
        "All water stored on and under the land: groundwater, soil water, snow, lakes, and ice.",
        "GRACE satellites weigh the water in a region by measuring tiny changes in gravity, "
        "including groundwater that no other satellite can see.",
        "cm equivalent water height",
        "The main way to test whether groundwater is being depleted across a whole region.",
        "Needs GRACE gravity data, which is on a different archive and grid.",
        (
            DatasetSuggestion(
                "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4", "JPL GRACE and GRACE-FO Mascon Grid",
                "NASA PO.DAAC", "Apr 2002 to present", "Monthly water storage anomalies, ~300 km effective resolution.",
            ),
        ),
        closest_available="M2TMNXLND/GWETROOT",
        keywords=("groundwater", "grace", "aquifer", "water storage"),
    ),
]


@dataclass(frozen=True)
class TrendQuestion:
    question: str
    why: str
    region_name: str
    start_year: int
    end_year: int
    variable_key: str | None = None  # available variable to analyze
    unavailable_id: str | None = None  # set instead when the needed data is not supported


_MERRA_START, _MERRA_END = 2014, 2023

QUESTIONS: list[TrendQuestion] = [
    TrendQuestion(
        "Is rainfall increasing or decreasing in California?",
        "California swings between drought and floods. A trend test shows whether the average has "
        "shifted, or whether the swings dominate.",
        "California", _MERRA_START, _MERRA_END, variable_key="GPM_3IMERGM/precipitation",
    ),
    TrendQuestion(
        "Is land surface temperature increasing in the Arctic?",
        "Snow and ice loss can heat the surface itself. Compare the result with air temperature "
        "for the same region.",
        "Arctic (north of 66.5\u00b0N)", _MERRA_START, _MERRA_END, variable_key="M2TMNXSLV/TS",
    ),
    TrendQuestion(
        "Is evaporation changing in the Amazon Basin?",
        "The rainforest recycles its own rain through evaporation. A change could affect rainfall "
        "across South America.",
        "Amazon Basin", _MERRA_START, _MERRA_END, variable_key="M2TMNXLND/EVLAND",
    ),
    TrendQuestion(
        "Are ocean temperatures increasing in the tropical Pacific?",
        "The Ni\u00f1o 3.4 region is where El Ni\u00f1o is measured. Use anomalies and a long period so "
        "El Ni\u00f1o and La Ni\u00f1a years average out.",
        "Tropical Pacific (Ni\u00f1o 3.4)", _MERRA_START, _MERRA_END, variable_key="M2TMNXOCN/TSKINWTR",
    ),
    TrendQuestion(
        "Is soil moisture decreasing in the drought-prone Sahel?",
        "The Sahel suffered severe droughts in the 1970s-80s. Root-zone moisture shows whether "
        "conditions for crops are changing now.",
        "Sahel", _MERRA_START, _MERRA_END, variable_key="M2TMNXLND/GWETROOT",
    ),
    TrendQuestion(
        "Are atmospheric water vapor levels changing over the Arctic?",
        "More vapor traps more heat and can bring more snow and rain. Compare with the Arctic "
        "temperature result.",
        "Arctic (north of 66.5\u00b0N)", _MERRA_START, _MERRA_END, variable_key="M2TMNXSLV/TQV",
    ),
    TrendQuestion(
        "Are wind patterns changing over the North Atlantic?",
        "North Atlantic winds drive storms toward Europe and power offshore wind farms.",
        "North Atlantic", _MERRA_START, _MERRA_END, variable_key="M2TMNXFLX/SPEED",
    ),
    TrendQuestion(
        "Is desert dust over the Sahel changing?",
        "Dust from the Sahara and Sahel crosses the Atlantic. It responds to drought, wind, and land use.",
        "Sahel", _MERRA_START, _MERRA_END, variable_key="M2TMNXAER/DUEXTTAU",
    ),
    TrendQuestion(
        "Is the Amazon becoming more or less leafy?",
        "Leaf cover reflects forest health. This is a model estimate; satellite NDVI would be the "
        "independent check.",
        "Amazon Basin", _MERRA_START, _MERRA_END, variable_key="M2TMNXLND/LAI",
    ),
    TrendQuestion(
        "Is river streamflow changing in California?",
        "River flow is not in the supported datasets. Surface runoff is the closest modeled quantity.",
        "California", _MERRA_START, _MERRA_END, unavailable_id="streamflow",
    ),
    TrendQuestion(
        "Is the North Atlantic getting fresher or saltier?",
        "Melting ice and changing rain could alter salinity. This needs satellite salinity data, "
        "which is not supported yet.",
        "North Atlantic", 2016, 2023, unavailable_id="sea_surface_salinity",
    ),
]


def unavailable_by_id(entry_id: str) -> UnavailableEntry:
    for entry in UNAVAILABLE:
        if entry.entry_id == entry_id:
            return entry
    raise KeyError(entry_id)


def validate_catalogue() -> None:
    """Every supported variable is catalogued, and every reference resolves."""
    missing = set(config.VARIABLES) - set(AVAILABLE)
    extra = set(AVAILABLE) - set(config.VARIABLES)
    if missing:
        raise ConfigError(f"Variables missing from the discovery catalogue: {sorted(missing)}")
    if extra:
        raise ConfigError(f"Catalogue lists variables the pipeline cannot retrieve: {sorted(extra)}")
    for key in config.DATASETS:
        if key not in DATASET_COVERAGE:
            raise ConfigError(f"DATASET_COVERAGE has no entry for dataset {key!r}")
        if key not in LOAD_SECONDS_PER_YEAR:
            raise ConfigError(f"LOAD_SECONDS_PER_YEAR has no entry for dataset {key!r}")
    ids = [e.entry_id for e in UNAVAILABLE]
    if len(ids) != len(set(ids)):
        raise ConfigError("UNAVAILABLE entry ids must be unique")
    entries = [(k, e.categories, e.level) for k, e in AVAILABLE.items()]
    entries += [(e.entry_id, e.categories, e.level) for e in UNAVAILABLE]
    for name, categories, level in entries:
        if not categories or any(c not in CATEGORIES for c in categories):
            raise ConfigError(f"Catalogue entry {name!r} has an unknown category: {categories}")
        if level not in LEVELS:
            raise ConfigError(f"Catalogue entry {name!r} has an unknown level {level!r}")
    for entry in UNAVAILABLE:
        if entry.closest_available and entry.closest_available not in config.VARIABLES:
            raise ConfigError(f"{entry.entry_id!r} closest_available is not a supported variable")
        if not entry.required_datasets:
            raise ConfigError(f"{entry.entry_id!r} must recommend at least one dataset")
    for q in QUESTIONS:
        if (q.variable_key is None) == (q.unavailable_id is None):
            raise ConfigError(f"Question {q.question!r} needs exactly one of variable_key / unavailable_id")
        if q.variable_key and q.variable_key not in config.VARIABLES:
            raise ConfigError(f"Question {q.question!r} refers to unknown variable {q.variable_key!r}")
        if q.unavailable_id and q.unavailable_id not in ids:
            raise ConfigError(f"Question {q.question!r} refers to unknown entry {q.unavailable_id!r}")
        if q.region_name not in config.PRESET_REGIONS:
            raise ConfigError(f"Question {q.question!r} refers to unknown region {q.region_name!r}")
        if q.start_year > q.end_year:
            raise ConfigError(f"Question {q.question!r} has start_year after end_year")
        if q.variable_key:
            dataset_key = q.variable_key.split("/", 1)[0]
            start, end = config.dataset_period(dataset_key)
            if q.start_year < start.year or q.end_year > end.year:
                raise ConfigError(f"Question {q.question!r} years fall outside {dataset_key} coverage")


validate_catalogue()
